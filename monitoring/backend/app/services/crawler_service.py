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


class CrawlerService:
    """Quản lý các tiến trình chạy crawler và stream log console thời gian thực."""

    def __init__(self):
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.log_buffers: Dict[str, list] = {}
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
        last_index = 0
        while True:
            buffer = self.log_buffers.get(source, [])
            if last_index < len(buffer):
                for idx in range(last_index, len(buffer)):
                    clean_line = buffer[idx].rstrip("\r\n")
                    yield f"data: {clean_line}\n\n"
                last_index = len(buffer)

            proc = self.active_processes.get(source)
            if proc is not None and proc.returncode is not None and last_index >= len(buffer):
                # Tiến trình đã xong và đã gửi hết log
                yield f"data: [EOF] Quá trình cào đã hoàn tất.\n\n"
                break

            await asyncio.sleep(0.5)

    def get_weekly_crawl_schedule(self) -> Dict[str, Any]:
        """Tạo bảng kế hoạch điều phối cào 7 ngày trong tuần với chỉ tiêu dự kiến vs thực tế."""
        schedule_definition = [
            {
                "day_of_week": "Thứ Hai",
                "day_index": 1,
                "focal_source": "topdev",
                "dag_id": "crawler_detail_topdev",
                "scheduled_time": "20:00",
                "projected_quota": 250,
                "engine": "curl_cffi (TLS Impersonation)",
                "recrawl_strategy": "Safe Skip + Re-crawl 21 ngày",
            },
            {
                "day_of_week": "Thứ Ba",
                "day_index": 2,
                "focal_source": "careerviet",
                "dag_id": "crawler_detail_careerviet",
                "scheduled_time": "20:00",
                "projected_quota": 200,
                "engine": "curl_cffi (HTML Parser)",
                "recrawl_strategy": "Anti-403 + Fallback",
            },
            {
                "day_of_week": "Thứ Tư",
                "day_index": 3,
                "focal_source": "itviec",
                "dag_id": "crawler_detail_itviec",
                "scheduled_time": "20:00",
                "projected_quota": 200,
                "engine": "curl_cffi (Session Auth)",
                "recrawl_strategy": "JSON-LD & DOM Matcher",
            },
            {
                "day_of_week": "Thứ Năm",
                "day_index": 4,
                "focal_source": "vietnamworks",
                "dag_id": "crawler_detail_vietnamworks",
                "scheduled_time": "20:00",
                "projected_quota": 300,
                "engine": "curl_cffi (Algolia/API)",
                "recrawl_strategy": "IT Domain Filter",
            },
            {
                "day_of_week": "Thứ Sáu",
                "day_index": 5,
                "focal_source": "topcv",
                "dag_id": "crawler_detail_topcv",
                "scheduled_time": "20:00",
                "projected_quota": 350,
                "engine": "playwright (Headless Cloudflare)",
                "recrawl_strategy": "Two-Phase Discovery/Detail",
            },
            {
                "day_of_week": "Thứ Bảy",
                "day_index": 6,
                "focal_source": "vieclam24h",
                "dag_id": "crawler_detail_vieclam24h",
                "scheduled_time": "20:00",
                "projected_quota": 250,
                "engine": "curl_cffi (Mobile UA)",
                "recrawl_strategy": "Safe Skip + CDC Hash",
            },
            {
                "day_of_week": "Chủ Nhật",
                "day_index": 7,
                "focal_source": "glints",
                "dag_id": "crawler_detail_glints",
                "scheduled_time": "20:00",
                "projected_quota": 250,
                "engine": "curl_cffi + playwright",
                "recrawl_strategy": "Weekly Catch-up & Backup",
            },
        ]

        days = []
        total_projected = 0
        total_actual = 0

        for item in schedule_definition:
            src = item["focal_source"]
            st = self.get_source_status(src)
            actual_count = st["total_raw"] if st["total_raw"] > 0 else st["total_urls"]

            # Trường hợp Chủ Nhật bao gồm cả glints và jobsgo
            if src == "glints":
                st_jobsgo = self.get_source_status("jobsgo")
                actual_count += (st_jobsgo["total_raw"] if st_jobsgo["total_raw"] > 0 else st_jobsgo["total_urls"])

            quota = item["projected_quota"]
            total_projected += quota
            total_actual += actual_count

            progress = round((actual_count / max(quota, 1)) * 100, 1)

            if st["is_running"]:
                status = "ACTIVE_QUEUE"
            elif actual_count >= quota:
                status = "COMPLETED"
            else:
                status = "SCHEDULED"

            day_entry = dict(item)
            day_entry["actual_crawled"] = actual_count
            day_entry["progress_pct"] = progress
            day_entry["status"] = status
            days.append(day_entry)

        overall_pct = round((total_actual / max(total_projected, 1)) * 100, 1)

        return {
            "total_projected_weekly": total_projected,
            "total_actual_crawled": total_actual,
            "overall_progress_pct": overall_pct,
            "days": days,
            "generated_at": datetime.now().isoformat(),
        }


crawler_service = CrawlerService()
