#!/usr/bin/env python3
"""Đo từ điển trích xuất JD trên bảng 03 và sinh trang duyệt (chỉ đọc, không gọi mạng).

Đọc `preprocessing/dictionaries/jd_extraction.json` và `data/preprocessing/03_transformation/all.parquet`,
áp các mẫu work_mode, employment_type, experience theo đúng thứ tự ưu tiên trong từ điển, đếm số tin theo luật
và theo nguồn, lấy ví dụ ngẫu nhiên (seed 7), rồi ghi:

- `<out-json>` (mặc định `data/preprocessing/jd_phrases/jd_dictionary_measure.json`): số đo và ví dụ;
- `docs/presentation/preprocessing_steps/jd_dictionary.html`: trang duyệt.

    python scripts/review_jd_dictionary.py [--out-json ...] [--out-html ...]

Logic trích xuất lấy từ `preprocessing/transformation/jd_extractor.py` (cùng code với bước 03 T9).
"""
import argparse
import collections
import html
import json
import random

import sys

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
sys.path.insert(0, str(ROOT))
from preprocessing.transformation import jd_extractor as J  # noqa: E402

R = J.load_rules()  # dừng nếu từ điển chưa duyệt
D = json.loads(J.DICT_PATH.read_text(encoding="utf-8"))
df = pd.read_parquet(ARGS.input)

stats = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
examples = collections.defaultdict(list)
for rec in df.to_dict(orient="records"):
    src = rec["source_platform"]
    title = J.norm(rec.get("job_title_clean") or rec.get("job_title"))
    body = list(J.sentences(rec.get("description_clean"))) + list(J.sentences(rec.get("requirements_clean")))
    t9 = J.extract(rec, R)
    # work mode
    h = J.hits(R.work_mode, title, body)
    for _, pid, _, ln in h:
        stats["wm_rule"][src][pid] += 1
        examples[pid].append((src, title[:80], ln[:220]))
    wr, wj = t9["work_mode_raw"], t9["work_mode_jd"]
    stats["wm_raw"][src][str(wr)] += 1
    stats["wm_jd"][src][str(wj)] += 1
    if t9["work_mode_conflict"]:
        stats["wm_conflict"][src][f"{wr}->{wj}"] += 1
        examples["WM_CONFLICT"].append((src, title[:80], f"raw={rec.get('raw_work_mode')} | jd={wj} | "
                                        + "; ".join(f"{pid}:{ln[:120]}" for _, pid, _, ln in h)))
    # cùng thứ tự với N14 mới của bước 04, trước luật suy từ địa điểm
    final = (wj if t9["work_mode_conflict"] and t9["work_mode_jd_strong"] else None) or wr or wj
    stats["wm_final_pre_default"][src][str(final)] += 1
    # employment
    h2 = J.hits(R.employment_type, title, body)
    for _, pid, _, ln in h2:
        stats["et_rule"][src][pid] += 1
        examples[pid].append((src, title[:80], ln[:220]))
    er, ej = t9["employment_type_raw"], t9["employment_type_jd"]
    stats["et_raw"][src][str(er)] += 1
    if t9["employment_type_conflict"]:
        stats["et_conflict"][src][f"{er}->{ej}"] += 1
        examples["ET_CONFLICT"].append((src, title[:80], f"raw={rec.get('raw_employment_type')} | "
                                        + "; ".join(f"{pid}:{ln[:120]}" for v, pid, _, ln in h2 if v == ej)))
    stats["et_final"][src][str(er or ej)] += 1
    # experience
    kind, lo = t9["exp_jd_kind"], t9["exp_min_years_jd"]
    exp_raw = rec.get("exp_min_years")
    has_raw = exp_raw is not None and pd.notna(exp_raw)
    if kind:
        stats["exp_jd"][src]["found_" + kind] += 1
        shown = f"{lo}..{t9['exp_max_years_jd']} «{t9['exp_jd_text']}»"
        if not has_raw:
            stats["exp_fill"][src][kind] += 1
            examples["EXP_FILL_" + kind].append((src, title[:80], shown))
        elif abs(lo - exp_raw) >= 1:
            stats["exp_diff"][src]["diff>=1"] += 1
            examples["EXP_DIFF"].append((src, title[:80], f"raw={rec.get('raw_experience_text')}→{exp_raw} | jd={shown}"))
        else:
            stats["exp_diff"][src]["agree"] += 1
    stats["exp_raw"][src]["has" if has_raw else "missing"] += 1
    if src == "itviec":
        fs = kind or ("itviec_jsonld" if has_raw else "none")
    else:
        fs = "raw" if has_raw else (kind or "none")
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
