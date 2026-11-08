#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/read_eda_diagnosis.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ công cụ trích xuất Bệnh án Chất lượng Dữ liệu & Bản thiết kế Tiền xử lý (EDA Diagnosis Extractor)
từ 8 Jupyter Notebooks EDA đơn nguồn (`collection/reports/EDA_<source>.ipynb`).

Sứ mệnh:
  - Phục vụ nguyên tắc "EDA-First / Diagnosis-First Protocol": AI Agent và kỹ sư bắt buộc
    phải nạp bệnh án dữ liệu trước khi thực hiện tiền xử lý.
  - Tối ưu hóa 95% token: Lọc sạch 100% mã ảnh Base64, đồ thị và mã thực thi thừa,
    chỉ giữ lại:
      * Bảng kiểm kê trường (Field Inventory)
      * 5 Phân vùng lỗi kỹ thuật WHAT - WHY - HOW (Completeness, Validity, Uniqueness, Distribution, Bias)
      * Chương 7: Kết luận kỹ thuật & Bản thiết kế tiền xử lý (Preprocessing Blueprint)

Cách dùng CLI:
  python scripts/read_eda_diagnosis.py --source topcv
  python scripts/read_eda_diagnosis.py --source all --format markdown
  python scripts/read_eda_diagnosis.py --source vieclam24h --format json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

VALID_SOURCES = [
    "careerviet",
    "glints",
    "itviec",
    "jobsgo",
    "topcv",
    "topdev",
    "vieclam24h",
    "vietnamworks",
]


def extract_eda_diagnosis(source: str, notebook_path: Optional[str] = None) -> Dict[str, Any]:
    """Trích xuất cô đọng phân vùng lỗi và bản thiết kế tiền xử lý từ notebook EDA.

    Args:
        source: Tên sàn (ví dụ: 'topcv', 'vieclam24h',...).
        notebook_path: Đường dẫn tới file notebook (nếu có, mặc định tìm trong collection/reports/).

    Returns:
        Dict chứa các mục chẩn đoán: title, inventory, pillars (1-5 WHAT-WHY-HOW), blueprint_ch7.
    """
    clean_src = source.lower().strip()
    if clean_src not in VALID_SOURCES:
        raise ValueError(f"Nguồn '{source}' không hợp lệ. Chọn 1 trong: {VALID_SOURCES}")

    if not notebook_path:
        base_dir = Path(__file__).resolve().parent.parent
        notebook_path = str(base_dir / f"collection/reports/EDA_{clean_src}.ipynb")

    if not os.path.exists(notebook_path):
        raise FileNotFoundError(f"Không tìm thấy notebook EDA tại: {notebook_path}")

    with open(notebook_path, "r", encoding="utf-8") as f:
        nb_data = json.load(f)

    diagnosis: Dict[str, Any] = {
        "source": clean_src,
        "notebook_path": notebook_path,
        "title": f"Bệnh án dữ liệu EDA nguồn {clean_src.upper()}",
        "field_inventory": None,
        "pillars": {},
        "blueprint_ch7": None,
        "raw_diagnostic_sections": [],
    }

    cells = nb_data.get("cells", [])
    
    pillar_keywords = {
        "pillar_1_completeness": ["Trụ Cột 1", "Completeness", "Độ Hoàn Thiện"],
        "pillar_2_validity": ["Trụ Cột 2", "Validity", "Tính Hợp Lệ"],
        "pillar_3_uniqueness": ["Trụ Cột 3", "Uniqueness", "Tính Duy Nhất"],
        "pillar_4_distribution": ["Trụ Cột 4", "Distribution", "Hình Thái Phân Phối"],
        "pillar_5_bias": ["Trụ Cột 5", "Bias", "Độ Thiên Lệch"],
    }

    current_pillar = None

    for cell in cells:
        if cell.get("cell_type") != "markdown":
            continue

        src = "".join(cell.get("source", []))
        if not src.strip():
            continue

        # 1. Bảng kiểm kê trường (Chương 1)
        if "Chương 1:" in src or "Field Inventory" in src:
            diagnosis["field_inventory"] = src.strip()

        # 2. Nhận diện tiêu đề Chương 2-6
        for p_key, kws in pillar_keywords.items():
            if any(kw in src for kw in kws) and ("Chương" in src or "Trụ Cột" in src):
                current_pillar = p_key

        # 3. Trích xuất khối chẩn đoán WHAT - WHY - HOW
        if "WHAT" in src and "WHY" in src and "HOW" in src:
            diagnosis["raw_diagnostic_sections"].append(src.strip())
            if current_pillar:
                diagnosis["pillars"][current_pillar] = src.strip()

        # 4. Trích xuất Chương 7 (Blueprint & 3 Deliverables)
        if "Chương 7:" in src or "Bản Thiết Kế Tiền Xử Lý" in src or "Chuẩn Xuất Bản 3 File" in src:
            diagnosis["blueprint_ch7"] = src.strip()

    return diagnosis


def format_diagnosis_as_markdown(diagnosis: Dict[str, Any]) -> str:
    """Định dạng bệnh án EDA thành văn bản Markdown cô đọng, dễ đọc cho AI Agent."""
    src = diagnosis["source"].upper()
    lines = [
        f"# 📋 BỆNH ÁN DỮ LIỆU & BẢN THIẾT KẾ TIỀN XỬ LÝ (EDA DIAGNOSIS) — {src}",
        f"> **Nguồn tuyển dụng:** `{diagnosis['source']}`  ",
        f"> **File gốc:** `{diagnosis['notebook_path']}`  ",
        "> **Nguyên tắc:** *EDA-First Protocol — Chẩn đoán tiên quyết trước khi can thiệp mã nguồn tiền xử lý.*\n",
        "---",
    ]

    # Phân vùng 5 Trụ Cột WHAT - WHY - HOW
    lines.append("## 1. PHÂN VÙNG 5 TRỤ CỘT LỖI DỮ LIỆU (WHAT — WHY — HOW)\n")
    if diagnosis["pillars"]:
        for pillar_name, content in diagnosis["pillars"].items():
            readable_title = pillar_name.replace("_", " ").upper()
            lines.append(f"### 🔍 {readable_title}")
            lines.append(content)
            lines.append("\n---\n")
    else:
        for idx, block in enumerate(diagnosis["raw_diagnostic_sections"], 1):
            lines.append(f"### 🔍 Phân vùng chẩn đoán {idx}")
            lines.append(block)
            lines.append("\n---\n")

    # Chương 7 Blueprint
    lines.append("## 2. KẾT LUẬN KỸ THUẬT & BẢN THIẾT KẾ TIỀN XỬ LÝ (PREPROCESSING BLUEPRINT)\n")
    if diagnosis["blueprint_ch7"]:
        lines.append(diagnosis["blueprint_ch7"])
    else:
        lines.append("*Chưa tìm thấy khối Chương 7 trong notebook.*")

    lines.append("\n---\n")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bộ trích xuất bệnh án dữ liệu EDA (Token-Efficient EDA Diagnosis Extractor)"
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default="all",
        help=f"Tên sàn cần trích xuất ({', '.join(VALID_SOURCES)}) hoặc 'all'",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Định dạng đầu ra (markdown hoặc json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Đường dẫn file lưu kết quả (nếu không có sẽ in ra stdout)",
    )

    args = parser.parse_args()

    targets = VALID_SOURCES if args.source.lower() == "all" else [args.source.lower()]

    results: Dict[str, Any] = {}
    md_outputs: List[str] = []

    for src in targets:
        try:
            diag = extract_eda_diagnosis(src)
            results[src] = diag
            md_outputs.append(format_diagnosis_as_markdown(diag))
        except Exception as e:
            sys.stderr.write(f"❌ Lỗi khi đọc EDA nguồn {src}: {e}\n")

    if args.format == "json":
        final_output = json.dumps(results if len(targets) > 1 else results[targets[0]], ensure_ascii=False, indent=2)
    else:
        final_output = "\n\n".join(md_outputs)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(final_output)
        print(f"✅ Đã xuất bệnh án EDA vào: {args.output}")
    else:
        print(final_output)


if __name__ == "__main__":
    main()
