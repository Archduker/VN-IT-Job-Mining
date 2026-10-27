# -*- coding: utf-8 -*-
"""preprocessing.normalization.target_schema_formatter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ định dạng dữ liệu chuẩn 11 khóa (Target Schema Formatter) cho VN-IT-Job-Mining.

Nhiệm vụ:
  1. Nhận record gốc (hoặc record đã qua normalization) kết hợp với kết quả làm giàu
     từ GeminiAllInOneAgent.
  2. Tinh giản triệt để toàn bộ các trường trung gian, cờ kỹ thuật và rác dữ liệu:
     (is_stub_jd, is_content_image, is_salary_winsorized, is_outlier_capped,
      quality_score, governance, nlp_metadata...).
  3. Cố định cấu trúc chính xác 11 khóa ở Root:
     - job_id_global
     - source_platform
     - source_url
     - job_info: {title, job_family, work_type, is_remote}
     - company: {name, industry, size}
     - locations: list[{province, district, Details_address}]
     - salary: {salary_min, salary_max, salary_currency, salary_source}
     - skills: {hard_skills, soft_skills, domain_skills}
     - requirements: {experience_years, standardized_seniority, standardized_education, is_saturday_work}
     - jd_text: {language, description, requirements, benefits}
     - date: {posted_date, expired_date}
  4. Cung cấp hàm `to_flat_target_record` hỗ trợ các mô hình ML/Data Mining dạng bảng phẳng.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Dict, List, Optional, Union

from preprocessing.normalization.text_cleaner import normalize_city

logger = logging.getLogger("target_schema_formatter")

CANONICAL_ROOT_KEYS = [
    "job_id_global",
    "source_platform",
    "source_url",
    "job_info",
    "company",
    "locations",
    "salary",
    "skills",
    "requirements",
    "jd_text",
    "date",
]


class TargetSchemaFormatter:
    """Formatter chuyển đổi mọi record về cấu trúc 11 khóa chuẩn."""

    @staticmethod
    def format_locations(raw_record: Dict[str, Any]) -> List[Dict[str, Optional[str]]]:
        """Chuẩn hóa mảng địa điểm thành list of {province, district, Details_address}."""
        locations: List[Dict[str, Optional[str]]] = []

        # 1. Nếu đã có cấu trúc locations
        raw_locs = raw_record.get("locations")
        if isinstance(raw_locs, list) and raw_locs:
            for item in raw_locs:
                if isinstance(item, dict):
                    prov = normalize_city(item.get("province") or item.get("city") or item.get("name"))
                    locations.append({
                        "province": prov or item.get("province") or "Chưa xác định",
                        "district": item.get("district"),
                        "Details_address": item.get("Details_address") or item.get("address"),
                    })
                elif isinstance(item, str) and item.strip():
                    prov = normalize_city(item)
                    locations.append({
                        "province": prov or item.strip(),
                        "district": None,
                        "Details_address": item.strip(),
                    })
            if locations:
                return locations

        # 2. Quét working_locations hoặc raw_location_text
        working_locs = raw_record.get("working_locations") or raw_record.get("working_locations_clean")
        raw_loc_text = raw_record.get("raw_location_text") or ""
        primary_city = raw_record.get("primary_city")

        if isinstance(working_locs, list) and working_locs:
            for w in working_locs:
                name = w.get("name") if isinstance(w, dict) else str(w)
                prov = normalize_city(name)
                locations.append({
                    "province": prov or name or "Chưa xác định",
                    "district": w.get("district") if isinstance(w, dict) else None,
                    "Details_address": raw_loc_text or None,
                })
        elif primary_city:
            locations.append({
                "province": primary_city,
                "district": None,
                "Details_address": raw_loc_text or None,
            })
        elif raw_loc_text:
            prov = normalize_city(raw_loc_text)
            locations.append({
                "province": prov or "Chưa xác định",
                "district": None,
                "Details_address": raw_loc_text,
            })
        else:
            locations.append({
                "province": "Chưa xác định",
                "district": None,
                "Details_address": None,
            })

        return locations

    @classmethod
    def format_record(
        cls,
        raw_record: Dict[str, Any],
        enriched_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Tổ chức record thành đúng 11 khóa chuẩn Target Schema.

        Args:
            raw_record: Record thô ban đầu hoặc record sau staging.
            enriched_data: Output từ GeminiAllInOneAgent.enrich_record().
        """
        enriched = enriched_data or {}

        # 1. Root IDs
        job_id = (
            raw_record.get("job_id_global")
            or raw_record.get("id")
            or f"job_{raw_record.get('source_platform', 'it')}_{id(raw_record)}"
        )
        source_platform = (
            raw_record.get("source_platform")
            or raw_record.get("platform")
            or "unknown"
        )
        source_url = (
            raw_record.get("source_url")
            or raw_record.get("url")
            or raw_record.get("job_url")
        )

        # 2. job_info
        raw_job_info = raw_record.get("job_info") if isinstance(raw_record.get("job_info"), dict) else {}
        title = (
            enriched.get("jd_text", {}).get("translated_title")
            or raw_job_info.get("title")
            or raw_record.get("job_title_clean")
            or raw_record.get("job_title")
            or "Chưa xác định"
        )
        job_family = (
            raw_job_info.get("job_family")
            or raw_record.get("standardized_job_family")
            or raw_record.get("job_family")
            or "JF00_OTHER_IT"
        )
        work_type = (
            raw_job_info.get("work_type")
            or raw_record.get("raw_work_type")
            or raw_record.get("work_type")
            or "fulltime"
        )
        is_remote_val = raw_job_info.get("is_remote")
        if is_remote_val is None:
            is_remote_val = raw_record.get("is_remote")
        is_remote = bool(is_remote_val) if is_remote_val is not None else False

        job_info = {
            "title": str(title).strip(),
            "job_family": str(job_family).strip(),
            "work_type": str(work_type).strip(),
            "is_remote": is_remote,
        }

        # 3. company
        raw_comp = raw_record.get("company") if isinstance(raw_record.get("company"), dict) else {}
        company = {
            "name": raw_comp.get("name") or raw_record.get("company_name") or "Chưa xác định",
            "industry": raw_comp.get("industry") or raw_record.get("company_industry"),
            "size": raw_comp.get("size") or raw_record.get("company_size"),
        }

        # 4. locations
        locations = cls.format_locations(raw_record)

        # 5. salary (Ground-Truth Realism: Preserve null for negotiable)
        en_sal = enriched.get("salary") or {}
        raw_sal = raw_record.get("salary") if isinstance(raw_record.get("salary"), dict) else {}

        sal_min = en_sal.get("salary_min")
        if sal_min is None:
            sal_min = raw_sal.get("salary_min") or raw_sal.get("salary_min_vnd") or raw_record.get("salary_min") or raw_record.get("salary_min_vnd")

        sal_max = en_sal.get("salary_max")
        if sal_max is None:
            sal_max = raw_sal.get("salary_max") or raw_sal.get("salary_max_vnd") or raw_record.get("salary_max") or raw_record.get("salary_max_vnd")

        sal_source = (
            en_sal.get("salary_source")
            or raw_sal.get("salary_source")
            or raw_record.get("salary_source")
            or ("explicit_range" if sal_min is not None else "negotiable")
        )

        is_neg = (
            en_sal.get("is_salary_negotiable")
            or raw_sal.get("is_salary_negotiable")
            or raw_sal.get("is_negotiable")
            or raw_record.get("is_salary_negotiable")
            or raw_record.get("is_negotiable")
        )

        if sal_min is not None and not (isinstance(sal_min, float) and math.isnan(sal_min)) and float(sal_min) > 0:
            sal_min_val = float(sal_min)
            sal_max_val = float(sal_max if sal_max is not None and not (isinstance(sal_max, float) and math.isnan(sal_max)) and float(sal_max) >= sal_min_val else sal_min_val)
            is_negotiable = False
            sal_source_str = str(sal_source).strip().lower()
            if sal_source_str in {"negotiable", "competitive", "predicted"}:
                sal_source_str = "explicit_range"
        else:
            sal_min_val = None
            sal_max_val = None
            is_negotiable = True
            sal_source_str = "competitive" if str(sal_source).strip().lower() == "competitive" else "negotiable"

        salary = {
            "salary_min": sal_min_val,
            "salary_max": sal_max_val,
            "salary_currency": "VND",
            "is_salary_negotiable": is_negotiable,
            "salary_source": sal_source_str,
        }

        # 6. skills
        en_skills = enriched.get("skills") or {}
        raw_skills = raw_record.get("skills") if isinstance(raw_record.get("skills"), dict) else {}
        skills = {
            "hard_skills": (
                en_skills.get("hard_skills")
                or raw_skills.get("hard_skills")
                or raw_record.get("hard_skills")
                or raw_record.get("skills_list")
                or []
            ),
            "soft_skills": (
                en_skills.get("soft_skills")
                or raw_skills.get("soft_skills")
                or raw_record.get("soft_skills")
                or []
            ),
            "domain_skills": (
                en_skills.get("domain_skills")
                or raw_skills.get("domain_skills")
                or raw_record.get("domain_skills")
                or []
            ),
        }

        # 7. requirements
        en_reqs = enriched.get("requirements") or {}
        raw_reqs = raw_record.get("requirements") if isinstance(raw_record.get("requirements"), dict) else {}
        exp_years = en_reqs.get("experience_years")
        if exp_years is None:
            exp_years = (
                raw_reqs.get("experience_years")
                or raw_job_info.get("min_experience_years")
                or raw_record.get("min_experience_years")
                or 0.0
            )

        sen = (
            en_reqs.get("standardized_seniority")
            or raw_reqs.get("standardized_seniority")
            or raw_job_info.get("standardized_seniority")
            or raw_record.get("standardized_seniority")
            or "middle"
        )
        sen = str(sen).strip().lower()

        edu = (
            en_reqs.get("standardized_education")
            or raw_reqs.get("standardized_education")
            or raw_record.get("standardized_education")
            or "none"
        )

        sat_work = en_reqs.get("is_saturday_work")
        if sat_work is None:
            sat_work = raw_reqs.get("is_saturday_work")

        requirements = {
            "experience_years": float(exp_years),
            "standardized_seniority": sen,
            "standardized_education": str(edu).strip().lower(),
            "is_saturday_work": sat_work if isinstance(sat_work, bool) else None,
        }

        # 8. jd_text
        en_jd = enriched.get("jd_text") or {}
        raw_jd = raw_record.get("jd_text") if isinstance(raw_record.get("jd_text"), dict) else {}
        desc = (
            en_jd.get("translated_description")
            or en_jd.get("description")
            or raw_jd.get("description")
            or raw_jd.get("description_text")
            or raw_record.get("jd_clean_text")
            or raw_record.get("raw_description_text")
            or ""
        )
        req_text = (
            en_jd.get("translated_requirements")
            or en_jd.get("requirements")
            or raw_jd.get("requirements")
            or raw_jd.get("requirements_text")
            or raw_record.get("requirements_clean_text")
            or raw_record.get("raw_requirements_text")
            or ""
        )
        benefits = (
            en_jd.get("translated_benefits")
            or en_jd.get("benefits")
            or raw_jd.get("benefits")
            or raw_jd.get("benefits_text")
            or raw_record.get("benefits_list")
            or []
        )
        if isinstance(benefits, str):
            benefits = [benefits]

        desc_clean = str(desc).strip()
        req_clean = str(req_text).strip()
        if not desc_clean and req_clean:
            desc_clean = req_clean
        elif not desc_clean:
            desc_clean = f"Tuyển dụng {title or 'nhân sự IT'}"

        jd_text = {
            "language": "vi",  # Chuẩn hóa về tiếng Việt sau bản địa hóa
            "description": desc_clean,
            "requirements": req_clean,
            "benefits": list(benefits),
        }

        # 9. date
        raw_date = raw_record.get("date") if isinstance(raw_record.get("date"), dict) else {}
        posted = (
            raw_date.get("posted_date")
            or raw_record.get("posted_date")
            or raw_record.get("created_at")
            or raw_record.get("crawl_date")
        )
        expired = (
            raw_date.get("expired_date")
            or raw_record.get("expired_date")
            or raw_record.get("deadline")
        )

        date = {
            "posted_date": str(posted).strip() if posted else None,
            "expired_date": str(expired).strip() if expired else None,
        }

        return {
            "job_id_global": str(job_id),
            "source_platform": str(source_platform),
            "source_url": str(source_url) if source_url else None,
            "job_info": job_info,
            "company": company,
            "locations": locations,
            "salary": salary,
            "skills": skills,
            "requirements": requirements,
            "jd_text": jd_text,
            "date": date,
        }

    @classmethod
    def to_flat_target_record(cls, hierarchical_record: Dict[str, Any]) -> Dict[str, Any]:
        """Làm phẳng hierarchical record 11 khóa thành 1 tầng đơn giản cho mô hình ML/Tabular."""
        root = hierarchical_record
        job_info = root.get("job_info") or {}
        comp = root.get("company") or {}
        sal = root.get("salary") or {}
        skills = root.get("skills") or {}
        reqs = root.get("requirements") or {}
        jd = root.get("jd_text") or {}
        date = root.get("date") or {}
        locs = root.get("locations") or []

        primary_city = locs[0].get("province") if locs and isinstance(locs[0], dict) else "Chưa xác định"

        return {
            "job_id_global": root.get("job_id_global"),
            "source_platform": root.get("source_platform"),
            "source_url": root.get("source_url"),
            "job_title": job_info.get("title"),
            "job_family": job_info.get("job_family"),
            "work_type": job_info.get("work_type"),
            "is_remote": job_info.get("is_remote", False),
            "company_name": comp.get("name"),
            "company_industry": comp.get("industry"),
            "company_size": comp.get("size"),
            "primary_city": primary_city,
            "locations_json": json.dumps(locs, ensure_ascii=False),
            "salary_min": sal.get("salary_min"),
            "salary_max": sal.get("salary_max"),
            "salary_currency": sal.get("salary_currency", "VND"),
            "is_salary_negotiable": sal.get("is_salary_negotiable", False if sal.get("salary_min") else True),
            "salary_source": sal.get("salary_source", "negotiable"),
            "hard_skills": skills.get("hard_skills", []),
            "soft_skills": skills.get("soft_skills", []),
            "domain_skills": skills.get("domain_skills", []),
            "experience_years": reqs.get("experience_years", 0.0),
            "standardized_seniority": reqs.get("standardized_seniority", "middle"),
            "standardized_education": reqs.get("standardized_education", "none"),
            "is_saturday_work": reqs.get("is_saturday_work"),
            "language": jd.get("language", "vi"),
            "description": jd.get("description", ""),
            "requirements": jd.get("requirements", ""),
            "benefits": jd.get("benefits", []),
            "posted_date": date.get("posted_date"),
            "expired_date": date.get("expired_date"),
        }
