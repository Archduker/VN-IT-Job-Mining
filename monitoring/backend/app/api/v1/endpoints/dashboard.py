# -*- coding: utf-8 -*-
"""Endpoint Trung Tâm Điều Hành: Executive Master Dashboard (/api/v1/dashboard).

Lưu trữ và phục vụ toàn bộ thông số về Bộ Dữ Liệu Sau Khi Integration (Golden Master Dataset).
"""

from fastapi import APIRouter
from app.services.dashboard_service import dashboard_service
from app.schemas.dashboard import DashboardResponse

router = APIRouter()


@router.get("", response_model=DashboardResponse, summary="Lấy toàn bộ thông tin bộ dữ liệu sau integration")
def get_master_dashboard():
    """Trả về các chỉ số vàng của Golden Master Dataset:

    - Số bài đăng duy nhất sau khử trùng lặp
    - Tỷ lệ giảm trùng lặp xuyên sàn
    - Bảng tỷ lệ hội tụ Schema đích
    - Phân bổ bài tuyển dụng từ 8 sàn
    - Phân phối mức lương toàn thị trường IT sau chuẩn hóa
    - Top kỹ năng công nghệ vàng ESCO
    - Truy vết luồng dữ liệu (Data Lineage)
    """
    return dashboard_service.get_master_dashboard_data()
