# -*- coding: utf-8 -*-
"""Pydantic schemas cho Cloudflare R2 Cloud Lakehouse."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class CloudHealthResponse(BaseModel):
    configured: bool
    connected: bool
    latency_ms: Optional[float] = None
    bucket: str
    endpoint: str
    message: str
    error: Optional[str] = None


class R2ObjectItem(BaseModel):
    key: str
    size: int
    last_modified: str
    etag: str


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


class LocalCloudDiff(BaseModel):
    source: str
    local_files: int
    cloud_files: int
    unpushed_count: int
    sync_status: str  # SYNCED | OUT_OF_SYNC | UNKNOWN
