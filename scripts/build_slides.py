#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh slide thuyết trình "Vấn đề dữ liệu → Pre-processing 5 bước" từ dữ liệu thật.

    python scripts/build_slides.py                 # ghi docs/presentation/slides.html
    python scripts/build_slides.py --save-before <04_all.parquet cũ>   # chụp số "trước sửa review" một lần

Số liệu đọc từ: docs/presentation/data/raw_issues_before.json (compute() của scripts/report_data_issues.py chạy bằng
code trước khi sửa, xem _nguon), compute() chạy lại bằng code hiện tại (số "sau"), reports/preprocessing/<bước>/_all.json,
data/preprocessing/04_normalization/all.parquet, docs/presentation/data/before_review.json.
Không gõ số tay: chạy lại pipeline rồi chạy lại script là slide cập nhật.
Trong slide: ← → chuyển, N mở lời nói + câu hỏi, P in lời nói, F toàn màn hình.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

OUT = ROOT / "docs" / "presentation" / "slides.html"
SCRIPT_MD = ROOT / "docs" / "presentation" / "script.md"
BEFORE = ROOT / "docs" / "presentation" / "data" / "before_review.json"
RAW_BEFORE = ROOT / "docs" / "presentation" / "data" / "raw_issues_before.json"
REPORTS = ROOT / "reports" / "preprocessing"
STEPS = ["01_clean", "02_integration", "03_transformation", "04_normalization", "05_encoding"]
STEP_VI = {"01_clean": "1. Clean", "02_integration": "2. Integration", "03_transformation": "3. Transformation",
           "04_normalization": "4. Normalization", "05_encoding": "5. Encoding"}

# Vấn đề (docs/preprocessing/data_issues_2026-11-03.md) -> luật giải quyết. Mức C, E–I do nhóm đánh giá.
ISSUES = {
    "A1": ("Tin ngoài IT lẫn vào", "Cao"),
    "A2": ("ITviec ngày đăng dạng tương đối", "Cao"),
    "A3": ("TopDev thiếu ngày đăng, kinh nghiệm", "TB"),
    "B": ("Trùng lặp: nhiều version, file batch, cùng tin", "Cao"),
    "C": ("Thiếu trường, khóa hỏng, null trá hình", "TB"),
    "D": ("Lương parse sai", "Cao"),
    "E": ("Địa điểm mỗi nguồn một kiểu", "TB"),
    "F": ("Kinh nghiệm, cấp bậc mỗi nguồn một bộ từ", "TB"),
    "G": ("Kỹ năng lẫn danh mục ngành", "TB"),
    "H": ("Ngày tháng nhiều định dạng", "Thấp"),
    "I": ("Văn bản: HTML, JD ngắn, tiếng Anh, tên công ty", "Thấp"),
}
ISSUE_TO_RULES = {
    "A1": ["C4a", "C4c", "E8"],
    "A2": ["I2"],
    "A3": ["I3"],
    "B": ["C1", "C2", "C6", "C7"],
    "C": ["C3", "I0", "I1", "I5", "T1", "T5", "E5"],
    "D": ["T2", "T2f", "N6a", "N6", "N7", "E6"],
    "E": ["T8", "N1", "E3"],
    "F": ["T4", "N2", "N2b", "E1"],
    "G": ["I4", "T7", "N3", "N4", "E2", "E4"],
    "H": ["T3", "E7"],
    "I": ["C5", "T6", "N5"],
}
# Cách giải viết bằng lời cho người xem; số kết quả = tổng rows_affected của các luật chính.
SOLVE = {
    "A1": ("Luật 2 tầng: từ khóa tiêu đề, rồi nhóm nghề + kỹ năng JD; kiểm bằng nhãn tay, bỏ tin ngoài IT", ["C4c"], "tin ngoài IT bị bỏ"),
    "A2": ("Lấy ngày đăng tuyệt đối có sẵn trong trang", ["I2"], "tin ITviec sửa ngày"),
    "A3": ("Đọc thêm trường có sẵn; phần còn thiếu phải cào lại", ["I3"], "tin TopDev bù trường"),
    "B": ("Giữ bản mới nhất, bỏ file batch, bỏ tin trùng công ty + tiêu đề + tỉnh + tuần", ["C1", "C2", "C6", "C7"], "bản ghi trùng bị bỏ"),
    "C": ("Giữ 18 trường chung, đổi null trá hình về null, thêm cờ thiếu giá trị", ["T1"], "ô null trá hình"),
    "D": ("Parse lại lương có đơn vị tiền, chặn 1–500 triệu/tháng, gắn cờ ngoại lai", ["T2"], "tin bóc lương lại"),
    "E": ("Tách tỉnh và phường, quy về 34 tỉnh và 3.321 phường/xã mới", ["N1"], "tin quy về 34 tỉnh"),
    "F": ("Bóc số năm kinh nghiệm, quy cấp bậc về 6 bậc", ["N2"], "tin có cấp bậc chuẩn"),
    "G": ("Bỏ tag ngành/SEO, chuẩn kỹ năng theo từ điển, xếp 12 nhóm nghề", ["N4"], "tin có kỹ năng chuẩn"),
    "H": ("Đưa ngày về một định dạng, tách tháng đăng, số ngày tới hạn", ["T3"], "tin có ngày chuẩn"),
    "I": ("Làm sạch HTML, bỏ JD dưới 30 từ, nhận ngôn ngữ, chuẩn tên công ty", ["C5"], "JD quá ngắn bị bỏ"),
}
ISSUE_SHORT = {"A1": "tin ngoài IT", "A2": "ngày ITviec", "A3": "TopDev thiếu trường", "B": "trùng lặp", "C": "thiếu trường",
               "D": "lương", "E": "địa điểm", "F": "cấp bậc", "G": "kỹ năng", "H": "ngày tháng", "I": "văn bản"}
STEP_OF = {"C": "Clean", "I": "Integration", "T": "Transformation", "N": "Normalization", "E": "Encoding"}
RULE_CODES = re.compile(r"\s*\((?:[CITNE]\d+[a-z]?)(?:\s*[,+–]\s*[CITNE]?\d+[a-z]?)*\)")
SEV_COLOR = {"Cao": "#B42318", "TB": "#B54708", "Thấp": "#067647"}
BEFORE_C, AFTER_C, BAR_C = "#98A2B3", "#1D4ED8", "#1D4ED8"


def check_links(issue_rules: dict, rule_ids: set) -> list:
    """Lỗi liên kết: vấn đề không có luật, luật không có thật, luật không giải vấn đề nào."""
    errs = [f"vấn đề {i} không có luật" for i, r in issue_rules.items() if not r]
    mapped = {r for rs in issue_rules.values() for r in rs}
    errs += [f"luật {r} không có trong báo cáo" for r in sorted(mapped - rule_ids)]
    errs += [f"luật {r} không giải vấn đề nào" for r in sorted(rule_ids - mapped)]
    return errs


def rule_issues(rule: str) -> list:
    return [i for i, rs in ISSUE_TO_RULES.items() if rule in rs]


# ---- định dạng số kiểu Việt Nam ----
def n(v) -> str:
    return f"{int(round(v)):,}".replace(",", ".")


def pct(v, d=1) -> str:
    return f"{v:.{d}f}".replace(".", ",") + "%"


def esc(s) -> str:
    return html.escape(str(s))


# ---- số liệu sau pre-processing (dùng chung cho bản trước sửa review) ----
def metrics(df) -> dict:
    import pandas as pd

    sen = df["seniority"].fillna("Không rõ").replace({"Chưa rõ": "Không rõ"})
    ward = df["locations"].apply(lambda locs: [l.get("phuong_xa") for l in (locs if locs is not None else []) if l.get("phuong_xa")])
    lang = df["language"].value_counts().to_dict()
    m = df["salary_max_vnd"]
    return {
        "rows": int(len(df)),
        "seniority": {k: int(v) for k, v in sen.value_counts().items()},
        "skill_c": int(df["skills_std"].apply(lambda x: x is not None and "C" in list(x)).sum()),
        "salary_over_500m": int((m > 5e8).sum()),
        "salary_under_1m": int((m < 1e6).sum()),
        "salary_from_title": int((df["salary_source"] == "title").sum()),
        "lang_en": int(lang.get("en", 0)), "lang_vi": int(lang.get("vi", 0)), "lang_bilingual": int(lang.get("bilingual", 0)),
        "jobs_with_ward": int(ward.apply(bool).sum()),
        "ward_dirty": int(ward.apply(lambda ws: any("(" in w or "quận" in w.lower() for w in ws)).sum()),
        "seniority_can_kiem": int(df["seniority_can_kiem"].sum()) if "seniority_can_kiem" in df else None,
        "job_family_can_kiem": int(df["job_family_can_kiem"].sum()) if "job_family_can_kiem" in df else None,
        "it_status": {k: int(v) for k, v in df["it_status"].value_counts().items()},
        "level2_kept": int((pd.to_numeric(df["it_rule_level"], errors="coerce") == 2).sum()) if "it_rule_level" in df else None,
        "salary_any": int((df["salary_min_vnd"].notna() | df["salary_max_vnd"].notna()).sum()),
        "family_khac": int((df["job_family"] == "Khác").sum()),
        "city_top2": int(df["tinh_chinh"].isin(["TP. Hà Nội", "TP. Hồ Chí Minh"]).sum()),
        "by_source": {k: int(v) for k, v in df["source_platform"].value_counts().items()},
    }


# ---- biểu đồ SVG ----
def _ticks(vmax: float, k: int = 5) -> list:
    raw = vmax / k
    mag = 10 ** len(str(int(raw))) / 10 if raw >= 1 else 1
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    return [step * i for i in range(int(-(-vmax // step)) + 1)] if vmax else [0, 1]


def hbar(rows, x_title, y_title, *, w=600, bar=22, label_w=150, fmt=n, colors=None, vmax=None):
    """Cột ngang: rows = [(nhãn, giá trị)]. Có tên trục, vạch chia, số trên cột."""
    gap, top, left = 8, 10, label_w + 34
    plot_w = w - left - 70
    h = top + len(rows) * (bar + gap) + 56
    vmax = vmax or max(v for _, v in rows) or 1
    ticks = _ticks(vmax)
    vmax = max(vmax, ticks[-1])
    sx = lambda v: left + plot_w * v / vmax  # noqa: E731
    base = top + len(rows) * (bar + gap)
    out = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" class="chart">']
    for t in ticks:
        out.append(f'<line x1="{sx(t):.1f}" y1="{top - 4}" x2="{sx(t):.1f}" y2="{base}" class="grid"/>'
                   f'<text x="{sx(t):.1f}" y="{base + 18}" class="tick" text-anchor="middle">{fmt(t)}</text>')
    for i, (lab, v) in enumerate(rows):
        y = top + i * (bar + gap)
        c = (colors or {}).get(lab, BAR_C)
        out.append(f'<text x="{left - 8}" y="{y + bar * 0.72:.1f}" class="lab" text-anchor="end">{esc(lab)}</text>'
                   f'<rect x="{left}" y="{y}" width="{max(sx(v) - left, 1):.1f}" height="{bar}" fill="{c}" rx="2"/>'
                   f'<text x="{sx(v) + 6:.1f}" y="{y + bar * 0.72:.1f}" class="val">{fmt(v)}</text>')
    out.append(f'<line x1="{left}" y1="{top - 4}" x2="{left}" y2="{base}" class="axis"/>'
               f'<line x1="{left}" y1="{base}" x2="{left + plot_w}" y2="{base}" class="axis"/>'
               f'<text x="{left + plot_w / 2:.1f}" y="{h - 6}" class="atitle" text-anchor="middle">{esc(x_title)}</text>'
               f'<text transform="translate(14,{(top + base) / 2:.1f}) rotate(-90)" class="atitle" text-anchor="middle">{esc(y_title)}</text></svg>')
    return "".join(out)


def pair_bar(rows, x_title, y_title, legend=("Trước", "Sau"), *, w=600, label_w=190, fmt=n, bar=16):
    """Cột đôi trước/sau: rows = [(nhãn, trước, sau)]."""
    gap, top, left = 14, 34, label_w + 34
    plot_w = w - left - 70
    group = 2 * bar + 2
    base = top + len(rows) * (group + gap)
    h = base + 56
    vmax = max(max(b, a) for _, b, a in rows) or 1
    ticks = _ticks(vmax)
    vmax = max(vmax, ticks[-1])
    sx = lambda v: left + plot_w * v / vmax  # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" class="chart">',
           f'<rect x="{left}" y="6" width="14" height="14" fill="{BEFORE_C}"/><text x="{left + 20}" y="18" class="lab">{esc(legend[0])}</text>'
           f'<rect x="{left + 150}" y="6" width="14" height="14" fill="{AFTER_C}"/><text x="{left + 170}" y="18" class="lab">{esc(legend[1])}</text>']
    for t in ticks:
        out.append(f'<line x1="{sx(t):.1f}" y1="{top - 4}" x2="{sx(t):.1f}" y2="{base}" class="grid"/>'
                   f'<text x="{sx(t):.1f}" y="{base + 18}" class="tick" text-anchor="middle">{fmt(t)}</text>')
    for i, (lab, b, a) in enumerate(rows):
        y = top + i * (group + gap)
        out.append(f'<text x="{left - 8}" y="{y + group * 0.62:.1f}" class="lab" text-anchor="end">{esc(lab)}</text>')
        for j, (v, c) in enumerate(((b, BEFORE_C), (a, AFTER_C))):
            yy = y + j * (bar + 2)
            out.append(f'<rect x="{left}" y="{yy}" width="{max(sx(v) - left, 1):.1f}" height="{bar}" fill="{c}" rx="2"/>'
                       f'<text x="{sx(v) + 6:.1f}" y="{yy + bar * 0.75:.1f}" class="val">{fmt(v)}</text>')
    out.append(f'<line x1="{left}" y1="{top - 4}" x2="{left}" y2="{base}" class="axis"/>'
               f'<line x1="{left}" y1="{base}" x2="{left + plot_w}" y2="{base}" class="axis"/>'
               f'<text x="{left + plot_w / 2:.1f}" y="{h - 6}" class="atitle" text-anchor="middle">{esc(x_title)}</text>'
               f'<text transform="translate(14,{(top + base) / 2:.1f}) rotate(-90)" class="atitle" text-anchor="middle">{esc(y_title)}</text></svg>')
    return "".join(out)


def heatmap(matrix, sources, fill):
    head = "".join(f"<th>{esc(s)}</th>" for s in sources)
    body = []
    for m in matrix:
        f = m["field"]
        cells = "".join(
            f'<td style="background:{"rgba(29,78,216,%.2f)" % (0.08 + 0.6 * fill[s][f] / 100) if fill[s][f] >= 50 else "rgba(180,35,24,%.2f)" % (0.1 + 0.4 * (1 - fill[s][f] / 50))}">{fill[s][f]:.0f}</td>'
            for s in sources)
        tag = '<b class="keep">Giữ</b>' if m["keep"] else '<b class="drop">Bỏ</b>'
        body.append(f"<tr><th class='f'>{esc(f)}</th>{cells}<td class='n'>{m['sources']}/8</td><td>{tag}</td></tr>")
    return (f'<table class="heat"><thead><tr><th class="f">Trường ↓ / Nguồn →</th>{head}<th>Số nguồn ≥ 50%</th><th></th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


# ---- dựng slide ----
def slide(title, body, say, qa, src, conclusion=None, tag=None):
    return {"title": title, "body": body, "say": say, "qa": qa, "src": src, "conclusion": conclusion, "tag": tag}


def chart_box(svg, source):
    return f'<figure>{svg}<figcaption>Nguồn: {esc(source)}</figcaption></figure>'


def link_tags(rules):
    return " ".join(f'<span class="rule">{esc(r)}</span>' for r in rules)


def build(raw: dict, raw_now: dict, reports: dict, after: dict, before: dict, storage: dict) -> list:
    S = [s for s in raw["sources"] if raw["sources"][s]["jobs"]]
    P = raw["sources"]
    rules = {r["id"]: r for st in STEPS for r in reports[st]["rules"]}
    ra = lambda rid: rules[rid]["rows_affected"]  # noqa: E731
    clean = reports["01_clean"]
    snap = sum(P[s]["files"].get("snapshot", 0) for s in S)
    levels = {}
    for v in clean["extra"].get("it_levels", {}).values():
        for k, x in v.items():
            levels[k] = levels.get(k, 0) + x
    review = {}
    for v in clean["extra"]["review"].values():
        for k, x in v.items():
            if isinstance(x, int):
                review[k] = review.get(k, 0) + x
    out = []

    # 1. Tiêu đề
    out.append(slide(
        "Tiền xử lý dữ liệu việc làm IT Việt Nam",
        f'<div class="hero"><p class="sub">Từ vấn đề dữ liệu raw đến 5 bước pre-processing</p>'
        f'<div class="kpis"><div><b>8</b><span>nguồn tuyển dụng</span></div><div><b>{n(clean["input"]["rows"])}</b><span>bản ghi raw vào</span></div>'
        f'<div><b>{n(clean["output"]["rows"])}</b><span>tin IT sạch ra</span></div><div><b>{n(reports["05_encoding"]["extra"]["total_columns"])}</b><span>cột đặc trưng (biến đầu vào mô hình)</span></div></div>'
        f'<p class="date">Số liệu chốt ngày {esc(reports["05_encoding"]["generated_at"][:10])}</p></div>',
        ["Em chào thầy và các bạn. Em xin trình bày phần tiền xử lý dữ liệu của đề tài khai phá việc làm IT từ 8 trang tuyển dụng.",
         f"Đầu vào là {n(clean['input']['rows'])} bản ghi raw, đầu ra là {n(clean['output']['rows'])} tin IT đã làm sạch với {n(reports['05_encoding']['extra']['total_columns'])} cột đặc trưng.",
         "Mọi con số trên slide đều sinh tự động từ báo cáo của pipeline, thầy hỏi số nào em chỉ được file gốc."],
        [("Tại sao chỉ 8 nguồn?", "Đây là 8 trang có lượng tin IT lớn và cào được ổn định; danh sách SOURCES trong preprocessing/common."),
         ("Số liệu lấy lúc nào?", "Ngày ghi trên slide là generated_at của báo cáo bước Encoding.")],
        ["reports/preprocessing/01_clean/_all.json (input.rows, output.rows)", "reports/preprocessing/05_encoding/_all.json (extra.total_columns)"]))

    # 2. Dữ liệu vào: 3 mức đếm, từ nhiều nhất đến số tin thật
    vers = sorted(((s, P[s]["files"].get("snapshot_v_lớn_hơn_1", 0)) for s in S), key=lambda x: -x[1])
    funnel = [("Tất cả bản ghi raw", clean["input"]["rows"]), ("Chỉ file từng tin (bỏ file batch)", snap),
              ("Tin khác nhau (bản mới nhất)", raw["total_jobs"])]
    out.append(slide(
        "Dữ liệu vào: 14 nghìn bản ghi nhưng chỉ 10,7 nghìn tin",
        '<div class="two">' + chart_box(hbar(funnel, "Số bản ghi", "Cách đếm", w=700, label_w=250, bar=70,
                                             colors={funnel[-1][0]: "#067647"}),
                                        "docs/presentation/data/raw_issues_before.json")
        + f'<div class="facts"><div><b>−{n(clean["input"]["rows"] - snap)}</b><span>tin nằm lại trong file batch cũ (VietnamWorks, Vieclam24h)</span></div>'
          f'<div><b>−{n(snap - raw["total_jobs"])}</b><span>phiên bản cũ của cùng tin; nhiều nhất {vers[0][0]} ({n(vers[0][1])}), {vers[1][0]} ({n(vers[1][1])})</span></div></div></div>',
        ["Cột trên cùng là mọi bản ghi raw đang có trên R2.",
         f"Bỏ {n(clean['input']['rows'] - snap)} tin chép lại trong file batch cũ thì còn {n(snap)} file từng tin.",
         f"Một tin cào lại khi đã đổi nội dung thì có thêm phiên bản, nên chỉ có {n(raw['total_jobs'])} tin khác nhau.",
         "Đây là lý do bước Clean phải giữ bản mới nhất trước khi làm gì khác."],
        [("Raw có bị sửa không?", "Không. Raw là bất biến; mọi sửa nằm ở pre-processing."),
         ("Phiên bản mới sinh ra khi nào?", "Khi hash JSON chuẩn hóa của tin đổi (CDC trong collection/common/url_ledger.py)."),
         ("Số theo từng nguồn đâu?", "Bảng 'Số tin theo nguồn' trong docs/preprocessing/data_issues_2026-11-03.html.")],
        ["docs/presentation/data/raw_issues_before.json → total_jobs, sources.<nguồn>.files", "reports/preprocessing/01_clean/_all.json → input.rows",
         "docs/preprocessing/data_issues_2026-11-03.html (bảng theo nguồn)"],
        conclusion=f"{n(clean['input']['rows'])} bản ghi nhưng chỉ {n(raw['total_jobs'])} tin khác nhau → phải giữ bản mới nhất và bỏ bản trùng trước."))

    # 3. Tổng quan vấn đề: bằng chứng là số thật, không có mã luật
    bad_sal = sum(P[x]["salary"]["parsed_under_1m"] + P[x]["salary"]["from_x_max_equals_min"] for x in S)
    no_date = [x for x in S if P[x]["dates"]["posted_empty_pct"] >= 99.9]
    evidence = {
        "A1": f"{pct(P['topdev']['title']['non_it_pct'], 0)} tin TopDev không phải việc IT",
        "A2": f"{n(P['itviec']['dates']['posted_relative'])} tin ITviec ghi \"Đăng … giờ trước\"",
        "A3": f"{pct(P['topdev']['fill']['raw_experience_text'], 0)} tin TopDev có kinh nghiệm",
        "B": f"{n(raw['dedup'][0]['extra_jobs'])} tin trùng tiêu đề + công ty",
        "C": f"{sum(1 for m in raw['field_matrix'] if not m['keep'])}/{len(raw['field_matrix'])} trường chỉ 1–2 nguồn có",
        "D": f"{n(bad_sal)} tin đọc lương sai đơn vị",
        "E": f"{n(sum(P[x]['location']['street_address'] for x in S))} tin ghi địa chỉ đường phố",
        "F": f"{n(sum(P[x]['seniority']['distinct'] for x in S))} cách ghi cấp bậc ở 8 nguồn",
        "G": f"{n(sum(P[x]['skills']['long_tags'] for x in S))} tag kỹ năng là câu hoặc ngành",
        "H": f"{', '.join(no_date)} không có ngày đăng",
        "I": f"{n(sum(P[x]['company']['same_company_variants'] for x in S))} công ty có nhiều cách viết",
    }
    steps_of = lambda c: sorted({STEP_OF[r[0]] for r in ISSUE_TO_RULES[c]}, key=list(STEP_OF.values()).index)  # noqa: E731
    cards = "".join(
        f'<div class="icard" style="border-color:{SEV_COLOR[sev]}"><div><span class="sev" style="background:{SEV_COLOR[sev]}">{sev}</span></div>'
        f'<p>{esc(name)}</p><div class="ev">{esc(evidence[code])}</div></div>'
        for code, (name, sev) in ISSUES.items())
    out.append(slide(
        "Dữ liệu raw có 11 nhóm vấn đề",
        f'<div class="igrid">{cards}</div><p class="legend"><span class="sev" style="background:{SEV_COLOR["Cao"]}">Cao</span> làm sai số liệu phân tích · '
        f'<span class="sev" style="background:{SEV_COLOR["TB"]}">TB</span> mất thông tin, khó so giữa các nguồn · '
        f'<span class="sev" style="background:{SEV_COLOR["Thấp"]}">Thấp</span> cần làm sạch thêm · dòng xanh là số đo trên raw</p>',
        ["Thống kê trên 10.758 tin raw (bản mới nhất mỗi tin), em gom được 11 nhóm vấn đề.",
         "Mỗi thẻ có một con số đo được trên raw để thấy độ lớn của vấn đề.",
         "Bốn vấn đề mức Cao là tin ngoài IT, ngày đăng tương đối, trùng lặp và lương sai, vì chúng làm sai thẳng kết quả phân tích.",
         "Hai slide sau là ví dụ raw thật để thầy thấy tận mắt."],
        [("Đo các số này thế nào?", "Script scripts/report_data_issues.py đọc raw, lấy bản mới nhất mỗi tin, làm phẳng rồi đếm; kết quả lưu ở raw_issues_before.json."),
         ("Mức Cao/TB/Thấp dựa vào đâu?", "Cao là làm sai kết quả phân tích; A1, A2, B, D theo docs/preprocessing/data_issues_2026-11-03.md, các nhóm còn lại do em đánh giá."),
         ("Tin ngoài IT ước lượng thế nào?", "Theo từ khóa tiêu đề, nên chỉ để thấy độ lớn; phân loại thật làm ở bước Clean và kiểm bằng nhãn tay.")],
        ["docs/presentation/data/raw_issues_before.json", "docs/preprocessing/data_issues_2026-11-03.md, .html"]))

    # 3b. Ví dụ raw thật (1): sai phạm vi, sai giá trị
    nonit = P["topdev"]["title"]["non_it_examples"][:2]
    sal_ex = [(x, P[x]["salary"]["parsed_under_1m_examples"][0]) for x in ("topdev", "itviec") if P[x]["salary"].get("parsed_under_1m_examples")]
    comp = next(P[x]["company"]["example"] for x in S if P[x]["company"]["example"])
    sneaky = next(((x, v) for x in S for v in P[x]["sneaky_null"]), None)
    rows = [("A1", "topdev", f"Tiêu đề: “{e['title']}”", "Việc kế toán, kinh doanh nằm trong dữ liệu IT") for e in nonit]
    rows += [("A2", "itviec", "Ngày đăng: “Đăng 6 giờ trước”", "Không biết ngày thật, mỗi lần cào ra giá trị khác")]
    rows += [("D", x, f"Lương “{e.split(' → ')[0]}” đọc thành {e.split(' → ')[1]}", "Dấu phân cách nghìn bị đọc thành dấu thập phân") for x, e in sal_ex]
    rows += [("I", "topcv", " / ".join(f"“{c}”" for c in comp[:2]), "Cùng công ty, hai cách viết → đếm thành hai")]
    if sneaky:
        field, val = sneaky[1][0].split(" = ")
        label = {"raw_education_text": "Trình độ học vấn", "raw_headcount": "Số lượng tuyển"}.get(field, field)
        rows += [("C", sneaky[0], f"{label}: “{val.strip(chr(39))}” ({n(sneaky[1][1])} tin)", "Giá trị “0” thật ra là không có thông tin")]
    trs = "".join(f'<tr><td>{esc(src)}</td><td>{esc(raw_v)}</td><td>{esc(why)}</td></tr>' for c, src, raw_v, why in rows)
    out.append(slide(
        "Ví dụ raw thật (1): sai phạm vi, sai giá trị",
        f'<table class="matrix ex"><thead><tr><th>Nguồn</th><th>Raw ghi</th><th>Vì sao sai</th></tr></thead><tbody>{trs}</tbody></table>',
        ["Đây là giá trị copy nguyên từ raw, không qua xử lý.",
         "Tin kế toán, kinh doanh nằm trong dữ liệu IT vì TopDev bỏ qua bộ lọc ngành.",
         "Lương USD bị đọc nhầm dấu phân cách hàng nghìn nên 2.000 USD còn vài chục nghìn đồng.",
         "Tên công ty viết hoa khác nhau thì máy đếm thành hai công ty."],
        [("Kiểm ví dụ này ở đâu?", "Link gốc của tin ngoài IT nằm trong raw_issues_before.json → sources.topdev.title.non_it_examples; mở trang là thấy."),
         ("Sao không sửa ở lúc cào?", "Raw giữ nguyên để kiểm lại được; sửa ở pre-processing. Riêng phạm vi TopDev thì đã ghi việc sửa crawler."),
         ("“Đăng 6 giờ trước” lấy đâu?", f"Trường posted_at_raw của ITviec; {n(P['itviec']['dates']['posted_relative'])} tin có dạng này (docs/preprocessing/data_issues_2026-11-03.md, A2).")],
        ["docs/presentation/data/raw_issues_before.json → title.non_it_examples, salary.parsed_under_1m_examples, company.example, sneaky_null"],
        conclusion="Không xử lý thì thống kê sẽ đếm cả việc kế toán, lương 2.000 USD thành 50 nghìn đồng, một công ty thành hai."))

    # 3c. Ví dụ raw thật (2): mỗi nguồn ghi một kiểu
    def top(x, key, i=0):
        t = P[x][key]["top"]
        return t[i][0] if len(t) > i else "(không có trường này)"
    cmp_rows = [
        ("Tỉnh/thành", [("topdev", top("topdev", "location")), ("topcv", top("topcv", "location", 1)), ("vietnamworks", top("vietnamworks", "location", 1)),
                        ("vieclam24h", top("vieclam24h", "location")), ("itviec", top("itviec", "location", 2))]),
        ("Cấp bậc", [("topcv", top("topcv", "seniority")), ("jobsgo", top("jobsgo", "seniority")), ("vietnamworks", top("vietnamworks", "seniority", 2)),
                     ("itviec", top("itviec", "seniority"))]),
        ("Kinh nghiệm", [("itviec", top("itviec", "experience")), ("jobsgo", top("jobsgo", "experience", 1)), ("vieclam24h", top("vieclam24h", "experience"))]),
        ("Kỹ năng", [("topcv", top("topcv", "skills")), ("jobsgo", top("jobsgo", "skills")), ("vieclam24h", top("vieclam24h", "skills"))]),
    ]
    blocks = "".join(f'<div class="cmp"><b>{esc(f)}</b>' + "".join(f'<div><span>{esc(x)}</span>“{esc(v)}”</div>' for x, v in vals) + "</div>"
                     for f, vals in cmp_rows)
    out.append(slide(
        "Ví dụ raw thật (2): cùng một thông tin, mỗi nguồn ghi một kiểu",
        f'<div class="cmps">{blocks}</div>',
        ["Cùng là TP.HCM nhưng mỗi nguồn ghi một kiểu, có nguồn ghi cả địa chỉ đường phố.",
         "Cấp bậc mỗi nguồn một bộ từ, ITviec không có trường này.",
         "Kinh nghiệm có dạng số tháng, dạng khoảng, dạng chữ.",
         "Trường kỹ năng ở TopCV, JobsGO, Vieclam24h thực ra là ngành nghề, có cả tên công ty bị cắt."],
        [("Ví dụ lấy thế nào?", "Là giá trị phổ biến nhất của mỗi nguồn (trường top) trong raw_issues_before.json."),
         ("Không chuẩn hóa thì sao?", "Không gom nhóm, không so giữa các nguồn được; ví dụ đếm tin theo tỉnh sẽ ra 5 dòng cho TP.HCM.")],
        ["docs/presentation/data/raw_issues_before.json → sources.<nguồn>.location.top, seniority.top, experience.top, skills.top"],
        conclusion="Cùng một thông tin nhưng mỗi nguồn một kiểu → phải chuẩn hóa về một dạng chung trước khi phân tích."))

    # 4. A1
    non_it = sorted(((s, P[s]["title"]["non_it_pct"]) for s in S), key=lambda x: -x[1])
    out.append(slide(
        "Tin ngoài IT lẫn vào dữ liệu",
        '<div class="two">' + chart_box(hbar(non_it, "Tỉ lệ tin có tiêu đề ngoài IT (%, ước lượng theo từ khóa)", "Nguồn",
                                             fmt=lambda v: pct(v, 0), colors={"topdev": "#B42318"}, w=640, label_w=110, bar=34),
                                        "raw_issues_before.json → sources.<nguồn>.title.non_it_pct")
        + f'<div class="facts"><div><b>14.572 = 14.572</b><span>TopDev trả cùng số tin dù có hay không có bộ lọc IT</span></div>'
          f'<div><b>{n(review["rule_correct"])}/{n(review["rule_decided"])}</b><span>tầng 1 (từ khóa tiêu đề) đúng trên nhãn tay</span></div>'
          f'<div><b>{n(review["level2_correct"])}/{n(review["level2_labeled"])}</b><span>tầng 2 (nhóm nghề + kỹ năng JD) đúng, {pct(100 * review["level2_correct"] / max(review["level2_labeled"], 1))}</span></div></div></div>',
        [f"TopDev có {pct(P['topdev']['title']['non_it_pct'], 0)} tiêu đề ngoài IT, ví dụ Kế toán trưởng, Nhân viên kinh doanh.",
         "Nguyên nhân: API TopDev bỏ qua tham số category_ids=1, có hay không có đều ra 14.572 tin.",
         "Bước Clean phân loại bằng luật if-else 2 tầng: tầng 1 xét từ khóa tiêu đề; tin chưa quyết được thì tầng 2 xét nhóm nghề và số kỹ năng trong JD.",
         f"Gán nhãn tay {n(review['labeled'])} tin để đo độ đúng, rồi mới bỏ {n(ra('C4c'))} tin ngoài IT."],
        [("Sao không bỏ hết TopDev?", f"Vẫn có tin IT thật; sau phân loại còn {n(clean['extra']['it_status']['topdev'].get('it', 0))} tin IT TopDev."),
         ("Luật đúng bao nhiêu?", f"Tầng 1 đúng {n(review['rule_correct'])}/{n(review['rule_decided'])}; tầng 2 khó hơn, đúng {n(review['level2_correct'])}/{n(review['level2_labeled'])}."),
         ("Tầng 2 là gì?", "Tiêu đề thuộc 1 trong 12 nhóm nghề IT và JD có ít nhất 2 kỹ năng công nghệ thì là IT; ngưỡng 2 cho kết quả tốt nhất khi thử 2–6."),
         ("Sao không dùng model AI?", "Luật if-else giải thích được từng quyết định, không phụ thuộc dịch vụ ngoài; độ đúng đo bằng nhãn tay.")],
        ["reports/preprocessing/01_clean/_all.json → extra.review, extra.it_levels, rules C4a/C4c", "data/preprocessing/review/it_<nguồn>.csv (nhãn tay)", "preprocessing/common/it_filter.py (classify, classify_unknown)"],
        conclusion=f"Không lọc thì {pct(P['topdev']['title']['non_it_pct'], 0)} tin TopDev là ngoài IT → Clean bỏ {n(ra('C4c'))} tin (C4c) sau khi kiểm bằng nhãn tay.",
        tag=None))

    # 5. B
    d = raw["dedup"]
    out.append(slide(
        "Trùng lặp: thêm điều kiện thì bớt trùng giả",
        '<div class="two"><div>' + chart_box(pair_bar([(x["step"].split(" (")[0].replace("+ tuần đăng", "+ cùng tuần đăng"), x["extra_jobs"], x["groups_cross_source"]) for x in d],
                                                 "Số tin / số nhóm", "Điều kiện so trùng (cộng dồn)", ("Tin thừa", "Nhóm trùng khác nguồn"), w=660, label_w=170, bar=40),
                                        "raw_issues_before.json → dedup")
        + '<p class="legend">Cùng tuần đăng: hai tin chỉ coi là trùng khi đăng trong cùng một tuần;<br>TopCV, TopDev thiếu ngày đăng thì dùng tuần cào.</p></div>'
        + f'<div class="facts"><div><b>{n(ra("C1"))}</b><span>bản cũ bỏ (C1)</span></div><div><b>{n(ra("C2"))}</b><span>tin file batch bỏ (C2)</span></div>'
          f'<div><b>{n(ra("C6"))} + {n(ra("C7"))}</b><span>trùng cùng nguồn (C6) + khác nguồn (C7)</span></div></div></div>',
        ["Luật trùng: cùng công ty, cùng tiêu đề, cùng tỉnh, cùng tuần đăng.",
         f"Chỉ so tiêu đề + công ty thì {n(d[0]['groups_cross_source'])} nhóm trùng khác nguồn; thêm tỉnh thì còn {n(d[1]['groups_cross_source'])}, vì mỗi nguồn ghi thành phố một kiểu.",
         "Thêm điều kiện cùng tuần đăng vì công ty hay đăng lại cùng vị trí sau vài tháng: đó là đợt tuyển mới, không phải bản trùng.",
         "Nên phải chuẩn hóa tỉnh trước rồi mới so trùng."],
        [("Tin trùng khác nguồn thì giữ bản nào?", "Giữ một bản, ghi các nguồn còn lại vào cột also_on (C7)."),
         ("Thiếu ngày đăng thì sao?", "TopCV, TopDev không có ngày đăng nên dùng tuần cào.")],
        ["raw_issues_before.json → dedup", "reports/preprocessing/01_clean/_all.json → rules C1, C2, C6, C7; extra.cross_source_pairs"],
        conclusion=f"Clean bỏ {n(ra('C1') + ra('C2') + ra('C6') + ra('C7'))} bản ghi trùng (C1, C2, C6, C7); so trùng chỉ đúng khi tỉnh đã chuẩn hóa.",
        tag=None))

    # 6. C
    fill = {s: P[s]["fill"] for s in S}
    kept = sum(1 for m in raw["field_matrix"] if m["keep"])
    out.append(slide(
        "Độ phủ trường: mỗi nguồn có một bộ trường khác nhau",
        f'<div class="two wide">{chart_box(heatmap(raw["field_matrix"], S, fill), "raw_issues_before.json → field_matrix, sources.<nguồn>.fill")}'
        f'<div class="facts"><div><b>{kept}/{len(raw["field_matrix"])}</b><span>trường giữ cho Integration</span></div>'
        f'<div><b>≥ 3 nguồn</b><span>có ≥ 50% tin có giá trị thì giữ</span></div>'
        f'<div><b>{n(ra("T1"))}</b><span>ô null trá hình đổi về null (T1)</span></div></div></div>',
        ["Ô là phần trăm tin có giá trị của trường đó ở nguồn đó; xanh là đủ, đỏ là thiếu.",
         "Luật: trích được thì lấy, không thì để null; chỉ giữ trường có ở ít nhất 3 nguồn.",
         "Ô đỏ ở TopDev và ITviec là do flattener chưa đọc đúng chỗ, đã sửa ở luật I2, I3."],
        [("Sao không bù giá trị thiếu?", "Bù sẽ tạo số giả; giữ null và có cột missing ở bước Encoding (E5)."),
         ("Null trá hình là gì?", "Giá trị như '0' hay chuỗi rỗng mà thật ra là thiếu, ví dụ VietnamWorks education = '0' ở 309 tin.")],
        ["raw_issues_before.json → field_matrix", "reports/preprocessing/02_integration/_all.json → fields (fill_pct_in/out)"],
        conclusion=f"Giữ {kept} trường dùng chung được; 6 trường chỉ 1–2 nguồn có thì bỏ (I1), null trá hình về null (T1, I5).",
        tag=None))

    # 7. D: số tin bộ parse cũ đọc sai theo nguồn + ví dụ raw: cũ đọc thế nào, mới đọc thế nào (tính lại ngay)
    from preprocessing.transformation.salary_parser import parse_salary_cascade

    bad = lambda src: src["salary"]["parsed_under_1m"] + src["salary"]["from_x_max_equals_min"]  # noqa: E731
    sal_bad = sorted(((s, bad(P[s])) for s in S if bad(P[s])), key=lambda x: -x[1])
    now_bad = sum(bad(raw_now["sources"][s]) for s in S)

    def vnd(lo, hi):
        f = lambda v: f"{v / 1e6:.1f}".replace(".", ",").replace(",0", "") + " triệu"  # noqa: E731
        return "–".join(f(v) for v in (lo, hi) if v) or "trống" if (lo or hi) else "trống"

    ex = list(dict.fromkeys(e for x in ("itviec", "topdev", "topcv") for e in P[x]["salary"].get("parsed_under_1m_examples", [])))[:4]
    ex_rows = []
    for e in ex:
        raw_s, old = e.split(" → ")
        r = parse_salary_cascade(raw_s)
        ex_rows.append((raw_s, old, vnd(r.get("salary_min_vnd"), r.get("salary_max_vnd"))))
    ex_html = "".join(f"<tr><td>“{esc(a)}”</td><td class='bad'>{esc(b)}</td><td class='good'>{esc(c)}</td></tr>" for a, b, c in ex_rows)
    out.append(slide(
        "Lương: bộ parse cũ đọc sai đơn vị",
        '<div class="two">' + chart_box(hbar(sal_bad, "Số tin bộ parse cũ đọc sai (< 1 triệu, hoặc 'Từ X' bị gán max = min)", "Nguồn",
                                             w=600, label_w=110, bar=34, colors={sal_bad[0][0]: "#B42318"}),
                                        "raw_issues_before.json → sources.<nguồn>.salary (code cũ)")
        + f'<div class="facts"><table class="matrix ex sal"><thead><tr><th>Raw ghi</th><th>Bộ cũ đọc</th><th>Bộ mới đọc</th></tr></thead><tbody>{ex_html}</tbody></table>'
          f'<div><b>{n(sum(x[1] for x in sal_bad))} → {n(now_bad)}</b><span>tin đọc sai: bộ cũ → bộ mới, trên cùng raw</span></div></div></div>',
        ["Biểu đồ là số tin bộ parse cũ đọc sai ở từng nguồn; bộ mới chạy lại trên cùng raw thì còn " + n(now_bad) + " tin sai.",
         "Lỗi chính: dấu phân cách hàng nghìn bị đọc thành dấu thập phân, nên 2.000 USD chỉ còn vài chục nghìn đồng.",
         "Bảng bên phải là ví dụ thật: chuỗi lương trong raw, bộ cũ đọc thành gì, bộ mới đọc thành gì.",
         "Bộ mới chỉ nhận số có đơn vị tiền, đọc nguyên số có dấu phân cách, chặn lương tháng ngoài 1–500 triệu."],
        [("Lương thỏa thuận xử lý sao?", "Giữ trống và cờ is_negotiable, không bù."),
         ("USD đổi thế nào?", "Tỉ giá cố định 25.400 VND/USD, ghi trong salary_parser.py."),
         ("Cột 'bộ mới đọc' lấy đâu?", "Script gọi parse_salary_cascade trên đúng chuỗi raw đó lúc tạo slide, không gõ tay."),
         ("Ngưỡng 500 triệu ở đâu ra?", "Lương tháng IT ở Việt Nam trên 500 triệu gần như không có; số trên đó là parse sai, nên để trống và gắn cờ salary_suspect.")],
        ["raw_issues_before.json → sources.<nguồn>.salary.parsed_under_1m_examples", "preprocessing/transformation/salary_parser.py → parse_salary_cascade",
         "reports/preprocessing/03_transformation/_all.json → rules T2, T2f"],
        conclusion=f"Bộ parse cũ đọc sai {n(sum(x[1] for x in sal_bad))} tin, bộ mới còn {n(now_bad)} → lương dùng được để thống kê.",
        tag=None))

    # 8. E–I
    small = lambda key, sub, xt, f=n: hbar(sorted(((s, P[s][key][sub]) for s in S), key=lambda x: -x[1]), xt, "Nguồn",  # noqa: E731
                                          w=600, bar=12, label_w=96, fmt=f)
    out.append(slide(
        "Địa điểm, cấp bậc, kỹ năng, ngày tháng: mỗi nguồn một kiểu",
        '<div class="grid4">'
        + chart_box(small("location", "street_address", "Số tin ghi địa chỉ đường phố thay vì tỉnh"), "raw_issues_before.json → location.street_address")
        + chart_box(small("seniority", "distinct", "Số giá trị cấp bậc khác nhau"), "raw_issues_before.json → seniority.distinct")
        + chart_box(small("skills", "long_tags", "Số tag kỹ năng dài > 4 từ (câu, danh mục)"), "raw_issues_before.json → skills.long_tags")
        + chart_box(small("dates", "posted_empty_pct", "Tỉ lệ tin thiếu ngày đăng (%)", lambda v: pct(v, 0)), "raw_issues_before.json → dates.posted_empty_pct")
        + "</div>",
        ["Bốn biểu đồ cho bốn nhóm vấn đề. ITviec và VietnamWorks ghi địa chỉ đường phố, phải tách ra tỉnh và phường.",
         "Cấp bậc mỗi nguồn một bộ từ, ITviec, Glints không có.",
         "Kỹ năng ở TopCV, JobsGO, Vieclam24h lẫn danh mục ngành và câu dài.",
         "TopCV, TopDev không có ngày đăng."],
        [("Phường/xã lấy theo danh mục nào?", "3.321 phường/xã sau sáp nhập 2025 từ thanglequoc/vietnamese-provinces-database (MIT), file wards_34.json."),
         ("Quận huyện đâu?", "Bỏ hẳn vì sau 2025 không còn cấp huyện."),
         ("Cấp bậc chuẩn có mấy bậc?", "6 bậc: Thực tập, Mới tốt nghiệp, Junior, Middle, Senior, Trưởng nhóm/Quản lý; không xác định thì để trống.")],
        ["raw_issues_before.json → sources.<nguồn>.location / seniority / skills / dates"],
        conclusion="Chưa chuẩn hóa thì không so được giữa các nguồn → bóc tách (T3, T4, T7, T8) rồi quy chuẩn (N1–N4)."))

    # 9. Pipeline
    boxes = "".join(
        f'<div class="step"><b>{STEP_VI[st]}</b><span class="rows">{n(reports[st]["input"]["rows"])} → {n(reports[st]["output"]["rows"])}</span>'
        f'<span>{len(reports[st]["rules"])} luật</span><span class="solves">Giải: {", ".join(ISSUE_SHORT[i] for i in ISSUES if any(i in rule_issues(r["id"]) for r in reports[st]["rules"]))}</span></div>'
        for st in STEPS)
    out.append(slide(
        "Pipeline 5 bước: số dòng vào → ra mỗi bước",
        f'<div class="center"><div class="flow">{boxes}</div>'
        f'<div class="layers"><div><b>Bronze</b><span>raw/ trên R2, bất biến</span></div><div><b>Silver</b><span>{storage["silver"]} object, bước 01–04</span></div>'
        f'<div><b>Gold</b><span>{storage["gold"]} object, bước 05</span></div></div></div>',
        ["Chỉ bước Clean bỏ dòng; bốn bước sau giữ nguyên số dòng, chỉ sửa và thêm cột.",
         "Mỗi bước ghi báo cáo theo luật bảo toàn: số vào bằng số ra cộng số bỏ.",
         "Từ Integration, 8 nguồn gộp thành một bảng all.parquet có cột source_platform.",
         "Dòng '←' là vấn đề mà bước đó giải."],
        [("Kiểm bảo toàn dòng ở đâu?", "Trường checks.rows_conserved trong mỗi _all.json, hiện đang true."),
         ("Sao gộp ở Integration?", "Từ đó các nguồn cùng schema, xử lý chung một lần; báo cáo vẫn giữ số theo nguồn (by_source)."),
         ("Silver, gold nằm đâu?", "R2 bucket vn-it-jobs: bronze raw/<nguồn>/…, silver staging/<nguồn>/preprocessing/<bước>.*, gold curated/preprocessing/features.parquet."),
         ("Cho thầy xem dữ liệu?", "Mở ./start_monitoring.sh, vào http://127.0.0.1:5173: trang Raw cho bronze; trang Pre-processing chọn bước, bấm một dòng để xem đủ trường (đọc thẳng từ R2)."),
         ("Máy và R2 có khớp không?", "python scripts/push_preprocessing_to_r2.py (không cờ chỉ so, không ghi); lần kiểm gần nhất 34/34 khớp.")],
        ["reports/preprocessing/<bước>/_all.json → input.rows, output.rows, checks", "python scripts/push_preprocessing_to_r2.py (chạy không cờ chỉ so máy với R2)"],
        conclusion=f"{n(clean['input']['rows'])} bản ghi raw → {n(clean['output']['rows'])} tin sạch; mọi dòng bị bỏ đều có luật và lý do."))

    # 10. Clean waterfall
    C_SHORT = {"C1": "Bản cũ", "C2": "File batch", "C3": "Bản ghi lỗi", "C4c": "Ngoài IT (tầng 1 + 2)", "C5": "JD quá ngắn", "C6": "Trùng cùng nguồn", "C7": "Trùng khác nguồn"}
    left_rows, cur = [("Vào Clean", clean["input"]["rows"])], clean["input"]["rows"]
    for r in clean["rules"]:
        if r["action"] == "drop" and r["rows_affected"]:
            cur -= r["rows_affected"]
            left_rows.append((f"− {C_SHORT.get(r['id'], r['name'])} ({n(r['rows_affected'])})", cur))
    out.append(slide(
        "1. Clean: bỏ bản cũ, trùng, ngoài IT, JD quá ngắn",
        '<div class="two">' + chart_box(hbar(left_rows, "Số bản ghi còn lại sau từng luật", "Luật bỏ dòng (số bỏ)", w=680, label_w=240, bar=36,
                                             colors={left_rows[-1][0]: "#067647"}), "01_clean/_all.json → rules[].rows_affected")
        + '<div class="facts tight">' + "".join(f'<div><b>{esc(C_SHORT.get(r["id"], r["id"]))}</b><span>{esc(r["name"])} ← {", ".join(ISSUE_SHORT[i] for i in rule_issues(r["id"]))}</span></div>'
                                          for r in clean["rules"] if r["action"] == "drop" and r["rows_affected"]) + "</div></div>",
        [f"Bỏ nhiều nhất là tin ngoài IT ({n(ra('C4c'))}) và bản cũ ({n(ra('C1'))}).",
         f"Tin ngoài IT: tầng 1 (từ khóa tiêu đề) xếp {n(levels.get('tang_1_non_it', 0))} tin, tầng 2 (nhóm nghề + kỹ năng JD) xếp {n(levels.get('tang_2_non_it', 0))} tin.",
         f"C5 bỏ {n(ra('C5'))} tin có JD dưới 30 từ, không đủ nội dung để phân tích.",
         f"Còn lại {n(clean['output']['rows'])} tin."],
        [("Sao ITviec vẫn còn vài tin ngoài IT?", "Chính sách đã duyệt cho ITviec là không bỏ tin nào vì đây là trang chuyên IT; tin bị luật xếp ngoài IT vẫn giữ."),
         ("Tin bị bỏ có xem lại được không?", "Có, mỗi luật lưu ví dụ (examples) trong báo cáo và hiện trên trang Monitoring.")],
        ["reports/preprocessing/01_clean/_all.json", "python scripts/run_preprocessing.py --step clean --source all --dry-run"],
        conclusion=f"Clean giữ {pct(100 * clean['output']['rows'] / clean['input']['rows'])} bản ghi; phần bỏ chủ yếu là bản trùng và tin ngoài IT.",
        tag="Bước 1"))

    # 11. Integration
    integ = reports["02_integration"]
    I_SHORT = {"I0": "JSON hỏng", "I1": "Làm phẳng 18 trường", "I2": "Ngày đăng ITviec", "I3": "Ngày, KN TopDev",
               "I4": "Bỏ tag SEO khỏi kỹ năng", "I5": "Rỗng → null"}
    out.append(slide(
        "2. Integration: gộp 8 nguồn về một schema 18 trường",
        '<div class="two">' + chart_box(hbar([(I_SHORT.get(r["id"], r["name"]), r["rows_affected"]) for r in integ["rules"]],
                                             "Số tin được sửa", "Luật", w=700, label_w=230, bar=40),
                                        "02_integration/_all.json → rules[].rows_affected")
        + '<div class="facts"><div><b>8 file → 1</b><span>all.parquet, cột source_platform</span></div>'
          f'<div><b>{n(ra("I2"))}</b><span>ITviec lấy ngày đăng tuyệt đối</span></div>'
          f'<div><b>{n(ra("I0"))}</b><span>dòng JSON hỏng (I0)</span></div></div></div>',
        ["Integration làm phẳng envelope của từng nguồn về cùng 18 trường.",
         f"Sửa {n(ra('I2'))} tin ITviec lấy ngày từ JSON-LD thay cho 'Đăng 6 giờ trước', và {n(ra('I3'))} tin TopDev lấy ngày đăng, kinh nghiệm.",
         f"I4 bỏ tag SEO, ngành nghề khỏi kỹ năng ở {n(ra('I4'))} tin."],
        [("I0 bằng 0 nghĩa là gì?", "Không có dòng JSON hỏng; luật vẫn chạy và tô đỏ trên Monitoring nếu có."),
         (f"Sao vẫn {n(integ['output']['rows'])} dòng?", "Integration không bỏ tin, chỉ đổi dạng.")],
        ["reports/preprocessing/02_integration/_all.json", "preprocessing/integration/json_flattener.py"],
        conclusion="Từ đây mọi nguồn dùng chung một schema → các bước sau xử lý một lần cho cả 8 nguồn.",
        tag="Bước 2"))

    # 12. Transformation
    tr = reports["03_transformation"]
    out.append(slide(
        "3. Transformation: bóc lương, ngôn ngữ, địa điểm",
        '<div class="two">' + chart_box(pair_bar([
            ("Lương lấy từ tiêu đề", before["salary_from_title"], after["salary_from_title"]),
            ("Lương tháng > 500 triệu", before["salary_over_500m"], after["salary_over_500m"]),
            ("Lương tháng < 1 triệu", before["salary_under_1m"], after["salary_under_1m"]),
            ("Nhãn ngôn ngữ 'bilingual'", before["lang_bilingual"], after["lang_bilingual"]),
            ("Tin JD tiếng Anh (en)", before["lang_en"], after["lang_en"]),
            ("Phường/xã còn ngoặc, quận cũ", before["ward_dirty"], after["ward_dirty"]),
        ], "Số tin", "Chỉ số", ("Trước sửa review", "Sau sửa"), w=700, label_w=200, bar=26), "before_review.json và 04_normalization/all.parquet")
        + f'<div class="facts"><div><b>{n(after["lang_en"])}</b><span>JD tiếng Anh: &lt; 1% chữ có dấu tiếng Việt</span></div>'
          f'<div><b>{n(after["jobs_with_ward"])}</b><span>tin có phường/xã khớp danh mục 3.321</span></div>'
          f'<div><b>{n(after["lang_vi"])} : {n(after["lang_en"])}</b><span>JD tiếng Việt : tiếng Anh, giữ nguyên không dịch</span></div></div></div>',
        ["Biểu đồ so cùng dữ liệu trước và sau khi sửa các lỗi tìm được khi review.",
         f"Lương chỉ lấy từ tiêu đề khi có đơn vị tiền, nên từ {n(before['salary_from_title'])} còn {n(after['salary_from_title'])} tin, bỏ các số trong mã tin, năm.",
         "Ngôn ngữ chỉ xét JD: dưới 1% chữ có dấu tiếng Việt là tiếng Anh; bỏ nhãn bilingual.",
         "Phường/xã chỉ nhận khi có trong danh mục mới của đúng tỉnh."],
        [("Sao không dịch JD tiếng Anh?", "Dự án không dùng model; từ điển kỹ năng song ngữ nên JD tiếng Anh vẫn rút được kỹ năng, cột language cho biết ngôn ngữ."),
         ("Sao tiếng Anh tăng?", f"{n(before['lang_bilingual'])} tin bilingual cũ được xếp lại theo JD; phần lớn là tiếng Việt có vài từ tiếng Anh."),
         ("Ngưỡng 1% ở đâu ra?", "Để chịu được tiêu đề mục song ngữ kiểu 'Bằng cấp / Education' trong JD tiếng Anh.")],
        ["reports/preprocessing/03_transformation/_all.json → rules T2–T8, extra.language_distribution", "docs/presentation/data/before_review.json"],
        conclusion=f"Không còn lương sai đơn vị; {n(after['lang_en'])} JD tiếng Anh được nhận đúng và vẫn rút được kỹ năng.",
        tag="Bước 3"))

    # 13. Normalization
    order = ["Thực tập", "Mới tốt nghiệp", "Junior", "Middle", "Senior", "Trưởng nhóm/Quản lý", "Không rõ"]
    sb, sa = before["seniority"], after["seniority"]
    out.append(slide(
        "4. Normalization: cấp bậc, nhóm nghề, kỹ năng chuẩn",
        '<div class="two">' + chart_box(pair_bar([(k, 100 * sb.get(k, 0) / before["rows"], 100 * sa.get(k, 0) / after["rows"]) for k in order],
                                                 "Tỉ lệ tin (%)", "Cấp bậc chuẩn", ("Trước sửa review", "Sau sửa"), w=660, label_w=160, fmt=lambda v: pct(v, 1), bar=22),
                                        "seniority trong before_review.json và 04_normalization/all.parquet")
        + f'<div class="facts"><div><b>{n(before["skill_c"])} → {n(after["skill_c"])}</b><span>tin có kỹ năng "C" (bỏ khớp chữ C đơn lẻ)</span></div>'
          f'<div><b>{n(ra("N2b"))}</b><span>tin có nhãn mâu thuẫn kinh nghiệm/kỹ năng, gắn cờ cần kiểm</span></div>'
          f'<div><b>{n(ra("N6"))}</b><span>lương ngoại lai IQR (N6)</span></div></div></div>',
        [f"Trước đây {pct(100 * sb.get('Middle', 0) / before['rows'], 0)} tin bị xếp Middle vì 'Nhân viên' bị hiểu là Middle; giờ còn {pct(100 * sa.get('Middle', 0) / after['rows'], 1)}.",
         "Không xác định được cấp bậc thì để trống, không đoán.",
         f"Kỹ năng C trước khớp cả chữ C đơn lẻ nên có ở {n(before['skill_c'])} tin; nay chỉ nhận C/C++, 'ngôn ngữ C'.",
         f"Luật mâu thuẫn gắn cờ {n(ra('N2b'))} tin: Senior mà dưới 2 năm kinh nghiệm, Thực tập mà từ 3 năm, hoặc có nhóm nghề mà JD không có kỹ năng nào."],
        [("Sao 'Không rõ' nhiều?", f"{n(sa.get('Không rõ', 0))} tin không ghi cấp bậc ở raw, tiêu đề hay số năm kinh nghiệm; để trống trung thực hơn đoán."),
         ("12 nhóm nghề gồm gì?", "Backend, Frontend, Fullstack, Mobile, Data/AI, DevOps/Cloud, QA/QC, Bảo mật, Hệ thống/Mạng, BA, PM, UI/UX; còn lại là Khác."),
         ("IQR làm gì?", f"Lương ngoài [Q1 − 1,5·IQR; Q3 + 1,5·IQR] gắn cờ is_outlier_salary ({n(ra('N6'))} tin), không xóa.")],
        ["reports/preprocessing/04_normalization/_all.json → rules N1–N7", "data/preprocessing/04_normalization/all.parquet (cột seniority, skills_std)"],
        conclusion="Phân bố cấp bậc hợp lý lại (Middle không còn chiếm đa số) → số liệu theo cấp bậc dùng phân tích được.",
        tag="Bước 4"))

    # 14. Encoding
    enc = reports["05_encoding"]
    ft = enc["extra"]["feature_types"]
    VI = {"id_columns": "Khóa", "ordinal_columns": "Thứ bậc (cấp bậc)", "one_hot_columns": "One-hot (nhóm nghề, nguồn…)",
          "multi_hot_columns": "Multi-hot (tỉnh, kỹ năng)", "continuous_numeric_columns": "Số liên tục (lương, năm KN)",
          "missing_indicator_columns": "Cờ thiếu giá trị", "rule_flag_columns": "Cờ của luật (tầng 2, mâu thuẫn)"}
    out.append(slide(
        "5. Encoding: bảng đặc trưng cho mô hình",
        '<div class="two"><div>' + chart_box(hbar(sorted(((VI.get(k, k), len(v)) for k, v in ft.items()), key=lambda x: -x[1]),
                                             "Số cột", "Loại đặc trưng", w=640, label_w=220, bar=34), "05_encoding/_all.json → extra.feature_types")
        + '<p class="legend">Cột đặc trưng = một biến số mà mô hình đọc được, ví dụ skill__python = 1 nếu tin cần Python, tinh__ha_noi = 1 nếu tin ở Hà Nội.</p></div>'
        + f'<div class="facts"><div><b>{n(enc["extra"]["total_columns"])}</b><span>cột trong features.parquet</span></div>'
          f'<div><b>{n(enc["extra"]["encoded_skills_count"])}</b><span>kỹ năng phổ biến nhất được mã hóa</span></div>'
          f'<div><b>{pct(enc["extra"]["skills_sparsity"])}</b><span>độ thưa ma trận kỹ năng</span></div></div></div>',
        ["Mô hình chỉ đọc được số, nên bước cuối đổi mọi trường thành các cột số; mỗi cột như vậy gọi là một cột đặc trưng.",
         "Cấp bậc là thứ bậc 0–5, chưa rõ là −1; nhóm nghề one-hot; tỉnh và kỹ năng multi-hot.",
         "Trường số giữ nguyên và có cờ thiếu giá trị đi kèm."],
        [("Sao chỉ 200 kỹ năng?", "Lấy kỹ năng phổ biến nhất để ma trận không quá thưa; danh sách trong encoding_dictionary.json."),
         (f"Độ thưa {pct(enc['extra']['skills_sparsity'], 0)} có sao không?", "Bình thường với multi-hot kỹ năng; mô hình dùng ma trận thưa.")],
        ["reports/preprocessing/05_encoding/_all.json", "data/preprocessing/05_encoding/features.parquet, encoding_dictionary.json"],
        conclusion=f"Đầu ra cuối là bảng {n(enc['output']['rows'])} dòng × {n(enc['extra']['total_columns'])} cột, lưu tầng gold trên R2.",
        tag="Bước 5"))

    # Đối chiếu vấn đề ↔ cách giải (bằng lời, số là kết quả thật)
    trs = "".join(
        f'<tr><td>{esc(nm)}</td><td>{esc(", ".join(str(list(STEP_OF.values()).index(x) + 1) for x in steps_of(c)))}</td><td>{esc(SOLVE[c][0])}</td>'
        f'<td class="n"><b>{n(sum(ra(r) for r in SOLVE[c][1]))}</b> {esc(SOLVE[c][2])}</td></tr>'
        for c, (nm, sv) in ISSUES.items())
    out.append(slide(
        "Đối chiếu: vấn đề nào được giải ở bước nào",
        f'<table class="matrix sol"><thead><tr><th>Vấn đề</th><th>Bước số</th><th>Cách giải</th><th>Kết quả</th></tr></thead><tbody>{trs}</tbody></table>',
        ["Bảng đọc theo hai chiều: mỗi vấn đề ở slide 4 đều có bước giải, và mọi luật trong 5 bước đều giải ít nhất một vấn đề.",
         "Cột kết quả là số tin thật mà bước đó bỏ hoặc sửa, lấy từ báo cáo của bước."],
        [("Kết quả lấy từ đâu?", "rows_affected của luật trong reports/preprocessing/<bước>/_all.json; mã luật: " +
          "; ".join(f"{c}: {', '.join(SOLVE[c][1])}" for c in ISSUES) + "."),
         ("Có luật nào bằng 0?", "C3 (bản ghi lỗi) và I0 (JSON hỏng) bằng 0: luật chặn an toàn, lần chạy này không gặp bản ghi lỗi."),
         ("Làm sao chắc không sót?", "Hàm check_links() trong build_slides.py so bảng vấn đề với danh sách luật của 5 báo cáo; lệch thì không tạo slide.")],
        ["scripts/build_slides.py → ISSUE_TO_RULES, SOLVE, check_links()", "reports/preprocessing/<bước>/_all.json → rules[].rows_affected"]))

    # Đánh giá (1): ưu điểm, mỗi điểm có số kiểm được
    l2 = pct(100 * review["level2_correct"] / max(review["level2_labeled"], 1))
    l2_err = pct(100 - 100 * review["level2_correct"] / max(review["level2_labeled"], 1), 0)
    conserved = sum(1 for st in STEPS if reports[st]["checks"].get("rows_conserved"))
    pros = [
        (f"{conserved}/{len(STEPS)}", "Truy vết được", "Bước nào cũng bảo toàn dòng: số vào = số ra + số bỏ; mỗi dòng bị bỏ có luật và lý do"),
        (f"{n(review['rule_correct'])}/{n(review['rule_decided'])}", "Luật được kiểm chứng", f"Lọc IT tầng 1 đo trên {n(review['labeled'])} tin gán nhãn tay, không đặt theo cảm tính"),
        (f"{n(bad_sal)} → {n(now_bad)}", "Sửa lỗi gốc", f"Lương sai đơn vị; Middle từ {pct(100 * sb.get('Middle', 0) / before['rows'], 1)} về {pct(100 * sa.get('Middle', 0) / after['rows'], 1)}"),
        ("0", "Không bịa dữ liệu", "Thiếu thì để trống + cờ; ngoại lai gắn cờ, không xóa, không bù trung bình"),
        ("0", "Không phụ thuộc model", "Toàn bộ là luật if-else: chạy lại ra cùng kết quả, không tốn tiền API"),
        ("1 lệnh", "Chạy lại được", f"Cả pipeline và mọi số trên slide sinh tự động; {storage['silver'] + storage['gold']} object silver/gold trên R2"),
    ]
    out.append(slide(
        "Ưu điểm",
        '<div class="center"><div class="pros">' + "".join(f"<div><b>{esc(v)}</b><strong>{esc(t)}</strong><span>{esc(d)}</span></div>" for v, t, d in pros) + "</div></div>",
        ["Trước hết là sáu điểm mạnh; điểm nào cũng có con số kiểm được.",
         "Quan trọng nhất là truy vết: báo cáo mỗi bước ghi số vào bằng số ra cộng số bỏ, nên không có dòng nào mất mà không rõ lý do.",
         f"Luật lọc IT không đặt theo cảm tính: tầng 1 đúng {n(review['rule_correct'])}/{n(review['rule_decided'])} tin trên mẫu gán nhãn tay.",
         "Các lỗi gốc như lương sai đơn vị và cấp bậc lệch về Middle đã sửa tận gốc ở bộ parse, không vá tay.",
         "Thiếu thì để trống và gắn cờ, không bù số giả; và toàn bộ là luật if-else nên ai chạy lại cũng ra đúng số này."],
        [("Bảo toàn dòng kiểm ở đâu?", "Trường checks.rows_conserved trong mỗi reports/preprocessing/<bước>/_all.json, cả 5 bước đều true."),
         ("Sao không bù giá trị thiếu?", "Bù sẽ tạo số giả, nhất là nhãn lương; giữ trống và có cột cờ thiếu giá trị ở bước Encoding."),
         ("Chạy lại toàn bộ thế nào?", "python scripts/run_preprocessing.py --step all --source all, rồi python scripts/build_slides.py.")],
        ["reports/preprocessing/<bước>/_all.json → checks.rows_conserved", "reports/preprocessing/01_clean/_all.json → extra.review",
         "docs/presentation/data/raw_issues_before.json, before_review.json (số trước sửa)"],
        conclusion="Kết quả xử lý kiểm chứng được bằng số và chạy lại được, không dựa vào cảm tính."))

    out[-1]["todo"] = [
        f"Luật IT tầng 2 đúng {l2} ({n(review['level2_correct'])}/{n(review['level2_labeled'])} tin gán nhãn); gán thêm nhãn tay để chỉnh luật nếu cần độ đúng cao hơn.",
        "TopDev: cần cào lại để có ngày đăng, kinh nghiệm; crawler cũng đang cào cả tin ngoài IT vì API bỏ qua bộ lọc ngành.",
        f"ITviec giữ mọi tin theo chính sách đã duyệt, kể cả {n(after['it_status'].get('non_it', 0))} tin luật xếp ngoài IT.",
        f"Mô hình: chờ thầy chọn hướng cho lương thiếu ({pct(100 * (after['rows'] - after['salary_any']) / after['rows'], 0)}), độ đúng luật IT, nhóm nghề 'Khác' ({pct(100 * after['family_khac'] / after['rows'], 0)}), giảm chiều, lệch vùng (PRE-11).",
        "Mức Cao/TB/Thấp của các nhóm thiếu trường, địa điểm, cấp bậc, kỹ năng, ngày, văn bản là tự đánh giá; tài liệu gốc chưa ghi.",
    ]

    # Đánh giá (2): nhược điểm = lỗ hổng còn lại cho bước mô hình
    N = after["rows"]
    gaps = [("Thiếu lương (thỏa thuận)", N - after["salary_any"]), ("Nhóm nghề 'Khác'", after["family_khac"]),
            ("Tin IT do luật tầng 2 quyết", after["level2_kept"] or 0), ("JD tiếng Anh (không dịch)", after["lang_en"]),
            ("Cấp bậc không rõ", after["seniority"].get("Không rõ", 0))]
    gaps.sort(key=lambda x: -x[1])
    out.append(slide(
        "Nhược điểm: dữ liệu còn 5 lỗ hổng",
        '<div class="two">' + chart_box(hbar([(k, 100 * v / N) for k, v in gaps], f"Tỉ lệ tin bị ảnh hưởng (% trên {n(N)} tin)", "Lỗ hổng",
                                             w=700, label_w=220, bar=44, fmt=lambda v: pct(v, 1), vmax=100), "04_normalization/all.parquet")
        + f'<div class="facts"><div><b>{pct(100 * after["city_top2"] / N, 0)}</b><span>tin ở Hà Nội + TP.HCM</span></div>'
          f'<div><b>{n(max(after["by_source"].values()))} : {n(min(after["by_source"].values()))}</b><span>tin nguồn nhiều nhất : ít nhất</span></div>'
          f'<div><b>{n(enc["extra"]["total_columns"])} cột</b><span>ma trận kỹ năng thưa {pct(enc["extra"]["skills_sparsity"])}</span></div></div></div>',
        [f"Ngược lại, em cũng nói thẳng nhược điểm: dữ liệu đưa vào mô hình còn năm lỗ hổng, đo trên cùng bảng {n(N)} tin.",
         f"Lớn nhất là lương: {pct(100 * (N - after['salary_any']) / N, 0)} tin để lương thỏa thuận, nên mô hình lương chỉ có {n(after['salary_any'])} tin có nhãn.",
         f"Nhóm nghề 'Khác' chiếm {pct(100 * after['family_khac'] / N, 0)}; {n(after['level2_kept'] or 0)} tin là IT do luật tầng 2 quyết, độ đúng thấp hơn tầng 1.",
         "Dữ liệu cũng lệch: tập trung ở Hà Nội, TP.HCM và vài nguồn lớn.",
         "Slide sau là việc em sẽ làm cho từng lỗ hổng."],
        [("Sao không bù lương thiếu luôn?", "Bù bằng trung bình sẽ tạo nhãn giả cho mô hình lương; em muốn thầy chọn hướng ở slide xin ý kiến."),
         ("'Khác' gồm gì?", "Tin IT không khớp 12 nhóm theo luật tiêu đề, ví dụ IT support, ERP, kỹ sư nhúng; xem cột job_family trong all.parquet."),
         ("Lệch vùng có sao không?", "Mô hình sẽ học chủ yếu thị trường Hà Nội, TP.HCM; kết luận cho tỉnh khác kém tin cậy.")],
        ["data/preprocessing/04_normalization/all.parquet → salary_min_vnd/salary_max_vnd, job_family, it_rule_level, language, seniority, tinh_chinh, source_platform",
         "reports/preprocessing/05_encoding/_all.json → extra.total_columns, extra.skills_sparsity"],
        conclusion=f"Lỗ hổng lớn nhất là lương ({pct(100 * (N - after['salary_any']) / N, 0)} thiếu) → cần chốt cách xử lý trước khi chọn mô hình."))

    # Đánh giá (3): hướng khắc phục, mỗi dòng có cách đo đã xong
    pN = lambda v: pct(100 * v / N, 0)  # noqa: E731
    fixes = [
        (f"Thiếu lương {pN(N - after['salary_any'])}", "Mô hình lương chỉ học trên tin có lương; cờ lương thỏa thuận làm đặc trưng", f"{n(after['salary_any'])} nhãn thật, 0 nhãn bù"),
        (f"Luật IT tầng 2 đúng {l2}", "Gán thêm nhãn tay cho tin tầng 2 quyết, chỉnh từ khóa và ngưỡng kỹ năng", "Độ đúng tầng 2 trên nhãn mới"),
        (f"Nhóm nghề 'Khác' {pN(after['family_khac'])}", "Thêm nhóm Nhúng, IT Support, ERP vào luật tiêu đề", "Tỉ lệ 'Khác' giảm"),
        (f"JD tiếng Anh {pN(after['lang_en'])}", "Bổ sung từ khóa tiếng Anh cho luật nhóm nghề, cấp bậc (kỹ năng đã song ngữ)", "Không cần dịch, không model"),
        (f"Cấp bậc không rõ {pN(after['seniority'].get('Không rõ', 0))}", "Giữ −1 và cờ thiếu; không đoán từ tiêu đề mơ hồ", "0 nhãn đoán"),
        ("TopDev thiếu trường", "Sửa crawler lọc IT, cào lại ngày đăng, kinh nghiệm", "TopDev đủ 2 trường"),
        (f"Lệch vùng {pN(after['city_top2'])} HN + TP.HCM", "Chia tầng theo tỉnh và nguồn khi tách train/test", "Đánh giá theo từng vùng"),
    ]
    out.append(slide(
        "Hướng khắc phục",
        '<table class="matrix fix"><thead><tr><th>Nhược điểm</th><th>Việc sẽ làm</th><th>Đo kết quả</th></tr></thead><tbody>'
        + "".join(f'<tr><td><b>{esc(a)}</b></td><td>{esc(b)}</td><td class="n">{esc(c)}</td></tr>' for a, b, c in fixes) + "</tbody></table>",
        ["Mỗi dòng là một nhược điểm, việc cụ thể em sẽ làm, và con số để biết đã xong.",
         f"Lương: không bù trung bình vì sẽ tạo nhãn giả; mô hình lương học trên {n(after['salary_any'])} tin có lương.",
         f"Luật IT tầng 2 còn sai khoảng {l2_err}: cách sửa là gán thêm nhãn tay rồi chỉnh luật, vẫn không dùng model.",
         "Hai việc này làm trước vì chúng quyết định nhãn của mô hình; vài hướng em chưa chắc nên xin ý kiến thầy ở slide sau."],
        [("Tin bị bỏ nhầm thì sao?", "Danh sách tin bị bỏ nằm trong báo cáo Clean (C4c); gán thêm nhãn tay vào data/preprocessing/review/ rồi chỉnh luật tầng 2."),
         ("Sao không dịch JD tiếng Anh?", "Từ điển kỹ năng có cả tiếng Anh và tiếng Việt nên vẫn rút được kỹ năng; dịch cần model, dự án đã bỏ model."),
         (f"{n(enc['extra']['total_columns'])} cột thưa {pct(enc['extra']['skills_sparsity'], 1)} thì sao?", "Mô hình dùng ma trận thưa; nếu cần thì giảm chiều bằng SVD hoặc chỉ giữ top 50 kỹ năng.")],
        ["data/preprocessing/04_normalization/all.parquet → salary_min_vnd, job_family, it_rule_level, language, seniority, tinh_chinh",
         "reports/preprocessing/01_clean/_all.json → extra.review"],
        conclusion="Ưu tiên lương và luật IT tầng 2 vì ảnh hưởng trực tiếp đến nhãn mô hình."))

    # 18. Câu hỏi xin ý kiến thầy
    asks = [
        ("Lương thiếu", f"{n(N - after['salary_any'])} tin thỏa thuận", f"Chỉ học trên {n(after['salary_any'])} tin có lương", "Bù theo nhóm nghề + cấp bậc"),
        ("Luật IT đúng " + l2, f"{n(after['level2_kept'] or 0)} tin do tầng 2 quyết", "Chấp nhận, ghi rõ sai số", "Gán thêm nhãn tay để chỉnh luật"),
        ("Nhóm nghề 'Khác'", f"{n(after['family_khac'])} tin", "Giữ là một lớp riêng", "Thêm từ khóa nhóm nghề từ tin 'Khác'"),
        (f"{n(enc['extra']['total_columns'])} cột, thưa {pct(enc['extra']['skills_sparsity'], 0)}", "multi-hot kỹ năng", "Giảm chiều (PCA, SVD)", "Bớt kỹ năng, chỉ giữ top 50"),
        ("Lệch vùng, nguồn", f"{pct(100 * after['city_top2'] / N, 0)} ở HN + TP.HCM", "Đặt trọng số mẫu", "Chia tầng khi tách train/test"),
    ]
    cards = "".join(f'<div class="ask"><b>{i}. {esc(t)}</b><span class="num">{esc(v)}</span>'
                    f'<div class="opt"><i>A</i>{esc(a)}</div><div class="opt"><i>B</i>{esc(b)}</div></div>'
                    for i, (t, v, a, b) in enumerate(asks, 1))
    out.append(slide(
        "Xin ý kiến thầy: chọn hướng xử lý trước khi làm mô hình",
        f'<div class="center"><div class="asks">{cards}</div></div>',
        ["Đây là các hướng em chưa tự quyết được: mỗi thẻ là một lỗ hổng, kèm hai hướng em đang cân nhắc.",
         "Em muốn thầy góp ý hướng nào hợp với mục tiêu đề tài, hoặc gợi ý hướng khác.",
         "Câu em ưu tiên hỏi nhất là số 1 (lương) và số 2 (độ đúng luật IT), vì ảnh hưởng trực tiếp đến dữ liệu đưa vào mô hình."],
        [("Em định dùng mô hình gì?", "Còn tùy hướng xử lý: dự đoán lương là hồi quy; phân nhóm nghề là phân loại; khai phá kỹ năng có thể dùng luật kết hợp."),
         ("Em nghiêng về hướng nào?", f"Lương: A, học trên tin có lương để khỏi nhãn giả. Luật IT: A nếu thầy chấp nhận sai số khoảng {pct(100 - 100 * review['level2_correct'] / max(review['level2_labeled'], 1), 0)}, B nếu cần chính xác hơn."),
         ("Sao không làm cả hai rồi so?", "Được, nếu thầy đồng ý thì em chạy cả A và B rồi báo cáo chênh lệch.")],
        ["data/preprocessing/04_normalization/all.parquet", "data/preprocessing/05_encoding/features.parquet, encoding_dictionary.json",
         "reports/preprocessing/01_clean/_all.json → extra.review"]))

    # Kết luận + cảm ơn (Q&A của slide này cũng là câu chốt cuối buổi)
    out.append(slide(
        "Kết luận",
        '<div class="concl-list">'
        f'<div><i>1</i><p><b>{n(clean["input"]["rows"])} → {n(clean["output"]["rows"])}</b> bản ghi raw thành tin IT sạch, {n(enc["extra"]["total_columns"])} cột đặc trưng</p></div>'
        f'<div><i>2</i><p><b>{len(ISSUES)}/{len(ISSUES)}</b> nhóm vấn đề có luật if-else xử lý, kiểm được bằng số trong báo cáo</p></div>'
        '<div><i>3</i><p><b>Bước tiếp:</b> dự đoán lương, phân loại nhóm nghề, luật kết hợp kỹ năng</p></div>'
        '</div><p class="thanks">Em cảm ơn thầy và các bạn đã lắng nghe</p>',
        [f"Tóm lại, từ {n(clean['input']['rows'])} bản ghi raw của 8 trang, em thu được {n(clean['output']['rows'])} tin IT sạch với {n(enc['extra']['total_columns'])} cột đặc trưng.",
         f"Cả {len(ISSUES)} nhóm vấn đề đều có luật xử lý, số liệu kiểm được trong báo cáo từng bước và trên Monitoring.",
         "Bước tiếp theo là mô hình: hồi quy cho lương, phân loại cho nhóm nghề, luật kết hợp cho kỹ năng, theo hướng thầy góp ý.",
         "Phần trình bày của em đến đây là hết. Em cảm ơn thầy và các bạn đã lắng nghe, em xin nhận câu hỏi và góp ý."],
        [("Em định dùng mô hình gì?", "Dự đoán lương là hồi quy; phân nhóm nghề là phân loại; khai phá kỹ năng dùng luật kết hợp (Apriori/FP-Growth)."),
         ("Cho thầy xem dữ liệu thật?", "./start_monitoring.sh, mở http://127.0.0.1:5173: trang Raw cho bronze, trang Pre-processing cho silver/gold, bấm một dòng để xem đủ trường.")],
        ["reports/preprocessing/01_clean/_all.json (input.rows, output.rows)", "reports/preprocessing/05_encoding/_all.json (extra.total_columns)"]))
    add_sections(out)
    return out


SECTIONS = [  # (tên phần, slide bắt đầu, lời mở phần, mô tả trên slide Bố cục)
    ("Vấn đề dữ liệu", lambda s: s["title"].startswith("Dữ liệu vào"),
     "Phần 1 là vấn đề dữ liệu: trước khi xử lý, em đo xem raw sai ở đâu và sai bao nhiêu.", "11 nhóm vấn đề đo trên raw, kèm ví dụ thật"),
    ("Quy trình xử lý", lambda s: s["title"].startswith("Pipeline"),
     "Phần 2 là quy trình: 5 bước nối tiếp, mỗi bước giải một số vấn đề vừa nêu.", "Clean → Encoding, số dòng và luật mỗi bước"),
    ("Đánh giá", lambda s: s["title"] == "Ưu điểm",
     "Phần 3, em tự đánh giá kết quả: ưu điểm, nhược điểm và hướng khắc phục.", "Ưu điểm, nhược điểm, hướng khắc phục, xin ý kiến"),
]


def add_sections(out: list) -> None:
    """Gắn tên phần (kicker) cho slide, thêm lời mở phần, chèn slide Bố cục sau slide tiêu đề."""
    starts = [next(i for i, s in enumerate(out) if match(s)) for _, match, _, _ in SECTIONS]
    for (name, _, intro, _), i in zip(SECTIONS, starts):
        out[i]["say"].insert(0, intro)
        for s in out[i:]:
            s["sec"] = name
    ends = [x - 1 for x in starts[1:]] + [len(out) - 1]
    cards = "".join(f'<div><i>0{k}</i><b>{esc(name)}</b><span>{esc(desc)}</span><em>Slide {a + 2}–{b + 2}</em></div>'
                    for k, ((name, _, _, desc), a, b) in enumerate(zip(SECTIONS, starts, ends), 1))
    agenda = slide("Bố cục bài trình bày", f'<div class="agenda">{cards}</div>',
                   ["Bài gồm ba phần: vấn đề của dữ liệu raw, quy trình 5 bước xử lý, và tự đánh giá kết quả.",
                    "Mỗi bước xử lý đều chỉ rõ nó giải vấn đề nào ở phần 1; phần đánh giá nêu cả ưu điểm lẫn nhược điểm, kèm việc cụ thể để khắc phục.",
                    "Cuối bài em có vài câu muốn xin ý kiến thầy trước khi làm mô hình."],
                   [("Trình bày bao lâu?", "Khoảng 1 phút mỗi slide; phần vấn đề và quy trình là chính, phần đánh giá ngắn hơn.")],
                   ["scripts/build_slides.py → SECTIONS"])
    agenda["sec"] = "Nội dung"
    out.insert(1, agenda)


CSS = """
:root{--ink:#1F2933;--muted:#52606D;--line:#D9E2EC;--bg:#E9EEF3;--paper:#FFFFFF;--accent:#1D4ED8}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);font-family:"Times New Roman",Times,serif}
#deck{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}
.s{position:absolute;width:1280px;height:720px;background:var(--paper);padding:34px 48px 26px;display:none;flex-direction:column;
   box-shadow:0 6px 30px rgba(31,41,51,.15);transform-origin:center}
.s.on{display:flex}
.s h1{font-size:38px;margin:0 0 14px;line-height:1.15;color:#102A43}
.s .tag{position:absolute;top:30px;right:48px;font-size:18px;color:var(--accent);border:1.5px solid var(--accent);border-radius:6px;padding:2px 10px}
.body{flex:1;min-height:0}
.center{display:flex;flex-direction:column;justify-content:center;height:100%}
.concl{margin-top:8px;font-size:22px;font-weight:bold;border-left:6px solid var(--accent);background:#EFF4FF;padding:8px 14px;border-radius:0 6px 6px 0}
.pg{position:absolute;bottom:8px;right:20px;font-size:14px;color:var(--muted)}
.two{display:flex;gap:28px;align-items:flex-start;height:100%}.two figure{flex:none}
.two.wide figure{flex:1}
figure{margin:0}figcaption{font-size:13px;color:var(--muted);margin-top:2px}
.facts{display:flex;flex-direction:column;gap:14px;flex:1;min-width:0}
.facts>div{border:1px solid var(--line);border-radius:8px;padding:10px 14px;background:#F8FAFC}
.facts b{display:block;font-size:28px;color:#102A43}.facts span{font-size:18px;color:var(--muted)}
.facts .ex ul{margin:4px 0 0;padding-left:20px;font-size:17px}
.chart text{font-family:"Times New Roman",Times,serif}.chart .lab{font-size:16px;fill:#243B53}.chart .val{font-size:15px;fill:#102A43;font-weight:bold}
.chart .tick{font-size:13px;fill:#52606D}.chart .atitle{font-size:15px;fill:#243B53;font-style:italic}
.chart .grid{stroke:#E4E7EB}.chart .axis{stroke:#7B8794;stroke-width:1.2}
.hero{display:flex;flex-direction:column;justify-content:center;height:100%;gap:26px}
.s:first-child h1{font-size:58px;margin-top:120px}
.hero .sub{font-size:28px;color:var(--muted);margin:0}.hero .date{font-size:18px;color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
.kpis div{border-top:5px solid var(--accent);background:#F8FAFC;padding:16px}.kpis b{display:block;font-size:44px}.kpis span{font-size:20px;color:var(--muted)}
.igrid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.icard{border:1.5px solid;border-left-width:6px;border-radius:8px;padding:12px 14px;font-size:18px;min-height:150px}.icard p{margin:6px 0;font-size:21px;line-height:1.2}
.icard b{font-size:20px}.to{font-size:17px}.ev{font-size:19px;color:#1D4ED8;font-weight:bold;margin-top:4px}
.matrix.ex td{font-size:19px;vertical-align:top}.matrix.sal td,.matrix.sal th{font-size:17px}.matrix .bad{color:#B42318}.matrix .good{color:#067647;font-weight:bold}.matrix td.n{white-space:nowrap}
.cmps{display:grid;grid-template-columns:1fr 1fr;gap:16px}.cmp{border:1px solid var(--line);border-radius:8px;padding:10px 14px;background:#F8FAFC}
.cmp b{font-size:22px;display:block;margin-bottom:4px}.cmp div{font-size:18px;line-height:1.45;overflow-wrap:anywhere}
.cmp span{display:inline-block;width:118px;color:var(--muted)}
.facts.tight{gap:8px}.facts.tight>div{padding:6px 12px}.facts.tight b{font-size:22px}.facts.tight span{font-size:16px}
.matrix.sol td,.matrix.sol th{font-size:18px;padding:6px 8px}
.matrix.where td{font-size:18px;vertical-align:top}.matrix.where code{font-size:15px;overflow-wrap:anywhere}.matrix small{color:var(--muted);font-size:15px}
.sev{color:#fff;border-radius:4px;padding:0 7px;font-size:14px;font-weight:bold}
.rule{display:inline-block;border:1px solid var(--accent);color:var(--accent);border-radius:4px;padding:0 5px;margin:1px;font-size:14px}
.rule small{color:var(--ink)}
.legend{font-size:15px;color:var(--muted);margin-top:10px}
.heat{border-collapse:collapse;font-size:12.5px}.heat td,.heat th{border:1px solid #fff;padding:1px 5px;text-align:center}
.heat th.f{text-align:left;font-weight:normal;font-size:13px}.heat thead th{font-size:12.5px;background:#F0F4F8}
.keep{color:#067647}.drop{color:#B42318}
.grid4{display:grid;grid-template-columns:1fr 1fr;gap:4px 30px}
.flow{display:flex;gap:14px;margin:40px 0 40px}.step{flex:1;border:2px solid var(--accent);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:6px;
  font-size:18px;position:relative;background:#F8FAFC}.step b{font-size:22px}.step .rows{font-size:24px;font-weight:bold;color:#102A43}.step .solves{color:#B54708}
.step:not(:last-child)::after{content:"→";position:absolute;right:-12px;top:40%;font-size:22px;color:var(--accent)}
.layers{display:flex;gap:14px}.layers div{flex:1;border-radius:8px;padding:12px 16px;font-size:19px}.layers b{display:block;font-size:24px}
.layers div:nth-child(1){background:#F6EEE3}.layers div:nth-child(2){background:#EEF2F6}.layers div:nth-child(3){background:#FBF3D5}
.matrix{border-collapse:collapse;width:100%;font-size:20px}.matrix th,.matrix td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left}
.matrix .rule{font-size:17px}
.matrix thead th{background:#F0F4F8}
.todo{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.todo div{border:1.5px solid #B54708;border-radius:8px;padding:12px 16px;background:#FFFAF0}
.todo b{display:block;font-size:28px;color:#B54708}.todo span{font-size:22px}
.end{font-size:28px;line-height:1.6;margin-top:40px}
.asks{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.ask{border:1.5px solid var(--accent);border-radius:10px;padding:18px 18px;min-height:240px;justify-content:center;background:#F8FAFC;display:flex;flex-direction:column;gap:6px}
.ask b{font-size:23px;color:#102A43}.ask .num{font-size:18px;color:#B54708}
.opt{font-size:19px;display:flex;gap:8px;align-items:baseline}.opt i{font-style:normal;font-weight:bold;color:#fff;background:var(--accent);border-radius:4px;padding:0 7px}
#notes{position:fixed;left:0;right:0;bottom:0;max-height:46vh;overflow:auto;background:#FFFDF5;border-top:3px solid #B54708;padding:12px 24px;
  font-size:17px;display:none;z-index:5}#notes.on{display:block}#notes h3{margin:6px 0;font-size:18px;color:#B54708}
#notes code{font-size:14px;background:#F0F4F8;padding:1px 4px}
#help{position:fixed;bottom:6px;left:10px;font-size:13px;color:var(--muted)}
.printnotes{display:none}
.kicker{position:absolute;top:10px;right:48px;margin:0;font-size:14px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);font-weight:bold}
.prog{position:absolute;left:0;bottom:0;height:5px;background:var(--accent)}
.agenda{display:grid;grid-template-columns:repeat(3,1fr);gap:26px;height:100%;align-items:center}
.agenda div{border-top:6px solid var(--accent);background:#F5F8FC;border-radius:0 0 10px 10px;padding:28px 26px;display:flex;flex-direction:column;gap:10px;min-height:300px}
.agenda i{font-style:normal;font-size:56px;font-weight:bold;color:#C7D4EA;line-height:1}
.agenda b{font-size:30px;color:#102A43}.agenda span{font-size:21px;color:var(--muted)}.agenda em{margin-top:auto;font-style:normal;font-size:17px;color:var(--accent)}
.pros{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.pros div{border-top:5px solid #067647;background:#F3FAF6;border-radius:0 0 10px 10px;padding:18px 20px;display:flex;flex-direction:column;gap:4px;min-height:200px}
.pros b{font-size:44px;color:#067647;line-height:1.1}.pros strong{font-size:23px;color:#102A43}.pros span{font-size:18px;color:var(--muted);line-height:1.35}
.matrix.fix th,.matrix.fix td{font-size:21px;padding:14px 10px;vertical-align:top}.matrix.fix td:first-child b{color:#B42318}
.matrix.fix td.n{color:#067647;font-weight:bold;white-space:normal}
.concl-list{display:flex;flex-direction:column;gap:22px;margin-top:40px}
.concl-list div{display:flex;align-items:center;gap:22px}
.concl-list i{flex:none;width:54px;height:54px;border-radius:50%;background:var(--accent);color:#fff;font-style:normal;font-size:28px;font-weight:bold;display:flex;align-items:center;justify-content:center}
.concl-list p{margin:0;font-size:28px}.concl-list b{color:#102A43}
.thanks{margin-top:56px;font-size:34px;color:var(--accent);font-style:italic;text-align:center}
@media print{@page{size:1280px 1500px;margin:0}html,body{background:#fff}#deck{position:static;display:block}#notes,#notes.on,#help{display:none!important}
  .s{display:flex!important;position:relative;transform:none!important;box-shadow:none;border:1px solid #ccc;height:auto;break-inside:avoid}
  .s .body{flex:none;height:560px}
  .printnotes{display:block;padding:10px 48px 30px;font-size:16px;break-after:page}}
"""

JS = """
const S=[...document.querySelectorAll('.s')],N=document.getElementById('notes');let i=0;
function fit(){const k=Math.min(innerWidth/1280,innerHeight/720)*0.98;S.forEach(s=>s.style.transform=`scale(${k})`)}
function go(j){i=Math.max(0,Math.min(S.length-1,j));S.forEach((s,k)=>s.classList.toggle('on',k===i));N.innerHTML=S[i].querySelector('.printnotes').innerHTML;history.replaceState(null,'','#'+(i+1))}
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key))go(i+1);else if(['ArrowLeft','PageUp'].includes(e.key))go(i-1);
 else if(e.key==='Home')go(0);else if(e.key==='End')go(S.length-1);else if(e.key==='n'||e.key==='N')N.classList.toggle('on');
 else if(e.key==='p'||e.key==='P')print();else if(e.key==='f'||e.key==='F'){document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen()}});
document.getElementById('deck').addEventListener('click',e=>go(i+(e.clientX>innerWidth/2?1:-1)));
addEventListener('resize',fit);fit();go((parseInt(location.hash.slice(1))||1)-1);
"""


def render(slides: list) -> str:
    parts = []
    for k, s in enumerate(slides, 1):
        notes = (f"<h3>Slide {k}: Lời nói</h3><ul>{''.join(f'<li>{esc(x)}</li>' for x in s['say'])}</ul>"
                 f"<h3>Câu hỏi có thể gặp</h3><ul>{''.join(f'<li><b>{esc(q)}</b> {esc(a)}</li>' for q, a in s['qa'])}</ul>"
                 f"<h3>Lấy số ở đâu</h3><ul>{''.join(f'<li><code>{esc(x)}</code></li>' for x in s['src'])}</ul>")
        parts.append(
            f'<section class="s"><h1>{esc(s["title"])}</h1>'
            + (f'<p class="kicker">{esc(" · ".join(x for x in (s.get("sec"), s["tag"]) if x))}</p>' if s.get("sec") or s["tag"] else "")
            + f'<div class="body">{RULE_CODES.sub("", s["body"])}</div>'
            + (f'<div class="concl">Kết luận: {esc(RULE_CODES.sub("", s["conclusion"]))}</div>' if s["conclusion"] else "")
            + f'<span class="pg">{k}/{len(slides)}</span><div class="prog" style="width:{100 * k / len(slides):.1f}%"></div>'
            f'<div class="printnotes">{notes}</div></section>')
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Tiền xử lý dữ liệu</title><style>{CSS}</style></head><body><div id="deck">{"".join(parts)}</div>'
            f'<div id="notes"></div><div id="help">← → chuyển slide · N lời nói và câu hỏi · P in lời nói · F toàn màn hình</div>'
            f'<script>{JS}</script></body></html>')


def load_inputs():
    import pandas as pd
    from report_data_issues import compute
    from preprocessing.common.r2_export import plan_objects

    reports = {st: json.loads((REPORTS / st / "_all.json").read_text(encoding="utf-8")) for st in STEPS}
    errs = check_links(ISSUE_TO_RULES, {r["id"] for st in STEPS for r in reports[st]["rules"]})
    if errs:
        raise SystemExit("Liên kết vấn đề ↔ luật lỗi:\n  " + "\n  ".join(errs))
    raw = json.loads(RAW_BEFORE.read_text(encoding="utf-8"))
    raw_now = compute(ROOT / "data")
    after = metrics(pd.read_parquet(ROOT / "data/preprocessing/04_normalization/all.parquet"))
    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    objs = plan_objects(build=False)
    storage = {"silver": sum(1 for o in objs if o["step"] != "05_encoding"), "gold": sum(1 for o in objs if o["step"] == "05_encoding")}
    return raw, raw_now, reports, after, before, storage


def render_md(slides: list) -> str:
    """Kịch bản thuyết trình: lời nói, câu hỏi dự đoán kèm trả lời, chỗ lấy số. Cùng nội dung với phím N trong slide."""
    lines = ["# Kịch bản thuyết trình: Tiền xử lý dữ liệu việc làm IT", "",
             "Sinh bởi `python scripts/build_slides.py`, cùng số với `docs/presentation/slides.html`. Sửa lời trong script rồi chạy lại, đừng sửa file này bằng tay.", "",
             f"**Thời lượng gợi ý:** khoảng 1 phút mỗi slide, tổng khoảng {len(slides)} phút, chưa tính hỏi đáp. Trong slide bấm N để xem lời nói.", "",
             "**Dàn bài:**", ""]
    sec = None
    for k, s in enumerate(slides, 1):
        if s.get("sec") != sec:
            sec = s.get("sec")
            lines.append(f"- **{sec or 'Mở đầu'}**")
        lines.append(f"  - Slide {k}. {s['title']}")
    lines.append("")
    todo = []
    for k, s in enumerate(slides, 1):
        lines += [f"## Slide {k}. {s['title']}" + (f" · {s['sec']}" if s.get("sec") else ""), ""]
        if s["conclusion"]:
            lines += [f"**Kết luận trên slide:** {s['conclusion']}", ""]
        lines += ["**Nói:**", ""] + [f"- {x}" for x in s["say"]] + ["", "**Thầy có thể hỏi:**", ""]
        lines += [f"- *{q}*  \n  {a}" for q, a in s["qa"]] + ["", "**Lấy số ở đâu:**", ""] + [f"- `{x}`" for x in s["src"]] + [""]
        if k < len(slides):
            lines += [f"*Chuyển ý → slide {k + 1}: {slides[k]['title']}*", ""]
        todo += s.get("todo", [])
    lines += ["## Việc còn tồn đọng (ghi chú cho mình, không chiếu)", ""] + [f"- {t}" for t in todo] + [""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save-before", type=Path, help="parquet bước 04 trước khi sửa review: ghi số vào before_review.json")
    args = ap.parse_args(argv)
    if args.save_before:
        import pandas as pd
        m = metrics(pd.read_parquet(args.save_before))
        m["_nguon"] = f"Tính từ {args.save_before.name}: output bước 04 trước khi sửa theo review (03/11/2026), bằng metrics() trong scripts/build_slides.py"
        BEFORE.parent.mkdir(parents=True, exist_ok=True)
        BEFORE.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"đã ghi {BEFORE.relative_to(ROOT)}")
        return 0
    slides = build(*load_inputs())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(slides), encoding="utf-8")
    SCRIPT_MD.write_text(render_md(slides), encoding="utf-8")
    print(f"đã ghi {OUT.relative_to(ROOT)}: {len(slides)} slide, {SCRIPT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
