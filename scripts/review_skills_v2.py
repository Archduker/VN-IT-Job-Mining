#!/usr/bin/env python3
"""Đo từ điển kỹ năng v2 trên bảng 02 và sinh trang duyệt (K8.14; chỉ đọc, không gọi mạng).

Đọc `processing/dictionaries/skills_v2.json` (kể cả bản chưa duyệt) và `data/preprocessing/02_integration/all.parquet`.
Dựng matcher đúng như bước 08 sẽ dùng (K8.15): alias dài khớp trên văn bản fold theo nguyên từ, alias ngắn khớp phân
biệt hoa thường trên văn bản gốc, cụm `not_skill` loại `degree` làm cụm chặn (khớp dài nhất thắng rồi bị bỏ).
Quét mục yêu cầu + mô tả của từng tin, đếm DF theo kỹ năng và theo alias, lấy 2 câu ví dụ (seed 42), rồi ghi:

- `<out-json>` (mặc định `data/processing/skill_candidates/skills_v2_measure.json`): số đo;
- `docs/presentation/processing_steps/skills_v2.html`: trang duyệt.

    python scripts/review_skills_v2.py [--input ...] [--out-json ...] [--out-html ...]
"""
import argparse
import collections
import html
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import _viz_html as V  # noqa: E402
from processing.extraction.skills import BLOCK, matcher_from_v2  # noqa: E402

DICT = ROOT / "processing" / "dictionaries" / "skills_v2.json"
SEED = 42

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--input", default=str(ROOT / "data" / "preprocessing" / "02_integration" / "all.parquet"))
ap.add_argument("--out-json", default=str(ROOT / "data" / "processing" / "skill_candidates" / "skills_v2_measure.json"))
ap.add_argument("--out-html", default=str(ROOT / "docs" / "presentation" / "processing_steps" / "skills_v2.html"))


def build_matcher(d):
    return matcher_from_v2(d)  # đúng matcher của bước 08 (K8.15), không kiểm approved để đo được bản nháp


def sentences(text):
    for line in re.split(r"[\n\r]+|(?<=[.;!?])\s+", text or ""):
        line = line.strip(" -•*\t")
        if line:
            yield line


def measure(d, df):
    m = build_matcher(d)
    sk_df, alias_df = collections.Counter(), collections.defaultdict(collections.Counter)
    by_src = collections.defaultdict(collections.Counter)
    pools = collections.defaultdict(list)
    kind = {s["slug"]: s["kind"] for s in d["skills"]}
    n_with = collections.Counter()
    n_src = collections.Counter()
    rng = random.Random(SEED)
    for rec in df[["source_platform", "raw_requirements_text", "raw_description_text"]].itertuples(index=False):
        src = rec.source_platform
        n_src[src] += 1
        seen, seen_alias = set(), set()
        for field in (rec.raw_requirements_text, rec.raw_description_text):
            for sent in sentences(unicodedata.normalize("NFC", field or "")):
                for h in m.find(sent):
                    if h.slug == BLOCK:
                        continue
                    form = sent[h.start:h.end]
                    if h.slug not in seen:
                        pool = pools[h.slug]  # reservoir 2 câu
                        k = sk_df[h.slug]
                        item = (src, sent[:240], form)
                        if len(pool) < 2:
                            pool.append(item)
                        elif rng.random() < 2 / (k + 1):
                            pool[rng.randrange(2)] = item
                        sk_df[h.slug] += 1
                        by_src[h.slug][src] += 1
                        seen.add(h.slug)
                    key = (h.slug, form.lower())
                    if key not in seen_alias:
                        alias_df[h.slug][form.lower()] += 1
                        seen_alias.add(key)
        kinds = {kind[s] for s in seen}
        n_with["any"] += bool(seen)
        n_with["technical"] += "technical" in kinds
        n_with[f"src_none:{src}"] += not any(kind[s] == "technical" for s in seen)
    return dict(n_jobs=len(df), n_src=dict(n_src), sk_df=dict(sk_df), by_src={k: dict(v) for k, v in by_src.items()},
                alias_df={k: dict(v.most_common(5)) for k, v in alias_df.items()}, examples=dict(pools),
                n_with=dict(n_with), conflicts={k: v for k, v in m.conflicts.items() if k})


def main():
    a = ap.parse_args()
    d = json.loads(DICT.read_text(encoding="utf-8"))
    df = pd.read_parquet(a.input)
    M = measure(d, df)
    Path(a.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out_json).write_text(json.dumps({k: v for k, v in M.items() if k != "examples"}, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    Path(a.out_html).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out_html).write_text(render(d, M), encoding="utf-8")
    print("ghi", a.out_json, "và", a.out_html)


e = html.escape


def hl(sent, form):
    i = sent.find(form)
    if i < 0:
        return e(sent)
    return e(sent[:i]) + "<mark>" + e(form) + "</mark>" + e(sent[i + len(form):])


def render(d, M):
    meta, skills, ns = d["_meta"], d["skills"], d["not_skill"]
    by_slug = {s["slug"]: s for s in skills}
    sk_df, N = M["sk_df"], M["n_jobs"]
    groups = meta["groups"]
    pct = lambda x: f"{100 * x / N:.1f}%"
    zero = [s for s in skills if not sk_df.get(s["slug"])]
    nw = M["n_with"]

    gstat = collections.defaultdict(lambda: [0, 0])
    for s in skills:
        gstat[s["group"]][0] += 1
        gstat[s["group"]][1] += sk_df.get(s["slug"], 0)
    group_rows = "".join(
        f"<tr><td>{e(groups[g])}</td><td><code>{g}</code></td><td class='n'>{gstat[g][0]}</td><td class='n'>{V.vn(gstat[g][1])}</td></tr>"
        for g in sorted(groups, key=lambda g: -gstat[g][1]))

    src_rows = "".join(
        f"<tr><td>{e(s)}</td><td class='n'>{V.vn(n)}</td><td class='n'>{V.vn(nw.get('src_none:' + s, 0))}</td>"
        f"<td class='n'>{100 * nw.get('src_none:' + s, 0) / n:.1f}%</td></tr>" for s, n in sorted(M["n_src"].items()))

    def ex_html(slug, n=2):
        return "".join(f"<div class='ex'><span class='src'>{e(src)}</span> {hl(sent, form)}</div>"
                       for src, sent, form in M["examples"].get(slug, [])[:n])

    ask_rows = []
    for q in d["can_hoi"]:
        dec = q["decision"]
        slug = dec.split(":", 1)[1] if dec.startswith(("skill:", "alias:")) else None
        now = f"{V.vn(sk_df.get(slug, 0))} tin" if slug else "không khớp"
        ask_rows.append(f"<tr><td><b>{e(q['display'])}</b><br><span class='note'>DF ứng viên {q['df']}</span></td>"
                        f"<td>{e(q['note'])}</td><td><code>{e(dec)}</code><br><span class='note'>đo lại: {now}</span></td>"
                        f"<td>{ex_html(slug, 1) if slug else ''}</td></tr>")

    top_rows = "".join(
        f"<tr><td>{i}</td><td>{e(by_slug[s]['name'])}</td><td><code>{s}</code></td><td>{e(by_slug[s]['kind'])}</td>"
        f"<td class='n'>{V.vn(n)}</td><td class='n'>{pct(n)}</td></tr>"
        for i, (s, n) in enumerate(sorted(sk_df.items(), key=lambda x: -x[1])[:60], 1))

    def skill_row(s):
        slug = s["slug"]
        al = M["alias_df"].get(slug, {})
        al_txt = ", ".join(f"{e(k)} ({v})" for k, v in al.items()) or "—"
        par = f"<code>{s['parent']}</code>" if s["parent"] else ""
        short = ", ".join(f"<code>{e(x)}</code>" for x in s["short_aliases"])
        n_alias = len(s["aliases"])
        return (f"<tr><td><b>{e(s['name'])}</b><br><code>{slug}</code> {par}<br><span class='note'>{s['kind']}"
                f" · {n_alias} alias{(' · ngắn: ' + short) if short else ''}</span></td>"
                f"<td class='n'>{V.vn(sk_df.get(slug, 0))}<br><span class='note'>ứng viên {s['df']}</span></td>"
                f"<td><span class='note'>dạng khớp nhiều nhất: {al_txt}</span>{ex_html(slug)}</td></tr>")

    group_blocks = []
    for g in sorted(groups, key=lambda g: -gstat[g][1]):
        rows = sorted((s for s in skills if s["group"] == g), key=lambda s: -sk_df.get(s["slug"], 0))
        if not rows:
            continue
        group_blocks.append(
            f"<details><summary><b>{e(groups[g])}</b> · {len(rows)} kỹ năng · {V.vn(gstat[g][1])} lượt tin</summary>"
            f"<div class='scroll'><table class='sk'><tr><th>Kỹ năng</th><th>Số tin</th><th>Ví dụ thật (bảng 02)</th></tr>"
            + "".join(skill_row(s) for s in rows) + "</table></div></details>")

    reasons = meta["not_skill_reasons"]
    ns_by = collections.defaultdict(list)
    for n in ns:
        ns_by[n["reason"]].append(n)
    ns_blocks = "".join(
        f"<details><summary><b>{e(reasons[r])}</b> (<code>{r}</code>) · {len(v)} mục</summary><p>"
        + ", ".join(f"{e(n['display'])} <span class='note'>({n['df']})</span>" for n in sorted(v, key=lambda n: -n["df"])[:150])
        + (f" <span class='note'>… và {len(v) - 150} mục khác</span>" if len(v) > 150 else "") + "</p></details>"
        for r, v in sorted(ns_by.items(), key=lambda x: -len(x[1])))

    zero_txt = ", ".join(f"{e(s['name'])} <span class='note'>(<code>{s['slug']}</code>)</span>" for s in
                         sorted(zero, key=lambda s: s["slug"]))
    kinds = collections.Counter(s["kind"] for s in skills)

    body = f"""<style>td{{overflow-wrap:anywhere;vertical-align:top}}td.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.ex{{font-size:13px;margin:4px 0;color:var(--text-2)}}.ex .src{{color:var(--muted);font-size:12px}}
mark{{background:color-mix(in srgb,var(--series-1) 30%,transparent);color:inherit;border-radius:3px;padding:0 2px}}
details{{margin:8px 0;border:1px solid var(--border);border-radius:8px;padding:8px 12px}}summary{{cursor:pointer}}
table.sk td:first-child{{width:30%}}table.sk td:nth-child(2){{width:80px}}</style>
<h1>Từ điển kỹ năng v2</h1>
<p class="sub">Bước 08 (K8.11–K8.16). Claude đọc hết {V.vn(meta['n_candidates'])} ứng viên DF ≥ 2 (<code>scripts/mine_skill_candidates.py</code>)
theo 36 lô, quyết định ghi ở <code>processing/dictionaries/skills_v2_decisions/</code>, build ra <code>processing/dictionaries/skills_v2.json</code>
(<code>approved: {str(meta['approved']).lower()}</code>). <b>{"Người dùng đã duyệt " + e(meta["approval"]["date"]) + "." if meta.get("approved") else "Chờ người dùng duyệt."}</b>
Số tin bên dưới đo lại bằng chính alias trong từ điển trên <code>data/preprocessing/02_integration/all.parquet</code>
({V.vn(N)} tin, mục yêu cầu + mô tả, văn bản gốc), khớp như bước 08 sẽ chạy: alias dài trên văn bản fold theo nguyên từ,
alias ngắn phân biệt hoa thường, cụm bằng cấp (not_skill <code>degree</code>) chặn khớp lồng bên trong (ví dụ "học máy" trong "Khoa học máy tính"). Thêm hai luật đề xuất cho K8.15: chỗ khớp có dấu phải đúng dấu của alias ("công nghệ" không khớp "nghe", "bản về" không khớp "bản vẽ"); alias ngắn đứng trước "-" + chữ cái bị bỏ ("Go-live").</p>
<div class="tiles">{V.tile(len(skills), 'kỹ năng')}{V.tile(len(ns), 'mục không phải kỹ năng')}
{V.tile(len(d['can_hoi']), 'câu hỏi cho người dùng')}{V.tile(pct(nw.get('technical', 0)), 'tin có ≥ 1 kỹ năng kỹ thuật')}
{V.tile(len(zero), 'kỹ năng không khớp tin nào')}</div>
<p class="note">Theo loại: {kinds['technical']} kỹ thuật, {kinds['soft']} kỹ năng mềm, {kinds['language']} ngoại ngữ.
Cột "ứng viên" là DF của cụm gốc lúc gom; cột "số tin" là DF đo lại sau khi gộp alias.</p>

<h2>1. Câu hỏi cần người dùng chốt ({len(d['can_hoi'])})</h2>
<p class="note">Claude đã chọn tạm (cột "đang xếp"); người dùng đồng ý hoặc sửa.</p>
<div class="scroll"><table><tr><th>Cụm</th><th>Vấn đề</th><th>Đang xếp</th><th>Ví dụ</th></tr>{''.join(ask_rows)}</table></div>

<h2>2. Theo nhóm</h2>
<div class="scroll"><table><tr><th>Nhóm</th><th>Mã</th><th>Kỹ năng</th><th>Lượt tin</th></tr>{group_rows}</table></div>

<h2>3. Tin không có kỹ năng kỹ thuật nào, theo sàn</h2>
<p class="note">Trước: bước 08 với taxonomy 230 có 7,8% tin không kỹ năng (đo trên bảng 04). Ở đây đo trên bảng 02, chưa lọc IT nên còn tin ngoài IT.</p>
<div class="scroll"><table><tr><th>Sàn</th><th>Tin</th><th>Không kỹ năng kỹ thuật</th><th>Tỷ lệ</th></tr>{src_rows}</table></div>

<h2>4. 60 kỹ năng nhiều tin nhất</h2>
<div class="scroll"><table><tr><th>#</th><th>Kỹ năng</th><th>Mã</th><th>Loại</th><th>Số tin</th><th>% tin</th></tr>{top_rows}</table></div>

<h2>5. Toàn bộ kỹ năng theo nhóm (bấm để mở)</h2>
<p class="note">Mỗi kỹ năng: tên, mã, cha, số tin đo lại, 5 dạng khớp nhiều nhất, 2 câu ví dụ ngẫu nhiên (seed {SEED}). Kiểm nhanh: dạng khớp lạ hoặc ví dụ sai nghĩa là alias gây nhiễu.</p>
{''.join(group_blocks)}

<h2>6. Kỹ năng không khớp tin nào ({len(zero)})</h2>
<p class="note">Thường là kỹ năng chỉ có alias ngắn viết hoa khác văn bản, hoặc ứng viên chỉ đến từ tag của sàn (nguồn a, bước 08 khớp tag riêng). Không ảnh hưởng tin khác.</p>
<p>{zero_txt}</p>

<h2>7. Không phải kỹ năng (theo lý do)</h2>
<p class="note">Bước 08 bỏ tag của sàn nằm trong danh sách này; mục <code>degree</code> dùng làm cụm chặn.</p>
{ns_blocks}
"""
    nav = V.nav([("../preprocessing_steps/index", "Pre-processing"), ("skills_v2", "Từ điển kỹ năng v2" + ("" if d["_meta"].get("approved") else " (nháp)"))], "skills_v2")
    return V.page("Từ điển kỹ năng v2", nav, body,
                  "Sinh bằng scripts/review_skills_v2.py từ skills_v2.json và bảng 02 trên máy.")


if __name__ == "__main__":
    main()
