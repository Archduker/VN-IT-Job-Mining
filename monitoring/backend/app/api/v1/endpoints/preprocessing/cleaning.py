# -*- coding: utf-8 -*-
"""Endpoints cho phân hệ Pre-processing (Giai đoạn 2: Tiền Xử Lý & Làm Sạch)."""

from fastapi import APIRouter, Depends

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


@router.get("/steps/{step}", summary="Báo cáo gộp 8 nguồn của một bước")
def get_step(step: str):
    return steps.get_step(step)


@router.get("/steps/{step}/{source}", summary="Báo cáo của một nguồn ở một bước")
def get_step_source(step: str, source: str = Depends(require_source)):
    return steps.get_step_source(step, source)
