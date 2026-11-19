#!/usr/bin/env python3
"""Đề xuất nhãn `type` (tool | concept) cho kỹ năng kỹ thuật của skills_v2 (K8.17). Chỉ ghi trên máy.

Đọc `processing/dictionaries/skills_v2.json`, `data/processing/08_skills/job_skills.parquet` (DF theo tin),
bảng Silver (ghép URL với dữ liệu ngoài) và `data/external/vnjt/step07.jsonl` (bằng chứng ngoài, xem `_vnjt.py`).
Mỗi kỹ năng kỹ thuật có DF ≥ `--min-df` (mặc định 5) được một dòng, sắp DF giảm dần, chia lô `--batch-size`:

    processing/dictionaries/skills_v2_decisions/types_t<NN>.json
      _meta: lô, luật, ngày sinh, approved (null; người dùng duyệt thì ghi {date, quote})
      items: slug, name, group, df, examples, ext {n, tech_stack, keywords}, de_xuat, ly_do, quyet_dinh (null)

`de_xuat` ban đầu theo luật: bằng chứng ngoài đủ (≥ `MIN_EXT` tin) thì theo tỷ lệ tech_stack/(tech_stack+keywords),
nếu không thì theo nhóm (`GROUP_PRIOR`); hai bên ngược nhau, hoặc nhóm ranh giới, thì `hoi`. Claude đọc lại từng lô và
ghi vào `types_claude.txt` (script áp vào `de_xuat`, `lop_hoi`); người dùng điền `quyet_dinh` khi muốn khác đề xuất, rồi duyệt cả lô.

Không ghi đè lô đã có (đã sửa tay hoặc đã duyệt); muốn sinh lại thì xóa file lô đó.

    python scripts/propose_skill_types.py [--min-df 5] [--batch-size 150] [--check]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import _vnjt as X  # noqa: E402
from processing.extraction.skills import matcher_from_v2  # noqa: E402

DICT = ROOT / "processing" / "dictionaries" / "skills_v2.json"
JOB_SKILLS = ROOT / "data" / "processing" / "08_skills" / "job_skills.parquet"
SILVER = ROOT / "data" / "preprocessing" / "04_normalization" / "silver.parquet"
DEC_DIR = ROOT / "processing" / "dictionaries" / "skills_v2_decisions"
PAGE = ROOT / "docs" / "presentation" / "processing_steps" / "skill_types.html"
CLASS_NOTE = {
    "chuan": "Chuẩn, giao thức, định dạng (REST, OAuth, TCP/IP, JSON, ISO 27001…): có tên riêng nhưng là đặc tả, không phải sản phẩm",
    "chung_chi": "Chứng chỉ (CCNA, PMP, ISTQB…): tên riêng nhưng là bằng, không phải công cụ dùng trực tiếp",
    "office": "Bộ văn phòng gộp (Microsoft Office, Google Workspace): Excel, Word, Google Sheets riêng lẻ đã xếp tool",
}
CLAUDE_REVIEW = DEC_DIR / "types_claude.txt"   # Claude đọc lại đề xuất theo luật: `tool|con|hoi:<lớp> slug slug ...`
TYPES = ("tool", "concept")
MIN_EXT = 5          # số tin trùng tối thiểu để dùng bằng chứng ngoài
TOOL_SHARE = 0.7     # tech_stack/(tech_stack+keywords) ≥ ngưỡng → tool
CONCEPT_SHARE = 0.3  # ≤ ngưỡng → concept

# Nhóm thường là công cụ có tên riêng / thường là khái niệm. Nhóm không có ở đây là ranh giới (chỉ theo bằng chứng).
GROUP_PRIOR = {
    "programming_languages": "tool", "frontend": "tool", "backend": "tool", "mobile": "tool", "databases": "tool",
    "messaging": "tool", "cloud": "tool", "dev_tools": "tool", "office_tools": "tool", "enterprise_apps": "tool",
    "cad_engineering": "tool", "ai_tools": "tool", "bi_analytics": "tool", "game_dev": "tool",
    "methodology_pm": "concept", "architecture_api": "concept", "security": "concept", "testing_qa": "concept",
    "systems_network": "concept", "data_science_ml": "concept", "ai_genai": "concept", "embedded_iot": "concept",
    "design_creative": "concept", "digital_marketing": "concept", "blockchain": "concept",
}


def evidence(d: dict, js: pd.DataFrame, silver: pd.DataFrame, ext: list) -> dict:
    """slug → {n, tech_stack, keywords}: trên các tin trùng mà mình bắt được slug, bên kia xếp nó vào đâu."""
    m = matcher_from_v2(d)
    matched = X.match_jobs(zip(silver["job_id"], silver["source"], silver["url"], silver["title"]), ext)
    sets = X.ext_slug_sets(matched, m)
    ours = js[js["job_id_global"].isin(sets)].groupby("job_id_global")["slug"].apply(set)
    ev = {}
    for j, slugs in ours.items():
        ts, kw = sets[j]
        for s in slugs:
            e = ev.setdefault(s, Counter())
            e["n"] += 1
            e["tech_stack"] += s in ts
            e["keywords"] += s in kw and s not in ts
    return {s: dict(c) for s, c in ev.items()}, len(matched)


def propose(group: str, ev: dict) -> tuple:
    prior = GROUP_PRIOR.get(group)
    hit = ev.get("tech_stack", 0) + ev.get("keywords", 0)
    by_ev = None
    if hit >= MIN_EXT:
        share = ev["tech_stack"] / hit
        by_ev = "tool" if share >= TOOL_SHARE else "concept" if share <= CONCEPT_SHARE else None
        note = f"ngoài {ev['tech_stack']}/{hit} ở tech_stack"
    else:
        note = f"ngoài ít ({hit} tin)"
    if by_ev and prior and by_ev != prior:
        return "hoi", f"nhóm {group} gợi ý {prior}, {note}"
    if by_ev or prior:
        return by_ev or prior, f"{note}; nhóm {group}"
    return "hoi", f"nhóm ranh giới {group}, {note}"


def load_review(path: Path = CLAUDE_REVIEW) -> dict:
    """slug → (de_xuat, lop_hoi). Một slug chỉ được nằm ở một dòng."""
    out = {}
    if not Path(path).exists():
        return out
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].split()
        if not line:
            continue
        head, slugs = line[0], line[1:]
        typ, _, lop = head.partition(":")
        typ = {"con": "concept"}.get(typ, typ)
        if typ not in (*TYPES, "hoi") or (typ == "hoi") != bool(lop):
            raise ValueError(f"{path.name}:{i}: nhãn lạ {head!r}")
        for s in slugs:
            if s in out:
                raise ValueError(f"{path.name}:{i}: {s} đã có ở dòng trước")
            out[s] = (typ, lop or None)
    return out


def build_items(d: dict, js: pd.DataFrame, ev: dict, min_df: int, review: dict | None = None) -> list:
    df = js.groupby("slug")["job_id_global"].nunique()
    items = []
    for s in d["skills"]:
        if s["kind"] != "technical" or df.get(s["slug"], 0) < min_df:
            continue
        e = ev.get(s["slug"], {})
        de_xuat, ly_do = propose(s["group"], e)
        lop_hoi = None
        if review and s["slug"] in review:
            new, lop_hoi = review[s["slug"]]
            if new != de_xuat or lop_hoi:
                ly_do = f"Claude đọc lại: {new}{' (' + lop_hoi + ')' if lop_hoi else ''}; luật: {de_xuat}; {ly_do}"
            de_xuat = new
        items.append({"slug": s["slug"], "name": s["name"], "group": s["group"], "df": int(df[s["slug"]]),
                      "examples": s.get("examples", [])[:2],
                      "ext": {"n": e.get("n", 0), "tech_stack": e.get("tech_stack", 0), "keywords": e.get("keywords", 0)},
                      "de_xuat": de_xuat, "lop_hoi": lop_hoi, "ly_do": ly_do, "quyet_dinh": None})
    return sorted(items, key=lambda x: (-x["df"], x["slug"]))


def render_page(batches: list) -> str:
    """Trang duyệt: câu hỏi theo lớp, rồi từng lô (bấm để mở). batches: [(tên, doc)] đọc từ đĩa."""
    import html as H
    import _viz_html as V
    e = H.escape
    items = [(n, i) for n, d in batches for i in d["items"]]
    cnt = Counter(i["de_xuat"] for _, i in items)
    changed = sum(i["ly_do"].startswith("Claude") for _, i in items)
    n_ext = batches[0][1]["_meta"].get("n_ext_jobs", 0) if batches else 0

    def ext(i):
        x = i["ext"]
        return f"{x['tech_stack']}/{x['keywords']}" if x["tech_stack"] + x["keywords"] else "–"

    q_blocks = []
    for lop, note in CLASS_NOTE.items():
        rows = [i for _, i in items if i["de_xuat"] == "hoi" and i["lop_hoi"] == lop]
        q_blocks.append(f"<h3>{e(lop)} ({len(rows)})</h3><p class='note'>{e(note)}</p><p>"
                        + ", ".join(f"{e(i['name'])} <span class='note'>({i['df']})</span>" for i in rows) + "</p>")
    b_blocks = []
    for name, d in batches:
        appr = d["_meta"].get("approved")
        rows = "".join(
            ("<tr style='font-weight:600'>" if i['ly_do'].startswith('Claude') else "<tr>") + f"<td>{e(i['name'])}<br>"
            f"<code>{e(i['slug'])}</code></td><td>{e(i['group'])}</td><td class='n'>{i['df']}</td><td class='n'>{ext(i)}</td>"
            f"<td>{e(i['quyet_dinh'] or i['de_xuat'])}{(' · ' + e(i['lop_hoi'])) if i['lop_hoi'] else ''}</td>"
            f"<td class='note'>{e(i['ly_do'])}</td></tr>" for i in d["items"])
        b_blocks.append(f"<details><summary><b>{e(name)}</b> · dòng {e(d['_meta']['rows'])} · "
                        f"{'đã duyệt' if appr else 'chờ duyệt'}</summary><div class='scroll'><table><thead><tr><th>Kỹ năng</th>"
                        f"<th>Nhóm</th><th>DF</th><th>Ngoài ts/kw</th><th>Nhãn</th><th>Lý do</th></tr></thead>"
                        f"<tbody>{rows}</tbody></table></div></details>")
    top = {t: ", ".join([e(i["name"]) for _, i in items if i["de_xuat"] == t][:40]) for t in TYPES}
    body = f"""<h1>Nhãn tool / concept cho skills_v2 (K8.17)</h1>
<p class="sub">Kỹ năng kỹ thuật có DF ≥ 5 trên bảng 04, sắp DF giảm dần, lô 150. <b>tool</b> = sản phẩm, ngôn ngữ, framework,
nền tảng, dịch vụ có tên riêng, học và dùng được trực tiếp; <b>concept</b> = lĩnh vực, phương pháp, kiến thức chung, hoạt động.
Chỉ <b>tool</b> vào K-tool (docs/target/06_yeu_cau_du_lieu.md).</p>
<div class="tiles">{V.tile(len(items), 'kỹ năng')}{V.tile(cnt['tool'], 'tool')}{V.tile(cnt['concept'], 'concept')}
{V.tile(cnt['hoi'], 'cần người dùng chọn')}{V.tile(changed, 'Claude đổi nhãn hoặc xếp lớp')}{V.tile(n_ext, 'tin trùng với dữ liệu ngoài')}</div>
<h2>1. Câu hỏi theo lớp</h2>
<p class="note">Mỗi lớp trả lời một lần (tool hoặc concept), ghi vào <code>_meta.approved.lop_hoi</code> của lô.</p>
{''.join(q_blocks)}
<h2>2. Top 40 theo DF</h2><p><b>tool:</b> {top['tool']}</p><p><b>concept:</b> {top['concept']}</p>
<h2>3. Từng lô (bấm để mở)</h2>
<p class="note">Cột "Ngoài ts/kw": trên các tin trùng URL và tiêu đề với dữ liệu ngoài (LLM sinh, chỉ để đối chiếu), số lần
kỹ năng nằm trong <code>tech_stack</code> / <code>keywords</code> của họ. Dòng chữ đậm: Claude đọc lại và đổi so với luật.</p>
{''.join(b_blocks)}"""
    nav = V.nav([("skills_v2", "Từ điển kỹ năng v2"), ("skill_types", "Nhãn tool / concept")], "skill_types")
    return V.page("Nhãn tool / concept", nav, body, "Sinh bằng scripts/propose_skill_types.py từ các lô types_t*.json trên máy.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-df", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=150)
    ap.add_argument("--check", action="store_true", help="chỉ in số, không ghi lô")
    a = ap.parse_args(argv)
    d = json.loads(DICT.read_text(encoding="utf-8"))
    js = pd.read_parquet(JOB_SKILLS, columns=["job_id_global", "slug"])
    silver = pd.read_parquet(SILVER, columns=["job_id", "source", "url", "title"])
    ev, n_matched = evidence(d, js, silver, X.load_ext())
    review = load_review()
    unknown = sorted(set(review) - {s["slug"] for s in d["skills"]})
    if unknown:
        raise SystemExit(f"{CLAUDE_REVIEW.name}: slug không có trong skills_v2: {unknown}")
    items = build_items(d, js, ev, a.min_df, review)
    print(f"tin trùng với dữ liệu ngoài: {n_matched}; kỹ năng kỹ thuật DF ≥ {a.min_df}: {len(items)}; "
          f"đề xuất {dict(Counter(i['de_xuat'] for i in items))}; "
          f"hỏi theo lớp {dict(Counter(i['lop_hoi'] or '-' for i in items if i['de_xuat'] == 'hoi'))}")
    if a.check:
        return 0
    today = dt.date.today().isoformat()
    written = skipped = 0
    for b in range(0, len(items), a.batch_size):
        name = f"t{b // a.batch_size + 1:02d}"
        path = DEC_DIR / f"types_{name}.json"
        if path.exists():
            skipped += 1
            continue
        doc = {"_meta": {"batch": name, "rule": "K8.17 (docs/spec/processing/08_skills.md)", "generated": today,
                         "min_df": a.min_df, "rows": f"{b + 1}-{min(b + a.batch_size, len(items))}",
                         "n_ext_jobs": n_matched, "approved": None},
               "items": items[b:b + a.batch_size]}
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        written += 1
    print(f"ghi {written} lô, bỏ qua {skipped} lô đã có ở {DEC_DIR.relative_to(ROOT)}")
    batches = [(p.stem, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(DEC_DIR.glob("types_t*.json"))]
    PAGE.write_text(render_page(batches), encoding="utf-8")
    print("ghi", PAGE.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
