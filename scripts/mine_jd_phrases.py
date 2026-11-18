#!/usr/bin/env python3
"""Gom câu ứng viên trong JD để dựng từ điển trích xuất của bước 03 (chỉ đọc, không gọi mạng).

Đọc `data/preprocessing/03_transformation/all.parquet`, tách tiêu đề, mô tả, yêu cầu (bản gốc và bản dịch
`*_vi` nếu có) thành từng dòng, giữ dòng chạm tới từng chủ đề bằng từ khóa rộng (để không bỏ sót), lấy cụm tối đa 5 từ hai bên
từ khóa, gộp cụm giống nhau sau khi hạ chữ thường và thay số bằng `#`, rồi ghi ra một file mỗi chủ đề kèm số tin và một ví dụ.
Người đọc (người dùng và Claude) duyệt các dòng này để lập từ điển trong `preprocessing/dictionaries/`.

    python scripts/mine_jd_phrases.py [--out data/preprocessing/jd_phrases] [--min-count 1]

Đầu ra: <out>/<chủ đề>.tsv (cột: số tin, số dòng, dòng chuẩn hóa, ví dụ gốc, nguồn) và <out>/_summary.json.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEXT_COLS = ("job_title_clean", "description_clean", "requirements_clean", "description_vi", "requirements_vi")
# Từ khóa rộng: chỉ để chọn dòng cho người đọc, không phải luật trích xuất
TOPICS = {
    "work_mode": r"remote|từ xa|hybrid|kết hợp|văn phòng|onsite|on-site|on site|wfh|work from|tại nhà|linh hoạt|flexib|office|tại công ty|làm online",
    "employment_type": r"full[- ]?time|toàn thời gian|part[- ]?time|bán thời gian|thực tập|intern|freelanc|hợp đồng|contract|thời vụ|cộng tác|chính thức|permanent|probation|thử việc",
    "experience": r"năm|year|yrs|kinh nghiệm|experience|exp\b|fresher|junior|senior|mới tốt nghiệp|sinh viên",
    "working_time": r"thứ\s*(?:2|hai|7|bảy|6|sáu)|t2|t7|monday|friday|saturday|sunday|chủ nhật|giờ làm|working (?:hour|time|day)|ca làm|shift|\d{1,2}\s*[h:]\s*\d{0,2}\s*[-–]|tăng ca|overtime|ot\b",
    "salary": r"lương|salary|thu nhập|income|triệu|usd|\$|vnđ|vnd|gross|net\b|thưởng|bonus",
}
_NUM = re.compile(r"\d+([.,]\d+)*")
# Kinh nghiệm: dòng quá đa dạng, nên chỉ lấy cụm tối đa 5 từ hai bên con số năm / cụm "không yêu cầu kinh nghiệm"
_EXP_WIN = re.compile(
    r"(?:\S+\s+){0,5}(?:\d+(?:[.,]\d+)?\s*\+?\s*(?:[-–~]|đến|to|tới)?\s*(?:\d+(?:[.,]\d+)?)?\s*\+?\s*"
    r"(?:năm|years?|yrs?|tháng|months?)|không yêu cầu kinh nghiệm|chưa có kinh nghiệm|no (?:prior )?experience"
    r"|fresher|mới tốt nghiệp|sinh viên năm cuối|fresh graduate)(?:\s+\S+){0,5}", re.IGNORECASE)


def _lines(text: str):
    for ln in re.split(r"[\n\r]+|(?<=[.;!?])\s+(?=[A-ZĐÀ-Ỵ])", text):
        ln = " ".join(ln.split()).strip(" -•*●▪–:")
        if 3 <= len(ln) <= 300:
            yield ln


def _norm(ln: str) -> str:
    return _NUM.sub("#", unicodedata.normalize("NFC", ln.lower()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(ROOT / "data" / "preprocessing" / "03_transformation" / "all.parquet"))
    ap.add_argument("--out", default=str(ROOT / "data" / "preprocessing" / "jd_phrases"))
    ap.add_argument("--min-count", type=int, default=1)
    a = ap.parse_args()
    import pandas as pd

    df = pd.read_parquet(a.input)
    pats = {t: re.compile(p, re.IGNORECASE) for t, p in TOPICS.items()}
    jobs = {t: collections.defaultdict(set) for t in TOPICS}
    lines_n = {t: collections.Counter() for t in TOPICS}
    example, srcs = {}, {t: collections.defaultdict(collections.Counter) for t in TOPICS}
    cols = [c for c in TEXT_COLS if c in df.columns]
    for rec in df[["job_id_global", "source_platform", *cols]].itertuples(index=False):
        jid, src = rec[0], rec[1]
        for col, text in zip(cols, rec[2:]):
            if not isinstance(text, str) or not text:
                continue
            for ln in _lines(text):
                for t, p in pats.items():
                    if not p.search(ln):
                        continue
                    if t == "experience":
                        pieces = [m.group(0) for m in _EXP_WIN.finditer(ln)]
                    else:  # cụm tối đa 5 từ hai bên từ khóa: gộp được các câu chỉ khác phần không liên quan
                        pieces = [m.group(0) for m in re.finditer(r"(?:\S+\s+){0,5}(?:" + TOPICS[t] + r")\S*(?:\s+\S+){0,5}",
                                                                  ln, re.IGNORECASE)]
                    for piece in pieces:
                        k = _norm(piece)
                        jobs[t][k].add(jid)
                        lines_n[t][k] += 1
                        srcs[t][k][src] += 1
                        example.setdefault((t, k), f"{ln}  [{col}]")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for t in TOPICS:
        rows = sorted(((len(j), lines_n[t][k], k) for k, j in jobs[t].items() if len(j) >= a.min_count), reverse=True)
        with (out / f"{t}.tsv").open("w", encoding="utf-8") as f:
            f.write("so_tin\tso_dong\tdong_chuan_hoa\tvi_du\tnguon\n")
            for n_job, n_line, k in rows:
                src = ",".join(f"{s}:{c}" for s, c in srcs[t][k].most_common())
                f.write(f"{n_job}\t{n_line}\t{k}\t{example[(t, k)]}\t{src}\n")
        summary[t] = {"distinct_lines": len(rows), "jobs_touched": len(set().union(*jobs[t].values())) if jobs[t] else 0}
        print(f"{t}: {len(rows):,} dòng khác nhau, chạm {summary[t]['jobs_touched']:,} tin")
    summary["input_rows"] = len(df)
    summary["text_cols"] = cols
    (out / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
