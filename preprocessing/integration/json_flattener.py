# -*- coding: utf-8 -*-
"""preprocessing.integration.json_flattener
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module ép phẳng JSON (JSON Flattening) và gom nhóm đa nguồn cho VN-IT-Job-Mining.

Hỗ trợ 2 định dạng biểu diễn:
  1. Dạng Nhóm Đối Tượng (Dual-Form / Grouped JSON):
     - Cấp gốc: Các khóa định danh phẳng (job_id_global, source_platform, source_job_id, source_url, crawled_at).
     - 8 nhóm thuộc tính: company, location, skills, jd, salary, date, extract, other.
  2. Dạng Phẳng 1 Tầng (Canonical Flat Record):
     - Mọi trường đều trải phẳng ở cấp 1, tối ưu cho việc đưa vào Pandas/Polars DataFrame.

Nguyên tắc:
  - BẢO TOÀN THÔNG TIN TUYỆT ĐỐI (Zero Information Loss).
  - Khai thác tối đa các trường ẩn: company_logo_image, geo_coordinates, is_content_image, salary_currency, age, gender.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from preprocessing.transformation.html_cleaner import strip_html_tags
from preprocessing.transformation.bullet_stitcher import stitch_fragmented_bullets


def _clean_str(val: Any) -> Optional[str]:
    """Làm sạch chuỗi ký tự, trả về None nếu rỗng hoặc chỉ chứa khoảng trắng."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _dedup_list(items: List[Any]) -> List[str]:
    """Khử trùng lặp phần tử trong list nhưng bảo toàn thứ tự ban đầu."""
    seen = set()
    result = []
    for item in items:
        if item is None:
            continue
        cleaned = str(item).strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            result.append(cleaned)
    return result


def _extract_job_locations_from_jsonld(jsonld: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Trích xuất địa điểm từ jobLocation trong JSON-LD một cách an toàn.

    Returns:
        Tuple: (raw_location_text, company_address, working_locations)
    """
    raw_loc = None
    company_addr = None
    w_locs = []

    job_loc = jsonld.get("jobLocation")
    if not job_loc:
        return raw_loc, company_addr, w_locs

    loc_list = job_loc if isinstance(job_loc, list) else [job_loc]
    for loc_item in loc_list:
        if isinstance(loc_item, dict):
            address = loc_item.get("address")
            if isinstance(address, dict):
                addr_loc = address.get("addressLocality") or address.get("addressRegion")
                street = address.get("streetAddress")
                if addr_loc and not raw_loc:
                    raw_loc = _clean_str(addr_loc)
                if street:
                    s_clean = _clean_str(street)
                    if not company_addr:
                        company_addr = s_clean
                    w_locs.append(s_clean)
                elif addr_loc:
                    w_locs.append(_clean_str(addr_loc))
            elif isinstance(address, str):
                s_clean = _clean_str(address)
                if not company_addr:
                    company_addr = s_clean
                w_locs.append(s_clean)
            else:
                direct_loc = loc_item.get("addressLocality") or loc_item.get("name")
                if direct_loc:
                    s_clean = _clean_str(direct_loc)
                    if not raw_loc:
                        raw_loc = s_clean
                    w_locs.append(s_clean)
        elif isinstance(loc_item, str):
            s_clean = _clean_str(loc_item)
            if not raw_loc:
                raw_loc = s_clean
            w_locs.append(s_clean)

    return raw_loc, company_addr, w_locs


def to_grouped_record(flat: Dict[str, Any]) -> Dict[str, Any]:
    """Chuyển bản ghi phẳng thành cấu trúc Khóa định danh phẳng + 8 nhóm đối tượng con."""
    return {
        # Khóa định danh phẳng ở cấp gốc
        "job_id_global": flat.get("job_id_global"),
        "source_platform": flat.get("source_platform"),
        "source_job_id": flat.get("source_job_id"),
        "source_url": flat.get("source_url"),
        "crawled_at": flat.get("crawled_at"),
        # 1. Nhóm Company (Doanh nghiệp)
        "company": {
            "company_name": flat.get("company_name"),
            "company_scale": flat.get("company_scale"),
            "company_address": flat.get("company_address"),
            "company_url": flat.get("company_url"),
            "company_logo_image": flat.get("company_logo_image"),
            "company_industry": flat.get("company_industry"),
        },
        # 2. Nhóm Địa điểm (Nơi làm việc ứng viên)
        "location": {
            "raw_location_text": flat.get("raw_location_text"),
            "working_locations": flat.get("working_locations", []),
            "geo_coordinates": flat.get("geo_coordinates"),
        },
        # 3. Nhóm Kỹ năng
        "skills": {
            "skills_list": flat.get("skills_list", []),
        },
        # 4. Nhóm JD
        "jd": {
            "job_title": flat.get("job_title"),
            "raw_description_text": flat.get("raw_description_text"),
            "raw_requirements_text": flat.get("raw_requirements_text"),
            "benefits_list": flat.get("benefits_list", []),
        },
        # 5. Nhóm Lương
        "salary": {
            "raw_salary_text": flat.get("raw_salary_text"),
            "salary_currency": flat.get("salary_currency"),
            "is_salary_visible": flat.get("is_salary_visible"),
        },
        # 6. Nhóm Thời gian
        "date": {
            "raw_posted_date": flat.get("raw_posted_date"),
            "raw_updated_at": flat.get("raw_updated_at"),
            "raw_deadline": flat.get("raw_deadline"),
        },
        # 7. Nhóm Trường Ẩn & Phái sinh
        "extract": {
            "raw_work_mode": flat.get("raw_work_mode"),
            "raw_seniority_text": flat.get("raw_seniority_text"),
            "raw_experience_text": flat.get("raw_experience_text"),
            "raw_education_text": flat.get("raw_education_text"),
            "raw_headcount": flat.get("raw_headcount"),
            "raw_working_time": flat.get("raw_working_time"),
            "raw_age_text": flat.get("raw_age_text"),
            "raw_gender_text": flat.get("raw_gender_text"),
            "raw_employment_type": flat.get("raw_employment_type"),
        },
        # 8. Nhóm Tính năng Bổ trợ bước sau
        "other": {
            "raw_category_text": flat.get("raw_category_text"),
            "is_content_image": flat.get("is_content_image"),
            "auxiliary_features": flat.get("auxiliary_features", {}),
        },
    }


def to_flat_record(grouped: Dict[str, Any]) -> Dict[str, Any]:
    """Trải phẳng cấu trúc nhóm về dạng phẳng 1 tầng."""
    flat: Dict[str, Any] = {
        "job_id_global": grouped.get("job_id_global"),
        "source_platform": grouped.get("source_platform"),
        "source_job_id": grouped.get("source_job_id"),
        "source_url": grouped.get("source_url"),
        "crawled_at": grouped.get("crawled_at"),
    }
    for grp_key in ["company", "location", "skills", "jd", "salary", "date", "extract", "other"]:
        grp_data = grouped.get(grp_key)
        if isinstance(grp_data, dict):
            flat.update(grp_data)
    return flat


CANONICAL_29_FLAT_KEYS = [
    "job_id_global", "source_platform", "source_job_id", "source_url", "crawled_at",
    "job_title", "company_name", "company_address", "company_scale", "raw_category_text",
    "raw_location_text", "working_locations", "raw_posted_date", "raw_updated_at", "raw_deadline", "raw_working_time",
    "raw_salary_text", "raw_employment_type", "raw_work_mode",
    "raw_experience_text", "raw_seniority_text", "raw_education_text", "raw_headcount", "raw_age_text", "raw_gender_text",
    "skills_list", "benefits_list", "raw_description_text", "raw_requirements_text",
]


def flatten_raw_job_record(
    record_data: Dict[str, Any],
    source_fallback: Optional[str] = None,
    return_grouped: bool = False,
    include_auxiliary: bool = False,
) -> Dict[str, Any]:
    """Ép phẳng một bản ghi JSON thô từ bất kỳ nguồn nào về cấu trúc chuẩn.

    Args:
        record_data: Dict chứa raw envelope (`metadata` + `raw_payload`) hoặc `_meta` + `raw`.
        source_fallback: Tên sàn dự phòng nếu metadata không khai báo.
        return_grouped: True nếu muốn trả về cấu trúc phân 8 nhóm có định danh phẳng; False trả về dict phẳng 1 tầng.

    Returns:
        Dict bản ghi đã tích hợp (Grouped hoặc Flat).
    """
    meta = record_data.get("metadata") or record_data.get("_meta") or {}
    raw = record_data.get("raw_payload") or record_data.get("raw") or {}

    source = (meta.get("source") or meta.get("source_platform") or source_fallback or "unknown").lower().strip()
    job_id = str(meta.get("job_id") or meta.get("source_job_id") or "")
    source_url = meta.get("source_url") or meta.get("url") or ""
    crawled_at = meta.get("scraped_at") or meta.get("crawled_at") or ""
    job_id_global = f"{source}_{job_id}"

    # Khởi tạo bản ghi phẳng toàn diện (Comprehensive Flat Record)
    flat: Dict[str, Any] = {
        # Identifiers
        "job_id_global": job_id_global,
        "source_platform": source,
        "source_job_id": job_id,
        "source_url": source_url,
        "crawled_at": crawled_at,
        # Company
        "company_name": None,
        "company_scale": None,
        "company_address": None,
        "company_url": None,
        "company_logo_image": None,
        "company_industry": None,
        # Location
        "raw_location_text": None,
        "working_locations": [],
        "geo_coordinates": None,
        # Skills
        "skills_list": [],
        # JD
        "job_title": None,
        "raw_description_text": None,
        "raw_requirements_text": None,
        "benefits_list": [],
        # Salary
        "raw_salary_text": None,
        "salary_currency": None,
        "is_salary_visible": None,
        # Date
        "raw_posted_date": None,
        "raw_updated_at": None,
        "raw_deadline": None,
        # Extract
        "raw_work_mode": None,
        "raw_seniority_text": None,
        "raw_experience_text": None,
        "raw_education_text": None,
        "raw_headcount": None,
        "raw_working_time": None,
        "raw_age_text": None,
        "raw_gender_text": None,
        "raw_employment_type": None,
        # Other
        "raw_category_text": None,
        "is_content_image": None,
        "auxiliary_features": {},
    }

    # Bóc tách đặc thù theo từng sàn
    if source == "careerviet":
        _flatten_careerviet(raw, flat)
    elif source == "glints":
        _flatten_glints(raw, flat)
    elif source == "itviec":
        _flatten_itviec(raw, flat)
    elif source == "jobsgo":
        _flatten_jobsgo(raw, flat)
    elif source == "topcv":
        _flatten_topcv(raw, flat)
    elif source == "topdev":
        _flatten_topdev(raw, flat)
    elif source == "vieclam24h":
        _flatten_vieclam24h(raw, flat)
    elif source == "vietnamworks":
        _flatten_vietnamworks(raw, flat)
    else:
        _flatten_generic(raw, flat)

    # Đảm bảo mảng danh sách được khử trùng lặp
    flat["skills_list"] = _dedup_list(flat.get("skills_list") or [])
    flat["benefits_list"] = _dedup_list(flat.get("benefits_list") or [])
    flat["working_locations"] = _dedup_list(flat.get("working_locations") or [])

    if return_grouped:
        return to_grouped_record(flat)
    if not include_auxiliary:
        return {k: flat.get(k) for k in CANONICAL_29_FLAT_KEYS}
    return flat


def _flatten_careerviet(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("job-company-name"))
    flat["raw_location_text"] = _clean_str(raw.get("map"))

    if raw.get("map"):
        flat["working_locations"].append(str(raw["map"]).strip())

    # Ép phẳng mảng chuỗi detail-box
    detail_box = raw.get("detail-box")
    if isinstance(detail_box, list):
        for item in detail_box:
            if not isinstance(item, str):
                continue
            item = item.strip()
            item_l = item.lower()
            if item.startswith("Lương") or "lương" in item_l[:10]:
                flat["raw_salary_text"] = re.sub(r"^(Lương\s*)+:?", "", item, flags=re.IGNORECASE).strip()
            elif item.startswith("Kinh nghiệm") or "kinh nghiệm" in item_l[:15]:
                flat["raw_experience_text"] = re.sub(r"^(Kinh nghiệm\s*)+:?", "", item, flags=re.IGNORECASE).strip()
            elif item.startswith("Cấp bậc") or "cấp bậc" in item_l[:12]:
                flat["raw_seniority_text"] = re.sub(r"^(Cấp bậc\s*)+:?", "", item, flags=re.IGNORECASE).strip()
            elif item.startswith("Hết hạn nộp") or "hết hạn" in item_l[:15]:
                flat["raw_deadline"] = re.sub(r"^(Hết hạn nộp\s*)+:?", "", item, flags=re.IGNORECASE).strip()
            elif item.startswith("Ngày cập nhật") or "cập nhật" in item_l[:15]:
                d_val = re.sub(r"^(Ngày cập nhật\s*)+:?", "", item, flags=re.IGNORECASE).strip()
                flat["raw_updated_at"] = d_val
                if not flat["raw_posted_date"]:
                    flat["raw_posted_date"] = d_val
            elif item.startswith("Hình thức") or "hình thức" in item_l[:15]:
                flat["raw_employment_type"] = re.sub(r"^(Hình thức\s*)+:?", "", item, flags=re.IGNORECASE).strip()
            elif item.startswith("Ngành nghề") or "ngành nghề" in item_l[:15]:
                flat["raw_category_text"] = re.sub(r"^(Ngành nghề\s*)+:?", "", item, flags=re.IGNORECASE).strip()
            elif "bằng cấp" in item_l or "trình độ" in item_l:
                flat["raw_education_text"] = re.sub(r"^(Bằng cấp|Trình độ)\s*:?", "", item, flags=re.IGNORECASE).strip()
            elif "số lượng" in item_l or "chỉ tiêu" in item_l:
                flat["raw_headcount"] = re.sub(r"^(Số lượng tuyển|Số lượng)\s*:?", "", item, flags=re.IGNORECASE).strip()
            elif "độ tuổi" in item_l or "tuổi" in item_l[:10]:
                flat["raw_age_text"] = re.sub(r"^(Độ tuổi|Tuổi)\s*:?", "", item, flags=re.IGNORECASE).strip()
            elif "giới tính" in item_l:
                flat["raw_gender_text"] = re.sub(r"^(Giới tính)\s*:?", "", item, flags=re.IGNORECASE).strip()

    # Ngành nghề phụ
    if not flat["raw_category_text"] and raw.get("Ngành nghề"):
        cat = raw.get("Ngành nghề")
        flat["raw_category_text"] = ", ".join(cat) if isinstance(cat, list) else str(cat)
    flat["company_industry"] = flat.get("raw_category_text")

    # Suy luận currency và visibility
    sal = flat.get("raw_salary_text") or ""
    if "$" in sal or "usd" in sal.lower():
        flat["salary_currency"] = "USD"
    elif "vnd" in sal.lower() or "triệu" in sal.lower() or "đ" in sal.lower():
        flat["salary_currency"] = "VND"
    if "cạnh tranh" in sal.lower() or "thỏa thuận" in sal.lower():
        flat["is_salary_visible"] = False
    elif any(c.isdigit() for c in sal):
        flat["is_salary_visible"] = True

    # Ép phẳng detail-row
    detail_row = raw.get("detail-row")
    if isinstance(detail_row, dict):
        flat["raw_description_text"] = _clean_str(detail_row.get("Mô tả Công việc"))
        flat["raw_requirements_text"] = _clean_str(detail_row.get("Yêu Cầu Công Việc"))
        work_addr = detail_row.get("Địa điểm làm việc")
        if work_addr:
            flat["company_address"] = _clean_str(work_addr)
            flat["working_locations"].append(str(work_addr).strip())

        ben_str = detail_row.get("Phúc lợi")
        if ben_str:
            flat["benefits_list"] = [b.strip() for b in re.split(r"[\n\r;•\-\*]+", str(ben_str)) if b.strip()]

    # Tags kỹ năng
    tags = raw.get("job-tags")
    if isinstance(tags, list):
        flat["skills_list"] = [str(t) for t in tags]


def _flatten_glints(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("job-title") or raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("company-name") or raw.get("company"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary"))
    flat["raw_description_text"] = _clean_str(raw.get("description"))
    flat["raw_requirements_text"] = _clean_str(raw.get("requirements"))

    # Bóc tách từ requirements text
    req_text = str(raw.get("requirements") or "")
    for line in req_text.splitlines():
        line_s = line.strip()
        line_l = line_s.lower()
        if "làm tại công ty" in line_l:
            flat["raw_work_mode"] = "Làm tại công ty / Onsite"
        elif "từ xa" in line_l or "remote" in line_l:
            flat["raw_work_mode"] = "Làm việc từ xa / Remote"
        elif "hybrid" in line_l or "kết hợp" in line_l:
            flat["raw_work_mode"] = "Hybrid"
        if "năm kinh nghiệm" in line_l and not flat["raw_experience_text"]:
            flat["raw_experience_text"] = line_s
        if any(e in line_l for e in ["cử nhân", "đại học", "cao đẳng", "thạc sĩ"]) and not flat["raw_education_text"]:
            flat["raw_education_text"] = line_s

    # Currency & Visibility từ text salary
    sal = flat.get("raw_salary_text") or ""
    if "₫" in sal or "vnd" in sal.lower():
        flat["salary_currency"] = "VND"
    elif "$" in sal or "usd" in sal.lower():
        flat["salary_currency"] = "USD"
    if any(c.isdigit() for c in sal):
        flat["is_salary_visible"] = True
    elif "thỏa thuận" in sal.lower() or "thương lượng" in sal.lower():
        flat["is_salary_visible"] = False

    # Bóc tách JSON-LD ngầm
    jsonld = raw.get("job_posting_jsonld")
    if isinstance(jsonld, dict):
        if not flat["job_title"]:
            flat["job_title"] = _clean_str(jsonld.get("title"))
        if not flat["raw_posted_date"]:
            flat["raw_posted_date"] = _clean_str(jsonld.get("datePosted"))
        if not flat["raw_deadline"]:
            flat["raw_deadline"] = _clean_str(jsonld.get("validThrough"))
        if not flat["raw_employment_type"]:
            flat["raw_employment_type"] = _clean_str(jsonld.get("employmentType"))
        if not flat["raw_category_text"]:
            flat["raw_category_text"] = _clean_str(jsonld.get("occupationalCategory") or jsonld.get("industry"))

        # Bằng cấp từ JSON-LD
        edu_req = jsonld.get("educationRequirements")
        if isinstance(edu_req, dict) and edu_req.get("credentialCategory"):
            flat["raw_education_text"] = _clean_str(edu_req.get("credentialCategory"))
        elif isinstance(edu_req, str):
            flat["raw_education_text"] = _clean_str(edu_req)

        # Thông tin Công ty từ JSON-LD
        org = jsonld.get("hiringOrganization")
        if isinstance(org, dict):
            if org.get("logo"):
                flat["company_logo_image"] = _clean_str(org.get("logo"))
            if org.get("sameAs"):
                flat["company_url"] = _clean_str(org.get("sameAs"))
            if not flat["company_name"]:
                flat["company_name"] = _clean_str(org.get("name"))

        # Địa điểm an toàn từ JSON-LD
        r_loc, c_addr, w_locs = _extract_job_locations_from_jsonld(jsonld)
        if r_loc and not flat["raw_location_text"]:
            flat["raw_location_text"] = r_loc
        if c_addr and not flat["company_address"]:
            flat["company_address"] = c_addr
        flat["working_locations"].extend(w_locs)

    # Skills
    skills_raw = raw.get("skills")
    if isinstance(skills_raw, str):
        flat["skills_list"] = [s.strip() for s in re.split(r"[,|;/•]+", skills_raw) if s.strip() and s.strip().lower() != "kỹ năng"]
    elif isinstance(skills_raw, list):
        flat["skills_list"] = [str(s) for s in skills_raw]

    # Benefits
    ben_raw = raw.get("benefits")
    if isinstance(ben_raw, str):
        flat["benefits_list"] = [b.strip() for b in ben_raw.splitlines() if b.strip() and "job benefits" not in b.lower()]


def _flatten_itviec(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("company_name") or raw.get("company"))
    flat["company_url"] = _clean_str(raw.get("company_url"))
    flat["raw_location_text"] = _clean_str(raw.get("work_location"))
    flat["raw_posted_date"] = _clean_str(raw.get("posted_at_raw"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary_display_text"))

    if raw.get("work_model"):
        flat["raw_work_mode"] = _clean_str(raw.get("work_model"))

    # Ép phẳng sections
    sections = raw.get("sections")
    if isinstance(sections, dict):
        for sec_name, sec_val in sections.items():
            text_val = "\n".join(sec_val) if isinstance(sec_val, list) else str(sec_val)
            sec_lower = sec_name.lower()
            if "mô tả" in sec_lower:
                flat["raw_description_text"] = text_val
            elif "yêu cầu" in sec_lower:
                flat["raw_requirements_text"] = text_val
            elif "tại sao" in sec_lower or "phúc lợi" in sec_lower or "lý do" in sec_lower:
                if isinstance(sec_val, list):
                    flat["benefits_list"].extend(sec_val)

    # Auxiliary features
    if raw.get("specialization"):
        flat["auxiliary_features"]["specialization"] = raw["specialization"]
    if raw.get("industries"):
        flat["auxiliary_features"]["industries"] = raw["industries"]
        flat["company_industry"] = ", ".join(raw["industries"]) if isinstance(raw["industries"], list) else str(raw["industries"])

    # Bóc tách JSON-LD
    jsonld = raw.get("job_posting_jsonld")
    if isinstance(jsonld, dict):
        if not flat["raw_posted_date"]:
            flat["raw_posted_date"] = _clean_str(jsonld.get("datePosted"))
        if not flat["raw_deadline"]:
            flat["raw_deadline"] = _clean_str(jsonld.get("validThrough"))
        if not flat["raw_employment_type"]:
            flat["raw_employment_type"] = _clean_str(jsonld.get("employmentType"))
        if not flat["raw_category_text"]:
            flat["raw_category_text"] = _clean_str(jsonld.get("industry"))

        # Công ty & Logo
        org = jsonld.get("hiringOrganization")
        if isinstance(org, dict):
            if org.get("logo"):
                flat["company_logo_image"] = _clean_str(org.get("logo"))
            if org.get("sameAs") and not flat["company_url"]:
                flat["company_url"] = _clean_str(org.get("sameAs"))

        base_sal = jsonld.get("baseSalary")
        if isinstance(base_sal, dict):
            flat["salary_currency"] = base_sal.get("currency", "USD")
            val_obj = base_sal.get("value")
            if isinstance(val_obj, dict):
                min_v = val_obj.get("minValue")
                max_v = val_obj.get("maxValue")
                curr = flat["salary_currency"]
                if min_v or max_v:
                    flat["raw_salary_text"] = f"{min_v} - {max_v} {curr}"
                    flat["is_salary_visible"] = True
            elif isinstance(val_obj, (int, float, str)):
                curr = flat["salary_currency"]
                flat["raw_salary_text"] = f"{val_obj} {curr}"
                flat["is_salary_visible"] = True

        # Địa điểm an toàn từ JSON-LD
        r_loc, c_addr, w_locs = _extract_job_locations_from_jsonld(jsonld)
        if r_loc and not flat["raw_location_text"]:
            flat["raw_location_text"] = r_loc
        if c_addr and not flat["company_address"]:
            flat["company_address"] = c_addr
        flat["working_locations"].extend(w_locs)

    # Skills
    skill_tags = raw.get("skill_tags") or raw.get("skills")
    if isinstance(skill_tags, list):
        flat["skills_list"].extend([str(s) for s in skill_tags])


def _flatten_jobsgo(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("company"))
    flat["company_industry"] = _clean_str(raw.get("company_field"))
    flat["company_address"] = _clean_str(raw.get("company_address"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary_raw"))
    flat["raw_experience_text"] = _clean_str(raw.get("experience"))
    flat["raw_location_text"] = _clean_str(raw.get("location"))
    flat["raw_deadline"] = _clean_str(raw.get("deadline_raw"))
    flat["raw_education_text"] = _clean_str(raw.get("education"))
    flat["raw_working_time"] = _clean_str(raw.get("working_time"))

    # Currency & Visibility
    sal = flat.get("raw_salary_text") or ""
    if "triệu" in sal.lower() or "vnđ" in sal.lower() or "vnd" in sal.lower():
        flat["salary_currency"] = "VND"
    elif "$" in sal:
        flat["salary_currency"] = "USD"
    flat["is_salary_visible"] = True if any(c.isdigit() for c in sal) else False

    # Địa điểm chi tiết
    wp = raw.get("working_places")
    if isinstance(wp, list):
        for p in wp:
            if p:
                flat["working_locations"].append(str(p).strip())

    # Ngành nghề
    occs = raw.get("occupations")
    if isinstance(occs, list):
        flat["raw_category_text"] = ", ".join(str(o) for o in occs if o)
        flat["skills_list"].extend([str(o) for o in occs if o])
        flat["auxiliary_features"]["occupations"] = occs

    # General info
    gen = raw.get("general_info")
    if isinstance(gen, dict):
        flat["raw_seniority_text"] = _clean_str(gen.get("job_level"))
        flat["raw_posted_date"] = _clean_str(gen.get("posted_date"))
        flat["raw_employment_type"] = _clean_str(gen.get("employment_type"))
        flat["raw_headcount"] = _clean_str(gen.get("hiring_quantity"))
        flat["raw_gender_text"] = _clean_str(gen.get("gender"))
        flat["raw_age_text"] = _clean_str(gen.get("age"))

    # Bullets
    desc = raw.get("description_bullets")
    if isinstance(desc, list):
        flat["raw_description_text"] = "\n".join(desc)
    reqs = raw.get("requirements_bullets")
    if isinstance(reqs, list):
        flat["raw_requirements_text"] = "\n".join(reqs)
    bens = raw.get("benefits_bullets")
    if isinstance(bens, list):
        flat["benefits_list"] = [str(b) for b in bens]


def _flatten_topcv(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("company"))
    flat["company_address"] = _clean_str(raw.get("company_address"))
    flat["company_scale"] = _clean_str(raw.get("company_scale"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary_raw"))
    flat["raw_experience_text"] = _clean_str(raw.get("experience"))
    flat["raw_location_text"] = _clean_str(raw.get("location"))
    flat["raw_deadline"] = _clean_str(raw.get("deadline_raw"))
    flat["raw_working_time"] = _clean_str(raw.get("working_time"))
    flat["raw_category_text"] = _clean_str(raw.get("company_industry"))
    flat["company_industry"] = flat.get("raw_category_text")

    # Currency & Visibility
    sal = flat.get("raw_salary_text") or ""
    if "triệu" in sal.lower() or "vnd" in sal.lower() or "đ" in sal.lower():
        flat["salary_currency"] = "VND"
    elif "$" in sal:
        flat["salary_currency"] = "USD"
    flat["is_salary_visible"] = True if any(c.isdigit() for c in sal) else False

    # Địa điểm chi nhánh
    wp = raw.get("working_places")
    if isinstance(wp, list):
        for p in wp:
            if p:
                flat["working_locations"].append(str(p).strip())
    elif wp:
        flat["working_locations"].append(str(wp).strip())

    # Ép phẳng general_info
    gen = raw.get("general_info")
    if isinstance(gen, dict):
        flat["raw_seniority_text"] = _clean_str(gen.get("Cấp bậc"))
        flat["raw_education_text"] = _clean_str(gen.get("Học vấn") or gen.get("Bằng cấp"))
        flat["raw_headcount"] = _clean_str(gen.get("Số lượng tuyển"))
        flat["raw_employment_type"] = _clean_str(gen.get("Loại hình làm việc") or gen.get("Hình thức làm việc"))
        flat["raw_gender_text"] = _clean_str(gen.get("Giới tính"))
        flat["raw_age_text"] = _clean_str(gen.get("Độ tuổi"))
        work_mode = gen.get("Hình thức làm việc")
        if work_mode:
            flat["raw_work_mode"] = str(work_mode).strip()
        if gen.get("Mức độ cạnh tranh"):
            flat["auxiliary_features"]["Mức độ cạnh tranh"] = gen["Mức độ cạnh tranh"]
        if gen.get("Kinh nghiệm quản lý"):
            flat["auxiliary_features"]["Kinh nghiệm quản lý"] = gen["Kinh nghiệm quản lý"]

    # Ép phẳng overview_tags
    otags = raw.get("overview_tags")
    if isinstance(otags, dict):
        if "Chuyên môn" in otags and isinstance(otags["Chuyên môn"], list):
            flat["skills_list"].extend(otags["Chuyên môn"])
        if "Quyền lợi" in otags and isinstance(otags["Quyền lợi"], list):
            flat["benefits_list"].extend(otags["Quyền lợi"])
        yêu_cầu = otags.get("Yêu cầu") or []
        if isinstance(yêu_cầu, list):
            for yc in yêu_cầu:
                yc_s = str(yc).strip()
                yc_l = yc_s.lower()
                if "tuổi" in yc_l and not flat["raw_age_text"]:
                    flat["raw_age_text"] = yc_s
                elif any(e in yc_l for e in ["đại học", "cao đẳng", "cử nhân", "thạc sĩ"]) and not flat["raw_education_text"]:
                    flat["raw_education_text"] = yc_s

    # Phúc lợi bổ sung
    for k in ["welfare_tags", "allowance_tags"]:
        tags = raw.get(k)
        if isinstance(tags, list):
            flat["benefits_list"].extend([str(t) for t in tags])

    # Kỹ năng bổ sung
    for k in ["required_skills", "industry_knowledge"]:
        skills = raw.get(k)
        if isinstance(skills, list):
            flat["skills_list"].extend([str(s) for s in skills])

    # Bullets
    desc = raw.get("description_bullets")
    if isinstance(desc, list):
        flat["raw_description_text"] = "\n".join(desc)
    reqs = raw.get("requirements_bullets")
    if isinstance(reqs, list):
        flat["raw_requirements_text"] = "\n".join(reqs)
    bens = raw.get("benefits_bullets")
    if isinstance(bens, list):
        flat["benefits_list"].extend(bens)


def _flatten_topdev(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("title") or raw.get("job-title"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary_raw") or raw.get("salary"))
    flat["raw_posted_date"] = _clean_str(raw.get("recalled_at") or raw.get("created_at"))
    flat["is_content_image"] = raw.get("is_content_image")

    # Company
    comp = raw.get("company")
    if isinstance(comp, dict):
        flat["company_name"] = _clean_str(comp.get("company_name") or comp.get("name") or raw.get("company-name"))
        flat["company_scale"] = _clean_str(comp.get("company_size") or comp.get("scale"))
        flat["company_industry"] = _clean_str(comp.get("industry"))
    else:
        flat["company_name"] = _clean_str(raw.get("company") or raw.get("company-name"))

    flat["company_url"] = _clean_str(raw.get("detail_url"))

    # Currency & Visibility
    sal = flat.get("raw_salary_text") or ""
    if "$" in sal or "usd" in sal.lower():
        flat["salary_currency"] = "USD"
    elif "vnd" in sal.lower() or "triệu" in sal.lower() or "đ" in sal.lower():
        flat["salary_currency"] = "VND"
    if "thỏa thuận" in sal.lower() or "negotiable" in sal.lower():
        flat["is_salary_visible"] = False
    elif any(c.isdigit() for c in sal):
        flat["is_salary_visible"] = True

    # Addresses
    addrs = raw.get("addresses")
    if isinstance(addrs, dict):
        region_list = addrs.get("address_region_list")
        if isinstance(region_list, list) and region_list:
            flat["raw_location_text"] = ", ".join(region_list)
        elif isinstance(region_list, str):
            flat["raw_location_text"] = region_list

        flat["company_address"] = _clean_str(addrs.get("full_address"))

        full_addrs = addrs.get("full_addresses")
        if isinstance(full_addrs, list):
            flat["working_locations"].extend([str(a).strip() for a in full_addrs if str(a).strip()])

        col_addrs = addrs.get("collection_addresses")
        if isinstance(col_addrs, list):
            for ca in col_addrs:
                if isinstance(ca, dict) and ca.get("full_address"):
                    flat["working_locations"].append(str(ca["full_address"]).strip())

    # Content & Requirements
    raw_desc = raw.get("responsibilities_original") or raw.get("content")
    flat["raw_description_text"] = strip_html_tags(raw_desc)
    flat["raw_requirements_text"] = strip_html_tags(raw.get("requirements_original"))

    # Benefits
    bens = raw.get("benefits_original") or raw.get("benefits_v2")
    if isinstance(bens, list):
        for b in bens:
            b_text = b.get("value") if isinstance(b, dict) else str(b)
            cleaned_b = strip_html_tags(b_text)
            if cleaned_b:
                flat["benefits_list"].append(cleaned_b)

    # Skills
    skills_arr = raw.get("skills_arr")
    if isinstance(skills_arr, list):
        flat["skills_list"] = [str(s) for s in skills_arr]
    elif raw.get("skills_str"):
        flat["skills_list"] = [s.strip() for s in str(raw.get("skills_str")).split(",") if s.strip()]


def _flatten_vieclam24h(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("title"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary"))
    flat["raw_experience_text"] = _clean_str(raw.get("experience_summary"))
    flat["raw_location_text"] = _clean_str(raw.get("location_summary"))
    flat["raw_deadline"] = _clean_str(raw.get("deadline"))
    flat["raw_working_time"] = _clean_str(raw.get("working_time"))

    # Currency & Visibility
    sal = flat.get("raw_salary_text") or ""
    if "triệu" in sal.lower() or "vnd" in sal.lower() or "đ" in sal.lower():
        flat["salary_currency"] = "VND"
    elif "$" in sal:
        flat["salary_currency"] = "USD"
    flat["is_salary_visible"] = True if any(c.isdigit() for c in sal) else False

    # Địa điểm làm việc
    w_addr = raw.get("working_address")
    if w_addr:
        flat["company_address"] = _clean_str(w_addr)
        flat["working_locations"].append(str(w_addr).strip())

    # Làm phẳng dict company
    comp = raw.get("company")
    if isinstance(comp, dict):
        flat["company_name"] = _clean_str(comp.get("name"))
        flat["company_scale"] = _clean_str(comp.get("size") or comp.get("scale"))
        if not flat["company_address"]:
            flat["company_address"] = _clean_str(comp.get("address"))
        flat["company_url"] = _clean_str(comp.get("website") or comp.get("url"))
    elif isinstance(comp, str):
        flat["company_name"] = _clean_str(comp)

    # General info
    gen = raw.get("general_info")
    if isinstance(gen, dict):
        flat["raw_seniority_text"] = _clean_str(gen.get("level"))
        flat["raw_posted_date"] = _clean_str(gen.get("posted_date"))
        flat["raw_headcount"] = _clean_str(gen.get("hiring_quantity"))
        flat["raw_employment_type"] = _clean_str(gen.get("working_type"))
        flat["raw_category_text"] = _clean_str(gen.get("industries"))
        flat["raw_education_text"] = _clean_str(gen.get("education") or gen.get("degree"))
        flat["raw_gender_text"] = _clean_str(gen.get("gender"))
        flat["raw_age_text"] = _clean_str(gen.get("age"))

        workplaces = gen.get("workplaces")
        if isinstance(workplaces, list):
            flat["working_locations"].extend([str(wp).strip() for wp in workplaces if str(wp).strip()])

    # Bullet lists
    desc = raw.get("description")
    if isinstance(desc, list):
        flat["raw_description_text"] = "\n".join(stitch_fragmented_bullets(desc))
    elif isinstance(desc, str):
        flat["raw_description_text"] = desc

    reqs = raw.get("requirements")
    if isinstance(reqs, list):
        flat["raw_requirements_text"] = "\n".join(stitch_fragmented_bullets(reqs))
    elif isinstance(reqs, str):
        flat["raw_requirements_text"] = reqs

    bens = raw.get("benefits")
    if isinstance(bens, list):
        flat["benefits_list"] = [str(b) for b in stitch_fragmented_bullets(bens)]
    elif isinstance(bens, str):
        flat["benefits_list"] = [bens]

    # Keywords
    kws = raw.get("keywords")
    if isinstance(kws, list):
        flat["skills_list"] = [str(k) for k in kws]
        flat["auxiliary_features"]["keywords"] = kws


def _flatten_vietnamworks(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("jobTitle") or raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("companyName") or (raw.get("company", {}).get("name") if isinstance(raw.get("company"), dict) else None))
    flat["company_logo_image"] = _clean_str(raw.get("companyLogo"))
    flat["company_url"] = _clean_str(raw.get("companyUrl"))
    flat["raw_posted_date"] = _clean_str(raw.get("createdOn") or raw.get("approvedOn") or raw.get("onlineOn"))
    flat["raw_updated_at"] = _clean_str(raw.get("lastUpdatedOn"))
    flat["raw_deadline"] = _clean_str(raw.get("expiredOn"))
    flat["raw_seniority_text"] = _clean_str(raw.get("jobLevelVI") or raw.get("jobLevel"))
    flat["raw_location_text"] = _clean_str(raw.get("location"))
    flat["company_address"] = _clean_str(raw.get("address"))
    flat["company_scale"] = _clean_str(raw.get("companySizeVI") or raw.get("companySize"))

    # Số lượng tuyển, độ tuổi, giới tính
    if raw.get("numberOfRecruits") is not None:
        flat["raw_headcount"] = str(raw.get("numberOfRecruits"))
    flat["raw_age_text"] = _clean_str(raw.get("rangeAge"))
    if raw.get("isShowGender") is not None:
        flat["raw_gender_text"] = _clean_str(raw.get("gender") or "Không hiển thị")

    # Bằng cấp
    deg_map = {
        1: "Trung học phổ thông",
        2: "Trung cấp",
        3: "Cao đẳng",
        4: "Cử nhân / Đại học",
        5: "Thạc sĩ",
        6: "Tiến sĩ",
        7: "Khác",
    }
    deg_id = raw.get("highestDegreeId")
    if deg_id in deg_map:
        flat["raw_education_text"] = deg_map[deg_id]
    elif deg_id is not None:
        flat["raw_education_text"] = str(deg_id)

    # Hình thức làm việc
    type_map = {1: "Toàn thời gian", 2: "Bán thời gian", 3: "Thực tập", 4: "Khác"}
    tw_id = raw.get("typeWorkingId")
    if tw_id in type_map:
        flat["raw_employment_type"] = type_map[tw_id]
    elif tw_id is not None:
        flat["raw_employment_type"] = str(tw_id)

    # Chi nhánh & Tọa độ GPS
    w_locs = raw.get("workingLocations")
    if isinstance(w_locs, list):
        for wl in w_locs:
            if isinstance(wl, dict):
                addr_s = wl.get("address") or wl.get("streetName")
                if addr_s:
                    flat["working_locations"].append(str(addr_s).strip())
                if not flat["geo_coordinates"] and "geoLoc" in wl and wl["geoLoc"]:
                    flat["geo_coordinates"] = wl["geoLoc"]
                if not flat["raw_location_text"] and wl.get("cityNameVI"):
                    flat["raw_location_text"] = _clean_str(wl.get("cityNameVI"))
            elif wl:
                flat["working_locations"].append(str(wl).strip())
    if flat["company_address"]:
        flat["working_locations"].append(flat["company_address"])

    # Ngành nghề
    industries = raw.get("industriesV3") or raw.get("industries")
    if isinstance(industries, list):
        names = []
        for ind in industries:
            if isinstance(ind, dict):
                n = ind.get("industryV3NameVI") or ind.get("industryV3Name") or ind.get("industryNameVI") or ind.get("industryName")
                if n:
                    names.append(n)
        if names:
            flat["raw_category_text"] = ", ".join(names)
            flat["company_industry"] = flat["raw_category_text"]

    # Kinh nghiệm
    exp_y = raw.get("yearsOfExperience")
    if exp_y is not None and int(exp_y) > 0:
        flat["raw_experience_text"] = f"{exp_y} năm"

    # Lương
    pretty_sal = raw.get("prettySalary") or raw.get("salary_raw")
    sal_min = raw.get("salaryMin", 0)
    sal_max = raw.get("salaryMax", 0)
    currency = raw.get("salaryCurrency", "VND")
    flat["salary_currency"] = currency
    flat["is_salary_visible"] = raw.get("isSalaryVisible")
    if sal_min > 0 or sal_max > 0:
        flat["raw_salary_text"] = f"{sal_min} - {sal_max} {currency}"
    elif pretty_sal:
        flat["raw_salary_text"] = _clean_str(pretty_sal)

    # Skills
    skills_obj = raw.get("skills")
    if isinstance(skills_obj, list):
        for s in skills_obj:
            if isinstance(s, dict) and s.get("skillName"):
                flat["skills_list"].append(str(s["skillName"]))
            elif isinstance(s, str):
                flat["skills_list"].append(s)

    # Benefits
    bens_obj = raw.get("benefits")
    if isinstance(bens_obj, list):
        for b in bens_obj:
            if isinstance(b, dict) and b.get("benefitValue"):
                flat["benefits_list"].append(str(b["benefitValue"]))
            elif isinstance(b, str):
                flat["benefits_list"].append(b)

    # Description & Requirements
    desc_list = raw.get("description_list")
    if isinstance(desc_list, list):
        flat["raw_description_text"] = "\n".join(desc_list)
    elif raw.get("jobDescription"):
        flat["raw_description_text"] = _clean_str(raw.get("jobDescription"))

    req_list = raw.get("requirements_list")
    if isinstance(req_list, list):
        flat["raw_requirements_text"] = "\n".join(req_list)
    elif raw.get("jobRequirement"):
        flat["raw_requirements_text"] = _clean_str(raw.get("jobRequirement"))

    # Auxiliary features
    for flag_k in ["isMobileHotJob", "isTopPriority", "isUrgentJob"]:
        if flag_k in raw:
            flat["auxiliary_features"][flag_k] = raw[flag_k]


def _flatten_generic(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("company"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary") or raw.get("salary_raw"))
    flat["raw_experience_text"] = _clean_str(raw.get("experience"))
    flat["raw_location_text"] = _clean_str(raw.get("location"))
    flat["raw_description_text"] = _clean_str(raw.get("description"))
