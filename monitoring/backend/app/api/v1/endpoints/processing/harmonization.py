# -*- coding: utf-8 -*-
"""Endpoints cho phân hệ Processing (Giai đoạn 3: Tích Hợp & Khử Trùng Lặp)."""

from fastapi import APIRouter

from app.services.pipeline_report_service import pipeline_report_service

router = APIRouter()


@router.get("/metrics", summary="Khử trùng lặp và độ đầy đủ schema, đọc từ báo cáo của pipeline")
def get_processing_metrics():
    return pipeline_report_service.get_processing()
