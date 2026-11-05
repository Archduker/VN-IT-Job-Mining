# -*- coding: utf-8 -*-
"""Endpoint Master Dashboard (/api/v1/dashboard): bộ Golden Master sau khử trùng lặp."""

from fastapi import APIRouter

from app.services.pipeline_report_service import pipeline_report_service

router = APIRouter()


@router.get("", summary="Bộ golden sau khử trùng lặp, đọc từ health card của pipeline")
def get_master_dashboard():
    return pipeline_report_service.get_dashboard()
