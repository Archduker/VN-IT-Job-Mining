#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/lakehouse_loader.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Universal Lakehouse Raw Data Ingestion & Auto-Sync Module for VN-IT-Job-Mining.

Provides seamless loading, intelligent multi-threaded caching, and live synchronization
of raw job snapshots from Cloudflare R2 / MinIO Lakehouse across all 8 sources:
  - CareerViet
  - Glints
  - ITviec
  - JobsGO
  - TopCV
  - TopDev
  - Vieclam24h
  - VietnamWorks

Design Principles:
  - Zero Information Loss (SD1): Preserves 100% of native payload fields and structure.
  - Auto-Sync by default: Detects missing files on local disk and pulls them automatically.
  - Graceful Offline Fallback: If offline or timeout occurs, safely uses local cache in 3s.
  - One-Click CLI: python scripts/lakehouse_loader.py --sync-all
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

# Setup project root and load environment variables
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

logger = logging.getLogger("lakehouse_loader")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

SUPPORTED_SOURCES = (
    "careerviet",
    "glints",
    "itviec",
    "jobsgo",
    "topcv",
    "topdev",
    "vieclam24h",
    "vietnamworks",
)


def get_lakehouse_client() -> Tuple[Any, Optional[str], Optional[str], str]:
    """Tạo kết nối tới Cloudflare R2 hoặc MinIO Lakehouse kèm kiểm tra kết nối nhanh (3s timeout).

    Returns:
        (s3_client, bucket_name, endpoint_url, connection_status)
    """
    try:
        import boto3
        from botocore.client import Config
    except ImportError:
        return None, None, None, "OFFLINE: Thiếu thư viện boto3"

    endpoint = (
        os.getenv("S3_ENDPOINT_URL")
        or os.getenv("R2_ENDPOINT_URL")
        or os.getenv("MINIO_ENDPOINT")
        or "http://localhost:9000"
    )
    ak = (
        os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("R2_ACCESS_KEY_ID")
        or os.getenv("MINIO_ROOT_USER")
        or "minioadmin"
    )
    sk = (
        os.getenv("AWS_SECRET_ACCESS_KEY")
        or os.getenv("R2_SECRET_ACCESS_KEY")
        or os.getenv("MINIO_ROOT_PASSWORD")
        or "minioadmin"
    )
    bucket = (
        os.getenv("S3_BUCKET_NAME")
        or os.getenv("R2_BUCKET_NAME")
        or os.getenv("MINIO_BUCKET")
        or "vn-it-jobs"
    )
    region = "auto" if "r2.cloudflarestorage.com" in endpoint else "us-east-1"

    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            config=Config(signature_version="s3v4", connect_timeout=3, read_timeout=10, retries={"max_attempts": 1}),
            region_name=region,
        )
        # Ping nhẹ kiểm tra quyền truy cập bucket
        s3.head_bucket(Bucket=bucket)
        return s3, bucket, endpoint, "CONNECTED"
    except Exception as exc:
        return None, bucket, endpoint, f"OFFLINE ({exc.__class__.__name__}: {exc})"


def sync_source_from_lakehouse(source: str, max_workers: int = 8) -> Dict[str, Any]:
    """Tự động kiểm tra và kéo các snapshot còn thiếu từ R2 Lakehouse về máy cục bộ.

    Returns:
        Dictionary chứa thông tin chi tiết về trạng thái đồng bộ
    """
    s3, bucket, endpoint, status = get_lakehouse_client()
    local_source_dir = PROJECT_ROOT / "data" / source / "raw"
    local_source_dir.mkdir(parents=True, exist_ok=True)
    existing_files = {p.name for p in (PROJECT_ROOT / "data" / source).rglob("*.json")}

    sync_result = {
        "status": status,
        "source": source,
        "endpoint": endpoint,
        "bucket": bucket,
        "cloud_keys_count": 0,
        "downloaded_count": 0,
        "local_files_count": len(existing_files),
        "message": ""
    }

    if status != "CONNECTED" or not s3:
        sync_result["message"] = f"Không có kết nối Cloud ({status}). Sử dụng {len(existing_files)} tệp bộ đệm cục bộ."
        logger.info(sync_result["message"])
        return sync_result

    prefix = f"raw/{source}/"
    try:
        paginator = s3.get_paginator("list_objects_v2")
        cloud_keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                cloud_keys.append(item["Key"])
        sync_result["cloud_keys_count"] = len(cloud_keys)
    except Exception as exc:
        sync_result["status"] = f"ERROR ({exc})"
        sync_result["message"] = f"Lỗi quét bucket {prefix}: {exc}"
        logger.warning(sync_result["message"])
        return sync_result

    if not cloud_keys:
        sync_result["message"] = f"Chưa có snapshot nào trên Cloud cho {source}. Dùng {len(existing_files)} tệp cục bộ."
        logger.info(sync_result["message"])
        return sync_result

    missing_keys = [k for k in cloud_keys if k.split("/")[-1] not in existing_files]
    if not missing_keys:
        sync_result["message"] = f"Đã đồng bộ đầy đủ ({len(cloud_keys)} snapshots trên Cloud, {len(existing_files)} tệp cục bộ)."
        logger.info("Nguồn %s: %s", source, sync_result["message"])
        return sync_result

    logger.info("Nguồn %s: Đang tải tự động %d snapshot còn thiếu từ Cloud...", source, len(missing_keys))
    downloaded = 0

    def _download(key: str):
        parts = key.split("/")
        filename = parts[-1]
        date_folder = parts[-2] if len(parts) >= 3 else "snapshot"
        target_dir = local_source_dir / date_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / filename
        s3.download_file(bucket, key, str(dest))
        return dest

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_download, k): k for k in missing_keys}
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
                downloaded += 1
            except Exception as e:
                logger.warning("Lỗi tải %s: %e", futures[f], e)

    sync_result["downloaded_count"] = downloaded
    sync_result["local_files_count"] = len(existing_files) + downloaded
    sync_result["message"] = f"Đã tải thành công {downloaded} snapshot mới từ Cloud R2 về {local_source_dir}."
    logger.info("Nguồn %s: %s", source, sync_result["message"])
    return sync_result


def sync_all_sources(max_workers: int = 8) -> Dict[str, Dict[str, Any]]:
    """Đồng bộ toàn bộ 8 nguồn tuyển dụng từ Cloud R2 về máy trong 1 lệnh duy nhất."""
    logger.info("=" * 70)
    logger.info("   BẮT ĐẦU ĐỒNG BỘ TOÀN BỘ 8 NGUỒN TỪ CLOUDFLARE R2 LAKEHOUSE")
    logger.info("=" * 70)
    results = {}
    for s in SUPPORTED_SOURCES:
        results[s] = sync_source_from_lakehouse(s, max_workers=max_workers)
    logger.info("=" * 70)
    logger.info("🎉 Hoàn tất kiểm tra và đồng bộ 8 nguồn dữ liệu!")
    return results


def load_raw_source_dataframe(
    source: str,
    auto_sync: bool = True,
    sample_limit: Optional[int] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Tải và trải phẳng tập dữ liệu thô nguyên bản của một sàn tuyển dụng (pd.json_normalize).

    Mặc định auto_sync=True: Tự động kiểm tra và kéo snapshot mới nhất từ Cloud R2 / MinIO.
    Nếu mất mạng hoặc offline: Tự động fallback về local cache trong 3 giây.

    Returns:
        (df_raw, audit_metadata)
    """
    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"Nguồn '{source}' không hỗ trợ. Phải thuộc: {SUPPORTED_SOURCES}")

    sync_info = {}
    if auto_sync:
        try:
            sync_info = sync_source_from_lakehouse(source)
        except Exception as exc:
            sync_info = {"status": f"OFFLINE_FALLBACK ({exc})", "message": "Tự động chuyển sang dùng dữ liệu cục bộ."}
            logger.warning("Bỏ qua đồng bộ Cloud cho %s do: %s", source, exc)

    data_dir = PROJECT_ROOT / "data" / source
    raw_files = []
    if data_dir.exists():
        for p in data_dir.rglob("*.json"):
            sp = str(p)
            if "url_ledger" not in sp and "manifest" not in sp and "session" not in sp:
                raw_files.append(p)

    src_dir = PROJECT_ROOT / "crawlers" / "sources" / source
    if src_dir.exists():
        for p in src_dir.rglob("*.json"):
            if "sample" in p.name or "test" in p.name or "jobs" in p.name:
                raw_files.append(p)

    logger.info("Nguồn %s: Đã tìm thấy %d tệp dữ liệu thô.", source, len(raw_files))

    raw_payloads: List[Dict[str, Any]] = []
    seen_ids = set()

    for fp in raw_files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = json.load(f)
                items = []
                if isinstance(content, list):
                    items = content
                elif isinstance(content, dict):
                    if "jobs" in content and isinstance(content["jobs"], list):
                        items = content["jobs"]
                    elif "records" in content and isinstance(content["records"], list):
                        items = content["records"]
                    else:
                        items = [content]

                for item in items:
                    meta = item.get("metadata") or item.get("_meta") or {}
                    payload = item.get("raw_payload") or item.get("raw") or item.get("listing_response") or item

                    jid = (
                        meta.get("job_id")
                        or (payload.get("id") if isinstance(payload, dict) else None)
                        or (payload.get("jobId") if isinstance(payload, dict) else None)
                        or (payload.get("job_id") if isinstance(payload, dict) else None)
                    )
                    if jid and jid in seen_ids:
                        continue
                    if jid:
                        seen_ids.add(jid)

                    if isinstance(payload, dict):
                        row_data = dict(payload)
                        if "job_id" not in row_data and meta.get("job_id"):
                            row_data["job_id"] = meta.get("job_id")
                        if "source_url" not in row_data and meta.get("source_url"):
                            row_data["source_url"] = meta.get("source_url")
                        if "canonical_hash" not in row_data and meta.get("canonical_hash"):
                            row_data["canonical_hash"] = meta.get("canonical_hash")
                        raw_payloads.append(row_data)
        except Exception as exc:
            logger.debug("Bỏ qua file %s do lỗi JSON: %s", fp.name, exc)

    if sample_limit and len(raw_payloads) > sample_limit:
        raw_payloads = raw_payloads[:sample_limit]

    logger.info("Nguồn %s: Đã giải nén %d bản ghi payload thô.", source, len(raw_payloads))

    df_raw = pd.json_normalize(raw_payloads) if raw_payloads else pd.DataFrame()

    ledger_catalog_file = PROJECT_ROOT / "data" / source / "url_ledger" / "catalog_master.json"
    ledger_audit = {
        "total_discovered": len(df_raw),
        "done_count": len(df_raw),
        "pending_count": 0,
        "status_breakdown": {},
        "sync_info": sync_info
    }
    if ledger_catalog_file.exists():
        try:
            with open(ledger_catalog_file, "r", encoding="utf-8") as f:
                cat = json.load(f)
                if isinstance(cat, dict):
                    statuses = pd.Series([v.get("status", "UNKNOWN") for v in cat.values()]).value_counts().to_dict()
                    ledger_audit["total_discovered"] = len(cat)
                    ledger_audit["status_breakdown"] = statuses
                    ledger_audit["done_count"] = statuses.get("DONE", 0)
                    ledger_audit["pending_count"] = statuses.get("PENDING", 0)
        except Exception as exc:
            logger.debug("Lỗi đọc catalog master %s: %s", source, exc)

    return df_raw, ledger_audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lakehouse Loader & Auto-Sync Tool")
    parser.add_argument("--sync-all", action="store_true", help="Kéo toàn bộ snapshot của 8 nguồn từ Cloud R2")
    parser.add_argument("--source", choices=list(SUPPORTED_SOURCES) + ["all"], default="all")
    args = parser.parse_args()

    if args.sync_all:
        sync_all_sources()
    else:
        sources_to_run = SUPPORTED_SOURCES if args.source == "all" else [args.source]
        for s in sources_to_run:
            df, audit = load_raw_source_dataframe(s, auto_sync=True)
            sync = audit.get("sync_info", {})
            print(f"{s.upper():12}: {len(df):5d} rows, {len(df.columns):3d} cols | Cloud: {sync.get('status')} ({sync.get('cloud_keys_count', 0)} keys, +{sync.get('downloaded_count', 0)} new)")
