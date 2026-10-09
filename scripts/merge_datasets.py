#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts.merge_datasets
~~~~~~~~~~~~~~~~~~~~~~~~~
Tích hợp và gộp dữ liệu tuyển dụng từ tất cả các nguồn crawler.

Quy trình:
1. Quét toàn bộ thư mục data/<source>/dt=YYYY-MM-DD/batch_*.json (hỗ trợ cả .jsonl fallback).
2. Tải và chuẩn hóa từng bản ghi JobRecord.
3. Khử trùng lặp dựa trên dedup_key (giữ bản ghi crawl mới nhất).
4. Thống kê số lượng: tổng số record, số record duy nhất, phân bố theo nguồn,
   tỷ lệ phân bố ngôn ngữ ('vi' vs 'en'), số lượng tin có mức lương bóc tách.
5. Ghi ra file duy nhất: data/processed/combined_jobs.json dạng mảng JSON [ ... ]
   sử dụng cơ chế atomic write (.tmp -> replace).
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Đảm bảo import được module dự án
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.common.schema import JobRecord, validate_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("merge_datasets")


def parse_job_file(file_path: Path) -> List[Dict[str, Any]]:
    """Đọc các bản ghi từ một file .json (mảng) hoặc .jsonl (dòng)."""
    records: List[Dict[str, Any]] = []
    if not file_path.exists() or file_path.stat().st_size == 0:
        return records

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return records

            if file_path.suffix == ".json" or content.startswith("["):
                try:
                    data = json.loads(content)
                    if isinstance(data, list):
                        records.extend(data)
                    elif isinstance(data, dict):
                        records.append(data)
                except json.JSONDecodeError:
                    # Fallback parse line by line
                    for line in content.splitlines():
                        line = line.strip()
                        if line:
                            try:
                                records.append(json.loads(line))
                            except Exception:
                                pass
            else:
                for line in content.splitlines():
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            pass
    except Exception as exc:
        logger.warning("Không thể đọc file %s: %s", file_path, exc)

    return records


def merge_datasets(
    input_dir: Path | str = "data",
    output_file: Path | str = "data/processed/combined_jobs.json",
) -> Dict[str, Any]:
    """Gộp tất cả các file batch từ input_dir thành output_file."""
    base_dir = Path(input_dir)
    out_path = Path(output_file)

    if not base_dir.exists():
        logger.error("Thư mục đầu vào không tồn tại: %s", base_dir)
        return {"total_read": 0, "total_unique": 0, "sources": {}}

    logger.info("Bắt đầu quét dữ liệu trong: %s", base_dir.resolve())

    # Tìm các file batch_*.json và batch_*.jsonl
    # Loại trừ thư mục processed
    all_files: List[Path] = []
    for p in base_dir.rglob("batch_*.json"):
        if "processed" not in p.parts:
            all_files.append(p)
    for p in base_dir.rglob("batch_*.jsonl"):
        if "processed" not in p.parts:
            # Chỉ thêm nếu chưa có bản .json tương ứng
            json_equiv = p.with_suffix(".json")
            if json_equiv not in all_files:
                all_files.append(p)

    logger.info("Tìm thấy %d file batch cần gộp.", len(all_files))

    raw_count = 0
    records_by_key: Dict[str, Dict[str, Any]] = {}
    sources_counter: Counter[str] = Counter()
    lang_counter: Counter[str] = Counter()
    salary_extracted_count = 0

    for fpath in sorted(all_files):
        items = parse_job_file(fpath)
        for item in items:
            raw_count += 1
            # Validate cấu trúc
            try:
                # Đảm bảo schema hợp lệ
                rec = validate_record(item)
                item_dict = rec.model_dump(mode="json", by_alias=True)
            except Exception:
                # Nếu không validate được bằng JobRecord, kiểm tra cơ bản dict
                if not isinstance(item, dict) or "_meta" not in item:
                    continue
                item_dict = item

            meta = item_dict.get("_meta", {})
            dedup_key = meta.get("dedup_key") or f"{meta.get('source', 'unknown')}:{meta.get('source_job_id', raw_count)}"
            crawled_at = meta.get("crawled_at", "")

            # Nếu đã có bản ghi, ưu tiên bản ghi mới hơn theo crawled_at
            if dedup_key in records_by_key:
                existing_crawled_at = records_by_key[dedup_key].get("_meta", {}).get("crawled_at", "")
                if str(crawled_at) > str(existing_crawled_at):
                    records_by_key[dedup_key] = item_dict
            else:
                records_by_key[dedup_key] = item_dict

    combined_list = list(records_by_key.values())
    unique_count = len(combined_list)

    for item in combined_list:
        meta = item.get("_meta", {})
        raw = item.get("raw", {})
        src = meta.get("source", "unknown")
        lang = meta.get("language", "vi")
        sources_counter[src] += 1
        sal_obj = raw.get("salary") or {}
        has_sal = (
            raw.get("salary_min") is not None
            or raw.get("salary_max") is not None
            or sal_obj.get("salary_min") is not None
            or sal_obj.get("salary_max") is not None
        )
        if has_sal:
            salary_extracted_count += 1

    logger.info("=" * 60)
    logger.info("TỔNG KẾT DỮ LIỆU:")
    logger.info("  - Tổng số bản ghi đọc được : %d", raw_count)
    logger.info("  - Số bản ghi duy nhất     : %d", unique_count)
    logger.info("  - Số trùng lặp loại bỏ     : %d", raw_count - unique_count)
    logger.info("  - Thống kê theo nguồn:")
    for src, cnt in sources_counter.most_common():
        logger.info("      + %-15s: %d", src, cnt)
    logger.info("  - Thống kê ngôn ngữ:")
    for lang, cnt in lang_counter.items():
        logger.info("      + %-15s: %d", lang, cnt)
    logger.info("  - Tin có bóc tách lương    : %d (%.1f%%)",
                salary_extracted_count,
                (salary_extracted_count / unique_count * 100) if unique_count else 0.0)
    logger.info("=" * 60)

    # Ghi ra file đích an toàn
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(combined_list, f, ensure_ascii=False, indent=2)

    tmp_path.replace(out_path)
    logger.info("Đã xuất file thành công: %s (%d bytes)", out_path.resolve(), out_path.stat().st_size)

    return {
        "total_read": raw_count,
        "total_unique": unique_count,
        "duplicates_removed": raw_count - unique_count,
        "sources": dict(sources_counter),
        "languages": dict(lang_counter),
        "salary_extracted_count": salary_extracted_count,
        "output_file": str(out_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VN-IT-Job-Mining Data Integration & Merging Tool")
    parser.add_argument(
        "--input-dir",
        "-i",
        type=str,
        default="data",
        help="Thư mục gốc chứa dữ liệu các nguồn crawler (mặc định: data)",
    )
    parser.add_argument(
        "--output-file",
        "-o",
        type=str,
        default="data/processed/combined_jobs.json",
        help="Đường dẫn file JSON đầu ra (mặc định: data/processed/combined_jobs.json)",
    )
    args = parser.parse_args()

    res = merge_datasets(input_dir=args.input_dir, output_file=args.output_file)
    print(f"\n✅ Merge hoàn tất! Tổng cộng {res['total_unique']} jobs đã được ghi vào {res.get('output_file')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
