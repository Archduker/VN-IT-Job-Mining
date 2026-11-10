# -*- coding: utf-8 -*-
"""Endpoints cho phân hệ Collection EDA (Giai đoạn 1: Khám Phá Dữ Liệu Thô)."""

from typing import List, Literal
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.services import eda_r2_service
from app.services.eda_collection_service import eda_collection_service
from app.services.pipeline_report_service import pipeline_report_service
from app.schemas.eda import EDASummary, FieldInventoryItem

router = APIRouter()


@router.get("/compare", summary="So sánh độ đầy đủ giữa 8 nguồn từ báo cáo Integration")
def get_cross_source_compare(origin: Literal["local", "r2"] = "local"):
    if origin == "r2":
        return eda_r2_service.compare(settings.SUPPORTED_SOURCES)
    return pipeline_report_service.get_eda_compare()


@router.get("/{source}/inventory", response_model=List[FieldInventoryItem], summary="Bảng kiểm kê trường DOM thô")
def get_field_inventory(source: str, origin: Literal["local", "r2"] = "local"):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")
    if origin == "r2":
        return eda_r2_service.inventory(source)
    return eda_collection_service.get_field_inventory(source)


@router.get("/{source}/summary", response_model=EDASummary, summary="Tóm tắt chất lượng dữ liệu cào thô")
def get_eda_summary(source: str, origin: Literal["local", "r2"] = "local"):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")
    if origin == "r2":
        return eda_r2_service.summary(source)
    return eda_collection_service.get_summary(source)


@router.get("/{source}/charts", summary="Dữ liệu 5 họ biểu đồ 2D cho nguồn")
def get_2d_charts(source: str, origin: Literal["local", "r2"] = "local"):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")
    if origin == "r2":
        return eda_r2_service.charts(source)
    return eda_collection_service.get_charts_2d(source)


@router.post("/{source}/scan", summary="Quét lại toàn bộ raw R2 trong nền")
def refresh_raw_scan(source: str):
    from app.services.eda_raw_scan_service import scan
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(404, detail="UNKNOWN_SOURCE")
    return {k: v for k, v in scan(source, refresh=True).items() if k != "inventory"}
