#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo vấn đề của dữ liệu raw trực tiếp trên R2 (chỉ đọc) và sinh slide HTML.

    python scripts/report_raw_problems_r2.py              # đọc R2, ghi JSON + slide
    python scripts/report_raw_problems_r2.py --from-json  # dựng lại slide từ JSON đã có, không gọi R2

Chỉ gọi list_objects_v2 và get_object; không ghi hay xóa gì trên R2, không ghi raw ra máy.
Chỉ lưu số liệu và vài ví dụ ngắn vào docs/presentation/raw_problems_r2.json.
Số theo nguồn dùng lại source_stats và dedup_funnel của scripts/report_data_issues.py.
"""

from __future__ import annotations

import argparse
import collections
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import report_data_issues as rdi  # noqa: E402
from collection.common.r2_storage import get_r2_client, resolve_r2_bucket, to_r2_key  # noqa: E402
from preprocessing.common.raw_reader import SKIP_DIRS, snapshot_order  # noqa: E402
from preprocessing.integration.json_flattener import flatten_raw_job_record  # noqa: E402
from preprocessing.normalization.skill_normalizer import extract_skills  # noqa: E402

OUT_JSON = ROOT / "docs" / "presentation" / "raw_problems_r2.json"
OUT_HTML = ROOT / "docs" / "presentation" / "slides_raw_problems.html"
SKIP = SKIP_DIRS | {"_manifest"}
VN_CHARS = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
SOURCES = rdi.SOURCES


# ---------------------------------------------------------------- đọc R2
def keep_key(key: str) -> bool:
    """Chỉ lấy file .json không nằm trong thư mục phụ (_index, _quality, _manifest, _listing...)."""
    parts = key.split("/")
    return key.endswith(".json") and not (SKIP & set(parts)) and not parts[-1].startswith(".")


def latest_per_job(snaps: Sequence[Tuple[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Snapshot mới nhất theo job_id (scraped_at rồi version), cùng luật C1 của bước Clean."""
    best: Dict[str, Dict[str, Any]] = {}
    for _, env in snaps:
        jid = str(env["metadata"].get("job_id") or "")
        if jid and (jid not in best or snapshot_order(env) > snapshot_order(best[jid])):
            best[jid] = env
    return list(best.values())


def read_source(s3: Any, bucket: str, src: str, workers: int = 8) -> Tuple[List[Tuple[str, Dict[str, Any]]], Dict[str, int]]:
    prefix = to_r2_key(f"raw/{src}/")
    keys = [it["Key"] for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
            for it in page.get("Contents", []) if keep_key(it["Key"])]

    def get(key: str) -> Tuple[str, Any]:
        try:
            return key, json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
        except Exception:  # noqa: BLE001 - file hỏng chỉ được đếm
            return key, None

    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(get, keys))
    snaps, counts = [], collections.Counter()
    for key, obj in results:
        if obj is None:
            counts["json_lỗi"] += 1
        elif isinstance(obj, list):
            counts["file_batch"] += 1
            counts["tin_trong_batch"] += len(obj)
        elif isinstance(obj, dict) and isinstance(obj.get("metadata"), dict):
            counts["snapshot"] += 1
            counts["snapshot_v_lớn_hơn_1"] += int(obj["metadata"].get("version") or 1) > 1
            snaps.append((key, obj))
        else:
            counts["không_phải_envelope"] += 1
    return snaps, dict(counts)


# ---------------------------------------------------------------- số đo thêm
def _pick(flats: List[Dict[str, Any]], pred, field: str, k: int = 2) -> List[Dict[str, Any]]:
    out = []
    for f in sorted(flats, key=lambda f: str(f.get("job_id_global"))):
        if pred(f):
            out.append({"job": f.get("job_id_global"), "text": str(f.get(field) or "")[:110], "url": f.get("source_url")})
            if len(out) == k:
                break
    return out


def extra_stats(flats: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(flats)
    tag0 = jd0 = en = short = 0
    skills_sum = 0
    for f in flats:
        tags = " ".join(map(str, f.get("skills_list") or []))
        text = " ".join(str(f.get(k) or "") for k in ("raw_description_text", "raw_requirements_text"))
        tag0 += not extract_skills(tags)
        found = extract_skills(f.get("job_title"), tags, text)
        jd0 += not found
        skills_sum += len(found)
        letters = sum(c.isalpha() for c in text)
        en += letters > 200 and len(VN_CHARS.findall(text)) / letters < 0.005
        short += len(text.split()) < 30
    rel = lambda f: re.search(r"trước|ago|hôm", str(f.get("raw_posted_date") or ""), re.I)  # noqa: E731
    return {
        "skills_tag_zero_pct": rdi.pct(tag0, n), "skills_jd_zero_pct": rdi.pct(jd0, n), "skills_jd_avg": round(skills_sum / n, 2) if n else 0,
        "english_like_pct": rdi.pct(en, n), "jd_under_30_words": short,
        "examples": {
            "salary_neg": _pick(flats, lambda f: rdi.NEGOTIABLE.search(str(f.get("raw_salary_text") or "")), "raw_salary_text"),
            "salary_usd": _pick(flats, lambda f: re.search(r"usd|\$", str(f.get("raw_salary_text") or ""), re.I), "raw_salary_text"),
            "location_multi": _pick(flats, lambda f: re.search(r",|;|\||&", str(f.get("raw_location_text") or "")), "raw_location_text"),
            "date_relative": _pick(flats, rel, "raw_posted_date"),
            "html_left": _pick(flats, lambda f: rdi.HTML_RE.search(str(f.get("raw_description_text") or "")), "raw_description_text"),
            "seniority": _pick(flats, lambda f: not rdi.is_empty(f.get("raw_seniority_text")), "raw_seniority_text"),
            "no_skill": _pick(flats, lambda f: not f.get("skills_list"), "job_title"),
        },
    }


def measure(workers: int = 8) -> Dict[str, Any]:
    s3, bucket = get_r2_client(), resolve_r2_bucket()
    per: Dict[str, Any] = {}
    rows: List[Tuple[str, Dict[str, Any]]] = []
    for src in SOURCES:
        snaps, counts = read_source(s3, bucket, src, workers)
        envs = latest_per_job(snaps)
        flats = [flatten_raw_job_record(e, src) for e in envs]
        per[src] = {"jobs": len(flats), "files": counts}
        if flats:
            per[src].update(rdi.source_stats(flats, envs))
            per[src]["extra"] = extra_stats(flats)
        rows += [(src, f) for f in flats]
        print(f"{src}: {len(flats)} tin, {counts}", flush=True)
    with_data = [s for s in per if per[s]["jobs"]]
    matrix = []
    for field in (list(per[with_data[0]]["fill"]) if with_data else []):
        have = [s for s in with_data if per[s]["fill"][field] >= rdi.FIELD_PRESENT_PCT]
        matrix.append({"field": field, "sources": len(have), "missing_in": [s for s in with_data if s not in have]})
    return {"generated_on": date.today().isoformat(), "bucket_read_only": True, "total_jobs": sum(per[s]["jobs"] for s in per),
            "sources": per, "field_matrix": matrix, "dedup": rdi.dedup_funnel(rows)}


# ---------------------------------------------------------------- slide
e = rdi._e
LABEL = {"topcv": "TopCV", "topdev": "TopDev", "vietnamworks": "VietnamWorks", "careerviet": "CareerViet",
         "vieclam24h": "Vieclam24h", "itviec": "ITviec", "glints": "Glints", "jobsgo": "JobsGO"}

# Luật có thật trong code (tên lấy từ reports/preprocessing/*/_all.json, N2 và I0 theo quyết định 09/11/2026)
STEPS = [
    ("1. Clean", "Bỏ phần không dùng được; không sửa giá trị", [
        ("C1", "Giữ snapshot mới nhất của mỗi job_id"), ("C2", "Bỏ tin trong file batch cũ đã có file riêng"),
        ("C3", "Bỏ bản ghi test, thiếu job_id/source_url hoặc sai nguồn"), ("C4a/C4c", "Phân loại IT bằng luật 2 tầng; bỏ tin ngoài IT theo it_policy.json"),
        ("C5", "Bỏ JD dưới 30 từ"), ("C6", "Bỏ tin trùng trong cùng nguồn (công ty + tiêu đề + tỉnh + tuần)"),
        ("C7", "Bỏ tin trùng khác nguồn, ghi nguồn còn lại vào also_on")]),
    ("2. Integration", "Gộp 8 nguồn về một schema 18 trường; không bỏ tin", [
        ("I0", "Dòng JSON hỏng: bỏ và ghi vào danh sách đã bỏ (đã chốt 09/11; code của Hoàng còn giữ lại, PRE-18)"),
        ("I1", "Làm phẳng envelope về 18 trường chuẩn + khóa"), ("I2", "ITviec lấy ngày đăng từ JSON-LD datePosted"),
        ("I3", "TopDev lấy ngày đăng và kinh nghiệm từ published/JSON-LD"), ("I4", "Bỏ tag SEO và ngành nghề khỏi skills_list"),
        ("I5", "Chuỗi rỗng và container rỗng về null")]),
    ("3. Transformation", "Bóc tách giá trị từ văn bản thô", [
        ("T1", "Null trá hình thành null"), ("T2/T2f", "Bóc dải lương (cascade); lương ngoài 1–500 triệu bỏ số, gắn cờ"),
        ("T3", "Ngày về dạng chuẩn"), ("T4", "Số năm kinh nghiệm"), ("T5", "Headcount"),
        ("T6", "Làm sạch HTML/bullet, phát hiện ngôn ngữ"), ("T7", "Rút kỹ năng và phúc lợi song ngữ"), ("T8", "Địa điểm 3 cấp")]),
    ("4. Normalization", "Đưa về danh mục chuẩn", [
        ("N1", "34 tỉnh/thành sau sáp nhập (tên \"TP. Hồ Chí Minh\")"), ("N2", "Cấp bậc 5 cấp: Intern/Fresher, Junior, Middle, Senior, Lead/Manager (đã chốt 09/11; code còn thang 6, F05)"),
        ("N2b", "Nhãn mâu thuẫn với kinh nghiệm/kỹ năng: gắn cờ cần kiểm"), ("N3", "12 nhóm nghề IT (UI/UX gộp vào Frontend, đã chốt 09/11; code chưa sửa)"),
        ("N4", "Ánh xạ kỹ năng chuẩn theo từ điển"), ("N5", "Chuẩn hóa tên công ty"),
        ("N6/N6a/N7", "Cờ ngoại lai lương (IQR, Winsorize), log1p")]),
    ("5. Encoding", "Đổi sang cột số cho mô hình", [
        ("E1", "Cấp bậc thành số thứ bậc, chưa rõ = −1"), ("E2", "Nhóm nghề one-hot, tỉnh và kỹ năng multi-hot (230 cột kỹ năng)"),
        ("E3", "Trường số giữ nguyên kèm cờ thiếu giá trị")]),
]
# vấn đề (mục A) → luật → còn mở (mã KNOWN_ISSUED.md)
MAP = [
    ("1. Tin ngoài IT", "C4a, C4c", "PRE-12 (nhãn), PRE-13, PRE-15 (dùng model xét lại tin bị loại)"),
    ("2. Trùng lặp", "C1, C2, C6, C7", "PRE-14, PRE-16"),
    ("3. Thiếu trường theo nguồn", "I1", "SCRAPE-5 (raw TopDev cũ)"),
    ("4. Null trá hình", "T1, I5", "đã có luật"),
    ("5. Lương", "T2, T2f, N6, N6a, N7", "PRE-23 (\"tối thiểu 10 triệu\", \"2 tỷ\")"),
    ("6. Địa điểm", "T8, N1", "PRE-23 (\"Điện Biên Phủ\" bị nhầm là tỉnh)"),
    ("7. Kinh nghiệm và cấp bậc", "T4, N2, N2b, E1", "PRE-22 (đưa code về 5 cấp, F05)"),
    ("8. Kỹ năng", "I4, T7, N4, E2", "PRE-28, PRE-29 (trích từ JD, từ điển hợp nhất)"),
    ("9. Ngày tháng", "I2, I3, T3", "đã có luật"),
    ("10. Văn bản, HTML, tiêu đề, công ty", "T6, N5, C5", "đã có luật"),
    ("11. Ngôn ngữ Anh/Việt", "T6, T7", "PRE-29 (dịch tùy chọn)"),
    ("12. JD thiếu hoặc quá ngắn", "C5", "SCRAPE-16 (cào lại TopCV)"),
]

CSS = rdi.CSS + """
html,body{height:100%}main{max-width:none;padding:0}
.deck{height:100vh;display:flex;flex-direction:column}
.slide{display:none;flex:1;overflow:auto;padding:28px 6vw 70px;max-width:1180px;margin:0 auto;width:100%}
.slide.on{display:block}.sec{color:var(--brand);font-weight:600;font-size:13px;letter-spacing:.04em;text-transform:uppercase}
.slide h1{font-size:28px;margin:4px 0 10px}.lead{font-size:18px;margin:6px 0 14px}
.ctl{position:fixed;left:0;right:0;bottom:0;display:flex;align-items:center;gap:10px;padding:8px 14px;background:var(--card);border-top:1px solid var(--line)}
.ctl button{font:inherit;border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:8px;padding:6px 14px;cursor:pointer}
.ctl span{flex:1;text-align:center;font-size:13px;color:var(--muted)}
.ex{font-size:13.5px;margin:4px 0}.ex code{display:inline-block;max-width:100%}
@media(prefers-color-scheme:dark){:root{--bg:#15141c;--card:#1d1c27;--line:#2e2d3c;--ink:#ecebf4;--muted:#a3a2b4}
th{background:#23222f}.note{background:#211f33}.high{background:#4a2227}.mid{background:#46341a}.low{background:#173627}code{background:#2a2938}}
@media print{.slide{display:block!important;page-break-after:always;overflow:visible}.ctl{display:none}.deck{height:auto}}
@media(max-width:600px){.slide{padding:18px 16px 70px}.slide h1{font-size:22px}}
"""
JS = """
var s=[].slice.call(document.querySelectorAll('.slide')),i=0;
function go(n){i=Math.max(0,Math.min(s.length-1,n));s.forEach(function(x,k){x.classList.toggle('on',k==i)});
document.getElementById('pos').textContent=(i+1)+' / '+s.length;try{history.replaceState(null,'','#'+(i+1))}catch(e){}s[i].scrollTop=0}
document.addEventListener('keydown',function(ev){if(ev.key=='ArrowRight'||ev.key==' ')go(i+1);if(ev.key=='ArrowLeft')go(i-1)});
document.getElementById('prev').onclick=function(){go(i-1)};document.getElementById('next').onclick=function(){go(i+1)};
go((parseInt(location.hash.slice(1))||1)-1);
"""


def _slide(sec: str, title: str, body: str, lead: str = "") -> str:
    return (f'<section class="slide"><div class="sec">{e(sec)}</div><h1>{e(title)}</h1>'
            f'{f"<p class=lead>{lead}</p>" if lead else ""}{body}</section>')


def _ex(items: Sequence[Dict[str, Any]], label: str) -> str:
    return "".join(f'<div class="ex"><span class="muted">{e(label)} · {e(x["job"])}:</span> <code>{e(x["text"])}</code></div>' for x in items)


def _all_ex(per: Dict[str, Any], key: str, k: int = 3) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for s in SOURCES:
        out += per[s].get("extra", {}).get("examples", {}).get(key, [])[:1]
    return out[:k]


def render(st: Dict[str, Any]) -> str:
    per = {s: v for s, v in st["sources"].items() if v["jobs"]}
    tot = st["total_jobs"]
    S = list(per)
    sm = lambda f: sum(f(per[s]) for s in S)  # noqa: E731
    by = lambda f, unit="%": rdi._bars({LABEL[s]: f(per[s]) for s in S}, unit)  # noqa: E731
    files = {k: sm(lambda p, k=k: p["files"].get(k, 0)) for k in ("snapshot", "snapshot_v_lớn_hơn_1", "file_batch", "tin_trong_batch")}
    dd = st["dedup"]
    A = "A. Vấn đề của dữ liệu raw"
    sl: List[str] = []

    sl.append(_slide("Vấn đề của dữ liệu raw và cách xử lý", "Dữ liệu raw của 8 sàn việc làm IT",
        f'<div class="kpis"><div class="kpi"><span class="muted">Tin (bản mới nhất)</span><b>{tot:,}</b></div>'
        f'<div class="kpi"><span class="muted">Snapshot trên R2</span><b>{files["snapshot"]:,}</b></div>'
        f'<div class="kpi"><span class="muted">Snapshot phiên bản &gt; 1</span><b>{files["snapshot_v_lớn_hơn_1"]:,}</b></div>'
        f'<div class="kpi"><span class="muted">File batch cũ</span><b>{files["file_batch"]}</b> <span class="muted">({files["tin_trong_batch"]:,} tin)</span></div></div>'
        f'<div class="note">Số liệu đo ngày {e(st["generated_on"])} <b>trực tiếp trên R2</b> (chỉ đọc), mỗi tin lấy snapshot mới nhất rồi làm phẳng bằng '
        f'<code>flatten_raw_job_record</code>. Mục A liệt kê 12 nhóm vấn đề; mục B (cuối bộ slide) là cách xử lý từng nhóm.</div>'
        + rdi._table(["Nguồn", "Tin", "Snapshot", "v&gt;1"], [(LABEL[s], f'{per[s]["jobs"]:,}', per[s]["files"].get("snapshot", 0),
                                                              per[s]["files"].get("snapshot_v_lớn_hơn_1", 0)) for s in S], 1)))

    nonit = [x for s in S for x in per[s]["title"]["non_it_examples"][:1]]
    sl.append(_slide(A, "1. Tin ngoài IT lẫn vào", by(lambda p: p["title"]["non_it_pct"]) +
        "".join(f'<div class="ex"><code>{e(x["title"])}</code></div>' for x in nonit[:4]) +
        '<div class="note">Ước lượng theo từ khóa tiêu đề, chỉ để thấy độ lớn; phân loại thật làm ở Clean và kiểm bằng nhãn tay (643 nhãn). Mức: <span class="tag high">Cao</span></div>',
        "Sàn tổng hợp xếp nhầm tin kế toán, nhân sự, bán hàng vào mục IT; TopDev trả cả tin ngoài IT vì API bỏ qua tham số lọc."))

    sl.append(_slide(A, "2. Trùng lặp", rdi._table(["Luật so khớp", "Tin dư", "Nhóm cùng nguồn", "Nhóm khác nguồn"],
        [(x["step"], x["extra_jobs"], x["groups_same_source"], x["groups_cross_source"]) for x in dd], 1) +
        f'<p>Ngoài ra {files["snapshot_v_lớn_hơn_1"]:,} snapshot là phiên bản mới của tin đã cào (cùng job_id), và {files["file_batch"]} file batch cũ gom {files["tin_trong_batch"]:,} tin trùng với file từng tin.</p>'
        '<div class="note">Càng thêm điều kiện (thành phố, tuần đăng) càng bớt trùng giả. Mức: <span class="tag high">Cao</span></div>',
        "Cùng một tin xuất hiện nhiều lần: nhiều phiên bản, nằm trong file batch cũ, đăng lại, hoặc đăng ở nhiều sàn."))

    fm = st["field_matrix"]
    heat = "".join(f"<tr><td>{e(m['field'])}</td>" + "".join(rdi._heat(per[s]["fill"][m["field"]]) for s in S) + f'<td class="n">{m["sources"]}/{len(S)}</td></tr>' for m in fm)
    sl.append(_slide(A, "3. Thiếu trường: mỗi nguồn có một bộ trường khác nhau",
        '<div class="scroll heat"><table><thead><tr><th>Trường</th>' + "".join(f"<th>{e(LABEL[s])}</th>" for s in S) + f"<th>Nguồn có</th></tr></thead><tbody>{heat}</tbody></table></div>"
        '<div class="note">Ô là % tin có giá trị (đỏ: ít, xanh: nhiều). Luật chốt: trường phải có ở ít nhất 3 nguồn mới đưa vào schema chung. Mức: <span class="tag mid">TB</span></div>',
        "Sau làm phẳng, độ phủ của từng trường rất khác nhau giữa các sàn."))

    sneaky = [(LABEL[s], x[0], x[1]) for s in S for x in per[s]["sneaky_null"][:2]]
    sl.append(_slide(A, "4. Null trá hình",
        rdi._table(["Nguồn", "Giá trị", "Số tin"], [(a, f"<code>{e(b)}</code>", c) for a, b, c in sneaky[:10]], 2) +
        '<div class="note">Chuỗi như "N/A", "0", "đang cập nhật", "[]" trông như có dữ liệu nhưng thật ra rỗng. Mức: <span class="tag mid">TB</span></div>',
        "Giá trị rỗng được ghi bằng chữ thay vì null."))

    sl.append(_slide(A, "5. Lương", "<h3>Tỷ lệ tin theo kiểu ghi lương</h3>" +
        rdi._table(["Nguồn", "Thỏa thuận %", "USD %", "Chỉ một phía", "Parse &lt; 1 triệu", "Lương trong tiêu đề"],
                   [(LABEL[s], per[s]["salary"]["negotiable_pct"], per[s]["salary"]["usd_pct"], per[s]["salary"]["one_sided"],
                     per[s]["salary"]["parsed_under_1m"], per[s]["salary"]["in_title"]) for s in S], 1) +
        _ex(_all_ex(per, "salary_neg"), "thỏa thuận") + _ex(_all_ex(per, "salary_usd"), "USD") +
        '<div class="note">"Parse &lt; 1 triệu" là lương bị đọc sai đơn vị bởi bộ parse hiện tại. Mức: <span class="tag high">Cao</span></div>',
        "Lương là chuỗi tự do: thỏa thuận, USD, chỉ có trần hoặc sàn, đơn vị khác nhau."))

    loc = lambda p: p["location"]  # noqa: E731
    sl.append(_slide(A, "6. Địa điểm", rdi._table(["Nguồn", "Giá trị khác nhau", "Nhiều thành phố", "Có địa chỉ đường", "Trường working_locations trống %"],
        [(LABEL[s], loc(per[s])["distinct"], loc(per[s])["multi_city"], loc(per[s])["street_address"], loc(per[s])["working_locations_empty_pct"]) for s in S], 1) +
        _ex(_all_ex(per, "location_multi"), "nhiều nơi") +
        '<div class="note">Cần đưa về 34 tỉnh/thành sau sáp nhập; tên chuẩn "TP. Hồ Chí Minh". Mức: <span class="tag mid">TB</span></div>',
        "Mỗi sàn ghi địa điểm một kiểu: tên tỉnh cũ, nhiều thành phố trong một ô, hoặc cả địa chỉ đường."))

    sl.append(_slide(A, "7. Kinh nghiệm và cấp bậc",
        rdi._table(["Nguồn", "Kinh nghiệm không có số", "Dạng khoảng", "Nhãn cấp bậc phổ biến"],
                   [(LABEL[s], per[s]["experience"]["no_number"], per[s]["experience"]["range"],
                     e("; ".join(f"{k} ({v})" for k, v in per[s]["seniority"]["top"][:2]) or "không có")) for s in S], 1) +
        '<div class="note">Nhãn của sàn thường chung chung ("Nhân viên"); TopDev, ITviec, Glints gần như không có nhãn. Đã chốt dùng 5 cấp. Mức: <span class="tag mid">TB</span></div>',
        "Nhãn cấp bậc thiếu hoặc chung chung; kinh nghiệm ghi bằng chữ."))

    sl.append(_slide(A, "8. Kỹ năng", "<h3>% tin không có kỹ năng nào (từ điển 92 kỹ năng của Duy)</h3>" +
        rdi._table(["Nguồn", "Chỉ thẻ của sàn %", "Thẻ + tiêu đề + JD %", "Kỹ năng TB/tin (thẻ + JD)", "Thẻ dài &gt; 4 từ"],
                   [(LABEL[s], per[s]["extra"]["skills_tag_zero_pct"], per[s]["extra"]["skills_jd_zero_pct"], per[s]["extra"]["skills_jd_avg"],
                     per[s]["skills"]["long_tags"]) for s in S], 1) +
        '<div class="note">Tính trên toàn bộ tin raw, gồm cả tin ngoài IT (không có kỹ năng IT là bình thường), nên cao hơn số đo trên 5.077 tin IT sau Clean (58% chỉ thẻ, 12,2% thẻ + JD). Hai sàn gần như không có thẻ kỹ năng; trích từ JD giảm mạnh số tin trống. Kỹ năng mềm gần như vắng ở thẻ. Mức: <span class="tag high">Cao</span></div>',
        "Cột kỹ năng phụ thuộc vào thẻ của sàn, mà nhiều sàn không có hoặc ghi thẻ SEO."))

    dt = lambda p: p["dates"]  # noqa: E731
    sl.append(_slide(A, "9. Ngày tháng", rdi._table(["Nguồn", "Ngày đăng trống %", "Ngày đăng tương đối", "Đăng quá 90 ngày", "Hạn nộp trống %", "Hạn trước ngày cào"],
        [(LABEL[s], dt(per[s])["posted_empty_pct"], dt(per[s])["posted_relative"], dt(per[s])["posted_older_90d"], dt(per[s])["deadline_empty_pct"],
          dt(per[s])["deadline_before_crawl"]) for s in S], 1) + _ex(_all_ex(per, "date_relative"), "tương đối") +
        '<div class="note">"Đăng 6 giờ trước" không đổi ngày thật được nếu không biết giờ cào. Mức: <span class="tag high">Cao</span></div>',
        "Ngày đăng ghi tương đối hoặc theo nhiều định dạng khác nhau, có nguồn không có."))

    sl.append(_slide(A, "10. Văn bản, HTML, tiêu đề, công ty", rdi._table(["Nguồn", "JD trống %", "JD còn HTML", "Tiêu đề có mã/ngoặc", "Tiêu đề viết hoa toàn bộ", "Công ty nhiều cách viết"],
        [(LABEL[s], per[s]["text"]["jd_empty_pct"], per[s]["text"]["html_left"], per[s]["title"]["codes_brackets"], per[s]["title"]["all_caps"],
          per[s]["company"]["same_company_variants"]) for s in S], 1) + _ex(_all_ex(per, "html_left"), "còn HTML") +
        '<div class="note">Mức: <span class="tag low">Thấp</span> (làm sạch thêm).</div>',
        "Mô tả còn thẻ HTML, tiêu đề lẫn mã tin, cùng một công ty viết nhiều kiểu."))

    sl.append(_slide(A, "11. Ngôn ngữ Anh/Việt", by(lambda p: p["extra"]["english_like_pct"]) +
        '<div class="note">Nhận diện thô: JD có dưới 0,5% chữ có dấu tiếng Việt, tính trên toàn bộ tin raw. Mức: <span class="tag mid">TB</span></div>',
        "Một phần đáng kể JD viết bằng tiếng Anh, nhất là ITviec và VietnamWorks; từ điển kỹ năng phải hiểu cả hai ngôn ngữ."))

    sl.append(_slide(A, "12. JD thiếu hoặc quá ngắn", rdi._table(["Nguồn", "JD dưới 30 từ", "JD dưới 200 ký tự (có chữ)"],
        [(LABEL[s], per[s]["extra"]["jd_under_30_words"], per[s]["text"]["jd_short"]) for s in S], 1) +
        '<div class="note">TopCV có một đợt cào 22–26/10 không lấy được JD (SCRAPE-16). Mức: <span class="tag high">Cao</span></div>',
        "Không đủ nội dung để rút kỹ năng, kinh nghiệm hay phân loại IT."))

    B = "B. Cách xử lý từng vấn đề"
    sl.append(_slide(B, "Vấn đề nào được giải ở bước nào",
        rdi._table(["Vấn đề (mục A)", "Luật xử lý", "Còn mở (KNOWN_ISSUED.md)"], [(a, f"<code>{e(b)}</code>", e(c)) for a, b, c in MAP], 3) +
        '<div class="note">Mã luật có trong code. Số tin bị mỗi luật ảnh hưởng chưa chạy lại trên bộ raw này (snapshot báo cáo cũ, PRE-17), nên slide không nêu.</div>',
        "Chỉ bước Clean bỏ dòng; Integration, Transformation, Normalization và Encoding giữ số dòng, chỉ sửa và thêm cột."))
    for name, role, rules in STEPS:
        sl.append(_slide(B, name, rdi._table(["Luật", "Việc làm"], [(f"<code>{e(a)}</code>", e(b)) for a, b in rules], 3), role))
    sl.append(_slide(B, "Cần nhóm quyết thêm",
        '<ul><li>Kỹ năng: hợp nhất từ điển 92 (Duy) và 230 (Phát), trích từ JD, có đưa kỹ năng mềm vào không.</li>'
        '<li>Tin ngoài IT: có dùng model xét lại tin bị loại không (OpenJev, Qwen local).</li>'
        '<li>Layout R2: ai đang đọc/ghi prefix nào trước khi xóa <code>quality/</code>, <code>integration/</code>, <code>transformation/</code>.</li>'
        '<li>Khoảng k của K-Means; cohort của Phát.</li></ul>'
        '<p class="muted">Chi tiết: <code>docs/presentation/van_de_can_chot.html</code>.</p>'))

    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Vấn đề dữ liệu raw</title><style>{CSS}</style></head><body><main><div class="deck">{"".join(sl)}</div>'
            f'<div class="ctl"><button id="prev">← Trước</button><span id="pos"></span><button id="next">Sau →</button></div></main><script>{JS}</script></body></html>')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-json", action="store_true", help="dựng lại slide từ JSON đã có, không gọi R2")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if args.from_json:
        st = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    else:
        st = measure(args.workers)
        OUT_JSON.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_HTML.write_text(render(st), encoding="utf-8")
    print(f"Đã ghi {OUT_JSON.name} và {OUT_HTML.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
