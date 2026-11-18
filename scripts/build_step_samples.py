#!/usr/bin/env python3
"""Dựng dữ liệu mẫu cho đặc tả từng bước pre-processing (chỉ đọc, không gọi mạng).

Với mỗi bước đã có đầu ra trên máy, ghi `docs/spec/preprocessing/samples/<bước>.json` gồm:

- `run`: thời điểm và `code_version` của report lần chạy thật, số dòng vào/ra theo nguồn, số bỏ theo luật;
- `rules`: mỗi luật một dòng (mã, tên, hành động, số tin, theo nguồn) và tối đa 3 ví dụ trước → sau lấy từ report;
- `schema`: các cột/khóa của đầu ra, kiểu, độ phủ;
- `trace`: trạng thái của **một tin mẫu xuyên suốt** (cùng `job_id`) ở bước đó.

Tin mẫu mặc định `topcv_2325743` (Backend Developer, 400–900 USD). Luật chọn (in ra khi chạy): tin còn tới bước 03,
có lương, kinh nghiệm, `raw_work_mode`, ≥ 3 phúc lợi, JD tiếng Anh, lương ngoại tệ và ≥ 2 snapshot raw, để một tin
đi qua được nhiều luật nhất (C1, `first_crawled_at`, đổi USD, dịch, work mode, kinh nghiệm). Không chọn ngẫu nhiên.

    python scripts/build_step_samples.py [--job topcv_2325743] [--step 01_clean ...]

Văn bản dài cắt ở 300 ký tự. Không ghi giờ chạy script vào file, nên chạy lại trên cùng dữ liệu ra file giống hệt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "preprocessing"
REPORTS = ROOT / "reports" / "preprocessing"
OUT = ROOT / "docs" / "spec" / "preprocessing" / "samples"
STEPS = ("01_clean", "01b_deduplication", "02_integration", "03_transformation", "04_normalization")
CUT = 300


def _short(v: Any) -> Any:
    """Cắt văn bản dài, đổi kiểu numpy/pandas về kiểu JSON."""
    try:
        import numpy as np
        if isinstance(v, np.ndarray):
            v = v.tolist()
        elif isinstance(v, np.generic):
            v = v.item()
    except ImportError:
        pass
    if isinstance(v, float) and v != v:  # NaN
        return None
    if isinstance(v, str):
        return v if len(v) <= CUT else v[:CUT] + f"… (+{len(v) - CUT} ký tự)"
    if isinstance(v, list):
        return [_short(x) for x in v[:15]] + ([f"… (+{len(v) - 15} phần tử)"] if len(v) > 15 else [])
    if isinstance(v, dict):
        return {k: _short(x) for k, x in v.items()}
    return v


def _report(step: str) -> dict[str, Any] | None:
    p = REPORTS / step / "_all.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _run_block(rep: dict[str, Any], step: str) -> dict[str, Any]:
    by_src = {}
    for p in sorted((REPORTS / step).glob("*.json")):
        if p.name.startswith("_"):
            continue
        r = json.loads(p.read_text(encoding="utf-8"))
        if "input" not in r:  # file phụ của bước (vd. anomalies), không phải report theo nguồn
            continue
        by_src[p.stem] = {"in": r["input"]["rows"], "out": r["output"]["rows"]}
    return {"generated_at": rep.get("generated_at"), "code_version": rep.get("code_version"), "mode": rep.get("mode"),
            "input": rep["input"], "output": rep["output"], "dropped": rep.get("dropped"), "by_source": by_src,
            "checks": rep.get("checks")}


def _rules_block(rep: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"id": r["id"], "name": r["name"], "action": r["action"], "rows": r["rows_affected"],
             "by_source": r.get("by_source"), "examples": _short((r.get("examples") or [])[:3])}
            for r in rep.get("rules", [])]


def _jsonl_find(path: Path, job: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    for line in path.open(encoding="utf-8"):
        if f'"{job}"' in line:
            env = json.loads(line)
            if str(env.get("metadata", {}).get("job_id")) == job:
                return env
    return None


def _jsonl_schema(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        env = json.loads(fh.readline())
    md = env.get("metadata", {})
    return {"format": "jsonl, mỗi dòng một envelope", "top_keys": sorted(env),
            "metadata_keys": sorted(md), "metadata_clean_keys": sorted(md.get("clean") or {}),
            "metadata_dedup_keys": sorted(md.get("dedup") or {})}


def _parquet_schema(df) -> list[dict[str, Any]]:
    out = []
    for c in df.columns:
        s = df[c]
        filled = s.apply(lambda v: v is not None and not (isinstance(v, float) and v != v)
                         and not (hasattr(v, "__len__") and not isinstance(v, str) and len(v) == 0)
                         and not (isinstance(v, str) and not v.strip()))
        out.append({"column": c, "dtype": str(s.dtype), "fill_pct": round(100 * filled.mean(), 1)})
    return out


def _raw_snapshots(src: str, sid: str) -> list[dict[str, Any]]:
    rows = []
    for p in sorted((ROOT / "data" / src / "raw").glob(f"*/{sid}_v*.json")):
        env = json.loads(p.read_text(encoding="utf-8"))
        md = env.get("metadata", {})
        rows.append({"file": f"data/{src}/raw/{p.parent.name}/{p.name}", "version": md.get("version"),
                     "scraped_at": md.get("scraped_at"), "content_hash": (md.get("content_hash") or "")[:16]})
    return rows


def build(step: str, job: str) -> dict[str, Any] | None:
    rep = _report(step)
    src, sid = job.split("_", 1)
    data_ok = (DATA / step / f"{src}.jsonl").is_file() or (DATA / step / "all.parquet").is_file()
    if rep is None or not data_ok:  # report trong git có thể là lần chạy cũ; không có dữ liệu thì không ghép
        return None
    doc: dict[str, Any] = {"step": step, "trace_job": job, "run": _run_block(rep, step), "rules": _rules_block(rep)}
    if step in ("01_clean", "01b_deduplication"):
        path = DATA / step / f"{src}.jsonl"
        if not path.is_file():
            return None
        doc["schema"] = _jsonl_schema(path)
        env = _jsonl_find(path, sid)
        md = (env or {}).get("metadata", {})
        payload = (env or {}).get("raw_payload", {})
        doc["trace"] = {"present": env is not None,
                        "metadata": _short({k: v for k, v in md.items() if k not in ("clean", "dedup")}),
                        "metadata_clean": _short(md.get("clean")), "metadata_dedup": _short(md.get("dedup")),
                        "raw_payload_keys": sorted(payload),
                        "raw_payload_excerpt": _short({k: payload.get(k) for k in sorted(payload)[:40]
                                                       if not isinstance(payload.get(k), (dict, list))})}
        if step == "01_clean":
            doc["trace"]["raw_snapshots"] = _raw_snapshots(src, sid)
        return doc
    import pandas as pd
    path = DATA / step / "all.parquet"
    if not path.is_file():
        return None
    df = pd.read_parquet(path)
    doc["schema"] = _parquet_schema(df)
    row = df[df["job_id_global"] == job]
    doc["trace"] = {"present": len(row) == 1, "row": _short(row.iloc[0].to_dict()) if len(row) else None}
    return doc


def candidates() -> int | None:
    """Số tin khớp luật chọn tin mẫu (để ghi vào đặc tả), đo trên bảng 03."""
    p = DATA / "03_transformation" / "all.parquet"
    if not p.is_file():
        return None
    import pandas as pd
    df = pd.read_parquet(p)
    m = (df.salary_min_vnd.notna() & df.exp_min_years.notna() & df.raw_work_mode.notna()
         & df.benefits_list.apply(lambda x: x is not None and len(x) >= 3) & (df.language == "en")
         & (df.salary_currency_raw == "USD"))
    n = 0
    for jid in df.loc[m, "job_id_global"]:
        s, i = jid.split("_", 1)
        n += len(list((ROOT / "data" / s / "raw").glob(f"*/{i}_v*.json"))) >= 2
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job", default="topcv_2325743")
    ap.add_argument("--step", nargs="*", default=list(STEPS))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print("tin khớp luật chọn tin mẫu:", candidates())
    for step in a.step:
        doc = build(step, a.job)
        if doc is None:
            print(f"{step}: chưa có đầu ra hoặc report trên máy, bỏ qua")
            continue
        (OUT / f"{step}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"{step}: ghi {OUT / f'{step}.json'} (tin mẫu có mặt: {doc['trace']['present']})")


if __name__ == "__main__":
    main()
