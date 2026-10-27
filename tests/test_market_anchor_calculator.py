# -*- coding: utf-8 -*-
"""Unit tests for MarketAnchorCalculator."""

from pathlib import Path
from preprocessing.missing_outlier.market_anchor_calculator import MarketAnchorCalculator


def test_fit_from_records_nested_and_flat():
    sample_records = [
        # Nested format
        {
            "source_platform": "itviec",
            "job_info": {"standardized_seniority": "Senior"},
            "salary": {"salary_min_vnd": 30000000.0, "salary_max_vnd": 50000000.0},
        },
        {
            "source_platform": "itviec",
            "job_info": {"standardized_seniority": "Senior"},
            "salary": {"salary_min_vnd": 40000000.0, "salary_max_vnd": 60000000.0},
        },
        # Flat format
        {
            "source_platform": "topcv",
            "standardized_seniority": "Junior",
            "salary_min_vnd": 10000000.0,
            "salary_max_vnd": 18000000.0,
        },
        # Negotiable record (should be skipped from anchor calculation)
        {
            "source_platform": "topcv",
            "standardized_seniority": "Junior",
            "salary_min_vnd": None,
            "salary_max_vnd": None,
        },
    ]

    calc = MarketAnchorCalculator(min_samples_per_cell=2)
    calc.fit_from_records(sample_records)

    assert calc.total_samples_analyzed == 3

    # Exact match for (itviec, Senior)
    anchor_senior = calc.get_anchor("itviec", "Senior")
    assert anchor_senior["median_min"] == 35000000.0
    assert anchor_senior["median_max"] == 55000000.0
    assert anchor_senior["sample_count"] == 2


def test_fallback_hierarchy():
    sample_records = [
        {
            "source_platform": "itviec",
            "job_info": {"standardized_seniority": "Middle"},
            "salary": {"salary_min_vnd": 20000000.0, "salary_max_vnd": 30000000.0},
        },
        {
            "source_platform": "topcv",
            "standardized_seniority": "Middle",
            "salary_min_vnd": 22000000.0,
            "salary_max_vnd": 32000000.0,
        },
    ]

    calc = MarketAnchorCalculator(min_samples_per_cell=5)  # Require 5, so exact cell will fallback
    calc.fit_from_records(sample_records)

    # Fallback to seniority level Middle across all platforms
    anchor_mid = calc.get_anchor("itviec", "Middle")
    assert anchor_mid["median_min"] == 21000000.0
    assert anchor_mid["median_max"] == 31000000.0

    # Fallback to floor map for unknown seniority
    anchor_intern = calc.get_anchor("unknown_platform", "Intern")
    assert anchor_intern["median_min"] == 3000000.0
    assert anchor_intern["median_max"] == 7000000.0


def test_format_anchor_context():
    calc = MarketAnchorCalculator()
    ctx = calc.format_anchor_context("itviec", "Senior")
    assert "itviec" in ctx
    assert "Senior" in ctx
    assert "VND" in ctx


def test_real_dataset_anchors():
    """Kiểm thử nạp trực tiếp từ golden_master.json của dự án."""
    golden_path = Path("data/curated/golden_master.json")
    if golden_path.is_file():
        calc = MarketAnchorCalculator()
        calc.fit_from_file(golden_path)
        assert calc.total_samples_analyzed > 3000

        # Anchor cho Senior trên Vietnamworks
        anchor = calc.get_anchor("vietnamworks", "Senior")
        assert anchor["median_min"] >= 20000000.0
        assert anchor["median_max"] > anchor["median_min"]
