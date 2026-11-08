# -*- coding: utf-8 -*-
"""Service điều phối và giám sát tiến trình Crawler (Subprocess Runner & SSE Streamer)."""

import asyncio
from datetime import datetime, time, timedelta, timezone
import logging
import os
import sys
from typing import Any, AsyncGenerator, Dict, Optional

from app.core.config import settings
from collection.common.adaptive_router import COOLDOWN_MINUTES_SURGE, MAX_ITEMS_PER_BATCH, VN_TZ
from collection.common.detail_schedule import WEEKDAY_SLOT_HOURS, WEEKEND_SLOT_HOURS

logger = logging.getLogger("crawler_service")


# Lịch Phase 2 lấy từ collection/common/detail_schedule.py, dùng chung với DAG và router.
DISCOVERY_SCHEDULE_TIME = "05:00 hằng ngày"


def _hours(hours) -> str:
    return ", ".join(f"{h:02d}" for h in hours) + "h"


DETAIL_SCHEDULE_TIME = (
    f"T2–T6: {_hours(WEEKDAY_SLOT_HOURS[:1])}"
    + (f" ({_hours(WEEKDAY_SLOT_HOURS[1:])} nếu ca trước bỏ qua)" if len(WEEKDAY_SLOT_HOURS) > 1 else "")
    + f" · T7, CN: {_hours(WEEKEND_SLOT_HOURS)}"
)


def next_detail_slot(now_vn: datetime) -> datetime:
    """Ca Phase 2 kế tiếp mà router cho phép chạy, theo giờ Việt Nam."""
    for offset in range(8):
        day = (now_vn + timedelta(days=offset)).date()
        slots = WEEKEND_SLOT_HOURS if day.weekday() >= 5 else WEEKDAY_SLOT_HOURS
        for hour in slots:
            slot = datetime.combine(day, time(hour), tzinfo=VN_TZ)
            if slot > now_vn:
                return slot
    raise RuntimeError("Không tìm được ca kế tiếp")


def _run_status(state: Optional[str]) -> str:
    """Đổi trạng thái Airflow sang nhãn bảng lịch."""
    if state == "success":
        return "SUCCESS"
    if state in ("failed", "upstream_failed"):
        return "FAILED"
    if state in ("running", "queued"):
        return "RUNNING"
    return "SCHEDULED"


def _discovery_status(states: Optional[Dict[str, Optional[str]]], task_id: str) -> str:
    """Đổi trạng thái task Airflow sang nhãn bảng Phase 1; không đọc được thì trả UNKNOWN."""
    if states is None or task_id not in states:
        return "UNKNOWN"
    return _run_status(states[task_id])


class CrawlerService:
    """Quản lý các tiến trình chạy crawler và stream log console thời gian thực."""

    def __init__(self):
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.log_buffers: Dict[str, list] = {}
        self.log_dropped: Dict[str, int] = {}
        self.log_done: Dict[str, bool] = {}  # True khi read_stream đã ghi dòng exit code
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
        sync_r2: bool = True,
    ) -> Dict[str, Any]:
        """Kích hoạt crawler nguồn chỉ định qua subprocess run.py.

        sync_r2 mặc định bật: chạy mà không đồng bộ thì raw và ledger chỉ nằm trên máy, lần chạy sau lệch (SCRAPE-4).
        """
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
        if sync_r2:
            cmd.append("--sync-r2")

        self.log_buffers[source] = []
        self.log_dropped[source] = 0
        self.log_done[source] = False
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
            self.log_done[source] = True

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
            # Đọc trạng thái trước khi gửi, để dòng nào ghi trước lúc read_stream xong cũng được gửi
            proc = self.active_processes.get(source)
            finished = proc is not None and proc.returncode is not None and self.log_done.get(source, True)

            buffer = self.log_buffers.get(source, [])
            dropped = self.log_dropped.get(source, 0)
            start = max(sent - dropped, 0)
            chunk = buffer[start:]  # chụp lại trước khi yield; buffer có thể dài thêm trong lúc gửi
            for line in chunk:
                yield line.rstrip("\r\n")
            sent = dropped + start + len(chunk)

            if proc is None:
                yield "[EOF] Nguồn này chưa có tiến trình đang chạy."
                break
            if finished:
                yield "[EOF] Quá trình cào đã hoàn tất."
                break

            await asyncio.sleep(0.5)

    def get_weekly_crawl_schedule(self) -> Dict[str, Any]:
        """Lịch 2 pha theo đúng DAG và AdaptiveWorkloadRouter, trạng thái lấy từ Airflow."""
        from app.services.airflow_service import airflow_service
        from app.services.ledger_service import ledger_service

        discovery_states = airflow_service.get_latest_discovery_states()
        history = airflow_service.get_run_history(days=14)
        latest_runs: Dict[str, Dict[str, Any]] = {}
        for run in history or []:
            latest_runs[run["dag_id"]] = run  # history đã sắp theo start_date tăng dần

        phase1_discovery = []
        phase2_detail = []
        total_actual = 0
        total_backlog = 0

        for src in settings.SUPPORTED_SOURCES:
            st = self.get_source_status(src)
            ledger_st = ledger_service.get_ledger_summary(src)
            # Router xả PENDING và tin đến hạn cào lại, gồm cả DONE từ 21 ngày (UrlLedger.get_queue_summary)
            queue = ledger_service.get_queue_summary(src)
            backlog = queue["pending"] + queue["recheck_due"]
            total_actual += st["total_raw"]
            total_backlog += backlog

            phase1_discovery.append({
                "focal_source": src,
                "dag_id": "dag_discovery_daily",
                "task_id": f"discover_{src}",
                "scheduled_time": DISCOVERY_SCHEDULE_TIME,
                "quota_pages": 2,
                "total_discovered": ledger_st.get("total", 0),
                "status": _discovery_status(discovery_states, f"discover_{src}"),
            })

            dag_id = f"crawler_detail_{src}"
            run = latest_runs.get(dag_id)
            if st["is_running"]:
                status = "RUNNING"
            elif history is None:
                status = "UNKNOWN"
            else:
                status = _run_status(run["state"] if run else None)
            phase2_detail.append({
                "focal_source": src,
                "dag_id": dag_id,
                "scheduled_time": DETAIL_SCHEDULE_TIME,
                "batch_limit": MAX_ITEMS_PER_BATCH,
                "actual_crawled": st["total_raw"],
                "uncrawled_pending": backlog,
                "batches_needed": -(-backlog // MAX_ITEMS_PER_BATCH),
                "last_run_start": run["start_date"].isoformat() if run and run.get("start_date") else None,
                "engine": st["engine"],
                "status": status,
            })

        return {
            "phase1_discovery": phase1_discovery,
            "phase2_detail": phase2_detail,
            "airflow_available": history is not None,
            "batch_limit": MAX_ITEMS_PER_BATCH,
            "cooldown_minutes": COOLDOWN_MINUTES_SURGE,
            "next_detail_slot": next_detail_slot(datetime.now(VN_TZ)).isoformat(),
            "total_actual_crawled": total_actual,
            "total_uncrawled_pending": total_backlog,
            "days": phase2_detail,  # backward compatibility
            "generated_at": datetime.now().isoformat(),
        }

crawler_service = CrawlerService()
