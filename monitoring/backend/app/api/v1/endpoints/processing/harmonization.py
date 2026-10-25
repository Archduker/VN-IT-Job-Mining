# -*- coding: utf-8 -*-
"""Endpoints cho phân hệ Processing (Giai đoạn 3: Tích Hợp & Khử Trùng Lặp)."""

from fastapi import APIRouter
from app.services.eda_processing_service import eda_processing_service

router = APIRouter()


@router.get("/metrics", summary="Lấy chỉ số khử trùng lặp và độ hội tụ Schema")
def get_processing_metrics():
    """Trả về phân phối điểm tương đồng Cosine Similarity và bảng kiểm kê schema mapping."""
    return eda_processing_service.get_processing_metrics()
