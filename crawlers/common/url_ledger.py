"""
Module quản lý URL Ledger & Cơ chế Re-crawl 21 ngày cho hệ thống VN-IT-Job-Mining.

Cung cấp các hàm chuẩn hóa URL, băm khối Container HTML sạch (tránh false positive),
quản lý trạng thái vòng đời (PENDING, DONE, RECHECK_DUE, FAILED, CLOSED),
và kiểm tra điều kiện re-crawl sau 21 ngày.
"""

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class UrlLedgerRecord:
    url_hash: str
    canonical_url: str
    source: str
    job_id: str
    discovered_at: str
    status: str = "PENDING"  # PENDING, DONE, RECHECK_DUE, FAILED, CLOSED
    preliminary_title: Optional[str] = None
    preliminary_company: Optional[str] = None
    identity_key: Optional[str] = None
    last_seen_at: Optional[str] = None
    last_scraped_at: Optional[str] = None
    content_hash: Optional[str] = None
    latest_version: int = 0
    repost_of_url_hash: Optional[str] = None
    error_log: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UrlLedgerRecord":
        import dataclasses
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        clean_data = {k: v for k, v in data.items() if k in valid_fields}
        if "last_crawled_at" in data and not clean_data.get("last_scraped_at"):
            clean_data["last_scraped_at"] = data["last_crawled_at"]
        return cls(**clean_data)


def clean_canonical_url(raw_url: str) -> str:
    """
    Làm sạch URL:
    - Loại bỏ fragment (#...)
    - Loại bỏ các tham số tracking: utm_*, ref, source, u_sr_id, ta_source, fbclid, gclid
    - Chuẩn hóa chữ thường trên hostname
    """
    if not raw_url:
        return ""
    
    parsed = urlparse(raw_url.strip())
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    
    # Danh sách các query param cần lọc bỏ
    tracking_prefixes = ("utm_", "fbclid", "gclid", "ref", "source", "u_sr_id", "ta_source")
    clean_params = {
        k: v for k, v in query_params.items()
        if not any(k.lower().startswith(prefix) for prefix in tracking_prefixes)
    }
    
    # Re-encode query
    clean_query = urlencode(clean_params, doseq=True)
    
    clean_url = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        clean_query,
        ""  # Xóa fragment #...
    ))
    return clean_url.rstrip("/")


def generate_url_hash(canonical_url: str) -> str:
    """Sinh mã MD5 từ canonical URL để làm khóa duy nhất."""
    return hashlib.md5(canonical_url.strip().encode("utf-8")).hexdigest()


def generate_identity_key(company: str, title: str) -> str:
    """
    Sinh identity key: slugify(company + title)
    Dùng để phát hiện tin đăng lại (repost) hoặc đối chiếu liên sàn.
    """
    def _slugify(text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "_", text)
        return text

    c_slug = _slugify(company)
    t_slug = _slugify(title)
    return f"{c_slug}__{t_slug}"


def calculate_container_html_hash(html_content: str, container_selector: str = "body") -> str:
    """
    Băm HTML khối nội dung chính, tự động loại bỏ các thành phần rác động:
    - Thẻ <script>, <style>, <iframe>, <noscript>, <svg>
    - Số lượt xem (views), timestamp hiển thị
    - Thuộc tính ngẫu nhiên (CSRF token, nonce)
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")
    target = soup.select_one(container_selector) or soup.body or soup

    # Xóa sạch các thẻ động gây nhảy hash oan
    for tag in target(["script", "style", "iframe", "noscript", "svg"]):
        tag.decompose()

    # Chuẩn hóa khoảng trắng
    clean_text = re.sub(r"\s+", " ", target.get_text(separator=" ", strip=True))
    return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()


def is_due_for_recrawl(last_scraped_at: Optional[str], days: int = 21) -> bool:
    """
    Kiểm tra xem bài đăng đã đến hạn cào lại hay chưa (mặc định 21 ngày).
    - Nếu chưa từng cào (None) -> True (cần cào)
    - Nếu đã cào >= 21 ngày -> True
    - Nếu cào < 21 ngày -> False (skip)
    """
    if not last_scraped_at:
        return True

    try:
        if "T" in last_scraped_at:
            scraped_dt = datetime.fromisoformat(last_scraped_at.replace("Z", "+00:00"))
        else:
            scraped_dt = datetime.strptime(last_scraped_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            
        now_dt = datetime.now(timezone.utc)
        diff_days = (now_dt - scraped_dt).total_seconds() / 86400.0
        return diff_days >= days
    except Exception as e:
        logger.warning(f"Error parsing last_scraped_at '{last_scraped_at}': {e}. Treating as due for recrawl.")
        return True


class UrlLedger:
    """
    Quản lý danh sách URL Manifests và State Catalog cho từng nguồn tuyển dụng.
    Lưu trữ cục bộ dưới dạng JSONL và có thể sync lên MinIO.
    """

    def __init__(self, source: str, storage_dir: Optional[str] = None):
        self.source = source.lower().strip()
        # Chuẩn hóa cấu trúc: data/<source>/url_ledger
        target_dir = Path(storage_dir) if storage_dir else Path(f"data/{self.source}/url_ledger")
        self.base_dir = target_dir
        self.manifests_dir = self.base_dir / "manifests"
        self.catalog_file = self.base_dir / "catalog_master.json"

        # Tự động di chuyển dữ liệu cũ từ data/url_ledger/<source> nếu có
        legacy_dir = Path(f"data/url_ledger/{self.source}")
        if legacy_dir.exists() and not self.catalog_file.exists():
            legacy_catalog = legacy_dir / "catalog_master.json"
            if legacy_catalog.exists():
                self.base_dir.mkdir(parents=True, exist_ok=True)
                import shutil
                try:
                    shutil.copy2(legacy_catalog, self.catalog_file)
                    legacy_manifests = legacy_dir / "manifests"
                    if legacy_manifests.exists():
                        self.manifests_dir.mkdir(parents=True, exist_ok=True)
                        for m_file in legacy_manifests.glob("*.jsonl"):
                            shutil.copy2(m_file, self.manifests_dir / m_file.name)
                    logger.info(f"Đã di chuyển dữ liệu URL Ledger từ {legacy_dir} sang {self.base_dir}")
                except Exception as e:
                    logger.warning(f"Lỗi khi di chuyển dữ liệu từ {legacy_dir}: {e}")

        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.records: Dict[str, Dict[str, Any]] = self._load_catalog()

    def _load_catalog(self) -> Dict[str, Dict[str, Any]]:
        if self.catalog_file.exists():
            try:
                with open(self.catalog_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load catalog {self.catalog_file}: {e}")
        return {}

    def save_catalog(self):
        """Lưu toàn bộ catalog xuống disk."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.catalog_file, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    def register_url(
        self,
        raw_url: str,
        job_id: str,
        preliminary_title: Optional[str] = None,
        preliminary_company: Optional[str] = None,
    ) -> UrlLedgerRecord:
        """
        Ghi nhận một URL mới phát hiện từ Phase 1 (Discovery).
        Nếu URL đã có, chỉ cập nhật last_seen_at.
        """
        canonical = clean_canonical_url(raw_url)
        url_hash = generate_url_hash(canonical)
        now_iso = datetime.now(timezone.utc).isoformat()
        identity_key = generate_identity_key(preliminary_company or "", preliminary_title or "")

        if url_hash in self.records:
            rec_dict = self.records[url_hash]
            rec_dict["last_seen_at"] = now_iso
            # Tự động cập nhật tiêu đề / công ty nếu trước đó bị rỗng
            if preliminary_title and not rec_dict.get("preliminary_title"):
                rec_dict["preliminary_title"] = preliminary_title
            if preliminary_company and not rec_dict.get("preliminary_company"):
                rec_dict["preliminary_company"] = preliminary_company
            # Nếu đã cào nhưng đã quá 21 ngày thì chuyển sang RECHECK_DUE
            scraped_time = rec_dict.get("last_scraped_at") or rec_dict.get("last_crawled_at")
            if rec_dict.get("status") == "DONE" and is_due_for_recrawl(scraped_time, days=21):
                rec_dict["status"] = "RECHECK_DUE"
            return UrlLedgerRecord.from_dict(rec_dict)

        # URL mới hoàn toàn
        new_record = UrlLedgerRecord(
            url_hash=url_hash,
            canonical_url=canonical,
            source=self.source,
            job_id=job_id,
            discovered_at=now_iso,
            status="PENDING",
            preliminary_title=preliminary_title,
            preliminary_company=preliminary_company,
            identity_key=identity_key,
            last_seen_at=now_iso,
        )
        self.records[url_hash] = new_record.to_dict()
        return new_record

    def export_daily_manifest(self, date_str: Optional[str] = None) -> Path:
        """Xuất các link phát hiện ra file manifest JSONL của ngày hôm đó."""
        d_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        manifest_path = self.manifests_dir / f"manifest_{d_str}.jsonl"

        with open(manifest_path, "w", encoding="utf-8") as f:
            for rec in self.records.values():
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(self.records)} records to {manifest_path}")
        return manifest_path

    def get_pending_or_due_records(self, recheck_days: int = 21) -> List[Dict[str, Any]]:
        """Lọc danh sách các link cần cào chi tiết ở Phase 2."""
        items = []
        for rec in self.records.values():
            status = rec.get("status")
            if status == "PENDING" or status == "RECHECK_DUE":
                items.append(rec)
            elif status == "DONE" and is_due_for_recrawl(rec.get("last_scraped_at"), days=recheck_days):
                rec["status"] = "RECHECK_DUE"
                items.append(rec)
        return items

    def mark_done(
        self,
        url_hash: str,
        content_hash: str,
        new_version: Optional[int] = None,
        repost_of_url_hash: Optional[str] = None,
    ):
        """Cập nhật trạng thái link thành DONE."""
        if url_hash in self.records:
            now_iso = datetime.now(timezone.utc).isoformat()
            rec = self.records[url_hash]
            rec["status"] = "DONE"
            rec["last_scraped_at"] = now_iso
            rec["content_hash"] = content_hash
            if new_version is not None:
                rec["latest_version"] = new_version
            if repost_of_url_hash:
                rec["repost_of_url_hash"] = repost_of_url_hash
            rec["error_log"] = None

    def mark_failed(self, url_hash: str, error_message: str):
        """Đánh dấu link bị cào lỗi (Safe Skip)."""
        if url_hash in self.records:
            rec = self.records[url_hash]
            rec["status"] = "FAILED"
            rec["error_log"] = str(error_message)
            rec["retry_count"] = rec.get("retry_count", 0) + 1

    def mark_closed(self, url_hash: str):
        """Đánh dấu link đã bị gỡ hoặc 404."""
        if url_hash in self.records:
            self.records[url_hash]["status"] = "CLOSED"

    def find_by_content_hash(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Tìm bài viết đã có content_hash tương tự để phát hiện Repost."""
        if not content_hash:
            return None
        for rec in self.records.values():
            if rec.get("content_hash") == content_hash and rec.get("status") == "DONE":
                return rec
        return None

    def sync_to_minio(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ) -> bool:
        """
        Đồng bộ URL Ledger (catalog_master.json và manifests/*.jsonl) lên MinIO / S3.
        Đích: minio://{bucket_name}/url_ledger/{source}/
        """
        import os
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass

        bucket = (
            bucket_name
            or os.getenv("S3_BUCKET_NAME")
            or os.getenv("R2_BUCKET_NAME")
            or os.getenv("MINIO_BUCKET")
            or os.getenv("S3_BUCKET")
            or "vn-it-jobs"
        )
        endpoint = (
            endpoint_url
            or os.getenv("S3_ENDPOINT_URL")
            or os.getenv("R2_ENDPOINT_URL")
            or os.getenv("MINIO_ENDPOINT")
            or "http://localhost:9000"
        )
        ak = (
            access_key
            or os.getenv("AWS_ACCESS_KEY_ID")
            or os.getenv("R2_ACCESS_KEY_ID")
            or os.getenv("MINIO_ROOT_USER")
            or "minioadmin"
        )
        sk = (
            secret_key
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or os.getenv("R2_SECRET_ACCESS_KEY")
            or os.getenv("MINIO_ROOT_PASSWORD")
            or "minioadmin"
        )
        region = "auto" if "r2.cloudflarestorage.com" in endpoint else os.getenv("AWS_REGION", "us-east-1")

        try:
            import boto3
            from botocore.client import Config

            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=ak,
                aws_secret_access_key=sk,
                config=Config(signature_version="s3v4", connect_timeout=3, retries={"max_attempts": 2}),
                region_name=region,
            )

            # Đảm bảo bucket tồn tại
            try:
                s3.head_bucket(Bucket=bucket)
            except Exception:
                try:
                    s3.create_bucket(Bucket=bucket)
                except Exception as b_exc:
                    logger.debug(f"Bucket {bucket} create/head check: {b_exc}")

            storage_label = "Cloudflare R2" if "r2.cloudflarestorage.com" in endpoint else "MinIO"

            # Upload catalog_master.json — guard: KHÔNG cho catalog RỖNG ghi đè catalog
            # (đã có) trên MinIO, chống runner làm mất sổ cái của source khác/đã có dữ liệu.
            local_records = self._load_catalog()
            if not local_records:
                logger.warning(
                    f"[{storage_label}] Bỏ sync catalog {self.source}: catalog local rỗng "
                    f"(tránh ghi đè ledger đã có)."
                )
                return False
            if self.catalog_file.exists():
                key = f"url_ledger/{self.source}/catalog_master.json"
                s3.upload_file(str(self.catalog_file), bucket, key)
                logger.info(f"[{storage_label}] Đã đồng bộ catalog ({len(local_records)} records) lên s3://{bucket}/{key}")

            # Upload all manifest files
            manifest_count = 0
            for m_path in self.manifests_dir.glob("*.jsonl"):
                key = f"url_ledger/{self.source}/manifests/{m_path.name}"
                s3.upload_file(str(m_path), bucket, key)
                manifest_count += 1

            logger.info(f"[{storage_label}] Đã đồng bộ thành công {manifest_count} manifests lên s3://{bucket}/url_ledger/{self.source}/manifests/")
            return True
        except Exception as exc:
            logger.warning(f"[{storage_label}] Không thể đồng bộ URL Ledger lên ({endpoint}): {exc}. Dữ liệu cục bộ vẫn an toàn.")
            return False

