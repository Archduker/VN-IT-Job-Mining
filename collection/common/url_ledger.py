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
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

try:
    import fcntl
except ImportError:
    fcntl = None

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@contextmanager
def file_lock(lock_path: Path, timeout: float = 10.0):
    """Context manager khóa file an toàn chống xung đột giữa các tiến trình."""
    if fcntl is None:
        yield
        return

    lock_file = open(lock_path, "a")
    start_time = time.time()
    locked = False
    while True:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            break
        except (BlockingIOError, IOError):
            if time.time() - start_time > timeout:
                logger.warning("Timeout (%.1fs) chờ lock trên %s. Tiếp tục xử lý.", timeout, lock_path)
                break
            time.sleep(0.05)
    try:
        yield
    finally:
        if locked:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
            except Exception:
                pass
        try:
            lock_file.close()
        except Exception:
            pass


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
    tracking_prefixes = ("utm_", "fbclid", "gclid", "ref", "source", "u_sr_id", "ta_source", "traceinfo")
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


def calculate_json_canonical_hash(
    payload: Any,
    exclude_keys: Optional[List[str]] = None,
) -> str:
    """
    Băm mã SHA-256 trên cấu trúc JSON/Dictionary sau khi đã chuẩn hóa khóa (Canonical JSON).
    - Tự động sắp xếp khóa (sort_keys=True) để bảo đảm thứ tự không ảnh hưởng mã băm.
    - Loại trừ các trường động hoặc metadata nếu được chỉ định trong exclude_keys (ví dụ: scraped_at, runtime).
    """
    if payload is None:
        return ""

    exclude = set(exclude_keys or ["scraped_at", "version", "content_hash", "crawler_version", "scraper_version"])

    def _filter_obj(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _filter_obj(v) for k, v in obj.items() if k not in exclude}
        elif isinstance(obj, list):
            return [_filter_obj(x) for x in obj]
        return obj

    filtered = _filter_obj(payload)
    try:
        canonical_str = json.dumps(filtered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    except Exception as exc:
        logger.warning(f"Lỗi khi canonicalize JSON hash: {exc}")
        return ""


def calculate_json_field_hashes(payload: Dict[str, Any]) -> Dict[str, str]:
    """
    Băm riêng biệt từng trường/khối nghiệp vụ trong đối tượng JSON (Granular Field Hashes):
    Ví dụ: salary, deadline, requirements, description, benefits, skills, location.
    Giúp định vị chính xác trường nào bị chỉnh sửa khi so sánh giữa 2 phiên bản.
    """
    if not isinstance(payload, dict):
        return {}

    field_hashes: Dict[str, str] = {}
    for key, val in payload.items():
        if key in ["scraped_at", "version", "content_hash", "raw_html"]:
            continue
        try:
            if isinstance(val, (dict, list)):
                norm_str = json.dumps(val, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            else:
                norm_str = re.sub(r"\s+", " ", str(val).strip())
            field_hashes[key] = hashlib.sha256(norm_str.encode("utf-8")).hexdigest()
        except Exception:
            continue
    return field_hashes


def diff_json_versions(old_payload: Dict[str, Any], new_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    So sánh đối chiếu chi tiết giữa 2 phiên bản JSON (v1 vs v2) để chỉ ra cụ thể:
    - Các trường bị sửa đổi giá trị (changed)
    - Các trường mới được thêm vào (added)
    - Các trường bị xóa bớt (removed)
    """
    ignore_keys = {"scraped_at", "version", "content_hash", "crawler_version", "scraper_version", "raw_html"}
    old_filtered = {k: v for k, v in (old_payload or {}).items() if k not in ignore_keys}
    new_filtered = {k: v for k, v in (new_payload or {}).items() if k not in ignore_keys}

    all_keys = set(old_filtered.keys()) | set(new_filtered.keys())
    changed: Dict[str, Dict[str, Any]] = {}
    added: Dict[str, Any] = {}
    removed: Dict[str, Any] = {}

    for k in sorted(all_keys):
        if k not in old_filtered:
            added[k] = new_filtered[k]
        elif k not in new_filtered:
            removed[k] = old_filtered[k]
        else:
            v_old = old_filtered[k]
            v_new = new_filtered[k]
            if v_old != v_new:
                changed[k] = {"before": v_old, "after": v_new}

    is_modified = bool(changed or added or removed)
    changed_fields = list(changed.keys()) + list(added.keys()) + list(removed.keys())

    return {
        "is_modified": is_modified,
        "changed_fields": changed_fields,
        "diff": {
            "changed": changed,
            "added": added,
            "removed": removed,
        },
    }


def calculate_container_html_hash(html_content: str, container_selector: str = "body") -> str:
    """
    [Legacy / Backwards Compatible]
    Băm HTML khối nội dung chính, tự động loại bỏ các thành phần rác động.
    Khuyến nghị: Với kiến trúc mới, hãy lưu Raw HTML trước, parse sang JSON rồi dùng
    `calculate_json_canonical_hash()` để băm chuẩn xác trên dữ liệu nghiệp vụ.
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
        if storage_dir:
            target_dir = Path(storage_dir)
            if not target_dir.is_absolute():
                target_dir = PROJECT_ROOT / target_dir
        else:
            target_dir = PROJECT_ROOT / f"data/{self.source}/url_ledger"

        self.base_dir = target_dir
        self.manifests_dir = self.base_dir / "manifests"
        self.catalog_file = self.base_dir / "catalog_master.json"

        # Tự động di chuyển dữ liệu cũ từ data/url_ledger/<source> nếu có
        legacy_dir = PROJECT_ROOT / f"data/url_ledger/{self.source}"
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
        self.by_job_id: Dict[str, str] = self._build_job_id_index()

    def _build_job_id_index(self) -> Dict[str, str]:
        """Xây dựng chỉ mục tra cứu nhanh job_id -> url_hash phục vụ kiểm tra trùng lặp Tầng 2."""
        index: Dict[str, str] = {}
        for u_hash, rec in self.records.items():
            jid = str(rec.get("job_id", "")).strip()
            if jid:
                index[jid] = u_hash
        return index

    def _load_catalog(self) -> Dict[str, Dict[str, Any]]:
        if self.catalog_file.exists():
            try:
                with open(self.catalog_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load catalog {self.catalog_file}: {e}")
        return {}

    def reload(self) -> None:
        """Nạp lại trạng thái mới nhất từ disk (cho Multi-Worker song song)."""
        self.records = self._load_catalog()
        self.by_job_id = self._build_job_id_index()

    def save_catalog(self):
        """Lưu toàn bộ catalog xuống disk với cơ chế FileLock và Ghi Nguyên Tử (Atomic Write) hỗ trợ Multi-Worker."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        lock_file = self.catalog_file.with_suffix(".lock")

        with file_lock(lock_file, timeout=15.0):
            # Hợp nhất an toàn (Merge) với dữ liệu từ các worker khác trên disk nếu có
            if self.catalog_file.exists():
                try:
                    with open(self.catalog_file, "r", encoding="utf-8") as f:
                        disk_records = json.load(f)
                    for k, v in self.records.items():
                        if k not in disk_records:
                            disk_records[k] = v
                        else:
                            disk_rec = disk_records[k]
                            # Nếu local đã cào xong (DONE), ưu tiên giữ DONE
                            if v.get("status") == "DONE":
                                disk_records[k] = v
                            elif v.get("last_scraped_at") and (not disk_rec.get("last_scraped_at") or v["last_scraped_at"] > disk_rec.get("last_scraped_at", "")):
                                disk_records[k] = v
                    self.records = disk_records
                    self.by_job_id = self._build_job_id_index()
                except Exception:
                    pass

            temp_file = self.catalog_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
            temp_file.replace(self.catalog_file)

            try:
                import pandas as pd
                parquet_file = self.base_dir / "catalog_master.parquet"
                temp_parquet = parquet_file.with_suffix(".tmp")
                pd.DataFrame(list(self.records.values())).to_parquet(temp_parquet, index=False)
                temp_parquet.replace(parquet_file)
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """Thống kê tổng quan số lượng URL theo trạng thái."""
        status_counts: Dict[str, int] = {}
        for r in self.records.values():
            st = r.get("status", "UNKNOWN")
            status_counts[st] = status_counts.get(st, 0) + 1
        return {
            "source": self.source,
            "total_urls": len(self.records),
            "by_status": status_counts,
        }

    def check_duplicate(
        self,
        raw_url: str,
        job_id: Optional[str] = None,
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Kiểm tra trùng lặp theo 2 tầng khóa:
        - Tầng 1: URL Hash chuẩn hóa (clean_canonical_url -> MD5)
        - Tầng 2: Job ID duy nhất do sàn cấp

        Returns:
            (is_duplicate: bool, match_type: str, existing_record_dict: Optional[dict])
            match_type: 'URL_HASH', 'JOB_ID', hoặc 'NONE'
        """
        canonical = clean_canonical_url(raw_url)
        u_hash = generate_url_hash(canonical)

        # 1. Trùng theo URL Hash
        if u_hash in self.records:
            return True, "URL_HASH", self.records[u_hash]

        # 2. Trùng theo Job ID
        jid_str = str(job_id).strip() if job_id else ""
        if jid_str and jid_str in self.by_job_id:
            matched_hash = self.by_job_id[jid_str]
            if matched_hash in self.records:
                return True, "JOB_ID", self.records[matched_hash]

        return False, "NONE", None

    def is_known(self, raw_url: str, job_id: Optional[str] = None) -> bool:
        """Kiểm tra xem URL hoặc Job ID đã từng xuất hiện trong hệ thống hay chưa."""
        is_dup, _, _ = self.check_duplicate(raw_url, job_id=job_id)
        return is_dup

    def get_record(
        self,
        raw_url: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Optional[UrlLedgerRecord]:
        """Lấy bản ghi từ URL hoặc Job ID nếu có."""
        if raw_url:
            _, _, rec = self.check_duplicate(raw_url, job_id=job_id)
            if rec:
                return UrlLedgerRecord.from_dict(rec)
        elif job_id:
            jid = str(job_id).strip()
            if jid in self.by_job_id:
                u_hash = self.by_job_id[jid]
                if u_hash in self.records:
                    return UrlLedgerRecord.from_dict(self.records[u_hash])
        return None

    def register_url(
        self,
        raw_url: str,
        job_id: str,
        preliminary_title: Optional[str] = None,
        preliminary_company: Optional[str] = None,
    ) -> UrlLedgerRecord:
        """
        Ghi nhận một URL mới phát hiện từ Phase 1 (Discovery).
        Kiểm tra trùng lặp đa tầng (URL Hash & Job ID).
        Nếu URL hoặc Job ID đã có:
          - Cập nhật last_seen_at = now
          - Cập nhật canonical_url nếu đổi redirect/slug
          - Bổ sung preliminary_title/company nếu trước đó khuyết
          - Kiểm tra 21 ngày recheck_due nếu status == "DONE"
        Nếu chưa từng xuất hiện:
          - Đăng ký mới với status = "PENDING"
        """
        canonical = clean_canonical_url(raw_url)
        url_hash = generate_url_hash(canonical)
        jid_str = str(job_id).strip() if job_id else ""
        now_iso = datetime.now(timezone.utc).isoformat()
        identity_key = generate_identity_key(preliminary_company or "", preliminary_title or "")

        is_dup, match_type, existing_rec = self.check_duplicate(raw_url, job_id=job_id)

        if is_dup and existing_rec:
            existing_rec["last_seen_at"] = now_iso

            # Nếu trùng theo Job ID nhưng đổi URL (ví dụ: đổi slug hoặc redirect)
            if match_type == "JOB_ID":
                existing_rec["canonical_url"] = canonical
                old_hash = existing_rec.get("url_hash", "")
                if old_hash and old_hash != url_hash:
                    # Lưu bản ghi dưới url_hash mới để tra cứu trực tiếp bằng URL mới
                    self.records[url_hash] = existing_rec
                    if jid_str:
                        self.by_job_id[jid_str] = url_hash

            if preliminary_title and not existing_rec.get("preliminary_title"):
                existing_rec["preliminary_title"] = preliminary_title
            if preliminary_company and not existing_rec.get("preliminary_company"):
                existing_rec["preliminary_company"] = preliminary_company

            scraped_time = existing_rec.get("last_scraped_at") or existing_rec.get("last_crawled_at")
            if existing_rec.get("status") == "DONE" and is_due_for_recrawl(scraped_time, days=21):
                existing_rec["status"] = "RECHECK_DUE"

            return UrlLedgerRecord.from_dict(existing_rec)

        # URL & Job ID mới hoàn toàn
        new_record = UrlLedgerRecord(
            url_hash=url_hash,
            canonical_url=canonical,
            source=self.source,
            job_id=jid_str,
            discovered_at=now_iso,
            status="PENDING",
            preliminary_title=preliminary_title,
            preliminary_company=preliminary_company,
            identity_key=identity_key,
            last_seen_at=now_iso,
        )
        self.records[url_hash] = new_record.to_dict()
        if jid_str:
            self.by_job_id[jid_str] = url_hash
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

    def get_queue_summary(self, recheck_days: int = 21) -> Dict[str, int]:
        """Thống kê chi tiết tình trạng hàng đợi cào chi tiết."""
        summary = {
            "total": len(self.records),
            "pending": 0,
            "recheck_due": 0,
            "done": 0,
            "closed": 0,
            "failed": 0,
        }
        for rec in self.records.values():
            st = rec.get("status", "UNKNOWN")
            if st == "PENDING":
                summary["pending"] += 1
            elif st == "RECHECK_DUE":
                summary["recheck_due"] += 1
            elif st == "DONE":
                if is_due_for_recrawl(rec.get("last_scraped_at") or rec.get("last_crawled_at"), days=recheck_days):
                    summary["recheck_due"] += 1
                else:
                    summary["done"] += 1
            elif st == "CLOSED":
                summary["closed"] += 1
            elif st == "FAILED":
                summary["failed"] += 1
        return summary

    def get_pending_or_due_records(
        self,
        recheck_days: int = 21,
        limit: Optional[int] = None,
        sort_newest: bool = False,
    ) -> List[Dict[str, Any]]:
        """Lọc và phân bổ danh sách các link cần cào chi tiết ở Phase 2 theo thứ tự ưu tiên:
        1. Ưu tiên 1 (P1): Các tin PENDING (tin mới phát hiện).
        2. Ưu tiên 2 (P2): Các tin RECHECK_DUE (tin cũ đã cào >= 21 ngày).
        3. Tuyệt đối loại trừ: Các tin CLOSED (đã đóng/hết hạn).
        
        Nếu sort_newest=True:
        - Nhóm PENDING sắp xếp theo ngày phát hiện mới nhất (discovered_at DESC).
        - Nhóm RECHECK_DUE sắp xếp theo ngày cào cũ nhất (last_scraped_at ASC).
        """
        pending_items: List[Dict[str, Any]] = []
        due_items: List[Dict[str, Any]] = []

        for rec in self.records.values():
            status = rec.get("status")
            if status == "CLOSED":
                continue
            if status == "PENDING":
                pending_items.append(rec)
            elif status == "RECHECK_DUE":
                due_items.append(rec)
            elif status == "DONE" and is_due_for_recrawl(rec.get("last_scraped_at") or rec.get("last_crawled_at"), days=recheck_days):
                rec["status"] = "RECHECK_DUE"
                due_items.append(rec)

        if sort_newest:
            # Sắp xếp P1: Tin mới nhất lên đầu
            pending_items.sort(
                key=lambda x: str(x.get("discovered_at") or x.get("last_seen_at") or ""),
                reverse=True,
            )

            # Sắp xếp P2: Tin cũ nhất đến hạn kiểm tra lên đầu
            due_items.sort(
                key=lambda x: str(x.get("last_scraped_at") or x.get("last_crawled_at") or ""),
                reverse=False,
            )

        priority_queue = pending_items + due_items
        if limit is not None and limit > 0:
            return priority_queue[:limit]
        return priority_queue

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

    def mark_scraped(
        self,
        url_hash: str,
        content_hash: str,
        version: Optional[int] = None,
        http_status: Optional[int] = None,
        **kwargs,
    ):
        """Tương thích ngược: Đánh dấu URL đã cào thành công (gọi mark_done)."""
        self.mark_done(url_hash=url_hash, content_hash=content_hash, new_version=version)


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

            parquet_file = self.base_dir / "catalog_master.parquet"
            if parquet_file.exists():
                try:
                    s3.upload_file(str(parquet_file), bucket, f"url_ledger/{self.source}/catalog_master.parquet")
                except Exception as p_err:
                    logger.debug(f"Không thể upload parquet: {p_err}")

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

    def pull_from_minio(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ) -> bool:
        """
        Kéo URL Ledger (catalog_master.json) từ MinIO / S3 về máy cục bộ.
        Nguồn: minio://{bucket_name}/url_ledger/{source}/catalog_master.json
        Hợp nhất an toàn: nếu local chưa có hoặc MinIO có record mới thì cập nhật.
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
        storage_label = "Cloudflare R2" if "r2.cloudflarestorage.com" in endpoint else "MinIO"

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

            key = f"url_ledger/{self.source}/catalog_master.json"
            try:
                resp = s3.get_object(Bucket=bucket, Key=key)
                remote_records = json.loads(resp["Body"].read().decode("utf-8"))
            except Exception as get_exc:
                logger.info(f"[{storage_label}] Khong tim thay {key} tren bucket {bucket} ({get_exc})")
                return False

            if not isinstance(remote_records, dict):
                return False

            merged_count = 0
            for uh, r_rec in remote_records.items():
                if uh not in self.records:
                    self.records[uh] = r_rec
                    merged_count += 1
                else:
                    local_rec = self.records[uh]
                    if local_rec.get("status") == "PENDING" and r_rec.get("status") == "DONE":
                        self.records[uh] = r_rec
                        merged_count += 1

            self.save_catalog()
            logger.info(f"[{storage_label}] Da keo {len(remote_records)} records tu s3://{bucket}/{key} ve local (cap nhat {merged_count}).")
            return True
        except Exception as exc:
            logger.warning(f"[{storage_label}] Khong the keo catalog tu MinIO ({endpoint}): {exc}")
            return False

    def get_failed_records(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các URL có trạng thái FAILED (Failed Queue)."""
        return [r for r in self.records.values() if r.get("status") == "FAILED"]

    # Cloudflare R2 Aliases
    sync_to_r2 = sync_to_minio
    pull_from_r2 = pull_from_minio


