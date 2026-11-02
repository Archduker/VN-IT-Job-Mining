# -*- coding: utf-8 -*-
"""Service điều phối và giám sát tiến trình Crawler (Subprocess Runner & SSE Streamer)."""

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, AsyncGenerator, Dict, Optional

from app.core.config import settings

logger = logging.getLogger("crawler_service")


# Lịch của crawler_detail_<source> trong airflow/dags/crawler_dags.py
DETAIL_SCHEDULE_TIME = "09, 14, 18, 21, 22h"


def _discovery_status(states: Optional[Dict[str, Optional[str]]], task_id: str) -> str:
    """Đổi trạng thái task Airflow sang nhãn bảng Phase 1; không đọc được thì trả UNKNOWN."""
    if states is None or task_id not in states:
        return "UNKNOWN"
    state = states[task_id]
    if state == "success":
        return "SUCCESS"
    if state in ("failed", "upstream_failed"):
        return "FAILED"
    if state == "running":
        return "RUNNING"
    return "SCHEDULED"


class CrawlerService:
    """Quản lý các tiến trình chạy crawler và stream log console thời gian thực."""

    def __init__(self):
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.log_buffers: Dict[str, list] = {}
        self.log_dropped: Dict[str, int] = {}
        self.job_status: Dict[str, Dict[str, Any]] = {}

    def get_source_status(self, source: str) -> Dict[str, Any]:
        """Lấy trạng thái thực thi hiện tại của crawler cho nguồn chỉ định."""
        proc = self.active_processes.get(source)
        is_running = proc is not None and proc.returncode is None

        # Đếm số file raw hiện có
        raw_dir = settings.DATA_DIR / source / "raw"
        raw_count = 0
        if raw_dir.exists():
            for _, _, files in os.walk(raw_dir):
                raw_count += len([f for f in files if f.endswith(".json")])

        # Đọc ledger
        from app.services.ledger_service import ledger_service
        ledger_st = ledger_service.get_ledger_summary(source)

        return {
            "source": source,
            "status": "running" if is_running else "idle",
            "is_running": is_running,
            "total_urls": ledger_st.get("total", 0),
            "total_raw": raw_count,
            "pid": proc.pid if is_running else None,
            "engine": "curl_cffi" if source in ["topcv", "jobsgo"] else "default",
        }

    async def trigger_crawler(
        self,
        source: str,
        phase: str = "all",
        max_items: int = 30,
        max_pages: Optional[int] = None,
        engine: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Kích hoạt crawler nguồn chỉ định qua subprocess run.py."""
        source = source.lower()
        if source not in settings.SUPPORTED_SOURCES:
            raise ValueError(f"Nguồn '{source}' không được hỗ trợ")

        if self.active_processes.get(source) and self.active_processes[source].returncode is None:
            return {
                "job_id": f"job_{source}",
                "source": source,
                "phase": phase,
                "status": "already_running",
                "message": f"Crawler cho {source} đang chạy (PID: {self.active_processes[source].pid})",
            }

        # Xây dựng lệnh gọi
        cmd = [
            sys.executable,
            str(settings.ROOT_DIR / "run.py"),
            "--source",
            source,
            "--phase",
            phase,
            "--max-items",
            str(max_items),
        ]
        if max_pages:
            cmd.extend(["--max-pages", str(max_pages)])
        if engine and source in ["topcv", "jobsgo"]:
            cmd.extend(["--engine", engine])

        self.log_buffers[source] = []
        self.log_dropped[source] = 0
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.log_buffers[source].append(f"[{now_str}] Bắt đầu thực thi: {' '.join(cmd)}\n")

        # Khởi chạy non-blocking subprocess
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(settings.ROOT_DIR),
        )

        self.active_processes[source] = proc
        self.job_status[source] = {
            "source": source,
            "phase": phase,
            "started_at": now_str,
            "status": "running",
        }

        # Background task để đọc và đệm log
        async def read_stream():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                self.log_buffers[source].append(decoded)
                # Giới hạn bộ đệm 2000 dòng gần nhất
                if len(self.log_buffers[source]) > 2000:
                    self.log_buffers[source].pop(0)
                    self.log_dropped[source] += 1
            await proc.wait()
            finish_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            self.log_buffers[source].append(
                f"[{finish_str}] Tiến trình kết thúc với exit code: {proc.returncode}\n"
            )

        asyncio.create_task(read_stream())

        return {
            "job_id": f"job_{source}_{proc.pid}",
            "source": source,
            "phase": phase,
            "status": "started",
            "message": f"Khởi động crawler {source} thành công (PID: {proc.pid})",
        }

    async def stop_crawler(self, source: str) -> Dict[str, Any]:
        """Dừng tiến trình crawler đang chạy."""
        proc = self.active_processes.get(source)
        if not proc or proc.returncode is not None:
            return {"source": source, "status": "not_running", "message": "Crawler không hoạt động"}

        try:
            proc.terminate()
            await asyncio.sleep(0.5)
            if proc.returncode is None:
                proc.kill()
            return {"source": source, "status": "stopped", "message": "Đã dừng crawler thành công"}
        except Exception as exc:
            return {"source": source, "status": "error", "message": str(exc)}

    async def stream_logs(self, source: str) -> AsyncGenerator[str, None]:
        """SSE Generator truyền log dòng lệnh theo thời gian thực."""
        sent = 0  # Tổng số dòng đã gửi, tính cả dòng đã bị cắt khỏi buffer
        while True:
            buffer = self.log_buffers.get(source, [])
            dropped = self.log_dropped.get(source, 0)
            for line in buffer[max(sent - dropped, 0):]:
                yield line.rstrip("\r\n")
            sent = dropped + len(buffer)

            proc = self.active_processes.get(source)
            if proc is None:
                yield "[EOF] Nguồn này chưa có tiến trình đang chạy."
                break
            if proc.returncode is not None:
                # Tiến trình đã xong và đã gửi hết log
                yield "[EOF] Quá trình cào đã hoàn tất."
                break

            await asyncio.sleep(0.5)

    def get_weekly_crawl_schedule(self) -> Dict[str, Any]:
        """Tạo bảng kế hoạch điều phối 2 Pha (Pha 1 Discovery & Pha 2 Detail) cho 8 sàn tuyển dụng."""
        from app.services.airflow_service import airflow_service
        from app.services.ledger_service import ledger_service

        discovery_states = airflow_service.get_latest_discovery_states()

        # Định nghĩa 8 sàn tuyển dụng chuẩn
        source_configs = [
            {
                "day_of_week": "Thứ Hai (Monday)",
                "day_index": 1,
                "focal_source": "topdev",
                "engine": "curl_cffi (TLS Impersonation)",
                "quota": 250,
                "recrawl_strategy": "Safe Skip + Re-crawl 21 ngày",
            },
            {
                "day_of_week": "Thứ Ba (Tuesday)",
                "day_index": 2,
                "focal_source": "careerviet",
                "engine": "curl_cffi (HTML Parser)",
                "quota": 200,
                "recrawl_strategy": "Anti-403 + Fallback",
            },
            {
                "day_of_week": "Thứ Tư (Wednesday)",
                "day_index": 3,
                "focal_source": "itviec",
                "engine": "curl_cffi (Session Auth)",
                "quota": 200,
                "recrawl_strategy": "JSON-LD & DOM Matcher",
            },
            {
                "day_of_week": "Thứ Năm (Thursday)",
                "day_index": 4,
                "focal_source": "vietnamworks",
                "engine": "curl_cffi (Algolia/API)",
                "quota": 300,
                "recrawl_strategy": "IT Domain Filter",
            },
            {
                "day_of_week": "Thứ Sáu (Friday)",
                "day_index": 5,
                "focal_source": "topcv",
                "engine": "playwright (Cloudflare Bypass)",
                "quota": 350,
                "recrawl_strategy": "Two-Phase Discovery/Detail",
            },
            {
                "day_of_week": "Thứ Bảy (Saturday)",
                "day_index": 6,
                "focal_source": "vieclam24h",
                "engine": "curl_cffi (Mobile UA)",
                "quota": 250,
                "recrawl_strategy": "Safe Skip + CDC Hash",
            },
            {
                "day_of_week": "Chủ Nhật S1 (Sunday)",
                "day_index": 7,
                "focal_source": "glints",
                "engine": "curl_cffi + playwright",
                "quota": 250,
                "recrawl_strategy": "Weekly Catch-up & Backup",
            },
            {
                "day_of_week": "Chủ Nhật S2 (Sunday)",
                "day_index": 8,
                "focal_source": "jobsgo",
                "engine": "curl_cffi (TLS Impersonation)",
                "quota": 250,
                "recrawl_strategy": "Safe Skip + Re-crawl 21 ngày",
            },
        ]

        phase1_discovery = []
        phase2_detail = []
        total_projected = 0
        total_actual = 0
        total_pending = 0

        for sc in source_configs:
            src = sc["focal_source"]
            st = self.get_source_status(src)
            ledger_st = ledger_service.get_ledger_summary(src)
            counts = ledger_st.get("counts", {})

            # Đã cào thực tế từ thư mục raw
            actual_count = st["total_raw"]
            # Số tin chờ cào (PENDING + NEW)
            pending_count = counts.get("PENDING", 0) + counts.get("NEW", 0)
            # Tổng số URLs trong ledger
            total_urls = ledger_st.get("total", 0)

            quota = sc["quota"]
            total_projected += quota
            total_actual += actual_count
            total_pending += pending_count

            progress = round((actual_count / max(quota, 1)) * 100, 1)

            # Airflow status
            if st["is_running"]:
                status = "RUNNING"
            elif actual_count >= quota or pending_count == 0:
                status = "SUCCESS"
            else:
                status = "SCHEDULED"

            # 1. Bảng Pha 1: Daily URL Discovery
            phase1_entry = {
                "day_of_week": sc["day_of_week"],
                "day_index": sc["day_index"],
                "focal_source": src,
                "dag_id": "dag_discovery_daily",
                "task_id": f"discover_{src}",
                "scheduled_time": "05:00 AM",
                "quota_pages": 2,
                "total_discovered": total_urls,
                "status": _discovery_status(discovery_states, f"discover_{src}"),
            }
            phase1_discovery.append(phase1_entry)

            # 2. Bảng Pha 2: Adaptive Detail Extraction
            phase2_entry = {
                "day_of_week": sc["day_of_week"],
                "day_index": sc["day_index"],
                "focal_source": src,
                "dag_id": f"crawler_detail_{src}",
                "scheduled_time": DETAIL_SCHEDULE_TIME,
                "projected_quota": quota,
                "actual_crawled": actual_count,
                "uncrawled_pending": pending_count,
                "progress_pct": progress,
                "engine": sc["engine"],
                "recrawl_strategy": sc["recrawl_strategy"],
                "status": status,
            }
            phase2_detail.append(phase2_entry)

        overall_pct = round((total_actual / max(total_projected, 1)) * 100, 1)

        return {
            "phase1_discovery": phase1_discovery,
            "phase2_detail": phase2_detail,
            "total_projected_weekly": total_projected,
            "total_actual_crawled": total_actual,
            "total_uncrawled_pending": total_pending,
            "overall_progress_pct": overall_pct,
            "days": phase2_detail,  # backward compatibility
            "generated_at": datetime.now().isoformat(),
        }


crawler_service = CrawlerService()
