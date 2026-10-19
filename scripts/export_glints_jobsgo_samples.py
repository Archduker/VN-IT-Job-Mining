# -*- coding: utf-8 -*-
"""Export three actual MinIO detail snapshots per source into samples/*.html + *.json.

Run this after both sources have at least three successful detail snapshots:
    python scripts/export_glints_jobsgo_samples.py

The script refuses to overwrite sample fixtures for a source unless it can export three
actual snapshots for that source. This prevents synthetic fixtures from being mistaken
for real crawl evidence in the final submission.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from crawlers.common.minio_raw_pipeline import MinioRawStore

SOURCES = ("glints", "jobsgo")
SNAPSHOT_RE = re.compile(r"^raw/(?P<source>glints|jobsgo)/\d{4}-\d{2}-\d{2}/.+_v(?P<version>\d+)\.json$")


def collect_latest(store: MinioRawStore, source: str) -> List[Tuple[str, Dict[str, Any]]]:
    latest: Dict[str, Tuple[int, str, Dict[str, Any]]] = {}
    for key in store.list_keys(f"raw/{source}/"):
        match = SNAPSHOT_RE.match(key)
        if not match or match.group("source") != source:
            continue
        try:
            obj = store.get_json(key)
        except Exception as exc:
            print(f"[WARN] Không đọc được {key}: {exc}")
            continue
        if not isinstance(obj, dict):
            continue
        raw = obj.get("raw")
        meta = obj.get("_meta")
        if not isinstance(raw, dict) or not isinstance(meta, dict) or not isinstance(raw.get("html"), str):
            continue
        job_id = str(meta.get("source_job_id") or key)
        version = int(meta.get("version") or match.group("version"))
        current = latest.get(job_id)
        if current is None or version > current[0]:
            latest[job_id] = (version, key, obj)
    return [(item[1], item[2]) for item in sorted(latest.values(), key=lambda x: (x[0], x[1]), reverse=True)]


def export_source(source: str, selected: List[Tuple[str, Dict[str, Any]]], count: int = 3) -> None:
    samples_dir = Path("crawlers") / "sources" / source / "samples"
    if len(selected) < count:
        raise RuntimeError(f"Cần ít nhất {count} snapshot detail thật để xuất sample của {source}.")

    samples_dir.mkdir(parents=True, exist_ok=True)
    # Prepare all outputs first; only write after enough actual snapshots were found.
    prepared = []
    for index, (key, snapshot) in enumerate(selected[:count], start=1):
        html = snapshot["raw"]["html"]
        json_text = json.dumps(snapshot, ensure_ascii=False, indent=2, default=str) + "\n"
        prepared.append((samples_dir / f"sample_{index}.html", html))
        prepared.append((samples_dir / f"sample_{index}.json", json_text))
        print(f"[{source}] sample_{index}: {key} (version={snapshot.get('_meta', {}).get('version')})")

    for path, content in prepared:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(content, encoding="utf-8", newline="\n")
        temp.replace(path)
    print(f"[{source}] Đã xuất {count} cặp HTML/JSON thật vào {samples_dir}")


def main() -> int:
    store = MinioRawStore()
    selected_by_source: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    failures = []
    # Preflight both sources before overwriting any fixture, avoiding mixed synthetic/real samples.
    for source in SOURCES:
        try:
            selected = collect_latest(store, source)
            if len(selected) < 3:
                raise RuntimeError(
                    f"Nguồn {source} hiện có {len(selected)} snapshot detail hợp lệ; cần ít nhất 3. "
                    "Chạy Phase 1 và Phase 2 bổ sung trước khi xuất sample thật."
                )
            selected_by_source[source] = selected[:3]
        except Exception as exc:
            failures.append((source, str(exc)))
    if failures:
        print("Không ghi đè sample nào vì chưa đủ dữ liệu thật cho cả hai nguồn:")
        for source, reason in failures:
            print(f"- {source}: {reason}")
        return 1

    for source in SOURCES:
        export_source(source, selected_by_source[source], count=3)
    print("Đã xuất đủ mẫu thực tế cho Glints và JobsGO.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
