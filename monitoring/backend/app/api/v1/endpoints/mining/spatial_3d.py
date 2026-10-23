# -*- coding: utf-8 -*-
"""Endpoints cho Phòng Thí Nghiệm Machine Learning Không Gian 3D (Stage 3)."""

from fastapi import APIRouter
from app.services.ml_spatial_3d_service import ml_spatial_3d_service
from app.schemas.eda import Spatial3DResponse

router = APIRouter()


@router.get("/umap", response_model=Spatial3DResponse, summary="Không gian vector ngữ nghĩa 3D (UMAP/t-SNE)")
def get_umap_3d():
    """Trả về tọa độ (X, Y, Z) của các tin tuyển dụng sau khi giảm chiều vector nhúng,

    phục vụ trực quan hóa các cụm Job Family trong không gian 3 chiều.
    """
    return ml_spatial_3d_service.get_umap_3d_clusters()


@router.get("/isolation-forest", response_model=Spatial3DResponse, summary="Ranh giới phân tách tin rác 3D (Isolation Forest)")
def get_isolation_forest_3d():
    """Trả về lưới bề mặt cong phân tách (Decision Surface) và các điểm dữ liệu bất thường."""
    return ml_spatial_3d_service.get_isolation_forest_3d()
