# -*- coding: utf-8 -*-
"""Endpoints giám sát Apache Airflow Orchestration."""

from typing import Any, Dict, List
from fastapi import APIRouter

from app.services.airflow_service import airflow_service

router = APIRouter()


@router.get("/status", summary="Lấy trạng thái daemon Scheduler và Webserver của Airflow")
def get_airflow_daemon_status():
    """Kiểm tra xem Airflow Scheduler và Webserver có đang chạy hay không."""
    return airflow_service.get_daemon_status()


@router.get("/dags", summary="Lấy danh sách 7 DAGs cào dữ liệu và trạng thái chạy gần nhất")
def get_crawler_dags():
    """Trả về danh sách các DAGs cào xoay vòng hàng ngày, lịch chạy, và kết quả thực thi gần nhất."""
    return airflow_service.get_crawler_dags_status()
