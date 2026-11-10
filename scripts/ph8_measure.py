# -*- coding: utf-8 -*-
"""PH8: sinh file ỨNG VIÊN (approved=false) và đo độ thưa ma trận kỹ năng trên data/preprocessing/01_clean (chỉ đọc).

    python scripts/ph8_measure.py --out-dir <thư mục ngoài data/ reports/> [--write-candidates]

--write-candidates ghi processing/dictionaries/*_candidates.json; người dùng chép mục duyệt sang section_headings.json,
priority_cues.json, short_aliases.json (đặt approved=true). Không có mục nào tự duyệt.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from preprocessing.common import SOURCES  # noqa: E402
from preprocessing.common.text_clean import clean_text  # noqa: E402
from preprocessing.deduplication.text_norm import fold  # noqa: E402
from preprocessing.integration.json_flattener import flatten_raw_job_record  # noqa: E402
from processing.extraction import run as R  # noqa: E402
from processing.extraction import sections as S  # noqa: E402
from processing.extraction import skills as K  # noqa: E402
from processing.extraction.sections import DICT_DIR  # noqa: E402
from processing.selection.sparsity import reduce_sparsity  # noqa: E402

CUE_RE = re.compile(r"uu tien|nice to have|la mot loi the|\bplus\b|loi the")


def load_df():
    rows = []
    for src in SOURCES:
        for line in (ROOT / "data" / "preprocessing" / "01_clean" / f"{src}.jsonl").open(encoding="utf-8"):
            f = flatten_raw_job_record(json.loads(line))
            rows.append({"job_id_global": f["job_id_global"], "source_platform": src,
                         "description_clean": clean_text(f.get("raw_description_text")),
                         "requirements_clean": clean_text(f.get("raw_requirements_text")),
                         "skills_list": f.get("skills_list")})
    return rows


def lines_of(rec):
    for k in ("description_clean", "requirements_clean"):
        for ln in str(rec[k] or "").split("\n"):
            t = ln.strip()
            t = t[2:].strip() if t.startswith("- ") else t
            if t:
                yield t


def candidates(rows, taxonomy):
    head, cue = Counter(), Counter()
    for rec in rows:
        seen_h, seen_c = set(), set()
        for t in lines_of(rec):
            key = fold(t).rstrip(":").strip()
            if len(key.split()) <= 6 and (t.endswith(":") or (t.isupper() and len(t) > 3)):
                seen_h.add(key)
            if CUE_RE.search(fold(t)):
                seen_c.add(" ".join(key.split()[:3]))
        head.update(seen_h)
        cue.update(seen_c)
    mk = lambda c, n, name: [{name: k, "n_jobs": v, "section": None, "approved": False} for k, v in c.most_common(n) if v >= 5]  # noqa: E731
    heads = mk(head, 80, "phrase")
    cues = [{"phrase": k, "n_jobs": v, "approved": False} for k, v in cue.most_common(40) if v >= 5]
    short = K.short_alias_candidates(taxonomy)
    by_form = defaultdict(set)
    for rec in rows:
        txt = "\n".join(lines_of(rec))
        ft = K.fold_aligned(txt)
        for c in short:
            if re.search(r"(?<![a-z0-9_#+])" + re.escape(c["alias"]) + r"(?![a-z0-9_#+])", ft):
                by_form[("fold", c["alias"], c["slug"])].add(rec["job_id_global"])
            if any(re.search(r"(?<![\w#+])" + re.escape(f) + r"(?![\w#+])", txt) for f in c["forms"]):
                by_form[("case", c["alias"], c["slug"])].add(rec["job_id_global"])
    for c in short:
        c["n_jobs_fold_noise"] = len(by_form[("fold", c["alias"], c["slug"])])
        c["n_jobs_case_sensitive"] = len(by_form[("case", c["alias"], c["slug"])])
    norm = defaultdict(list)
    for s in taxonomy:
        norm[re.sub(r"[^a-z0-9#+]", "", fold(s["canonical"])).removesuffix("js")].append(s["slug"])
    merges = [{"slugs": v, "approved": False} for v in norm.values() if len(v) > 1]
    return heads, cues, short, merges


def sparsity(rows, matcher, taxonomy):
    groups = {s["slug"]: s["group"] for s in taxonomy}
    sk, n = [], len(rows)
    for rec in rows:
        _, srows, _ = R.analyze(rec, matcher, {}, [])
        sk += [{**r, "job_id_global": rec["job_id_global"]} for r in srows if r["via"] == "text"]
    out = {}
    for mode in ("family", "other"):
        for t in (None, 3, 5, 10, 20, 50):
            _, rep = reduce_sparsity(sk, n, groups, len(groups), None, t, mode)
            out[f"{mode}_min_df={t}"] = {"n_skills_folded": rep["n_skills_folded"], "after": rep["after"]}
    return {"before": reduce_sparsity(sk, n, groups, len(groups))[1]["before"], "variants": out}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--write-candidates", action="store_true")
    a = ap.parse_args(argv)
    for bad in ("data", "reports"):
        if (ROOT / bad) in [a.out_dir.resolve(), *a.out_dir.resolve().parents]:
            raise SystemExit(f"--out-dir không được nằm trong {bad}/")
    rows, taxonomy = load_df(), K.load_taxonomy()
    heads, cues, short, merges = candidates(rows, taxonomy)
    if a.write_candidates:
        for name, items in (("section_headings_candidates", heads), ("priority_cues_candidates", cues),
                            ("short_aliases_candidates", short), ("skill_merge_candidates", merges)):
            (DICT_DIR / f"{name}.json").write_text(json.dumps({"version": 1, "n_jobs_scanned": len(rows), "items": items},
                                                            ensure_ascii=False, indent=1), encoding="utf-8")
    base = K.SkillMatcher(taxonomy, K.load_short_forms())
    hypo = K.SkillMatcher(taxonomy, [(c["slug"], f) for c in short if not c["ambiguous"] for f in c["forms"]])
    res = {"n_jobs": len(rows), "approved_short_forms_used": len(base.short_map),
           "sparsity_current_dictionaries": sparsity(rows, base, taxonomy),
           "sparsity_hypothetical_all_short_candidates_approved": sparsity(rows, hypo, taxonomy)}
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "ph8_sparsity.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("headings", len(heads), "cues", len(cues), "short", len(short), "merges", len(merges))
    return 0


if __name__ == "__main__":
    sys.exit(main())
