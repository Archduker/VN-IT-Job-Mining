"""
pipeline.py - Module quản lý trạng thái, khử trùng lặp & xuất JSON
Bao gồm: Checkpoint management, Deduplication, JSON export.
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# CHECKPOINT MANAGER
# ============================================================

class CheckpointManager:
    """
    Quản lý trạng thái crawl để recovery khi crash/gián đoạn.

    Structure của checkpoint.json:
    {
        "crawled_urls": [...],        # URL đã crawl chi tiết thành công
        "queued_urls": {              # URL đang chờ crawl theo category
            "CNTT - Phần mềm": [...],
            ...
        },
        "completed_categories": [...], # Danh mục đã lấy xong URL listing
        "last_updated": "ISO-timestamp",
        "stats": { "total": 0, "success": 0, "error": 0 }
    }
    """

    def __init__(self, checkpoint_path: str):
        self.path = checkpoint_path
        self._data = self._load()

    # ---- Load / Save ----------------------------------------

    def _load(self) -> dict:
        """Load checkpoint từ file nếu tồn tại."""
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"[Checkpoint] Đã load checkpoint: {self.path}")
                logger.info(
                    f"[Checkpoint] Tiến độ cũ → "
                    f"Đã cào: {len(data.get('crawled_urls', []))} URL | "
                    f"Danh mục hoàn thành: {data.get('completed_categories', [])}"
                )
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"[Checkpoint] File hỏng, tạo mới: {e}")

        return self._empty_state()

    def save(self):
        """Ghi checkpoint xuống disk (atomic write)."""
        self._data["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp_path = self.path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            # Atomic rename
            os.replace(tmp_path, self.path)
        except IOError as e:
            logger.error(f"[Checkpoint] Không thể lưu: {e}")

    @staticmethod
    def _empty_state() -> dict:
        return {
            "crawled_urls":          [],
            "queued_urls":           {},
            "completed_categories":  [],
            "last_updated":          None,
            "stats": {
                "total":   0,
                "success": 0,
                "error":   0,
            },
        }

    # ---- Query / Update ------------------------------------

    def is_url_crawled(self, url: str) -> bool:
        """Kiểm tra URL đã được cào chi tiết chưa."""
        return url in self._data["crawled_urls"]

    def mark_url_crawled(self, url: str, success: bool = True):
        """Đánh dấu URL đã cào xong."""
        if url not in self._data["crawled_urls"]:
            self._data["crawled_urls"].append(url)
        self._data["stats"]["total"] += 1
        if success:
            self._data["stats"]["success"] += 1
        else:
            self._data["stats"]["error"] += 1

    def get_queued_urls(self, category: str) -> list[str]:
        """Lấy danh sách URL chờ cào của một danh mục."""
        return self._data["queued_urls"].get(category, [])

    def set_queued_urls(self, category: str, urls: list[str]):
        """Lưu danh sách URL của danh mục vào checkpoint."""
        self._data["queued_urls"][category] = urls
        self.save()

    def add_queued_urls(self, category: str, new_urls: list[str]):
        """Append thêm URL vào queue của danh mục."""
        existing = set(self._data["queued_urls"].get(category, []))
        added = [u for u in new_urls if u not in existing]
        self._data["queued_urls"].setdefault(category, []).extend(added)

    def is_category_listing_done(self, category: str) -> bool:
        """Kiểm tra đã lấy hết URL listing của danh mục chưa."""
        return category in self._data["completed_categories"]

    def mark_category_listing_done(self, category: str):
        """Đánh dấu danh mục đã lấy xong toàn bộ URL listing."""
        if category not in self._data["completed_categories"]:
            self._data["completed_categories"].append(category)
        self.save()

    @property
    def stats(self) -> dict:
        return self._data["stats"]

    def get_all_queued_urls(self) -> dict:
        return self._data["queued_urls"]

    @property
    def crawled_count(self) -> int:
        return len(self._data["crawled_urls"])


# ============================================================
# DEDUPLICATOR
# ============================================================

class Deduplicator:
    """
    Khử trùng lặp dữ liệu job dựa trên job_id hoặc URL hash.
    Hỗ trợ in-memory set + persist xuống checkpoint.
    """

    def __init__(self):
        self._seen_ids: set[str] = set()

    def load_from_checkpoint(self, checkpoint: CheckpointManager):
        """Load các job_id đã thấy từ checkpoint (tránh trùng sau restart)."""
        for url in checkpoint._data.get("crawled_urls", []):
            self._seen_ids.add(self._url_to_id(url))

    def load_from_existing_output(self, output_path: str):
        """Load job_id từ file JSON output đã có (resume mode)."""
        if not os.path.exists(output_path):
            return
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_jobs = json.load(f)
            for job in existing_jobs:
                jid = job.get("job_id", "")
                if jid:
                    self._seen_ids.add(jid)
            logger.info(f"[Dedup] Đã load {len(self._seen_ids)} job_id từ output cũ.")
        except Exception as e:
            logger.warning(f"[Dedup] Không đọc được output cũ: {e}")

    def is_duplicate(self, job_record: dict) -> bool:
        """Kiểm tra job_record có bị trùng không."""
        jid = job_record.get("job_id", "")
        if not jid:
            jid = self._url_to_id(job_record.get("url", ""))
        return jid in self._seen_ids

    def mark_seen(self, job_record: dict):
        """Đánh dấu job đã thấy."""
        jid = job_record.get("job_id", "")
        if not jid:
            jid = self._url_to_id(job_record.get("url", ""))
        self._seen_ids.add(jid)

    @staticmethod
    def _url_to_id(url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:8].upper()

    @property
    def seen_count(self) -> int:
        return len(self._seen_ids)


# ============================================================
# OUTPUT MANAGER
# ============================================================

class OutputManager:
    """
    Ghi/Đọc dữ liệu job ra file JSON với cơ chế atomic write
    và streaming append để tránh mất dữ liệu khi crash.
    """

    def __init__(self, output_path: str):
        self.path = output_path
        self._buffer: list[dict] = []
        self._flush_interval = 10  # Flush mỗi 10 record
        self._total_written = 0

    def load_existing(self) -> list[dict]:
        """Đọc dữ liệu đã ghi trước đó (dùng khi resume)."""
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._total_written = len(data)
            logger.info(f"[Output] Đã load {self._total_written} record từ file cũ.")
            return data
        except Exception as e:
            logger.warning(f"[Output] Không đọc được file cũ: {e}")
            return []

    def append(self, job_record: dict, existing_data: list[dict]):
        """
        Thêm 1 record vào buffer và flush định kỳ.
        existing_data là list hiện tại (được quản lý bởi caller).
        """
        self._buffer.append(job_record)
        if len(self._buffer) >= self._flush_interval:
            self.flush(existing_data)

    def flush(self, all_data: list[dict]):
        """Ghi toàn bộ all_data xuống file (atomic)."""
        if not all_data:
            return
        tmp_path = self.path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
            self._total_written = len(all_data)
            self._buffer.clear()
            logger.debug(f"[Output] Đã flush {self._total_written} records.")
        except IOError as e:
            logger.error(f"[Output] Lỗi khi ghi file: {e}")

    @property
    def total_written(self) -> int:
        return self._total_written


# ============================================================
# ERROR LOGGER
# ============================================================

class ErrorLogger:
    """Ghi log các URL bị lỗi ra file riêng."""

    def __init__(self, log_path: str):
        self.path = log_path

    def log(self, url: str, error: str, category: str = ""):
        """Ghi một dòng lỗi."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"[{timestamp}] [{category}] ERROR: {url} | {error}\n"
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        except IOError:
            pass  # Không để lỗi logger phá vỡ main flow


# ============================================================
# STATS REPORTER
# ============================================================

class StatsReporter:
    """Thu thập và in báo cáo thống kê cuối quá trình."""

    def __init__(self):
        self._category_stats: dict[str, dict] = {}
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None

    def start(self):
        self._start_time = datetime.now()

    def stop(self):
        self._end_time = datetime.now()

    def record(self, category: str, success: bool):
        if category not in self._category_stats:
            self._category_stats[category] = {"success": 0, "error": 0}
        if success:
            self._category_stats[category]["success"] += 1
        else:
            self._category_stats[category]["error"] += 1

    def print_report(self):
        """In báo cáo tổng kết ra console."""
        elapsed = ""
        if self._start_time and self._end_time:
            delta = self._end_time - self._start_time
            h, rem = divmod(int(delta.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            elapsed = f"{h:02d}:{m:02d}:{s:02d}"

        total_success = sum(v["success"] for v in self._category_stats.values())
        total_error   = sum(v["error"]   for v in self._category_stats.values())

        print("\n" + "=" * 60)
        print("     CAREERVIET SCRAPER - BÁO CÁO KẾT QUẢ")
        print("=" * 60)
        print(f"  Thời gian chạy : {elapsed}")
        print(f"  Tổng thu thập  : {total_success} jobs")
        print(f"  Tổng lỗi       : {total_error} jobs")
        print("-" * 60)
        print("  Chi tiết theo danh mục:")
        for cat, stats in self._category_stats.items():
            print(f"    • {cat:<45} ✓ {stats['success']:>4}  ✗ {stats['error']:>3}")
        print("=" * 60 + "\n")
