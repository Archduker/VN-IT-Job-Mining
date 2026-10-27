# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.run_gemini_enrichment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Runner điều phối Gemini All-in-One Preprocessing Agent cho VN-IT-Job-Mining.

Cơ chế vận hành:
  1. Nạp tập dữ liệu đầu vào (hỗ trợ cả JSON mảng và JSON Lines).
  2. Tính toán ma trận mốc thị trường (MarketAnchorCalculator) từ các bài có lương.
  3. Tích hợp CheckpointStore (Zero-Loss): bỏ qua các job_id_global đã chạy trước đó.
  4. Hỗ trợ đa luồng (Worker Pool) kết hợp kiểm soát tốc độ (Rate Limiting).
  5. Hỗ trợ cờ `--mock` cho phép kiểm thử offline toàn bộ pipeline mà không cần API key.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from preprocessing.missing_outlier.checkpoint_store import CheckpointStore
from preprocessing.missing_outlier.gemini_all_in_one_agent import GeminiAllInOneAgent
from preprocessing.missing_outlier.market_anchor_calculator import MarketAnchorCalculator
from preprocessing.normalization.target_schema_formatter import TargetSchemaFormatter

logger = logging.getLogger("run_enrichment")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Đường dẫn mặc định
DEFAULT_INPUT_FILE = "data/staging/normalized_jobs.json"
DEFAULT_CHECKPOINT_FILE = "data/staging/gemini_checkpoint.jsonl"
DEFAULT_GOLDEN_MASTER = "data/curated/golden_master.json"
DEFAULT_CURATED_FLAT = "data/curated/curated_flat_golden_jobs.json"


def load_input_records(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Nạp danh sách record từ tệp JSON mảng hoặc JSON Lines."""
    p = Path(file_path)
    if not p.exists():
        # Thử tìm các file thay thế phổ biến trong staging
        fallback_paths = [
            Path("data/staging/normalized_jobs.json"),
            Path("data/staging/validated_clean_jobs.json"),
            Path("data/curated/golden_master.json"),
        ]
        for fb in fallback_paths:
            if fb.exists():
                logger.info("Tệp %s không tồn tại, sử dụng tệp thay thế: %s", p, fb)
                p = fb
                break
        else:
            raise FileNotFoundError(f"Không tìm thấy tệp đầu vào tại: {file_path}")

    logger.info("Đang nạp dữ liệu từ: %s", p)
    content = p.read_text(encoding="utf-8").strip()
    if not content:
        return []

    if content.startswith("["):
        records = json.loads(content)
        if isinstance(records, list):
            return records
        return []

    # Định dạng JSON Lines
    records = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records


def run_enrichment_pipeline(
    input_file: str = DEFAULT_INPUT_FILE,
    checkpoint_file: str = DEFAULT_CHECKPOINT_FILE,
    golden_output: Optional[str] = None,
    flat_output: Optional[str] = None,
    limit: Optional[int] = None,
    mock_mode: bool = False,
    workers: int = 4,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Hàm điều phối toàn bộ quá trình làm giàu dữ liệu."""
    start_time = time.time()
    records = load_input_records(input_file)
    total_records = len(records)
    logger.info("Tổng số bản ghi đầu vào: %d", total_records)

    # 1. Tính toán mốc thị trường trên toàn bộ tập dữ liệu đầu vào
    logger.info("Bắt đầu tính toán mốc thị trường (MarketAnchorCalculator)...")
    anchor_calc = MarketAnchorCalculator()
    anchor_calc.fit(records)

    if limit and limit > 0:
        records = records[:limit]
        logger.info("Áp dụng cờ limit: chỉ xử lý %d bản ghi", len(records))

    # 2. Khởi tạo Checkpoint Store
    ckpt_path = Path(checkpoint_file)
    ckpt_store = CheckpointStore(ckpt_path)
    processed_ids = set() if force else ckpt_store.get_processed_ids()
    logger.info("Số bản ghi đã có trong checkpoint: %d", len(processed_ids))

    # Lọc danh sách bản ghi cần xử lý
    pending_records = [
        r for r in records
        if (r.get("job_id_global") or r.get("id")) not in processed_ids
    ]
    logger.info("Số bản ghi cần xử lý mới: %d", len(pending_records))

    # 3. Khởi tạo Agent
    agent = GeminiAllInOneAgent(
        api_key=api_key,
        model_name=model_name,
        mock_mode=mock_mode,
    )

    # 4. Xử lý bản ghi với Worker Pool
    processed_count = 0
    errors_count = 0

    def _process_single(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        job_id = rec.get("job_id_global") or rec.get("id") or f"id_{id(rec)}"
        platform = rec.get("source_platform") or rec.get("platform") or "unknown"
        sen = rec.get("standardized_seniority") or rec.get("job_seniority") or "middle"

        anchor = anchor_calc.get_anchor(platform, sen)
        try:
            enriched = agent.enrich_record(rec, market_anchor=anchor)
            formatted = TargetSchemaFormatter.format_record(rec, enriched_data=enriched)
            ckpt_store.append(formatted)
            return formatted
        except Exception as exc:
            logger.error("Lỗi khi xử lý record %s: %s", job_id, exc)
            return None

    if pending_records:
        logger.info("Bắt đầu xử lý với %d workers (mock_mode=%s)...", workers, mock_mode)
        if workers > 1 and not mock_mode:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(_process_single, r): r for r in pending_records}
                for idx, fut in enumerate(concurrent.futures.as_completed(futures), 1):
                    res = fut.result()
                    if res:
                        processed_count += 1
                    else:
                        errors_count += 1
                    if idx % 50 == 0 or idx == len(pending_records):
                        logger.info("Tiến độ: [%d/%d] bản ghi hoàn thành", idx, len(pending_records))
        else:
            for idx, r in enumerate(pending_records, 1):
                res = _process_single(r)
                if res:
                    processed_count += 1
                else:
                    errors_count += 1
                if idx % 50 == 0 or idx == len(pending_records):
                    logger.info("Tiến độ: [%d/%d] bản ghi hoàn thành", idx, len(pending_records))

    # 5. Xuất Golden Master nếu được chỉ định
    all_checkpoints = ckpt_store.load_all()
    logger.info("Tổng số bản ghi trong checkpoint sau khi xử lý: %d", len(all_checkpoints))

    if golden_output:
        g_path = Path(golden_output)
        g_path.parent.mkdir(parents=True, exist_ok=True)
        g_path.write_text(json.dumps(all_checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Đã ghi tệp Golden Master (%d records) tại: %s", len(all_checkpoints), g_path)

    if flat_output:
        f_path = Path(flat_output)
        f_path.parent.mkdir(parents=True, exist_ok=True)
        flat_records = [TargetSchemaFormatter.to_flat_target_record(r) for r in all_checkpoints]
        f_path.write_text(json.dumps(flat_records, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Đã ghi tệp Curated Flat (%d records) tại: %s", len(flat_records), f_path)

    duration = time.time() - start_time
    logger.info("Hoàn thành pipeline trong %.2f giây (Mới: %d, Lỗi: %d)", duration, processed_count, errors_count)

    return {
        "total_records": total_records,
        "processed_count": processed_count,
        "errors_count": errors_count,
        "checkpoint_records": len(all_checkpoints),
        "duration_seconds": duration,
    }


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runner điều phối Gemini Preprocessing Agent")
    parser.add_argument("--input", default=DEFAULT_INPUT_FILE, help="Đường dẫn tệp đầu vào")
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT_FILE, help="Đường dẫn tệp checkpoint JSONL")
    parser.add_argument("--golden-output", default=DEFAULT_GOLDEN_MASTER, help="Đường dẫn xuất golden master JSON")
    parser.add_argument("--flat-output", default=DEFAULT_CURATED_FLAT, help="Đường dẫn xuất curated flat JSON")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số bản ghi xử lý")
    parser.add_argument("--mock", action="store_true", help="Chạy chế độ mock offline không cần API key")
    parser.add_argument("--workers", type=int, default=4, help="Số worker song song")
    parser.add_argument("--model", default=None, help="Tên model Gemini")
    parser.add_argument("--force", action="store_true", help="Chạy lại toàn bộ không bỏ qua checkpoint")
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    parsed = parse_args(args)
    res = run_enrichment_pipeline(
        input_file=parsed.input,
        checkpoint_file=parsed.checkpoint,
        golden_output=parsed.golden_output,
        flat_output=parsed.flat_output,
        limit=parsed.limit,
        mock_mode=parsed.mock,
        workers=parsed.workers,
        model_name=parsed.model,
        force=parsed.force,
    )
    return 0 if res["errors_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
