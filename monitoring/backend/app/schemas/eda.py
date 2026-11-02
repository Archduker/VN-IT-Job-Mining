# -*- coding: utf-8 -*-
"""Pydantic schemas cho EDA."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class FieldInventoryItem(BaseModel):
    field_name: str
    data_type: str
    null_count: int
    null_rate_pct: float
    unique_count: int
    sample_value: Optional[str] = None


class OutlierProfile(BaseModel):
    q1: float
    median: float
    q3: float
    iqr: float
    lower_bound: float
    upper_bound: float
    outlier_count: int
    outlier_rate_pct: float
    max_value: Optional[float] = None
    min_value: Optional[float] = None


class Distribution2D(BaseModel):
    bins: List[float]
    counts: List[int]
    density_kde: Optional[List[float]] = None
    box: Dict[str, float]


class EDASummary(BaseModel):
    source: str
    total_records: Optional[int] = None
    sampled_records: int = 0
    fields_count: int
    completeness_score_pct: Optional[float] = None
    salary_parse_rate_pct: Optional[float] = None
    negotiable_salary_pct: Optional[float] = None
    reason: Optional[str] = None
