# -*- coding: utf-8 -*-
"""Endpoints cho phân hệ Pre-processing (Giai đoạn 2: Tiền Xử Lý & Làm Sạch)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.data_paths import require_source
from app.services import preprocessing_step_service as steps
from app.services.pipeline_report_service import pipeline_report_service

router = APIRouter()


@router.get("/metrics", summary="Kết quả làm sạch từng nguồn, đọc từ health card của pipeline cũ")
def get_preprocessing_metrics():
    return pipeline_report_service.get_preprocessing()


@router.get("/steps", summary="5 bước Clean → Integration → Transformation → Normalization → Encoding, đúng thứ tự")
def list_steps():
    return steps.list_steps()


@router.get("/processing-steps", summary="Bước 07-09 (reports/processing/), thiếu thì available=false, reason NO_DATA")
def list_processing_steps():
    return steps.list_processing_steps()


@router.get("/anomalies", summary="Bất thường bước 04 (anomalies.json), lọc theo loại và nguồn")
def get_anomalies(kind: Optional[str] = Query(None), source: Optional[str] = Query(None), offset: int = Query(0, ge=0),
                  limit: int = Query(50, ge=1, le=steps.ANOMALY_MAX)):
    if source is not None:
        require_source(source)
    return steps.get_anomalies(kind, source, offset, limit)


@router.get("/jobs/{source}/{job_id}", summary="Mở đúng tin theo job_id (đọc parquet trên máy, không gọi R2)")
def get_job(job_id: str, source: str = Depends(require_source), job_id_global: Optional[str] = Query(None)):
    return steps.find_job(source, job_id, job_id_global)


@router.get("/steps/{step}", summary="Báo cáo gộp 8 nguồn của một bước")
def get_step(step: str):
    return steps.get_step(step)


@router.get("/storage", summary="So output từng bước trên máy với R2, theo từng key")
def get_storage():
    return steps.storage_status()


@router.get("/steps/{step}/rows", summary="Một trang dòng dữ liệu silver/gold của một bước, đọc từ R2 hoặc file trên máy")
def get_rows(step: str, source: Optional[str] = Query(None), offset: int = Query(0, ge=0),
             limit: int = Query(50, ge=1, le=steps.MAX_ROWS), origin: str = Query("r2", pattern="^(r2|local)$")):
    if source is not None:
        require_source(source)
    return steps.get_rows(step, source, offset, limit, origin)


@router.get("/steps/{step}/{source}", summary="Báo cáo của một nguồn ở một bước")
def get_step_source(step: str, source: str = Depends(require_source)):
    return steps.get_step_source(step, source)
