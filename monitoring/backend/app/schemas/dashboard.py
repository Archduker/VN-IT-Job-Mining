# -*- coding: utf-8 -*-
"""Pydantic schemas cho Executive Master Dashboard (/api/v1/dashboard).

Thông tin tổng hợp bộ dữ liệu sau integration (Golden Master Dataset).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatasetMetadata(BaseModel):
    version: str = "1.0.0"
    storage_layer: str = "curated/golden_master"
    format: str = "parquet"
    total_raw_scraped: int = Field(..., description="Tổng số bài cào thô ban đầu")
    total_preprocessed: int = Field(..., description="Tổng số bài sau bước tiền xử lý")
    total_golden_unique: int = Field(..., description="Tổng số bài vàng sau khử trùng lặp")
    deduplication_rate_pct: float = Field(..., description="Tỷ lệ trùng lặp bị loại bỏ (%)")
    overall_completeness_score: float = Field(..., description="Điểm toàn vẹn dữ liệu (%)")


class PlatformBreakdown(BaseModel):
    source: str
    raw_count: int
    contributed_unique: int
    share_pct: float


class MarketSalaryBenchmark(BaseModel):
    currency: str = "VND"
    unit: str = "Million"
    p25: float
    median: float
    mean: float
    p75: float
    p90: float
    min_valid: float
    max_valid: float


class GoldenSkill(BaseModel):
    skill: str
    job_count: int
    percentage: float


class DataLineage(BaseModel):
    raw_input_files: int
    preprocessed_records: int
    filtered_spams: int
    cross_platform_duplicates_merged: int
    final_golden_records: int


class DashboardResponse(BaseModel):
    status: str = "success"
    generated_at: str
    dataset_metadata: DatasetMetadata
    platform_breakdown: List[PlatformBreakdown]
    schema_convergence: Dict[str, float]
    market_salary_benchmark_vnd: MarketSalaryBenchmark
    top_golden_skills: List[GoldenSkill]
    data_lineage: DataLineage
