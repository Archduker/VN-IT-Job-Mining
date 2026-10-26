import json
from datetime import date, datetime, timezone

import pytest

from preprocessing.normalization.text_cleaner import normalize_city
from preprocessing.transformation import (
    coerce_number,
    normalize_employment_type,
    normalize_work_mode,
    parse_date_to_iso,
    transform_job_record,
)
from preprocessing.transformation import run_transformation as transformation_runner
from preprocessing.transformation.run_transformation import _salary_range_records
from preprocessing.transformation.salary_parser import UniversalSalaryParser


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-26", "2026-10-26"),
        ("2026-10-26T18:30:00Z", "2026-10-26"),
        ("26/10/2026", "2026-10-26"),
        ("26-10-2026", "2026-10-26"),
        (date(2026, 10, 26), "2026-10-26"),
        (datetime(2026, 10, 26, tzinfo=timezone.utc), "2026-10-26"),
        ("2 days ago", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_date_to_iso(value, expected):
    assert parse_date_to_iso(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1.500.000", 1_500_000.0),
        ("1,5 năm", 1.5),
        ("1,234.56", 1234.56),
        ("1.234,56", 1234.56),
        ("Khoảng 3 năm", 3.0),
        ("Không yêu cầu", None),
        (float("inf"), None),
        (True, None),
    ],
)
def test_coerce_number(value, expected):
    assert coerce_number(value) == expected


@pytest.mark.parametrize(
    ("raw_type", "expected"),
    [
        ("FULL_TIME", "Full-time"),
        ("Toàn thời gian", "Full-time"),
        ("Part-time", "Part-time"),
        ("Thực tập sinh", "Internship"),
        ("Hợp đồng", "Contract"),
        ("unknown", None),
    ],
)
def test_normalize_employment_type(raw_type, expected):
    assert normalize_employment_type(raw_type) == expected


@pytest.mark.parametrize(
    ("raw_mode", "expected"),
    [
        ("Làm việc từ xa / Remote", "Remote"),
        ("Hybrid", "Hybrid"),
        ("Làm tại công ty / Onsite", "Onsite"),
        ("unknown", None),
    ],
)
def test_normalize_work_mode(raw_mode, expected):
    assert normalize_work_mode(raw_mode) == expected


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("Quận 1, TP.HCM", "Hồ Chí Minh"),
        ("HN", "Hà Nội"),
        ("DN", "Đà Nẵng"),
        ("John Smith", "John Smith"),
        ("Remote", "Remote"),
        ("  ", "Không xác định"),
    ],
)
def test_normalize_city_uses_city_aliases_without_substring_false_matches(location, expected):
    assert normalize_city(location) == expected


def test_transform_job_record_preserves_raw_and_adds_typed_fields():
    raw_record = {
        "raw_salary_text": "Thỏa thuận",
        "raw_description_text": "Vị trí Senior Engineer. Lương 20-25 triệu/tháng.",
        "raw_requirements_text": "Tối thiểu 2 năm kinh nghiệm.",
        "raw_posted_date": "26/10/2026",
        "raw_updated_at": "2026-10-27T10:00:00+07:00",
        "raw_deadline": "2026-11-30",
        "crawled_at": "2026-10-26T11:30:00Z",
        "raw_location_text": "Quận 1, TP.HCM",
        "working_locations": ["Quận 1, TP.HCM"],
        "raw_employment_type": "Full-time",
        "raw_work_mode": "Hybrid",
        "raw_experience_text": "6 tháng kinh nghiệm",
        "raw_headcount": "2 người",
        "skills_list": ["Python", "SQL"],
        "benefits_list": [],
    }

    transformed = transform_job_record(raw_record)

    assert transformed["salary_min_vnd"] == 20_000_000.0
    assert transformed["salary_max_vnd"] == 25_000_000.0
    assert transformed["salary_source"] == "jd_regex"
    assert transformed["posted_date"] == "2026-10-26"
    assert transformed["updated_date"] == "2026-10-27"
    assert transformed["deadline_date"] == "2026-11-30"
    assert transformed["crawled_at_iso"] == "2026-10-26"
    assert transformed["primary_city"] == "Hồ Chí Minh"
    assert transformed["employment_type"] == "Full-time"
    assert transformed["work_mode"] == "Hybrid"
    assert transformed["min_experience_years"] == 0.5
    assert transformed["headcount"] == 2
    assert transformed["skills_list"] == ["Python", "SQL"]
    assert transformed["raw_salary_text"] == raw_record["raw_salary_text"]
    assert transformed["raw_posted_date"] == raw_record["raw_posted_date"]
    assert raw_record["raw_location_text"] == "Quận 1, TP.HCM"


def test_transform_job_record_handles_missing_fields():
    transformed = transform_job_record({})

    assert transformed["salary_min_vnd"] is None
    assert transformed["posted_date"] is None
    assert transformed["primary_city"] == "Không xác định"
    assert transformed["employment_type"] is None
    assert transformed["work_mode"] is None
    assert transformed["min_experience_years"] is None
    assert transformed["headcount"] is None
    assert transformed["working_locations"] == []
    assert transformed["skills_list"] == []
    assert transformed["benefits_list"] == []


def test_sgd_salary_is_parsed_but_not_converted_to_vnd():
    parsed = UniversalSalaryParser.parse_text("1,500 - 2,000 SGD/month")

    assert parsed["salary_currency_original"] == "SGD"
    assert parsed["salary_min_original"] == 1500.0
    assert parsed["salary_max_original"] == 2000.0
    assert parsed["salary_min_vnd"] is None
    assert parsed["salary_max_vnd"] is None


def test_sgd_salary_converts_using_historical_rate_and_normalizes_pay_period():
    parsed = UniversalSalaryParser.parse_text(
        "1,500 - 2,000 SGD/year",
        sgd_to_vnd_rate=20_000.0,
    )

    assert parsed["salary_min_original"] == 1500.0
    assert parsed["salary_max_original"] == 2000.0
    assert parsed["salary_min_vnd"] == 2_500_000.0
    assert parsed["salary_max_vnd"] == (40_000_000 / 12)


def test_single_sgd_salary_keeps_thousands_separator_as_integer():
    parsed = UniversalSalaryParser.parse_text(
        "1,500 SGD/month",
        sgd_to_vnd_rate=20_000.0,
    )

    assert parsed["salary_min_original"] == 1500.0
    assert parsed["salary_max_original"] == 1500.0
    assert parsed["salary_min_vnd"] == 30_000_000.0
    assert parsed["salary_max_vnd"] == 30_000_000.0


def test_salary_report_filters_unknown_salary_and_sorts_by_vnd_range():
    records = [
        {"job_id_global": "job-30", "salary_min_vnd": 30_000_000, "salary_max_vnd": 40_000_000},
        {"job_id_global": "job-unknown", "salary_min_vnd": None, "salary_max_vnd": None},
        {"job_id_global": "job-10", "salary_min_vnd": 10_000_000, "salary_max_vnd": 20_000_000},
        {"job_id_global": "job-up-to", "salary_min_vnd": None, "salary_max_vnd": 25_000_000},
    ]

    salary_report = _salary_range_records(records)

    assert [record["job_id_global"] for record in salary_report] == [
        "job-10",
        "job-30",
        "job-up-to",
    ]
    assert len(records) == 4


def test_transform_marks_zero_salary_as_negotiable_without_changing_raw():
    record = {"raw_salary_text": "0"}

    transformed = transform_job_record(record)

    assert transformed["salary_min_vnd"] is None
    assert transformed["salary_max_vnd"] is None
    assert transformed["is_salary_negotiable_declared"] == 1
    assert transformed["raw_salary_text"] == "0"


def test_transform_marks_zero_range_salary_as_negotiable():
    transformed = transform_job_record({"raw_salary_text": "0 - 0 VND"})

    assert transformed["salary_min_vnd"] is None
    assert transformed["salary_max_vnd"] is None
    assert transformed["salary_source"] == "header_negotiable"
    assert transformed["is_salary_negotiable_declared"] == 1


def test_transform_runner_reads_integration_and_writes_outputs(tmp_path, monkeypatch):
    input_dir = tmp_path / "integration"
    output_dir = tmp_path / "transformation"
    reports_dir = tmp_path / "reports"
    source = "glints"
    source_input = input_dir / source / f"{source}_integrated_flat.json"
    source_input.parent.mkdir(parents=True)
    integration_records = [
        {
            "job_id_global": "glints_1",
            "raw_salary_text": "1,500 - 2,000 SGD/month",
            "raw_posted_date": "26/10/2026",
            "raw_location_text": "Remote",
        }
    ]
    source_input.write_text(
        json.dumps(integration_records, ensure_ascii=False),
        encoding="utf-8",
    )
    second_source_input = input_dir / "topcv" / "topcv_integrated_flat.json"
    second_source_input.parent.mkdir(parents=True)
    second_source_input.write_text(
        json.dumps([{"job_id_global": "topcv_2", "raw_salary_text": "20 triệu"}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        transformation_runner,
        "_load_sgd_usd_rates",
        lambda _start, _end: {"2026-10-23": 0.78},
    )

    report = transformation_runner.run_transformation(
        sources=(source, "topcv"),
        input_dir=input_dir,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )

    transformed_path = output_dir / source / f"{source}_transformed_flat.json"
    report_path = reports_dir / f"{source}_transformation_report.json"
    transformed_records = json.loads(transformed_path.read_text(encoding="utf-8"))
    source_report = json.loads(report_path.read_text(encoding="utf-8"))

    assert transformed_records[0]["job_id_global"] == "glints_1"
    assert transformed_records[0]["salary_min_original"] == 1500.0
    assert transformed_records[0]["salary_min_vnd"] == 1500 * 0.78 * 25_400
    assert transformed_records[0]["salary_currency"] == "SGD"
    assert transformed_records[0]["salary_fx_rate_date"] == "2026-10-23"
    assert transformed_records[0]["salary_fx_source"] == (
        "frankfurter_sgd_usd_x_fixed_project_usd_vnd"
    )
    assert transformed_records[0]["posted_date"] == "2026-10-26"
    assert source_report["step"] == "transformation"
    assert source_report["input_records"] == source_report["output_records"] == 1
    assert source_report["unconverted_non_vnd_records"] == 0
    assert source_report["sgd_converted_records"] == 1
    assert report["total_input_records"] == report["total_output_records"] == 2
    assert source_report["salary_range_report"]["records_with_numeric_vnd_salary"] == 1
    source_salary_report = json.loads(
        (
            output_dir / source / f"{source}_salary_sorted_vnd.json"
        ).read_text(encoding="utf-8")
    )
    assert [record["job_id_global"] for record in source_salary_report] == ["glints_1"]
    master_records = json.loads(
        (output_dir / "transformed_flat_all_sources.json").read_text(encoding="utf-8")
    )
    assert [record["job_id_global"] for record in master_records] == ["glints_1", "topcv_2"]
    master_salary_report = json.loads(
        (output_dir / "salary_sorted_all_sources_vnd.json").read_text(encoding="utf-8")
    )
    assert [record["job_id_global"] for record in master_salary_report] == [
        "topcv_2",
        "glints_1",
    ]
    assert (reports_dir / "master_transformation_report.json").is_file()
    assert json.loads(source_input.read_text(encoding="utf-8")) == integration_records


def test_salary_parser_dot_split_and_negative_patterns():
    from preprocessing.transformation.salary_parser import scan_salary_in_jd_text

    # 1. Số có dấu chấm hàng nghìn không bị gãy
    parsed = scan_salary_in_jd_text("Thu nhập: 15.000.000 - 20.000.000 VNĐ hàng tháng")
    assert parsed is not None
    assert parsed["salary_min_vnd"] == 15_000_000.0
    assert parsed["salary_max_vnd"] == 20_000_000.0

    # 2. Bộ lọc Negative Patterns chặn trích xuất nhầm từ phúc lợi
    assert scan_salary_in_jd_text("Hưởng lương tháng thứ 13 và thưởng Tết.") is None
    assert scan_salary_in_jd_text("Chính sách xét tăng lương 1-2 lần hàng năm.") is None
    assert scan_salary_in_jd_text("Thử việc hưởng 100% lương.") is None
    assert scan_salary_in_jd_text("Thưởng các dịp lễ 30/4 - 1/5 hấp dẫn.") is None
    assert scan_salary_in_jd_text("Hỗ trợ phụ cấp ăn trưa 1 triệu/tháng.") is None


def test_salary_parser_lower_bound_and_thousand_units():
    # Cận dưới
    p1 = UniversalSalaryParser.parse_text("Từ 15 triệu")
    assert p1["salary_min_vnd"] == 15_000_000.0
    assert p1["salary_max_vnd"] is None

    p2 = UniversalSalaryParser.parse_text("Trên 20 triệu")
    assert p2["salary_min_vnd"] == 20_000_000.0
    assert p2["salary_max_vnd"] is None

    p3 = UniversalSalaryParser.parse_text("Tối thiểu $1000")
    assert p3["salary_min_vnd"] == 25_400_000.0
    assert p3["salary_max_vnd"] is None

    # Đơn vị nghìn k
    p4 = UniversalSalaryParser.parse_text("500k - 800k")
    assert p4["salary_min_vnd"] == 500_000.0
    assert p4["salary_max_vnd"] == 800_000.0


def test_parse_salary_cascade_with_benefits():
    from preprocessing.transformation.salary_parser import parse_salary_cascade

    # Header là thỏa thuận, JD không có số, nhưng benefits có số
    res = parse_salary_cascade(
        raw_salary_text="Thỏa thuận",
        jd_text="Mô tả công việc chung, không có số lương.",
        benefits=["Lương cơ bản 15 - 20 triệu/tháng", "Đóng bảo hiểm đầy đủ"],
    )
    assert res["salary_min_vnd"] == 15_000_000.0
    assert res["salary_max_vnd"] == 20_000_000.0
    assert res["salary_source"] == "benefits_regex"


def test_parse_age_and_education_and_seniority():
    from preprocessing.transformation.record_transformer import (
        _parse_age_range,
        _parse_education_level,
        _parse_seniority_level,
        _parse_company_scale,
        _parse_saturday_work,
    )

    # Age
    assert _parse_age_range("22-32") == (22, 32)
    assert _parse_age_range("Tuổi 23 - 45") == (23, 45)
    assert _parse_age_range("Từ 30 tuổi trở xuống") == (None, 30)
    assert _parse_age_range("Từ 25 tuổi trở lên") == (25, None)

    # Education
    assert _parse_education_level("Cao Đẳng trở lên") == "Cao đẳng"
    assert _parse_education_level("bachelor degree") == "Cử nhân / Đại học"
    assert _parse_education_level("Thạc sĩ") == "Thạc sĩ / Cao học"
    assert _parse_education_level("Tiến sĩ") == "Tiến sĩ"
    assert _parse_education_level("Không yêu cầu") == "Không yêu cầu"
    assert _parse_education_level("0") is None

    # Seniority (Phương án 1)
    assert _parse_seniority_level("Trưởng nhóm", "Backend Developer") == "Senior / Lead"
    assert _parse_seniority_level(None, "Senior Java Developer") == "Senior / Lead"
    assert _parse_seniority_level("Giám Đốc và Cấp Cao Hơn", None) == "Director / Executive"
    assert _parse_seniority_level(None, "Fresher ReactJS") == "Intern / Fresher"
    assert _parse_seniority_level("Nhân viên", None) == "Junior / Middle"

    # Company scale
    assert _parse_company_scale("500-1000 nhân viên") == (500, 1000, "Large")
    assert _parse_company_scale("25-99") == (25, 99, "SME")
    assert _parse_company_scale("Hơn 50.000") == (50000, None, "Enterprise")

    # Saturday work
    assert _parse_saturday_work("Thứ 2 - Thứ 6 (từ 08:30 đến 17:30)") is False
    assert _parse_saturday_work("Thứ 2 - Thứ 6 + Thứ 7 cách tuần") is True
    assert _parse_saturday_work("Thứ 2 - Thứ 7") is True
    assert _parse_saturday_work("Nghỉ thứ 7 và Chủ Nhật") is False


def test_transform_job_record_comprehensive_extraction():
    raw_record = {
        "job_title": "Senior Python Developer",
        "raw_salary_text": "Thỏa thuận",
        "raw_description_text": "<div class='jd'><p>Phát triển hệ thống Microservices Python.</p></div>",
        "raw_requirements_text": "Tối thiểu 3 năm kinh nghiệm với Django và FastAPI.",
        "benefits_list": ["Lương thỏa thuận", "Bảo hiểm sức khỏe cao cấp", "Du lịch hàng năm"],
        "raw_posted_date": "20/10/2026",
        "raw_age_text": "24-35",
        "raw_education_text": "Đại học trở lên",
        "raw_seniority_text": None,
        "company_scale": "100-499 nhân viên",
        "raw_working_time": "Thứ 2 - Thứ 6 (08:30 - 17:30)",
        "raw_location_text": "Quận 1, TP.HCM",
        "skills_list": ["Python", "FastAPI", "Mê Linh", "không yêu cầu kinh nghiệm"],
    }

    transformed = transform_job_record(raw_record)

    # 1. Seniority fallback từ job_title
    assert transformed["standardized_seniority"] == "Senior / Lead"

    # 2. Tuổi
    assert transformed["age_min"] == 24
    assert transformed["age_max"] == 35

    # 3. Học vấn
    assert transformed["standardized_education"] == "Cử nhân / Đại học"

    # 4. Quy mô công ty
    assert transformed["company_size_min"] == 100
    assert transformed["company_size_max"] == 499
    assert transformed["company_scale_tier"] == "Medium"

    # 5. Làm thứ 7
    assert transformed["is_saturday_work"] is False

    # 6. Làm sạch skills & đếm counts
    assert "Mê Linh" not in transformed["skills_list"]
    assert "không yêu cầu kinh nghiệm" not in transformed["skills_list"]
    assert "Python" in transformed["skills_list"]
    assert transformed["skills_count"] == 2
    assert transformed["benefits_count"] == 3

    # 7. Text metrics & HTML cleaning
    assert "<div" not in transformed["jd_clean_text"]
    assert "<p" not in transformed["jd_clean_text"]
    assert transformed["word_count"] > 0
    assert transformed["is_stub_jd"] is True  # short test sample (<30 words)
    assert transformed["primary_language"] == "vi"

    # 8. Tiền đề Bước 3 & Bước 4
    assert transformed["is_salary_missing"] is True  # do header Thỏa thuận và JD không có số
    assert transformed["salary_mid_vnd"] is None
    assert transformed["missing_skills_flag"] is False
    assert transformed["missing_seniority_flag"] is False
    assert transformed["missing_education_flag"] is False
    assert transformed["seniority_rank"] == 3  # Senior / Lead = 3
    assert transformed["education_rank"] == 4  # Cử nhân / Đại học = 4
    assert transformed["genai_imputation_eligible"] is False  # stub JD


def test_benefits_salary_cascade_rejection_and_acceptance():
    from preprocessing.transformation.salary_parser import parse_salary_cascade

    # 1. Các bẫy phúc lợi phổ biến PHẢI BỊ LOẠI BỎ (không được gán làm lương)
    trap_cases = [
        ["13th-month salary", "Chế độ bảo hiểm"],
        ["Thưởng tháng lương thứ 13 và các gói phúc lợi đa dạng"],
        ["14 ngày nghỉ phép năm có hưởng lương, nghỉ chế độ có hưởng lương"],
        ["MB tự hào mang đến mức thu nhập bình quân 37,4 triệu VNĐ/tháng (Nguồn: BCTN 2024)"],
        ["Full salary in 2 months of probation"],
        ["Social insurance based on 100% salary"],
        ["Performance bonus of up to 4 months’ salary"],
        ["Salary review every 6 months"],
    ]
    for traps in trap_cases:
        res = parse_salary_cascade(
            raw_salary_text="Đăng nhập để xem mức lương",
            jd_text="Mô tả công việc không có lương",
            benefits=traps,
        )
        assert res["salary_min_vnd"] is None, f"Bẫy {traps} không được nhận là lương!"
        assert res["salary_max_vnd"] is None, f"Bẫy {traps} không được nhận là lương!"

    # 2. Dải lương thực thụ trong benefits PHẢI ĐƯỢC BÓC TÁCH CHÍNH XÁC
    valid_res1 = parse_salary_cascade(
        raw_salary_text="Đăng nhập để xem mức lương",
        jd_text="Công việc thú vị",
        benefits=["Competitive Package", "Salary (Gross): 35 - 45 millions", "Health insurance"],
    )
    assert valid_res1["salary_min_vnd"] == 35_000_000.0
    assert valid_res1["salary_max_vnd"] == 45_000_000.0
    assert valid_res1["salary_source"] == "benefits_regex"

    valid_res2 = parse_salary_cascade(
        raw_salary_text="Thương lượng",
        jd_text="Tuyển dụng lập trình viên",
        benefits=["Thu nhập cạnh tranh (up to 50M), đánh giá theo năng lực", "Team building"],
    )
    assert valid_res2["salary_max_vnd"] == 50_000_000.0
    assert valid_res2["salary_source"] == "benefits_regex"
    assert valid_res2["pay_period"] == "month"  # không bị nhầm year-end bonus thành annual
