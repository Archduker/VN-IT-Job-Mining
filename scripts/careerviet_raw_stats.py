#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thống kê chất lượng dữ liệu cào thô (Raw As-Is) cho nguồn CareerViet.

Đọc file batch JSON từ data/raw/careerviet/dt=YYYY-MM-DD/ và hiển thị:
1. Tỷ lệ rỗng của tất cả các trường trong raw_fields.
2. Thống kê phân bố salary_raw.
3. Phân bố giá trị experience_raw, seniority_raw, employment_type_raw, location_raw (Top 10).
4. Kiểm tra sâu 3 tin rỗng experience_raw:
   - experienceRequirements trong embedded_json_raw
   - Kiểm tra tồn tại file HTML và quét dòng có chữ 'Kinh nghiệm'
5. Khảo sát tags_raw vs skills trong embedded_json_raw:
   - Các tin tags_raw rỗng: skills trong JSON-LD có gì không?
   - Các tin tags_raw không rỗng: skills khác tags_raw thế nào?
6. Thống kê độ phủ của embedded_json_raw và monthsOfExperience.
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter
from typing import Any, Dict, List


def find_latest_batch(base_dir: str = "data/raw/careerviet") -> str:
    """Tìm file batch JSON mới nhất trong thư mục raw partitioned."""
    pattern = os.path.join(base_dir, "dt=*", "batch_*.json")
    matches = glob.glob(pattern)
    if not matches:
        matches = glob.glob(os.path.join(base_dir, "*.json"))
        matches = [m for m in matches if "cdc_catalog" not in m]

    if not matches:
        raise FileNotFoundError(f"Không tìm thấy file batch nào theo mẫu: {pattern}")
    matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return matches[0]


def is_empty(val: Any) -> bool:
    """Kiểm tra giá trị có được coi là rỗng hay không."""
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    if isinstance(val, (list, dict, set, tuple)) and len(val) == 0:
        return True
    return False


def print_counter_table(title: str, counter: Counter, total: int, limit: int | None = None) -> None:
    print("\n" + "-" * 75)
    print(f"BẢNG PHÂN BỐ: {title}")
    print("-" * 75)
    print(f"{'STT':<4} | {'Giá trị':<45} | {'Số lượng':<10} | {'Tỷ lệ':<10}")
    print("-" * 75)
    items = counter.most_common(limit) if limit else counter.most_common()
    for idx, (val, cnt) in enumerate(items, start=1):
        pct = (cnt / total) * 100 if total > 0 else 0
        disp_val = "[RỖNG / NONE]" if val == "" or val is None else str(val)
        if len(disp_val) > 43:
            disp_val = disp_val[:40] + "..."
        print(f"{idx:<4} | {disp_val:<45} | {cnt:<10} | {pct:8.2f}%")
    print("-" * 75)


def analyze_batch(batch_path: str) -> None:
    print("=" * 80)
    print("BÁO CÁO THỐNG KÊ TOÀN DIỆN DỮ LIỆU CÀO THÔ CAREERVIET (BƯỚC 3.6)")
    print(f"File nguồn: {batch_path}")
    print("=" * 80)

    with open(batch_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("Lỗi: Dữ liệu batch không phải dạng list.")
        return

    total = len(data)
    print(f"\nTổng số bản ghi trong batch: {total}\n")

    # 1. Tỷ lệ rỗng của tất cả các trường trong raw_fields
    all_keys = set()
    for item in data:
        rf = item.get("raw_fields", {})
        all_keys.update(rf.keys())

    print("-" * 75)
    print("1. TỶ LỆ RỖNG TOÀN BỘ CÁC TRƯỜNG RAW_FIELDS:")
    print("-" * 75)
    print(f"{'STT':<4} | {'Tên trường (raw_fields)':<25} | {'Số rỗng':<10} | {'Tổng số':<8} | {'Tỷ lệ rỗng':<12}")
    print("-" * 75)

    empty_records_by_field: Dict[str, List[Dict[str, Any]]] = {}

    for idx, k in enumerate(sorted(all_keys), start=1):
        empty_cnt = 0
        empty_records_by_field[k] = []
        for item in data:
            val = item.get("raw_fields", {}).get(k)
            if is_empty(val):
                empty_cnt += 1
                empty_records_by_field[k].append(item)
        rate = (empty_cnt / total) * 100 if total > 0 else 0
        print(f"{idx:<4} | {k:<25} | {empty_cnt:<10} | {total:<8} | {rate:10.2f}%")
    print("-" * 75)

    # 2. Thống kê phân bố salary_raw
    salary_counts = Counter()
    for item in data:
        s_val = item.get("raw_fields", {}).get("salary_raw", "")
        salary_counts[s_val] += 1
    print_counter_table("salary_raw", salary_counts, total)

    # 2a. Phân bố các giá trị của experience_raw, seniority_raw, employment_type_raw, location_raw (top 10)
    print("\n" + "=" * 80)
    print("2a. PHÂN BỐ CÁC GIÁ TRỊ KHÁC NHAU VÀ SỐ LƯỢNG (TOP GIÁ TRỊ):")
    print("=" * 80)

    for field_name, limit in [
        ("experience_raw", None),
        ("seniority_raw", None),
        ("employment_type_raw", None),
        ("location_raw", 10),
    ]:
        c = Counter()
        for item in data:
            val = item.get("raw_fields", {}).get(field_name, "")
            c[val] += 1
        label = f"{field_name} (Top 10)" if limit else field_name
        print_counter_table(label, c, total, limit=limit)

    # 2b. Chi tiết 3 tin experience_raw rỗng (35C87378, 35C8A764, 35C8A798)
    print("\n" + "=" * 80)
    print("2b. KIỂM TRA SÂU CÁC BẢN GHI RỖNG experience_raw (35C87378, 35C8A764, 35C8A798):")
    print("=" * 80)

    target_empty_ids = ["35C87378", "35C8A764", "35C8A798"]
    for jid in target_empty_ids:
        item = next((x for x in data if x.get("_technical", {}).get("job_id") == jid), None)
        if not item:
            print(f"\n[Job ID: {jid}] -> KHÔNG TÌM THẤY TRONG BATCH!")
            continue

        rf = item.get("raw_fields", {})
        emb = item.get("embedded_json_raw") or {}
        exp_req = emb.get("experienceRequirements", None)
        html_path = f"data/raw/careerviet/html/{jid}.html"

        print(f"\n--- Job ID: {jid} ---")
        print(f"  - Tiêu đề      : {rf.get('title_raw')}")
        print(f"  - Công ty      : {rf.get('company_raw')}")
        print(f"  - URL          : {item.get('_technical', {}).get('url')}")
        print(f"  - File HTML    : {html_path}")
        html_exists = os.path.exists(html_path)
        print(f"    -> Tệp HTML cục bộ: {'TỒN TẠI' if html_exists else 'CHƯA TỒN TẠI'}")
        print(f"  - Giá trị experienceRequirements trong embedded_json_raw:")
        print(f"      {json.dumps(exp_req, ensure_ascii=False)}")

        # Quét HTML tìm chữ "Kinh nghiệm"
        if html_exists:
            print(f"  - Đối chiếu chữ 'Kinh nghiệm' trong DOM và file HTML:")
            with open(html_path, "r", encoding="utf-8") as hf:
                html_text = hf.read()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            page_el = soup.find(class_="job-detail-page") or soup

            # 1. Trong hộp metadata (.detail-box li)
            box_matches = [li.get_text(" ", strip=True) for li in page_el.select(".detail-box li") if "kinh nghiệm" in li.text.lower()]
            if box_matches:
                print(f"      [Trong .detail-box]: {box_matches}")
            else:
                print(f"      [Trong .detail-box]: KHÔNG CÓ thẻ nào chứa 'Kinh nghiệm' (nhà tuyển dụng không khai báo)")

            # 2. Trong nội dung JD chi tiết (.job-detail-content)
            jd_matches = []
            for el in page_el.select(".job-detail-content p, .job-detail-content li"):
                txt = el.get_text(" ", strip=True)
                if "kinh nghiệm" in txt.lower() and txt not in jd_matches:
                    jd_matches.append(txt)
                    if len(jd_matches) >= 3:
                        break

            if jd_matches:
                print(f"      [Trong nội dung JD]: Tìm thấy {len(jd_matches)} câu có nhắc tới kinh nghiệm:")
                for s in jd_matches:
                    print(f"         • {s}")
            else:
                print(f"      [Trong nội dung JD]: Không có đoạn văn nào nhắc đến kinh nghiệm.")

            # 3. Trích xuất vị trí trong HTML thô
            raw_occurrences = []
            for m in re.finditer(r"kinh\s+nghiệm", html_text, flags=re.IGNORECASE):
                start = max(0, m.start() - 30)
                end = min(len(html_text), m.end() + 50)
                snip = html_text[start:end].replace("\n", " ").strip()
                # Lọc bỏ các template string dùng chung nếu có
                if "null Năm" in snip or "lĩnh vực" in snip or "Yêu cầu" in snip:
                    raw_occurrences.append((m.start(), snip))
                elif len(raw_occurrences) < 2:
                    raw_occurrences.append((m.start(), snip))

            print(f"      [Trích đoạn HTML thô (mẫu tiêu biểu)]: ")
            for pos, snip in raw_occurrences[:3]:
                print(f"         - (Vị trí ký tự {pos}): ...{snip}...")
        print()

    # 2c. Khảo sát tags_raw vs skills trong embedded_json_raw
    print("=" * 80)
    print("2c. KHẢO SÁT tags_raw VS skills TRONG embedded_json_raw:")
    print("=" * 80)

    tags_empty_items = [x for x in data if is_empty(x.get("raw_fields", {}).get("tags_raw"))]
    tags_present_items = [x for x in data if not is_empty(x.get("raw_fields", {}).get("tags_raw"))]

    print(f"Tổng số tin tags_raw rỗng    : {len(tags_empty_items)}")
    print(f"Tổng số tin tags_raw có dữ liệu: {len(tags_present_items)}\n")

    # Phân tích nhóm tags_raw rỗng
    empty_with_skills = 0
    print("--- 1. NHÓM TIN CÓ tags_raw RỖNG: GIÁ TRỊ skills TRONG JSON-LD ---")
    for idx, it in enumerate(tags_empty_items, start=1):
        jid = it.get("_technical", {}).get("job_id")
        title = it.get("raw_fields", {}).get("title_raw")
        emb = it.get("embedded_json_raw") or {}
        skills_val = emb.get("skills")
        if skills_val and str(skills_val).strip():
            empty_with_skills += 1
            skills_str = str(skills_val)
            if len(skills_str) > 75:
                skills_str = skills_str[:72] + "..."
            print(f"  [{idx:2d}] {jid} ({title[:30]}): skills = '{skills_str}'")
        else:
            print(f"  [{idx:2d}] {jid} ({title[:30]}): skills = [RỖNG / NONE]")

    print(f"\n=> KẾT QUẢ: Trong {len(tags_empty_items)} tin có tags_raw rỗng, có {empty_with_skills}/{len(tags_empty_items)} tin có skills KHÔNG RỖNG trong JSON-LD.")

    # Phân tích nhóm tags_raw có dữ liệu
    print("\n--- 2. NHÓM TIN CÓ tags_raw KHÔNG RỖNG: SO SÁNH tags_raw VS skills ---")
    print(f"{'Job ID':<10} | {'tags_raw (DOM widget)':<35} | {'skills (JSON-LD)':<40}")
    print("-" * 90)
    for it in tags_present_items[:8]:  # Mẫu 8 tin
        jid = it.get("_technical", {}).get("job_id")
        tags = it.get("raw_fields", {}).get("tags_raw", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        emb = it.get("embedded_json_raw") or {}
        skills_str = str(emb.get("skills", ""))
        if len(tags_str) > 33:
            tags_str = tags_str[:30] + "..."
        if len(skills_str) > 38:
            skills_str = skills_str[:35] + "..."
        print(f"{jid:<10} | {tags_str:<35} | {skills_str:<40}")
    print("-" * 90)
    print("Nhận xét so sánh:")
    print(" - tags_raw: là danh sách tags ngắn được người dùng gắn trực tiếp ở widget cuối bài (vd: Java, Python).")
    print(" - skills (JSON-LD): là chuỗi từ khóa mở rộng do hệ thống CareerViet tự sinh/gợi ý theo chức danh.")

    # 2d. Thống kê embedded_json_raw và monthsOfExperience
    print("\n" + "=" * 80)
    print("2d. THỐNG KÊ embedded_json_raw VÀ monthsOfExperience:")
    print("=" * 80)

    has_emb_cnt = sum(1 for x in data if x.get("embedded_json_raw") is not None)
    no_emb_cnt = total - has_emb_cnt
    print(f"- Số tin CÓ embedded_json_raw    : {has_emb_cnt}/{total} ({(has_emb_cnt/total)*100:.2f}%)")
    print(f"- Số tin KHÔNG CÓ embedded_json_raw: {no_emb_cnt}/{total} ({(no_emb_cnt/total)*100:.2f}%)")

    months_counter = Counter()
    missing_months_cnt = 0
    zero_months_cnt = 0

    for it in data:
        emb = it.get("embedded_json_raw")
        if not emb:
            missing_months_cnt += 1
            continue
        exp_req = emb.get("experienceRequirements")
        if not exp_req or not isinstance(exp_req, dict):
            missing_months_cnt += 1
            continue
        if "monthsOfExperience" not in exp_req:
            missing_months_cnt += 1
            continue

        m_val = exp_req.get("monthsOfExperience")
        if m_val is None:
            missing_months_cnt += 1
        else:
            months_counter[m_val] += 1
            if m_val == 0:
                zero_months_cnt += 1

    print(f"- Số tin có monthsOfExperience = 0: {zero_months_cnt}/{total} ({(zero_months_cnt/total)*100:.2f}%)")
    print(f"- Số tin thiếu monthsOfExperience : {missing_months_cnt}/{total} ({(missing_months_cnt/total)*100:.2f}%)")
    print_counter_table("Phân bố monthsOfExperience", months_counter, total)
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Thống kê dữ liệu cào thô CareerViet")
    parser.add_argument(
        "--batch-path",
        type=str,
        default=None,
        help="Đường dẫn đến file batch JSON. Mặc định tự tìm file mới nhất.",
    )
    args = parser.parse_args()

    batch_path = args.batch_path
    if not batch_path:
        try:
            batch_path = find_latest_batch()
        except FileNotFoundError as err:
            print(f"Lỗi: {err}")
            sys.exit(1)

    analyze_batch(batch_path)


if __name__ == "__main__":
    main()
