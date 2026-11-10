# -*- coding: utf-8 -*-
"""Đọc báo cáo từng bước pre-processing (reports/preprocessing/<bước>/<nguồn>.json).

Chỉ đọc file do scripts/run_preprocessing.py ghi; không tính lại, không ước lượng.
Đặc tả: docs/spec/monitoring/preprocessing_page_spec.md, schema: docs/spec/preprocessing/spec/P0_pipeline_contract.md mục 4.
"""

from __future__ import annotations

import io
import json
import math
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.config import settings
from app.core.data_paths import load_json_report
from app.core.r2_client import r2_client
from preprocessing.common import SOURCES, r2_export

STEPS = ("01_clean", "01b_deduplication", "02_integration", "03_transformation", "04_normalization", "05_encoding")
PROCESSING_STEPS = ("07_sections", "08_skills", "09_tokens")  # báo cáo ở reports/processing/<bước>/ (PH9 D4)
PER_SOURCE_STEPS = ("01_clean", "01b_deduplication")  # jsonl theo nguồn, các bước sau gộp all.parquet
STEP_NAMES = {"07_sections": "Sections", "08_skills": "Skills", "09_tokens": "Tokens", "01_clean": "Clean", "01b_deduplication": "Deduplication", "02_integration": "Integration", "03_transformation": "Transformation",
              "04_normalization": "Normalization", "05_encoding": "Encoding"}


def _root(step: str = ""):
    return settings.ROOT_DIR / "reports" / ("processing" if step in PROCESSING_STEPS else "preprocessing")


def _command(step: str, source: str = "all") -> str:
    if step in PROCESSING_STEPS:
        return ""  # driver bước 07-09 chưa chốt (PH9 D1), không bịa lệnh
    return f"python scripts/run_preprocessing.py --step {step.split("_", 1)[1]} --source {source} --dry-run"


def _require_step(step: str) -> str:
    if step not in STEPS + PROCESSING_STEPS:  # chặn giá trị lạ trước khi ghép vào đường dẫn
        raise HTTPException(status_code=404, detail=f"Bước '{step}' không tồn tại")
    return step


def _load(step: str, source: str) -> Optional[Dict[str, Any]]:
    return load_json_report(_root(step) / step / f"{source}.json")


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


def list_processing_steps() -> List[Dict[str, Any]]:
    """Bước 07-09: chưa có reports/processing/ thì Empty State (reason NO_DATA), không điền 0."""
    out: List[Dict[str, Any]] = []
    for step in PROCESSING_STEPS:
        r = _load(step, "_all")
        base = {"step": step, "name": STEP_NAMES[step]}
        if r is None:
            out.append({**base, "available": False, "reason": "NO_DATA", "command": ""})
        else:
            out.append({**base, "available": True, "mode": r.get("mode"), "generated_at": r.get("generated_at"),
                        "input_rows": r["input"]["rows"], "output_rows": r["output"]["rows"], "stale": False})
    return out


def get_step(step: str) -> Dict[str, Any]:
    step = _require_step(step)
    total = _load(step, "_all")
    if total is None:
        return {"step": step, "available": False, "reason": "NO_DATA", "command": _command(step)}
    return {"step": step, "available": True, "report": total}


def get_step_source(step: str, source: str) -> Dict[str, Any]:
    step = _require_step(step)
    report = _load(step, source)
    if report is None:
        return {"step": step, "source": source, "available": False, "reason": "NO_DATA", "command": _command(step, source)}
    return {"step": step, "source": source, "available": True, "report": report}


# ---- Bất thường bước 04 và tra tin theo job_id ------------------------------------------------

ANOMALY_MAX = 200


def get_anomalies(kind: Optional[str], source: Optional[str], offset: int, limit: int) -> Dict[str, Any]:
    """Danh sách trong reports/preprocessing/04_normalization/anomalies.json, lọc theo loại/nguồn; chưa có file thì NO_DATA."""
    path = _root("04_normalization") / "04_normalization" / "anomalies.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    items = data.get("anomalies", data.get("items")) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return {"available": False, "reason": "NO_DATA", "by_kind": {}, "total": 0, "items": []}
    items = [i for i in items if isinstance(i, dict)]
    by_kind: Dict[str, int] = {}
    for i in items:
        if source is None or i.get("source") == source:
            by_kind[str(i.get("kind"))] = by_kind.get(str(i.get("kind")), 0) + 1
    sel = [i for i in items if (kind is None or i.get("kind") == kind) and (source is None or i.get("source") == source)]
    limit = max(1, min(limit, ANOMALY_MAX))
    return {"available": True, "reason": None, "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
            "total": len(sel), "offset": offset, "limit": limit, "items": sel[max(0, offset): max(0, offset) + limit]}


# Sau 04 mới có cột chuẩn hóa; bước trước vẫn giữ JD và giá trị gốc. Bước cuối có tin thì dùng bước đó.
_LOOKUP_ORDER = ("04_normalization", "03_transformation", "02_integration")


def find_job(source: str, job_id: str, job_id_global: Optional[str] = None) -> Dict[str, Any]:
    """Tìm tin theo job_id (mã nguồn) hoặc job_id_global trong parquet trên máy, chỉ đọc, không gọi R2."""
    import pandas as pd

    for step in _LOOKUP_ORDER:
        p = r2_export.DATA / step / "all.parquet"
        if not p.exists():
            continue
        cached = _local_frames.get(p)
        if not cached or cached[0] != p.stat().st_mtime:
            cached = _local_frames[p] = (p.stat().st_mtime, pd.read_parquet(p))
        df = cached[1]
        hit = pd.Series(False, index=df.index)
        if job_id_global and "job_id_global" in df.columns:
            hit = df["job_id_global"].astype(str) == job_id_global
        if not hit.any() and "source_job_id" in df.columns:
            hit = (df["source_job_id"].astype(str) == str(job_id)) & (df["source_platform"] == source)
        if hit.any():
            row = _safe(df[hit].iloc[0].to_dict())
            return {"available": True, "step": step, "source": source, "job_id": str(job_id), "row": row}
    return {"available": False, "reason": "NO_DATA", "source": source, "job_id": str(job_id), "step": None, "row": None}


# ---- Lưu trữ (máy ↔ R2) và bảng dòng silver -------------------------------------------------

_STORAGE_TTL = 60.0
_storage_cache: Dict[str, Any] = {"at": 0.0, "data": None}
_r2_frames: Dict[str, Any] = {}  # key -> (etag, rows) để không tải lại object không đổi
_local_frames: Dict[Any, Any] = {}  # path -> (mtime, DataFrame)
MAX_ROWS = 200


def _head(s3, key: str) -> Optional[Dict[str, Any]]:
    from botocore.exceptions import ClientError

    try:
        h = s3.head_object(Bucket=r2_client.bucket_name, Key=key)
        return {"meta": h.get("Metadata", {}), "etag": h.get("ETag", "").strip('"'), "size": h.get("ContentLength")}
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def storage_status() -> Dict[str, Any]:
    """So từng key: dữ liệu trên máy (theo báo cáo bước) với object trên R2 (metadata generated-at, rows)."""
    now = time.time()
    if _storage_cache["data"] is not None and now - _storage_cache["at"] < _STORAGE_TTL:
        return _storage_cache["data"]
    objs = r2_export.plan_objects(build=False)
    s3 = r2_client.get_client()
    reason = None if s3 else "Chưa cấu hình R2 trong .env"
    items = []
    for o in objs:
        remote = None
        if s3 is not None and reason is None:
            try:
                remote = _head(s3, o["key"])
            except Exception as exc:  # mất mạng: vẫn trả phần trên máy
                reason = f"Không đọc được R2: {type(exc).__name__}"
        status = r2_export.compare(o, remote["meta"] if remote else None) if reason is None else "khong_ro"
        items.append({"step": o["step"], "source": o["source"], "key": o["key"], "local_rows": o["rows"],
                      "local_generated_at": o["generated_at"], "status": status,
                      "r2_rows": int(remote["meta"]["rows"]) if remote and remote["meta"].get("rows") else None,
                      "r2_size": remote["size"] if remote else None})
    data = {"bucket": r2_client.bucket_name, "reason": reason, "items": items,
            "command": "python scripts/push_preprocessing_to_r2.py"}
    _storage_cache.update(at=now, data=data)
    return data


def _safe(v: Any) -> Any:
    """Giá trị numpy/pandas → JSON: NaN thành None, mảng thành list."""
    if hasattr(v, "tolist"):
        v = v.tolist()
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, dict):
        return {k: _safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_safe(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _parse(body: bytes, key: str) -> List[Dict[str, Any]]:
    if key.endswith(".jsonl"):
        return [json.loads(line) for line in body.decode("utf-8").splitlines() if line.strip()]
    import pandas as pd

    return pd.read_parquet(io.BytesIO(body)).to_dict(orient="records")


_heads: Dict[str, Any] = {}  # key -> (thời điểm, head): bảng dòng gọi nhiều trang liền nhau, không hỏi R2 mỗi lần


def _read_r2(key: str) -> Optional[List[Dict[str, Any]]]:
    s3 = r2_client.get_client()
    if s3 is None:
        return None
    hit = _heads.get(key)
    if hit and time.time() - hit[0] < _STORAGE_TTL:
        head = hit[1]
    else:
        head = _head(s3, key)
        _heads[key] = (time.time(), head)
    if head is None:
        return None
    cached = _r2_frames.get(key)
    if cached and cached[0] == head["etag"]:
        return cached[1]
    body = s3.get_object(Bucket=r2_client.bucket_name, Key=key)["Body"].read()
    rows = _parse(body, key)
    _r2_frames[key] = (head["etag"], rows)
    return rows


def _read_local(step: str, source: Optional[str]) -> List[Dict[str, Any]]:
    import pandas as pd

    base = r2_export.DATA / step
    if step in PER_SOURCE_STEPS:
        p = base / f"{source}.jsonl"
        return _parse(p.read_bytes(), p.name) if p.exists() else []
    p = base / ("features.parquet" if step == "05_encoding" else "all.parquet")
    if not p.exists():
        return []
    cached = _local_frames.get(p)
    if not cached or cached[0] != p.stat().st_mtime:
        cached = _local_frames[p] = (p.stat().st_mtime, pd.read_parquet(p))
    df = cached[1]
    if source and "source_platform" in df.columns:
        df = df[df["source_platform"] == source]
    return df.to_dict(orient="records")


def get_rows(step: str, source: Optional[str], offset: int, limit: int, origin: str) -> Dict[str, Any]:
    """Một trang dòng dữ liệu của một bước. origin=r2 đọc object trên R2 (tách theo nguồn), local đọc file trên máy."""
    step = _require_step(step)
    if step in PER_SOURCE_STEPS and not source:
        raise HTTPException(status_code=400, detail="Bước Clean xem theo từng nguồn: cần tham số source")
    limit = max(1, min(limit, MAX_ROWS))
    offset = max(0, offset)
    used, rows, note = origin, None, None
    if origin == "r2":
        if step == "05_encoding":
            keys = [r2_export.GOLD_KEYS["features.parquet"]]
        else:
            keys = [r2_export.silver_key(step, s) for s in ([source] if source else SOURCES)]
        try:
            parts = [_read_r2(k) for k in keys]
        except Exception as exc:
            parts, note = [None], f"Không đọc được R2: {type(exc).__name__}"
        if all(p is not None for p in parts):
            rows = [r for p in parts for r in p]
        else:
            note = note or "Chưa có trên R2: đang hiện bản trên máy"
    if rows is None:
        used, rows = "local", _read_local(step, source)
    page = rows[offset: offset + limit]
    return {"step": step, "source": source, "origin": used, "note": note, "total": len(rows),
            "offset": offset, "limit": limit, "rows": [_safe(r) for r in page]}
