#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script chuẩn hóa và di chuyển URL Ledger TopCV trên Cloudflare R2 Lakehouse.

Từ: topcv/url_ledger/... (sai định dạng, sai đường dẫn)
Sang: url_ledger/topcv/... (chuẩn hóa schema, PENDING, content_hash=None, json/jsonl/parquet)
"""

import json
import logging
import os
import sys
from pathlib import Path

# Thêm REPO_ROOT vào sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from crawlers.common.minio_raw_pipeline import MinioRawStore
from crawlers.common.url_ledger import UrlLedgerRecord

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fix_topcv_ledger")


def main():
    store = MinioRawStore()
    logger.info("Kết nối tới Object Storage: %s / %s", store.endpoint, store.bucket)

    # 1. Tải catalog cũ từ topcv/url_ledger/catalog_master.json
    old_catalog_key = "topcv/url_ledger/catalog_master.json"
    old_manifest_key = "topcv/url_ledger/manifests/manifest_2026-10-16.jsonl"

    raw_cat = store.get_json(old_catalog_key)
    if not raw_cat:
        logger.error("Không tìm thấy catalog cũ tại: %s", old_catalog_key)
        return 1

    logger.info("Đã tải catalog cũ: %d records", len(raw_cat))

    # 2. Chuẩn hóa từng bản ghi
    cleaned_catalog = {}
    pending_count = 0
    reset_failed_count = 0
    done_count = 0

    for url_hash, item in raw_cat.items():
        # Xóa trường thừa
        item.pop("last_crawled_at", None)

        status = item.get("status", "PENDING")
        if status == "FAILED":
            # Reset các bản ghi dính Cloudflare trước đây để cào mới
            item["status"] = "PENDING"
            item["error_log"] = None
            item["retry_count"] = 0
            item["content_hash"] = None
            reset_failed_count += 1
            pending_count += 1
        elif status == "DONE":
            done_count += 1
        else:
            item["status"] = "PENDING"
            item["content_hash"] = None
            pending_count += 1

        rec = UrlLedgerRecord.from_dict(item)
        cleaned_catalog[url_hash] = rec.to_dict()

    logger.info(
        "Chuẩn hóa xong: %d records (PENDING: %d, reset FAILED: %d, DONE: %d)",
        len(cleaned_catalog),
        pending_count,
        reset_failed_count,
        done_count,
    )

    # 3. Lưu cục bộ data/topcv/url_ledger/
    local_dir = Path("data/topcv/url_ledger")
    manifests_dir = local_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    catalog_path = local_dir / "catalog_master.json"
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_catalog, f, ensure_ascii=False, indent=2)
    logger.info("Đã lưu catalog local: %s", catalog_path)

    # Manifest jsonl
    manifest_path = manifests_dir / "manifest_2026-10-16.jsonl"
    with open(manifest_path, "w", encoding="utf-8") as f:
        for rec in cleaned_catalog.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Đã lưu manifest local: %s", manifest_path)

    # Parquet
    parquet_path = local_dir / "catalog_master.parquet"
    try:
        import pandas as pd
        df = pd.DataFrame(list(cleaned_catalog.values()))
        df.to_parquet(parquet_path, index=False)
        logger.info("Đã tạo parquet local: %s", parquet_path)
    except Exception as e:
        logger.warning("Không thể tạo parquet: %s", e)
        parquet_path = None

    # 4. Tải lên R2 tại prefix chuẩn
    target_catalog_key = "url_ledger/topcv/catalog_master.json"
    target_manifest_key = "url_ledger/topcv/manifests/manifest_2026-10-16.jsonl"
    target_parquet_key = "url_ledger/topcv/catalog_master.parquet"

    logger.info("Bắt đầu đồng bộ lên R2 tại prefix chuẩn: url_ledger/topcv/...")
    store.put_file(target_catalog_key, catalog_path, content_type="application/json")
    logger.info("-> Uploaded %s", target_catalog_key)

    store.put_file(target_manifest_key, manifest_path, content_type="application/x-ndjson")
    logger.info("-> Uploaded %s", target_manifest_key)

    if parquet_path and parquet_path.exists():
        store.put_file(target_parquet_key, parquet_path, content_type="application/octet-stream")
        logger.info("-> Uploaded %s", target_parquet_key)

    # 5. Xóa key cũ trên R2
    logger.info("Dọn dẹp key cũ trên R2...")
    try:
        store.s3.delete_object(Bucket=store.bucket, Key=old_catalog_key)
        logger.info("-> Đã xóa %s", old_catalog_key)
        store.s3.delete_object(Bucket=store.bucket, Key=old_manifest_key)
        logger.info("-> Đã xóa %s", old_manifest_key)
    except Exception as e:
        logger.warning("Lỗi khi xóa key cũ: %s", e)

    # 6. Xác nhận lại
    new_keys = store.list_keys("url_ledger/topcv")
    logger.info("Kiểm tra R2 keys dưới 'url_ledger/topcv': %s", new_keys)

    old_keys = store.list_keys("topcv/url_ledger")
    logger.info("Kiểm tra R2 keys dưới 'topcv/url_ledger': %s (mong muốn: rỗng)", old_keys)

    logger.info("Hoàn tất chuẩn hóa TopCV URL Ledger thành công!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
