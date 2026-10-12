# -*- coding: utf-8 -*-
"""crawlers.preprocessing.preClean.schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Schema cho dữ liệu công việc hợp nhất đầy đủ ý phục vụ EDA.
Giữ nguyên vẹn cấu trúc List cho các trường bullet points (description_list,
requirements_list, benefits_list) và loại bỏ các trường thừa _clean.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CleanedJobRecord(BaseModel):
    """Bản ghi tuyển dụng hợp nhất đầy đủ ý (Full-Fidelity EDA Record)."""

    model_config = ConfigDict(populate_by_name=True)

    meta: Dict[str, Any] = Field(
        ...,
        alias="_meta",
        description="Metadata hệ thống: unified_id, source, source_job_id, url, crawled_at, language",
    )

    # Thông tin cơ bản
    title: str = Field(..., description="Tiêu đề bài đăng đã làm sạch trực tiếp")
    company: str = Field(..., description="Tên công ty đã làm sạch trực tiếp")

    # Mức lương định lượng chuẩn hóa
    salary: Dict[str, Any] = Field(
        ...,
        description="Thông tin lương chuẩn hóa: salary_min, salary_max, salary_currency, salary_type, salary_raw_text",
    )

    # Danh sách nội dung (Bảo toàn dạng List, làm sạch từng dòng, không sinh thêm cột _clean)
    description_list: List[str] = Field(
        default_factory=list,
        description="Danh sách các ý mô tả công việc (đã làm sạch)",
    )
    requirements_list: List[str] = Field(
        default_factory=list,
        description="Danh sách các ý yêu cầu tuyển dụng (đã làm sạch)",
    )
    benefits_list: List[str] = Field(
        default_factory=list,
        description="Danh sách các ý quyền lợi & đãi ngộ (đã làm sạch)",
    )

    # Thẻ tags phân nhóm (3 nhóm: skills, requirements, benefits)
    tags: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Phân loại 3 nhóm thẻ: skills, requirements, benefits",
    )

    # Địa điểm & Hình thức làm việc
    locations: List[str] = Field(
        default_factory=list,
        description="Danh sách các tỉnh/thành phố chuẩn hóa",
    )
    location_text: Optional[str] = Field(None, description="Chuỗi địa điểm gốc")
    employment_type_text: Optional[str] = Field(None, description="Hình thức làm việc: Toàn thời gian, Part-time...")
    seniority_text: Optional[str] = Field(None, description="Cấp bậc: Junior, Senior, Lead, Manager...")

    # Mốc thời gian
    posted_date_text: Optional[str] = Field(None, description="Ngày đăng tin tuyển dụng")
    deadline_text: Optional[str] = Field(None, description="Hạn nộp hồ sơ tuyển dụng")

    # Thông tin bổ trợ phong phú (học vấn, kinh nghiệm, quy mô, số lượng tuyển...)
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata bổ sung: experience, education, company_size, hiring_quantity, industry, work_schedule...",
    )
