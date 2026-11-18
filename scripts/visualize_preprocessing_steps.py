#!/usr/bin/env python3
"""Trực quan hóa dữ liệu qua từng bước pre-processing (01 → 04) thành trang HTML tĩnh.

Chỉ đọc file trên máy, không gọi R2 hay mạng:
- report của bước: reports/preprocessing/<bước>/_all.json và <nguồn>.json (số luật, số bỏ, độ phủ, mẫu);
- đầu ra của bước: data/preprocessing/<bước>/<nguồn>.jsonl (01, 01b) hoặc all.parquet (02 → 04),
  để đo độ phủ từng trường theo nguồn và phân bố các trường chính.

    python scripts/visualize_preprocessing_steps.py [--step 01_clean|...|all] [--out docs/presentation/preprocessing_steps]

Bước chưa có đầu ra trên máy thì trang tổng hợp ghi "chưa chạy lại", không vẽ số cũ như số mới.
Cột "Lần trước" lấy từ report đã commit (git HEAD), để so lần chạy này với lần trước.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import html
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _viz_html as V  # noqa: E402  (scripts/_viz_html.py)
from preprocessing.integration.json_flattener import flatten_raw_job_record  # noqa: E402

SOURCES = ("topcv", "topdev", "vietnamworks", "careerviet", "vieclam24h", "itviec", "glints", "jobsgo")
STEPS = {
    "01_clean": "Clean: giữ snapshot mới nhất, lọc IT, bỏ JD ngắn, bỏ tin CTV",
    "01b_deduplication": "Deduplication: khử trùng trong nguồn và giữa các nguồn",
    "02_integration": "Integration: làm phẳng 8 nguồn về một bảng",
    "03_transformation": "Transformation: lương, kinh nghiệm, ngày, làm sạch văn bản, kỹ năng, phúc lợi",
    "04_normalization": "Normalization: tỉnh, chức danh, nhóm nghề, cấp bậc, công ty, ngoại lai",
}
# Trường chính cần xem phân bố ở đầu ra mỗi bước (bỏ qua cột không có)
KEY_COLS = {
    "02_integration": ["raw_salary_text", "raw_experience_text", "raw_work_mode", "language"],
    "03_transformation": ["salary_min_vnd", "salary_max_vnd", "is_negotiable", "exp_min_years", "headcount",
                          "language", "benefits_std", "skills_std", "posted_date"],
    "04_normalization": ["tinh_chinh", "job_family", "seniority", "work_mode", "title_canonical",
                         "salary_min_vnd_capped", "salary_max_vnd_capped", "company_key", "benefits_std"],
}
MATRIX_KEYS_MAX = 40  # bảng nguồn × khóa: tối đa số khóa hiển thị


def _filled(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, float) and math.isnan(v):
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if hasattr(v, "__len__") and not isinstance(v, (str, bytes)):
        return len(v) > 0
    return True


def _short(v: Any, n: int = 160) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    s = " ".join(s.split())
    return s[:n] + ("…" if len(s) > n else "")


def _load(path: Path) -> Dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _prev_report(step: str) -> Dict[str, Any] | None:
    """Report đã commit (git HEAD) của bước, để so với lần chạy này."""
    try:
        out = subprocess.run(["git", "show", f"HEAD:reports/preprocessing/{step}/_all.json"], cwd=ROOT,
                             capture_output=True, check=True)
        return json.loads(out.stdout.decode("utf-8"))
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return None


# ─────────────────────────── đo trên đầu ra ───────────────────────────

def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def profile_output(step: str, data_dir: Path) -> Dict[str, Any] | None:
    """Độ phủ từng trường theo nguồn + phân bố trường chính, đo trên file đầu ra của bước."""
    sdir = data_dir / "preprocessing" / step
    if step in ("01_clean", "01b_deduplication"):
        files = {s: sdir / f"{s}.jsonl" for s in SOURCES}
        if not any(p.exists() for p in files.values()):
            return None
        rows_by_src: Dict[str, List[Dict[str, Any]]] = {}
        meta_keys: Dict[str, collections.Counter] = {}
        for s, p in files.items():
            recs = list(_iter_jsonl(p)) if p.exists() else []
            rows_by_src[s] = [flatten_raw_job_record(r, source_fallback=s) for r in recs]
            mk: collections.Counter = collections.Counter()
            for r in recs:
                for k, v in ((r.get("metadata") or {}).get("clean") or {}).items():
                    if k in ("it_status", "it_rule", "it_rule_level"):
                        mk[f"{k}={v}"] += 1
            meta_keys[s] = mk
        cols = [k for k in next((r for rs in rows_by_src.values() for r in rs), {})
                if k not in ("source_platform", "source")]
        res = _fill_matrix(cols, rows_by_src)
        res["note"] = ("Đo trên envelope đầu ra, làm phẳng bằng json_flattener (cùng bộ của bước 02) chỉ để đo; "
                       "chưa qua bước 03 nên lương, kinh nghiệm vẫn là chữ gốc.")
        res["clean_meta"] = {s: dict(c) for s, c in meta_keys.items()}
        return res

    pq = sdir / "all.parquet"
    if not pq.exists():
        return None
    import pandas as pd

    df = pd.read_parquet(pq)
    scol = "source_platform" if "source_platform" in df.columns else "source"
    rows_by_src = {s: df[df[scol] == s] for s in SOURCES}
    res = _fill_matrix_df(list(df.columns), rows_by_src)
    res["dtypes"] = {c: str(t) for c, t in df.dtypes.items()}
    res["samples"] = {c: _short(next((v for v in df[c] if _filled(v)), None), 90) for c in df.columns}
    res["key_cols"] = {}
    for c in KEY_COLS.get(step, []):
        if c in df.columns:
            res["key_cols"][c] = _distribution(df[c])
    res["note"] = f"Đo trên <code>data/preprocessing/{step}/all.parquet</code> ({V.vn(len(df))} dòng, {V.vn(len(df.columns))} cột)."
    return res


def _fill_matrix(cols: List[str], rows_by_src: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    n = {s: len(r) for s, r in rows_by_src.items()}
    tot = sum(n.values())
    fill = []
    for c in cols:
        per = {s: (round(100 * sum(_filled(r.get(c)) for r in rs) / len(rs), 1) if rs else None)
               for s, rs in rows_by_src.items()}
        allv = round(100 * sum(_filled(r.get(c)) for rs in rows_by_src.values() for r in rs) / tot, 1) if tot else None
        fill.append([c, allv, per])
    return {"rows": tot, "rows_by_source": n, "fill": fill}


def _fill_matrix_df(cols: List[str], parts: Dict[str, Any]) -> Dict[str, Any]:
    n = {s: len(p) for s, p in parts.items()}
    tot = sum(n.values())
    fill = []
    for c in cols:
        cnt = {s: int(sum(_filled(v) for v in p[c])) if len(p) else 0 for s, p in parts.items()}
        per = {s: (round(100 * cnt[s] / n[s], 1) if n[s] else None) for s in parts}
        fill.append([c, round(100 * sum(cnt.values()) / tot, 1) if tot else None, per])
    return {"rows": tot, "rows_by_source": n, "fill": fill}


def _distribution(series) -> Dict[str, Any]:
    vals = [v for v in series if _filled(v)]
    missing = len(series) - len(vals)
    if vals and all(isinstance(v, (bool,)) or str(type(v)).endswith("bool_'>") for v in vals[:50]):
        return {"kind": "cat", "rows": V.top(collections.Counter(str(bool(v)) for v in vals)), "missing": missing}
    if vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals[:200]):
        xs = sorted(float(v) for v in vals)
        q = [xs[int(p * (len(xs) - 1))] for p in (0.0, 0.25, 0.5, 0.75, 1.0)]
        big = q[2] >= 100_000
        div = 1_000_000 if big else 1
        lo, hi = xs[0] / div, xs[int(0.99 * (len(xs) - 1))] / div
        step = max((hi - lo) / 10, 1e-9)
        nice = 10 ** math.floor(math.log10(step))
        step = math.ceil(step / nice) * nice
        if all(float(x).is_integer() for x in xs):  # số năm, số người: khoảng phải là số nguyên
            step = max(1, math.ceil(step))
        start = math.floor(lo / step) * step
        edges = [round(start + i * step, 6) for i in range(11)]
        edges = [int(e) if float(e).is_integer() else e for e in edges]
        return {"kind": "num", "unit": "triệu VND" if big else "", "rows": V.hist([x / div for x in xs], edges),
                "quantiles": [x / div for x in q], "missing": missing, "n": len(xs)}
    if vals and hasattr(vals[0], "__len__") and not isinstance(vals[0], str):
        c = collections.Counter(str(x) for v in vals for x in v)
        per = collections.Counter(min(len(v), 10) for v in vals)
        return {"kind": "list", "rows": V.top(c, 20), "per_row": sorted(per.items()), "missing": missing}
    return {"kind": "cat", "rows": V.top(collections.Counter(_short(v, 70) for v in vals), 15), "missing": missing,
            "distinct": len(set(map(str, vals)))}


# ─────────────────────────── HTML ───────────────────────────

FOOTER = ("Sinh bằng <code>scripts/visualize_preprocessing_steps.py</code> lúc {g}. Số liệu lấy từ report của bước "
          "(<code>reports/preprocessing/&lt;bước&gt;/</code>) và đo trên đầu ra trong <code>data/preprocessing/</code>. "
          "Không có số giả định.")


def _nav(active: str) -> str:
    return V.nav([("index", "Tổng hợp")] + [(s, s) for s in STEPS] + [("silver_gap", "Đối chiếu Silver")], active)


def _badge(action: str) -> str:
    return f"<span class='badge {html.escape(action)}'>{html.escape(action)}</span>"


def _src_table(rep_by_src: Dict[str, Dict[str, Any]], prev_src: Dict[str, Dict[str, int]]) -> str:
    rows = ""
    for s in SOURCES:
        r = rep_by_src.get(s)
        if not r:
            continue
        i, o = r["input"]["rows"], r["output"]["rows"]
        pv = prev_src.get(s, {})
        rows += (f"<tr><td>{s}</td><td class='n'>{V.vn(i)}</td><td class='n'>{V.vn(o)}</td><td class='n'>{V.vn(i - o)}</td>"
                 f"<td class='n'>{V.vn(100 * o / i if i else 0.0)}%</td>"
                 f"<td class='n'>{V.vn(pv['output']) if 'output' in pv else '–'}</td></tr>")
    return ("<div class='card scroll'><table><tr><th>Nguồn</th><th class='n'>Vào</th><th class='n'>Ra</th><th class='n'>Bỏ</th>"
            f"<th class='n'>Giữ lại</th><th class='n'>Ra (lần trước)</th></tr>{rows}</table></div>")


def _rules_table(rep: Dict[str, Any], prev: Dict[str, Any] | None) -> str:
    prev_rules = {r["id"]: r.get("rows_affected") for r in (prev or {}).get("rules", [])}
    head = "".join(f"<th class='n'>{s}</th>" for s in SOURCES)
    rows = ""
    for r in rep.get("rules", []):
        bs = r.get("by_source") or {}
        cells = "".join(f"<td class='n'>{V.vn(bs[s]) if s in bs else '–'}</td>" for s in SOURCES)
        pv = prev_rules.get(r["id"])
        diff = "" if pv is None or pv == r["rows_affected"] else f" <span class='warn'>(lần trước {V.vn(pv)})</span>"
        ex = r.get("examples") or []
        exs = ""
        if ex:
            exs = "<details><summary>Ví dụ</summary><div class='scroll'><table><tr><th>job_id</th><th>Trường</th><th>Trước</th><th>Sau</th></tr>" + "".join(
                f"<tr><td>{html.escape(str(e.get('job_id', '')))}</td><td><code>{html.escape(str(e.get('field', '')))}</code></td>"
                f"<td class='samp'>{html.escape(_short(e.get('before'), 140))}</td><td class='samp'>{html.escape(_short(e.get('after'), 140))}</td></tr>"
                for e in ex[:6]) + "</table></div></details>"
        rows += (f"<tr><td><b>{html.escape(r['id'])}</b></td><td>{html.escape(r.get('name', ''))}{exs}</td><td>{_badge(r.get('action', ''))}</td>"
                 f"<td class='n'>{V.vn(r.get('rows_affected', 0))}{diff}</td>{cells}</tr>")
    return (f"<div class='card scroll'><table><tr><th>Mã</th><th>Luật</th><th>Hành động</th><th class='n'>Số tin</th>{head}</tr>"
            f"{rows}</table></div>")


def _fill_table(prof: Dict[str, Any], rep_fields: List[Dict[str, Any]] | None) -> str:
    io = {f["field"]: f for f in rep_fields or []}
    head = "".join(f"<th class='n'>{s}</th>" for s in SOURCES)
    rows = ""
    for c, allv, per in prof["fill"]:
        f = io.get(c)
        inout = f"{V.vn(f['fill_pct_in'])} → " if f and f.get("fill_pct_in") is not None else ""
        rows += (f"<tr><td><code>{html.escape(c)}</code></td><td class='n'>{inout}{V.vn(allv) if allv is not None else '–'}</td>"
                 + "".join(V.heat(per.get(s)) for s in SOURCES) + "</tr>")
    return (f"<div class='card scroll tbox'><table><tr><th>Trường</th><th class='n'>Tất cả (%)</th>{head}</tr>{rows}</table></div>")


def _extra_html(extra: Dict[str, Any]) -> str:
    """Hiện phần extra của report: dict nguồn → dict số thành bảng; dict chữ → số thành biểu đồ; còn lại dạng JSON."""
    out, scalars, rest = "", [], {}
    for k, v in extra.items():
        if k in ("sources", "partial_run"):
            continue
        if isinstance(v, (int, float, str, bool)) or v is None:
            scalars.append((k, v))
        elif isinstance(v, dict) and v and set(v) <= set(SOURCES) and all(isinstance(x, dict) for x in v.values()) \
                and all(isinstance(y, (int, float)) for x in v.values() for y in x.values()):
            keys = sorted({kk for x in v.values() for kk in x})[:MATRIX_KEYS_MAX]
            head = "".join(f"<th class='n'>{html.escape(kk)}</th>" for kk in keys)
            body = "".join(f"<tr><td>{s}</td>" + "".join(f"<td class='n'>{V.vn(v[s].get(kk, 0))}</td>" for kk in keys) + "</tr>"
                           for s in SOURCES if s in v)
            out += f"<h3 style='margin-top:18px'><code>{html.escape(k)}</code></h3><div class='card scroll'><table><tr><th>Nguồn</th>{head}</tr>{body}</table></div>"
        elif isinstance(v, dict) and v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v.values()):
            rows = sorted(([str(a), b] for a, b in v.items()), key=lambda r: -r[1])[:25]
            out += f"<div style='margin-top:18px;max-width:640px'>{V.card(k, '', V.chart('h', rows, ''))}</div>"
        else:
            rest[k] = v
    if scalars:
        out = ("<div class='card scroll'><table>" + "".join(
            f"<tr><td><code>{html.escape(k)}</code></td><td class='n'>{V.vn(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else html.escape(str(v))}</td></tr>"
            for k, v in scalars) + "</table></div>") + out
    for k, v in rest.items():
        out += f"<details><summary><code>{html.escape(k)}</code> (JSON)</summary><pre>{html.escape(json.dumps(v, ensure_ascii=False, indent=1, default=str)[:20000])}</pre></details>"
    return out


def _dist_card(col: str, d: Dict[str, Any], total: int) -> str:
    miss = f"Trống {V.vn(d['missing'])} / {V.vn(total)} tin ({V.vn(100 * d['missing'] / total if total else 0.0)}%)."
    if d["kind"] == "num":
        q = d["quantiles"]
        note = (f"{miss} Min {V.vn(q[0])}, Q1 {V.vn(q[1])}, trung vị {V.vn(q[2])}, Q3 {V.vn(q[3])}, max {V.vn(q[4])} "
                f"{d['unit']}. Trục cắt ở phân vị 99, tin lớn hơn nằm ở cột cuối.")
        return V.card(col, note, V.chart("v", d["rows"]))
    if d["kind"] == "list":
        return V.card(col, f"{miss} Top 20 phần tử của list.", V.chart("h", d["rows"], "tin", total))
    extra = f" {V.vn(d['distinct'])} giá trị khác nhau." if "distinct" in d else ""
    return V.card(col, miss + extra, V.chart("h", d["rows"], "tin", total))


def render_step(step: str, rep: Dict[str, Any], rep_by_src: Dict[str, Dict[str, Any]], prof: Dict[str, Any] | None,
                prev: Dict[str, Any] | None, generated: str) -> str:
    i, o = rep["input"]["rows"], rep["output"]["rows"]
    dropped = sum(d.get("rows", 0) for d in rep.get("dropped", []))
    checks = rep.get("checks") or {}
    ok = checks.get("rows_conserved")
    body = (f"<h1>{step}</h1><p class='sub'>{html.escape(STEPS[step])}. Chạy lúc {html.escape(str(rep.get('generated_at', ''))[:16])} UTC, "
            f"code <code>{html.escape(str(rep.get('code_version', '')))}</code>.</p>")
    body += "<div class='tiles'>" + V.tile(i, "dòng vào") + V.tile(o, "dòng ra") + V.tile(dropped, "dòng bị bỏ") + \
        V.tile(len(rep.get("rules", [])), "luật") + V.tile("đạt" if ok else ("KHÔNG đạt" if ok is False else "–"), "bảo toàn số dòng") + "</div>"
    if prev:
        body += (f"<p class='note'>Lần trước (report trong git HEAD, {html.escape(str(prev.get('generated_at', ''))[:10])}): "
                 f"vào {V.vn(prev['input']['rows'])}, ra {V.vn(prev['output']['rows'])}.</p>")
    if checks.get("notes"):
        body += "<p class='warn'>" + "<br>".join(html.escape(str(n)) for n in checks["notes"]) + "</p>"

    prev_src = (prev or {}).get("extra", {}).get("sources") or {}
    body += "<h2>1. Số dòng theo nguồn</h2><p class='note'>Vào = đầu vào của bước; Ra = số dòng ghi ra; Bỏ = Vào − Ra.</p>"
    body += _src_table(rep_by_src, prev_src)
    if rep.get("dropped"):
        dr = [[f"{d['rule']}: {d['reason']}", d.get("rows", 0)] for d in rep["dropped"] if d.get("rows")]
        body += f"<div style='margin-top:16px;max-width:640px'>{V.card('Dòng bị bỏ theo luật', 'Chỉ luật có bỏ dòng', V.chart('h', dr, 'dòng', i))}</div>"

    body += ("<h2>2. Luật của bước</h2><p class='note'><b>drop</b>: bỏ dòng; <b>modify</b>: sửa giá trị; <b>flag</b>: chỉ gắn cờ. "
             "Số tin theo nguồn lấy từ <code>by_source</code> của report (– là report không tách theo nguồn). "
             "Chữ cam: khác lần chạy trước.</p>")
    body += _rules_table(rep, prev)

    body += "<h2>3. Độ phủ từng trường ở đầu ra</h2>"
    if prof:
        body += f"<p class='note'>{prof['note']} Ô càng đậm càng nhiều tin có giá trị. Cột \"Tất cả\": trước → sau bước nếu report có.</p>"
        body += _fill_table(prof, rep.get("fields"))
    else:
        body += "<div class='empty'>Chưa có file đầu ra trên máy.</div>"

    if prof and prof.get("key_cols"):
        body += "<h2>4. Phân bố trường chính</h2><div class='grid2'>"
        body += "".join(_dist_card(c, d, prof["rows"]) for c, d in prof["key_cols"].items())
        body += "</div>"
    if prof and prof.get("clean_meta"):
        keys = sorted({k for c in prof["clean_meta"].values() for k in c})
        head = "".join(f"<th class='n'>{html.escape(k)}</th>" for k in keys)
        rows = "".join(f"<tr><td>{s}</td>" + "".join(f"<td class='n'>{V.vn(prof['clean_meta'][s].get(k, 0))}</td>" for k in keys) + "</tr>"
                       for s in SOURCES if s in prof["clean_meta"])
        body += ("<h2>4. Nhãn IT của tin còn lại</h2><p class='note'>Từ <code>metadata.clean</code> của từng tin đầu ra "
                 "(luật 2 tầng C4a: tầng 1 theo chức danh, tầng 2 theo nội dung).</p>"
                 f"<div class='card scroll'><table><tr><th>Nguồn</th>{head}</tr>{rows}</table></div>")

    if rep.get("samples"):
        rows = "".join(
            f"<tr><td>{html.escape(str(s.get('source', '')))}</td><td>{html.escape(str(s.get('job_id', '')))}</td><td><code>{html.escape(str(s.get('field', '')))}</code></td>"
            f"<td class='samp'>{html.escape(_short(s.get('before'), 220))}</td><td class='samp'>{html.escape(_short(s.get('after'), 220))}</td></tr>"
            for s in rep["samples"])
        body += ("<h2>5. Mẫu trước → sau</h2><p class='note'>Mẫu do bước ghi vào report.</p>"
                 f"<div class='card scroll tbox'><table><tr><th>Nguồn</th><th>job_id</th><th>Trường</th><th>Trước</th><th>Sau</th></tr>{rows}</table></div>")

    if rep.get("extra"):
        body += "<h2>6. Số đo khác của bước</h2><p class='note'>Phần <code>extra</code> của report.</p>" + _extra_html(rep["extra"])

    if prof and prof.get("dtypes"):
        rows = "".join(f"<tr><td><code>{html.escape(c)}</code></td><td>{html.escape(t)}</td><td class='samp'>{html.escape(prof['samples'].get(c, ''))}</td></tr>"
                       for c, t in prof["dtypes"].items())
        body += ("<h2>7. Cột của bảng đầu ra</h2><p class='note'>Kiểu dữ liệu và một giá trị mẫu (giá trị có đầu tiên).</p>"
                 f"<div class='card scroll tbox'><table><tr><th>Cột</th><th>Kiểu</th><th>Mẫu</th></tr>{rows}</table></div>")
    return V.page(f"Bước {step}", _nav(step), body, FOOTER.format(g=generated))


def render_index(summary: List[Dict[str, Any]], generated: str, local_only_note: str) -> str:
    rows, funnel = "", []
    for s in summary:
        if s["fresh"]:
            if not funnel:
                funnel.append(["raw (đầu vào 01)", s["input"]])
            funnel.append([s["step"], s["output"]])
        status = "đã chạy lại" if s["fresh"] else "<span class='warn'>chưa chạy lại</span>"
        link = f"<a href='{s['step']}.html'>{s['step']}</a>" if s["fresh"] else s["step"]
        rows += (f"<tr><td>{link}</td><td>{html.escape(STEPS[s['step']])}</td><td>{status}</td>"
                 f"<td class='n'>{V.vn(s['input']) if s['fresh'] else '–'}</td><td class='n'>{V.vn(s['output']) if s['fresh'] else '–'}</td>"
                 f"<td class='n'>{V.vn(s['prev_output']) if s.get('prev_output') is not None else '–'}</td></tr>")
    body = ("<h1>Pre-processing · từng bước</h1><p class='sub'>Dữ liệu qua từng bước 01 → 04, đích là bảng Silver "
            "(spec 05 mục 4.4). Mỗi bước có một trang: số dòng, luật, độ phủ từng trường theo nguồn, mẫu trước/sau.</p>"
            f"<p class='note'>{local_only_note}</p>"
            "<div class='card scroll'><table><tr><th>Bước</th><th>Việc</th><th>Trạng thái</th><th class='n'>Vào</th>"
            f"<th class='n'>Ra</th><th class='n'>Ra (lần trước)</th></tr>{rows}</table></div>")
    if funnel:
        body += "<h2>Số dòng sau mỗi bước</h2><div class='card' style='max-width:640px'>" + V.chart("v", funnel, "dòng") + "</div>"
    return V.page("Pre-processing từng bước", _nav("index"), body, FOOTER.format(g=generated))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", choices=[*STEPS, "all"], default="all")
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "presentation" / "preprocessing_steps"))
    a = ap.parse_args()
    out, data_dir = Path(a.out), Path(a.data_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    rep_dir = ROOT / "reports" / "preprocessing"

    summary, profiles = [], {}
    for step in STEPS:
        rep = _load(rep_dir / step / "_all.json")
        prev = _prev_report(step)
        fresh = rep is not None and (data_dir / "preprocessing" / step).exists()
        summary.append({"step": step, "fresh": fresh, "input": rep["input"]["rows"] if rep else None,
                        "output": rep["output"]["rows"] if rep else None,
                        "prev_output": prev["output"]["rows"] if prev else None})
        if not fresh or (a.step != "all" and a.step != step):
            continue
        rep_by_src = {s: r for s in SOURCES if (r := _load(rep_dir / step / f"{s}.json"))}
        prof = profile_output(step, data_dir)
        profiles[step] = prof
        (out / f"{step}.html").write_text(render_step(step, rep, rep_by_src, prof, prev, generated), encoding="utf-8")
        print(f"{step}: vào {rep['input']['rows']:,} → ra {rep['output']['rows']:,}; đo đầu ra: {prof['rows'] if prof else 'không có'} dòng")

    local_dir = data_dir / "_local_only"
    n_local = sum(1 for p in local_dir.rglob("*.json")) if local_dir.exists() else 0
    note = ("Chạy trên đúng tập raw đang có trên R2." + (
        f" {V.vn(n_local)} file raw chỉ có trên máy (cào 17/11, chưa đẩy R2) được để riêng ở "
        "<code>data/_local_only/</code> và không đi vào các bước này; trang raw_bronze vẫn tính chúng." if n_local else ""))
    (out / "index.html").write_text(render_index(summary, generated, note), encoding="utf-8")
    if not (out / "silver_gap.html").exists():
        msg = "<h1>Đối chiếu Silver</h1><div class='empty'>Chưa có: trang này sinh sau khi chạy lại bước 04.</div>"
        (out / "silver_gap.html").write_text(V.page("Đối chiếu Silver", _nav("silver_gap"), msg, FOOTER.format(g=generated)), encoding="utf-8")
    (out / "profiles.json").write_text(json.dumps({"summary": summary, "profiles": profiles}, ensure_ascii=False, indent=1, default=str),
                                       encoding="utf-8")
    print(f"Đã ghi {out}")


if __name__ == "__main__":
    main()
