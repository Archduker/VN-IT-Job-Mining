#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tool phân tích cây DOM từ file HTML thô đại diện.
Tiếp nhận file HTML đầu vào, tự động dò tìm tất cả các trường dữ liệu cào được,
chỉ định Container Selector để băm Clean HTML Hash, và sinh mã Python Parser mẫu.

Sử dụng:
    python .agents/skills/crawling-architect/scripts/analyze_html_dom.py --html path/to/sample.html
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Thêm workspace root vào sys.path
ROOT_DIR = Path(__file__).resolve().parents[4]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from bs4 import BeautifulSoup
from crawlers.common.url_ledger import calculate_container_html_hash


def clean_str(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def analyze_html_file(html_path: str):
    path = Path(html_path)
    if not path.exists():
        print(f"❌ File không tồn tại: {html_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "html.parser")
    print("\n" + "=" * 80)
    print(f"🔍 [DOM ANALYZER] BÁO CÁO PHÂN TÍCH CÂY DOM: {path.name}")
    print(f"📁 Kích thước: {len(html_content):,} bytes | File: {path}")
    print("=" * 80)

    # 1. Quét Metadata Ẩn (JSON-LD, OpenGraph)
    print("\n📦 1. METADATA & DỮ LIỆU CẤU TRÚC ẨN:")
    json_ld_scripts = soup.find_all("script", type="application/ld+json")
    if json_ld_scripts:
        print(f"  ✅ Tìm thấy {len(json_ld_scripts)} thẻ JSON-LD (application/ld+json):")
        for i, tag in enumerate(json_ld_scripts, 1):
            try:
                data = json.loads(tag.string or "{}")
                schema_type = data.get("@type", "Unknown")
                print(f"    - Thẻ #{i}: @type = '{schema_type}'")
            except Exception:
                print(f"    - Thẻ #{i}: (Chứa chuỗi JSON phức tạp)")
    else:
        print("  ℹ️ Không tìm thấy thẻ JSON-LD.")

    # 2. Dò tìm các trường cốt lõi (Core Fields Discovery)
    print("\n🎯 2. DÒ TÌM TRƯỜNG DỮ LIỆU & CSS SELECTORS ĐỀ XUẤT:")
    print(f"{'Tên trường':<22} | {'Selector đề xuất':<32} | {'Giá trị trích xuất mẫu'}")
    print("-" * 80)

    discovered_fields = {}

    # Tiêu đề
    title_el = soup.select_one("h1.box-header-job__title, h1.job-title, h1.title, h1")
    title_sel = "h1" if not title_el else (title_el.get("class", ["h1"])[0] if title_el.get("class") else "h1")
    title_sel_str = f"h1.{title_sel}" if title_sel != "h1" else "h1"
    title_val = clean_str(title_el.get_text()) if title_el else "KHÔNG TÌM THẤY"
    discovered_fields["title"] = (title_sel_str, title_val)
    print(f"{'Tiêu đề (title)':<22} | {title_sel_str:<32} | {title_val[:35]}")

    # Công ty
    comp_el = soup.select_one(".box-header-job__company-name, .company-name, .company, [class*='company']")
    comp_sel = ".company" if not comp_el else f".{comp_el.get('class')[0]}"
    comp_val = clean_str(comp_el.get_text()) if comp_el else "KHÔNG TÌM THẤY"
    discovered_fields["company"] = (comp_sel, comp_val)
    print(f"{'Công ty (company)':<22} | {comp_sel:<32} | {comp_val[:35]}")

    # Mức lương
    sal_el = soup.select_one(".box-header-job__salary--title, .salary, [class*='salary']")
    sal_sel = ".salary" if not sal_el else f".{sal_el.get('class')[0]}"
    sal_val = clean_str(sal_el.get_text()) if sal_el else "KHÔNG TÌM THẤY"
    discovered_fields["salary"] = (sal_sel, sal_val)
    print(f"{'Mức lương (salary)':<22} | {sal_sel:<32} | {sal_val[:35]}")

    # Hạn nộp
    dead_el = soup.select_one("[class*='deadline'], [class*='expire']")
    dead_sel = "[class*='deadline']" if not dead_el else f".{dead_el.get('class')[0]}"
    dead_val = clean_str(dead_el.get_text()) if dead_el else "KHÔNG TÌM THẤY"
    discovered_fields["deadline"] = (dead_sel, dead_val)
    print(f"{'Hạn nộp (deadline)':<22} | {dead_sel:<32} | {dead_val[:35]}")

    # Kinh nghiệm
    exp_el = soup.select_one("[class*='experience'], div:-soup-contains('Kinh nghiệm')")
    exp_val = clean_str(exp_el.get_text()) if exp_el else "KHÔNG TÌM THẤY"
    print(f"{'Kinh nghiệm (exp)':<22} | {'[class*=\"experience\"]':<32} | {exp_val[:35]}")

    # 3. Dò tìm các khối nội dung lớn (Content Blocks) & Thẻ Tags
    print("\n📜 3. DÒ TÌM CÁC KHỐI NỘI DUNG LỚN & THẺ TAGS (ZERO LOSS):")
    desc_el = soup.select_one(".job-description, .box-job-information-detail-item:has(h2:-soup-contains('Mô tả')) .box-job-information-detail-item__text")
    req_el = soup.select_one(".job-requirements, .box-job-information-detail-item:has(h2:-soup-contains('Yêu cầu')) .box-job-information-detail-item__text")
    ben_el = soup.select_one(".job-benefits, .box-job-information-detail-item:has(h2:-soup-contains('Quyền lợi')) .box-job-information-detail-item__text")
    
    print(f"  - Khối Mô tả (Description): {'✅ Tìm thấy' if desc_el else '⚠️ Cần selector tùy biến'}")
    print(f"  - Khối Yêu cầu (Requirements): {'✅ Tìm thấy' if req_el else '⚠️ Cần selector tùy biến'}")
    print(f"  - Khối Quyền lợi (Benefits): {'✅ Tìm thấy' if ben_el else '⚠️ Cần selector tùy biến'}")

    tag_elements = soup.select(".badge-tag-list .item, .tag, .badge, [class*='skill'], [class*='tag'] a, [class*='tag'] span")
    clean_tags = list(dict.fromkeys([clean_str(t.get_text()) for t in tag_elements if len(clean_str(t.get_text())) in range(2, 35)]))[:10]
    if clean_tags:
        print(f"  ✅ Phát hiện {len(clean_tags)} thẻ tags đại diện: {clean_tags}")
    else:
        print("  ℹ️ Không phát hiện thẻ tag dạng danh sách.")

    # 4. Xác định Container Selector băm Hash
    print("\n🛡️ 4. CHỈ ĐỊNH CONTAINER SELECTOR BĂM CLEAN HTML HASH:")
    candidate_containers = [".job-detail", "#job-detail", ".box-header-job", "article", "main", "body"]
    best_container = "body"
    max_len = 0
    for cand in candidate_containers:
        target = soup.select_one(cand)
        if target:
            t_len = len(target.get_text(strip=True))
            if t_len > 250 and t_len > max_len and cand != "body":
                max_len = t_len
                best_container = cand

    clean_hash = calculate_container_html_hash(html_content, container_selector=best_container)
    print(f"  👉 Container Selector tối ưu: '{best_container}' (Độ dài text: {max_len} chars)")
    print(f"  👉 Clean Hash SHA256 mẫu:     {clean_hash}")

    # 5. Sinh Code Python Parser Gợi Ý (Bảo Toàn 100% Trường - Zero Information Loss)
    print("\n💻 5. CODE PYTHON PARSER GỢI Ý (ZERO INFORMATION LOSS):")
    print("-" * 80)
    snippet = f'''from bs4 import BeautifulSoup
from crawlers.common.url_ledger import calculate_container_html_hash

def parse_raw_payload(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 1. Clean Container Hash
    content_hash = calculate_container_html_hash(html_content, container_selector="{best_container}")
    
    # 2. Bóc tách 100% trường dữ liệu gốc (Zero Information Loss)
    # Lưu ý: Giữ nguyên cấu trúc HTML, không tự ý parse thành list[str] ở tầng cào thô
    return {{
        "title": soup.select_one("{title_sel_str}").get_text(strip=True) if soup.select_one("{title_sel_str}") else None,
        "company_name": soup.select_one("{comp_sel}").get_text(strip=True) if soup.select_one("{comp_sel}") else None,
        "salary_raw": soup.select_one("{sal_sel}").get_text(strip=True) if soup.select_one("{sal_sel}") else None,
        "deadline_raw": soup.select_one("{dead_sel}").get_text(strip=True) if soup.select_one("{dead_sel}") else None,
        "tag_groups": {{g.select_one(".job-tags__group-name").get_text(strip=True): [a.get_text(strip=True) for a in g.select(".item, a") if a != g.select_one(".job-tags__group-name")] for g in soup.select(".job-tags__group")}} if soup.select(".job-tags__group") else [t.get_text(strip=True) for t in soup.select(".tag, [class*='tag'] span")],
        "description_html": str(soup.select_one(".job-description, .box-job-information-detail-item__text")),
        "requirements_html": str(soup.select_one(".job-requirements, .box-job-information-required-candidate .box-job-information-detail-item__text")),
        "benefits_html": str(soup.select_one(".job-benefits, .box-job-information-benefit .box-job-information-detail-item__text")),
        "content_hash": content_hash,
        "raw_html": html_content,
    }}
'''
    print(snippet)
    print("=" * 80 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phân tích cây DOM từ file HTML thô đại diện.")
    parser.add_argument("--html", required=True, help="Đường dẫn tới file HTML mẫu đại diện")
    args = parser.parse_args()
    analyze_html_file(args.html)
