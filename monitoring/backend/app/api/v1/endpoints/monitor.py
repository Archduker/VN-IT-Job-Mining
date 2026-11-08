# -*- coding: utf-8 -*-
"""Endpoints cho hai trang chính Collection và Raw."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.data_paths import require_source
from app.services.collection_monitor_service import collection_monitor_service
from app.services.source_report_service import source_report_service

router = APIRouter()


@router.get("/collection", summary="Tin theo ngày, lịch chạy và tiến độ thu thập")
def get_collection(days: int = Query(14, ge=7, le=14)) -> Dict[str, Any]:
    return collection_monitor_service.get_collection(days)


@router.get("/sources", summary="Độ đầy đủ tổng quan của 8 nguồn")
def list_sources() -> List[Dict[str, Any]]:
    return source_report_service.list_overview()


@router.get("/sources/{source}/report", summary="Báo cáo 8 feature target của một nguồn")
def get_source_report(source: str = Depends(require_source)) -> Dict[str, Any]:
    return source_report_service.get_report(source)


@router.get("/sources/{source}/univariate/{code}", summary="Phân tích đơn biến một feature")
def get_univariate(code: str, source: str = Depends(require_source)) -> Dict[str, Any]:
    return source_report_service.get_univariate(source, code.upper())


@router.get("/sources/{source}/samples", summary="Danh sách ID bản ghi raw")
def list_samples(q: str = "", source: str = Depends(require_source)) -> Dict[str, Any]:
    return source_report_service.list_samples(source, q)


@router.get("/sources/{source}/samples/{job_id}", summary="Một bản ghi raw kèm chú thích F1–F8")
def get_sample(job_id: str, source: str = Depends(require_source)) -> Dict[str, Any]:
    sample = source_report_service.get_sample(source, job_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy bản ghi {job_id}")
    return sample
