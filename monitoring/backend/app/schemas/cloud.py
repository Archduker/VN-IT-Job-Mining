# -*- coding: utf-8 -*-
"""Pydantic schemas cho Cloudflare R2 Cloud Lakehouse."""

from typing import Dict, Optional
from pydantic import BaseModel


class CloudHealthResponse(BaseModel):
    configured: bool
    connected: bool
    latency_ms: Optional[float] = None
    bucket: str
    endpoint: str
    message: str
    error: Optional[str] = None


class LayerMetric(BaseModel):
    count: int
    size_bytes: int
    size_mb: float


class StorageBreakdownResponse(BaseModel):
    bucket: str
    connected: bool
    total_objects: int
    total_size_mb: float
    layers: Dict[str, LayerMetric]
    error: Optional[str] = None

