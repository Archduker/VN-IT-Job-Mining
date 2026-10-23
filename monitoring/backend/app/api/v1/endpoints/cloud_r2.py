# -*- coding: utf-8 -*-
"""Endpoints quản trị độc quyền Cloudflare R2 Cloud Lakehouse."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query

from app.core.r2_client import r2_client
from app.schemas.cloud import CloudHealthResponse, StorageBreakdownResponse

router = APIRouter()


@router.get("/status", response_model=CloudHealthResponse, summary="Kiểm tra kết nối Cloudflare R2")
def get_r2_status():
    """Kiểm tra tính kết nối, đo độ trễ (latency ms) tới bucket vn-it-jobs trên Cloudflare R2."""
    res = r2_client.check_connection()
    return CloudHealthResponse(**res)


@router.get("/layers", response_model=StorageBreakdownResponse, summary="Thống kê 4 phân tầng Lakehouse trên R2")
def get_r2_layers():
    """Thống kê tổng số lượng file và dung lượng MB theo từng tầng: url_ledger, raw, staging, curated."""
    res = r2_client.get_layers_summary()
    return StorageBreakdownResponse(**res)


@router.get("/presigned-url", summary="Sinh link tải trực tiếp từ Cloudflare R2")
def get_presigned_url(key: str = Query(..., description="Đường dẫn object key trên R2")):
    """Sinh URL có thời hạn 15 phút để tải file trực tiếp qua browser."""
    url = r2_client.generate_presigned_url(key)
    if not url:
        raise HTTPException(status_code=400, detail="Không thể sinh presigned url hoặc thiếu cấu hình R2")
    return {"key": key, "presigned_url": url, "expires_in_seconds": 900}


@router.get("/diff/{source}", summary="Kiểm tra chênh lệch dữ liệu giữa máy cục bộ và Cloudflare R2")
def get_source_diff(source: str):
    """So sánh số lượng và mã băm các file giữa local data/{source} và remote R2."""
    return r2_client.compute_source_diff(source)


@router.post("/sync/{source}", summary="Kích hoạt đồng bộ tải lên Cloudflare R2")
def sync_source_to_r2(source: str):
    """Đẩy các file cục bộ chưa có lên bucket vn-it-jobs trên Cloudflare R2."""
    return r2_client.sync_upload_source(source)
