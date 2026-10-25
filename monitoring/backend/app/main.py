# -*- coding: utf-8 -*-
"""Điểm khởi động trung tâm của Monitoring Backend (FastAPI).

VN-IT-Job-Mining Central Observatory.
"""

import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Đảm bảo PYTHONPATH nhận thư mục gốc repo để nạp các package collection/
if str(settings.ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(settings.ROOT_DIR))

from app.api.v1.router import api_router
from app.services.dashboard_service import dashboard_service

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    Hệ thống Giám sát & Điều phối Toàn diện (Central Observatory) cho VN-IT-Job-Mining.
    Miêu tả hình ảnh thực tế của dữ liệu qua các thông số và biểu đồ liên tục theo chuỗi chuẩn:
    Collection -> Pre-processing -> Processing -> AI/ML Data Mining.
    """,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Cấu hình CORS mở cho các client frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount toàn bộ API v1
app.include_router(api_router, prefix=settings.API_V1_STR)


# Alias trực tiếp cho /api/dashboard theo yêu cầu
@app.get("/api/dashboard", tags=["Master Dashboard"], summary="Alias trực tiếp cho /api/v1/dashboard")
def get_dashboard_alias():
    """Alias trực tiếp truy cập vào thông tin bộ dữ liệu sau integration."""
    return dashboard_service.get_master_dashboard_data()


@app.get("/", tags=["System"], summary="Health check gốc")
def root_health():
    return {
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs",
        "master_dashboard_api": f"{settings.API_V1_STR}/dashboard",
        "alias_dashboard_api": "/api/dashboard",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
