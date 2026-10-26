# -*- coding: utf-8 -*-
"""preprocessing.integration.json_flattener
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module ép phẳng JSON (JSON Flattening) đa nguồn cho VN-IT-Job-Mining.

Nguyên tắc:
  - Nhận vào payload thô (RawJobEnvelope hoặc dict) từ 8 nguồn.
  - Phân rã toàn bộ cấu trúc lồng nhau (nested dicts, array, detail-box, jsonld).
  - Ép phẳng về một dict duy nhất (Canonical Flat Dict) gồm 25 trường phẳng chuẩn.
  - Cột `skills_list`, `benefits_list`, `working_locations` lưu dưới dạng Python list[str].
  - BẢO TOÀN THÔNG TIN (Zero Information Loss): Mọi trường thô đều được giữ nguyên văn bản,
    nếu nguồn nào không có trường đó thì gán None (null) chứ không bỏ sót cột.
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

    Hỗ trợ cả trường hợp jobLocation là dict, list[dict], str hoặc None.

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


def flatten_raw_job_record(
    record_data: Dict[str, Any], source_fallback: Optional[str] = None
) -> Dict[str, Any]:
    """Ép phẳng một bản ghi JSON thô từ bất kỳ nguồn nào về cấu trúc phẳng 25 trường chuẩn.

    Args:
        record_data: Dict chứa raw envelope (`metadata` + `raw_payload`) hoặc `_meta` + `raw`.
        source_fallback: Tên sàn dự phòng nếu metadata không khai báo.

    Returns:
        Dict phẳng gồm 25 trường (Canonical Flat Record).
    """
    # 1. Tách metadata và raw_payload
    meta = record_data.get("metadata") or record_data.get("_meta") or {}
    raw = record_data.get("raw_payload") or record_data.get("raw") or {}

    source = (meta.get("source") or meta.get("source_platform") or source_fallback or "unknown").lower().strip()
    job_id = str(meta.get("job_id") or meta.get("source_job_id") or "")
    source_url = meta.get("source_url") or meta.get("url") or ""
    crawled_at = meta.get("scraped_at") or meta.get("crawled_at") or ""
    job_id_global = f"{source}_{job_id}"

    # Khởi tạo 25 trường phẳng chuẩn mực (Canonical 25 Flat Schema)
    flat: Dict[str, Any] = {
        # 1. Định danh & Nguồn gốc (5 trường)
        "job_id_global": job_id_global,
        "source_platform": source,
        "source_job_id": job_id,
        "source_url": source_url,
        "crawled_at": crawled_at,
        # 2. Thông tin cơ bản vị trí & Doanh nghiệp (5 trường)
        "job_title": None,
        "company_name": None,
        "company_address": None,
        "company_scale": None,
        "raw_category_text": None,
        # 3. Địa điểm & Thời gian làm việc (6 trường)
        "raw_location_text": None,
        "working_locations": [],
        "raw_posted_date": None,
        "raw_updated_at": None,
        "raw_deadline": None,
        "raw_working_time": None,
        # 4. Đãi ngộ & Hình thức công việc (3 trường)
        "raw_salary_text": None,
        "raw_employment_type": None,
        "raw_work_mode": None,
        # 5. Yêu cầu ứng viên & Chỉ tiêu (6 trường)
        "raw_experience_text": None,
        "raw_seniority_text": None,
        "raw_education_text": None,
        "raw_headcount": None,
        "raw_age_text": None,
        "raw_gender_text": None,
        # 6. Kỹ năng, Quyền lợi & Văn bản (4 trường)
        "skills_list": [],
        "benefits_list": [],
        "raw_description_text": None,
        "raw_requirements_text": None,
    }

    # 2. Xử lý logic ép phẳng đặc thù theo từng sàn
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

    # Đảm bảo các mảng danh sách được khử trùng lặp và làm sạch
    flat["skills_list"] = _dedup_list(flat.get("skills_list") or [])
    flat["benefits_list"] = _dedup_list(flat.get("benefits_list") or [])
    flat["working_locations"] = _dedup_list(flat.get("working_locations") or [])

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
    flat["raw_location_text"] = _clean_str(raw.get("work_location"))
    flat["raw_posted_date"] = _clean_str(raw.get("posted_at_raw"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary_display_text"))

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

    # Bóc tách JSON-LD để lấy baseSalary, employmentType, industry, jobLocation
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

        base_sal = jsonld.get("baseSalary")
        if isinstance(base_sal, dict):
            val_obj = base_sal.get("value")
            if isinstance(val_obj, dict):
                min_v = val_obj.get("minValue")
                max_v = val_obj.get("maxValue")
                curr = base_sal.get("currency", "USD")
                if min_v or max_v:
                    flat["raw_salary_text"] = f"{min_v} - {max_v} {curr}"
            elif isinstance(val_obj, (int, float, str)):
                curr = base_sal.get("currency", "USD")
                flat["raw_salary_text"] = f"{val_obj} {curr}"

        exp_req = jsonld.get("experienceRequirements")
        if isinstance(exp_req, dict) and exp_req.get("monthsOfExperience"):
            months = exp_req.get("monthsOfExperience")
            try:
                years = round(int(months) / 12, 1)
                if not flat["raw_experience_text"]:
                    flat["raw_experience_text"] = f"{years} năm ({months} tháng)"
            except (ValueError, TypeError):
                pass

        # Địa điểm an toàn từ JSON-LD
        r_loc, c_addr, w_locs = _extract_job_locations_from_jsonld(jsonld)
        if r_loc and not flat["raw_location_text"]:
            flat["raw_location_text"] = r_loc
        if c_addr and not flat["company_address"]:
            flat["company_address"] = c_addr
        flat["working_locations"].extend(w_locs)

        # Skills fallback từ jsonld
        if not flat["skills_list"] and jsonld.get("skills"):
            s_val = jsonld.get("skills")
            if isinstance(s_val, str):
                flat["skills_list"] = [s.strip() for s in s_val.split(",") if s.strip()]
            elif isinstance(s_val, list):
                flat["skills_list"] = [str(s) for s in s_val]

        # Benefits fallback từ jsonld (jobBenefits HTML)
        if not flat["benefits_list"] and jsonld.get("jobBenefits"):
            jb = strip_html_tags(str(jsonld.get("jobBenefits")))
            if jb:
                b_lines = [b.strip() for b in jb.splitlines() if b.strip()]
                flat["benefits_list"].extend(b_lines)

    # Skills
    skill_tags = raw.get("skill_tags") or raw.get("skills")
    if isinstance(skill_tags, list):
        flat["skills_list"].extend([str(s) for s in skill_tags])


def _flatten_jobsgo(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("company"))
    flat["company_address"] = _clean_str(raw.get("company_address"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary_raw"))
    flat["raw_experience_text"] = _clean_str(raw.get("experience"))
    flat["raw_location_text"] = _clean_str(raw.get("location"))
    flat["raw_deadline"] = _clean_str(raw.get("deadline_raw"))
    flat["raw_education_text"] = _clean_str(raw.get("education"))
    flat["raw_working_time"] = _clean_str(raw.get("working_time"))

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

    # Ép phẳng general_info
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

    # Company
    comp = raw.get("company")
    if isinstance(comp, dict):
        flat["company_name"] = _clean_str(comp.get("company_name") or comp.get("name") or raw.get("company-name"))
        flat["company_scale"] = _clean_str(comp.get("company_size") or comp.get("scale"))
    else:
        flat["company_name"] = _clean_str(raw.get("company") or raw.get("company-name"))

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

    # Clean HTML từ content và responsibilities (100% rác HTML được làm sạch)
    raw_desc = raw.get("responsibilities_original") or raw.get("content")
    flat["raw_description_text"] = strip_html_tags(raw_desc)
    flat["raw_requirements_text"] = strip_html_tags(raw.get("requirements_original"))

    # Benefits từ benefits_original (HTML mảng)
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

    # Địa điểm làm việc
    w_addr = raw.get("working_address")
    if w_addr:
        flat["company_address"] = _clean_str(w_addr)
        flat["working_locations"].append(str(w_addr).strip())

    # Làm phẳng dict company
    comp = raw.get("company")
    if isinstance(comp, dict):
        flat["company_name"] = _clean_str(comp.get("name"))
        flat["company_scale"] = _clean_str(comp.get("scale"))
        if not flat["company_address"]:
            flat["company_address"] = _clean_str(comp.get("address"))
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

    # Bullet lists có áp dụng Bullet Stitcher (chống đứt gãy câu)
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


def _flatten_vietnamworks(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("jobTitle") or raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("companyName") or (raw.get("company", {}).get("name") if isinstance(raw.get("company"), dict) else None))
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

    # Bằng cấp (highestDegreeId: 1: THPT, 2: Trung cấp, 3: Cao đẳng, 4: Cử nhân/Đại học, 5: Thạc sĩ, 6: Tiến sĩ)
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

    # Hình thức làm việc (typeWorkingId: 1: Toàn thời gian, 2: Bán thời gian, 3: Thực tập)
    type_map = {1: "Toàn thời gian", 2: "Bán thời gian", 3: "Thực tập", 4: "Khác"}
    tw_id = raw.get("typeWorkingId")
    if tw_id in type_map:
        flat["raw_employment_type"] = type_map[tw_id]
    elif tw_id is not None:
        flat["raw_employment_type"] = str(tw_id)

    # Chi nhánh / Working locations
    w_locs = raw.get("workingLocations")
    if isinstance(w_locs, list):
        for wl in w_locs:
            if isinstance(wl, dict):
                addr_s = wl.get("address") or wl.get("streetName")
                if addr_s:
                    flat["working_locations"].append(str(addr_s).strip())
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

    # Kinh nghiệm số học có sẵn
    exp_y = raw.get("yearsOfExperience")
    if exp_y is not None and int(exp_y) > 0:
        flat["raw_experience_text"] = f"{exp_y} năm"

    # Lương: VietnamWorks có cả numeric và prettySalary
    pretty_sal = raw.get("prettySalary") or raw.get("salary_raw")
    sal_min = raw.get("salaryMin", 0)
    sal_max = raw.get("salaryMax", 0)
    currency = raw.get("salaryCurrency", "VND")
    if sal_min > 0 or sal_max > 0:
        flat["raw_salary_text"] = f"{sal_min} - {sal_max} {currency}"
    elif pretty_sal:
        flat["raw_salary_text"] = _clean_str(pretty_sal)

    # Skills: danh sách dict {skillId, skillName, skillWeight}
    skills_obj = raw.get("skills")
    if isinstance(skills_obj, list):
        for s in skills_obj:
            if isinstance(s, dict) and s.get("skillName"):
                flat["skills_list"].append(str(s["skillName"]))
            elif isinstance(s, str):
                flat["skills_list"].append(s)

    # Benefits: danh sách dict {benefitId, benefitValue...}
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


def _flatten_generic(raw: Dict[str, Any], flat: Dict[str, Any]) -> None:
    flat["job_title"] = _clean_str(raw.get("title"))
    flat["company_name"] = _clean_str(raw.get("company"))
    flat["raw_salary_text"] = _clean_str(raw.get("salary") or raw.get("salary_raw"))
    flat["raw_experience_text"] = _clean_str(raw.get("experience"))
    flat["raw_location_text"] = _clean_str(raw.get("location"))
    flat["raw_description_text"] = _clean_str(raw.get("description"))
