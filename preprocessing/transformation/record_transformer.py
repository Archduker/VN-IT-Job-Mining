"""Chuyển đổi bản ghi phẳng sang các trường dữ liệu có kiểu và định dạng chuẩn."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from preprocessing.transformation.bullet_stitcher import stitch_fragmented_bullets
from preprocessing.transformation.html_cleaner import strip_html_tags
from preprocessing.transformation.salary_parser import parse_salary_cascade
from preprocessing.transformation.text_metrics import calculate_text_metrics

_NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:[.,]\d+)*")


def parse_date_to_iso(value: Any) -> str | None:
    """Chuyển ngày hoặc chuỗi ngày phổ biến về YYYY-MM-DD; giá trị không rõ trả về None."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, bool):
        return None

    text = str(value).strip()
    if not text:
        return None

    iso_text = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        return datetime.fromisoformat(iso_text).date().isoformat()
    except ValueError:
        pass

    for date_format in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue

    return None


def coerce_number(value: Any) -> float | None:
    """Đọc số từ giá trị số hoặc chuỗi có dấu phân cách hàng nghìn/thập phân."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = float(value)
        return number if math.isfinite(number) else None

    match = _NUMBER_PATTERN.search(str(value).strip())
    if not match:
        return None

    number_text = match.group()
    if "," in number_text and "." in number_text:
        decimal_separator = "," if number_text.rfind(",") > number_text.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        number_text = number_text.replace(thousands_separator, "")
        number_text = number_text.replace(decimal_separator, ".")
    elif "," in number_text or "." in number_text:
        separator = "," if "," in number_text else "."
        parts = number_text.split(separator)
        if (
            len(parts) > 1
            and len(parts[0].lstrip("+-")) <= 3
            and all(len(part) == 3 for part in parts[1:])
        ):
            number_text = "".join(parts)
        else:
            number_text = parts[0] + "." + "".join(parts[1:])

    try:
        number = float(number_text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _parse_experience_years(value: Any) -> float | None:
    years = coerce_number(value)
    if years is None:
        return None
    if isinstance(value, str) and any(unit in value.lower() for unit in ("tháng", "month")):
        return years / 12.0
    return years


def _parse_headcount(value: Any) -> int | None:
    if isinstance(value, str) and re.search(r"\d\s*[-–—]\s*\d", value):
        return None
    count = coerce_number(value)
    if count is None or not count.is_integer():
        return None
    return int(count)


def _normalize_list(value: Any) -> list[str]:
    values = value if isinstance(value, list | tuple | set) else [value]
    return [str(item).strip() for item in values if item is not None and str(item).strip()]


def normalize_employment_type(value: Any) -> str | None:
    """Chuẩn hóa hình thức tuyển dụng về các nhãn phổ biến, không suy đoán giá trị lạ."""
    if value is None:
        return None
    text = re.sub(r"[_-]+", " ", str(value)).strip().lower()
    if not text:
        return None

    if any(term in text for term in ("full time", "toàn thời gian", "toàn thời")):
        return "Full-time"
    if any(term in text for term in ("part time", "bán thời gian", "bán thời")):
        return "Part-time"
    if any(term in text for term in ("intern", "thực tập", "trainee")):
        return "Internship"
    if any(term in text for term in ("contract", "hợp đồng", "freelance", "cộng tác viên")):
        return "Contract"
    if any(term in text for term in ("temporary", "thời vụ")):
        return "Temporary"
    return None


def normalize_work_mode(value: Any) -> str | None:
    """Chuẩn hóa hình thức làm việc tại văn phòng, từ xa hoặc kết hợp."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if any(term in text for term in ("hybrid", "kết hợp", "linh hoạt")):
        return "Hybrid"
    if any(term in text for term in ("remote", "từ xa", "work from home", "làm tại nhà", "online")):
        return "Remote"
    if any(term in text for term in ("onsite", "on-site", "tại văn phòng", "tại công ty", "trực tiếp")):
        return "Onsite"
    return None


def _parse_age_range(value: Any) -> tuple[int | None, int | None]:
    """Bóc tách độ tuổi tuyển dụng tối thiểu và tối đa từ chuỗi văn bản."""
    if not value or isinstance(value, bool):
        return None, None
    text = str(value).strip().lower()
    if not text:
        return None, None

    # Dưới X tuổi / từ X tuổi trở xuống / <= X
    below_m = re.search(r"(?:dưới|từ\s*(\d+)\s*tuổi\s*trở\s*xuống|<|<=)\s*(\d+)?", text)
    if below_m:
        age_str = below_m.group(1) or below_m.group(2)
        if age_str and age_str.isdigit():
            return None, int(age_str)

    # Từ X tuổi trở lên / trên X tuổi / >= X
    above_m = re.search(r"(?:trên|từ)\s*(\d+)\s*(?:tuổi)?\s*(?:trở\s*lên|>|>=)", text)
    if above_m:
        return int(above_m.group(1)), None

    # Dải tuổi "22-32", "23 - 45", "18-35"
    range_m = re.search(r"(\d{2})\s*[-–—tođến]+\s*(\d{2})", text)
    if range_m:
        a1, a2 = int(range_m.group(1)), int(range_m.group(2))
        if 16 <= a1 <= 70 and 16 <= a2 <= 70:
            return (a1, a2) if a1 <= a2 else (a2, a1)

    return None, None


def _parse_education_level(value: Any) -> str | None:
    """Chuẩn hóa trình độ học vấn về các bậc quy chuẩn."""
    if not value or isinstance(value, bool):
        return None
    text = str(value).strip().lower()
    if not text or text in ("0", "none", "null", "không hiển thị"):
        return None
    if "không yêu cầu" in text:
        return "Không yêu cầu"
    if any(term in text for term in ("tiến sĩ", "phd", "doctorate")):
        return "Tiến sĩ"
    if any(term in text for term in ("thạc sĩ", "cao học", "master")):
        return "Thạc sĩ / Cao học"
    if any(term in text for term in ("đại học", "cử nhân", "bachelor", "kỹ sư")):
        return "Cử nhân / Đại học"
    if any(term in text for term in ("cao đẳng", "associate")):
        return "Cao đẳng"
    if any(term in text for term in ("trung cấp", "nghề", "vocational", "sơ cấp", "chứng chỉ", "certificate")):
        return "Trung cấp / Nghề"
    if any(term in text for term in ("phổ thông", "cấp 3", "high school")):
        return "Trung học phổ thông"
    return None


def _parse_seniority_level(raw_seniority: Any, job_title: Any = None) -> str | None:
    """Chuẩn hóa cấp bậc chuyên môn (Phương án 1: ưu tiên raw_seniority_text, fallback job_title)."""
    text = str(raw_seniority or "").strip().lower()
    title_text = str(job_title or "").strip().lower()

    candidates = [text, title_text] if text else [title_text]

    for s in candidates:
        if not s:
            continue
        if any(term in s for term in ("giám đốc", "director", "cấp cao hơn", "executive", "head of", "c-level", "chief", "cto", "cio", "ceo")):
            return "Director / Executive"
        if any(term in s for term in ("trưởng phòng", "phó phòng", "manager", "quản lý")):
            return "Manager"
        if any(term in s for term in ("trưởng nhóm", "team lead", "tech lead", "lead", "leader", "senior", "chuyên gia", "chuyên viên chính", "sr.", "sr ")):
            return "Senior / Lead"
        if any(term in s for term in ("middle", "mid-level", "nhân viên", "chuyên viên", "cộng tác viên", "junior", "jr.", "jr ")):
            return "Junior / Middle"
        if any(term in s for term in ("thực tập", "intern", "trainee", "fresher", "mới tốt nghiệp", "sinh viên")):
            return "Intern / Fresher"

    return None


def _parse_company_scale(value: Any) -> tuple[int | None, int | None, str | None]:
    """Bóc tách quy mô công ty: số nhân viên min, max và phân tầng quy mô."""
    if not value or isinstance(value, bool):
        return None, None, None
    text = str(value).strip().lower().replace(".", "").replace(",", "")
    if not text:
        return None, None, None

    range_m = re.search(r"(\d+)\s*[-–—tođến]+\s*(\d+)", text)
    if range_m:
        s_min, s_max = int(range_m.group(1)), int(range_m.group(2))
    else:
        plus_m = re.search(r"(?:hơn|>|>=)?\s*(\d+)\s*(?:\+|nhân\s*viên)?", text)
        if plus_m and ("hơn" in text or "+" in text):
            s_min, s_max = int(plus_m.group(1)), None
        else:
            single_m = re.search(r"\d+", text)
            if single_m:
                s_min, s_max = int(single_m.group()), None
            else:
                return None, None, None

    val_check = s_max if s_max is not None else s_min
    if val_check is not None:
        if val_check < 25:
            tier = "Startup"
        elif val_check < 100:
            tier = "SME"
        elif val_check < 500:
            tier = "Medium"
        elif val_check <= 1000:
            tier = "Large"
        else:
            tier = "Enterprise"
    else:
        tier = None

    return s_min, s_max, tier


def _parse_saturday_work(value: Any) -> bool | None:
    """Xác định có phải làm việc vào thứ 7 hay không."""
    if not value or isinstance(value, bool):
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if any(neg in text for neg in ("không làm thứ 7", "nghỉ thứ 7", "không làm thứ bảy", "nghỉ thứ bảy", "nghỉ t7")):
        return False
    if any(term in text for term in ("thứ 7", "thứ bảy", "saturday", "t7")):
        return True
    if any(term in text for term in ("thứ 2 - thứ 6", "thứ 2 đến thứ 6", "t2 - t6", "t2 đến t6", "monday to friday", "mon - fri")):
        return False
    return None


def _clean_skills_list(skills: list[str], city: str | None = None) -> list[str]:
    """Lọc bỏ các nhãn địa danh hoặc 'kinh nghiệm' bị gom nhầm vào skills_list."""
    cleaned: list[str] = []
    stop_terms = {"không yêu cầu kinh nghiệm", "kinh nghiệm", "mê linh", "huyện mê linh"}
    city_lower = city.lower() if city else ""
    for s in skills:
        item = str(s).strip()
        item_lower = item.lower()
        if not item or item_lower in stop_terms:
            continue
        if city_lower and item_lower == city_lower:
            continue
        cleaned.append(item)
    return cleaned


def transform_job_record(
    record: Mapping[str, Any],
    *,
    sgd_to_vnd_rate: float | None = None,
    sgd_fx_rate_date: str | None = None,
) -> dict[str, Any]:
    """Bổ sung các trường chuẩn hóa mà không ghi đè hoặc loại bỏ dữ liệu raw."""
    transformed = dict(record)

    # 1. Làm sạch HTML và nối bullet cho JD text
    raw_desc = record.get("raw_description_text")
    raw_req = record.get("raw_requirements_text")
    clean_desc = strip_html_tags(raw_desc) or ""
    clean_req = strip_html_tags(raw_req) or ""
    if clean_desc and ("•" in clean_desc or "\n" in clean_desc):
        stitched = stitch_fragmented_bullets(clean_desc)
        clean_desc = "\n".join(stitched) if stitched else clean_desc

    jd_text = " ".join(part for part in (clean_desc, clean_req) if part).strip()

    # 2. Bóc tách dải lương Cascade đa tầng (Header -> JD -> Benefits)
    benefits_raw = record.get("benefits_list")
    salary_result = parse_salary_cascade(
        record.get("raw_salary_text"), jd_text, sgd_to_vnd_rate, benefits=benefits_raw
    )
    transformed.update(salary_result)
    transformed["salary_currency"] = salary_result["salary_currency_original"]
    if salary_result["salary_currency_original"] == "SGD":
        transformed["salary_fx_rate_to_vnd"] = sgd_to_vnd_rate
        transformed["salary_fx_rate_date"] = sgd_fx_rate_date
        transformed["salary_fx_source"] = (
            "frankfurter_sgd_usd_x_fixed_project_usd_vnd"
            if sgd_to_vnd_rate is not None
            else None
        )
    elif salary_result["salary_currency_original"] == "USD":
        transformed["salary_fx_rate_to_vnd"] = 25_400.0
        transformed["salary_fx_rate_date"] = None
        transformed["salary_fx_source"] = "fixed_project_usd_vnd"
    else:
        transformed["salary_fx_rate_to_vnd"] = 1.0
        transformed["salary_fx_rate_date"] = None
        transformed["salary_fx_source"] = "identity_vnd"
    raw_salary = record.get("raw_salary_text")
    salary_text = str(raw_salary or "").strip()
    declares_zero_salary = bool(
        salary_text
        and re.fullmatch(
            r"0+(?:[.,]0+)?(?:\s*[-–—]\s*0+(?:[.,]0+)?)?"
            r"(?:\s*(?:triệu|tr|m|trđ|vnd|vnđ|₫|usd|sgd|\$))?",
            salary_text,
            re.IGNORECASE,
        )
    )
    if declares_zero_salary:
        transformed["salary_min_vnd"] = None
        transformed["salary_max_vnd"] = None
        transformed["salary_min_original"] = None
        transformed["salary_max_original"] = None
        transformed["is_negotiable"] = True
        transformed["salary_source"] = "header_negotiable"
    transformed["is_salary_negotiable_declared"] = int(
        bool(salary_text and salary_result.get("is_negotiable")) or declares_zero_salary
    )

    # 3. Chuẩn hóa ngày tháng ISO 8601
    for raw_field, output_field in (
        ("raw_posted_date", "posted_date"),
        ("raw_updated_at", "updated_date"),
        ("raw_deadline", "deadline_date"),
        ("crawled_at", "crawled_at_iso"),
    ):
        transformed[output_field] = parse_date_to_iso(record.get(raw_field))

    # 4. Chuẩn hóa địa điểm
    location = record.get("raw_location_text")
    if not location:
        locations = _normalize_list(record.get("working_locations"))
        location = locations[0] if locations else None
    from preprocessing.normalization.text_cleaner import normalize_city
    transformed["primary_city"] = normalize_city(location)

    # 5. Chuẩn hóa hình thức & kinh nghiệm
    transformed["employment_type"] = normalize_employment_type(
        record.get("raw_employment_type")
    )
    transformed["work_mode"] = normalize_work_mode(record.get("raw_work_mode"))
    transformed["min_experience_years"] = _parse_experience_years(
        record.get("raw_experience_text")
    )
    transformed["headcount"] = _parse_headcount(record.get("raw_headcount"))

    # 6. Các trường bóc tách mới (Age, Education, Seniority, Company Scale, Saturday)
    metrics = calculate_text_metrics(jd_text)
    transformed["jd_clean_text"] = jd_text if jd_text else None
    transformed["word_count"] = metrics["word_count"]
    transformed["char_count"] = metrics["char_count"]
    transformed["is_stub_jd"] = metrics["is_stub_jd"]
    transformed["primary_language"] = metrics["primary_language"]

    age_min, age_max = _parse_age_range(record.get("raw_age_text"))
    transformed["age_min"] = age_min
    transformed["age_max"] = age_max

    transformed["standardized_education"] = _parse_education_level(
        record.get("raw_education_text")
    )
    transformed["standardized_seniority"] = _parse_seniority_level(
        record.get("raw_seniority_text"), record.get("job_title")
    )

    comp_min, comp_max, comp_tier = _parse_company_scale(record.get("company_scale"))
    transformed["company_size_min"] = comp_min
    transformed["company_size_max"] = comp_max
    transformed["company_scale_tier"] = comp_tier

    transformed["is_saturday_work"] = _parse_saturday_work(record.get("raw_working_time"))

    # 7. Mảng danh sách chuẩn hóa
    transformed["working_locations"] = _normalize_list(record.get("working_locations"))

    norm_skills = _normalize_list(record.get("skills_list"))
    transformed["skills_list"] = _clean_skills_list(norm_skills, transformed["primary_city"])
    transformed["skills_count"] = len(transformed["skills_list"])

    transformed["benefits_list"] = _normalize_list(record.get("benefits_list"))
    transformed["benefits_count"] = len(transformed["benefits_list"])

    # 8. Tiền đề cho Bước 3 & Bước 4 (Feature Engineering Precursors & Imputation Flags)
    s_min = transformed.get("salary_min_vnd")
    s_max = transformed.get("salary_max_vnd")
    if s_min is not None and s_max is not None:
        transformed["salary_mid_vnd"] = round((s_min + s_max) / 2.0, 2)
    elif s_min is not None:
        transformed["salary_mid_vnd"] = float(s_min)
    elif s_max is not None:
        transformed["salary_mid_vnd"] = float(s_max)
    else:
        transformed["salary_mid_vnd"] = None

    transformed["is_salary_missing"] = bool(s_min is None and s_max is None)
    transformed["missing_skills_flag"] = bool(transformed["skills_count"] == 0)
    transformed["missing_seniority_flag"] = bool(transformed["standardized_seniority"] is None)
    transformed["missing_education_flag"] = bool(transformed["standardized_education"] is None)
    transformed["genai_imputation_eligible"] = bool(
        not transformed["is_stub_jd"] and transformed["word_count"] >= 30
    )

    seniority_ranks = {
        "Intern / Fresher": 1,
        "Junior / Middle": 2,
        "Senior / Lead": 3,
        "Manager": 4,
        "Director / Executive": 5,
    }
    transformed["seniority_rank"] = seniority_ranks.get(transformed["standardized_seniority"])

    education_ranks = {
        "Không yêu cầu": 0,
        "Trung học phổ thông": 1,
        "Trung cấp / Nghề": 2,
        "Cao đẳng": 3,
        "Cử nhân / Đại học": 4,
        "Thạc sĩ / Cao học": 5,
        "Tiến sĩ": 6,
    }
    transformed["education_rank"] = education_ranks.get(transformed["standardized_education"])

    return transformed


def to_flat_record(grouped: Mapping[str, Any]) -> dict[str, Any]:
    """Trải phẳng cấu trúc nhóm về dạng phẳng 1 tầng."""
    flat: dict[str, Any] = {
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
    for k, v in grouped.items():
        if k not in ["company", "location", "skills", "jd", "salary", "date", "extract", "other"] and k not in flat:
            flat[k] = v
    return flat


def is_empty_stub_record(record: Mapping[str, Any]) -> bool:
    """Kiểm tra bản ghi có phải là bài đăng rỗng/vô nghĩa (stub) cần loại bỏ không."""
    jd_group = record.get("jd") if isinstance(record.get("jd"), dict) else record
    other_group = record.get("other") if isinstance(record.get("other"), dict) else record

    title = str(jd_group.get("job_title") or record.get("job_title") or "").strip()
    if not title:
        return True

    desc = str(jd_group.get("raw_description_text") or record.get("raw_description_text") or "").strip()
    if not desc:
        is_banner = (
            other_group.get("is_content_image") is True
            or record.get("is_content_image") is True
        )
        if is_banner:
            return False  # Bảo vệ bài đăng ảnh banner
        return True

    return False


def extract_raw_salary_bounds(
    salary_text: str | None,
    raw_min: Any | None = None,
    raw_max: Any | None = None,
) -> tuple[float | None, float | None]:
    """Trích xuất 2 con số thô min và max từ chuỗi lương hoặc từ số có sẵn."""
    from preprocessing.transformation.salary_parser import UniversalSalaryParser

    try:
        if raw_min is not None and float(raw_min) > 0:
            s_min = float(raw_min)
            s_max = float(raw_max) if (raw_max is not None and float(raw_max) > 0) else None
            return s_min, s_max
        if raw_max is not None and float(raw_max) > 0:
            return None, float(raw_max)
    except (ValueError, TypeError):
        pass

    if not salary_text or not str(salary_text).strip():
        return None, None

    res = UniversalSalaryParser.parse_text(str(salary_text).strip())
    s_min = res.get("salary_min_original")
    s_max = res.get("salary_max_original")
    return s_min, s_max
