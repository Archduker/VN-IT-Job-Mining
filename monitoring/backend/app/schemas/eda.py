# -*- coding: utf-8 -*-
"""Pydantic schemas cho EDA và Machine Learning 3D."""

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
    total_records: int
    fields_count: int
    completeness_score_pct: float
    salary_parse_rate_pct: float
    negotiable_salary_pct: float


class SemanticVectorPoint3D(BaseModel):
    id: str
    title: str
    company: str
    job_family: str
    salary_vnd: Optional[float] = None
    x: float
    y: float
    z: float
    is_anomaly: bool = False
    skills: List[str] = []


class Spatial3DResponse(BaseModel):
    algorithm: str  # umap_3d | tsne_3d | isolation_forest_3d
    total_points: int
    points: List[SemanticVectorPoint3D]
    decision_boundary_mesh: Optional[Dict[str, Any]] = None
