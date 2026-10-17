#!/usr/bin/env python3
"""Script kiểm tra và chấm điểm tự động hồ sơ nghiệm thu thu thập dữ liệu (DoD Verifier).

Sử dụng:
    python3 .agents/skills/collection-submission/scripts/verify_submission.py --source topcv
    python3 .agents/skills/collection-submission/scripts/verify_submission.py --source vietnamworks
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(source: str) -> None:
    print(f"\n{CYAN}{BOLD}{'=' * 65}{RESET}")
    print(f"{CYAN}{BOLD} KIỂM TRA HỒ SƠ NGHIỆM THU THU THẬP DỮ LIỆU: [{source.upper()}]{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 65}{RESET}\n")


def check_samples(source: str) -> tuple[bool, list[str]]:
    details = []
    samples_dir = Path("crawlers") / "sources" / source / "samples"
    if not samples_dir.is_dir():
        details.append(f"{RED}[FAIL]{RESET} Thư mục mẫu không tồn tại: {samples_dir}")
        return False, details

    html_files = sorted(list(samples_dir.glob("*.html")))
    json_files = sorted(list(samples_dir.glob("*.json")))
    md_files = sorted(list(samples_dir.glob("*.md")))

    # 1. Kiểm tra số lượng HTML files
    if len(html_files) >= 3:
        details.append(f"{GREEN}[PASS]{RESET} File HTML thô: tìm thấy {len(html_files)}/3 file")
        for f in html_files:
            size_kb = f.stat().st_size / 1024
            details.append(f"       • {f.name} ({size_kb:.1f} KB)")
    else:
        details.append(f"{RED}[FAIL]{RESET} File HTML thô: chỉ có {len(html_files)}/3 file (yêu cầu tối thiểu 3 file)")

    # 2. Kiểm tra số lượng JSON files & tính hợp lệ
    valid_json = 0
    if len(json_files) >= 3:
        details.append(f"{GREEN}[PASS]{RESET} File JSON tương ứng: tìm thấy {len(json_files)}/3 file")
        for f in json_files:
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    valid_json += 1
                    keys_info = list(data.keys()) if isinstance(data, dict) else f"{len(data)} items"
                    details.append(f"       • {f.name} (Valid JSON, structure: {keys_info[:4]})")
            except Exception as e:
                details.append(f"       • {RED}{f.name} (Lỗi cú pháp JSON: {e}){RESET}")
    else:
        details.append(f"{RED}[FAIL]{RESET} File JSON: chỉ có {len(json_files)}/3 file (yêu cầu tối thiểu 3 file)")

    # 3. Kiểm tra file markdown mô tả sample (tùy chọn)
    if md_files:
        details.append(f"{GREEN}[PASS]{RESET} File Markdown mô tả sample: {', '.join(f.name for f in md_files)}")
    else:
        details.append(f"{YELLOW}[INFO]{RESET} File Markdown mô tả sample: Không có (khuyến khích thêm samples/README.md)")

    passed = len(html_files) >= 3 and valid_json >= 3
    return passed, details


def check_docs_and_reports(source: str) -> tuple[bool, list[str]]:
    details = []
    crawl_doc = Path("docs") / "crawl" / f"{source}.md"
    inventory_report = Path("reports") / f"{source}_inventory.md"
    eda_report = Path("reports") / f"{source}_eda.md"

    # Kiểm tra doc
    if crawl_doc.is_file() and crawl_doc.stat().st_size > 100:
        details.append(f"{GREEN}[PASS]{RESET} Tài liệu phân tích kiến trúc web: {crawl_doc} ({crawl_doc.stat().st_size} bytes)")
    else:
        details.append(f"{RED}[FAIL]{RESET} Tài liệu phân tích kiến trúc web thiếu hoặc quá ngắn: {crawl_doc}")

    # Kiểm tra inventory report
    if inventory_report.is_file() and inventory_report.stat().st_size > 100:
        details.append(f"{GREEN}[PASS]{RESET} Báo cáo kiểm kê trường dữ liệu: {inventory_report}")
    else:
        details.append(f"{RED}[FAIL]{RESET} Thiếu báo cáo kiểm kê: {inventory_report}")

    # Kiểm tra eda report
    if eda_report.is_file() and eda_report.stat().st_size > 100:
        details.append(f"{GREEN}[PASS]{RESET} Báo cáo phân tích EDA sơ bộ: {eda_report}")
    else:
        details.append(f"{RED}[FAIL]{RESET} Thiếu báo cáo EDA: {eda_report}")

    passed = crawl_doc.is_file() and inventory_report.is_file() and eda_report.is_file()
    return passed, details


def check_storage_readiness() -> tuple[bool, list[str]]:
    details = []
    # Nạp .env nếu có
    env_file = Path(".env")
    if env_file.is_file():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    # Kiểm tra MinIO
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    details.append(f"{GREEN}[PASS]{RESET} MinIO Endpoint được cấu hình: {minio_endpoint}")

    # Kiểm tra Cloudflare R2
    r2_endpoint = os.getenv("R2_ENDPOINT_URL") or os.getenv("S3_ENDPOINT_URL")
    if r2_endpoint and "r2.cloudflarestorage.com" in r2_endpoint:
        details.append(f"{GREEN}[PASS]{RESET} Cloudflare R2 Endpoint: {r2_endpoint}")
    else:
        details.append(f"{YELLOW}[WARN]{RESET} Chưa cấu hình R2_ENDPOINT_URL trong .env (chạy local-only hoặc điền theo .env.example)")

    return True, details


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra nghiệm thu hồ sơ thu thập dữ liệu (DoD)")
    parser.add_argument("--source", required=True, help="Tên nguồn (VD: topcv, vietnamworks, careerviet, itviec...)")
    args = parser.parse_args()

    source = args.source.strip().lower()
    print_banner(source)

    print(f"{BOLD}1. Kiểm Tra Bộ Mẫu Dữ Liệu (crawlers/sources/{source}/samples/):{RESET}")
    samples_ok, samples_details = check_samples(source)
    for line in samples_details:
        print(f"  {line}")

    print(f"\n{BOLD}2. Kiểm Tra Tài Liệu & Báo Cáo Nghiệm Thu:{RESET}")
    docs_ok, docs_details = check_docs_and_reports(source)
    for line in docs_details:
        print(f"  {line}")

    print(f"\n{BOLD}3. Kiểm Tra Hạ Tầng Lưu Trữ Đa Tầng (MinIO & Cloudflare R2):{RESET}")
    storage_ok, storage_details = check_storage_readiness()
    for line in storage_details:
        print(f"  {line}")

    print(f"\n{CYAN}{BOLD}{'=' * 65}{RESET}")
    if samples_ok and docs_ok:
        print(f"{GREEN}{BOLD} KẾT QUẢ TỔNG THỂ: ĐẠT TIÊU CHUẨN NGHIỆM THU (DOD PASSED)!{RESET}")
        print(f"{GREEN} Nhánh 'crawls/{source}' đã sẵn sàng tạo Pull Request vào nhánh 'main'.{RESET}")
        print(f"{CYAN}{BOLD}{'=' * 65}{RESET}\n")
        return 0
    else:
        print(f"{RED}{BOLD} KẾT QUẢ TỔNG THỂ: CHƯA ĐẠT TIÊU CHUẨN NGHIỆM THU (DOD FAILED)!{RESET}")
        print(f"{YELLOW} Vui lòng hoàn thiện các mục bị đánh dấu [FAIL] ở trên trước khi nộp bài.{RESET}")
        print(f"{CYAN}{BOLD}{'=' * 65}{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
