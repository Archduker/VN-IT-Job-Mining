# -*- coding: utf-8 -*-
"""crawlers.sources.careerviet.url_provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tách biệt kiến trúc nạp danh sách URLs mục tiêu cho CareerViet Crawler.

Cung cấp:
- BaseUrlProvider: Giao diện chuẩn cho mọi nhà cung cấp danh sách URLs.
- LocalFileUrlProvider: Đọc an toàn từ các file JSON nguồn cục bộ
  (urls_c1_*.json, urls_c61_*.json, urls_developer_*.json...),
  trích xuất job_id, url, và source_category nguyên bản, khử trùng lặp theo job_id.
- MinIOUrlProvider: Chuẩn bị sẵn kiến trúc đọc URLs từ MinIO / S3 bucket
  cho tương lai, không hardcode credentials (sử dụng env vars hoặc client tiêm vào).
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)

JOB_ID_REGEX = re.compile(r"([A-Z0-9]{6,12})\.html", re.IGNORECASE)


def extract_job_id_from_url(url: str) -> Optional[str]:
    """Trích xuất mã định danh job_id (chuỗi 6-12 ký tự hex/alphanumeric) từ URL tuyển dụng CareerViet."""
    if not url:
        return None
    m = JOB_ID_REGEX.search(url)
    return m.group(1).upper() if m else None


class BaseUrlProvider(ABC):
    """Giao diện trừu tượng cung cấp danh sách URLs cho crawler."""

    @abstractmethod
    def get_target_jobs(self) -> List[Dict[str, Any]]:
        """Trả về danh sách các job mục tiêu:
        [
            {
                "job_id": str,
                "url": str,
                "source_category": str,
            },
            ...
        ]
        Đã được khử trùng lặp theo job_id.
        """
        pass


class LocalFileUrlProvider(BaseUrlProvider):
    """Đọc danh sách URLs từ các file JSON cục bộ theo nguyên tắc:
    - Chỉ đọc input (read-only), không chỉnh sửa hoặc ghi đè file input.
    - Hỗ trợ các file urls_c1_*.json, urls_c61_*.json, urls_developer_*.json hoặc danh sách đường dẫn tùy chọn.
    - Trích xuất url, job_id, và lưu giữ source_category theo từng URL.
    - Khử trùng theo job_id giữa các file/nguồn, giữ lại thông tin xuất hiện đầu tiên.
    """

    def __init__(
        self,
        file_paths: Optional[List[str | Path]] = None,
        base_dir: Optional[str | Path] = None,
        file_patterns: Optional[List[str]] = None,
    ) -> None:
        """Khởi tạo LocalFileUrlProvider.

        Args:
            file_paths: Danh sách file cụ thể. Nếu cung cấp, sẽ ưu tiên đọc các file này.
            base_dir: Thư mục chứa các file URL nguồn (mặc định: 'data/raw/careerviet').
            file_patterns: Danh sách glob patterns để tìm kiếm nếu không truyền file_paths.
        """
        self.base_dir = Path(base_dir or "data/raw/careerviet")
        self.file_paths = [Path(p) for p in file_paths] if file_paths else []
        self.file_patterns = file_patterns or [
            "urls_c1_*.json",
            "urls_c61_*.json",
            "urls_developer_*.json",
        ]

    def _resolve_input_files(self) -> List[Path]:
        """Xác định danh sách các file cần nạp."""
        if self.file_paths:
            resolved = []
            for p in self.file_paths:
                path_obj = Path(p)
                if not path_obj.is_absolute():
                    candidate = self.base_dir / path_obj
                    resolved.append(candidate if candidate.exists() else path_obj)
                else:
                    resolved.append(path_obj)
            return [p for p in resolved if p.exists() and p.is_file()]

        if not self.base_dir.exists():
            log.warning("[LocalFileUrlProvider] Thư mục cơ sở không tồn tại: %s", self.base_dir)
            return []

        resolved_files: List[Path] = []
        for pattern in self.file_patterns:
            matches = sorted(self.base_dir.glob(pattern))
            if matches:
                # Nếu có nhiều ngày, lấy file mới nhất theo tên file
                resolved_files.append(matches[-1])

        return resolved_files

    def _deduce_source_category(self, file_path: Path, data: Any) -> str:
        """Suy luận source_category từ metadata của file hoặc tên file."""
        if isinstance(data, dict):
            src = data.get("source")
            if src:
                return str(src).strip()

        fn = file_path.name.lower()
        if "c1" in fn:
            return "c1"
        if "c61" in fn:
            return "c61"
        if "developer" in fn:
            return "keyword:developer"
        if "c37" in fn:
            return "c37"
        if "sitemap" in fn:
            return "sitemap"
        return "general"

    def get_target_jobs(self) -> List[Dict[str, Any]]:
        """Đọc và trích xuất danh sách URLs từ các file nguồn."""
        input_files = self._resolve_input_files()
        if not input_files:
            log.warning("[LocalFileUrlProvider] Không tìm thấy file URL nào trong %s", self.base_dir)
            return []

        seen_job_ids: Set[str] = set()
        targets: List[Dict[str, Any]] = []

        for fpath in input_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                log.error("[LocalFileUrlProvider] Không thể đọc file %s: %s", fpath, exc)
                continue

            default_cat = self._deduce_source_category(fpath, data)

            items_to_process: List[Any] = []
            if isinstance(data, dict):
                if "records" in data and isinstance(data["records"], list):
                    items_to_process = data["records"]
                elif "all_urls_sorted" in data and isinstance(data["all_urls_sorted"], list):
                    items_to_process = data["all_urls_sorted"]
                elif "urls" in data and isinstance(data["urls"], list):
                    items_to_process = data["urls"]
                else:
                    items_to_process = [data]
            elif isinstance(data, list):
                items_to_process = data

            file_added = 0
            for item in items_to_process:
                if isinstance(item, dict):
                    url = item.get("url")
                    job_id = item.get("job_id")
                    cat = item.get("source_category") or default_cat
                elif isinstance(item, str):
                    url = item.strip()
                    job_id = None
                    cat = default_cat
                else:
                    continue

                if not url:
                    continue

                if not job_id:
                    job_id = extract_job_id_from_url(url)

                if not job_id:
                    continue

                job_id = str(job_id).upper().strip()

                if job_id in seen_job_ids:
                    continue

                seen_job_ids.add(job_id)
                targets.append({
                    "job_id": job_id,
                    "url": url,
                    "source_category": cat,
                })
                file_added += 1

            log.info("[LocalFileUrlProvider] Nạp %s: %d jobs mới (Tổng cộng: %d)", fpath.name, file_added, len(targets))

        return targets


class MinIOUrlProvider(BaseUrlProvider):
    """Provider đọc danh sách URLs từ MinIO / S3 bucket.
    Thiết kế sẵn sàng mở rộng, KHÔNG hardcode credentials.
    Thông tin kết nối được lấy từ env vars hoặc qua client được tiêm vào (DI).
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "careerviet/urls/",
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: bool = False,
        client: Optional[Any] = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.endpoint = endpoint or os.environ.get("MINIO_ENDPOINT")
        self.access_key = access_key or os.environ.get("MINIO_ACCESS_KEY")
        self.secret_key = secret_key or os.environ.get("MINIO_SECRET_KEY")
        self.secure = secure
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from minio import Minio
        except ImportError:
            raise ImportError(
                "Thư viện 'minio' chưa được cài đặt. Cài đặt qua: `pip install minio`"
            )

        if not self.endpoint or not self.access_key or not self.secret_key:
            raise ValueError(
                "Thiếu thông tin kết nối MinIO (endpoint, access_key, secret_key). "
                "Cung cấp qua tham số khởi tạo hoặc biến môi trường MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY."
            )

        self._client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )
        return self._client

    def get_target_jobs(self) -> List[Dict[str, Any]]:
        """Tải các file JSON từ MinIO bucket và phân giải danh sách target jobs."""
        client = self._get_client()
        objects = client.list_objects(self.bucket_name, prefix=self.prefix, recursive=True)
        seen_job_ids: Set[str] = set()
        targets: List[Dict[str, Any]] = []

        for obj in objects:
            if not obj.object_name.endswith(".json"):
                continue
            response = client.get_object(self.bucket_name, obj.object_name)
            try:
                content = response.read().decode("utf-8")
                data = json.loads(content)
            except Exception as exc:
                log.error("[MinIOUrlProvider] Lỗi đọc object %s: %s", obj.object_name, exc)
                continue
            finally:
                response.close()
                response.release_conn()

            obj_path = Path(obj.object_name)
            default_cat = "minio"
            if "c1" in obj.object_name:
                default_cat = "c1"
            elif "c61" in obj.object_name:
                default_cat = "c61"
            elif "developer" in obj.object_name:
                default_cat = "keyword:developer"

            items_to_process = data.get("records", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for item in items_to_process:
                if isinstance(item, dict):
                    url = item.get("url")
                    job_id = item.get("job_id")
                    cat = item.get("source_category") or default_cat
                elif isinstance(item, str):
                    url = item.strip()
                    job_id = None
                    cat = default_cat
                else:
                    continue

                if not url:
                    continue
                if not job_id:
                    job_id = extract_job_id_from_url(url)
                if not job_id:
                    continue

                job_id = str(job_id).upper().strip()
                if job_id in seen_job_ids:
                    continue

                seen_job_ids.add(job_id)
                targets.append({
                    "job_id": job_id,
                    "url": url,
                    "source_category": cat,
                })

        return targets
