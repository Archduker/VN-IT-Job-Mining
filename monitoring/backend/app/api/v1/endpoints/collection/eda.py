# -*- coding: utf-8 -*-
"""Endpoints cho phân hệ Collection EDA (Giai đoạn 1: Khám Phá Dữ Liệu Thô)."""

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.services.eda_collection_service import eda_collection_service
from app.schemas.eda import EDASummary, FieldInventoryItem

router = APIRouter()


@router.get("/{source}/inventory", response_model=List[FieldInventoryItem], summary="Bảng kiểm kê trường DOM thô")
def get_field_inventory(source: str):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")
    return eda_collection_service.get_field_inventory(source)


@router.get("/{source}/summary", response_model=EDASummary, summary="Tóm tắt chất lượng dữ liệu cào thô")
def get_eda_summary(source: str):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")
    return eda_collection_service.get_summary(source)


@router.get("/{source}/charts", summary="Dữ liệu 5 họ biểu đồ 2D cho nguồn")
def get_2d_charts(source: str):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")
    return eda_collection_service.get_charts_2d(source)
