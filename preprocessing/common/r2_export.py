# -*- coding: utf-8 -*-
"""Bố cục R2 cho output pre-processing (silver/gold), dùng chung cho script đẩy và Monitoring.

Tầng staging/ bắt buộc có tên nguồn ở cấp 2 (canonicalize_lakehouse_key), nên bảng đã gộp
được tách lại theo cột source_platform khi đẩy lên:
  silver:     staging/<nguồn>/preprocessing/<bước>.jsonl|parquet   (bước 01–04)
  pipeline:   pipeline/<bước>/<file>   bảng gộp 8 nguồn của Pre-processing (02–04, silver) và Processing (07, 08, 10, 12_e5)
  mining:     curated/mining/<file>    kết quả Mining M1–M6 (mining/artifacts/)
Key cũ không còn đúng với dữ liệu hiện tại nằm ở OBSOLETE_KEYS (script đẩy chỉ xóa khi có --push --delete-obsolete).
Metadata mỗi object ghi generated_at của báo cáo bước và số dòng, để so máy với R2 theo từng key.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from collection.common.r2_storage import to_r2_key
from preprocessing.common import REPO_ROOT, SOURCES, STEPS

DATA = REPO_ROOT / "data" / "preprocessing"
REPORTS = REPO_ROOT / "reports" / "preprocessing"
SILVER_STEPS = ("01_clean", "02_integration", "03_transformation", "04_normalization")  # 01b chưa đẩy R2


def silver_key(step: str, source: str) -> str:
    ext = "jsonl" if step == "01_clean" else "parquet"
    return to_r2_key(f"staging/{source}/preprocessing/{step}.{ext}")


PIPELINE_STEPS = (*STEPS, "07_sections", "08_skills", "09_tokens", "10_features", "12_e5", "rejected", "translation")
PROCESSING_FILES = {
    "07_sections": ("all.parquet",),
    "08_skills": ("job_skills.parquet",),
    "09_tokens": ("all.parquet",),
    "10_features": ("features.parquet", "encoding_dictionary.json"),
    "12_e5": ("job_emb.npz", "bullet_emb.npy", "bullet_index.parquet", "meta.json"),  # bỏ cache/ (tạm)
}
PREPROCESSING_TABLES = {
    "02_integration": ("all.parquet",),
    "03_transformation": ("all.parquet",),
    "04_normalization": ("all.parquet", "silver.parquet", "quarantine.parquet"),
}
MINING_DIR = REPO_ROOT / "mining" / "artifacts"
MINING_PREFIX = "curated/mining"

# Key trên R2 không còn đúng với dữ liệu hiện tại: bước 05_encoding đã bỏ (thay bằng 10_features),
# bộ silver_* là đầu ra pipeline cũ run_staging_integration_pipeline.py (PRE-39) và sai bố cục staging/<nguồn>/.
OBSOLETE_KEYS = (
    "curated/preprocessing/features.parquet",
    "curated/preprocessing/encoding_dictionary.json",
    "staging/silver_flat_jobs.json",
    "staging/silver_master_dataset.json",
    "staging/silver_dataset_health_card.json",
)

_CONTENT_TYPES = {
    ".parquet": "application/vnd.apache.parquet",
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".csv": "text/csv",
    ".npz": "application/octet-stream",
    ".npy": "application/octet-stream",
}


def _content_type(name: str) -> str:
    return _CONTENT_TYPES.get(Path(name).suffix, "application/octet-stream")


def _rows(path: Path) -> Optional[int]:
    if path.suffix != ".parquet":
        return None
    import pyarrow.parquet as pq

    return pq.ParquetFile(path).metadata.num_rows


def pipeline_key(step: str, name: str) -> str:
    """Key bảng gộp 8 nguồn: pipeline/<bước>/<tên file> (PH0)."""
    if step not in PIPELINE_STEPS:
        raise ValueError(f"bước pipeline không hợp lệ: {step!r}; hợp lệ: {PIPELINE_STEPS}")
    return to_r2_key(f"pipeline/{step}/{name}")


GOLD_KEYS = {
    "features.parquet": to_r2_key("curated/preprocessing/features.parquet"),
    "skill_cooccurrence.parquet": to_r2_key("curated/preprocessing/skill_cooccurrence.parquet"),
    "encoding_dictionary.json": to_r2_key("curated/preprocessing/encoding_dictionary.json"),
}


def _generated_at(step: str) -> Optional[str]:
    path = REPORTS / step / "_all.json"
    if step in PROCESSING_FILES and (REPO_ROOT / "reports" / "processing" / step / "_all.json").exists():
        path = REPO_ROOT / "reports" / "processing" / step / "_all.json"
    return json.loads(path.read_text(encoding="utf-8")).get("generated_at") if path.exists() else None


def _mining_generated_at() -> Optional[str]:
    path = MINING_DIR / "mining_metrics.json"
    return json.loads(path.read_text(encoding="utf-8")).get("generated_at") if path.exists() else None


def mining_key(name: str) -> str:
    return to_r2_key(f"{MINING_PREFIX}/{name}")


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
    # pipeline/<bước>/<tên file>: bảng gộp 8 nguồn (PH9); chỉ liệt kê file có trên máy
    tables = dict(PREPROCESSING_TABLES)
    tables.update(PROCESSING_FILES)
    for step, names in tables.items():
        for name in names:
            p = (DATA.parent / "processing" if step in PROCESSING_FILES else DATA) / step / name
            if p.exists():
                out.append({"step": step, "source": None, "key": pipeline_key(step, name),
                            "rows": _rows(p), "generated_at": _generated_at(step),
                            "content_type": _content_type(name),
                            "build": (lambda p=p: p.read_bytes()) if build else None})
    # curated/mining/<file>: kết quả Mining (một lần chạy, cùng generated_at của mining_metrics.json)
    if MINING_DIR.exists():
        gen_m = _mining_generated_at()
        for p in sorted(MINING_DIR.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                out.append({"step": "mining", "source": None, "key": mining_key(p.name), "rows": _rows(p),
                            "generated_at": gen_m, "content_type": _content_type(p.name),
                            "build": (lambda p=p: p.read_bytes()) if build else None})
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
