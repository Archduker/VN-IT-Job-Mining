# -*- coding: utf-8 -*-
"""Dedicated Cloudflare R2 Client cho VN-IT-Job-Mining.

Kết nối trực tiếp tới Cloudflare R2 Endpoint qua giao thức S3v4,
loại bỏ hoàn toàn MinIO S3 cục bộ.
"""

from datetime import datetime
import logging
import os
import time
from typing import Any, Dict, List, Optional
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import settings

logger = logging.getLogger("r2_client")


class CloudflareR2Client:
    """Client chuyên trách giao tiếp Cloudflare R2 Lakehouse."""

    def __init__(self):
        self.endpoint_url = settings.computed_r2_endpoint
        self.access_key = settings.R2_ACCESS_KEY_ID
        self.secret_key = settings.R2_SECRET_ACCESS_KEY
        self.bucket_name = settings.R2_BUCKET_NAME
        self._client = None
        self._sync_status_cache: Optional[Dict[str, Any]] = None
        self._sync_status_cache_time: float = 0.0

    @property
    def is_configured(self) -> bool:
        """Kiểm tra xem thông tin đăng nhập R2 đã được cấu hình hay chưa."""
        return bool(self.endpoint_url and self.access_key and self.secret_key)

    def get_client(self):
        """Khởi tạo hoặc trả về session S3 client tới Cloudflare R2."""
        if not self.is_configured:
            return None

        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=5,
                    read_timeout=10,
                    retries={"max_attempts": 2},
                ),
                region_name="auto",
            )
        return self._client

    def check_connection(self) -> Dict[str, Any]:
        """Kiểm tra tính sẵn sàng và đo độ trễ tới Cloudflare R2."""
        if not self.is_configured:
            return {
                "configured": False,
                "connected": False,
                "message": "Chưa cấu hình R2 credentials trong .env (Cần R2_ENDPOINT_URL hoặc R2_ACCOUNT_ID)",
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url or "N/A",
            }

        client = self.get_client()
        import time
        start_t = time.perf_counter()
        try:
            client.head_bucket(Bucket=self.bucket_name)
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return {
                "configured": True,
                "connected": True,
                "latency_ms": latency_ms,
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "message": "Kết nối Cloudflare R2 thành công",
            }
        except (ClientError, EndpointConnectionError, Exception) as exc:
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return {
                "configured": True,
                "connected": False,
                "latency_ms": latency_ms,
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "error": str(exc),
                "message": f"Không thể kết nối Cloudflare R2: {exc}",
            }

    def list_layer_objects(self, prefix: str, max_keys: int = 100) -> List[Dict[str, Any]]:
        """Liệt kê danh sách objects theo prefix phân tầng trên Cloudflare R2."""
        client = self.get_client()
        if not client:
            return []

        try:
            resp = client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
            contents = resp.get("Contents", [])
            return [
                {
                    "key": item["Key"],
                    "size": item["Size"],
                    "last_modified": item["LastModified"].isoformat(),
                    "etag": item.get("ETag", "").strip('"'),
                }
                for item in contents
            ]
        except Exception as exc:
            logger.error("Lỗi liệt kê objects prefix=%s từ R2: %s", prefix, exc)
            return []

    def get_layers_summary(self) -> Dict[str, Any]:
        """Thống kê tổng số lượng object và dung lượng 4 phân tầng Lakehouse trên R2."""
        layers = ["url_ledger/", "raw/", "staging/", "curated/"]
        client = self.get_client()
        result = {
            "bucket": self.bucket_name,
            "connected": False,
            "total_objects": 0,
            "total_size_mb": 0.0,
            "layers": {},
        }

        if not client:
            return result

        try:
            for layer in layers:
                resp = client.list_objects_v2(Bucket=self.bucket_name, Prefix=layer)
                items = resp.get("Contents", [])
                cnt = len(items)
                sz = sum(it["Size"] for it in items)
                result["layers"][layer.rstrip("/")] = {
                    "count": cnt,
                    "size_bytes": sz,
                    "size_mb": round(sz / (1024 * 1024), 2),
                }
                result["total_objects"] += cnt
                result["total_size_mb"] += round(sz / (1024 * 1024), 2)

            result["connected"] = True
            return result
        except Exception as exc:
            result["error"] = str(exc)
            return result

    def generate_presigned_url(self, object_key: str, expires_in: int = 900) -> Optional[str]:
        """Sinh URL có chữ ký để tải trực tiếp từ Cloudflare R2 qua browser."""
        client = self.get_client()
        if not client:
            return None
        try:
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            logger.error("Lỗi sinh presigned url cho key=%s: %s", object_key, exc)
            return None

    def compute_source_diff(self, source: str) -> Dict[str, Any]:
        """So sánh chênh lệch giữa thư mục cục bộ data/{source} và Cloudflare R2."""
        import os
        from pathlib import Path

        local_raw_dir = settings.DATA_DIR / source / "raw"
        local_files = []
        if local_raw_dir.exists():
            for root, _, files in os.walk(local_raw_dir):
                for f in files:
                    if f.endswith(".json"):
                        f_path = Path(root) / f
                        rel = f_path.relative_to(settings.DATA_DIR)
                        local_files.append(str(rel))

        # Liệt kê từ Cloudflare R2: hỗ trợ cả 2 chuẩn prefix raw/{source}/ và {source}/raw/
        client = self.get_client()
        remote_keys = set()
        if client:
            try:
                paginator = client.get_paginator("list_objects_v2")
                for prefix in [f"raw/{source}/", f"{source}/raw/"]:
                    for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                        for obj in page.get("Contents", []):
                            k = obj["Key"]
                            remote_keys.add(k)
                            # Bình thường hoá để so khớp:
                            # Nếu key trên cloud là raw/topcv/xxx.json -> map sang topcv/raw/xxx.json
                            if k.startswith(f"raw/{source}/"):
                                remote_keys.add(k.replace(f"raw/{source}/", f"{source}/raw/", 1))
                            elif k.startswith(f"{source}/raw/"):
                                remote_keys.add(k.replace(f"{source}/raw/", f"raw/{source}/", 1))
            except Exception as e:
                logger.warning("Không thể lấy danh sách R2 cho diff %s: %s", source, e)

        # Chênh lệch: các file local chưa có trên remote
        unpushed = [f for f in local_files if f not in remote_keys]
        total_local = len(local_files)
        total_cloud = len([k for k in remote_keys if k.startswith(f"{source}/raw/") or k.startswith(f"raw/{source}/")])
        synced_count = total_local - len(unpushed)
        synced_pct = round((synced_count / max(total_local, 1)) * 100, 1)
        is_in_sync = len(unpushed) == 0 and total_local > 0

        return {
            "source": source,
            "local_count": total_local,
            "local_total": total_local,
            "cloud_count": total_cloud,
            "cloud_total": total_cloud,
            "missing_in_cloud": unpushed,
            "missing_count": len(unpushed),
            "unpushed_count": len(unpushed),
            "unpushed_samples": unpushed[:10],
            "synced_pct": synced_pct,
            "status": "IN_SYNC" if is_in_sync else "DESYNC",
            "sync_status": "SYNCED" if is_in_sync else "OUT_OF_SYNC",
            "is_connected": client is not None,
        }

    def sync_upload_source(self, source: str) -> Dict[str, Any]:
        """Đẩy các file cục bộ chưa có lên Cloudflare R2."""
        diff = self.compute_source_diff(source)
        client = self.get_client()
        if not client:
            return {"source": source, "status": "failed", "message": "Chưa kết nối được Cloudflare R2"}

        unpushed = diff["unpushed_samples"]
        uploaded = 0
        errors = []

        import os
        from pathlib import Path
        local_raw_dir = settings.DATA_DIR / source / "raw"
        if local_raw_dir.exists():
            for root, _, files in os.walk(local_raw_dir):
                for f in files:
                    if f.endswith(".json"):
                        f_path = Path(root) / f
                        rel_under_raw = str(f_path.relative_to(local_raw_dir)).replace("\\", "/")
                        key = f"raw/{source}/{rel_under_raw}"
                        try:
                            client.upload_file(str(f_path), self.bucket_name, key)
                            uploaded += 1
                        except Exception as e:
                            errors.append(f"{f}: {e}")

        self._sync_status_cache = None

        return {
            "source": source,
            "status": "completed",
            "uploaded_count": uploaded,
            "errors_count": len(errors),
            "message": f"Đã đồng bộ {uploaded} files lên Cloudflare R2",
        }

    def sync_ledger_to_r2(self, source: str) -> Dict[str, Any]:
        """Đồng bộ catalog_master.json và manifests của nguồn lên Cloudflare R2."""
        client = self.get_client()
        if not client:
            return {"source": source, "success": False, "message": "Chưa kết nối được Cloudflare R2"}

        ledger_dir = settings.DATA_DIR / source / "url_ledger"
        if not ledger_dir.exists():
            ledger_dir = settings.DATA_DIR / "url_ledger" / source

        if not ledger_dir.exists():
            return {"source": source, "success": False, "message": f"Không tìm thấy thư mục url_ledger cho {source}"}

        uploaded_files = []
        errors = []

        # 1. Upload catalog_master.json
        cat_file = ledger_dir / "catalog_master.json"
        if cat_file.exists():
            r2_key = f"url_ledger/{source}/catalog_master.json"
            try:
                client.upload_file(str(cat_file), self.bucket_name, r2_key)
                uploaded_files.append(r2_key)
            except Exception as e:
                errors.append(f"catalog_master.json: {e}")

        # 2. Upload manifests/*.jsonl
        manifest_dir = ledger_dir / "manifests"
        if manifest_dir.exists():
            for f in manifest_dir.glob("*.jsonl"):
                r2_key = f"url_ledger/{source}/manifests/{f.name}"
                try:
                    client.upload_file(str(f), self.bucket_name, r2_key)
                    uploaded_files.append(r2_key)
                except Exception as e:
                    errors.append(f"{f.name}: {e}")

        self._sync_status_cache = None
        return {
            "source": source,
            "success": len(errors) == 0,
            "uploaded_files": uploaded_files,
            "errors": errors,
            "message": f"Đã đẩy {len(uploaded_files)} files Ledger lên R2 (Lỗi: {len(errors)})",
        }

    def get_full_cloud_sync_status(self) -> Dict[str, Any]:
        """Kiểm toán tổng thể tình trạng đồng bộ giữa máy cục bộ và Cloudflare R2 cho toàn bộ 8 nguồn."""
        now_ts = time.time()
        if self._sync_status_cache is not None and (now_ts - self._sync_status_cache_time < 60.0):
            return self._sync_status_cache

        conn = self.check_connection()
        client = self.get_client()

        source_statuses = {}
        total_local_raw = 0
        total_cloud_raw = 0

        # Liệt kê tệp trên R2 theo prefix để tăng tốc
        r2_source_counts = {s: 0 for s in settings.SUPPORTED_SOURCES}
        r2_ledger_exists = {s: False for s in settings.SUPPORTED_SOURCES}

        if client:
            try:
                paginator = client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=self.bucket_name, MaxKeys=1000):
                    for obj in page.get("Contents", []):
                        k = obj["Key"]
                        for s in settings.SUPPORTED_SOURCES:
                            if k.startswith(f"raw/{s}/"):
                                r2_source_counts[s] += 1
                            elif k.startswith(f"url_ledger/{s}/"):
                                r2_ledger_exists[s] = True
            except Exception as exc:
                logger.warning("Không thể lấy thống kê R2: %s", exc)

        for src in settings.SUPPORTED_SOURCES:
            # Đếm số raw cục bộ
            local_raw_dir = settings.DATA_DIR / src / "raw"
            local_raw_count = 0
            if local_raw_dir.exists():
                for root, _, files in os.walk(local_raw_dir):
                    local_raw_count += sum(1 for f in files if f.endswith(".json"))

            # Kiểm tra ledger cục bộ
            cat_file = settings.DATA_DIR / src / "url_ledger" / "catalog_master.json"
            if not cat_file.exists():
                cat_file = settings.DATA_DIR / "url_ledger" / src / "catalog_master.json"
            local_has_ledger = cat_file.exists()

            cloud_count = r2_source_counts[src]
            total_local_raw += local_raw_count
            total_cloud_raw += cloud_count

            sync_pct = round((cloud_count / max(local_raw_count, 1)) * 100, 1) if local_raw_count > 0 else (100.0 if cloud_count > 0 else 0.0)
            sync_pct = min(100.0, sync_pct)

            source_statuses[src] = {
                "source": src,
                "ledger_local": local_has_ledger,
                "ledger_cloud": r2_ledger_exists[src],
                "local_raw_count": local_raw_count,
                "cloud_raw_count": cloud_count,
                "sync_pct": sync_pct,
                "status": "SYNCED" if (sync_pct >= 95.0 and r2_ledger_exists[src]) else "OUT_OF_SYNC",
            }

        overall_sync = round((total_cloud_raw / max(total_local_raw, 1)) * 100, 1) if total_local_raw > 0 else 100.0

        result = {
            "connected": conn.get("connected", False),
            "latency_ms": conn.get("latency_ms", 0),
            "bucket": self.bucket_name,
            "overall_sync_pct": min(100.0, overall_sync),
            "total_local_raw": total_local_raw,
            "total_cloud_raw": total_cloud_raw,
            "sources": source_statuses,
            "last_synced_at": datetime.now().isoformat(),
        }
        self._sync_status_cache = result
        self._sync_status_cache_time = now_ts
        return result


r2_client = CloudflareR2Client()
