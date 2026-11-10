"""Read R2 objects into RAM only. No disk cache or local fallback."""

import io
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pandas as pd
from app.core.r2_client import r2_client
from app.services.eda_raw_scan_service import scan
from app.services.pipeline_report_service import pipeline_report_service
from botocore.exceptions import ClientError
from fastapi import HTTPException

_cache = {}
_locks = {}
MAX_OBJECT_BYTES = 128 * 1024 * 1024


def _read(client, key):
    response = client.get_object(Bucket=r2_client.bucket_name, Key=key)
    body = response["Body"]
    try:
        if response.get("ContentLength", 0) > MAX_OBJECT_BYTES:
            raise HTTPException(413, detail={"reason": "R2_OBJECT_TOO_LARGE"})
        data = body.read(MAX_OBJECT_BYTES + 1)
        if len(data) > MAX_OBJECT_BYTES:
            raise HTTPException(413, detail={"reason": "R2_OBJECT_TOO_LARGE"})
        return data
    finally:
        body.close()


def dataset(source):
    # Serialize cold reads so summary, inventory and charts share one scan.
    with _locks.setdefault(source, Lock()):
        cached = _cache.get(source)
        if cached and time.monotonic() - cached[0] < 60:
            return cached[1]
        try:
            client = r2_client.get_client()
            if client is None:
                raise HTTPException(503, detail={"reason": "R2_NOT_CONFIGURED"})
            samples = []
            frame = None
            for key in (
                f"staging/{source}/preprocessing/04_normalization.parquet",
                f"staging/{source}/{source}_flat_clean.parquet",
            ):
                try:
                    frame = pd.read_parquet(io.BytesIO(_read(client, key)))
                    break
                except ClientError as exc:
                    code = str(exc.response.get("Error", {}).get("Code"))
                    if code not in ("NoSuchKey", "404", "NotFound"):
                        raise
            data = (samples, frame)
            _cache[source] = (time.monotonic(), data)
            return data
        except HTTPException:
            raise
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code"))
            reason = (
                "R2_ACCESS_DENIED"
                if code in ("403", "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch")
                else "R2_READ_FAILED"
            )
            raise HTTPException(503, detail={"reason": reason}) from exc
        except Exception as exc:
            # Never include SDK exceptions: they may contain credentials or URLs.
            raise HTTPException(503, detail={"reason": "R2_READ_FAILED"}) from exc


def inventory(source):
    return scan(source)["inventory"]


def summary(source):
    samples, frame = dataset(source)
    job = scan(source)
    fields = job["inventory"]
    total = len(frame) if frame is not None else None
    salary_rate = negotiable = None
    if total:
        cols = [c for c in ("salary_min_vnd", "salary_max_vnd") if c in frame]
        if cols:
            salary_rate = round(100 * float(frame[cols].apply(pd.to_numeric, errors="coerce").replace([float("inf"), float("-inf")], float("nan")).notna().any(axis=1).mean()), 2)
        if "is_salary_negotiable_declared" in frame:
            negotiable = round(
                100
                * float(frame["is_salary_negotiable_declared"].fillna(False).astype(bool).mean()),
                2,
            )
    return {
        "source": source,
        "total_records": total,
        "sampled_records": job["records"],
        "raw_scan": {k: v for k, v in job.items() if k != "inventory"},
        "fields_count": len(fields),
        "completeness_score_pct": round(
            100 - sum(f["null_rate_pct"] for f in fields) / len(fields), 2
        )
        if fields
        else None,
        "salary_parse_rate_pct": salary_rate,
        "negotiable_salary_pct": negotiable,
        "reason": "NO_DATA"
        if job["status"] == "COMPLETE" and not job["records"] and frame is None
        else "NO_STAGING_DATA"
        if frame is None
        else None,
    }


def charts(source):
    result = pipeline_report_service.eda_charts_from_frame(dataset(source)[1], source)
    result["origin"] = "r2"
    if not result["available"]:
        result["unavailable_reason"] = "NO_STAGING_DATA: chưa có Parquet staging tương ứng trên R2."
    return result


def compare(sources):
    def row(source):
        s = summary(source)
        return {
            "source": source,
            "available": bool(s["sampled_records"] or s["total_records"] or s["raw_scan"]["status"] in ("QUEUED", "RUNNING")),
            "records": s["total_records"],
            "completeness_pct": s["completeness_score_pct"],
            "salary_text_pct": None,
            "salary_numeric_pct": s["salary_parse_rate_pct"],
            "experience_pct": None,
            "seniority_pct": None,
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(row, sources))
    present = any(row["available"] for row in rows)
    return {
        "available": present,
        "sources": rows,
        "unavailable_reason": None if present else "NO_DATA: R2 chưa có dữ liệu EDA.",
    }
