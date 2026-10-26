#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts.push_transformation_to_r2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Đẩy toàn bộ dữ liệu JSON của giai đoạn Transformation và các báo cáo tương ứng
lên Cloudflare R2 Cloud Lakehouse (Bucket: vn-it-jobs, Prefix: transformation/).
LOẠI TRỪ 100% các tệp salary_sort theo chỉ đạo của người dùng.
"""

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
    print("      ĐỒNG BỘ DỮ LIỆU TRANSFORMATION LÊN CLOUDFLARE R2 CLOUD LAKEHOUSE")
    print("      Dự án: VN-IT-Job-Mining (Loại trừ các tệp salary_sort)")
    print("=" * 80)

    bucket = os.getenv("R2_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "vn-it-jobs"
    s3 = get_r2_client()

    files_to_upload = []

    # 1. Dữ liệu phẳng đã chuyển hóa trong data/transformation/
    data_tf_dir = PROJECT_ROOT / "data" / "transformation"
    for p in sorted(data_tf_dir.glob("**/*.json")):
        # Loại trừ các file salary_sort
        if "salary_sort" in p.name.lower():
            continue
        rel_key = f"transformation/{p.relative_to(data_tf_dir)}"
        files_to_upload.append((p, rel_key))

    # 2. Báo cáo transformation trong reports/transformation/
    reports_tf_dir = PROJECT_ROOT / "reports" / "transformation"
    if reports_tf_dir.exists():
        for p in sorted(reports_tf_dir.glob("*.json")):
            if "salary_sort" in p.name.lower():
                continue
            rel_key = f"transformation/reports/{p.name}"
            files_to_upload.append((p, rel_key))

    total_files = len(files_to_upload)
    total_bytes = sum(f[0].stat().st_size for f in files_to_upload)
    print(f"Tổng số tệp JSON cần đồng bộ: {total_files}")
    print(f"Tổng dung lượng dữ liệu:     {total_bytes / (1024 * 1024):.2f} MB")
    print("-" * 80)
    for p, k in files_to_upload:
        print(f"  • {k:<60} ({p.stat().st_size / (1024 * 1024):.2f} MB)")
    print("-" * 80)

    t0 = time.time()
    uploaded_count = 0
    uploaded_bytes = 0

    for idx, (local_path, s3_key) in enumerate(files_to_upload, 1):
        fsize = local_path.stat().st_size
        fsize_mb = fsize / (1024 * 1024)
        print(f"[{idx:2d}/{total_files:2d}] Đang đẩy: {s3_key:<60} ({fsize_mb:5.2f} MB)...", end="", flush=True)

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
    print(f"   Target Bucket: s3://{bucket}/transformation/")
    print("=" * 80)


if __name__ == "__main__":
    main()
