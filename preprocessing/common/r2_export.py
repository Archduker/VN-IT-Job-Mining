# -*- coding: utf-8 -*-
"""Bố cục R2 cho output pre-processing (silver/gold), dùng chung cho script đẩy và Monitoring.

Tầng staging/ bắt buộc có tên nguồn ở cấp 2 (canonicalize_lakehouse_key), nên bảng đã gộp
được tách lại theo cột source_platform khi đẩy lên:
  silver: staging/<nguồn>/preprocessing/<bước>.jsonl|parquet   (bước 01–04)
  gold:   curated/preprocessing/features.parquet, curated/preprocessing/encoding_dictionary.json
Metadata mỗi object ghi generated_at của báo cáo bước và số dòng, để so máy với R2 theo từng key.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from preprocessing.common import REPO_ROOT, SOURCES, STEPS

DATA = REPO_ROOT / "data" / "preprocessing"
REPORTS = REPO_ROOT / "reports" / "preprocessing"
SILVER_STEPS = STEPS[:4]


def silver_key(step: str, source: str) -> str:
    ext = "jsonl" if step == "01_clean" else "parquet"
    return f"staging/{source}/preprocessing/{step}.{ext}"


GOLD_KEYS = {
    "features.parquet": "curated/preprocessing/features.parquet",
    "skill_cooccurrence.parquet": "curated/preprocessing/skill_cooccurrence.parquet",
    "encoding_dictionary.json": "curated/preprocessing/encoding_dictionary.json",
}


def _generated_at(step: str) -> Optional[str]:
    path = REPORTS / step / "_all.json"
    return json.loads(path.read_text(encoding="utf-8")).get("generated_at") if path.exists() else None


def _parquet_part(path: Path, source: str) -> Callable[[], bytes]:
    def build() -> bytes:
        import pandas as pd

        df = pd.read_parquet(path)
        buf = io.BytesIO()
        df[df["source_platform"] == source].to_parquet(buf, engine="pyarrow", index=False)
        return buf.getvalue()
    return build


def _rows_by_source(path: Path) -> Dict[str, int]:
    import pyarrow.parquet as pq

    col = pq.read_table(path, columns=["source_platform"]).column(0).to_pylist()
    return {s: col.count(s) for s in set(col)}


def plan_objects(build: bool = True) -> List[Dict[str, Any]]:
    """Danh sách object cần có trên R2 theo dữ liệu trên máy. build=False: chỉ key/rows/generated_at (không đọc nội dung)."""
    out: List[Dict[str, Any]] = []
    for step in SILVER_STEPS:
        gen = _generated_at(step)
        if step == "01_clean":
            for src in SOURCES:
                p = DATA / step / f"{src}.jsonl"
                if p.exists():
                    rows = sum(1 for line in p.open(encoding="utf-8") if line.strip())
                    out.append({"step": step, "source": src, "key": silver_key(step, src), "rows": rows,
                                "generated_at": gen, "content_type": "application/x-ndjson",
                                "build": (lambda p=p: p.read_bytes()) if build else None})
            continue
        p = DATA / step / "all.parquet"
        if not p.exists():
            continue
        for src, rows in sorted(_rows_by_source(p).items()):
            out.append({"step": step, "source": src, "key": silver_key(step, src), "rows": rows,
                        "generated_at": gen, "content_type": "application/vnd.apache.parquet",
                        "build": _parquet_part(p, src) if build else None})
    gen = _generated_at("05_encoding")
    for name, key in GOLD_KEYS.items():
        p = DATA / "05_encoding" / name
        if p.exists():
            rows = None
            if name.endswith(".parquet"):
                import pyarrow.parquet as pq
                rows = pq.ParquetFile(p).metadata.num_rows
            out.append({"step": "05_encoding", "source": None, "key": key, "rows": rows, "generated_at": gen,
                        "content_type": "application/vnd.apache.parquet" if name.endswith(".parquet") else "application/json",
                        "build": (lambda p=p: p.read_bytes()) if build else None})
    return out


def object_metadata(obj: Dict[str, Any]) -> Dict[str, str]:
    return {"step": obj["step"], "generated-at": obj["generated_at"] or "", "rows": str(obj["rows"] if obj["rows"] is not None else "")}


def compare(local: Dict[str, Any], remote_meta: Optional[Dict[str, str]]) -> str:
    """'khop' | 'lech' | 'chua_day' theo generated_at và số dòng ghi trong metadata."""
    if remote_meta is None:
        return "chua_day"
    same = remote_meta.get("generated-at") == (local["generated_at"] or "") and remote_meta.get("rows") == str(local["rows"] if local["rows"] is not None else "")
    return "khop" if same else "lech"
