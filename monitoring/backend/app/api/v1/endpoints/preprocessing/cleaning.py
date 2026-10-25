# -*- coding: utf-8 -*-
"""Endpoints cho phân hệ Pre-processing (Giai đoạn 2: Tiền Xử Lý & Làm Sạch)."""

from fastapi import APIRouter
from app.services.eda_preprocessing_service import eda_preprocessing_service

router = APIRouter()


@router.get("/metrics", summary="Lấy chỉ số đánh giá hiệu quả tiền xử lý & làm sạch")
def get_preprocessing_metrics():
    """Trả về tỷ lệ parse regex dải lương, kinh nghiệm, hạn nộp và mức độ giảm null."""
    return eda_preprocessing_service.get_preprocessing_metrics()
