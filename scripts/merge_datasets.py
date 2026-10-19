#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts.merge_datasets
~~~~~~~~~~~~~~~~~~~~~~~~~
Tích hợp và gộp dữ liệu tuyển dụng từ tất cả các nguồn crawler.

Quy trình:
1. Quét toàn bộ thư mục data/<source>/dt=YYYY-MM-DD/batch_*.json (hỗ trợ cả .jsonl fallback).
   Tự động nạp snapshot thô từ data/raw/* và crawlers/sources/*/samples/sample_*.json
   hoặc test_5_jobs.json để đảm bảo dữ liệu từ tất cả các nguồn crawler được nạp đầy đủ.
2. Tải, trích xuất envelope raw (metadata/raw_payload) và chuẩn hóa từng bản ghi JobRecord.
3. Khử trùng lặp dựa trên dedup_key (giữ bản ghi crawl mới nhất).
4. Thống kê số lượng: tổng số record, số record duy nhất, phân bố theo nguồn,
   tỷ lệ phân bố ngôn ngữ ('vi' vs 'en'), số lượng tin có mức lương bóc tách,
   và tỷ lệ tuân thủ schema JobRecord.
5. Ghi ra các file batch chuẩn theo từng nguồn trong data/<source>/dt=YYYY-MM-DD/batch_001.json
   và xuất file tổng hợp duy nhất: data/processed/combined_jobs.json dạng mảng JSON [ ... ]
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

# Danh sách tất cả các nguồn crawler trong dự án
CRAWLER_SOURCES = [
    "topcv",
    "topdev",
    "vieclam24h",
    "vietnamworks",
    "careerviet",
    "glints",
    "jobsgo",
    "itviec",
]


def parse_job_file(file_path: Path) -> List[Dict[str, Any]]:
    """Đọc các bản ghi từ một file .json (mảng/đối tượng) hoặc .jsonl (dòng)."""
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


def convert_to_job_record(
    item: Dict[str, Any],
    file_path: Optional[Path] = None,
    vnw_crawler: Any = None,
    topcv_crawler: Any = None,
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Chuyển đổi item bất kỳ sang JobRecord dict chuẩn.

    Returns:
        (record_dict, is_valid_schema)
    """
    if not isinstance(item, dict):
        return None, False

    # 1. Trường hợp item đã là cấu trúc JobRecord (_meta & raw)
    if "_meta" in item and "raw" in item:
        try:
            rec = validate_record(item)
            return rec.model_dump(mode="json", by_alias=True), True
        except Exception:
            # Vẫn giữ nguyên dict nếu có _meta
            return item, False

    # 2. Trường hợp envelope raw: metadata & raw_payload
    if "metadata" in item and "raw_payload" in item:
        meta = item["metadata"]
        raw = item["raw_payload"]
        src = str(meta.get("source", "")).lower().strip()

        # 2a. VietnamWorks raw payload
        if src == "vietnamworks" or (isinstance(raw, dict) and "jobTitle" in raw):
            try:
                if vnw_crawler is None:
                    from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler
                    vnw_crawler = VietnamWorksCrawler()
                rec = vnw_crawler.parse_item(raw)
                if rec:
                    return rec.model_dump(mode="json", by_alias=True), True
            except Exception as exc:
                logger.debug("Lỗi parse VietnamWorks raw payload: %s", exc)

        # 2b. TopCV raw payload
        elif src == "topcv":
            try:
                if topcv_crawler is None:
                    from crawlers.sources.topcv.crawler import TopCVCrawler
                    topcv_crawler = TopCVCrawler()

                if isinstance(raw, dict) and "raw_html" in raw:
                    rec = topcv_crawler.parse_item({
                        "job_id": meta.get("job_id"),
                        "url": meta.get("source_url"),
                        "title": raw.get("title"),
                        "html_content": raw.get("raw_html"),
                    })
                    if rec:
                        return rec.model_dump(mode="json", by_alias=True), True

                elif isinstance(raw, dict) and "box-header-job" in raw and file_path:
                    html_path = file_path.with_suffix(".html")
                    html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
                    rec = topcv_crawler.parse_item({
                        "job_id": meta.get("source_job_id") or meta.get("job_id"),
                        "url": meta.get("url") or meta.get("source_url"),
                        "title": raw.get("box-header-job", {}).get("box-header-job__title", ""),
                        "html_content": html_text,
                    })
                    if rec:
                        return rec.model_dump(mode="json", by_alias=True), True
            except Exception as exc:
                logger.debug("Lỗi parse TopCV raw payload: %s", exc)

        # 2c. Generic fallback mapping metadata -> _meta
        try:
            jid = str(meta.get("source_job_id") or meta.get("job_id") or "1")
            adapted_meta = {
                "source": src or "unknown",
                "source_job_id": jid,
                "url": meta.get("source_url") or meta.get("url") or f"https://{src}.vn/jobs/{jid}",
                "dedup_key": f"{src}:{jid}",
                "crawled_at": meta.get("scraped_at") or meta.get("crawled_at") or datetime.now().isoformat(),
                "batch_id": meta.get("batch_id") or f"{datetime.now().strftime('%Y-%m-%d')}_{src}_001",
                "crawler_version": meta.get("crawler_version") or meta.get("scraper_version") or "0.1.0",
                "language": meta.get("language") or "vi",
            }
            rec = validate_record({"_meta": adapted_meta, "raw": raw})
            return rec.model_dump(mode="json", by_alias=True), True
        except Exception:
            pass

    return None, False


def discover_input_files(base_dir: Path, include_snapshots: bool = True) -> List[Path]:
    """Tìm tất cả các file dữ liệu cần nạp, bao gồm cả batch partitions và raw snapshots."""
    all_files: List[Path] = []
    seen_paths = set()

    def add_file(p: Path):
        abs_p = p.resolve()
        if abs_p not in seen_paths and p.is_file() and p.stat().st_size > 0:
            seen_paths.add(abs_p)
            all_files.append(p)

    if base_dir.exists():
        # 1. Các file batch trong data/
        for p in base_dir.rglob("batch_*.json"):
            if "processed" not in p.parts and "minio" not in p.parts:
                add_file(p)
        for p in base_dir.rglob("batch_*.jsonl"):
            if "processed" not in p.parts and "minio" not in p.parts:
                json_equiv = p.with_suffix(".json")
                if json_equiv.resolve() not in seen_paths:
                    add_file(p)

        # 2. Các file raw batch và raw snapshot trong data/
        for p in base_dir.rglob("raw_batch*.json"):
            if "processed" not in p.parts and "minio" not in p.parts:
                add_file(p)
        for p in base_dir.rglob("*_v*.json"):
            if "processed" not in p.parts and "minio" not in p.parts:
                add_file(p)

    # 3. Nạp snapshot từ crawlers/sources/*/samples/ và test_5_jobs.json
    if include_snapshots:
        crawlers_dir = PROJECT_ROOT / "crawlers" / "sources"
        if crawlers_dir.exists():
            for p in crawlers_dir.rglob("sample_*.json"):
                add_file(p)
            for p in crawlers_dir.rglob("test_5_jobs.json"):
                add_file(p)

        # 4. Kiểm tra data/raw/
        raw_root = PROJECT_ROOT / "data" / "raw"
        if raw_root.exists():
            for p in raw_root.rglob("*.json"):
                if "minio" not in p.parts:
                    add_file(p)

    return sorted(all_files)


def merge_datasets(
    input_dir: Path | str = "data",
    output_file: Path | str = "data/processed/combined_jobs.json",
    include_snapshots: Optional[bool] = None,
    write_partitions: Optional[bool] = None,
) -> Dict[str, Any]:
    """Gộp tất cả các file batch & snapshot từ input_dir thành output_file."""
    base_dir = Path(input_dir)
    out_path = Path(output_file)

    is_project_data_dir = (base_dir.resolve() == (PROJECT_ROOT / "data").resolve()) or str(input_dir) in ["data", "data/"]

    if include_snapshots is None:
        include_snapshots = is_project_data_dir
    if write_partitions is None:
        write_partitions = is_project_data_dir

    logger.info("Bắt đầu quét dữ liệu trong: %s", base_dir.resolve())

    # Khởi tạo crawler helpers
    try:
        from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler
        vnw_crawler = VietnamWorksCrawler()
    except Exception:
        vnw_crawler = None

    try:
        from crawlers.sources.topcv.crawler import TopCVCrawler
        topcv_crawler = TopCVCrawler()
    except Exception:
        topcv_crawler = None

    all_files = discover_input_files(base_dir, include_snapshots=include_snapshots)
    logger.info("Tìm thấy %d file dữ liệu cần nạp vào quy trình gộp.", len(all_files))

    raw_count = 0
    valid_schema_count = 0
    records_by_key: Dict[str, Dict[str, Any]] = {}
    sources_counter: Counter[str] = Counter()
    lang_counter: Counter[str] = Counter()
    salary_extracted_count = 0

    for fpath in all_files:
        items = parse_job_file(fpath)
        for item in items:
            raw_count += 1
            item_dict, is_valid = convert_to_job_record(
                item, file_path=fpath, vnw_crawler=vnw_crawler, topcv_crawler=topcv_crawler
            )
            if not item_dict:
                continue

            if is_valid:
                valid_schema_count += 1

            meta = item_dict.get("_meta", {})
            src = meta.get("source", "unknown")
            jid = meta.get("source_job_id", raw_count)
            dedup_key = meta.get("dedup_key") or f"{src}:{jid}"
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

    # Thống kê sau khử trùng lặp
    for item in combined_list:
        meta = item.get("_meta", {})
        raw = item.get("raw", {})
        src = meta.get("source", "unknown")
        lang = meta.get("language", "vi")
        sources_counter[src] += 1
        lang_counter[lang] += 1
        sal_obj = raw.get("salary") or {}
        has_sal = (
            raw.get("salary_min") is not None
            or raw.get("salary_max") is not None
            or sal_obj.get("salary_min") is not None
            or sal_obj.get("salary_max") is not None
        )
        if has_sal:
            salary_extracted_count += 1

    # Kiểm tra tỷ lệ tuân thủ schema JobRecord trên tập kết quả cuối cùng
    final_schema_valid_count = 0
    for it in combined_list:
        try:
            validate_record(it)
            final_schema_valid_count += 1
        except Exception:
            pass

    schema_compliance_rate = (final_schema_valid_count / unique_count * 100) if unique_count else 0.0

    logger.info("=" * 65)
    logger.info("TỔNG KẾT DỮ LIỆU:")
    logger.info("  - Tổng số bản ghi đọc được : %d", raw_count)
    logger.info("  - Số bản ghi duy nhất     : %d", unique_count)
    logger.info("  - Số trùng lặp loại bỏ     : %d", raw_count - unique_count)
    logger.info("  - Tỷ lệ tuân thủ JobRecord : %d/%d (%.1f%%)",
                final_schema_valid_count, unique_count, schema_compliance_rate)
    logger.info("  - Thống kê theo nguồn:")
    for src, cnt in sources_counter.most_common():
        logger.info("      + %-15s: %d (%.1f%%)", src, cnt, (cnt / unique_count * 100) if unique_count else 0.0)
    logger.info("  - Thống kê ngôn ngữ:")
    for lang, cnt in lang_counter.items():
        logger.info("      + %-15s: %d", lang, cnt)
    logger.info("  - Tin có bóc tách lương    : %d (%.1f%%)",
                salary_extracted_count,
                (salary_extracted_count / unique_count * 100) if unique_count else 0.0)
    logger.info("=" * 65)

    # Ghi ra phân vùng dữ liệu data/<source>/dt=YYYY-MM-DD/batch_001.json
    if write_partitions:
        today_str = datetime.now().strftime("%Y-%m-%d")
        by_source: Dict[str, List[Dict[str, Any]]] = {}
        for it in combined_list:
            s = it.get("_meta", {}).get("source", "unknown")
            by_source.setdefault(s, []).append(it)

        for src, items_for_src in by_source.items():
            src_part_dir = base_dir / src / f"dt={today_str}"
            src_part_dir.mkdir(parents=True, exist_ok=True)
            batch_file = src_part_dir / "batch_001.json"
            tmp_batch = batch_file.with_suffix(".json.tmp")
            with open(tmp_batch, "w", encoding="utf-8") as f:
                json.dump(items_for_src, f, ensure_ascii=False, indent=2)
            tmp_batch.replace(batch_file)
            logger.info("Đã đồng bộ phân vùng: %s (%d records)", batch_file, len(items_for_src))

    # Ghi ra file tổng hợp duy nhất: data/processed/combined_jobs.json
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
        "schema_compliance_count": final_schema_valid_count,
        "schema_compliance_rate": schema_compliance_rate,
        "sources": dict(sources_counter),
        "languages": dict(lang_counter),
        "salary_extracted_count": salary_extracted_count,
        "salary_extracted_rate": (salary_extracted_count / unique_count * 100) if unique_count else 0.0,
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
    parser.add_argument(
        "--no-snapshots",
        action="store_true",
        help="Không tự động nạp snapshots từ crawlers/sources/*/samples/ và data/raw/",
    )
    parser.add_argument(
        "--no-partitions",
        action="store_true",
        help="Không tự động ghi phân vùng data/<source>/dt=YYYY-MM-DD/batch_001.json",
    )
    args = parser.parse_args()

    res = merge_datasets(
        input_dir=args.input_dir,
        output_file=args.output_file,
        include_snapshots=not args.no_snapshots,
        write_partitions=not args.no_partitions,
    )
    print(f"\n✅ Merge hoàn tất! Tổng cộng {res['total_unique']} jobs đã được ghi vào {res.get('output_file')}")
    print(f"📊 Tỷ lệ tuân thủ schema JobRecord: {res['schema_compliance_rate']:.1f}% ({res['schema_compliance_count']}/{res['total_unique']})")
    print(f"🏢 Phân bố theo nguồn: {res['sources']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
