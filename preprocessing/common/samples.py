# -*- coding: utf-8 -*-
"""Khối `samples` của báo cáo bước (PH9): mẫu TRƯỚC/SAU cố định seed 42, dữ liệu thật, ưu tiên dòng bị bước đổi."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd

SEED = 42
PER_SOURCE = 3
MAX_CHARS = 200


def _val(v: Any) -> Any:
    if v is None:
        return None
    if hasattr(v, "tolist"):  # numpy
        v = v.tolist()
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, (list, tuple)):
        return [_val(x) for x in list(v)[:20]]
    if isinstance(v, dict):
        return {str(k): _val(x) for k, x in list(v.items())[:20]}
    if isinstance(v, str):
        return v if len(v) <= MAX_CHARS else v[:MAX_CHARS] + "…"
    return v if isinstance(v, (int, float, bool)) else str(v)[:MAX_CHARS]


def _pick(cands: List[dict], k: int, rng: random.Random) -> List[dict]:
    """Ưu tiên dòng đã đổi, rải đều giữa các trường; kết quả tất định theo seed."""
    cands = sorted(cands, key=lambda c: (c["job_id"], c["field"]))
    rng.shuffle(cands)
    chosen: List[dict] = []
    for pool in ([c for c in cands if c["changed"]], [c for c in cands if not c["changed"]]):
        while pool and len(chosen) < k:
            count = {}
            for c in chosen:
                count[c["field"]] = count.get(c["field"], 0) + 1
            used = {c["job_id"] for c in chosen}
            pool.sort(key=lambda c: (c["job_id"] in used, count.get(c["field"], 0)))  # sort ổn định giữ thứ tự xáo
            chosen.append(pool.pop(0))
    return chosen


def pair_samples(before: pd.DataFrame, after: pd.DataFrame, pairs: Sequence[Tuple[str, str, str]],
                 key: str = "job_id_global", src: str = "source_platform", per_source: int = PER_SOURCE
                 ) -> Dict[str, List[dict]]:
    """pairs = (tên trường, cột TRƯỚC, cột SAU). Trả {nguồn: [mẫu]}; nguồn không có dòng chung thì không có khóa."""
    b = before[[key, src, *{p[1] for p in pairs}]].rename(columns=lambda c: f"__b_{c}" if c not in (key, src) else c)
    a = after[[key, *{p[2] for p in pairs}]].rename(columns=lambda c: f"__a_{c}" if c != key else c)
    m = b.merge(a, on=key, how="inner")
    out: Dict[str, List[dict]] = {}
    for s, g in m.groupby(src, sort=True):
        cands = []
        for rec in g.to_dict("records"):
            for field, bc, ac in pairs:
                bv, av = _val(rec[f"__b_{bc}"]), _val(rec[f"__a_{ac}"])
                cands.append({"job_id": rec[key], "source": s, "field": field, "before": bv, "after": av,
                              "changed": bv != av})
        out[s] = _pick(cands, per_source, random.Random(f"{SEED}:{s}"))
    return out


def dropped_samples(path: Path, source: str, *, field: str, before_key: str, after_fmt: str,
                    per_source: int = PER_SOURCE) -> List[dict]:
    """Mẫu từ file rejected/ (dòng bị bỏ): after = nhãn luật. Không đọc raw_line."""
    if not path.is_file():
        return []
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows.sort(key=lambda r: str(r.get("job_id")))
    random.Random(f"{SEED}:{source}").shuffle(rows)
    return [{"job_id": r.get("job_id"), "source": source, "field": field, "before": _val(r.get(before_key)),
             "after": after_fmt.format(**{k: r.get(k) for k in ("rule", "reason", "drop_rule", "duplicate_of")}),
             "changed": True} for r in rows[:per_source]]


def inject_samples(report_root: Path, step: str, by_source: Dict[str, List[dict]], reason: str | None = None,
                   sources: Iterable[str] | None = None) -> None:
    """Ghi `samples` vào <report_root>/<step>/<nguồn>.json và _all.json (đã có). Rỗng thì ghi `samples_reason`."""
    d = report_root / step
    total: List[dict] = []
    for s in (sources if sources is not None else by_source):
        total += by_source.get(s, [])
    for name, rows in [(s, by_source.get(s, [])) for s in (sources if sources is not None else by_source)] + [("_all", total)]:
        p = d / f"{name}.json"
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        data["samples"] = rows
        if not rows:
            data["samples_reason"] = reason or "NO_ROWS_CHANGED"
        else:
            data.pop("samples_reason", None)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
