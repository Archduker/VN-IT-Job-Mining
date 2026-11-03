# -*- coding: utf-8 -*-
"""Bước 03 Transformation (docs/preprocessing/spec/P3_transformation.md).

Ép kiểu dữ liệu, bóc tách lương cascade, ngày, kinh nghiệm, headcount,
làm sạch text, rút kỹ năng/phúc lợi, dịch JD tiếng Anh sang tiếng Việt (chỉ khi đã chọn model
trong translate_model.json), tách địa điểm 3 cấp theo 34 tỉnh. Đọc và ghi một file all.parquet.
"""

from __future__ import annotations

import csv
import json
import random
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from preprocessing.common import REPO_ROOT, SOURCES
from preprocessing.common.step_report import StepReport, merge_reports
from preprocessing.missing_outlier.sneaky_null_detector import is_val_null
from preprocessing.transformation.bullet_stitcher import stitch_fragmented_bullets
from preprocessing.transformation.date_parser import process_dates
from preprocessing.transformation.experience_parser import parse_experience
from preprocessing.transformation.headcount_parser import parse_headcount
from preprocessing.transformation.html_cleaner import strip_html_tags
from preprocessing.transformation.location_parser import parse_locations
from preprocessing.transformation.salary_parser import parse_salary_cascade
from preprocessing.transformation.skill_extractor import extract_benefits, extract_skills
from preprocessing.transformation.text_metrics import detect_jd_language
from preprocessing.transformation.translator import DEFAULT_MODEL, GeminiTranslator

STEP = "03_transformation"
DATA_DIR = REPO_ROOT / "data"
IN_FILE = DATA_DIR / "preprocessing" / "02_integration" / "all.parquet"
OUT_FILE = DATA_DIR / "preprocessing" / STEP / "all.parquet"
REVIEW_DIR = DATA_DIR / "preprocessing" / "review"
# Model dịch do người dùng chọn sau khi chấm translate_30.csv; chưa có file thì chỉ dịch 30 JD mẫu
MODEL_CHOICE_PATH = REPO_ROOT / "preprocessing" / "transformation" / "translate_model.json"

KEY_FIELDS = (
    "salary_min_vnd", "salary_max_vnd", "posted_date", "deadline_date",
    "exp_min_years", "exp_max_years", "headcount", "job_title_clean",
    "description_clean", "skills_clean", "benefits_std", "description_vi",
    "locations", "language"
)


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


def _clean_text_field(raw_text: Optional[str]) -> Optional[str]:
    """T6: Bỏ HTML và nối bullet cho văn bản mô tả."""
    if not raw_text or not str(raw_text).strip():
        return None
    stripped = strip_html_tags(raw_text)
    if not stripped:
        return None
    stitched_lines = stitch_fragmented_bullets(stripped)
    return "\n".join(stitched_lines) if stitched_lines else stripped


def _clean_job_title(title: Optional[str]) -> Optional[str]:
    """Làm sạch tiêu đề tuyển dụng."""
    if not title or not str(title).strip():
        return None
    s = str(title).strip()
    return s


def process_source(
    source: str,
    input_records: List[Dict[str, Any]],
    translator: Optional[GeminiTranslator],
    dry_run: bool = True
) -> tuple[List[Dict[str, Any]], StepReport, List[Dict[str, Any]]]:
    report = StepReport(STEP, source, dry_run)
    total_rows = len(input_records)
    report.set_io(IN_FILE, total_rows, OUT_FILE, total_rows)

    transformed_rows: List[Dict[str, Any]] = []
    en_sample_candidates: List[Dict[str, Any]] = []

    # Thống kê luật
    t1_count, t2_count, t3_count, t4_count, t5_count, t6_count, t7_count, t8_count = 0, 0, 0, 0, 0, 0, 0, 0
    t2_salary_under_1m = 0
    t2_suspect = 0
    t6b_count = t6b_lost = 0
    t2_from_x_count = 0
    t2_sources_count = {"header": 0, "title": 0, "jd": 0, "none": 0}

    t2_examples = []
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
        desc_clean = _clean_text_field(rec.get("raw_description_text"))
        req_clean = _clean_text_field(rec.get("raw_requirements_text"))
        title_clean = _clean_job_title(rec.get("job_title"))
        rec["description_clean"] = desc_clean
        rec["requirements_clean"] = req_clean
        rec["job_title_clean"] = title_clean
        t6_count += 1

        # Đo ngôn ngữ
        combined_text = f"{desc_clean or ''} {req_clean or ''}".strip()
        lang = detect_jd_language(combined_text, title_clean, rec.get("company_name"))
        rec["language"] = lang

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

        # T7: Kỹ năng & Phúc lợi
        skills_clean = extract_skills(rec.get("skills_list"), combined_text, rec.get("company_name"))
        rec["skills_clean"] = skills_clean
        benefits_std = extract_benefits(rec.get("benefits_list"), desc_clean or "")
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

        # T6b: chỉ dịch JD tiếng Anh; JD tiếng Việt giữ nguyên
        rec["description_vi"], rec["requirements_vi"], rec["translated_by"] = desc_clean, req_clean, None
        if lang == "en" and desc_clean:
            en_sample_candidates.append({"job_id": job_id, "source": source, "title": title_clean, "jd": desc_clean})
            rec["description_vi"] = rec["requirements_vi"] = None
            if translator is not None:
                desc_vi, lost_desc = translator.translate_text(desc_clean)
                req_vi, lost_req = translator.translate_text(req_clean)
                rec["description_vi"], rec["requirements_vi"] = desc_vi, req_vi
                rec["translated_by"] = translator.model if desc_vi else None
                if desc_vi:
                    t6b_count += 1
                if lost_desc or lost_req:
                    flags.append("translate_lost_term")
                    t6b_lost += 1

        rec["flags"] = flags
        transformed_rows.append(rec)

    # Đăng ký các rules
    report.rule("T1", "Null trá hình thành null", "modify", t1_count)
    report.rule("T2", "Bóc tách dải số lương Cascade", "modify", t2_count, t2_examples)
    report.rule("T3", "Bóc tách ngày chuẩn ISO/dd/mm/yyyy", "modify", t3_count)
    report.rule("T4", "Bóc tách số năm kinh nghiệm", "modify", t4_count, t4_examples)
    report.rule("T5", "Bóc tách chỉ tiêu headcount", "modify", t5_count)
    report.rule("T2f", "Lương tháng ngoài 1–500 triệu: bỏ số, gắn cờ salary_suspect", "flag", t2_suspect)
    report.rule("T6", "Làm sạch text HTML/bullet và phát hiện ngôn ngữ", "modify", t6_count)
    report.rule("T6b", "Dịch JD tiếng Anh sang tiếng Việt", "modify", t6b_count)
    report.rule("T6c", "Bản dịch thiếu thuật ngữ cần giữ: gắn cờ translate_lost_term", "flag", t6b_lost)
    report.rule("T7", "Rút kỹ năng và phúc lợi song ngữ", "modify", t7_count, t7_examples)
    report.rule("T8", "Bóc tách địa điểm 3 cấp", "modify", t8_count, t8_examples)

    # Đo độ phủ trường
    fields_stats = []
    for f in KEY_FIELDS:
        filled_cnt = sum(1 for r in transformed_rows if _is_filled(r.get(f)))
        pct = round((filled_cnt / total_rows) * 100.0, 1) if total_rows > 0 else 0.0
        fields_stats.append({"field": f, "fill_pct_in": pct, "fill_pct_out": pct})
    report.data["fields"] = fields_stats

    # Extra stats
    report.data["extra"] = {
        "salary_source_distribution": t2_sources_count,
        "salary_under_1m_count": t2_salary_under_1m,
        "salary_from_x_count": t2_from_x_count,
        "language_distribution": {k: sum(1 for r in transformed_rows if r.get("language") == k) for k in ("vi", "en")},
        "experience_parsed_rate": round((t4_count / total_rows) * 100.0, 1) if total_rows > 0 else 0.0,
    }

    report.check_conserved()
    return transformed_rows, report, en_sample_candidates


def export_review_30_jd(candidates: List[Dict[str, Any]], use_api: bool, dry_run: bool) -> Dict[str, Any]:
    """30 JD tiếng Anh rải đều theo nguồn, dịch bằng model mặc định để người dùng chấm điểm.

    Chỉ ghi file khi đủ bản dịch thật; file đã có điểm chấm thì không đụng tới.
    """
    out_csv = REVIEW_DIR / "translate_30.csv"
    if out_csv.exists():
        with out_csv.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if any((r.get("diem_1_den_5") or r.get("diem_a") or r.get("diem_b") or "").strip() for r in rows):
            return {"status": "đã có điểm chấm, giữ nguyên"}

    by_src: Dict[str, List[Dict[str, Any]]] = {}
    for c in sorted(candidates, key=lambda c: str(c["job_id"])):
        by_src.setdefault(c["source"], []).append(c)
    rng = random.Random(42)
    for lst in by_src.values():
        rng.shuffle(lst)
    sampled: List[Dict[str, Any]] = []
    while len(sampled) < 30 and any(by_src.values()):  # lấy vòng tròn qua các nguồn
        for src in sorted(by_src):
            if by_src[src] and len(sampled) < 30:
                sampled.append(by_src[src].pop())

    models = (DEFAULT_MODEL,)  # người dùng chọn tiết kiệm (03/11/2026): chỉ chấm 3.8 Flash, không thi Argon
    trs = [GeminiTranslator(use_api=use_api, dry_run=dry_run, model=m, max_budget_usd=0.05) for m in models]
    out = [[t.translate_text(item["jd"][:1500])[0] for t in trs] for item in sampled]
    stats = {m: t.stats() for m, t in zip(models, trs)}
    if dry_run or not all(all(o) for o in out):
        return {"status": "chưa ghi file: chưa có đủ bản dịch thật", "sampled": len(sampled), "api": stats}

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["job_id", "source", "title", "ban_goc", "ban_dich", "diem_1_den_5", "ghi_chu"])
        for item, (a,) in zip(sampled, out):
            w.writerow([item["job_id"], item["source"], item["title"], item["jd"][:1500], a, "", ""])
    return {"status": "đã ghi file", "sampled": len(sampled), "model": models[0], "api": stats}


def run(
    sources: Sequence[str] = SOURCES,
    dry_run: bool = True,
    use_api: bool = False
) -> Dict[str, StepReport]:
    chosen = json.loads(MODEL_CHOICE_PATH.read_text(encoding="utf-8")).get("model") if MODEL_CHOICE_PATH.exists() else None
    # dry-run --use-api vẫn ước tính tiền dịch toàn bộ bằng model mặc định, kể cả khi chưa chọn model
    model = chosen or (DEFAULT_MODEL if dry_run and use_api else None)
    translator = GeminiTranslator(use_api=use_api, dry_run=dry_run, model=model) if model else None
    df_in = pd.read_parquet(IN_FILE) if IN_FILE.exists() else pd.DataFrame(columns=["source_platform"])
    groups = {src: g.to_dict(orient="records") for src, g in df_in.groupby("source_platform")}

    reports: Dict[str, StepReport] = {}
    all_rows: List[Dict[str, Any]] = []
    all_en: List[Dict[str, Any]] = []
    for src in sources:
        rows, rep, en_cand = process_source(src, groups.get(src, []), translator, dry_run=dry_run)
        reports[src] = rep
        all_rows.extend(rows)
        all_en.extend(en_cand)

    review = export_review_30_jd(all_en, use_api, dry_run) if all_en else {"status": "không có JD tiếng Anh"}
    api = translator.stats() if translator else {"used": False, "reason": "chưa chọn model: chấm data/preprocessing/review/translate_30.csv rồi ghi preprocessing/transformation/translate_model.json"}
    for rep in reports.values():
        rep.data["api"] = api
        rep.check_conserved()
        rep.write()

    total_rep = merge_reports(STEP, list(reports.values()), dry_run)
    total_rep.set_io(IN_FILE, len(df_in), OUT_FILE, len(all_rows))
    total_rep.data["api"] = api
    total_rep.data["extra"]["translate_review"] = review
    total_rep.data["extra"]["language_distribution"] = {k: sum(1 for r in all_rows if r.get("language") == k) for k in ("vi", "en")}
    total_rep.check_conserved()
    if not dry_run and all_rows:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(all_rows).to_parquet(OUT_FILE, engine="pyarrow", index=False)
    total_rep.write()
    return reports
