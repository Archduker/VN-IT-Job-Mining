#!/usr/bin/env python3
"""Profiling 8 nguồn (PH1-A): tỉ lệ thiếu, chất lượng văn bản, heatmap, ydata-profiling nếu chạy được.

    python scripts/profile_sources.py --when both [--sample 500] [--seed 42] [--dry-run]
before_clean: raw mới nhất mỗi job_id, làm phẳng. after_clean: data/preprocessing/03_transformation/all.parquet (cột *_clean; 02 chỉ làm phẳng, còn HTML/NFD theo hợp đồng).
Chỉ đọc; ghi vào reports/preprocessing/00_profiling/<when>/.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from preprocessing.common import SOURCES  # noqa: E402

OUT = REPO_ROOT / "reports" / "preprocessing" / "00_profiling"
EMPTY_TOKENS = {"", "0", "đang cập nhật", "none", "nan", "null"}
CONVENTION = "rỗng = None/NaN, chuỗi rỗng, '0', 'Đang cập nhật', 'None', danh sách rỗng"
TEXT_COLS = ["job_title", "raw_description_text", "raw_requirements_text"]
AFTER_TEXT_COLS = ["job_title_clean", "description_clean", "requirements_clean"]  # đầu ra PH2 (03_transformation)
TAG = re.compile(r"<[^>]+>|&[a-zA-Z]{2,8};|&#\d+;")
VI_DIACRITIC = re.compile(r"[ăâđêôơưàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ]", re.I)
# shortcut: heuristic từ khoá tiếng Việt không dấu, chưa nhận diện ngôn ngữ thật (PH3 làm), đổi khi có cột lang
VI_ASCII_MARK = re.compile(r"\b(yeu cau|kinh nghiem|mo ta|quyen loi|cong viec|luong|tuyen dung|ung vien)\b", re.I)


def _is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, (list, tuple, dict)) or hasattr(v, "__len__") and not isinstance(v, str):
        return len(v) == 0
    if isinstance(v, float) and v != v:
        return True
    return str(v).strip().lower() in EMPTY_TOKENS


def missing_rates(df: pd.DataFrame, cols) -> dict:
    n = max(len(df), 1)
    return {c: round(float(sum(_is_empty(v) for v in df[c])) / n, 4) if c in df else 1.0 for c in cols}


def text_quality(df: pd.DataFrame, cols=None) -> dict:
    """% giá trị văn bản (các cột TEXT_COLS có mặt, bỏ giá trị rỗng) còn HTML/entity, NFD, tiếng Việt không dấu."""
    texts = [str(v) for c in (cols or TEXT_COLS) if c in df for v in df[c] if not _is_empty(v)]
    n = len(texts)
    if not n:
        return {"n_texts": 0, "html": None, "nfd": None, "no_diacritic": None}
    pct = lambda k: round(100.0 * k / n, 2)  # noqa: E731
    return {
        "n_texts": n,
        "html": pct(sum(bool(TAG.search(t)) for t in texts)),
        "nfd": pct(sum(unicodedata.normalize("NFC", t) != t for t in texts)),
        "no_diacritic": pct(sum(not VI_DIACRITIC.search(t) and bool(VI_ASCII_MARK.search(t)) for t in texts)),
    }


def load_before(source: str) -> pd.DataFrame:
    from preprocessing.common.raw_reader import latest_envelopes
    from preprocessing.integration.json_flattener import flatten_raw_job_record

    envs, _ = latest_envelopes(REPO_ROOT / "data" / source / "raw")
    envs.sort(key=lambda e: str(e["metadata"].get("job_id")))
    return pd.DataFrame([flatten_raw_job_record(e) for e in envs])


def load_after(source: str) -> pd.DataFrame:
    path = REPO_ROOT / "data" / "preprocessing" / "03_transformation" / "all.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path, filters=[("source_platform", "==", source)])


def heatmap_html(matrix: dict, title: str) -> str:
    cols = sorted({c for m in matrix.values() for c in m})
    esc = html_lib.escape
    rows = []
    for c in cols:
        cells = "".join(
            f'<td style="background:hsl({int(120 * (1 - matrix[s].get(c, 1.0)))},60%,45%)" title="{esc(s)} {esc(c)}: {matrix[s].get(c, 1.0):.0%}">{matrix[s].get(c, 1.0):.0%}</td>'
            for s in matrix
        )
        rows.append(f"<tr><th>{esc(c)}</th>{cells}</tr>")
    head = "".join(f"<th>{esc(s)}</th>" for s in matrix)
    return (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)}</title><style>body{{font:13px sans-serif;margin:8px}}.w{{overflow-x:auto}}"
        "table{border-collapse:collapse}td,th{padding:3px 6px;border:1px solid #888;text-align:center;color:#fff}"
        "th{color:inherit;position:sticky;left:0}td{min-width:44px}</style>"
        f"<h3>{esc(title)} (đỏ = thiếu nhiều)</h3><div class=w><table><tr><th></th>{head}</tr>{''.join(rows)}</table></div>"
    )


def run(when: str, sample: int, seed: int, dry: bool) -> None:
    loader = load_before if when == "before_clean" else load_after
    out = OUT / when
    missing, text, sizes, ydata = {}, {}, {}, {}
    for src in SOURCES:
        df = loader(src)
        sizes[src] = {"total": len(df)}
        if df.empty:
            missing[src], text[src] = {}, text_quality(df, AFTER_TEXT_COLS if when == "after_clean" else None)
            ydata[src] = "không có dữ liệu"
            print(f"[{when}] {src}: 0 dòng (không có dữ liệu)")
            continue
        df = df.sample(min(sample, len(df)), random_state=seed)
        sizes[src]["sampled"] = len(df)
        print(f"[{when}] {src}: {sizes[src]['total']} dòng, mẫu {len(df)}")
        if dry:
            continue
        cols = [c for c in df.columns if c != "source_platform"]
        missing[src], text[src] = missing_rates(df, cols), text_quality(df, AFTER_TEXT_COLS if when == "after_clean" else None)
        try:
            from ydata_profiling import ProfileReport

            # words=False (cat+text): wordcloud ném ValueError "Couldn't find space to draw" khi cột chữ toàn từ bị lọc (vieclam24h before, glints after)
            flat = df.drop(columns=[c for c in df if df[c].map(lambda v: isinstance(v, (list, dict))).any()])
            out.mkdir(parents=True, exist_ok=True)
            ProfileReport(flat, minimal=True, title=f"{src} {when}", vars={"cat": {"words": False}, "text": {"words": False}}).to_file(out / f"profile_{src}.html")
            ydata[src] = "ok"
        except Exception as e:  # ghi lý do, không hạ pandas
            ydata[src] = f"bỏ: {type(e).__name__}: {str(e)[:200]}"
    if dry:
        print("dry-run: không ghi file")
        return
    if not any(missing.values()):
        print(f"[{when}] không nguồn nào có dữ liệu: không ghi báo cáo (after_clean cần chạy Transformation để có 03_transformation/all.parquet)")
        return
    out.mkdir(parents=True, exist_ok=True)
    meta = {"when": when, "seed": seed, "sample": sample, "generated_at": datetime.now(timezone.utc).isoformat(), "sizes": sizes}
    dump = lambda name, obj: (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")  # noqa: E731
    dump("missing_matrix.json", {**meta, "convention": CONVENTION, "missing_rate": missing})
    dump("text_quality.json", {**meta, "text_cols": AFTER_TEXT_COLS if when == "after_clean" else TEXT_COLS, "no_diacritic_rule": "không có ký tự có dấu và có cụm tiếng Việt không dấu (heuristic)", "by_source": text, "ydata_profiling": ydata})
    present = {s: m for s, m in missing.items() if m}
    (out / "missing_heatmap.html").write_text(heatmap_html(present, f"Tỉ lệ thiếu {when}"), encoding="utf-8")
    print(f"Đã ghi {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--when", choices=["before_clean", "after_clean", "both"], default="both")
    ap.add_argument("--sample", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for w in ("before_clean", "after_clean") if a.when == "both" else (a.when,):
        run(w, a.sample, a.seed, a.dry_run)


if __name__ == "__main__":
    main()
