# -*- coding: utf-8 -*-
"""Báo cáo bước theo schema chung (docs/spec/preprocessing/spec/P0_pipeline_contract.md mục 4).

Monitoring chỉ đọc các file này, nên mọi số hiện trên trang Pre-processing phải đi qua đây.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from preprocessing.common import REPO_ROOT

REPORTS_ROOT = REPO_ROOT / "reports" / "preprocessing"
MAX_EXAMPLES = 3


class StepReportError(RuntimeError):
    """Báo cáo sai luật bảo toàn: không ghi output."""


def _code_version() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _rel(path: Optional[Path | str]) -> Optional[str]:
    if path is None:
        return None
    path = Path(path)
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


class StepReport:
    def __init__(self, step: str, source: str, dry_run: bool):
        self.data: Dict[str, Any] = {
            "step": step,
            "source": source,
            "mode": "dry_run" if dry_run else "applied",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "code_version": _code_version(),
            "input": {"path": None, "rows": 0},
            "output": {"path": None, "rows": 0},
            "dropped": [],
            "rules": [],
            "fields": [],
            "checks": {"rows_conserved": None, "notes": []},
            "api": {"used": False, "reason": "pipeline không dùng model (luật if-else)"},
            "extra": {},
        }

    def set_io(self, input_path, input_rows: int, output_path, output_rows: int) -> None:
        self.data["input"] = {"path": _rel(input_path), "rows": int(input_rows)}
        self.data["output"] = {"path": _rel(output_path), "rows": int(output_rows)}

    def rule(self, rule_id: str, name: str, action: str, rows_affected: int,
             examples: Iterable[Dict[str, Any]] = (), reason: Optional[str] = None) -> None:
        """action: drop | flag | modify. Luật drop được cộng vào dropped để kiểm bảo toàn."""
        ex = sorted(examples, key=lambda e: str(e.get("job_id", "")))[:MAX_EXAMPLES]
        self.data["rules"].append({"id": rule_id, "name": name, "action": action,
                                   "rows_affected": int(rows_affected), "examples": ex})
        if action == "drop":
            self.data["dropped"].append({"rule": rule_id, "reason": reason or name, "rows": int(rows_affected)})

    def note(self, text: str) -> None:
        self.data["checks"]["notes"].append(text)

    def check_conserved(self) -> None:
        d = self.data
        dropped = sum(x["rows"] for x in d["dropped"])
        ok = d["input"]["rows"] == d["output"]["rows"] + dropped
        d["checks"]["rows_conserved"] = ok
        if not ok:
            raise StepReportError(f"{d['step']}/{d['source']}: input {d['input']['rows']} != "
                                  f"output {d['output']['rows']} + bỏ {dropped}")

    def write(self, root: Optional[Path] = None) -> Path:
        self.check_conserved()
        root = root or REPORTS_ROOT
        path = root / self.data["step"] / f"{self.data['source']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def merge_reports(step: str, reports: List[StepReport], dry_run: bool) -> StepReport:
    """Báo cáo `_all`: cộng số theo luật, giữ ví dụ đầu tiên của các nguồn."""
    total = StepReport(step, "_all", dry_run)
    total.set_io(None, sum(r.data["input"]["rows"] for r in reports),
                 None, sum(r.data["output"]["rows"] for r in reports))
    rules: Dict[str, Dict[str, Any]] = {}
    for r in reports:
        for rule in r.data["rules"]:
            agg = rules.setdefault(rule["id"], {**rule, "rows_affected": 0, "examples": [], "by_source": {}})
            agg["rows_affected"] += rule["rows_affected"]
            agg["by_source"][r.data["source"]] = rule["rows_affected"]
            agg["examples"] += rule["examples"]
    for rule in rules.values():
        reason = next((d["reason"] for r in reports for d in r.data["dropped"] if d["rule"] == rule["id"]), None)
        total.rule(rule["id"], rule["name"], rule["action"], rule["rows_affected"], rule["examples"], reason)
        total.data["rules"][-1]["by_source"] = rule["by_source"]
    weights = {r.data["source"]: r.data["output"]["rows"] for r in reports}
    n = sum(weights.values())
    fields: Dict[str, Dict[str, float]] = {}
    for r in reports:  # độ phủ của bảng gộp = trung bình theo số dòng của từng nguồn
        for f in r.data.get("fields") or []:
            agg = fields.setdefault(f["field"], {"field": f["field"], "fill_pct_in": 0.0, "fill_pct_out": 0.0})
            for k in ("fill_pct_in", "fill_pct_out"):
                agg[k] += (f.get(k) or 0) * weights[r.data["source"]] / n if n else 0
    total.data["fields"] = [{**f, "fill_pct_in": round(f["fill_pct_in"], 1), "fill_pct_out": round(f["fill_pct_out"], 1)}
                            for f in fields.values()]
    total.data["extra"]["sources"] = {r.data["source"]: {"input": r.data["input"]["rows"],
                                                         "output": r.data["output"]["rows"]} for r in reports}
    return total
