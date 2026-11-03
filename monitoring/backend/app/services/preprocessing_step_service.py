# -*- coding: utf-8 -*-
"""Đọc báo cáo từng bước pre-processing (reports/preprocessing/<bước>/<nguồn>.json).

Chỉ đọc file do scripts/run_preprocessing.py ghi; không tính lại, không ước lượng.
Đặc tả: docs/monitoring/preprocessing_page_spec.md, schema: docs/preprocessing/spec/P0_pipeline_contract.md mục 4.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.config import settings
from app.core.data_paths import load_json_report

STEPS = ("01_clean", "02_integration", "03_transformation", "04_normalization", "05_encoding")
STEP_NAMES = {"01_clean": "Clean", "02_integration": "Integration", "03_transformation": "Transformation",
              "04_normalization": "Normalization", "05_encoding": "Encoding"}


def _root():
    return settings.ROOT_DIR / "reports" / "preprocessing"


def _command(step: str, source: str = "all") -> str:
    return f"python scripts/run_preprocessing.py --step {step[3:]} --source {source} --dry-run"


def _require_step(step: str) -> str:
    if step not in STEPS:  # chặn giá trị lạ trước khi ghép vào đường dẫn
        raise HTTPException(status_code=404, detail=f"Bước '{step}' không tồn tại")
    return step


def _load(step: str, source: str) -> Optional[Dict[str, Any]]:
    return load_json_report(_root() / step / f"{source}.json")


def list_steps() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for step in STEPS:
        r = _load(step, "_all")
        base = {"step": step, "name": STEP_NAMES[step]}
        if r is None:
            out.append({**base, "available": False, "command": _command(step)})
            continue
        prev = next((s for s in reversed(out) if s["available"]), None)
        stale = bool(prev and prev["generated_at"] > (r.get("generated_at") or ""))
        out.append({**base, "available": True, "mode": r.get("mode"), "generated_at": r.get("generated_at"),
                    "input_rows": r["input"]["rows"], "output_rows": r["output"]["rows"], "stale": stale})
    return out


def get_step(step: str) -> Dict[str, Any]:
    step = _require_step(step)
    total = _load(step, "_all")
    if total is None:
        return {"step": step, "available": False, "command": _command(step)}
    return {"step": step, "available": True, "report": total}


def get_step_source(step: str, source: str) -> Dict[str, Any]:
    step = _require_step(step)
    report = _load(step, source)
    if report is None:
        return {"step": step, "source": source, "available": False, "command": _command(step, source)}
    return {"step": step, "source": source, "available": True, "report": report}
