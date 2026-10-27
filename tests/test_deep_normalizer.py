"""
Unit tests for preprocessing/normalization/deep_normalizer.py
Verifies deep normalization of skills, saturday work, work mode, education,
age constraints, hierarchical locations, benefits cleaning, category list,
unicode, and complete elimination of raw_* fields in Golden Master.
"""

import pytest
from preprocessing.normalization.deep_normalizer import (
    clean_benefits_list,
    deep_normalize_record,
    extract_age_range,
    extract_cities_and_districts,
    extract_education,
    extract_hierarchical_locations,
    extract_normalized_skills,
    extract_saturday_work,
    extract_work_mode,
    normalize_company_categories,
    normalize_employment_type,
    normalize_text_unicode,
    to_curated_flat_record,
)


def test_normalize_text_unicode():
    raw = "Hà Nội\u200b  Việt Nam  "
    norm = normalize_text_unicode(raw)
    assert norm == "Hà Nội Việt Nam"
    assert normalize_text_unicode(None) == ""


def test_clean_benefits_list():
    raw_b = ["Phúc lợi Chế độ bảo hiểm Phụ cấp Chế độ thưởng", "Đào tạo nghiệp vụ"]
    cleaned = clean_benefits_list(raw_b)
    assert cleaned[0] == "Chế độ bảo hiểm Phụ cấp Chế độ thưởng"
    assert cleaned[1] == "Đào tạo nghiệp vụ"


def test_normalize_company_categories():
    assert normalize_company_categories("Ngân hàng , CNTT - Phần mềm") == ["Ngân hàng", "CNTT - Phần mềm"]
    assert normalize_company_categories(["Fintech", "E-commerce"]) == ["Fintech", "E-commerce"]
    assert normalize_company_categories(None) == []


def test_extract_hierarchical_locations():
    loc_sample = [
        "Hồ Chí Minh, Hà Nội",
        "Địa điểm làm việc Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM Hà Nội 89 Láng Hạ, Đống Đa, Hà Nội",
    ]
    cities, districts, detailed = extract_hierarchical_locations(loc_sample)
    assert "Hà Nội" in cities
    assert "Hồ Chí Minh" in cities
    assert "Quận 1" in districts
    assert "Đống Đa" in districts
    assert len(detailed) >= 2
    assert any(x["province"] == "Hồ Chí Minh" and x["district"] == "Quận 1" for x in detailed)
    assert any(x["province"] == "Hà Nội" and x["district"] == "Đống Đa" for x in detailed)


def test_extract_normalized_skills():
    raw_skills = [
        "IT - Phần mềm",
        "ReactJS",
        "Golang",
        "Kỹ năng giao tiếp",
        "Fintech",
        "Bán hàng / Kinh doanh",
        "NodeJS",
    ]
    res = extract_normalized_skills(raw_skills, text_corpus="Yêu cầu làm việc với Docker và Kubernetes")

    # Noise categories must be filtered
    assert "IT - Phần mềm" in res["portal_categories"]
    assert "IT - Phần mềm" not in res["hard_skills"]

    # Canonical mapping
    assert "React" in res["hard_skills"]
    assert "Go" in res["hard_skills"]
    assert "Node.js" in res["hard_skills"]
    # JD extraction
    assert "Docker" in res["hard_skills"]
    assert "Kubernetes" in res["hard_skills"]

    # Soft skills
    assert any("giao tiếp" in s.lower() for s in res["soft_skills"])

    # Domain skills
    assert "Fintech" in res["domain_skills"]


def test_extract_saturday_work():
    # Saturday off
    rec_off = {"raw_description_text": "Thời gian làm việc: Thứ 2 - Thứ 6, nghỉ Thứ Bảy và Chủ Nhật."}
    assert extract_saturday_work(rec_off) is False

    # Saturday work
    rec_work = {"raw_description_text": "Thời gian làm việc: Từ Thứ 2 đến Thứ 7 hàng tuần (8h30 - 17h30)."}
    assert extract_saturday_work(rec_work) is True

    # Undefined
    rec_unknown = {"raw_description_text": "Lương thỏa thuận theo năng lực."}
    assert extract_saturday_work(rec_unknown) is None


def test_extract_work_mode():
    assert extract_work_mode({"raw_work_mode": "Hybrid", "raw_description_text": "Linh hoạt 2 ngày WFH"}) == "Hybrid"
    assert extract_work_mode({"raw_description_text": "Chế độ làm việc: 100% Remote tại nhà"}) == "Remote"
    assert extract_work_mode({"raw_description_text": "Làm việc trực tiếp tại văn phòng Hà Nội"}) == "Onsite"


def test_extract_education():
    assert extract_education({"raw_education_text": "Đại học"}) == "Đại học"
    assert extract_education({"raw_description_text": "Yêu cầu tốt nghiệp Thạc sĩ chuyên ngành CNTT"}) == "Thạc sĩ / Cao học"
    assert extract_education({"raw_description_text": "Tốt nghiệp Cao đẳng CNTT trở lên"}) == "Cao đẳng"
    assert extract_education({"raw_description_text": "Không yêu cầu bằng cấp"}) == "Không yêu cầu"
    assert extract_education({"raw_description_text": "Công việc trao đổi khi phỏng vấn"}) == "Không đề cập"


def test_extract_age_range():
    min_age, max_age = extract_age_range({"raw_requirements_text": "Tuyển dụng nhân sự độ tuổi từ 22 đến 32 tuổi"})
    assert min_age == 22
    assert max_age == 32

    min_age2, max_age2 = extract_age_range({"raw_requirements_text": "Yêu cầu tuổi dưới 35 tuổi"})
    assert min_age2 is None
    assert max_age2 == 35


def test_extract_cities_and_districts():
    rec = {
        "raw_location_text": "Hồ Chí Minh: Quận 1, Tòa nhà Bitexco",
        "company_address": "Cầu Giấy, Hà Nội",
    }
    cities, districts = extract_cities_and_districts(rec)
    assert "Hồ Chí Minh" in cities
    assert "Hà Nội" in cities
    assert any("Quận 1" in d for d in districts)
    assert any("Cầu Giấy" in d for d in districts)


def test_normalize_employment_type():
    assert normalize_employment_type({"job_title": "Frontend Intern / Thực tập sinh"}) == "Internship"
    assert normalize_employment_type({"raw_employment_type": "Bán thời gian / Part-time"}) == "Part-time"
    assert normalize_employment_type({"job_title": "Cộng tác viên lập trình Freelance"}) == "Contract"
    assert normalize_employment_type({"raw_employment_type": "Toàn thời gian"}) == "Full-time"


def test_deep_normalize_record_zero_raw_in_golden():
    sample_record = {
        "job_id_global": "careerviet_35C8AEA1",
        "source_platform": "careerviet",
        "source_job_id": "35C8AEA1",
        "source_url": "https://careerviet.vn/vi/tim-viec-lam/hn-hcm-soc-engineer.35C8AEA1.html",
        "job_title": "[HN/HCM] SOC Engineer",
        "company_name": "Ngân Hàng TMCP Việt Nam Thịnh Vượng - VPBANK",
        "company_scale": None,
        "raw_category_text": "Ngân hàng , CNTT - Phần mềm",
        "raw_working_time": None,
        "raw_salary_text": "Cạnh tranh",
        "raw_employment_type": "Nhân viên chính thức",
        "raw_work_mode": None,
        "raw_experience_text": "4 - 5 Năm",
        "raw_seniority_text": "Nhân viên",
        "raw_education_text": "Đại học",
        "raw_headcount": None,
        "raw_age_text": "Tuổi từ 25 đến 35 tuổi",
        "raw_gender_text": None,
        "salary_min_vnd": 30000000,
        "salary_max_vnd": 50000000,
        "working_locations": [
            "Hồ Chí Minh, Hà Nội",
            "Địa điểm làm việc Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM Hà Nội 89 Láng Hạ, Đống Đa, Hà Nội",
        ],
        "benefits_list": [
            "Phúc lợi Chế độ bảo hiểm Phụ cấp Chế độ thưởng Chăm sóc sức khỏe Đào tạo Nghỉ phép năm"
        ],
        "raw_description_text": "Mô tả Công việc Giám sát an ninh 24/7 hệ thống CNTT. Thời gian: Thứ 2 - Thứ 6 (nghỉ thứ 7, cn).",
        "raw_requirements_text": "Yêu Cầu Công Việc Tốt nghiệp Đại học chuyên ngành về CNTT. Kỹ năng lập trình Python, Shell, PHP.",
        "skills_list": ["SOC Engineer", "Soc Analyst", "IT - Phần mềm"],
    }
    
    # Golden master normalize: keep_raw=False
    golden = deep_normalize_record(sample_record, keep_raw=False)

    # 1. 10 Nhóm Nghiệp vụ + 5 Định danh toàn cục (15 root keys chính xác)
    expected_root_keys = {
        "job_id_global", "source_platform", "source_job_id", "source_url", "crawled_at_iso",
        "job_info", "company", "location", "salary", "skills", "requirements", "jd_text", "date", "nlp_metadata", "governance",
    }
    assert set(golden.keys()) == expected_root_keys, f"Khóa root không khớp 10 nhóm chuẩn: {set(golden.keys()) ^ expected_root_keys}"

    # Khẳng định cấm trùng lặp legacy
    assert "extract_from_jd" not in golden, "Vẫn còn tồn tại extract_from_jd cũ!"
    assert "Extract_from_JD" not in golden, "Vẫn còn tồn tại alias Extract_from_JD cũ!"
    assert "standardized_districts" not in golden, "Vẫn còn trùng lặp standardized_districts ở root!"

    # 2. company.category_text is a list
    assert isinstance(golden["company"]["category_text"], list)
    assert "Ngân hàng" in golden["company"]["category_text"]
    assert "CNTT - Phần mềm" in golden["company"]["category_text"]

    # 3. location hierarchy
    assert "Hồ Chí Minh" in golden["location"]["cities_list"]
    assert "Hà Nội" in golden["location"]["cities_list"]
    assert any("Quận 1" in d for d in golden["location"]["districts_list"])
    assert any("Đống Đa" in d for d in golden["location"]["districts_list"])
    assert len(golden["location"]["detailed_locations"]) >= 2

    # 4. jd_text has description_text and requirements_text (no raw_ prefix)
    assert "description_text" in golden["jd_text"]
    assert "requirements_text" in golden["jd_text"]
    assert "raw_description_text" not in golden["jd_text"]
    assert "raw_requirements_text" not in golden["jd_text"]
    assert not golden["jd_text"]["benefits_text"][0].startswith("Phúc lợi")

    # 5. skills group at root level
    assert "skills" in golden
    assert isinstance(golden["skills"]["skills_list"], list)
    assert golden["skills"]["skills_count"] == len(golden["skills"]["skills_list"])
    assert "SOC Engineer" in golden["skills"]["skills_list"]

    # 6. requirements attributes
    req = golden["requirements"]
    assert req["is_saturday_work"] is False
    assert req["standardized_education"] == "Đại học"
    assert req["age_min"] == 25
    assert req["age_max"] == 35

    # 7. job_info attributes
    jinfo = golden["job_info"]
    assert jinfo["job_title"] == "SOC Engineer"
    assert jinfo["work_mode"] == "Onsite"
    assert jinfo["employment_type"] == "Full-time"
    assert jinfo["min_experience_years"] == 4.0

    # 8. to_curated_flat_record verification
    flat = to_curated_flat_record(golden)
    assert flat["job_id_global"] == "careerviet_35C8AEA1"
    assert flat["job_title"] == "SOC Engineer"
    assert flat["primary_city"] in ["Hồ Chí Minh", "Hà Nội"]
    assert flat["standardized_education"] == "Đại học"
    assert flat["is_saturday_work"] is False
    assert flat["salary_min_vnd"] == 30000000.0
    assert flat["salary_max_vnd"] == 50000000.0
