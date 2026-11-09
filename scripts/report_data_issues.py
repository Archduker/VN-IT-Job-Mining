#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thống kê vấn đề dữ liệu raw (sau làm phẳng) và vẽ thành một file HTML tự chứa. Chỉ đọc dữ liệu.

    python scripts/report_data_issues.py                       # ghi docs/spec/preprocessing/data_issues_2026-11-03.html
    python scripts/report_data_issues.py --out /tmp/x.html

Mỗi tin lấy snapshot mới nhất; file batch cũ (list) và thư mục phụ bị bỏ qua. Làm phẳng bằng
flatten_raw_job_record của preprocessing, parse lương bằng parse_salary_cascade, để số liệu đúng với pipeline hiện tại.
compute() trả dict thuần JSON để Monitoring dùng lại sau này.
"""

from __future__ import annotations

import argparse
import collections
import html
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from preprocessing.common.raw_reader import latest_envelopes  # noqa: E402,F401  (test gọi rdi.latest_envelopes)
from preprocessing.integration.json_flattener import flatten_raw_job_record  # noqa: E402
from preprocessing.transformation.salary_parser import parse_salary_cascade  # noqa: E402

SOURCES = ("topcv", "topdev", "vietnamworks", "careerviet", "vieclam24h", "itviec", "glints", "jobsgo")
ID_FIELDS = {"job_id_global", "source_platform", "source_job_id", "source_url", "crawled_at"}
FIELD_PRESENT_PCT = 50   # nguồn "có" trường khi >= 50% tin có giá trị
MIN_SOURCES_TO_KEEP = 3  # luật chốt 03/11/2026: trường phải có ở >= 3–4/8 nguồn mới đưa vào integration
SNEAKY = {"", "n/a", "na", "null", "none", "-", "--", "đang cập nhật", "updating", "0", "[]", "{}"}
NEGOTIABLE = re.compile(r"thỏa thuận|thoả thuận|thoa thuan|thương lượng|negotiable|cạnh tranh|competitive|you'll love it", re.I)
# shortcut: lọc ngành IT bằng từ khóa trong tiêu đề, chỉ để ước lượng; phân loại thật làm ở bước normalization (P4)
IT_WORDS = re.compile(
    r"develop|engineer|lập trình|program|software|phần mềm|data|dữ liệu|tester|\bqa\b|\bqc\b|devops|cloud|security|"
    r"bảo mật|\bit\b|system|hệ thống|network|mạng|backend|frontend|fullstack|full-stack|mobile|android|ios|web|ai\b|"
    r"machine learning|\bml\b|game|unity|product owner|business analyst|\bba\b|scrum|erp|sap|database|dba|kỹ sư|"
    r"technical|tech|công nghệ|ui/ux|designer|thiết kế|automation|embedded|nhúng|blockchain|python|java|\.net|php|"
    r"react|node|golang|c\+\+|kotlin|flutter|helpdesk|support|kỹ thuật viên", re.I)
# Ví dụ minh họa ưu tiên tin ngoài IT rõ ràng, để người đọc tự kiểm được
CLEAR_NON_IT = re.compile(r"kinh doanh|kế toán|tài xế|giáo viên|nhân sự|\bhr\b|marketing|bán hàng|sales|tuyển sinh|lái xe|giao hàng|hành chính|logistics|thu ngân|chăm sóc khách hàng", re.I)
HTML_RE = re.compile(r"<[a-zA-Z/][^>]{0,80}>|&(amp|nbsp|lt|gt|quot|#\d+);")
# Đo bằng tay ngày 03/11/2026 (2 lần gọi GET /td/v2/jobs, page_size=50): không gọi mạng mỗi lần chạy script
TOPDEV_API_PROBE = {
    "measured_on": "2026-11-03",
    "with_category_ids_1_total": 14572,
    "without_category_ids_total": 14572,
    "page1_same_titles": "50/50",
    "code": "collection/sources/topdev/crawler.py:_fetch_listing gửi category_ids=1 (CLI ghi '1 = IT')",
}


# ---------------------------------------------------------------- tiện ích
def strip_accents(text: Any) -> str:
    s = unicodedata.normalize("NFD", str(text or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")


def norm(text: Any) -> str:
    return re.sub(r"\s+", " ", strip_accents(text).lower()).strip()


def norm_company(name: Any) -> str:
    k = re.sub(r"^(cong ty|cty|ctcp)( co phan| tnhh)?\s+", "", norm(name))
    return re.sub(r"\b(jsc|co\.?,? ?ltd|ltd|company|corporation|corp|inc|limited)\b\.?", "", k).strip(" .,")


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)):
        return not value
    return str(value).strip().lower() in SNEAKY


def parse_day(value: Any) -> Optional[datetime]:
    if not value:
        return None
    s = str(value).strip()
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    try:
        d = datetime(int(m[3]), int(m[2]), int(m[1])) if m else datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


# ---------------------------------------------------------------- thống kê một nguồn
def source_stats(flats: List[Dict[str, Any]], envs: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(flats)
    fields = [k for k in flats[0] if k not in ID_FIELDS]
    out: Dict[str, Any] = {"fill": {c: pct(sum(not is_empty(f.get(c)) for f in flats), n) for c in fields}}
    sneaky = collections.Counter(f"{c} = {f[c].strip()!r}" for f in flats for c in fields
                                 if isinstance(f.get(c), str) and f[c].strip() and f[c].strip().lower() in SNEAKY)
    out["sneaky_null"] = sneaky.most_common(5)

    # Lương: dùng bộ parse thật của pipeline
    salaries = [str(f.get("raw_salary_text")) for f in flats if not is_empty(f.get("raw_salary_text"))]
    tiny, from_eq, examples = 0, 0, []
    for s in salaries:
        r = parse_salary_cascade(s, None)
        lo, hi = r.get("salary_min_vnd"), r.get("salary_max_vnd")
        if (lo and lo < 1_000_000) or (hi and hi < 1_000_000):
            tiny += 1
            if len(examples) < 3:
                examples.append(f"{s} → {hi or lo:,.0f} VND")
        if re.match(r"\s*(từ|from)\b", s, re.I) and lo and hi == lo:
            from_eq += 1
    out["salary"] = {
        "negotiable_pct": pct(sum(1 for s in salaries if NEGOTIABLE.search(s) and not re.search(r"\d", s)), n),
        "usd_pct": pct(sum(1 for s in salaries if re.search(r"usd|\$", s, re.I)), n),
        "one_sided": sum(1 for s in salaries if re.search(r"up to|tới|đến|lên đến", s, re.I)
                         and len(re.findall(r"\d+(?:[.,]\d+)*", s)) == 1),
        "parsed_under_1m": tiny, "parsed_under_1m_examples": examples, "from_x_max_equals_min": from_eq,
        "in_title": sum(1 for f in flats if re.search(r"\d+\s*(tr|triệu|usd|\$)|lương|salary|up to", str(f.get("job_title") or ""), re.I)),
    }

    locs = collections.Counter(str(f.get("raw_location_text")).strip() for f in flats if not is_empty(f.get("raw_location_text")))
    out["location"] = {
        "distinct": len(locs),
        "multi_city": sum(c for loc, c in locs.items() if re.search(r",|;|\||&| và | and |\+", loc)),
        "street_address": sum(c for loc, c in locs.items() if re.search(r"\d+\s+\w|tầng|tòa|toà|đường|street|phường|quận", loc, re.I)),
        "working_locations_empty_pct": pct(sum(is_empty(f.get("working_locations")) for f in flats), n),
        "top": locs.most_common(4),
    }
    exp = collections.Counter(str(f.get("raw_experience_text")).strip() for f in flats if not is_empty(f.get("raw_experience_text")))
    out["experience"] = {"distinct": len(exp), "no_number": sum(c for e, c in exp.items() if not re.search(r"\d", e)),
                         "range": sum(c for e, c in exp.items() if re.search(r"\d\s*[-–~]\s*\d", e)), "top": exp.most_common(4)}
    sen = collections.Counter(str(f.get("raw_seniority_text")).strip() for f in flats if not is_empty(f.get("raw_seniority_text")))
    out["seniority"] = {"distinct": len(sen), "top": sen.most_common(5)}

    skills = [f.get("skills_list") or [] for f in flats]
    tags = collections.Counter(t for s in skills for t in s)
    out["skills"] = {"empty_pct": pct(sum(not s for s in skills), n), "avg": round(sum(map(len, skills)) / n, 1),
                     "long_tags": sum(c for t, c in tags.items() if len(str(t).split()) > 4), "top": tags.most_common(6)}

    now = datetime.now(timezone.utc)
    posted = [f.get("raw_posted_date") for f in flats]
    parsed = [parse_day(p) for p in posted if not is_empty(p)]
    out["dates"] = {
        "posted_empty_pct": pct(sum(is_empty(p) for p in posted), n),
        "posted_relative": sum(1 for p in posted if p and re.search(r"trước|ago|hôm", str(p), re.I)),
        "posted_older_90d": sum(1 for p in parsed if p and (now - p).days > 90),
        "deadline_empty_pct": pct(sum(is_empty(f.get("raw_deadline")) for f in flats), n),
        "deadline_before_crawl": sum(1 for f in flats if parse_day(f.get("raw_deadline")) and parse_day(f.get("crawled_at"))
                                     and parse_day(f.get("raw_deadline")) < parse_day(f.get("crawled_at"))),
    }
    desc = [str(f.get("raw_description_text") or "") for f in flats]
    heads = collections.Counter(norm(d)[:300] for d in desc if len(d) > 50)
    out["text"] = {"jd_empty_pct": pct(sum(not d.strip() for d in desc), n), "jd_short": sum(1 for d in desc if 0 < len(d.strip()) < 200),
                   "html_left": sum(1 for d in desc if HTML_RE.search(d)), "jd_same_head": sum(c for c in heads.values() if c > 1)}
    titles = [str(f.get("job_title") or "") for f in flats]
    non_it = [i for i, t in enumerate(titles) if t and not IT_WORDS.search(t)]
    out["title"] = {"codes_brackets": sum(1 for t in titles if re.search(r"\(|\[|#|\d{4,}", t)),
                    "all_caps": sum(1 for t in titles if len(t) > 8 and t.upper() == t),
                    "non_it_pct": pct(len(non_it), n),
                    "non_it_examples": [{"title": titles[i], "url": flats[i].get("source_url")}
                                        for i in sorted(non_it, key=lambda i: not CLEAR_NON_IT.search(titles[i]))[:8]]}
    by_day = collections.defaultdict(lambda: [0, 0])
    for i, env in enumerate(envs):
        day = str(env["metadata"].get("scraped_at") or "")[:10]
        by_day[day][0] += 1
        by_day[day][1] += i in set(non_it)
    out["title"]["non_it_by_crawl_day"] = {d: v for d, v in sorted(by_day.items()) if v[0] >= 20}
    groups = collections.defaultdict(set)
    for f in flats:
        if not is_empty(f.get("company_name")):
            groups[norm_company(f["company_name"])].add(f["company_name"].strip())
    out["company"] = {"same_company_variants": sum(1 for g in groups.values() if len(g) > 1),
                      "example": next((sorted(g)[:3] for g in groups.values() if len(g) > 1), [])}
    return out


# ---------------------------------------------------------------- trùng lặp
def _week(value: Any) -> Optional[Tuple[int, int]]:
    d = parse_day(value)
    return d.isocalendar()[:2] if d else None


def dedup_funnel(rows: Sequence[Tuple[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Luật của người dùng: cùng công ty + tiêu đề + nơi làm việc + khung thời gian đăng; thêm từng điều kiện để thấy tác dụng."""
    steps = [("Tiêu đề + công ty", 2), ("+ thành phố", 3), ("+ tuần đăng (thiếu ngày đăng thì dùng tuần cào)", 4)]
    keyed = []
    for src, f in rows:
        title, company = norm(f.get("job_title")), norm_company(f.get("company_name"))
        if not title or not company:
            continue
        city = norm(((f.get("working_locations") or [None])[0]) or f.get("raw_location_text"))[:20]
        week = _week(f.get("raw_posted_date")) or _week(f.get("crawled_at"))
        keyed.append((src, (title, company, city, week)))
    result = []
    for label, size in steps:
        groups = collections.defaultdict(list)
        for src, key in keyed:
            groups[key[:size]].append(src)
        dup = [g for g in groups.values() if len(g) > 1]
        result.append({"step": label, "extra_jobs": sum(len(g) - 1 for g in dup),
                       "groups_same_source": sum(1 for g in dup if len(set(g)) == 1),
                       "groups_cross_source": sum(1 for g in dup if len(set(g)) > 1)})
    return result


# ---------------------------------------------------------------- tổng hợp
def compute(data_dir: Path, sources: Iterable[str] = SOURCES) -> Dict[str, Any]:
    per: Dict[str, Any] = {}
    rows: List[Tuple[str, Dict[str, Any]]] = []
    for src in sources:
        envs, files = latest_envelopes(data_dir / src / "raw")
        flats = [flatten_raw_job_record(e, src) for e in envs]
        per[src] = {"jobs": len(flats), "files": files}
        if flats:
            per[src].update(source_stats(flats, envs))
            per[src]["address_pct"] = per[src]["fill"].get("company_address", 0.0)
        rows += [(src, f) for f in flats]
    with_data = [s for s in per if per[s]["jobs"]]
    fields = list(per[with_data[0]]["fill"]) if with_data else []
    matrix = []
    for field in fields:
        have = [s for s in with_data if per[s]["fill"][field] >= FIELD_PRESENT_PCT]
        matrix.append({"field": field, "sources": len(have), "keep": len(have) >= MIN_SOURCES_TO_KEEP,
                       "missing_in": [s for s in with_data if s not in have]})
    return {"generated_on": date.today().isoformat(), "total_jobs": sum(per[s]["jobs"] for s in per),
            "sources": per, "field_matrix": matrix, "dedup": dedup_funnel(rows), "topdev_api_probe": TOPDEV_API_PROBE}


# ---------------------------------------------------------------- HTML
CSS = """
:root{--bg:#F4F4F7;--card:#fff;--line:#ECEBF2;--ink:#1C1B26;--muted:#6B6A7B;--brand:#5B4CE6;--ok:#1E9E62;--warn:#E08A1E;--bad:#D6404E}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 "Be Vietnam Pro",system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:0 0 12px}
h3{font-size:15px;margin:18px 0 8px}p{margin:6px 0}.muted{color:var(--muted)}a{color:var(--brand)}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 18px 20px;margin:16px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}.kpi b{display:block;font-size:22px}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{font-weight:600;background:#FAFAFC;white-space:nowrap}
td.n{text-align:right;font-variant-numeric:tabular-nums}.tag{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600}
.high{background:#FBE5E7;color:var(--bad)}.mid{background:#FCEFD9;color:#9A5B0C}.low{background:#E7F6EE;color:var(--ok)}.fixable{background:#ECEAFD;color:var(--brand)}
.bar{display:flex;align-items:center;gap:8px;margin:3px 0}.bar span.l{width:96px;flex:none;font-size:13px}.bar span.t{flex:1;min-width:0;max-width:300px}.bar i{display:block;height:14px;border-radius:4px;background:var(--brand)}
.bar em{font-style:normal;font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.heat td.h{text-align:center;font-variant-numeric:tabular-nums;font-size:12.5px}code{background:#F1F0F6;border-radius:5px;padding:1px 5px;font-size:12.5px}
p,li,.note,code{overflow-wrap:anywhere}
.note{border-left:3px solid var(--brand);padding:6px 12px;background:#F7F6FE;border-radius:0 8px 8px 0;margin:10px 0}
"""


def _e(value: Any) -> str:
    return html.escape(str(value))


def _bars(values: Dict[str, float], unit: str = "%", max_value: Optional[float] = None) -> str:
    top = max_value or max([v for v in values.values()] + [1])
    rows = "".join(f'<div class="bar"><span class="l">{_e(k)}</span><span class="t"><i style="width:{max(1, 100 * v / top):.0f}%"></i></span>'
                   f"<em>{v:g}{unit}</em></div>" for k, v in values.items())
    return f'<div>{rows}</div>'


def _table(head: Sequence[str], rows: Iterable[Sequence[Any]], numeric_from: int = 1) -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f'<td class="n">{_e(c)}</td>' if i >= numeric_from else f"<td>{c}</td>"
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _heat(value: float) -> str:
    # 0% đỏ → 100% xanh, độ đậm theo tỉ lệ
    color = "214,64,78" if value < 50 else "30,158,98"
    alpha = 0.12 + 0.55 * (abs(value - 50) / 50)
    return f'<td class="h" style="background:rgba({color},{alpha:.2f})">{value:g}</td>'


def render_html(stats: Dict[str, Any]) -> str:
    per = stats["sources"]
    S = [s for s in per if per[s]["jobs"]]
    val = lambda sec, key: {s: per[s][sec][key] for s in S}  # noqa: E731
    td = per.get("topdev", {})
    probe = stats["topdev_api_probe"]
    dedup = stats["dedup"]
    keep = [m for m in stats["field_matrix"] if m["keep"]]
    drop = [m for m in stats["field_matrix"] if not m["keep"]]

    parts = [f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vấn đề dữ liệu raw</title><style>{CSS}</style></head><body><main>
<h1>Vấn đề dữ liệu raw trước khi refactor pre-processing</h1>
<p class="muted">Sinh bởi <code>scripts/report_data_issues.py</code> ngày {_e(stats['generated_on'])}. Mỗi tin lấy snapshot mới nhất, làm phẳng bằng
<code>flatten_raw_job_record</code> hiện tại. Chỉ đọc dữ liệu. Chi tiết việc cần làm: <code>docs/spec/preprocessing/data_issues_2026-11-03.md</code>.</p>
<div class="kpis"><div class="kpi"><span class="muted">Tin (bản mới nhất)</span><b>{stats['total_jobs']:,}</b></div>
<div class="kpi"><span class="muted">Nguồn</span><b>{len(S)}</b></div>
<div class="kpi"><span class="muted">Trường giữ cho integration</span><b>{len(keep)}/{len(stats['field_matrix'])}</b></div>
<div class="kpi"><span class="muted">Tin trùng (luật đầy đủ)</span><b>{dedup[-1]['extra_jobs']:,}</b></div></div>
<p><span class="tag high">Cao</span> làm sai số liệu phân tích · <span class="tag mid">TB</span> mất thông tin hoặc khó so nguồn ·
<span class="tag low">Thấp</span> làm sạch thêm · <span class="tag fixable">Khắc phục được</span> trích xuất lại hoặc cào lại là hết</p>"""]

    parts.append("<section><h2>Số tin theo nguồn</h2>" + _table(
        ["Nguồn", "Tin", "Snapshot", "Snapshot v>1", "File batch cũ (tin)"],
        [(s, per[s]["jobs"], per[s]["files"].get("snapshot", 0), per[s]["files"].get("snapshot_v_lớn_hơn_1", 0),
          f"{per[s]['files'].get('file_batch', 0)} ({per[s]['files'].get('tin_trong_batch', 0)})") for s in S]) + "</section>")

    # A
    day_rows = [(d, v[0], v[1], f"{pct(v[1], v[0]):g}%") for d, v in td.get("title", {}).get("non_it_by_crawl_day", {}).items()]
    examples = "".join(f'<li><a href="{_e(x["url"])}" rel="noopener">{_e(x["title"])}</a></li>'
                       for x in td.get("title", {}).get("non_it_examples", []))
    parts.append(f"""<section><h2>A. Phạm vi dữ liệu</h2>
<h3><span class="tag high">Cao</span> A1. Tin ngoài IT lẫn vào (ước lượng theo từ khóa tiêu đề)</h3>{_bars(val('title', 'non_it_pct'), max_value=100)}
<p class="muted">Bộ lọc từ khóa thô: dùng để thấy độ lớn, phân loại thật làm ở bước normalization (gắn cờ, không xóa).</p>
<h3>Bằng chứng TopDev</h3>
<p>Tỉ lệ tiêu đề ngoài IT gần như không đổi giữa các đợt cào, nên không phải do một đợt lỗi:</p>
{_table(["Ngày cào", "Tin", "Ngoài IT", "Tỉ lệ"], day_rows)}
<div class="note">Discovery gọi <code>GET /td/v2/jobs</code> với <code>category_ids=1</code> ({_e(probe['code'])}). Đo ngày {_e(probe['measured_on'])}:
có <code>category_ids=1</code> tổng <b>{probe['with_category_ids_1_total']:,}</b> tin, bỏ tham số tổng <b>{probe['without_category_ids_total']:,}</b> tin,
trang 1 giống nhau {_e(probe['page1_same_titles'])}. Kết luận: <b>API bỏ qua tham số này</b>, nên crawler đang cào toàn bộ TopDev (TopDev nay đăng cả tin ngoài IT).
<code>job_posting_jsonld.industry</code> cũng ghi "Information Technology" cho nhiều tin ngoài IT, nên không lọc bằng trường đó được.</div>
<p>Ví dụ tin ngoài IT trong raw TopDev:</p><ul>{examples}</ul>
<h3><span class="tag fixable">Khắc phục được</span> A2. ITviec lưu ngày đăng dạng "Đăng 6 giờ trước"</h3>
<p>Raw đã có <code>job_posting_jsonld.datePosted</code> dạng ngày tuyệt đối → sửa flattener là đủ, không cần cào lại.
Riêng crawler phải bỏ <code>posted_at_raw</code> khỏi hash, nếu không mỗi lần cào lại sẽ sinh version mới vô ích.
Số tin đang có ngày tương đối: <b>{per.get('itviec', {}).get('dates', {}).get('posted_relative', 0):,}</b>.</p>
<h3><span class="tag fixable">Khắc phục được</span> A3. Raw TopDev cũ thiếu kinh nghiệm, cấp bậc, ngày đăng</h3>
<p><code>DETAIL_FIELDS</code> đã sửa ngày 02/11 → cào lại là có đủ (SCRAPE-5).</p></section>""")

    # B
    parts.append(f"""<section><h2>B. Trùng lặp</h2>
<p>Luật: <b>cùng công ty + cùng tiêu đề + cùng nơi làm việc + cùng khung thời gian đăng</b>. Thêm lần lượt từng điều kiện:</p>
{_table(["Điều kiện", "Tin thừa", "Nhóm trong 1 nguồn", "Nhóm khác nguồn"],
        [(d["step"], d["extra_jobs"], d["groups_same_source"], d["groups_cross_source"]) for d in dedup])}
<div class="note">Thêm điều kiện thành phố làm số nhóm trùng khác nguồn tụt từ <b>{dedup[0]['groups_cross_source']}</b> xuống
<b>{dedup[1]['groups_cross_source']}</b>: mỗi nguồn ghi thành phố một kiểu ("TP Hồ Chí Minh", "Hồ Chí Minh", địa chỉ đường phố…).
Phải <b>chuẩn hóa thành phố trước</b> rồi mới so trùng. Trụ sở công ty không dùng làm điều kiện được vì TopDev có
{_e(per.get('topdev', {}).get('address_pct', 0))}% tin có địa chỉ; TopCV và TopDev không có ngày đăng nên tạm dùng tuần cào.</div>
<p>Trùng do version cũ và file batch đã được loại ngay khi lấy snapshot mới nhất (bảng đầu trang).</p></section>""")

    # C
    head = "".join(f"<th>{_e(s)}</th>" for s in S)
    rows = ""
    for m in stats["field_matrix"]:
        cells = "".join(_heat(per[s]["fill"][m["field"]]) for s in S)
        badge = '<span class="tag low">Giữ</span>' if m["keep"] else '<span class="tag high">Bỏ</span>'
        rows += f"<tr><td><code>{_e(m['field'])}</code></td>{cells}<td class='n'>{m['sources']}/{len(S)}</td><td>{badge}</td></tr>"
    parts.append(f"""<section><h2>C. Độ phủ trường sau làm phẳng (% tin có giá trị)</h2>
<p>Luật: trích xuất được thì lấy, không thì để null; chỉ giữ trường mà <b>ít nhất {MIN_SOURCES_TO_KEEP} nguồn</b> có (≥ {FIELD_PRESENT_PCT}% tin có giá trị).
Giữ <b>{len(keep)}</b> trường, bỏ <b>{len(drop)}</b>: {", ".join(f"<code>{_e(m['field'])}</code> ({m['sources']} nguồn)" for m in drop)}.</p>
<div class="scroll heat"><table><thead><tr><th>Trường</th>{head}<th>Số nguồn có</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="muted">Ô đỏ là chỗ cần xem: nguồn có dữ liệu nhưng flattener chưa đọc (TopDev ngày đăng/kinh nghiệm, ITviec ngày đăng), hoặc nguồn thật sự không có.</p></section>""")

    # D
    parts.append(f"""<section><h2>D. Lương</h2>
<h3>Tỉ lệ lương thỏa thuận (giữ NaN + cờ, không bù)</h3>{_bars(val('salary', 'negotiable_pct'), max_value=100)}
<h3><span class="tag high">Cao</span> Bộ parse lương ra kết quả sai</h3>
{_table(["Nguồn", "Ra lương < 1 triệu VND", "\"Từ X\" bị gán max = min", "Chỉ một đầu (Up to/Tới)", "Lương USD %", "Lương trong tiêu đề"],
        [(s, per[s]["salary"]["parsed_under_1m"], per[s]["salary"]["from_x_max_equals_min"], per[s]["salary"]["one_sided"],
          per[s]["salary"]["usd_pct"], per[s]["salary"]["in_title"]) for s in S])}
<p>Ví dụ: {"; ".join(_e(x) for s in S for x in per[s]["salary"]["parsed_under_1m_examples"][:1])}.
Nguyên nhân chính: dấu phân cách hàng nghìn ("2,000", "4.000") bị đọc như dấu thập phân. Một phần lương &lt; 1 triệu là thực tập thật ("0.5 - 1 triệu").</p></section>""")

    # E–I
    parts.append(f"""<section><h2>E. Địa điểm</h2>{_table(["Nguồn", "Giá trị khác nhau", "Nhiều thành phố / chuỗi", "Có dạng địa chỉ đường phố", "working_locations rỗng %"],
        [(s, per[s]["location"]["distinct"], per[s]["location"]["multi_city"], per[s]["location"]["street_address"],
          per[s]["location"]["working_locations_empty_pct"]) for s in S])}</section>""")
    parts.append(f"""<section><h2>F. Kinh nghiệm và cấp bậc</h2>{_table(["Nguồn", "Kinh nghiệm: số dạng", "Không có số", "Dạng khoảng", "Cấp bậc: số giá trị", "Cấp bậc phổ biến"],
        [(s, per[s]["experience"]["distinct"], per[s]["experience"]["no_number"], per[s]["experience"]["range"],
          per[s]["seniority"]["distinct"], ", ".join(f"{_e(k)} ({c})" for k, c in per[s]["seniority"]["top"][:4])) for s in S], numeric_from=1)}
<p class="muted">Mỗi nguồn một bộ từ cấp bậc → cần bảng ánh xạ theo nguồn. ITviec, Glints, TopDev không có cấp bậc.</p></section>""")
    parts.append(f"""<section><h2>G. Kỹ năng</h2><h3>Tỉ lệ tin không có kỹ năng</h3>{_bars(val('skills', 'empty_pct'), max_value=100)}
{_table(["Nguồn", "TB số kỹ năng", "Tag dài > 4 từ", "Tag phổ biến (thường là danh mục ngành, không phải kỹ năng)"],
        [(s, per[s]["skills"]["avg"], per[s]["skills"]["long_tags"], ", ".join(_e(t) for t, _ in per[s]["skills"]["top"])) for s in S], numeric_from=1)}</section>""")
    parts.append(f"""<section><h2>H. Ngày tháng</h2>{_table(["Nguồn", "Ngày đăng rỗng %", "Ngày đăng tương đối", "Đăng > 90 ngày", "Hạn nộp rỗng %", "Hạn nộp trước ngày cào"],
        [(s, per[s]["dates"]["posted_empty_pct"], per[s]["dates"]["posted_relative"], per[s]["dates"]["posted_older_90d"],
          per[s]["dates"]["deadline_empty_pct"], per[s]["dates"]["deadline_before_crawl"]) for s in S])}</section>""")
    parts.append(f"""<section><h2>I. Văn bản, tiêu đề, công ty</h2>{_table(["Nguồn", "JD rỗng %", "JD < 200 ký tự", "Còn HTML", "300 ký tự đầu JD trùng", "Tiêu đề có mã/ngoặc", "Viết hoa toàn bộ", "Cty khác cách viết", "Null trá hình"],
        [(s, per[s]["text"]["jd_empty_pct"], per[s]["text"]["jd_short"], per[s]["text"]["html_left"], per[s]["text"]["jd_same_head"],
          per[s]["title"]["codes_brackets"], per[s]["title"]["all_caps"], per[s]["company"]["same_company_variants"],
          "; ".join(f"{k} ({c})" for k, c in per[s]["sneaky_null"]) or "—") for s in S])}</section>""")

    links = [("A1 Tin ngoài IT", "mới (SCRAPE: phạm vi TopDev, Vieclam24h)", "P4 gắn cờ is_it_job"),
             ("A2 Ngày tương đối ITviec", "mới", "P1 (flattener) + sửa crawler"),
             ("A3 TopDev thiếu trường", "SCRAPE-5", "cào lại"),
             ("B Trùng lặp", "PRE-8 (file batch)", "P1 (version, batch) + P5 (luật trùng)"),
             ("C Độ phủ trường", "PRE-7 (TopDev)", "P1"),
             ("D Parse lương", "mới", "P2"),
             ("E Địa điểm", "PRE-3", "P4"),
             ("F Kinh nghiệm, cấp bậc", "PRE-1", "P2 + P4"),
             ("G Kỹ năng", "PRE-6", "P1"),
             ("H Ngày tháng", "mới", "P1 + P2"),
             ("I Văn bản, công ty", "mới", "P4")]
    parts.append("<section><h2>Liên hệ với việc đang mở và phase refactor</h2>" +
                 _table(["Vấn đề", "Mục trong KNOWN_ISSUED.md", "Phase xử lý"], links, numeric_from=9) + "</section>")
    parts.append("</main></body></html>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "spec" / "preprocessing" / "data_issues_2026-11-03.html")
    args = parser.parse_args()
    stats = compute(args.data_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_html(stats), encoding="utf-8")
    print(f"Đã ghi {args.out}: {stats['total_jobs']:,} tin, trùng theo luật đầy đủ {stats['dedup'][-1]['extra_jobs']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
