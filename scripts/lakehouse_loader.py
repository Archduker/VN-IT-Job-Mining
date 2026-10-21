#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/lakehouse_loader.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Universal Lakehouse Raw Data Ingestion Module for VN-IT-Job-Mining.

Provides loading and local caching of raw job snapshots from Cloudflare R2 / MinIO
Lakehouse across all 8 sources without altering or forcing a premature unified schema:
  - CareerViet
  - Glints
  - ITviec
  - JobsGO
  - TopCV
  - TopDev
  - Vieclam24h
  - VietnamWorks

Design Principle:
  - Zero Information Loss (SD1): Preserves 100% of native payload fields and structure.
  - Returns flattened native DataFrame via pd.json_normalize() for honest EDA.
"""

from __future__ import annotations

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


def get_lakehouse_client():
    """Tạo kết nối tới Cloudflare R2 hoặc MinIO Lakehouse."""
    try:
        import boto3
        from botocore.client import Config
    except ImportError:
        logger.warning("Thư viện boto3 chưa được cài đặt. Chỉ có thể dùng dữ liệu cục bộ.")
        return None, None, None

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
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=20, retries={"max_attempts": 2}),
            region_name=region,
        )
        return s3, bucket, endpoint
    except Exception as exc:
        logger.warning("Không thể khởi tạo Boto3 client: %s", exc)
        return None, None, None


def sync_source_from_lakehouse(source: str, max_workers: int = 8) -> int:
    """Tải các snapshot còn thiếu từ R2 Lakehouse về thư mục data/<source>/raw/."""
    s3, bucket, endpoint = get_lakehouse_client()
    if not s3 or not bucket:
        return 0

    prefix = f"raw/{source}/"
    logger.info("Đang kiểm tra dữ liệu trên Lakehouse: %s (Bucket: %s)", prefix, bucket)

    try:
        paginator = s3.get_paginator("list_objects_v2")
        cloud_keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                cloud_keys.append(item["Key"])
    except Exception as exc:
        logger.warning("Không thể lấy danh sách từ Cloud: %s", exc)
        return 0

    if not cloud_keys:
        logger.info("Không có snapshot nào trên Cloud cho nguồn %s", source)
        return 0

    local_source_dir = PROJECT_ROOT / "data" / source / "raw"
    local_source_dir.mkdir(parents=True, exist_ok=True)
    existing_files = {p.name for p in (PROJECT_ROOT / "data" / source).rglob("*.json")}

    missing_keys = [k for k in cloud_keys if k.split("/")[-1] not in existing_files]
    logger.info("Nguồn %s: %d keys trên Cloud, %d tệp cục bộ, cần tải %d tệp.", source, len(cloud_keys), len(existing_files), len(missing_keys))

    if not missing_keys:
        return 0

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

    logger.info("Đã đồng bộ xong %d snapshot mới về %s", downloaded, local_source_dir)
    return downloaded


def load_raw_source_dataframe(
    source: str,
    auto_sync: bool = False,
    sample_limit: Optional[int] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Tải và trải phẳng tập dữ liệu thô nguyên bản của một sàn tuyển dụng (pd.json_normalize).

    Không can thiệp, không đổi tên cột, giữ nguyên 100% trường dữ liệu bản địa.

    Returns:
        (df_raw, audit_metadata)
    """
    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"Nguồn '{source}' không hỗ trợ. Phải thuộc: {SUPPORTED_SOURCES}")

    if auto_sync:
        try:
            sync_source_from_lakehouse(source)
        except Exception as exc:
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

                    # Xác định ID để lọc trùng lặp
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
                        raw_payloads.append(payload)
        except Exception as exc:
            logger.debug("Bỏ qua file %s do lỗi JSON: %s", fp.name, exc)

    if sample_limit and len(raw_payloads) > sample_limit:
        raw_payloads = raw_payloads[:sample_limit]

    logger.info("Nguồn %s: Đã giải nén %d bản ghi payload thô.", source, len(raw_payloads))

    # Trải phẳng cấu trúc JSON nguyên bản
    df_raw = pd.json_normalize(raw_payloads) if raw_payloads else pd.DataFrame()

    # Đọc URL Ledger audit metadata
    ledger_catalog_file = PROJECT_ROOT / "data" / source / "url_ledger" / "catalog_master.json"
    ledger_audit = {
        "total_discovered": len(df_raw),
        "done_count": len(df_raw),
        "pending_count": 0,
        "status_breakdown": {}
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
    for s in SUPPORTED_SOURCES:
        df, audit = load_raw_source_dataframe(s, auto_sync=False)
        print(f"{s.upper():15}: {len(df):5d} rows, {len(df.columns):4d} raw native columns. Sample cols: {list(df.columns)[:5]}")
