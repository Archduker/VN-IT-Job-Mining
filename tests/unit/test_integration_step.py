# -*- coding: utf-8 -*-
"""Kiểm thử Bước 02 Integration (docs/preprocessing/spec/P2_integration.md).

Kiểm định:
- Output Contract: đúng 28 cột chuẩn (5 keys + 5 clean + 18 retained).
- Không có 6 trường cấm.
- I1: Làm phẳng đúng.
- I2: ITviec lấy datePosted JSON-LD.
- I3: TopDev lấy date và experience từ JSON-LD / published.
- I4: CareerViet / JobsGO không lấy tag SEO / occupation làm kỹ năng.
- I5: Chuỗi rỗng chuyển thành None.
- Bảo toàn số lượng bản ghi: rows_in == rows_out.
"""

import json
from pathlib import Path
import pandas as pd
import pytest

from preprocessing.integration import run as integration
from preprocessing.integration.json_flattener import flatten_raw_job_record
from preprocessing.common import step_report

PROHIBITED_FIELDS = (
    "company_scale",
    "raw_age_text",
    "raw_gender_text",
    "raw_updated_at",
    "raw_working_time",
    "raw_work_mode",
)


def _make_env(src, job_id, raw_payload, clean_meta=None):
    return {
        "metadata": {
            "job_id": job_id,
            "source": src,
            "source_url": f"https://example.com/{src}/{job_id}",
            "scraped_at": "2026-11-01T06:00:00+00:00",
            "clean": clean_meta or {
                "it_rule": "it",
                "it_rule_level": 1,
                "it_status": "it",
                "dedup_key": f"company|title|hanoi|2026-W44",
                "also_on": [],
            },
        },
        "raw_payload": raw_payload,
    }


def test_i2_itviec_date_posted():
    """I2: ITviec raw_posted_date lấy datePosted từ JSON-LD, không lấy chuỗi tương đối."""
    raw = {
        "title": "Senior Python Engineer",
        "posted_at_raw": "Đăng\n6 giờ trước",
        "job_posting_jsonld": {
            "datePosted": "2026-11-01T03:00:00+07:00",
            "validThrough": "2026-12-01",
        },
    }
    env = _make_env("itviec", "it_01", raw)
    flat = flatten_raw_job_record(env)
    assert flat["raw_posted_date"] == "2026-11-01T03:00:00+07:00"
    assert flat["raw_deadline"] == "2026-12-01"


def test_i3_topdev_date_and_experience():
    """I3: TopDev lấy raw_posted_date từ published.date / date_posted và raw_experience_text từ experienceRequirements."""
    raw = {
        "title": "Java Team Lead",
        "date_posted": "2026-10-28",
        "job_posting_jsonld": {
            "experienceRequirements": {
                "@type": "OccupationalExperienceRequirements",
                "monthsOfExperience": 24,
            }
        },
    }
    env = _make_env("topdev", "td_01", raw)
    flat = flatten_raw_job_record(env)
    assert flat["raw_posted_date"] == "2026-10-28"
    assert "24 months" in (flat["raw_experience_text"] or "")


def test_i4_careerviet_and_jobsgo_clean_skills():
    """I4: CareerViet không lấy job-tags (SEO tags), JobsGO không lấy occupations làm skills_list."""
    cv_raw = {
        "title": "Tester",
        "job-tags": ["Tuyển dụng Tester", "Việc làm IT", "Hà Nội Tuyển Dụng"],
    }
    cv_env = _make_env("careerviet", "cv_01", cv_raw)
    cv_flat = flatten_raw_job_record(cv_env)
    assert cv_flat["skills_list"] == []

    jg_raw = {
        "title": "DevOps",
        "occupations": ["IT - Phần mềm", "Viễn thông"],
    }
    jg_env = _make_env("jobsgo", "jg_01", jg_raw)
    jg_flat = flatten_raw_job_record(jg_env)
    assert jg_flat["skills_list"] == []


def test_i5_empty_values_to_none():
    """I5: Chuỗi rỗng, khoảng trắng, container rỗng phải chuyển thành None."""
    assert integration._clean_empty("") is None
    assert integration._clean_empty("   ") is None
    assert integration._clean_empty([]) is None
    assert integration._clean_empty({}) is None
    assert integration._clean_empty("Valid string") == "Valid string"
    assert integration._clean_empty(["Python"]) == ["Python"]


def test_integration_output_contract_and_conservation(tmp_path, monkeypatch):
    """Kiểm định Contract 28 cột, cấm 6 trường, và bảo toàn số lượng bản ghi."""
    test_in = tmp_path / "data" / "preprocessing" / "01_clean"
    test_out = tmp_path / "data" / "preprocessing" / "02_integration"
    test_rep = tmp_path / "reports" / "preprocessing"

    test_in.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(integration, "IN_DIR", test_in)
    monkeypatch.setattr(integration, "OUT_FILE", test_out / "all.parquet")
    monkeypatch.setattr(step_report, "REPORTS_ROOT", test_rep)

    # Tạo 3 bản ghi mẫu
    envs = [
        _make_env("glints", "g1", {"title": "Dev 1", "company": "Cty A", "salary": "15-20 triệu"}),
        _make_env("glints", "g2", {"title": "Dev 2", "company": "", "salary": "Thỏa thuận"}),
        _make_env("glints", "g3", {"title": "Dev 3", "company": "Cty B", "skills": "Python, Django"}),
    ]
    with (test_in / "glints.jsonl").open("w", encoding="utf-8") as f:
        for e in envs:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        f.write('{"hỏng": \n')  # I0: dòng JSON hỏng phải vào dropped, không biến mất

    # Chạy thật (dry_run=False)
    reports = integration.run(["glints"], dry_run=False)
    rep = reports["glints"]

    # 1. Kiểm tra bảo toàn dòng
    assert rep.data["input"]["rows"] == 4
    assert rep.data["output"]["rows"] == 3
    assert rep.data["dropped"] == [{"rule": "I0", "reason": "dòng không đọc được JSON, cần xem lại file 01_clean", "rows": 1}]
    assert rep.data["checks"]["rows_conserved"] is True

    # 2. Đọc file parquet lên kiểm tra Contract
    parquet_path = test_out / "all.parquet"
    assert parquet_path.exists()
    df = pd.read_parquet(parquet_path)
    assert len(df) == 3

    # Assert đúng 28 cột
    assert list(df.columns) == list(integration.ALL_OUTPUT_COLUMNS)
    assert len(df.columns) == 28

    # Assert không có 6 trường cấm
    for bad_col in PROHIBITED_FIELDS:
        assert bad_col not in df.columns

    # Assert company rỗng ở g2 đã chuyển thành None/NaN (I5)
    row_g2 = df[df["source_job_id"] == "g2"].iloc[0]
    assert pd.isna(row_g2["company_name"])
