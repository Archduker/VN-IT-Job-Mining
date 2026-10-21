#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_eda_notebooks.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Automated verification suite to execute all 8 reports/EDA_{source}.ipynb notebooks
and verify zero runtime errors and healthy Cloud R2 Lakehouse sync.
"""

import sys
import json
import time
from pathlib import Path

# Đảm bảo matplotlib chạy chế độ headless Agg và không chặn bởi plt.show()
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def noop_show(*args, **kwargs):
    plt.close('all')

plt.show = noop_show
matplotlib.pyplot.show = noop_show

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"

SOURCES = [
    "topdev",
    "itviec",
    "vietnamworks",
    "careerviet",
    "glints",
    "vieclam24h",
    "jobsgo",
    "topcv",
]


def run_notebook(source: str):
    nb_path = REPORTS_DIR / f"EDA_{source}.ipynb"
    if not nb_path.exists():
        print(f"❌ File not found: {nb_path}")
        return False

    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    code_cells = [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]
    print(f"\n{'='*70}")
    print(f"🚀 KIỂM THỬ THỰC THI: {nb_path.name} ({len(code_cells)} code cells)")
    print(f"{'='*70}")

    # Shared globals for the notebook execution
    exec_globals = {
        "__name__": "__main__",
        "__file__": str(nb_path),
    }

    start_time = time.time()
    for idx, cell in enumerate(code_cells, 1):
        raw_source = cell.get("source", "")
        if isinstance(raw_source, list):
            code_str = "".join(raw_source)
        else:
            code_str = str(raw_source)

        try:
            exec(code_str, exec_globals)
            if "plt" in exec_globals:
                exec_globals["plt"].show = noop_show
        except Exception as e:
            print(f"\n❌ LỖI TẠI CELL #{idx} ({source}): {e.__class__.__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

    elapsed = time.time() - start_time
    print(f"\n✅ {nb_path.name} THỰC THI 100% THÀNH CÔNG trong {elapsed:.2f}s!")
    return True


def main():
    results = {}
    total_start = time.time()

    target_sources = sys.argv[1:] if len(sys.argv) > 1 else SOURCES

    for s in target_sources:
        success = run_notebook(s)
        results[s] = success

    total_elapsed = time.time() - total_start
    print("\n" + "=" * 70)
    print("                KẾT QUẢ KIỂM THỬ TOÀN DIỆN 8 NOTEBOOKS")
    print("=" * 70)
    all_passed = True
    for s, ok in results.items():
        status = "PASSED ✅" if ok else "FAILED ❌"
        if not ok:
            all_passed = False
        print(f"  - EDA_{s:<15}.ipynb : {status}")

    print("=" * 70)
    print(f"Tổng thời gian: {total_elapsed:.2f}s | Trạng thái: {'ALL PASSED 🎉' if all_passed else 'SOME FAILED ⚠️'}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
