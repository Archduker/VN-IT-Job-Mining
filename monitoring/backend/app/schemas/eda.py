# -*- coding: utf-8 -*-
"""Pydantic schemas cho EDA."""

from typing import Optional
from pydantic import BaseModel


class FieldInventoryItem(BaseModel):
    field_name: str
    data_type: str
    null_count: int
    null_rate_pct: float
    unique_count: int
    sample_value: Optional[str] = None


class EDASummary(BaseModel):
    source: str
    total_records: Optional[int] = None
    sampled_records: int = 0
    fields_count: int
    completeness_score_pct: Optional[float] = None
    salary_parse_rate_pct: Optional[float] = None
    negotiable_salary_pct: Optional[float] = None
    reason: Optional[str] = None
