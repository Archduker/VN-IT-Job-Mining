# -*- coding: utf-8 -*-
"""Service tổng hợp và phát hiện cảnh báo thời gian thực trên hệ thống Monitoring.

VN-IT-Job-Mining Central Observatory.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List
from sqlalchemy import text

from app.core.config import settings
from app.services.airflow_service import airflow_service

logger = logging.getLogger("alert_service")


class AlertService:
    """Quản lý các sự cố, cảnh báo và bất thường của toàn bộ hệ sinh thái."""

    def __init__(self):
        self.acknowledged_alerts: set = set()

    def get_system_alerts(self) -> Dict[str, Any]:
        """Tổng hợp toàn bộ cảnh báo đang hoạt động từ các phân hệ."""
        alerts: List[Dict[str, Any]] = []

        # 1. Kiểm tra kết nối PostgreSQL
        db_connected = airflow_service._check_db_connection()
        if not db_connected:
            alerts.append({
                "id": "db_offline",
                "severity": "CRITICAL",
                "category": "DATABASE",
                "title": "PostgreSQL Metadata Database Mất Kết Nối",
                "message": "Không thể kết nối đến cơ sở dữ liệu PostgreSQL (Port 5432). Airflow Scheduler và Webserver có thể bị ngắt quãng.",
                "source": "airflow",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action_url": "/airflow",
            })

        # 2. Kiểm tra trạng thái Airflow Scheduler Daemon
        status = airflow_service.get_daemon_status()
        if not status["scheduler"]["running"]:
            alerts.append({
                "id": "scheduler_stopped",
                "severity": "CRITICAL",
                "category": "AIRFLOW",
                "title": "Airflow Scheduler Đang Dừng Hoạt Động",
                "message": "Scheduler daemon chưa được khởi động. Các tác vụ cào và đồng bộ tự động sẽ không được kích hoạt theo lịch.",
                "source": "airflow",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action_url": "/airflow",
            })

        # 3. Quét Task Instance bị FAILED trong PostgreSQL (nếu DB online)
        if db_connected and airflow_service.engine:
            try:
                with airflow_service.engine.connect() as conn:
                    failed_tasks = conn.execute(text("""
                        SELECT dag_id, task_id, state, execution_date, duration
                        FROM task_instance
                        WHERE state = 'failed'
                        ORDER BY execution_date DESC
                        LIMIT 5
                    """)).fetchall()

                    for ft in failed_tasks:
                        alerts.append({
                            "id": f"task_failed_{ft[0]}_{ft[1]}",
                            "severity": "WARNING",
                            "category": "AIRFLOW",
                            "title": f"Tác vụ Airflow Thất Bại: {ft[1]}",
                            "message": f"DAG '{ft[0]}' gặp sự cố ở task '{ft[1]}' vào lúc {ft[3]}. Vui lòng kiểm tra log trên Cloudflare R2.",
                            "source": ft[0].replace("crawler_detail_", ""),
                            "timestamp": str(ft[3]),
                            "action_url": "/airflow",
                        })
            except Exception as e:
                logger.warning("[AlertService] Lỗi quét task_instance: %s", e)

        # 4. Kiểm tra sức khỏe Cloudflare R2 Cloud Lakehouse
        bucket = os.getenv("R2_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "vn-it-jobs"
        try:
            from collection.common.r2_storage import get_r2_client
            s3 = get_r2_client()
            s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        except Exception as r2_err:
            alerts.append({
                "id": "r2_lakehouse_error",
                "severity": "CRITICAL",
                "category": "STORAGE",
                "title": "Cloudflare R2 Lakehouse Mất Kết Nối",
                "message": f"Không thể xác thực hoặc truy vấn Bucket '{bucket}' trên Cloudflare R2: {r2_err}",
                "source": "cloudflare_r2",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action_url": "/cloud",
            })

        # 5. Kiểm tra cảnh báo Hàng đợi dồn ứ (Backlog Surge)
        try:
            from collection.common.adaptive_router import AdaptiveWorkloadRouter
            topcv_router = AdaptiveWorkloadRouter("topcv")
            pending_count = topcv_router.get_pending_count()
            if pending_count > 500:
                alerts.append({
                    "id": "backlog_surge_topcv",
                    "severity": "WARNING",
                    "category": "CRAWLER",
                    "title": f"Cảnh Báo Hàng Đợi TopCV: {pending_count:,} Tin PENDING",
                    "message": f"Nguồn TopCV đang tồn đọng {pending_count:,} liên kết chưa cào chi tiết. Đang áp dụng cơ chế xả cuối tuần an toàn.",
                    "source": "topcv",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action_url": "/crawling",
                })
        except Exception:
            pass

        # Lọc ra các cảnh báo chưa được người dùng ẩn đi
        active_alerts = [a for a in alerts if a["id"] not in self.acknowledged_alerts]
        critical_count = sum(1 for a in active_alerts if a["severity"] == "CRITICAL")
        warning_count = sum(1 for a in active_alerts if a["severity"] == "WARNING")

        return {
            "total_alerts": len(active_alerts),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "alerts": active_alerts,
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Đánh dấu đã xem và ẩn cảnh báo."""
        self.acknowledged_alerts.add(alert_id)
        return True


alert_service = AlertService()
