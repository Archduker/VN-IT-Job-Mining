# -*- coding: utf-8 -*-
"""Endpoints cho phân hệ Crawling Observatory (Giai đoạn 1)."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.r2_client import r2_client
from app.services.crawler_service import crawler_service
from app.services.ledger_service import ledger_service
from app.schemas.crawling import (
    CrawlJobResponse,
    LedgerResponse,
    SourceStatus,
    TriggerCrawlRequest,
)

router = APIRouter()


@router.get("/sources", response_model=List[SourceStatus], summary="Danh sách 8 nguồn cào và trạng thái")
def list_sources():
    """Lấy danh sách 8 website tuyển dụng IT kèm tổng số bài cào và trạng thái."""
    results = []
    for src in settings.SUPPORTED_SOURCES:
        st = crawler_service.get_source_status(src)
        results.append(
            SourceStatus(
                id=src,
                name=src.upper(),
                status=st["status"],
                total_urls=st["total_urls"],
                total_raw=st["total_raw"],
                engine=st["engine"],
            )
        )
    return results


@router.get("/enum-summary", summary="Thống kê định lượng 5 trạng thái Enum vòng đời URL")
def get_enum_summary():
    """Trả về số lượng và tỷ lệ % của 5 trạng thái Enum: PENDING, DONE, RECHECK_DUE, CLOSED, FAILED."""
    return ledger_service.get_system_enum_summary()


@router.get("/weekly-schedule", summary="Bảng lịch điều phối cào 7 ngày trong tuần")
def get_weekly_schedule():
    """Trả về bảng lịch cào từ Thứ Hai đến Chủ Nhật kèm chỉ tiêu dự kiến và số tin thực tế."""
    return crawler_service.get_weekly_crawl_schedule()


@router.get("/cloud-sync-status", summary="Tình trạng đồng bộ giữa máy cục bộ và Cloudflare R2")
def get_cloud_sync_status():
    """Kiểm toán mức độ đồng bộ URL Ledger và Raw JSONs lên Cloudflare R2 bucket vn-it-jobs."""
    return r2_client.get_full_cloud_sync_status()


@router.post("/sync-all-cloud", summary="Đồng bộ toàn bộ 8 nguồn lên Cloudflare R2")
def sync_all_sources_to_cloud():
    """Kích hoạt đồng bộ cả URL Ledger và Raw JSONs cho toàn bộ các sàn lên Cloudflare R2."""
    results = {}
    for src in settings.SUPPORTED_SOURCES:
        l_res = r2_client.sync_ledger_to_r2(src)
        r_res = r2_client.sync_upload_source(src)
        results[src] = {
            "ledger": l_res,
            "raw": r_res,
        }
    return {
        "status": "completed",
        "message": "Đã hoàn thành đồng bộ toàn bộ 8 nguồn lên Cloudflare R2",
        "details": results,
    }


@router.post("/{source}/sync-cloud", summary="Đồng bộ 1 nguồn lên Cloudflare R2")
def sync_source_to_cloud(source: str):
    """Đồng bộ URL Ledger và các Raw JSON chưa có của nguồn chỉ định lên Cloudflare R2."""
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")

    ledger_res = r2_client.sync_ledger_to_r2(source)
    raw_res = r2_client.sync_upload_source(source)
    return {
        "source": source,
        "status": "completed",
        "ledger_sync": ledger_res,
        "raw_sync": raw_res,
    }


@router.get("/{source}/status", summary="Lấy trạng thái chi tiết của crawler")
def get_source_status(source: str):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")
    return crawler_service.get_source_status(source)


@router.post("/{source}/trigger", response_model=CrawlJobResponse, summary="Kích hoạt cào batch")
async def trigger_crawl(source: str, req: TriggerCrawlRequest):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")

    res = await crawler_service.trigger_crawler(
        source=source,
        phase=req.phase,
        max_items=req.max_items,
        max_pages=req.max_pages,
        engine=req.engine,
    )
    return CrawlJobResponse(**res)


@router.post("/{source}/stop", summary="Dừng khẩn cấp crawler")
async def stop_crawl(source: str):
    source = source.lower()
    return await crawler_service.stop_crawler(source)


@router.get("/{source}/ledger", response_model=LedgerResponse, summary="Lấy danh mục URL Ledger Catalog")
def get_ledger(
    source: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")

    res = ledger_service.list_ledger_items(
        source=source,
        page=page,
        page_size=page_size,
        status_filter=status,
        search_query=search,
    )
    return LedgerResponse(**res)


@router.get("/{source}/logs/stream", summary="Stream log console trực tiếp qua SSE")
async def stream_crawler_logs(source: str):
    source = source.lower()
    if source not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")

    return EventSourceResponse(crawler_service.stream_logs(source))
