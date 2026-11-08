# -*- coding: utf-8 -*-
"""Đọc raw envelope của một nguồn: snapshot từng tin và tin trong file batch cũ."""

from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

SKIP_DIRS = {"_index", "_quality", "_listing", "_listing_failures"}

Item = Tuple[str, Dict[str, Any]]  # (đường dẫn tương đối trong raw/, envelope)


def read_raw(raw_dir: Path) -> Tuple[List[Item], List[Item], Dict[str, int]]:
    """Trả (snapshot, tin trong file batch, bộ đếm). Không lọc trùng."""
    snapshots: List[Item] = []
    batch: List[Item] = []
    counts: collections.Counter = collections.Counter()
    for path in sorted(raw_dir.rglob("*.json")) if raw_dir.exists() else []:
        rel = path.relative_to(raw_dir)
        if SKIP_DIRS & set(rel.parts):
            continue
        try:
            env = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            counts["json_lỗi"] += 1
            continue
        if isinstance(env, list):
            counts["file_batch"] += 1
            counts["tin_trong_batch"] += len(env)
            batch.extend((rel.as_posix(), e) for e in env if isinstance(e, dict) and isinstance(e.get("metadata"), dict))
            continue
        if not isinstance(env, dict) or not isinstance(env.get("metadata"), dict):
            counts["không_phải_envelope"] += 1
            continue
        counts["snapshot"] += 1
        counts["snapshot_v_lớn_hơn_1"] += int(env["metadata"].get("version") or 1) > 1
        snapshots.append((rel.as_posix(), env))
    return snapshots, batch, dict(counts)


def snapshot_order(env: Dict[str, Any]) -> Tuple[str, int]:
    meta = env["metadata"]
    return str(meta.get("scraped_at") or ""), int(meta.get("version") or 1)


def latest_envelopes(raw_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Snapshot mới nhất theo job_id (scraped_at rồi version). Tin trong file batch chỉ được đếm."""
    snapshots, _, counts = read_raw(raw_dir)
    best: Dict[str, Dict[str, Any]] = {}
    for _, env in snapshots:
        job_id = str(env["metadata"].get("job_id") or "")
        if job_id and (job_id not in best or snapshot_order(env) > snapshot_order(best[job_id])):
            best[job_id] = env
    return list(best.values()), counts
