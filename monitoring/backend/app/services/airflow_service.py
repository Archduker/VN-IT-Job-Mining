# -*- coding: utf-8 -*-
"""Service giám sát sức khỏe và lịch trình thực thi Apache Airflow.

Đọc trực tiếp trạng thái tiến trình Scheduler/Webserver và truy vấn SQLite database (airflow/airflow.db).
"""

from datetime import datetime
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger("airflow_service")


class AirflowService:
    """Quản lý giám sát trạng thái Apache Airflow và các DAGs cào dữ liệu."""

    def __init__(self):
        self.airflow_dir = settings.ROOT_DIR / "airflow"
        self.db_path = self.airflow_dir / "airflow.db"
        self.schedule_map = {
            "crawler_topdev": {"day": "Thứ Hai 20:00", "source": "topdev"},
            "crawler_careerviet": {"day": "Thứ Ba 20:00", "source": "careerviet"},
            "crawler_itviec": {"day": "Thứ Tư 20:00", "source": "itviec"},
            "crawler_vietnamworks": {"day": "Thứ Năm 20:00", "source": "vietnamworks"},
            "crawler_topcv": {"day": "Thứ Sáu 20:00", "source": "topcv"},
            "crawler_vieclam24h": {"day": "Thứ Bảy 20:00", "source": "vieclam24h"},
            "crawler_glints": {"day": "Chủ Nhật 20:00", "source": "glints"},
            "crawler_jobsgo": {"day": "Hàng ngày 22:00", "source": "jobsgo"},
        }

    def _check_pid(self, pid_file: Path) -> Optional[int]:
        """Đọc PID từ file và kiểm tra tiến trình có đang sống hay không."""
        if not pid_file.exists():
            return None
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            # Kiểm tra tiến trình có tồn tại
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            return None

    def get_daemon_status(self) -> Dict[str, Any]:
        """Kiểm tra sức khỏe của Scheduler và Webserver daemon."""
        scheduler_pid = self._check_pid(self.airflow_dir / "run" / "scheduler.pid")
        if not scheduler_pid:
            scheduler_pid = self._check_pid(self.airflow_dir / "scheduler.pid")

        webserver_pid = self._check_pid(self.airflow_dir / "run" / "webserver.pid")
        if not webserver_pid:
            webserver_pid = self._check_pid(self.airflow_dir / "webserver.pid")

        # Kiểm tra socket cổng 8080 (Webserver)
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        webserver_port_open = sock.connect_ex(("127.0.0.1", 8080)) == 0
        sock.close()

        is_scheduler_live = scheduler_pid is not None
        is_webserver_live = webserver_pid is not None or webserver_port_open

        # Đếm số DAGs đang có
        try:
            dags = self.get_crawler_dags_status()
            active_dags = len(dags)
        except Exception:
            active_dags = len(self.schedule_map)

        return {
            "scheduler": {
                "running": is_scheduler_live,
                "pid": scheduler_pid,
                "status": "ONLINE" if is_scheduler_live else "STOPPED",
                "pid_file": str(self.airflow_dir / "run" / "scheduler.pid"),
            },
            "webserver": {
                "running": is_webserver_live,
                "pid": webserver_pid,
                "port": 8080,
                "status": "ONLINE" if is_webserver_live else "STOPPED",
                "ui_url": "http://localhost:8080" if is_webserver_live else None,
            },
            "database": {
                "connected": self.db_path.exists(),
                "engine": "sqlite",
                "exists": self.db_path.exists(),
                "path": str(self.db_path),
                "size_kb": round(self.db_path.stat().st_size / 1024, 1) if self.db_path.exists() else 0,
                "size_mb": round(self.db_path.stat().st_size / (1024 * 1024), 2) if self.db_path.exists() else 0.0,
            },
            "active_dags_count": active_dags,
            "last_checked": datetime.now().isoformat(),
        }

    def get_crawler_dags_status(self) -> List[Dict[str, Any]]:
        """Truy vấn bảng SQLite airflow.db để lấy thông tin các DAGs cào dữ liệu."""
        if not self.db_path.exists():
            return []

        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            # Lấy trạng thái kích hoạt DAG
            cursor.execute("SELECT dag_id, is_paused, is_active FROM dag")
            dags_meta = {row[0]: {"is_paused": bool(row[1]), "is_active": bool(row[2])} for row in cursor.fetchall()}

            # Lấy lần chạy gần nhất của từng DAG
            cursor.execute("""
                SELECT dag_id, state, execution_date, start_date, end_date
                FROM dag_run
                ORDER BY id DESC
            """)
            runs = cursor.fetchall()
            conn.close()

            latest_runs: Dict[str, Dict[str, Any]] = {}
            for r in runs:
                dag_id = r[0]
                if dag_id not in latest_runs:
                    start_d = r[3]
                    end_d = r[4]
                    duration_sec = None
                    if start_d and end_d:
                        try:
                            t1 = datetime.fromisoformat(start_d.replace(" ", "T"))
                            t2 = datetime.fromisoformat(end_d.replace(" ", "T"))
                            duration_sec = round((t2 - t1).total_seconds(), 1)
                        except Exception:
                            duration_sec = None

                    latest_runs[dag_id] = {
                        "state": r[1] or "queued",
                        "execution_date": r[2],
                        "start_date": start_d,
                        "end_date": end_d,
                        "duration_seconds": duration_sec,
                    }

            # Kết hợp thông tin cấu hình và dữ liệu thực tế
            results = []
            for dag_id, info in self.schedule_map.items():
                meta = dags_meta.get(dag_id, {"is_paused": False, "is_active": True})
                run_st = latest_runs.get(dag_id, {
                    "state": "scheduled",
                    "execution_date": None,
                    "start_date": None,
                    "end_date": None,
                    "duration_seconds": None,
                })

                results.append({
                    "dag_id": dag_id,
                    "source": info["source"],
                    "schedule_day": info["day"],
                    "is_paused": meta["is_paused"],
                    "is_active": meta["is_active"],
                    "last_run_state": run_st["state"].upper(),
                    "last_execution_date": run_st["execution_date"],
                    "last_start_date": run_st["start_date"],
                    "last_end_date": run_st["end_date"],
                    "duration_seconds": run_st["duration_seconds"],
                })

            return results
        except Exception as exc:
            logger.error("Lỗi truy vấn airflow.db: %s", exc)
            return []


airflow_service = AirflowService()
