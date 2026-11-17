#!/usr/bin/env python3
"""Trực quan hóa tầng Bronze (raw/ + url_ledger/) của từng nguồn thành trang HTML tĩnh.

Chỉ đọc dữ liệu trên máy (data/<nguồn>/raw/, data/<nguồn>/url_ledger/catalog_master.json),
không gọi R2 hay mạng. Tải Bronze trước bằng scripts/sync_cloud_lakehouse.py --download.

    python scripts/visualize_raw_bronze.py [--source topcv] [--out docs/presentation/raw_bronze]

Đầu ra: <out>/<nguồn>.html cho từng nguồn và <out>/index.html (bảng tổng hợp 8 nguồn).
Mọi số liệu tính từ file thật; nguồn chưa có dữ liệu thì trang ghi rõ "chưa có dữ liệu".
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import html
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from preprocessing.common.raw_reader import read_raw, snapshot_order  # noqa: E402
from preprocessing.integration.json_flattener import flatten_raw_job_record  # noqa: E402
from preprocessing.transformation.date_parser import parse_date  # noqa: E402
import _viz_html as V  # noqa: E402  (scripts/_viz_html.py)

SOURCES = ("topcv", "topdev", "vietnamworks", "careerviet", "vieclam24h", "itviec", "glints", "jobsgo")
TEXT_FIELDS = ("raw_salary_text", "raw_experience_text", "raw_seniority_text", "raw_employment_type",
               "raw_work_mode", "raw_category_text", "raw_education_text")


def _filled(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict, tuple)):
        return len(v) > 0
    return True


def _type_name(v: Any) -> str:
    return {dict: "object", list: "list", str: "string", bool: "bool", int: "number",
            float: "number", type(None): "null"}.get(type(v), type(v).__name__)


def _sample(v: Any, n: int = 100) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    s = " ".join(s.split())
    return s[:n] + ("…" if len(s) > n else "")


def _day(ts: Any) -> str | None:
    s = str(ts or "")
    return s[:10] if len(s) >= 10 and s[4] == "-" else None


MONTH_FLOOR = "2026-08"  # tháng sớm hơn gộp thành một cột, để trục không bị kéo dài vì vài tin cũ


def _months(counter: collections.Counter) -> List[List[Any]]:
    old = sum(c for m, c in counter.items() if m < MONTH_FLOOR)
    rows = [[m, c] for m, c in sorted(counter.items()) if m >= MONTH_FLOOR]
    return ([[f"trước {MONTH_FLOOR[5:]}/{MONTH_FLOOR[:4]}", old]] if old else []) + rows


_vn = V.vn
_top = V.top
_hist = V.hist


def profile_source(source: str, data_dir: Path) -> Dict[str, Any]:
    raw_dir = data_dir / source / "raw"
    ledger_path = data_dir / source / "url_ledger" / "catalog_master.json"
    res: Dict[str, Any] = {"source": source, "has_raw": raw_dir.exists(), "has_ledger": ledger_path.exists()}

    # Ledger
    if ledger_path.exists():
        led = json.loads(ledger_path.read_text(encoding="utf-8"))
        recs = list(led.values()) if isinstance(led, dict) else list(led)
        res["ledger_total"] = len(recs)
        res["ledger_status"] = _top(collections.Counter(str(r.get("status")) for r in recs), 10)
        res["ledger_discovered_by_day"] = sorted(collections.Counter(
            d for d in (_day(r.get("discovered_at")) for r in recs) if d).items())
        res["ledger_scraped_by_day"] = sorted(collections.Counter(
            d for d in (_day(r.get("last_scraped_at")) for r in recs) if d).items())

    snapshots, batch, counts = read_raw(raw_dir)
    res["raw_counts"] = counts
    res["raw_files"] = len(snapshots)
    if not snapshots:
        return res

    by_job: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for _, env in snapshots:
        by_job[str(env["metadata"].get("job_id") or "")].append(env)
    res["unique_jobs"] = len(by_job)
    res["versions_per_job"] = sorted(collections.Counter(len(v) for v in by_job.values()).items())
    res["scraped_by_day"] = sorted(collections.Counter(
        d for d in (_day(env["metadata"].get("scraped_at")) for _, env in snapshots) if d).items())

    first_month: collections.Counter = collections.Counter()
    posted_month: collections.Counter = collections.Counter()
    no_posted = 0
    key_fill: collections.Counter = collections.Counter()
    key_types: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    key_sample: Dict[str, str] = {}
    flat_fill: collections.Counter = collections.Counter()
    tops = {f: collections.Counter() for f in TEXT_FIELDS}
    loc, skills, bens = collections.Counter(), collections.Counter(), collections.Counter()
    bens_per_job, desc_len, req_len = [], [], []
    flat_keys: List[str] = []

    for envs in by_job.values():
        first = min(envs, key=snapshot_order)
        latest = max(envs, key=snapshot_order)
        fd = _day(first["metadata"].get("scraped_at"))
        if fd:
            first_month[fd[:7]] += 1
        payload = latest.get("raw_payload") or {}
        for k, v in payload.items():
            key_types[k][_type_name(v)] += 1
            if _filled(v):
                key_fill[k] += 1
                key_sample.setdefault(k, _sample(v))
        flat = flatten_raw_job_record(latest, source_fallback=source)
        if not flat_keys:
            flat_keys = [k for k in flat if k not in ("job_id", "source_platform", "source", "url", "crawled_at")]
        for k in flat_keys:
            flat_fill[k] += _filled(flat.get(k))
        pdte = parse_date(flat.get("raw_posted_date"))
        if pdte:
            posted_month[pdte[:7]] += 1
        else:
            no_posted += 1
        for f in TEXT_FIELDS:
            if _filled(flat.get(f)):
                tops[f][" ".join(str(flat[f]).split())[:80]] += 1
        for x in flat.get("working_locations") or []:
            loc[" ".join(str(x).split())[:80]] += 1
        for x in flat.get("skills_list") or []:
            skills[str(x).strip()[:60]] += 1
        bl = flat.get("benefits_list") or []
        bens_per_job.append(len(bl))
        for x in bl:
            bens[" ".join(str(x).split())[:90]] += 1
        desc_len.append(len(flat.get("raw_description_text") or ""))
        req_len.append(len(flat.get("raw_requirements_text") or ""))

    n = len(by_job)
    res["first_crawl_month"] = sorted(first_month.items())
    res["posted_month"] = sorted(posted_month.items())  # đủ tháng, cho index gộp; biểu đồ dùng _months()
    res["no_posted_date"] = no_posted
    res["payload_keys"] = sorted(
        ([k, round(100 * key_fill[k] / n, 1), ", ".join(t for t, _ in key_types[k].most_common()), key_sample.get(k, "")]
         for k in key_types), key=lambda r: (-r[1], r[0]))
    res["flat_fill"] = [[k, round(100 * flat_fill[k] / n, 1)] for k in flat_keys]
    res["tops"] = {f: _top(c) for f, c in tops.items()}
    res["top_locations"] = _top(loc)
    res["top_skills"] = _top(skills, 20)
    res["top_benefits"] = _top(bens, 20)
    res["benefits_per_job"] = _hist(bens_per_job, [0, 1, 3, 6, 10, 15])
    res["desc_len"] = _hist(desc_len, [0, 1, 500, 1000, 2000, 4000, 8000])
    res["req_len"] = _hist(req_len, [0, 1, 300, 600, 1200, 2400, 4800])
    res["median_desc_len"] = int(statistics.median(desc_len)) if desc_len else 0
    return res


# ─────────────────────────── HTML ───────────────────────────

_chart, _card, _tile = V.chart, V.card, V.tile
FOOTER = ("Sinh bằng <code>scripts/visualize_raw_bronze.py</code> lúc {g}, từ dữ liệu Bronze trên máy "
          "(data/&lt;nguồn&gt;/raw, url_ledger). Không có số giả định.")


def _page(title: str, nav: str, body: str, generated: str) -> str:
    return V.page(title, nav, body, FOOTER.format(g=generated))


def _nav(active: str) -> str:
    return V.nav([("index", "Tổng hợp")] + [(s, s) for s in SOURCES], active)


def render_source(p: Dict[str, Any], generated: str) -> str:
    s = p["source"]
    head = f"<h1>Bronze · {s}</h1><p class='sub'>Toàn bộ raw và URL ledger của nguồn {s}, trước mọi bước xử lý.</p>"
    if not p.get("raw_files"):
        msg = "chưa có file raw trên máy" if not p["has_raw"] else "thư mục raw không có snapshot hợp lệ"
        led = f" Ledger có {_vn(p.get('ledger_total', 0))} URL." if p.get("has_ledger") else ""
        return _page(f"Bronze {s}", _nav(s), head + f'<div class="empty">Chưa có dữ liệu: {msg}.{led}</div>', generated)

    n = p["unique_jobs"]
    status = dict(p.get("ledger_status", []))
    tiles = "".join([
        _tile(p["raw_files"], "file raw (snapshot)"), _tile(n, "tin duy nhất (job_id)"),
        _tile(p.get("ledger_total", 0), "URL trong ledger"), _tile(status.get("PENDING", 0), "URL PENDING (chưa cào)"),
        _tile(p["no_posted_date"], "tin không có ngày đăng"), _tile(p["median_desc_len"], "ký tự mô tả (trung vị)"),
    ])
    body = head + f"<div class='tiles'>{tiles}</div>"

    body += "<h2>1. Thời gian</h2><p class='note'>Tháng đăng lấy từ ngày đăng của nguồn (parse như bước 03); tin không có ngày đăng không nằm trong biểu đồ đăng.</p><div class='grid2'>"
    body += _card("Tin theo tháng đăng", f"{_vn(n - p['no_posted_date'])} / {_vn(n)} tin có ngày đăng parse được", _chart("v", _months(collections.Counter(dict(p["posted_month"])))))
    body += _card("Tin theo tháng cào lần đầu", "Theo snapshot sớm nhất của mỗi job_id", _chart("v", p["first_crawl_month"]))
    body += _card("Snapshot theo ngày cào", "Mỗi lần cào (kể cả cào lại) là một snapshot", _chart("v", p["scraped_by_day"], "file"))
    body += _card("URL phát hiện theo ngày (ledger)", "Trường discovered_at của ledger", _chart("v", p.get("ledger_discovered_by_day", []), "URL"))
    body += "</div>"

    body += "<h2>2. Ledger và phiên bản</h2><div class='grid2'>"
    body += _card("Trạng thái URL trong ledger", "PENDING: đã phát hiện, chưa cào chi tiết", _chart("h", p.get("ledger_status", []), "URL", p.get("ledger_total")))
    body += _card("Số snapshot mỗi tin", "1 = chỉ cào một lần; > 1 = cào lại hoặc nội dung đổi", _chart("h", [[f"{k} snapshot", v] for k, v in p["versions_per_job"]], "tin", n))
    body += "</div>"

    rows = "".join(
        f"<tr><td><code>{html.escape(k)}</code></td><td class='n'><span class='meter'><i style='width:{f}%'></i></span>{f}%</td>"
        f"<td>{html.escape(t)}</td><td class='samp'>{html.escape(smp)}</td></tr>" for k, f, t, smp in p["payload_keys"])
    body += ("<h2>3. Trường trong raw_payload</h2><p class='note'>Mỗi khóa cấp 1 của raw_payload ở snapshot mới nhất của mỗi tin: tỷ lệ có giá trị, kiểu, một giá trị mẫu (cắt 100 ký tự).</p>"
             f"<div class='card scroll tbox'><table><tr><th>Khóa</th><th>Có giá trị</th><th>Kiểu</th><th>Mẫu</th></tr>{rows}</table></div>")

    ff = sorted(p["flat_fill"], key=lambda r: -r[1])
    body += ("<h2>4. Độ phủ sau khi làm phẳng (25 trường chuẩn)</h2><p class='note'>Cùng bộ làm phẳng của bước 02 (json_flattener), chỉ để đo; không ghi file nào.</p>"
             + f"<div class='card' style='max-width:640px'>{_chart('h', ff, '%')}</div>")

    labels = {"raw_salary_text": "Lương (chữ gốc)", "raw_experience_text": "Kinh nghiệm", "raw_seniority_text": "Cấp bậc",
              "raw_employment_type": "Loại hình", "raw_work_mode": "Hình thức làm việc", "raw_category_text": "Ngành nghề",
              "raw_education_text": "Học vấn"}
    body += "<h2>5. Giá trị hay gặp</h2><p class='note'>Top 15 giá trị chữ gốc, chưa chuẩn hóa.</p><div class='grid2'>"
    for f, lab in labels.items():
        if p["tops"].get(f):
            body += _card(lab, f"<code>{f}</code>", _chart("h", p["tops"][f], "tin", n))
    body += _card("Địa điểm", "<code>working_locations</code>", _chart("h", p["top_locations"], "tin", n))
    body += _card("Kỹ năng (tag nguồn)", "<code>skills_list</code>, top 20", _chart("h", p["top_skills"], "tin", n))
    body += "</div>"

    body += "<h2>6. Phúc lợi và độ dài văn bản</h2><div class='grid2'>"
    body += _card("Số item phúc lợi mỗi tin", "<code>benefits_list</code> sau khi tách theo luật bước 02", _chart("v", p["benefits_per_job"]))
    body += _card("Item phúc lợi hay gặp", "Top 20, chữ gốc", _chart("h", p["top_benefits"], "tin", n))
    body += _card("Độ dài mô tả (ký tự)", "<code>raw_description_text</code>", _chart("v", p["desc_len"]))
    body += _card("Độ dài yêu cầu (ký tự)", "<code>raw_requirements_text</code>", _chart("v", p["req_len"]))
    body += "</div>"
    return _page(f"Bronze {s}", _nav(s), body, generated)


def render_index(profiles: List[Dict[str, Any]], generated: str) -> str:
    rows, months = "", collections.Counter()
    for p in profiles:
        st = dict(p.get("ledger_status", []))
        n = p.get("unique_jobs", 0)
        has = n - p.get("no_posted_date", 0) if n else 0
        for m, c in p.get("posted_month", []):
            months[m] += c
        sep = sum(c for m, c in p.get("posted_month", []) if m == "2026-09")
        rows += (f"<tr><td><a href='{p['source']}.html'>{p['source']}</a></td><td class='n'>{_vn(p.get('raw_files', 0))}</td>"
                 f"<td class='n'>{_vn(n)}</td><td class='n'>{_vn(p.get('ledger_total', 0))}</td><td class='n'>{_vn(st.get('DONE', 0))}</td>"
                 f"<td class='n'>{_vn(st.get('PENDING', 0))}</td><td class='n'>{_vn(100 * has / n if n else 0.0)}%</td>"
                 f"<td class='n'>{_vn(sep)}</td></tr>")
    tot_jobs = sum(p.get("unique_jobs", 0) for p in profiles)
    body = ("<h1>Bronze · 8 nguồn</h1><p class='sub'>Tổng quan raw và URL ledger trước mọi bước xử lý.</p>"
            f"<div class='tiles'>{_tile(sum(p.get('raw_files', 0) for p in profiles), 'file raw')}{_tile(tot_jobs, 'tin duy nhất')}"
            f"{_tile(sum(p.get('ledger_total', 0) for p in profiles), 'URL trong ledger')}</div>"
            "<h2>Theo nguồn</h2><div class='card scroll'><table><tr><th>Nguồn</th><th>File raw</th><th>Tin duy nhất</th>"
            f"<th>URL ledger</th><th>DONE</th><th>PENDING</th><th>Có ngày đăng</th><th>Đăng tháng 9</th></tr>{rows}</table></div>"
            "<h2>Phân bố</h2><div class='grid2'>"
            + _card("Tin theo tháng đăng (gộp các nguồn)", "Chỉ tin có ngày đăng parse được; topcv không ghi ngày đăng nên không có ở đây",
                    _chart("v", _months(months)))
            + _card("Tin duy nhất theo nguồn", "", _chart("h", sorted([[p["source"], p.get("unique_jobs", 0)] for p in profiles], key=lambda r: -r[1]), "tin", tot_jobs))
            + "</div>")
    return _page("Bronze tổng hợp", _nav("index"), body, generated)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=SOURCES)
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "presentation" / "raw_bronze"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    generated = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    profiles = []
    for s in ([a.source] if a.source else SOURCES):
        p = profile_source(s, Path(a.data_dir))
        profiles.append(p)
        (out / f"{s}.html").write_text(render_source(p, generated), encoding="utf-8")
        print(f"{s}: {p.get('raw_files', 0):,} file raw, {p.get('unique_jobs', 0):,} tin, ledger {p.get('ledger_total', 0):,}"
              f", tháng đăng {dict(p.get('posted_month', []))}")
    if not a.source:
        (out / "index.html").write_text(render_index(profiles, generated), encoding="utf-8")
        (out / "profiles.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Đã ghi {out}")


if __name__ == "__main__":
    main()
