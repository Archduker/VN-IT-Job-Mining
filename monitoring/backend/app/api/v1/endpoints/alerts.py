# -*- coding: utf-8 -*-
"""Endpoint quản lý Cảnh báo thời gian thực trên Web Monitor.

VN-IT-Job-Mining Central Observatory.
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Dict

from app.services.alert_service import alert_service

router = APIRouter()


@router.get("", summary="Lấy danh sách cảnh báo hệ thống thời gian thực")
def get_alerts() -> Dict[str, Any]:
    """Trả về danh sách các cảnh báo sự cố từ Airflow, PostgreSQL, Cloudflare R2 và Crawler."""
    return alert_service.get_system_alerts()


@router.post("/{alert_id}/acknowledge", summary="Đánh dấu đã xem và ẩn cảnh báo")
def acknowledge_alert(alert_id: str) -> Dict[str, Any]:
    """Đánh dấu một cảnh báo đã được quản trị viên xử lý hoặc xem."""
    success = alert_service.acknowledge_alert(alert_id)
    return {"status": "success", "alert_id": alert_id, "acknowledged": success}
