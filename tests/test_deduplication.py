# -*- coding: utf-8 -*-
"""Tests for record linkage and Golden Record survivorship."""

import json

import pandas as pd
import pytest

from preprocessing.deduplication.record_linkage import (
    LinkageConfig,
    jaro_winkler_similarity,
    link_duplicate_records,
    normalize_city,
    normalize_company_name,
    render_deduplication_report,
)
from preprocessing.deduplication.golden_record_resolver import resolve_golden_records


SAME_JD = (
    "Develop backend services with Python and PostgreSQL. Design REST APIs, write unit tests, "
    "review code, monitor production services, and collaborate with product engineers."
)


def job(job_id, source, title="Senior Software Engineer", description=SAME_JD,
        skills=None, company="Công ty TNHH Example Group Vietnam", city="Hồ Chí Minh",
        family="Backend", **extra):
    row = {
        "job_id_global": job_id,
        "source_platform": source,
        "job_title": title,
        "company_name": company,
        "primary_city": city,
        "standardized_job_family": family,
        "raw_description_text": description,
        "skills_list": skills if skills is not None else ["Python", "PostgreSQL", "REST API"],
        "benefits_list": ["Health insurance"],
        "raw_salary_text": "Thỏa thuận",
        "salary_min_vnd": None,
        "salary_max_vnd": None,
        "is_salary_negotiable": True,
    }
    row.update(extra)
    return row


def test_normalize_company_and_city_aliases():
    assert normalize_company_name("CÔNG TY TNHH WIR GROUP VIỆT NAM") == "wir"
    assert normalize_company_name("WIR Group Vietnam Co., Ltd.") == "wir"
    assert normalize_city("TP. Hồ Chí Minh") == "ho chi minh"
    assert normalize_city("HCMC") == "ho chi minh"
    assert normalize_city("Hà Nội") == "ha noi"


def test_jaro_winkler_title_similarity_handles_word_order():
    assert jaro_winkler_similarity("Senior Software Engineer (ODOO)", "Senior Odoo Software Engineer") == 1.0
    assert jaro_winkler_similarity("Senior Backend Engineer", "Senior Backend Engineer") == 1.0
    assert jaro_winkler_similarity("Senior Backend Engineer", "HR Payroll Specialist") < 0.6
    assert jaro_winkler_similarity("", "Senior Engineer") == 0.0


def test_linkage_detects_intra_and_cross_platform_and_preserves_rows():
    rows = [
        job("glints_1", "glints", title="Senior Software Engineer (ODOO)"),
        job("glints_2", "glints", title="Senior Odoo Software Engineer", raw_salary_text="30-45 triệu", salary_min_vnd=30_000_000, salary_max_vnd=45_000_000, is_salary_negotiable=False, skills_list=["Python", "Odoo", "Docker"]),
        job("topcv_3", "topcv", title="Senior Odoo Software Engineer", skills=["Python", "Odoo", "Docker", "PostgreSQL"]),
        job("jobsgo_4", "jobsgo", title="QA Engineer", description=SAME_JD, skills=["Python", "PostgreSQL", "REST API"]),
    ]
    linked, metrics = link_duplicate_records(pd.DataFrame(rows))

    assert len(linked) == len(rows)  # linking never drops source records
    assert linked.loc[0, "cluster_id"] == linked.loc[1, "cluster_id"] == linked.loc[2, "cluster_id"]
    assert bool(linked.loc[0, "is_duplicate"]) is True
    assert int(linked.loc[0, "duplicate_count"]) == 3
    assert set(linked.loc[0, "source_platforms"]) == {"glints", "topcv"}
    assert linked.loc[3, "is_duplicate"] == False  # noqa: E712
    assert metrics["intra_platform_pair_count"] >= 1
    assert metrics["cross_platform_pair_count"] >= 1
    assert metrics["duplicate_cluster_count"] == 1
    assert metrics["source_intra_platform_duplicate_records"]["glints"] == 2
    assert metrics["source_cross_platform_duplicate_records"]["topcv"] == 1
    assert metrics["similarity_backend"] in {"all-MiniLM-L6-v2", "tfidf_fallback"}


def test_blocking_requires_all_three_keys_and_does_not_merge_missing_keys():
    rows = [
        job("topcv_1", "topcv", family="Backend"),
        job("jobsgo_2", "jobsgo", family=None),
        job("glints_3", "glints", company=None),
        job("itviec_4", "itviec", city=None),
    ]
    linked, metrics = link_duplicate_records(pd.DataFrame(rows))
    assert linked["cluster_id"].nunique() == 4
    assert not linked["is_duplicate"].any()
    assert metrics["blocking_missing_records"] == 3
    assert {"standardized_job_family", "normalized_company", "primary_city"}.issubset(
        {key for detail in metrics["blocking_missing_details"] for key in detail["missing_keys"]}
    )


def test_same_company_and_title_but_different_family_are_not_compared():
    rows = [
        job("topcv_1", "topcv", family="Backend"),
        job("jobsgo_2", "jobsgo", family="Data/AI"),
    ]
    linked, metrics = link_duplicate_records(pd.DataFrame(rows))
    assert linked["cluster_id"].nunique() == 2
    assert metrics["pairwise_candidate_count"] == 0
    assert metrics["matched_pair_count"] == 0


def test_golden_resolver_fuses_salary_skills_benefits_and_preserves_member_payloads():
    rows = [
        job("careerviet_1001", "careerviet", title="Senior Software Engineer (ODOO)",
            description=SAME_JD[:-12], skills=["Python", "Odoo"], benefits_list=["Health insurance"]),
        job("vietnamworks_2002", "vietnamworks", title="Senior Odoo Software Engineer",
            description=SAME_JD, skills=["Docker", "PostgreSQL", "Python"],
            raw_salary_text="35 - 50 triệu", salary_min_vnd=35_000_000, salary_max_vnd=50_000_000,
            salary_source="header_regex", is_salary_negotiable=False,
            benefits_list=["13th-month salary", "MacBook"]),
    ]
    linked, _ = link_duplicate_records(pd.DataFrame(rows))
    golden_df = resolve_golden_records(linked)

    assert len(golden_df) == 1
    golden = golden_df.iloc[0]
    assert bool(golden["is_duplicate"]) is True
    assert int(golden["duplicate_count"]) == 2
    assert set(golden["source_platforms"]) == {"careerviet", "vietnamworks"}
    assert golden["salary_min_vnd"] == 35_000_000
    assert golden["salary_max_vnd"] == 50_000_000
    assert len(golden["raw_description_text"]) == len(SAME_JD)
    assert {"Python", "Odoo", "Docker", "PostgreSQL"}.issubset(set(golden["skills_list"]))
    assert {"Health insurance", "13th-month salary", "MacBook"}.issubset(set(golden["benefits_list"]))
    payload = json.loads(golden["duplicate_member_records_json"])
    assert len(payload) == 2
    assert {record["job_id_global"] for record in payload} == {"careerviet_1001", "vietnamworks_2002"}


def test_golden_resolver_keeps_singletons_and_empty_frame():
    linked, _ = link_duplicate_records(pd.DataFrame([job("topcv_1", "topcv", family=None)]))
    result = resolve_golden_records(linked)
    assert len(result) == 1
    assert result.iloc[0]["duplicate_count"] == 1
    assert result.iloc[0]["is_duplicate"] == False  # noqa: E712
    assert json.loads(result.iloc[0]["duplicate_member_records_json"])[0]["job_id_global"] == "topcv_1"

    empty = pd.DataFrame(columns=["job_id_global", "source_platform"])
    linked_empty, metrics = link_duplicate_records(empty)
    golden_empty = resolve_golden_records(linked_empty)
    assert linked_empty.empty and golden_empty.empty
    assert metrics["total_input_records"] == 0


def test_report_contains_8_platform_matrix_and_eda_evidence():
    linked, metrics = link_duplicate_records(pd.DataFrame([
        job("topcv_1", "topcv"),
        job("jobsgo_2", "jobsgo"),
    ]))
    report = render_deduplication_report(metrics)
    assert "Ma trận trùng chéo 8 sàn" in report
    assert "CareerViet" in report
    assert "10,4%" in report
    assert "topcv" in report and "jobsgo" in report
    assert metrics["platform_pair_matrix_counts"]["topcv"]["jobsgo"] == metrics["platform_pair_matrix_counts"]["jobsgo"]["topcv"]
    assert 0.0 <= metrics["platform_pair_matrix_rate_pct"]["topcv"]["jobsgo"] <= 100.0
    assert 0.0 <= metrics["platform_pair_matrix_rate_pct"]["jobsgo"]["topcv"] <= 100.0



def test_pandas_nullable_missing_keys_are_not_stringified_into_block_keys():
    rows = [
        job("topcv_1", "topcv", company=pd.NA),
        job("jobsgo_2", "jobsgo", city=pd.NA),
        job("glints_3", "glints", family=pd.NA),
    ]
    linked, metrics = link_duplicate_records(pd.DataFrame(rows))
    assert len(linked) == 3
    assert not linked["is_duplicate"].any()
    assert metrics["blocking_missing_records"] == 3


def test_golden_resolver_handles_pandas_nullable_salary_without_crashing():
    rows = [
        job("topcv_1", "topcv", salary_min_vnd=pd.NA, salary_max_vnd=pd.NA,
            raw_salary_text=pd.NA),
        job("jobsgo_2", "jobsgo", salary_min_vnd=25_000_000,
            salary_max_vnd=35_000_000, raw_salary_text="25-35 triệu", is_salary_negotiable=False),
    ]
    linked, _ = link_duplicate_records(pd.DataFrame(rows))
    golden = resolve_golden_records(linked).iloc[0]
    assert golden["salary_min_vnd"] == 25_000_000
    assert golden["salary_max_vnd"] == 35_000_000

def test_threshold_validation():
    with pytest.raises(ValueError):
        LinkageConfig(title_similarity_threshold=1.2)


def test_golden_resolver_handles_nullable_source_platform():
    first = job("topcv_1", "topcv")
    first["source_platform"] = pd.NA
    first["source"] = "topcv"
    second = job(
        "jobsgo_2", "jobsgo",
        raw_salary_text="25-35 triệu", salary_min_vnd=25_000_000,
        salary_max_vnd=35_000_000, is_salary_negotiable=False,
    )
    second["source_platform"] = pd.NA
    second["source"] = "jobsgo"
    linked, _ = link_duplicate_records(pd.DataFrame([first, second]))
    golden = resolve_golden_records(linked).iloc[0]
    assert set(golden["source_platforms"]) == {"topcv", "jobsgo"}
    assert int(golden["duplicate_count"]) == 2


def test_cross_platform_rate_matrix_is_directional():
    rows = [
        job("topcv_match", "topcv"),
        job("topcv_other_family", "topcv", family="Data/AI"),
        job("jobsgo_match", "jobsgo"),
    ]
    linked, metrics = link_duplicate_records(pd.DataFrame(rows))
    rates = metrics["platform_pair_matrix_rate_pct"]
    assert rates["topcv"]["jobsgo"] == 50.0
    assert rates["jobsgo"]["topcv"] == 100.0
    assert len(linked) == 3
