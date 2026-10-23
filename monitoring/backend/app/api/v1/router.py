# -*- coding: utf-8 -*-
"""Tổng hợp định tuyến API v1 cho Monitoring Backend."""

from fastapi import APIRouter

from app.api.v1.endpoints import cloud_r2, dashboard
from app.api.v1.endpoints.collection import crawling, eda as collection_eda
from app.api.v1.endpoints.preprocessing import cleaning
from app.api.v1.endpoints.processing import harmonization
from app.api.v1.endpoints.mining import spatial_3d
from app.api.v1.endpoints.orchestration import airflow

api_router = APIRouter()

# 1. Trung Tâm Điều Hành: Master Dashboard Sau Integration
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Master Dashboard"])

# 2. Phân Hệ Vận Hành Cào Dữ Liệu: Crawling Operations (Độc Lập 100%)
api_router.include_router(crawling.router, prefix="/crawling", tags=["Crawling Operations"])
api_router.include_router(crawling.router, prefix="/collection/crawling", tags=["Crawling Operations (Legacy)"])

# 3. Phân Hệ Khoa Học Dữ Liệu: EDA Intelligence (Độc Lập 100%)
api_router.include_router(collection_eda.router, prefix="/eda", tags=["EDA Intelligence"])
api_router.include_router(collection_eda.router, prefix="/collection/eda", tags=["EDA Intelligence (Legacy)"])

# 4. Phân Hệ Giám Sát Apache Airflow Orchestration
api_router.include_router(airflow.router, prefix="/orchestration/airflow", tags=["Airflow Orchestration"])
api_router.include_router(airflow.router, prefix="/airflow", tags=["Airflow Orchestration (Alias)"])

# 5. Giai Đoạn 2: Pre-processing & Cleaning Metrics
api_router.include_router(cleaning.router, prefix="/preprocessing", tags=["Pre-processing"])

# 6. Giai Đoạn 3: Processing & Post-Integration Harmonization
api_router.include_router(harmonization.router, prefix="/processing", tags=["Processing"])

# 7. Phân Hệ Machine Learning: Không Gian 3D WebGL
api_router.include_router(spatial_3d.router, prefix="/mining/spatial-3d", tags=["ML Spatial 3D Lab"])

# 8. Hạ Tầng Cloudflare R2 Cloud Lakehouse (Sync Engine & Diff)
api_router.include_router(cloud_r2.router, prefix="/cloud/r2", tags=["Cloudflare R2"])
