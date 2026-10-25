# -*- coding: utf-8 -*-
"""Service giám sát sức khỏe và lịch trình thực thi Apache Airflow.

VN-IT-Job-Mining Central Observatory (Zero-SQLite Policy: PostgreSQL Backend).
"""

from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text

from app.core.config import settings

logger = logging.getLogger("airflow_service")


class AirflowService:
    """Quản lý giám sát trạng thái Apache Airflow và các DAGs cào dữ liệu qua PostgreSQL."""

    def __init__(self):
        self.airflow_dir = settings.ROOT_DIR / "airflow"
        self.db_url = os.getenv(
            "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN",
            "postgresql+psycopg2://airflow:airflow@localhost:5432/airflow",
        )
        try:
            self.engine = create_engine(self.db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
        except Exception as e:
            logger.warning("[AirflowService] Không thể khởi tạo SQLAlchemy Engine: %s", e)
            self.engine = None

        self.schedule_map = {
            "dag_discovery_daily": {"day": "Hàng ngày 05:00", "source": "all"},
            "crawler_detail_topdev": {"day": "Cuối tuần + Tối T2-T6", "source": "topdev"},
            "crawler_detail_vietnamworks": {"day": "Cuối tuần + Tối T2-T6", "source": "vietnamworks"},
            "crawler_detail_careerviet": {"day": "Cuối tuần + Tối T2-T6", "source": "careerviet"},
            "crawler_detail_vieclam24h": {"day": "Cuối tuần + Tối T2-T6", "source": "vieclam24h"},
            "crawler_detail_itviec": {"day": "Cuối tuần + Tối T2-T6", "source": "itviec"},
            "crawler_detail_topcv": {"day": "Cuối tuần + Tối T2-T6", "source": "topcv"},
            "crawler_detail_jobsgo": {"day": "Cuối tuần + Tối T2-T6", "source": "jobsgo"},
            "crawler_detail_glints": {"day": "Cuối tuần + Tối T2-T6", "source": "glints"},
        }

    def _check_pid(self, pid_file: Path) -> Optional[int]:
        """Đọc PID từ file và kiểm tra tiến trình có đang sống hay không."""
        if not pid_file.exists():
            return None
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            return None

    def _check_db_connection(self) -> bool:
        """Kiểm tra kết nối trực tiếp đến PostgreSQL database."""
        if not self.engine:
            return False
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_daemon_status(self) -> Dict[str, Any]:
        """Kiểm tra sức khỏe của Scheduler, Webserver và PostgreSQL."""
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
        db_connected = self._check_db_connection()

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
                "connected": db_connected,
                "engine": "postgresql",
                "host": os.getenv("POSTGRES_HOST", "localhost"),
                "port": int(os.getenv("POSTGRES_PORT", 5432)),
                "name": os.getenv("POSTGRES_DB", "airflow"),
            },
            "active_dags_count": active_dags,
            "last_checked": datetime.now().isoformat(),
        }

    def get_crawler_dags_status(self) -> List[Dict[str, Any]]:
        """Truy vấn PostgreSQL để lấy thông tin các DAGs cào dữ liệu."""
        if not self._check_db_connection():
            return []

        try:
            with self.engine.connect() as conn:
                # 1. Lấy trạng thái kích hoạt DAG
                dags_meta_query = conn.execute(text("SELECT dag_id, is_paused, is_active FROM dag"))
                dags_meta = {
                    row[0]: {"is_paused": bool(row[1]), "is_active": bool(row[2])}
                    for row in dags_meta_query.fetchall()
                }

                # 2. Lấy lần chạy gần nhất của từng DAG
                runs_query = conn.execute(text("""
                    SELECT dag_id, state, execution_date, start_date, end_date
                    FROM dag_run
                    ORDER BY id DESC
                """))
                runs = runs_query.fetchall()

            latest_runs: Dict[str, Dict[str, Any]] = {}
            for r in runs:
                dag_id = r[0]
                if dag_id not in latest_runs:
                    start_d = r[3]
                    end_d = r[4]
                    duration_sec = None
                    if start_d and end_d:
                        try:
                            duration_sec = round((end_d - start_d).total_seconds(), 1)
                        except Exception:
                            duration_sec = None

                    latest_runs[dag_id] = {
                        "state": r[1],
                        "execution_date": str(r[2]),
                        "start_date": str(start_d) if start_d else None,
                        "end_date": str(end_d) if end_d else None,
                        "duration_seconds": duration_sec,
                    }

            result = []
            for dag_id, meta in self.schedule_map.items():
                dag_run = latest_runs.get(dag_id, {})
                db_meta = dags_meta.get(dag_id, {"is_paused": False, "is_active": True})

                result.append({
                    "dag_id": dag_id,
                    "source": meta["source"],
                    "schedule_display": meta["day"],
                    "is_paused": db_meta["is_paused"],
                    "is_active": db_meta["is_active"],
                    "latest_run_state": dag_run.get("state", "NO_RUNS"),
                    "latest_execution_date": dag_run.get("execution_date"),
                    "latest_duration_seconds": dag_run.get("duration_seconds"),
                })

            return result
        except Exception as exc:
            logger.error("[AirflowService] Lỗi truy vấn PostgreSQL Airflow: %s", exc)
            return []


airflow_service = AirflowService()
