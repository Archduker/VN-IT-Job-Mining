# -*- coding: utf-8 -*-
"""Driver pipeline pre-processing 5 bước: Clean → Integration → Transformation → Normalization → Encoding.

    python scripts/run_preprocessing.py --step clean --source glints --dry-run
    python scripts/run_preprocessing.py --step all --source all

Mỗi bước ghi reports/preprocessing/<bước>/<nguồn>.json (Monitoring đọc). Chỉ ghi trên máy, không đụng R2.
Đặc tả: docs/preprocessing/spec/P0_pipeline_contract.md.
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

MODULES = {"01_clean": "preprocessing.clean.run"}  # các bước sau thêm khi làm P2–P5


def main(argv=None) -> int:
    names = {s[3:]: s for s in STEPS}
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--step", required=True, choices=[*names, "all"])
    parser.add_argument("--source", default="all", choices=[*SOURCES, "all"])
    parser.add_argument("--dry-run", action="store_true", help="chỉ đọc và ghi báo cáo, không ghi dữ liệu")
    parser.add_argument("--use-api", action="store_true", help="cho phép gọi JEV/LLM (có cache)")
    args = parser.parse_args(argv)

    steps = list(STEPS) if args.step == "all" else [names[args.step]]
    sources = list(SOURCES) if args.source == "all" else [args.source]
    for step in steps:  # đúng thứ tự, không đảo
        if step not in MODULES:
            print(f"{step}: chưa làm (xem docs/prompting/), dừng.")
            return 1
        reports = importlib.import_module(MODULES[step]).run(sources, dry_run=args.dry_run, use_api=args.use_api)
        for src, r in reports.items():
            d = r.data
            print(f"{step} {src}: input {d['input']['rows']} → output {d['output']['rows']} ({d['mode']})"
                  f" → reports/preprocessing/{step}/{src}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
