# -*- coding: utf-8 -*-
"""Cấu hình trung tâm cho Monitoring Backend.

Đọc biến môi trường, định vị đường dẫn thư mục dự án và tham số Cloudflare R2 Lakehouse.
"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Thư mục gốc repo VN-IT-Job-Mining
REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "monitoring" / "backend"

# Nạp file .env từ thư mục gốc repo
load_dotenv(REPO_ROOT / ".env")


class Settings(BaseSettings):
    PROJECT_NAME: str = "VN-IT-Job-Mining Central Observatory"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Đường dẫn thư mục cốt lõi
    ROOT_DIR: Path = REPO_ROOT
    DATA_DIR: Path = REPO_ROOT / "data"
    REPORTS_DIR: Path = REPO_ROOT / "reports"
    NOTEBOOKS_DIR: Path = REPO_ROOT / "notebooks"
    LOGS_DIR: Path = REPO_ROOT / "logs"

    # Danh sách 8 sàn tuyển dụng CNTT được hỗ trợ
    SUPPORTED_SOURCES: List[str] = [
        "topcv",
        "topdev",
        "itviec",
        "careerviet",
        "vieclam24h",
        "vietnamworks",
        "glints",
        "jobsgo",
    ]

    # Cấu hình độc quyền Cloudflare R2 Lakehouse
    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID: str = (
        os.getenv("R2_ACCESS_KEY_ID")
        or os.getenv("AWS_ACCESS_KEY_ID", "")
    )
    R2_SECRET_ACCESS_KEY: str = (
        os.getenv("R2_SECRET_ACCESS_KEY")
        or os.getenv("AWS_SECRET_ACCESS_KEY", "")
    )
    R2_BUCKET_NAME: str = (
        os.getenv("R2_BUCKET_NAME")
        or os.getenv("S3_BUCKET_NAME", "vn-it-jobs")
    )
    R2_ENDPOINT_URL: str = (
        os.getenv("R2_ENDPOINT_URL")
        or os.getenv("S3_ENDPOINT_URL", "")
    )

    @property
    def computed_r2_endpoint(self) -> str:
        """Sinh ra R2 Endpoint tự động từ Account ID nếu chưa thiết lập đầy đủ."""
        if self.R2_ENDPOINT_URL and "r2.cloudflarestorage.com" in self.R2_ENDPOINT_URL:
            return self.R2_ENDPOINT_URL
        if self.R2_ACCOUNT_ID:
            return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        return self.R2_ENDPOINT_URL

    class Config:
        case_sensitive = True


settings = Settings()
