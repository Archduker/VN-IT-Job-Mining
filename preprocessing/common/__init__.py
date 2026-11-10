# -*- coding: utf-8 -*-
"""Phần dùng chung của pipeline 5 bước (docs/spec/preprocessing/spec/P0_pipeline_contract.md)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES = ("topcv", "topdev", "vietnamworks", "careerviet", "vieclam24h", "itviec", "glints", "jobsgo")
STEPS = ("01_clean", "01b_deduplication", "02_integration", "03_transformation", "04_normalization", "05_encoding")
