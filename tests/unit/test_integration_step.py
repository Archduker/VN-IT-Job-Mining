# -*- coding: utf-8 -*-
"""Kiểm thử Bước 02 Integration (docs/spec/preprocessing/spec/P2_integration.md).

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
    test_in = tmp_path / "data" / "preprocessing" / "01b_deduplication"
    test_out = tmp_path / "data" / "preprocessing" / "02_integration"
    test_rep = tmp_path / "reports" / "preprocessing"

    test_in.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(integration, "IN_DIR", test_in)
    monkeypatch.setattr(integration, "OUT_DIR", test_out)
    monkeypatch.setattr(integration, "OUT_FILE", test_out / "all.parquet")
    monkeypatch.setattr(integration, "REJECTED_DIR", tmp_path / "rejected")
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
    # I0: dòng JSON hỏng bị drop, vào rejected, không dựng dòng giả
    assert rep.data["output"]["rows"] == 3
    assert [d for d in rep.data["dropped"] if d["rows"]] == [{"rule": "I0", "reason": "JSON_INVALID", "rows": 1}]
    assert rep.data["checks"]["rows_conserved"] is True
    rej = [json.loads(x) for x in (tmp_path / "rejected" / "glints.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rej) == 1 and rej[0]["rule"] == "I0" and rej[0]["line_no"] == 4
    assert "raw_line" not in json.dumps(rep.data, ensure_ascii=False)

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


def _run_one(tmp_path, monkeypatch, lines, src="glints"):
    d_in = tmp_path / "in"
    d_in.mkdir()
    monkeypatch.setattr(integration, "IN_DIR", d_in)
    monkeypatch.setattr(integration, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(integration, "OUT_FILE", tmp_path / "out" / "all.parquet")
    monkeypatch.setattr(integration, "REJECTED_DIR", tmp_path / "rejected")
    monkeypatch.setattr(step_report, "REPORTS_ROOT", tmp_path / "rep")
    (d_in / f"{src}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return integration.run([src], dry_run=False)[src], tmp_path / "rejected" / f"{src}.jsonl"


def test_i6_missing_crawled_at_and_empty_title_rejected(tmp_path, monkeypatch):
    ok = _make_env("glints", "g1", {"title": "Dev 1"})
    no_date = _make_env("glints", "g2", {"title": "Dev 2"})
    del no_date["metadata"]["scraped_at"]
    no_title = _make_env("glints", "g3", {"title": ""})
    rep, rej = _run_one(tmp_path, monkeypatch, [json.dumps(e) for e in (ok, no_date, no_title)])
    assert rep.data["output"]["rows"] == 1
    reasons = sorted(json.loads(x)["reason"] for x in rej.read_text(encoding="utf-8").splitlines())
    assert reasons == ["SCHEMA: crawled_at", "SCHEMA: job_title"]
    assert rep.data["checks"]["rows_conserved"] is True


def test_i7_flatten_error_rejected_not_swallowed(tmp_path, monkeypatch):
    def boom(raw, flat):
        raise KeyError("x")
    from preprocessing.integration import json_flattener as jf
    monkeypatch.setattr(jf, "_flatten_glints", boom)
    rep, rej = _run_one(tmp_path, monkeypatch, [json.dumps(_make_env("glints", "g1", {"title": "Dev"}))])
    assert rep.data["output"]["rows"] == 0
    assert json.loads(rej.read_text(encoding="utf-8"))["reason"] == "FLATTEN_ERROR: KeyError"
    # chế độ mặc định (các nơi gọi khác) vẫn rơi về generic
    assert flatten_raw_job_record(_make_env("glints", "g1", {"title": "Dev"}))["job_title"] == "Dev"


def test_fallback_id_deterministic_across_hash_seeds():
    import os, subprocess, sys
    code = ("from preprocessing.integration.json_flattener import flatten_raw_job_record as f;"
            "print(f({'metadata':{'source':'glints','source_url':'https://glints.com/vn/opportunities/jobs/x'},'raw_payload':{'title':'t'}})['job_id_global'])")
    outs = {subprocess.run([sys.executable, "-c", code], cwd=ROOT_DIR, capture_output=True, text=True,
                           env={**os.environ, "PYTHONHASHSEED": s}).stdout for s in ("1", "2")}
    assert len(outs) == 1 and next(iter(outs)).startswith("glints_")


ROOT_DIR = Path(__file__).resolve().parents[2]
