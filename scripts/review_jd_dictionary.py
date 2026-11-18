#!/usr/bin/env python3
"""Đo từ điển trích xuất JD trên bảng 03 và sinh trang duyệt (chỉ đọc, không gọi mạng).

Đọc `preprocessing/dictionaries/jd_extraction.json` và `data/preprocessing/03_transformation/all.parquet`,
áp các mẫu work_mode, employment_type, experience theo đúng thứ tự ưu tiên trong từ điển, đếm số tin theo luật
và theo nguồn, lấy ví dụ ngẫu nhiên (seed 7), rồi ghi:

- `<out-json>` (mặc định `data/preprocessing/jd_phrases/jd_dictionary_measure.json`): số đo và ví dụ;
- `docs/presentation/preprocessing_steps/jd_dictionary.html`: trang duyệt.

    python scripts/review_jd_dictionary.py [--out-json ...] [--out-html ...]

Đây là bản đo để duyệt từ điển; luật chính thức chạy trong bước 03 (`preprocessing/transformation/`).
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
sys.path.insert(0, str(ROOT / "scripts"))
import _viz_html as V  # noqa: E402

_ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
_ap.add_argument("--input", default=str(ROOT / "data" / "preprocessing" / "03_transformation" / "all.parquet"))
_ap.add_argument("--out-json", default=str(ROOT / "data" / "preprocessing" / "jd_phrases" / "jd_dictionary_measure.json"))
_ap.add_argument("--out-html", default=str(ROOT / "docs" / "presentation" / "preprocessing_steps" / "jd_dictionary.html"))
ARGS = _ap.parse_args()
D = json.load(open(ROOT / "preprocessing" / "dictionaries" / "jd_extraction.json", encoding="utf-8"))
df = pd.read_parquet(ARGS.input)
F = re.IGNORECASE


def nfc(s):
    return " ".join(unicodedata.normalize("NFC", s).split()) if isinstance(s, str) else ""


def lines(t):
    for ln in re.split(r"[\n\r]+|(?<=[.;!?])\s+(?=[A-ZĐÀ-Ỵ])", t or ""):
        ln = " ".join(ln.split())
        if ln:
            yield ln


def comp_noise(lst):
    return re.compile("|".join(f"(?:{x})" for x in lst), F) if lst else None


def run_topic(name, rec, title, body_lines, glints_head):
    T = D[name]
    noise = {k: comp_noise(v) for k, v in T["jd_noise"].items() if not k.startswith("_")}
    hits = []
    for val, pats in T["jd_patterns"].items():
        nz = noise.get(val)
        for p in pats:
            rx = re.compile(p["re"], F)
            srcs = {"title": [title], "body": body_lines, "title+body": [title] + body_lines,
                    "glints_header": [glints_head]}[p["where"]]
            for ln in srcs:
                if not ln:
                    continue
                l2 = nz.sub(" ", ln) if nz else ln
                m = rx.search(l2)
                if m:
                    hits.append((val, p["id"], ln[:220], "title" if ln is title else "body"))
                    break
    return hits


def resolve_wm(vals):
    s = set(vals)
    if not s:
        return None
    if "hybrid" in s or {"remote", "onsite"} <= s:
        return "hybrid"
    return next(iter(s))


def wm_raw(src, raw_wm, raw_et):
    m = D["work_mode"]["raw_map"]
    if isinstance(raw_wm, str) and raw_wm:
        parts = [m.get(p.strip().lower()) for p in re.split(r",\s*(?=[A-ZKL])", raw_wm)]
        return resolve_wm([p for p in parts if p])
    et = (raw_et or "").lower()
    if src == "jobsgo" and "remote" in et:
        return "remote"
    if src == "topcv" and et == "làm tại nhà":
        return "remote"
    if src == "vietnamworks" and et == "7":
        return "remote"
    return None


def et_raw(src, raw_et):
    if not isinstance(raw_et, str) or not raw_et:
        return None
    m = D["employment_type"]["raw_map"]
    for p in [x.strip().lower() for x in raw_et.split(",")]:
        v = m.get(p)
        if isinstance(v, str) and not v.startswith("->"):
            return v
    return None


E = D["experience"]["grammar"]
EXP = re.compile(r"(?:(dưới|under|less than)\s*)?" + E["prefix"] + r"\s*" + E["number"] + r"\s*" + E["unit"], F)
CTX = re.compile(E["context"], F)
NOISE = re.compile("|".join(f"(?:{x})" for x in D["experience"]["noise"]), F)
ZERO = re.compile("|".join(f"(?:{x})" for x in D["experience"]["zero_phrases"]), F)
WORDS6 = 6


def exp_from(lines_):
    for ln in lines_:
        for m in EXP.finditer(ln):
            before = " ".join(ln[:m.start()].split()[-WORDS6:])
            after = " ".join(ln[m.end():].split()[:WORDS6])
            win = before + " " + m.group(0) + " " + after
            if not CTX.search(win) or NOISE.search(win):
                continue
            a = float(m.group(2).replace(",", "."))
            b = float(m.group(3).replace(",", ".")) if m.group(3) else None
            u = m.group(4).lower()
            k = 1 / 12 if u.startswith(("tháng", "month")) else 1
            if m.group(1):
                a, b = 0, a
            lo, hi = a * k, (b * k if b is not None else None)
            if lo > 20:
                continue
            return round(lo, 2), hi, m.group(0), ln[:220], "jd"
        if ZERO.search(ln) and not NOISE.search(ln):
            return 0.0, None, ZERO.search(ln).group(0), ln[:220], "jd_zero"
    return None


stats = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
examples = collections.defaultdict(list)
for r in df.itertuples(index=False):
    src = r.source_platform
    title = nfc(r.job_title_clean or r.job_title)
    desc, req = nfc(r.description_clean), nfc(r.requirements_clean)
    body = list(lines(r.description_clean)) + list(lines(r.requirements_clean))
    body = [nfc(x) for x in body]
    gh = desc[:80] if src == "glints" else ""
    # work mode
    h = run_topic("work_mode", r, title, body, gh)
    for v, pid, ln, w in h:
        stats["wm_rule"][src][pid] += 1
        examples[pid].append((src, title[:80], ln))
    title_vals = [v for v, pid, ln, w in h if w == "title"]
    wj = resolve_wm(title_vals) or resolve_wm([v for v, *_ in h])
    wr = wm_raw(src, r.raw_work_mode, r.raw_employment_type)
    stats["wm_raw"][src][str(wr)] += 1
    stats["wm_jd"][src][str(wj)] += 1
    if wr and wj and wr != wj:
        stats["wm_conflict"][src][f"{wr}->{wj}"] += 1
        examples["WM_CONFLICT"].append((src, title[:80], f"raw={r.raw_work_mode} | jd={wj} | " + "; ".join(f"{pid}:{ln[:120]}" for v, pid, ln, w in h)))
    strong = [v for v, pid, ln, w in h if w == "title" or pid in ("WH4", "WH5")]
    final = (resolve_wm(strong) if (wr and wj and wr != wj and strong) else None) or wr or wj
    stats["wm_final_pre_default"][src][str(final)] += 1
    # employment
    h2 = run_topic("employment_type", r, title, body, "")
    for v, pid, ln, w in h2:
        stats["et_rule"][src][pid] += 1
        examples[pid].append((src, title[:80], ln))
    order = ["internship", "part_time", "contract", "full_time"]
    ej = next((o for o in order if o in {v for v, *_ in h2}), None)
    er = et_raw(src, r.raw_employment_type)
    stats["et_raw"][src][str(er)] += 1
    if er and ej and er != ej and ej != "full_time":
        stats["et_conflict"][src][f"{er}->{ej}"] += 1
        examples["ET_CONFLICT"].append((src, title[:80], f"raw={r.raw_employment_type} | " + "; ".join(f"{pid}:{ln[:120]}" for v, pid, ln, w in h2 if v == ej)))
    stats["et_final"][src][str(er or ej)] += 1
    # experience
    ex = exp_from([nfc(x) for x in lines(r.requirements_clean)] + [nfc(x) for x in lines(r.description_clean)])
    has_raw = pd.notna(r.exp_min_years)
    if ex:
        stats["exp_jd"][src]["found_" + ex[4]] += 1
        if not has_raw:
            stats["exp_fill"][src][ex[4]] += 1
            examples["EXP_FILL_" + ex[4]].append((src, title[:80], f"{ex[0]}..{ex[1]} «{ex[2]}» {ex[3]}"))
        elif abs(ex[0] - r.exp_min_years) >= 1:
            stats["exp_diff"][src]["diff>=1"] += 1
            examples["EXP_DIFF"].append((src, title[:80], f"raw={r.raw_experience_text}→{r.exp_min_years} | jd={ex[0]} «{ex[2]}» {ex[3]}"))
        else:
            stats["exp_diff"][src]["agree"] += 1
    stats["exp_raw"][src]["has" if has_raw else "missing"] += 1
    if src == "itviec":
        fs = ex[4] if ex else ("itviec_jsonld" if has_raw else "none")
    else:
        fs = "raw" if has_raw else (ex[4] if ex else "none")
    stats["exp_final_source"][src][fs] += 1

random.seed(7)
ex_out = {k: random.sample(v, min(len(v), 25)) for k, v in examples.items()}
cnt = {k: len(v) for k, v in examples.items()}
Path(ARGS.out_json).parent.mkdir(parents=True, exist_ok=True)
json.dump({"stats": {k: {s: dict(c) for s, c in v.items()} for k, v in stats.items()}, "examples": ex_out, "example_counts": cnt},
          open(Path(ARGS.out_json), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k in ["wm_raw", "wm_jd", "wm_conflict", "wm_final_pre_default", "et_raw", "et_conflict", "et_final", "exp_raw", "exp_jd", "exp_fill", "exp_diff", "exp_final_source"]:
    print("==", k)
    for s, c in sorted(stats[k].items()):
        print("  ", s, dict(c))
print("rule hits:", {k: v for k, v in cnt.items()})


# ---- trang duyệt ----
M = json.load(open(ARGS.out_json, encoding="utf-8"))
S, EX, EC = M["stats"], M["examples"], M["example_counts"]
SRC = ["careerviet", "glints", "itviec", "jobsgo", "topcv", "topdev", "vieclam24h", "vietnamworks"]
e = html.escape


def src_table(stat, keys, labels=None, pct=True):
    labels = labels or keys
    h = "<tr><th>Nguồn</th>" + "".join(f'<th class="n">{e(l)}</th>' for l in labels) + '<th class="n">Tổng</th></tr>'
    tot = {k: 0 for k in keys}
    for s in SRC:
        row = S.get(stat, {}).get(s, {})
        n = sum(row.values())
        cells = ""
        for k in keys:
            v = row.get(k, 0)
            tot[k] += v
            cells += f'<td class="n">{V.vn(v)}' + (f' <span class="note">({v / n * 100:.0f}%)</span>' if pct and n else "") + "</td>"
        h += f"<tr><td>{s}</td>{cells}<td class='n'>{V.vn(n)}</td></tr>"
    h += "<tr><th>Tổng</th>" + "".join(f'<th class="n">{V.vn(tot[k])}</th>' for k in keys) + f'<th class="n">{V.vn(sum(tot.values()))}</th></tr>'
    return f'<div class="scroll"><table>{h}</table></div>'


def examples(key, n=25):
    xs = EX.get(key, [])
    if not xs:
        return '<p class="note">Không có ca nào.</p>'
    rows = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td><td class='samp'>{e(c)}</td></tr>" for a, b, c in xs[:n])
    more = f" (hiện {min(n, len(xs))}/{EC.get(key, len(xs))}, chọn ngẫu nhiên)" if EC.get(key, 0) > len(xs[:n]) else ""
    return f'<details><summary>Ví dụ{more}</summary><div class="scroll tbox"><table><tr><th>Nguồn</th><th>Tiêu đề</th><th>Câu khớp</th></tr>{rows}</table></div></details>'


def rule_table(topic, rule_stat):
    rows = ""
    for val, pats in D[topic]["jd_patterns"].items():
        for p in pats:
            per = {s: S.get(rule_stat, {}).get(s, {}).get(p["id"], 0) for s in SRC}
            n = sum(per.values())
            by = ", ".join(f"{s} {v}" for s, v in per.items() if v)
            rows += (f"<tr><td><b>{p['id']}</b></td><td>{val}</td><td>{p['where']}</td><td><code class='samp'>{e(p['re'])}</code></td>"
                     f"<td class='n'>{V.vn(n)}</td><td class='note'>{e(by)}</td></tr>"
                     f"<tr><td></td><td colspan='5'>{examples(p['id'], 30)}</td></tr>")
    return f'<div class="scroll"><table><tr><th>Mã</th><th>Giá trị</th><th>Đọc ở</th><th>Mẫu (regex)</th><th class="n">Số tin</th><th>Theo nguồn</th></tr>{rows}</table></div>'


def kv_table(d, h1="Giá trị nguồn (chữ thường)", h2="Map sang"):
    rows = "".join(f"<tr><td>{e(str(k))}</td><td>{e(str(v))}</td></tr>" for k, v in d.items() if not str(k).startswith("_"))
    return f"<table><tr><th>{h1}</th><th>{h2}</th></tr>{rows}</table>"


def noise_list(d):
    return "".join(f"<p><b>{e(k)}</b>: " + ", ".join(f"<code>{e(x)}</code>" for x in v) + "</p>" for k, v in d.items() if not k.startswith("_"))


wm, et, ex = D["work_mode"], D["employment_type"], D["experience"]
tot = lambda st, k: sum(S.get(st, {}).get(s, {}).get(k, 0) for s in SRC)
n_rows = sum(sum(S["wm_raw"][s].values()) for s in SRC)

body = f"""<style>code{{word-break:break-all}}td{{overflow-wrap:anywhere}}ol{{padding-left:20px}}</style><h1>Từ điển trích xuất JD</h1>
<p class="sub">Bước 03 (T-JD): rút <b>hình thức làm việc</b>, <b>loại hợp đồng</b>, <b>kinh nghiệm tối thiểu</b> từ ô của sàn và từ JD.
Luật if-else + regex, không dùng model. File: <code>preprocessing/dictionaries/jd_extraction.json</code> (<code>approved: {D['_meta']['approved']}</code>, duyệt {D['_meta'].get('approved_date', '—')}).
Mọi số đo trên <code>data/preprocessing/03_transformation/all.parquet</code> ({V.vn(n_rows)} tin).</p>
<div class="tiles">{V.tile(tot('wm_final_pre_default','None'), 'tin chưa có work_mode sau raw + JD')}
{V.tile(EC.get('WM_CONFLICT',0), 'tin raw ≠ JD (work_mode)')}
{V.tile(EC.get('ET_CONFLICT',0), 'tin tiêu đề Intern nhưng raw ghi loại khác')}
{V.tile(EC.get('EXP_FILL_jd',0)+EC.get('EXP_FILL_jd_zero',0), 'tin được điền kinh nghiệm từ JD')}
{V.tile(S['exp_final_source']['itviec'].get('jd',0) + S['exp_final_source']['itviec'].get('jd_zero',0), 'tin itviec lấy kinh nghiệm từ JD thay mức gom')}</div>

<h2>Quyết định của người dùng</h2>
<div class="scroll"><table><tr><th>Câu hỏi</th><th>Quyết định</th><th>Ngày</th></tr>{''.join(f'<tr><td>{e(d["q"])}</td><td>{e(d["a"])}</td><td>{e(d["date"])}</td></tr>' for d in D['decisions'])}</table></div>

<h2>1. Hình thức làm việc (<code>work_mode</code>)</h2>
<p class="note">{e(wm['priority'])}</p>
<div class="grid2">{V.card('1.1 Map giá trị của sàn', e(wm['raw_multi_value_rule']), kv_table(wm['raw_map']) + '<h3 style="margin-top:12px">Ghi ở ô loại hình</h3>' + kv_table(wm['raw_from_employment_type'], 'Nguồn: giá trị', 'Map sang'))}
{V.card('1.2 Trước: chỉ dùng ô của sàn', 'None = sàn không có ô này hoặc để trống.', src_table('wm_raw', ['onsite','hybrid','remote','None']))}</div>
<h2>1.3 Mẫu trong JD</h2><p class="note">{e(wm['jd_resolve'])} {e(wm['jd_noise_rule'])}</p>
{rule_table('work_mode', 'wm_rule')}
<details><summary>Cụm nhiễu (xóa khỏi câu trước khi so mẫu)</summary>{noise_list(wm['jd_noise'])}</details>
<h2>1.4 Sau: ô của sàn + JD (chưa áp mặc định theo địa điểm của bước 04)</h2>
<p class="note">Tin còn None sẽ được bước 04 suy theo địa điểm (luật N14), không suy được thì <code>unknown</code>.</p>
{src_table('wm_final_pre_default', ['onsite','hybrid','remote','None'])}
<h2>1.5 Ca raw ≠ JD ({EC.get('WM_CONFLICT',0)} tin)</h2>
<p class="note">Đọc tay từng ca. Đã chốt: JD thắng khi tín hiệu nằm ở tiêu đề hoặc có số ngày cụ thể (WH4, WH5).</p>
{src_table('wm_conflict', sorted({k for s in S.get('wm_conflict',{}).values() for k in s}), pct=False)}{examples('WM_CONFLICT', 40)}

<h2>2. Loại hợp đồng (<code>employment_type</code>)</h2>
<p class="note">{e(et['_note'])} {e(et['priority'])}</p>
<div class="grid2">{V.card('2.1 Map giá trị của sàn', e(et['raw_multi_value_rule']), kv_table(et['raw_map']))}
{V.card('2.2 Sau map (chỉ ô của sàn)', 'Toàn thời gian chiếm phần lớn ở mọi nguồn có ô này; topdev không có ô.', src_table('et_raw', ['full_time','internship','part_time','contract','None']))}</div>
<h2>2.3 Mẫu trong JD</h2>{rule_table('employment_type', 'et_rule')}
<details><summary>Cụm nhiễu</summary>{noise_list(et['jd_noise'])}</details>
<h2>2.4 Ca raw ≠ JD ({EC.get('ET_CONFLICT',0)} tin)</h2>
<p class="note">Gần hết là tiêu đề "Intern/Thực tập sinh" mà ô của sàn ghi Toàn thời gian (thực tập toàn thời gian). Đã chốt: tiêu đề thắng → internship, gắn cờ.</p>
{src_table('et_conflict', sorted({k for s in S.get('et_conflict',{}).values() for k in s}), pct=False)}{examples('ET_CONFLICT', 40)}

<h2>3. Kinh nghiệm tối thiểu (<code>exp_min_years</code>)</h2>
<p class="note">{e(ex['priority'])}</p>
<div class="grid2">{V.card('3.1 Ngữ pháp', e(ex['grammar']['rule']) + ' ' + e(ex['selection']),
 '<pre>' + e('\n'.join(f'{k}: {v}' for k, v in ex['grammar'].items() if k != 'rule')) + '</pre>'
 + '<p><b>Cụm "0 năm"</b>: ' + ', '.join(f'<code>{e(x)}</code>' for x in ex['zero_phrases']) + '</p>'
 + '<p><b>Nhiễu</b> (cửa sổ quanh con số chứa cụm này thì bỏ): ' + ', '.join(f'<code>{e(x)}</code>' for x in ex['noise']) + '</p>')}
{V.card('3.2 Nguồn của giá trị cuối', 'raw = ô của sàn; jd = cụm số trong JD; jd_zero = cụm "không yêu cầu kinh nghiệm"…; itviec_jsonld = mức gom 10/37/61 tháng; none = vẫn trống.',
 src_table('exp_final_source', ['raw','jd','jd_zero','itviec_jsonld','none']))}</div>
<h2>3.3 Tin được điền từ JD (ô của sàn trống)</h2>{examples('EXP_FILL_jd', 30)}{examples('EXP_FILL_jd_zero', 30)}
<h2>3.4 Ô của sàn ≠ JD (lệch ≥ 1 năm)</h2>
<p class="note">itviec lệch vì ô là mức gom JSON-LD. Các nguồn khác: ô của sàn hay ghi mức trên của khoảng trong JD.</p>
{src_table('exp_diff', ['agree','diff>=1'], ['khớp (<1 năm)','lệch ≥1 năm'])}{examples('EXP_DIFF', 40)}
"""
nav = V.nav([("index", "Tổng hợp"), ("01_clean", "01_clean"), ("01b_deduplication", "01b_deduplication"), ("02_integration", "02_integration"),
             ("03_transformation", "03_transformation"), ("jd_dictionary", "Từ điển JD (nháp)")], "jd_dictionary")
Path(ARGS.out_html).write_text(V.page("Từ điển JD", nav, body, "Sinh bằng scripts/review_jd_dictionary.py từ jd_extraction.json và bảng 03 trên máy."), encoding="utf-8")
print("ghi", ARGS.out_html)
