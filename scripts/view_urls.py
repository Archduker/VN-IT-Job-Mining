#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Công cụ kiểm tra & hiển thị danh sách URL đã lưu (URL Ledger) cho hệ thống VN-IT-Job-Mining.

Hỗ trợ:
1. Xem dữ liệu cục bộ trong data/<source>/url_ledger/
2. Xem dữ liệu trực tiếp trên MinIO Lakehouse: minio://vn-it-jobs/url_ledger/<source>/ (qua cờ --minio)
3. Lọc theo trạng thái (PENDING, DONE, FAILED, RECHECK_DUE, CLOSED), hiển thị bảng trực quan và xuất file.

Sử dụng:
    python scripts/view_urls.py --source topcv
    python scripts/view_urls.py --source topcv --minio
    python scripts/view_urls.py --source topcv --status PENDING --limit 20
    python scripts/view_urls.py --source topcv --status FAILED --show-errors
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Thêm REPO_ROOT vào sys.path để import url_ledger validator
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from crawlers.common.url_ledger import UrlLedgerRecord, clean_canonical_url, generate_url_hash
except Exception:
    UrlLedgerRecord = None
    clean_canonical_url = None
    generate_url_hash = None

ALL_SOURCES = (
    "careerviet",
    "glints",
    "itviec",
    "jobsgo",
    "topcv",
    "topdev",
    "vieclam24h",
    "vietnamworks",
)


def load_local_ledger(source: str) -> Dict[str, Any]:
    """Tải catalog_master.json từ thư mục cục bộ data/<source>/url_ledger/."""
    # Ưu tiên chuẩn mới data/<source>/url_ledger, fallback data/url_ledger/<source>
    target_path = Path(f"data/{source}/url_ledger/catalog_master.json")
    if not target_path.exists():
        legacy_path = Path(f"data/url_ledger/{source}/catalog_master.json")
        if legacy_path.exists():
            target_path = legacy_path

    if not target_path.exists():
        return {"records": {}, "source_path": str(target_path), "exists": False}

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"records": data, "source_path": str(target_path), "exists": True}
    except Exception as exc:
        print(f"❌ Lỗi khi đọc {target_path}: {exc}", file=sys.stderr)
        return {"records": {}, "source_path": str(target_path), "exists": False}


def load_minio_ledger(
    source: str,
    bucket_name: Optional[str] = None,
    endpoint: Optional[str] = None,
    ak: Optional[str] = None,
    sk: Optional[str] = None,
) -> Dict[str, Any]:
    """Tải catalog_master.json và manifests trực tiếp từ MinIO / Cloudflare R2 S3 Lakehouse."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    b_name = bucket_name or os.getenv("S3_BUCKET_NAME") or os.getenv("MINIO_BUCKET") or "vn-it-jobs"
    ep = endpoint or os.getenv("S3_ENDPOINT_URL") or os.getenv("MINIO_ENDPOINT") or "http://localhost:9000"
    is_localhost = "localhost" in ep or "127.0.0.1" in ep
    if is_localhost:
        access = ak or ("minioadmin" if os.getenv("MINIO_ROOT_USER") == os.getenv("AWS_ACCESS_KEY_ID") else os.getenv("MINIO_ROOT_USER", "minioadmin"))
        secret = sk or ("minioadmin" if os.getenv("MINIO_ROOT_PASSWORD") == os.getenv("AWS_SECRET_ACCESS_KEY") else os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"))
    else:
        access = ak or os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("R2_ACCESS_KEY_ID") or os.getenv("MINIO_ROOT_USER") or "minioadmin"
        secret = sk or os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("MINIO_ROOT_PASSWORD") or "minioadmin"
    reg = "auto" if "r2.cloudflarestorage.com" in ep else os.getenv("AWS_REGION", "us-east-1")
    is_r2 = "r2.cloudflarestorage.com" in ep

    try:
        import boto3
        from botocore.client import Config

        s3 = boto3.client(
            "s3",
            endpoint_url=ep,
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            config=Config(signature_version="s3v4", connect_timeout=4, retries={"max_attempts": 2}),
            region_name=reg,
        )

        catalog_key = f"url_ledger/{source}/catalog_master.json"
        scheme = "r2" if is_r2 else "minio"
        try:
            resp = s3.get_object(Bucket=b_name, Key=catalog_key)
            catalog_data = json.loads(resp["Body"].read().decode("utf-8"))
            return {
                "records": catalog_data,
                "source_path": f"{scheme}://{b_name}/{catalog_key}",
                "exists": True,
                "from_minio": True,
                "is_r2": is_r2,
            }
        except Exception:
            # Nếu catalog_master chưa có, quét các file manifest JSONL
            prefix = f"url_ledger/{source}/manifests/"
            objs = s3.list_objects_v2(Bucket=b_name, Prefix=prefix)
            contents = objs.get("Contents", [])
            if not contents:
                return {
                    "records": {},
                    "source_path": f"{scheme}://{b_name}/{prefix}",
                    "exists": False,
                    "from_minio": True,
                    "is_r2": is_r2,
                }

            combined_records = {}
            for item in sorted(contents, key=lambda x: x["LastModified"], reverse=True):
                m_key = item["Key"]
                if not m_key.endswith(".jsonl"):
                    continue
                m_resp = s3.get_object(Bucket=b_name, Key=m_key)
                for line in m_resp["Body"].read().decode("utf-8").splitlines():
                    if line.strip():
                        rec = json.loads(line)
                        combined_records[rec["url_hash"]] = rec

            return {
                "records": combined_records,
                "source_path": f"{scheme}://{b_name}/{prefix} ({len(contents)} manifests)",
                "exists": True,
                "from_minio": True,
                "is_r2": is_r2,
            }

    except Exception as exc:
        target_name = "Cloudflare R2" if is_r2 else "MinIO"
        print(f"❌ Không thể kết nối tới {target_name} tại {ep}: {exc}", file=sys.stderr)
        if not is_r2:
            print("💡 Gợi ý: Chạy 'bash scripts/start_minio.sh' hoặc kiểm tra Docker container MinIO.", file=sys.stderr)
        return {"records": {}, "source_path": f"s3://{b_name}/url_ledger/{source}/", "exists": False, "from_minio": True, "is_r2": is_r2}


def render_dashboard(
    records: Dict[str, Dict[str, Any]],
    source: str,
    source_path: str,
    status_filter: Optional[str] = None,
    limit: int = 25,
    show_errors: bool = False,
    is_minio: bool = False,
):
    """Vẽ dashboard tóm tắt và bảng danh sách URL."""
    total = len(records)
    counts = Counter(r.get("status", "UNKNOWN") for r in records.values())
    repost_count = sum(1 for r in records.values() if r.get("repost_of_url_hash"))

    if is_minio:
        if "r2://" in source_path or "r2.cloudflarestorage.com" in source_path:
            storage_label = "☁️ [CLOUDFLARE R2 LAKEHOUSE]"
        else:
            storage_label = "🌐 [MINIO S3 LAKEHOUSE]"
    else:
        storage_label = "💻 [LOCAL STORAGE]"

    print("=" * 86)
    print(f"  BÁO CÁO KIỂM KÊ URL LEDGER — NGUỒN: {source.upper()} {storage_label}")
    print(f"  Đường dẫn: {source_path}")
    print("=" * 86)
    print(
        f"  Tổng phát hiện: {total:<6} | PENDING: {counts['PENDING']:<5} | DONE: {counts['DONE']:<5} "
        f"| FAILED: {counts['FAILED']:<5} | RECHECK: {counts['RECHECK_DUE']:<5} | REPOST: {repost_count}"
    )
    print("-" * 86)

    # Lọc danh sách
    filtered = list(records.values())
    if status_filter:
        s_filter = status_filter.upper()
        filtered = [r for r in filtered if r.get("status") == s_filter]

    # Sắp xếp mới nhất lên đầu
    filtered.sort(key=lambda x: x.get("discovered_at") or "", reverse=True)

    shown_count = len(filtered) if limit <= 0 else min(len(filtered), limit)
    filter_label = f" (Bộ lọc: {status_filter})" if status_filter else ""
    print(f"  Hiển thị {shown_count}/{len(filtered)} bài đăng{filter_label}:")
    print("-" * 86)
    print(f"{'#':<3} | {'Job ID':<10} | {'Status':<11} | {'Công Ty':<25} | {'Tiêu Đề':<28}")
    print("-" * 86)

    for i, r in enumerate(filtered[:shown_count], start=1):
        job_id = str(r.get("job_id", ""))[:10]
        st = r.get("status", "UNKNOWN")[:11]
        comp = (r.get("preliminary_company") or "Unknown")[:25]
        title = (r.get("preliminary_title") or r.get("canonical_url", ""))[:28]
        if not title.strip():
            title = r.get("canonical_url", "")[:28]

        # Đánh dấu màu trạng thái
        st_icon = "⏳" if st == "PENDING" else "✅" if st == "DONE" else "❌" if st == "FAILED" else "🔄"
        print(f"{i:<3} | {job_id:<10} | {st_icon} {st:<8} | {comp:<25} | {title:<28}")

        if show_errors and r.get("error_log"):
            print(f"    └── ⚠️ Lỗi: {r.get('error_log')}")

    print("-" * 86)
    if is_minio:
        print("💡 Bạn có thể xem trực quan trên MinIO Web Console UI: http://localhost:9001 (User: minioadmin / Pass: minioadmin)")
    else:
        print("💡 Để xem dữ liệu lưu trên MinIO S3, chạy thêm cờ: --minio")
    print("=" * 86)


def audit_source_metadata(records: Dict[str, Any]) -> Dict[str, Any]:
    """Kiểm toán chi tiết độ chuẩn hóa metadata của một sàn tuyển dụng."""
    total = len(records)
    valid_schema = 0
    hash_match = 0
    clean_url_count = 0
    statuses = Counter()
    has_title = 0
    has_company = 0
    has_identity = 0

    for u_hash, rec in records.items():
        st = rec.get("status", "UNKNOWN")
        statuses[st] += 1

        # 1. Kiểm tra Data Contract UrlLedgerRecord
        if UrlLedgerRecord:
            try:
                UrlLedgerRecord.from_dict(rec)
                valid_schema += 1
            except Exception:
                pass
        else:
            # Fallback nếu không có UrlLedgerRecord class
            req = {"url_hash", "canonical_url", "source", "job_id", "status", "discovered_at"}
            if req.issubset(rec.keys()):
                valid_schema += 1

        # 2. Kiểm tra tính toàn vẹn băm URL MD5
        can_url = rec.get("canonical_url", "")
        if can_url:
            if generate_url_hash:
                if generate_url_hash(can_url) == u_hash:
                    hash_match += 1
            else:
                import hashlib
                if hashlib.md5(can_url.strip().encode("utf-8")).hexdigest() == u_hash:
                    hash_match += 1

            if clean_canonical_url:
                if can_url == clean_canonical_url(can_url):
                    clean_url_count += 1
            else:
                clean_url_count += 1

        if rec.get("preliminary_title"):
            has_title += 1
        if rec.get("preliminary_company"):
            has_company += 1
        if rec.get("identity_key"):
            has_identity += 1

    is_ok = total > 0 and valid_schema == total and hash_match == total
    return {
        "total": total,
        "valid_schema": valid_schema,
        "hash_match": hash_match,
        "clean_url_count": clean_url_count,
        "statuses": dict(statuses),
        "has_title": has_title,
        "has_company": has_company,
        "has_identity": has_identity,
        "is_ok": is_ok,
    }


def render_all_sources_audit(all_results: Dict[str, Dict[str, Any]], is_minio: bool = False):
    """Vẽ bảng dashboard kiểm toán metadata toàn diện cho toàn bộ 8 nguồn tuyển dụng."""
    if is_minio:
        title_source = "☁️ [CLOUDFLARE R2 / MINIO CLOUD LAKEHOUSE]"
    else:
        title_source = "💻 [LOCAL STORAGE]"

    print("=" * 106)
    print(f"       BÁO CÁO KIỂM TOÁN CHUẨN HÓA METADATA TOÀN BỘ SÀN TUYỂN DỤNG {title_source}")
    print("=" * 106)
    print(
        f"{'Sàn Tuyển Dụng':<15} | {'Tổng Link':<10} | {'Schema Hợp Lệ':<14} | {'Mã Băm Khớp':<13} "
        f"| {'URL Sạch':<12} | {'Trạng Thái (Status)':<23} | {'Đánh Giá':<10}"
    )
    print("-" * 106)

    grand_total = 0
    grand_valid_schema = 0
    grand_hash_match = 0
    grand_clean_url = 0
    grand_statuses = Counter()

    for s in ALL_SOURCES:
        info = all_results.get(s, {})
        if not info.get("exists") or not info.get("records"):
            print(f"{s.upper():<15} | {'0 (Trống)':<10} | {'-':<14} | {'-':<13} | {'-':<12} | {'CHƯA CÓ DỮ LIỆU':<23} | ⚠️ THIẾU")
            continue

        audit = audit_source_metadata(info["records"])
        tot = audit["total"]
        grand_total += tot
        grand_valid_schema += audit["valid_schema"]
        grand_hash_match += audit["hash_match"]
        grand_clean_url += audit["clean_url_count"]
        for st, c in audit["statuses"].items():
            grand_statuses[st] += c

        st_strs = [f"{st[:3]}:{cnt}" for st, cnt in sorted(audit["statuses"].items())]
        st_summary = ", ".join(st_strs)[:23]

        pct_schema = f"{audit['valid_schema']}/{tot} ({(audit['valid_schema']/tot*100):.1f}%)" if tot else "-"
        pct_hash = f"{audit['hash_match']}/{tot} ({(audit['hash_match']/tot*100):.1f}%)" if tot else "-"
        pct_clean = f"{audit['clean_url_count']}/{tot} ({(audit['clean_url_count']/tot*100):.1f}%)" if tot else "-"
        eval_label = "✅ ĐẠT CHUẨN" if audit["is_ok"] else "⚠️ CẦN SỬA"

        print(
            f"{s.upper():<15} | {tot:<10,d} | {pct_schema:<14} | {pct_hash:<13} "
            f"| {pct_clean:<12} | {st_summary:<23} | {eval_label:<10}"
        )

    print("=" * 106)
    if grand_total > 0:
        total_schema_pct = (grand_valid_schema / grand_total) * 100
        total_hash_pct = (grand_hash_match / grand_total) * 100
        overall_ok = grand_valid_schema == grand_total and grand_hash_match == grand_total
        eval_all = "🎉 HOÀN HẢO (100% ĐẠT CHUẨN)" if overall_ok else "⚠️ CÓ LỖI SCHEMA"
        status_line = ", ".join(f"{st}: {c:,d}" for st, c in sorted(grand_statuses.items()))

        print(
            f"{'TỔNG CỘNG':<15} | {grand_total:<10,d} | {f'{grand_valid_schema:,d} ({total_schema_pct:.1f}%)':<14} "
            f"| {f'{grand_hash_match:,d} ({total_hash_pct:.1f}%)':<13} | {f'{grand_clean_url:,d}':<12} "
            f"| {eval_all}"
        )
        print("-" * 106)
        print(f"  Phân bổ vòng đời link toàn hệ thống: {status_line}")
        print("=" * 106)
    else:
        print("⚠️ Không có bất kỳ bản ghi URL Ledger nào được tìm thấy!")
        print("=" * 106)


def export_data(
    records: List[Dict[str, Any]],
    json_path: Optional[str] = None,
    csv_path: Optional[str] = None,
):
    """Xuất danh sách ra JSON hoặc CSV."""
    if json_path:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã xuất {len(records)} bản ghi ra JSON: {json_path}")

    if csv_path:
        fieldnames = [
            "job_id", "status", "canonical_url", "preliminary_title",
            "preliminary_company", "discovered_at", "last_scraped_at",
            "content_hash", "error_log"
        ]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                writer.writerow(r)
        print(f"✅ Đã xuất {len(records)} bản ghi ra CSV: {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Xem và kiểm tra danh sách URL Ledger (Cục bộ & MinIO)")
    parser.add_argument("--source", type=str, default="topcv", help="Nguồn tuyển dụng (mặc định: topcv, dùng 'all' để xem tất cả)")
    parser.add_argument("--audit", action="store_true", default=False, help="Chạy chế độ kiểm toán chuẩn hóa metadata cho toàn bộ sàn")
    parser.add_argument("--minio", action="store_true", default=False, help="Đọc trực tiếp từ MinIO / Cloudflare R2 S3 Lakehouse")
    parser.add_argument("--status", type=str, default=None, help="Lọc theo trạng thái: PENDING, DONE, FAILED, RECHECK_DUE, CLOSED")
    parser.add_argument("--limit", type=int, default=25, help="Giới hạn số bài hiển thị (mặc định: 25, 0 = tất cả)")
    parser.add_argument("--show-errors", action="store_true", default=False, help="In chi tiết log lỗi cho các link FAILED")
    parser.add_argument("--export-json", type=str, default=None, help="Đường dẫn file xuất JSON")
    parser.add_argument("--export-csv", type=str, default=None, help="Đường dẫn file xuất CSV")
    parser.add_argument("--endpoint", type=str, default=None, help="Endpoint MinIO/S3 (mặc định lấy từ .env hoặc http://localhost:9000)")
    parser.add_argument("--bucket", type=str, default="vn-it-jobs", help="Tên bucket MinIO")

    args = parser.parse_args()

    # Chế độ audit hoặc xem tất cả nguồn
    if args.source.lower() == "all" or args.audit:
        all_results = {}
        for s in ALL_SOURCES:
            if args.minio:
                res = load_minio_ledger(
                    source=s,
                    bucket_name=args.bucket,
                    endpoint=args.endpoint,
                )
            else:
                res = load_local_ledger(source=s)
            all_results[s] = res

        render_all_sources_audit(all_results, is_minio=args.minio)
        return

    if args.minio:
        res = load_minio_ledger(
            source=args.source,
            bucket_name=args.bucket,
            endpoint=args.endpoint,
        )
    else:
        res = load_local_ledger(source=args.source)

    if not res["exists"] or not res["records"]:
        print(f"⚠️ Không tìm thấy bản ghi URL Ledger nào cho '{args.source}' tại: {res['source_path']}")
        if not args.minio:
            print(f"💡 Thử chạy với cờ '--minio' hoặc chạy Phase 1 Discovery: python -m crawlers.sources.{args.source}.crawler --phase discovery")
        return

    render_dashboard(
        records=res["records"],
        source=args.source,
        source_path=res["source_path"],
        status_filter=args.status,
        limit=args.limit,
        show_errors=args.show_errors,
        is_minio=args.minio,
    )

    if args.export_json or args.export_csv:
        export_data(
            list(res["records"].values()),
            json_path=args.export_json,
            csv_path=args.export_csv,
        )


if __name__ == "__main__":
    main()
