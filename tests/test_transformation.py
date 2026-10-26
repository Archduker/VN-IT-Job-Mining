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
