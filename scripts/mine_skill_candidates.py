#!/usr/bin/env python3
"""Gom ứng viên kỹ năng để lập từ điển `skills_v2.json` (K8.12, chỉ đọc, không gọi mạng).

Đọc bảng 02 (`data/preprocessing/02_integration/all.parquet`, văn bản gốc, mục yêu cầu + mô tả) và gom 4 nguồn:

- a: tag kỹ năng của sàn (`skills_list`);
- b: token hoặc cụm 1–3 từ "dáng công nghệ" (chữ Latin; có số hoặc ký hiệu `# + . /`, hoặc viết hoa giữa câu),
     chỉ giữ cụm có >= 60% số lần xuất hiện mang dáng đó;
- c: cụm sau từ báo hiệu ("kinh nghiệm với", "thành thạo", "experience with"...), tách theo `, / ; & và hoặc and or`;
- d: alias của hai từ điển cũ (`processing/dictionaries/skills_taxonomy_230.json`, `preprocessing/dictionaries/skills.json`).

Khóa gộp = fold (hạ chữ thường, bỏ dấu) + gộp khoảng trắng. Giữ ứng viên có DF (số tin) >= --min-df.
Mỗi ứng viên ghi DF tổng, DF theo nguồn a–d, DF theo sàn, dạng viết hay gặp nhất và 3 câu ví dụ (seed 42).

    python scripts/mine_skill_candidates.py [--min-df 2] [--out data/processing/skill_candidates]

Đầu ra: <out>/candidates.tsv (DF giảm dần) và <out>/_summary.json.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from preprocessing.deduplication.text_norm import fold  # noqa: E402

SEED = 42
SOURCES = ("a", "b", "c", "d")
TAXONOMY = ROOT / "processing" / "dictionaries" / "skills_taxonomy_230.json"
OLD_SKILLS = ROOT / "preprocessing" / "dictionaries" / "skills.json"

TOK = re.compile(r"(?<![\w.#+])([A-Za-z][A-Za-z0-9]*(?:[.#+\-/][A-Za-z0-9#+]+)*[#+]*)(?![\w#+])")
SYMBOLIC = re.compile(r"\d|[#+./]")
SENT_END = re.compile(r"[.:;!?(\[\"“]\s*$")
CUE = re.compile(
    r"(?:kinh nghiệm(?: làm việc)?(?: với| về| sử dụng| trong)|thành thạo(?: các| một trong các)?|sử dụng thành thạo"
    r"|am hiểu(?: về)?|hiểu biết(?: về)?|nắm vững|kiến thức(?: về)?|biết sử dụng|làm việc với|có kỹ năng"
    r"|experience (?:with|in|using)|proficien(?:t|cy) (?:in|with)|knowledge of|familiar(?:ity)? with"
    r"|hands-on (?:experience )?(?:with|in)|expertise in|skilled in|understanding of|working knowledge of)"
    r"\s*:?\s*(.{2,160}?)(?=\.(?:\s|$)|[;(\n]|$)",
    re.IGNORECASE,
)
CUE_SPLIT = re.compile(r"\s*(?:,|/|;|&|\||\bvà\b|\bhoặc\b|\band\b|\bor\b|\betc\b|\bv\.v\b)\s*", re.IGNORECASE)
LINE_SPLIT = re.compile(r"[\n\r]+|(?<=[.;!?])\s+(?=[A-ZĐÀ-Ỵ])")


def key_of(s: str) -> str:
    """Khóa gộp: fold + gộp khoảng trắng + bỏ dấu câu ở hai đầu."""
    return " ".join(fold(unicodedata.normalize("NFC", s)).split()).strip(" -–:,.;()[]\"'")


def lines_of(text: str):
    for ln in LINE_SPLIT.split(unicodedata.normalize("NFC", text or "")):
        ln = " ".join(ln.split()).strip(" -•*●▪–")
        if 2 <= len(ln) <= 400:
            yield ln


def shaped_ngrams(line: str, max_n: int = 3):
    """Mọi n-gram 1–3 token Latin liền nhau (cách một khoảng trắng). Trả (n-gram gốc, có dáng công nghệ không)."""
    toks = [(m.start(1), m.end(1), m.group(1)) for m in TOK.finditer(line)]
    out = []
    for i in range(len(toks)):
        for n in range(1, max_n + 1):
            j = i + n
            if j > len(toks):
                break
            if any(line[toks[k][1]:toks[k + 1][0]] != " " for k in range(i, j - 1)):
                break
            words = [t[2] for t in toks[i:j]]
            if n == 1 and len(words[0]) < 2:
                continue
            start = toks[i][0]
            at_start = start == 0 or bool(SENT_END.search(line[max(0, start - 3):start]))
            caps = [bool(SYMBOLIC.search(w)) or w[0].isupper() for w in words]
            if at_start:  # đầu câu: chữ hoa của từ đầu không nói lên gì
                shaped = bool(SYMBOLIC.search(words[0])) if n == 1 else all(caps)
            else:
                shaped = all(caps)
            out.append((" ".join(words), shaped))
    return out


def cue_phrases(line: str):
    out = []
    for m in CUE.finditer(line):
        for piece in CUE_SPLIT.split(m.group(1)):
            piece = piece.strip(" -–:,.()[]\"'")
            if 2 <= len(piece) <= 40 and 1 <= len(piece.split()) <= 4:
                out.append(piece)
    return out


def load_old_aliases():
    """alias đã fold của hai từ điển cũ."""
    al = set()
    for s in json.loads(TAXONOMY.read_text(encoding="utf-8"))["skills"]:
        al.update(key_of(a) for a in (s["canonical"], *s["aliases"]))
    for name, aliases in json.loads(OLD_SKILLS.read_text(encoding="utf-8")).items():
        al.update(key_of(a) for a in (name, *aliases))
    return {a for a in al if a}


def alias_regex(aliases):
    alts = sorted(aliases, key=lambda a: (-len(a), a))
    return re.compile(r"(?<![a-z0-9_#+])(?:" + "|".join(map(re.escape, alts)) + r")(?![a-z0-9_#+])")


def doc_items(tags, text, alias_re):
    """Một tin → list (khóa, nguồn, dạng gốc, câu, dáng). Nguồn b trả cả lần không có dáng để tính tỷ lệ."""
    items = []
    lines = list(lines_of(text))
    folded = [key_of(ln) for ln in lines]
    for t in tags or ():
        t = " ".join(str(t).split())
        k = key_of(t)
        if k:
            line = next((ln for ln, f in zip(lines, folded) if f"{k}" in f), f"[tag] {t}")
            items.append((k, "a", t, line, True))
    for ln, f in zip(lines, folded):
        for g, shaped in shaped_ngrams(ln):
            items.append((key_of(g), "b", g, ln, shaped))
        for p in cue_phrases(ln):
            items.append((key_of(p), "c", p, ln, True))
        for m in alias_re.finditer(f):
            items.append((m.group(), "d", m.group(), ln, True))
    return [it for it in items if it[0]]


def display_from_examples(key, lines):
    """Dạng viết gốc hay gặp nhất của khóa trong các câu (tìm theo vị trí trên văn bản fold cùng độ dài)."""
    from processing.extraction.skills import fold_aligned

    c = collections.Counter()
    pat = re.compile(r"(?<![a-z0-9_#+])" + re.escape(key) + r"(?![a-z0-9_#+])")
    for ln in lines:
        f = fold_aligned(ln)
        if len(f) == len(ln):
            c.update(ln[m.start():m.end()] for m in pat.finditer(f))
    return c.most_common(1)[0][0] if c else key


def mine(df, alias_re, min_df=2, b_ratio=0.6):
    docs = []
    for r in df.itertuples(index=False):
        text = f"{r.raw_requirements_text or ''}\n{r.raw_description_text or ''}"
        tags = list(r.skills_list) if r.skills_list is not None else []
        docs.append((r.job_id_global, r.source_platform, doc_items(tags, text, alias_re)))

    src_docs = collections.defaultdict(lambda: {s: set() for s in SOURCES})
    b_occ, b_shaped = collections.Counter(), collections.Counter()
    for jid, _, items in docs:
        for k, src, _, _, shaped in items:
            if src == "b":
                b_occ[k] += 1
                b_shaped[k] += shaped
                if not shaped:
                    continue
            src_docs[k][src].add(jid)
    b_ok = {k for k in b_occ if b_shaped[k] / b_occ[k] >= b_ratio}

    def docs_of(k):
        s = src_docs[k]
        return s["a"] | (s["b"] if k in b_ok else set()) | s["c"] | s["d"]

    kept = {k for k in src_docs if len(docs_of(k)) >= min_df}

    forms = collections.defaultdict(collections.Counter)
    by_plat = collections.defaultdict(collections.Counter)
    ex = collections.defaultdict(dict)
    for jid, plat, items in docs:
        seen = set()
        for k, src, form, line, shaped in items:
            if k not in kept or (src == "b" and (not shaped or k not in b_ok)):
                continue
            if src != "d":  # nguồn d khớp trên văn bản fold: không có dạng viết gốc
                forms[k][form] += 1
            if k not in seen:
                seen.add(k)
                by_plat[k][plat] += 1
                ex[k].setdefault(jid, line)
    rng = random.Random(SEED)
    rows = []
    for k in kept:
        s = src_docs[k]
        jids = sorted(ex[k])
        pick = sorted(rng.sample(jids, min(3, len(jids))))
        rows.append({
            "key": k,
            "display": forms[k].most_common(1)[0][0] if forms[k] else display_from_examples(k, [ex[k][j] for j in jids]),
            "df": len(docs_of(k)),
            **{f"df_{x}": len(s[x]) if (x != "b" or k in b_ok) else 0 for x in SOURCES},
            "by_platform": ",".join(f"{p}:{n}" for p, n in sorted(by_plat[k].items(), key=lambda kv: (-kv[1], kv[0]))),
            "examples": " ‖ ".join(ex[k][j][:220] for j in pick),
        })
    rows.sort(key=lambda r: (-r["df"], r["key"]))
    return rows


def main() -> None:
    import pandas as pd

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(ROOT / "data" / "preprocessing" / "02_integration" / "all.parquet"))
    ap.add_argument("--out", default=str(ROOT / "data" / "processing" / "skill_candidates"))
    ap.add_argument("--min-df", type=int, default=2)
    a = ap.parse_args()

    df = pd.read_parquet(a.input, columns=["job_id_global", "source_platform", "skills_list",
                                           "raw_description_text", "raw_requirements_text"])
    df = df.sort_values("job_id_global", kind="stable")
    rows = mine(df, alias_regex(load_old_aliases()), min_df=a.min_df)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["key", "display", "df", "df_a", "df_b", "df_c", "df_d", "by_platform", "examples"]
    with (out / "candidates.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]).replace("\t", " ").replace("\n", " ") for c in cols) + "\n")
    summary = {
        "input": Path(a.input).relative_to(ROOT).as_posix() if Path(a.input).is_relative_to(ROOT) else a.input,
        "n_jobs": len(df), "min_df": a.min_df, "n_candidates": len(rows),
        "by_source": {x: sum(1 for r in rows if r[f"df_{x}"] > 0) for x in SOURCES},
        "only_source": {x: sum(1 for r in rows if r[f"df_{x}"] > 0 and all(r[f"df_{y}"] == 0 for y in SOURCES if y != x))
                        for x in SOURCES},
    }
    (out / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
