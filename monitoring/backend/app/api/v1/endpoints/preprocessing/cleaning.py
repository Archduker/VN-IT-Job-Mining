# -*- coding: utf-8 -*-
"""Endpoints cho phân hệ Pre-processing (Giai đoạn 2: Tiền Xử Lý & Làm Sạch)."""

from fastapi import APIRouter

from app.services.pipeline_report_service import pipeline_report_service

router = APIRouter()


@router.get("/metrics", summary="Kết quả làm sạch từng nguồn, đọc từ health card của pipeline")
def get_preprocessing_metrics():
    return pipeline_report_service.get_preprocessing()
