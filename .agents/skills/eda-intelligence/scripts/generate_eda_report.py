#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tool tự động sinh Báo cáo EDA sơ bộ từ URL Ledger và tập dữ liệu cào thô.

Sử dụng:
    python .agents/skills/eda-intelligence/scripts/generate_eda_report.py --source topcv
"""

import argparse
import json
import sys
from pathlib import Path

# Thêm workspace root vào sys.path
ROOT_DIR = Path(__file__).resolve().parents[4]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import numpy as np



def generate_eda(source: str, output_path: str = None):
    source = source.lower().strip()
    ledger_path = Path(f"data/url_ledger/{source}/catalog_master.json")

    print(f"\n📊 [EDA INTELLIGENCE] Đang phân tích dữ liệu nguồn: {source.upper()}")

    if not ledger_path.exists():
        print(f"⚠️ Chưa tìm thấy catalog tại {ledger_path}. Hãy chạy crawler trước.")
        return

    with open(ledger_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    df = pd.DataFrame(list(catalog.values()))
    total_records = len(df)
    print(f"Tổng số bản ghi trong Ledger: {total_records}")

    # 1. Cơ cấu trạng thái vòng đời
    status_counts = df["status"].value_counts().to_dict() if "status" in df.columns else {}
    print("\n1. Vòng đời bài đăng (Lifecycle Status):")
    for st, cnt in status_counts.items():
        pct = (cnt / total_records) * 100
        print(f"  - {st:<12}: {cnt:>5} ({pct:.1f}%)")

    # 2. Đánh giá Missing Values
    print("\n2. Tỷ lệ khuyết thiếu (Missing Rate):")
    missing_report = []
    for col in df.columns:
        null_count = df[col].isnull().sum() + (df[col] == "").sum()
        null_pct = (null_count / total_records) * 100
        missing_report.append((col, null_count, null_pct))
        print(f"  - {col:<22}: {null_count:>5} rỗng ({null_pct:.1f}%)")

    # 3. Xuất file markdown nếu yêu cầu
    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(f"# BÁO CÁO EDA SƠ BỘ — NGUỒN {source.upper()}\n\n")
            f.write(f"- **Tổng số URL phát hiện:** {total_records}\n")
            f.write("## 1. Trạng thái vòng đời\n\n")
            f.write("| Trạng thái | Số lượng | Tỷ lệ (%) |\n| :--- | :---: | :---: |\n")
            for st, cnt in status_counts.items():
                f.write(f"| `{st}` | {cnt} | {(cnt/total_records)*100:.1f}% |\n")
            f.write("\n## 2. Kiểm kê tỷ lệ khuyết thiếu\n\n")
            f.write("| Tên trường | Số lượng rỗng | Tỷ lệ null (%) |\n| :--- | :---: | :---: |\n")
            for col, n_cnt, n_pct in missing_report:
                f.write(f"| `{col}` | {n_cnt} | {n_pct:.1f}% |\n")
        print(f"\n✅ Đã lưu báo cáo thành công tại: {out_p}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sinh báo cáo EDA sơ bộ từ ledger.")
    parser.add_argument("--source", required=True, help="Tên sàn (ví dụ: topcv, topdev)")
    parser.add_argument("--out", required=False, help="Đường dẫn lưu file markdown báo cáo")
    args = parser.parse_args()
    generate_eda(args.source, args.out)
