#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts.push_integration_to_r2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Đẩy toàn bộ dữ liệu JSON của giai đoạn Integration và các báo cáo tương ứng
lên Cloudflare R2 Cloud Lakehouse (Bucket: vn-it-jobs, Prefix: integration/).
"""

import glob
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from collection.common.r2_storage import get_r2_client

def main():
    print("=" * 80)
    print("      ĐỒNG BỘ DỮ LIỆU INTEGRATION LÊN CLOUDFLARE R2 CLOUD LAKEHOUSE")
    print("      Dự án: VN-IT-Job-Mining (100% Định dạng JSON)")
    print("=" * 80)

    bucket = os.getenv("R2_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "vn-it-jobs"
    s3 = get_r2_client()

    # 1. Thu thập danh sách tệp cần đẩy lên
    files_to_upload = []

    # A. Dữ liệu phẳng tích hợp trong data/integration/
    data_int_dir = PROJECT_ROOT / "data" / "integration"
    for p in data_int_dir.glob("**/*.json"):
        rel_key = f"integration/{p.relative_to(data_int_dir)}"
        files_to_upload.append((p, rel_key))

    # B. Báo cáo chất lượng tích hợp trong reports/integration/
    reports_int_dir = PROJECT_ROOT / "reports" / "integration"
    if reports_int_dir.exists():
        for p in reports_int_dir.glob("*.json"):
            rel_key = f"integration/reports/{p.name}"
            files_to_upload.append((p, rel_key))

    total_files = len(files_to_upload)
    total_bytes = sum(f[0].stat().st_size for f in files_to_upload)
    print(f"Tổng số tệp JSON cần đồng bộ: {total_files}")
    print(f"Tổng dung lượng dữ liệu:     {total_bytes / (1024 * 1024):.2f} MB")
    print("-" * 80)

    t0 = time.time()
    uploaded_count = 0
    uploaded_bytes = 0

    for idx, (local_path, s3_key) in enumerate(files_to_upload, 1):
        fsize = local_path.stat().st_size
        fsize_mb = fsize / (1024 * 1024)
        print(f"[{idx:2d}/{total_files:2d}] Đang đẩy: {s3_key:<55} ({fsize_mb:5.2f} MB)...", end="", flush=True)

        try:
            with open(local_path, "rb") as fp:
                s3.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=fp.read(),
                    ContentType="application/json; charset=utf-8",
                )
            print(" -> [THÀNH CÔNG]")
            uploaded_count += 1
            uploaded_bytes += fsize
        except Exception as exc:
            print(f" -> [LỖI: {exc}]")

    dt = time.time() - t0
    speed = (uploaded_bytes / (1024 * 1024)) / dt if dt > 0 else 0

    print("=" * 80)
    print(f"🎉 HOÀN TẤT ĐỒNG BỘ {uploaded_count}/{total_files} TỆP LÊN CLOUDFLARE R2 TRONG {dt:.2f}s ({speed:.2f} MB/s)!")
    print(f"   Target Bucket: s3://{bucket}/integration/")
    print("=" * 80)

if __name__ == "__main__":
    main()
