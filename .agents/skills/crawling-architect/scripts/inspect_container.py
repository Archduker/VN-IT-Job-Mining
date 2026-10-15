#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tool kiểm tra HTML thô, lọc bỏ rác động và đề xuất Container Selector
tối ưu nhất để tính Clean Container HTML Hash.

Sử dụng:
    python .agents/skills/crawling-architect/scripts/inspect_container.py --html path/to/sample.html
"""

import argparse
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from crawlers.common.url_ledger import calculate_container_html_hash


def inspect_html(html_path: str):
    path = Path(html_path)
    if not path.exists():
        print(f"❌ File không tồn tại: {html_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    soup = BeautifulSoup(content, "html.parser")
    print(f"\n🔍 [INSPECT] Đang phân tích file: {path.name} ({len(content):,} bytes)")

    # Thử nghiệm các selector phổ biến trong tuyển dụng
    candidate_selectors = [
        ".job-detail",
        "#job-detail",
        ".job-description",
        ".job__description",
        ".box-header-job",
        "div[class*='detail']",
        "div[class*='content']",
        "main",
        "article",
        "body",
    ]

    print("\n📊 Bảng đánh giá các ứng viên Container Selector:")
    print(f"{'Selector':<25} | {'Tìm thấy':<10} | {'Độ dài text':<12} | {'Clean Hash (SHA256 đầu)'}")
    print("-" * 75)

    best_selector = "body"
    max_text_len = 0

    for sel in candidate_selectors:
        el = soup.select_one(sel)
        if el:
            clean_hash = calculate_container_html_hash(content, container_selector=sel)
            text_len = len(el.get_text(strip=True))
            print(f"{sel:<25} | {'CÓ':<10} | {text_len:<12} | {clean_hash[:16]}...")
            if text_len > 200 and text_len > max_text_len and sel != "body":
                max_text_len = text_len
                best_selector = sel
        else:
            print(f"{sel:<25} | {'KHÔNG':<10} | {'-':<12} | -")

    print("\n💡 GỢI Ý CỦA AGENT:")
    print(f"👉 Container Selector khuyến nghị: '{best_selector}'")
    print(f"👉 Dùng trong crawler: calculate_container_html_hash(html, container_selector='{best_selector}')\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kiểm tra HTML và gợi ý container selector để băm hash.")
    parser.add_argument("--html", required=True, help="Đường dẫn tới file HTML mẫu")
    args = parser.parse_args()
    inspect_html(args.html)
