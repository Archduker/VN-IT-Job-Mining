# -*- coding: utf-8 -*-
"""Bước 03 Transformation (docs/spec/preprocessing/03_transformation.md).

Ép kiểu, bóc tách lương cascade, ngày và tháng đăng (T3b), kinh nghiệm, headcount; làm sạch chữ (T6, T6.5);
nhận ngôn ngữ bằng fastText lid.176; dịch EN→VI bằng envit5 khi có --translate (T6b, giữ cột gốc);
rút kỹ năng (chỉ từ bản gốc) và phúc lợi; tách địa điểm 3 cấp theo 34 tỉnh; rút hình thức làm việc,
loại hợp đồng, kinh nghiệm từ ô của sàn và JD (T9, chỉ ghi giá trị và cờ, bước 04 chọn).
Đọc và ghi một file all.parquet. Không bỏ dòng.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common.step_report import StepReport, merge_reports
from preprocessing.missing_outlier.sneaky_null_detector import is_val_null
from preprocessing.common import text_clean as tc
from preprocessing.transformation.date_parser import process_dates
from preprocessing.transformation.experience_parser import parse_experience
from preprocessing.transformation.headcount_parser import parse_headcount
from preprocessing.transformation import jd_extractor
from preprocessing.transformation.location_parser import parse_locations
from preprocessing.transformation.salary_parser import parse_salary_cascade
from preprocessing.transformation.skill_extractor import extract_benefits, extract_skills
from preprocessing.common.lang_id import CONF_MIN, detect_lang, model_sha256
from preprocessing.transformation.text_metrics import detect_jd_language
from preprocessing.translation.core import TranslationContext

STEP = "03_transformation"
DATA_DIR = REPO_ROOT / "data"
IN_FILE = DATA_DIR / "preprocessing" / "02_integration" / "all.parquet"
OUT_FILE = DATA_DIR / "preprocessing" / STEP / "all.parquet"

KEY_FIELDS = (
    "salary_min_vnd", "salary_max_vnd", "posted_date", "deadline_date",
    "exp_min_years", "exp_max_years", "headcount", "job_title_clean",
    "description_clean", "skills_clean", "benefits_std",
    "locations", "language", "posted_month", "benefits_clean", "work_mode_raw", "work_mode_jd",
    "employment_type_raw", "employment_type_jd", "exp_min_years_jd"
)
_VN_TZ = timezone(timedelta(hours=7))


def posted_month(posted_date: Any, first_crawled_at: Any) -> Optional[str]:
    """T3b (PRE-37): YYYY-MM của ngày đăng; không có thì của lần cào đầu đổi sang giờ Việt Nam (UTC+7)."""
    if isinstance(posted_date, str) and len(posted_date) >= 7:
        return posted_date[:7]
    if not isinstance(first_crawled_at, str) or not first_crawled_at:
        return None
    try:
        ts = datetime.fromisoformat(first_crawled_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:  # không có múi giờ thì coi là UTC, như scraped_at của crawler
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(_VN_TZ).strftime("%Y-%m")


def clean_benefits(items: Any) -> Optional[List[str]]:
    """T6.5: làm sạch từng item phúc lợi như T6 (NFC, ký tự ẩn, khoảng trắng), bỏ item rỗng."""
    if items is None or isinstance(items, (str, bytes)) or not hasattr(items, "__iter__"):
        return None
    out = []
    for it in items:
        s = tc.clean_text(it) if isinstance(it, str) else None
        s = " ".join(tc._HIDDEN.sub("", s).split()) if s else ""
        if s:
            out.append(s)
    return out or None


def skill_source_text(rec: Dict[str, Any]) -> str:
    """T7: văn bản để rút kỹ năng, chỉ bản gốc (preprocessing/CLAUDE.md); không đọc cột *_vi."""
    return f"{rec.get('description_clean') or ''} {rec.get('requirements_clean') or ''}".strip()


def _t9_tally(t9: Dict[str, Any], rec: Dict[str, Any], st: Dict[str, Counter],
              ex: Dict[str, List[Dict[str, Any]]], job_id: Any, url: Any) -> None:
    """Đếm cho report: số tin có giá trị JD, phân bố, ca lệch; tối đa 3 ví dụ mỗi luật (ưu tiên ca lệch)."""
    st["wm_raw"][str(t9["work_mode_raw"])] += 1
    st["wm_jd"][str(t9["work_mode_jd"])] += 1
    st["et_raw"][str(t9["employment_type_raw"])] += 1
    st["et_jd"][str(t9["employment_type_jd"])] += 1
    st["exp_kind"][str(t9["exp_jd_kind"])] += 1
    for pid in t9["work_mode_jd_rules"]:
        st["wm_rules"][pid] += 1
    if t9["work_mode_conflict"] and t9["work_mode_jd_strong"]:
        st["conflict"]["T9a_strong"] += 1
    for key, has, conflict, before, after in (
        ("T9a", t9["work_mode_jd"], t9["work_mode_conflict"], rec.get("raw_work_mode"),
         f"raw={t9['work_mode_raw']} jd={t9['work_mode_jd']} strong={t9['work_mode_jd_strong']}"),
        ("T9b", t9["employment_type_jd"], t9["employment_type_conflict"], rec.get("raw_employment_type"),
         f"raw={t9['employment_type_raw']} jd={t9['employment_type_jd']}"),
        ("T9c", t9["exp_jd_kind"], False, rec.get("raw_experience_text"),
         f"{t9['exp_min_years_jd']} - {t9['exp_max_years_jd']} «{t9['exp_jd_text']}»"),
    ):
        if has:
            st[key]["jd"] += 1
        if conflict:
            st["conflict"][key] += 1
        if has and len(ex[key]) < 3 and (conflict or key == "T9c"):
            ex[key].append({"job_id": job_id, "field": key, "before": str(before), "after": after, "url": url})


def _is_filled(val: Any) -> bool:
    """Kiểm tra an toàn giá trị có dữ liệu hay không."""
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (list, tuple, dict, set)):
        return len(val) > 0
    if hasattr(val, "__len__"):
        return len(val) > 0
    return True


_INFO_KEYS = ("html", "nfc", "hidden", "dash_bullet", "residual_html", "residual_nfd", "residual_hidden")


def _clean_text_field(raw_text: Optional[str]) -> Optional[str]:
    """T6: làm sạch ký tự (HTML, NFC, ký tự ẩn, gạch ngang, bullet, nối bullet)."""
    return tc.clean_text(raw_text)


def _clean_job_title(title: Optional[str]) -> Optional[str]:
    return tc.clean_text(title)


def process_source(
    source: str,
    input_records: List[Dict[str, Any]],
    dry_run: bool = True,
    translation: Optional[TranslationContext] = None,
) -> tuple[List[Dict[str, Any]], StepReport]:
    report = StepReport(STEP, source, dry_run)
    total_rows = len(input_records)
    report.set_io(IN_FILE, total_rows, OUT_FILE, total_rows)

    transformed_rows: List[Dict[str, Any]] = []

    # Thống kê luật
    t1_count, t2_count, t3_count, t4_count, t5_count, t6_count, t7_count, t8_count = 0, 0, 0, 0, 0, 0, 0, 0
    t2_salary_under_1m = 0
    t6b_count = 0
    t2_suspect = 0
    t2_from_x_count = 0
    t2_sources_count = {"header": 0, "title": 0, "jd": 0, "none": 0}

    abbrev = tc.load_abbreviations()
    tq = {k: 0 for k in _INFO_KEYS}
    t2_examples = []
    t3b_src: Counter = Counter()
    t65_count = 0
    t9_stats: Dict[str, Counter] = {k: Counter() for k in (
        "T9a", "T9b", "T9c", "wm_rules", "wm_raw", "wm_jd", "et_raw", "et_jd", "exp_kind", "conflict")}
    t9_examples: Dict[str, List[Dict[str, Any]]] = {"T9a": [], "T9b": [], "T9c": []}
    t4_examples = []
    t7_examples = []
    t8_examples = []

    for row in input_records:
        rec = dict(row)
        flags: List[str] = []
        job_id = rec.get("source_job_id") or rec.get("job_id_global") or ""
        url = rec.get("source_url") or ""

        # T1: Null trá hình -> None
        for k in list(rec.keys()):
            if k.startswith("raw_") and is_val_null(rec[k]):
                rec[k] = None
                t1_count += 1

        # T6: Làm sạch văn bản (HTML + Bullet)
        row_info = {k: False for k in _INFO_KEYS}
        cols = {}
        for name, src_col in (("description", "raw_description_text"), ("requirements", "raw_requirements_text"),
                              ("job_title", "job_title")):
            clean, info = tc.clean_text_checked(rec.get(src_col))
            for k in _INFO_KEYS:
                row_info[k] = row_info[k] or bool(info.get(k))
            _, norm, fold_ = tc._columns(clean, abbrev)
            cols[name] = (clean, norm, fold_)
        desc_clean, req_clean, title_clean = cols["description"][0], cols["requirements"][0], cols["job_title"][0]
        rec["description_clean"], rec["description_norm"], rec["description_fold"] = cols["description"]
        rec["requirements_clean"], rec["requirements_norm"], rec["requirements_fold"] = cols["requirements"]
        rec["job_title_clean"], rec["job_title_norm"], rec["job_title_fold"] = cols["job_title"]
        t6_count += 1
        for k in _INFO_KEYS:
            tq[k] += row_info[k]

        # Đo ngôn ngữ
        combined_text = f"{desc_clean or ''} {req_clean or ''}".strip()
        # PH3 S4: fastText lid.176 quyết định; luật đếm dấu cũ giữ lại để so bất đồng
        rec["language_rule"] = detect_jd_language(combined_text, title_clean, rec.get("company_name"))
        rec["language"], rec["language_conf"] = detect_lang(desc_clean)
        lang = rec["language"]  # PH5 T6b đọc biến này

        # T6b: dịch description/requirements tiếng Anh (PH5); giữ cột gốc, bước sau dùng thêm bản dịch
        tr = (translation or TranslationContext()).translate_fields(desc_clean, req_clean, lang)
        rec.update(tr)
        for name in ("description", "requirements"):
            _, rec[f"{name}_vi_norm"], rec[f"{name}_vi_fold"] = tc._columns(tr[f"{name}_vi"], abbrev)
        if tr["translation_status"] in ("translated", "failed"):
            t6b_count += 1

        # T2: Parse lương Cascade 3 tầng
        raw_sal = rec.get("raw_salary_text")
        sal_res = parse_salary_cascade(raw_sal, title=title_clean, jd_text=desc_clean)
        rec["salary_min_vnd"] = sal_res.get("salary_min_vnd")
        rec["salary_max_vnd"] = sal_res.get("salary_max_vnd")
        rec["salary_currency_raw"] = sal_res.get("salary_currency_original", "VND")
        rec["salary_period_raw"] = sal_res.get("pay_period", "month")
        rec["is_negotiable"] = sal_res.get("is_negotiable", False)
        sal_src = sal_res.get("salary_source", "none")
        sal_src = "jd" if sal_src.startswith("jd") else sal_src
        rec["salary_source"] = sal_src
        t2_sources_count[sal_src] = t2_sources_count.get(sal_src, 0) + 1

        rec["salary_suspect"] = bool(sal_res.get("salary_suspect"))
        if rec["salary_suspect"]:
            flags.append("salary_suspect")
            t2_suspect += 1
        if sal_res.get("salary_under_1m"):
            flags.append("salary_under_1m")
            t2_salary_under_1m += 1

        if raw_sal and "từ" in raw_sal.lower() and rec["salary_max_vnd"] is None and rec["salary_min_vnd"] is not None:
            t2_from_x_count += 1

        if rec["salary_min_vnd"] is not None or rec["salary_max_vnd"] is not None:
            t2_count += 1
            if len(t2_examples) < 3:
                t2_examples.append({
                    "job_id": job_id,
                    "field": "salary_min_max",
                    "before": str(raw_sal),
                    "after": f"{rec['salary_min_vnd']} - {rec['salary_max_vnd']} VND ({sal_src})",
                    "url": url,
                })

        # T3: Parse ngày & kiểm tra deadline trước crawl
        posted_d, deadline_d, is_exp_before_crawl = process_dates(
            rec.get("raw_posted_date"), rec.get("raw_deadline"), rec.get("crawled_at")
        )
        rec["posted_date"] = posted_d
        rec["deadline_date"] = deadline_d
        if is_exp_before_crawl:
            flags.append("deadline_before_crawl")
        if posted_d or deadline_d:
            t3_count += 1
        # T3b: tháng đăng (bảng sạch dùng cột này thay posted_date, spec 05 mục 4.2)
        rec["posted_month"] = posted_month(posted_d, rec.get("first_crawled_at"))
        t3b_src["posted_date" if posted_d else ("first_crawled_at" if rec["posted_month"] else "none")] += 1

        # T4: Parse kinh nghiệm
        exp_min, exp_max = parse_experience(rec.get("raw_experience_text"))
        rec["exp_min_years"] = exp_min
        rec["exp_max_years"] = exp_max
        if exp_min is not None or exp_max is not None:
            t4_count += 1
            if len(t4_examples) < 3:
                t4_examples.append({
                    "job_id": job_id,
                    "field": "exp_min_max",
                    "before": str(rec.get("raw_experience_text")),
                    "after": f"{exp_min} - {exp_max} years",
                    "url": url,
                })

        # T5: Parse headcount
        rec["headcount"] = parse_headcount(rec.get("raw_headcount"))
        if rec["headcount"] is not None:
            t5_count += 1

        # T6.5: làm sạch từng item phúc lợi
        raw_benefits = rec.get("benefits_list")
        rec["benefits_clean"] = clean_benefits(raw_benefits)
        if raw_benefits is not None and not isinstance(raw_benefits, str) \
                and list(rec["benefits_clean"] or []) != [x for x in raw_benefits]:
            t65_count += 1

        # T7: Kỹ năng (chỉ bản gốc) & Phúc lợi
        skills_clean = extract_skills(rec.get("skills_list"), skill_source_text(rec), rec.get("company_name"))
        rec["skills_clean"] = skills_clean
        benefits_std = extract_benefits(rec["benefits_clean"], desc_clean or "")
        rec["benefits_std"] = benefits_std
        if skills_clean or benefits_std:
            t7_count += 1
            if len(t7_examples) < 3:
                t7_examples.append({
                    "job_id": job_id,
                    "field": "skills_clean",
                    "before": str(rec.get("skills_list")),
                    "after": str(skills_clean[:5]),
                    "url": url,
                })

        # T8: Địa điểm 3 cấp
        locs = parse_locations(
            rec.get("working_locations"), rec.get("raw_location_text"), rec.get("company_address")
        )
        rec["locations"] = locs
        if locs:
            t8_count += 1
            if len(t8_examples) < 3:
                t8_examples.append({
                    "job_id": job_id,
                    "field": "locations",
                    "before": str(rec.get("raw_location_text")),
                    "after": str(locs[0]),
                    "url": url,
                })

        # T9: hình thức làm việc, loại hợp đồng, kinh nghiệm từ ô của sàn và JD (chỉ ghi, bước 04 chọn)
        t9 = jd_extractor.extract(rec)
        rec.update(t9)
        _t9_tally(t9, rec, t9_stats, t9_examples, job_id, url)

        rec["flags"] = flags
        transformed_rows.append(rec)

    # Đăng ký các rules
    report.rule("T1", "Null trá hình thành null", "modify", t1_count)
    report.rule("T2", "Bóc tách dải số lương Cascade", "modify", t2_count, t2_examples)
    report.rule("T3", "Bóc tách ngày chuẩn ISO/dd/mm/yyyy", "modify", t3_count)
    report.rule("T4", "Bóc tách số năm kinh nghiệm", "modify", t4_count, t4_examples)
    report.rule("T3b", "Tháng đăng posted_month: ngày đăng, không có thì lần cào đầu (giờ Việt Nam)", "modify",
                t3b_src["posted_date"] + t3b_src["first_crawled_at"])
    report.rule("T5", "Bóc tách chỉ tiêu headcount", "modify", t5_count)
    report.rule("T2f", "Lương tháng ngoài 1–500 triệu: bỏ số, gắn cờ salary_suspect", "flag", t2_suspect)
    report.rule("T6", "Làm sạch text HTML/bullet và phát hiện ngôn ngữ", "modify", t6_count)
    report.rule("T6.1", "Bóc thẻ HTML và entity", "modify", tq["html"])
    report.rule("T6.2", "Chuẩn hóa Unicode về NFC", "modify", tq["nfc"])
    report.rule("T6.3", "Bỏ ký tự ẩn", "modify", tq["hidden"])
    report.rule("T6.4", "Gạch ngang và bullet về một chuẩn", "modify", tq["dash_bullet"])
    for key, label in (("residual_html", "HTML"), ("residual_nfd", "NFD")):
        if tq[key]:
            report.note(f"CẢNH BÁO: {tq[key]} tin còn {label} sau {tc.MAX_RETRIES} lượt làm sạch (không dừng pipeline)")
    report.rule("T6b", "Dịch description/requirements tiếng Anh sang tiếng Việt (envit5)", "modify", t6b_count)
    report.rule("T6.5", "Làm sạch từng item phúc lợi (NFC, ký tự ẩn, khoảng trắng, bỏ item rỗng)", "modify", t65_count)
    report.rule("T7", "Rút kỹ năng (chỉ bản gốc) và phúc lợi song ngữ", "modify", t7_count, t7_examples)
    report.rule("T8", "Bóc tách địa điểm 3 cấp", "modify", t8_count, t8_examples)
    report.rule("T9a", "Hình thức làm việc từ JD (jd_extraction.json), cờ lệch với ô của sàn", "flag",
                t9_stats["T9a"]["jd"], t9_examples["T9a"])
    report.rule("T9b", "Loại hợp đồng từ JD, cờ lệch với ô của sàn", "flag", t9_stats["T9b"]["jd"], t9_examples["T9b"])
    report.rule("T9c", "Kinh nghiệm từ JD (cụm số năm hoặc cụm không yêu cầu kinh nghiệm)", "flag",
                t9_stats["T9c"]["jd"], t9_examples["T9c"])

    # Đo độ phủ trường
    fields_stats = []
    for f in KEY_FIELDS:
        filled_cnt = sum(1 for r in transformed_rows if _is_filled(r.get(f)))
        pct = round((filled_cnt / total_rows) * 100.0, 1) if total_rows > 0 else 0.0
        fields_stats.append({"field": f, "fill_pct_in": pct, "fill_pct_out": pct})
    report.data["fields"] = fields_stats

    # Extra stats
    pct = lambda n: round(n / total_rows * 100.0, 2) if total_rows else 0.0
    report.data["extra"] = {
        "salary_source_distribution": t2_sources_count,
        "salary_under_1m_count": t2_salary_under_1m,
        "salary_from_x_count": t2_from_x_count,
        "language_distribution": {k: sum(1 for r in transformed_rows if r.get("language") == k) for k in ("vi", "en", "other")},
        "language_fasttext": _lang_extra(transformed_rows),
        "text_quality": {
            "before": {k: tq[k] for k in ("html", "nfc", "hidden")},
            "residual_html_pct": pct(tq["residual_html"]),
            "residual_nfd_pct": pct(tq["residual_nfd"]),
            "residual_hidden_char_pct": pct(tq["residual_hidden"]),
            "residual_rows": {k: tq[k] for k in ("residual_html", "residual_nfd", "residual_hidden")},
            "abbreviations_approved": len(abbrev),
        },
        "translation": translation.manifest() if translation else None,
        "experience_parsed_rate": round((t4_count / total_rows) * 100.0, 1) if total_rows > 0 else 0.0,
        "posted_month_source": dict(t3b_src),
        "posted_month_distribution": dict(Counter(str(r.get("posted_month")) for r in transformed_rows)),
        "jd_extraction": {
            "dictionary": str(jd_extractor.DICT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "work_mode_raw": dict(t9_stats["wm_raw"]), "work_mode_jd": dict(t9_stats["wm_jd"]),
            "work_mode_jd_rules": dict(t9_stats["wm_rules"]),
            "employment_type_raw": dict(t9_stats["et_raw"]), "employment_type_jd": dict(t9_stats["et_jd"]),
            "exp_jd_kind": dict(t9_stats["exp_kind"]),
            "conflicts": dict(t9_stats["conflict"]),
        },
    }

    report.check_conserved()
    return transformed_rows, report


def _lang_extra(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    dis = [r for r in rows if r.get("language") != r.get("language_rule")]
    conf = [r["language_conf"] for r in rows if r.get("language_conf") is not None]
    return {"model": "lid.176.bin", "sha256": model_sha256() if rows else None, "conf_min": CONF_MIN,
            "disagree_with_old_rule": len(dis),
            "disagree_examples": [str(r.get("source_job_id")) for r in dis[:10]],
            "conf_lt_0_9": sum(c < 0.9 for c in conf)}


def run(
    sources: Sequence[str] = SOURCES,
    dry_run: bool = True,
    translate: bool = False,
) -> Dict[str, StepReport]:
    df_in = pd.read_parquet(IN_FILE) if IN_FILE.exists() else pd.DataFrame(columns=["source_platform"])
    groups = {src: g.to_dict(orient="records") for src, g in df_in.groupby("source_platform")}

    ctx = None
    if translate and not dry_run:  # chạy model thật chỉ khi có cờ rõ ràng (PH5)
        from preprocessing.translation.translator import make_context
        ctx = make_context(4, DATA_DIR / "preprocessing" / "translation" / "translations_cache.jsonl")
    reports: Dict[str, StepReport] = {}
    all_rows: List[Dict[str, Any]] = []
    for src in sources:
        rows, rep = process_source(src, groups.get(src, []), dry_run=dry_run, translation=ctx)
        reports[src] = rep
        all_rows.extend(rows)

    for rep in reports.values():
        rep.check_conserved()
        rep.write()

    total_rep = merge_reports(STEP, list(reports.values()), dry_run)
    total_rep.set_io(IN_FILE, int(df_in['source_platform'].isin(list(sources)).sum()), OUT_FILE, len(all_rows))
    total_rep.data["extra"]["language_distribution"] = {k: sum(1 for r in all_rows if r.get("language") == k) for k in ("vi", "en", "other")}
    tqs = [r.data["extra"]["text_quality"] for r in reports.values()]
    n_all = len(all_rows)
    res = {k: sum(t["residual_rows"][k] for t in tqs) for k in ("residual_html", "residual_nfd", "residual_hidden")}
    total_rep.data["extra"]["text_quality"] = {
        "before": {k: sum(t["before"][k] for t in tqs) for k in ("html", "nfc", "hidden")},
        "residual_rows": res,
        **{f"{k}_pct": round(res[k] / n_all * 100.0, 2) if n_all else 0.0
           for k in ("residual_html", "residual_nfd")},
        "residual_hidden_char_pct": round(res["residual_hidden"] / n_all * 100.0, 2) if n_all else 0.0,
    }
    total_rep.check_conserved()
    if not dry_run and all_rows:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(all_rows).to_parquet(OUT_FILE, engine="pyarrow", index=False)
    total_rep.write()
    return reports
