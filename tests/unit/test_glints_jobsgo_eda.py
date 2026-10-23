from __future__ import annotations

import pandas as pd

from scripts.run_glints_jobsgo_eda import (
    SOURCES,
    extract_record,
    field_inventory,
    generate_charts,
    missing_rate_table,
    parse_salary,
    skill_frequency,
)


def _row(source: str, job_id: str, html: str, listing_payload: dict | None = None) -> dict:
    return {
        "source": source,
        "job_id": job_id,
        "version": 1,
        "snapshot_key": f"raw/{source}/2026-10-17/{job_id}_v1.json",
        "snapshot": {
            "_meta": {
                "source": source,
                "source_job_id": job_id,
                "url": f"https://example.test/{source}/{job_id}",
                "version": 1,
            },
            "raw": {"html": html, "listing_payload": listing_payload or {}},
        },
    }


def test_glints_monthly_vnd_salary_is_comparable():
    result = parse_salary(
        "glints",
        "<html><body>Software Engineer</body></html>",
        {"salaries": [{"minAmount": 20_000_000, "maxAmount": 30_000_000,
                       "CurrencyCode": "VND", "salaryMode": "MONTHLY"}]},
    )
    assert result["salary_comparable_monthly"] is True
    assert result["salary_min_million_vnd_month"] == 20
    assert result["salary_max_million_vnd_month"] == 30


def test_jobsgo_monthly_million_vnd_salary_is_comparable():
    result = parse_salary(
        "jobsgo",
        "<html><body><p>Mức lương: 20 - 30 triệu VNĐ/tháng</p></body></html>",
        {"card_text": "Mức lương: 20 - 30 triệu VNĐ/tháng"},
    )
    assert result["salary_min_raw"] == 20
    assert result["salary_max_raw"] == 30
    assert result["salary_comparable_monthly"] is True
    assert result["salary_min_million_vnd_month"] == 20
    assert result["salary_max_million_vnd_month"] == 30


def test_usd_not_converted_without_explicit_fx_rate():
    html = "<html><body><p>Salary: $3,000</p></body></html>"
    no_fx = parse_salary("jobsgo", html, {"card_text": "Salary: $3,000 per month"})
    with_fx = parse_salary("jobsgo", html, {"card_text": "Salary: $3,000 per month"}, fx_vnd_per_usd=25_000)
    assert no_fx["salary_currency"] == "USD"
    assert no_fx["salary_comparable_monthly"] is False
    assert with_fx["salary_comparable_monthly"] is True
    assert with_fx["salary_min_million_vnd_month"] == 75



def test_monthly_marker_far_from_salary_does_not_make_salary_comparable():
    html = "<html><body><p>Mức lương: 20 - 30 triệu VNĐ</p><p>Team reviews code monthly.</p></body></html>"
    result = parse_salary("jobsgo", html, {"card_text": "Mức lương: 20 - 30 triệu VNĐ"})
    assert result["salary_public_numeric"] is True
    assert result["salary_comparable_monthly"] is False
    assert result["salary_min_million_vnd_month"] is None


def test_go_keyword_does_not_match_google_or_mongodb():
    row = _row(
        "jobsgo", "j1",
        "<html><body><h1>Backend developer</h1><p>Google, MongoDB, Python</p></body></html>",
        {"title": "Backend developer", "company": "Example"},
    )
    result = extract_record(row)
    skills = result["skills_keyword_scan"]
    assert "Python" in skills
    assert "Go" not in skills


def test_jobsgo_row_is_not_lost_when_source_has_zero_records():
    df = pd.DataFrame([
        {"source": "glints", "title": "Engineer", "company": "A", "salary_text": None,
         "location": None, "min_experience_years": None, "description_chars": 120, "skill_tags_raw": []}
    ])
    missing = missing_rate_table(df)
    jobsgo = missing[missing["source"] == "jobsgo"]
    assert len(jobsgo) > 0
    assert (jobsgo["records"] == 0).all()
    assert jobsgo["missing_rate_pct"].isna().all()


def test_inventory_distinguishes_null_from_absent_and_empty_string():
    rows = [
        _row("glints", "g1", "<html><body><h1>A</h1></body></html>", {"title": "A", "company": None, "skills": []}),
        _row("glints", "g2", "<html><body><h1>B</h1></body></html>", {"title": "B", "company": "", "other": "x"}),
    ]
    inv = field_inventory(rows)
    company = inv[inv["field_or_selector"] == "listing_field:company"].iloc[0]
    title = inv[inv["field_or_selector"] == "listing_field:title"].iloc[0]
    assert company["records_present"] == 2
    assert company["records_non_null"] == 0
    assert company["null_or_empty_when_present_pct"] == 100.0
    assert company["absent_rate_pct"] == 0.0
    assert title["presence_rate_pct"] == 100.0


def test_chart_generation_writes_all_eight_charts_even_for_empty_data(tmp_path):
    columns = [
        "source", "salary_min_million_vnd_month", "salary_max_million_vnd_month",
        "min_experience_years", "description_words", "skill_count", "html_chars",
        "salary_public_numeric", "salary_comparable_monthly",
    ]
    empty = pd.DataFrame(columns=columns)
    charts = generate_charts(empty, pd.DataFrame(), tmp_path)
    expected = {
        "01_salary_distribution.png", "02_experience_salary_relationship.png",
        "03_salary_dispersion_by_source.png", "04_pearson_correlation.png",
        "05_spearman_correlation.png", "06_skills_pareto.png",
        "07_salary_disclosure_by_source.png", "08_missing_rate_by_source.png",
    }
    assert expected == {p.name for p in tmp_path.glob("*.png")}
    assert set(charts) == {"pearson", "spearman"}


def test_generic_competitive_jd_text_is_not_labeled_as_negotiable_salary():
    result = parse_salary(
        "jobsgo",
        "<html><body><p>We provide a competitive work environment and good teamwork.</p></body></html>",
        {"card_text": "Backend Engineer"},
    )
    assert result["salary_negotiable"] is False
    assert result["salary_missing"] is True


def test_minio_is_default_even_when_old_s3_endpoint_variable_exists(monkeypatch):
    from scripts import run_glints_jobsgo_eda as eda

    class FakeS3:
        def __init__(self):
            self.headed = None

        def head_bucket(self, **kwargs):
            self.headed = kwargs["Bucket"]

    client = FakeS3()
    captured = {}

    def fake_boto_client(service, **kwargs):
        captured.update(kwargs)
        return client

    monkeypatch.setattr(eda.boto3, "client", fake_boto_client)
    monkeypatch.setenv("S3_PROVIDER", "minio")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://old-account.r2.cloudflarestorage.com")
    monkeypatch.setenv("S3_BUCKET_NAME", "r2-old-bucket")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "r2-old-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "r2-old-secret")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://localhost:9123")
    monkeypatch.setenv("MINIO_BUCKET", "vn-it-jobs")
    monkeypatch.setenv("MINIO_ROOT_USER", "local-user")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "local-secret")

    s3, bucket, endpoint = eda.connect_s3()

    assert s3 is client
    assert endpoint == "http://localhost:9123"
    assert bucket == "vn-it-jobs"
    assert client.headed == "vn-it-jobs"
    assert captured["aws_access_key_id"] == "local-user"
    assert captured["aws_secret_access_key"] == "local-secret"
