# -*- coding: utf-8 -*-
"""Driver pipeline pre-processing 5 bước: Clean → Dedup (01b) → Integration → Transformation → Normalization → Encoding.

    python scripts/run_preprocessing.py --step clean --source glints --dry-run
    python scripts/run_preprocessing.py --step all --source all

Mỗi bước ghi reports/preprocessing/<bước>/<nguồn>.json (Monitoring đọc). Chỉ ghi trên máy, không đụng R2. Không gọi model nào: mọi phân loại là luật if-else.
Đặc tả: docs/spec/preprocessing/spec/P0_pipeline_contract.md.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from preprocessing.common import SOURCES, STEPS  # noqa: E402

MODULES = {
    "01_clean": "preprocessing.clean.run",
    "01b_deduplication": "preprocessing.deduplication.run",
    "02_integration": "preprocessing.integration.run",
    "03_transformation": "preprocessing.transformation.run",
    "04_normalization": "preprocessing.normalization.run",
    "05_encoding": "preprocessing.encoding.run",
}


def main(argv=None) -> int:
    step_map = {s.split("_", 1)[1]: s for s in STEPS}
    step_map.update({s: s for s in STEPS})
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--step", required=True, choices=[*step_map.keys(), "all"])
    parser.add_argument("--source", default="all", choices=[*SOURCES, "all"])
    parser.add_argument("--dry-run", action="store_true", help="chỉ đọc và ghi báo cáo, không ghi dữ liệu")
    args = parser.parse_args(argv)

    steps = list(STEPS) if args.step == "all" else [step_map[args.step]]
    sources = list(SOURCES) if args.source == "all" else [args.source]
    for step in steps:  # đúng thứ tự, không đảo
        if step not in MODULES:
            print(f"{step}: chưa làm (xem docs/prompting/), dừng.")
            return 1
        reports = importlib.import_module(MODULES[step]).run(sources, dry_run=args.dry_run)
        for src, r in reports.items():
            d = r.data
            print(f"{step} {src}: input {d['input']['rows']} → output {d['output']['rows']} ({d['mode']})"
                  f" → reports/preprocessing/{step}/{src}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
