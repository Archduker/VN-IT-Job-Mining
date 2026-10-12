# -*- coding: utf-8 -*-
"""
crawlers.common.job_catalog
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Quản lý trạng thái vòng đời tin tuyển dụng (State Catalog) và Hàng đợi (Queue)
với định danh (source, job_id) ánh xạ 1-1 tới job_url.

Cung cấp:
- Kiểm tra trùng lặp siêu tốc O(1) qua SQLite.
- Quản lý trạng thái: DISCOVERED, SUCCESS, FAILED_RETRY_NEXT_RUN.
- Next-Run Deferred Retry: Tự động gom các tin lỗi kỳ trước vào hàng đợi để cào bù.
- Theo dõi first_seen_at và last_seen_at để phục vụ phát hiện tin hết hạn.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from crawlers.common.logger import get_logger

logger = get_logger("job_catalog")

STATUS_DISCOVERED = "DISCOVERED"
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED_RETRY = "FAILED_RETRY_NEXT_RUN"


class JobStateCatalog:
    """Quản lý trạng thái vòng đời công việc và phân bổ hàng đợi cào chi tiết."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        """Khởi tạo kết nối SQLite và tạo schema nếu chưa có."""
        self.db_path = Path(db_path or "data/state/job_catalog.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Khởi tạo bảng job_state_catalog."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS job_state_catalog (
                    source            TEXT NOT NULL,
                    job_id            TEXT NOT NULL,
                    job_url           TEXT NOT NULL,
                    first_seen_at     TEXT NOT NULL,
                    last_seen_at      TEXT NOT NULL,
                    crawl_status      TEXT NOT NULL,
                    retry_count       INTEGER DEFAULT 0,
                    last_error        TEXT,
                    output_batch_path TEXT,
                    PRIMARY KEY (source, job_id)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_source_status ON job_state_catalog (source, crawl_status)"
            )
            conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def register_harvested_jobs(
        self,
        source: str,
        harvested_items: list[dict[str, str]],
    ) -> tuple[list[dict[str, Any]], int]:
        """Tiếp nhận danh sách (job_id, job_url) thu hoạch từ Full Listing,
        lọc trùng lặp và trả về danh sách thực sự cần cào chi tiết.

        Args:
            source: Tên nguồn tuyển dụng (e.g., 'topcv', 'itviec').
            harvested_items: Danh sách dict [{'job_id': '...', 'job_url': '...'}, ...].

        Returns:
            Tuple (queue_items, skipped_count):
                - queue_items: Danh sách các jobs cần cào chi tiết (tin mới hoặc tin lỗi kỳ trước).
                - skipped_count: Số tin đã crawl thành công từ trước, được bỏ qua.
        """
        source_key = source.lower().strip()
        now_ts = self._now_iso()
        queue_items: list[dict[str, Any]] = []
        skipped_count = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for item in harvested_items:
                raw_id = str(item.get("job_id", "")).strip()
                raw_url = str(item.get("job_url", "")).strip()
                if not raw_id or not raw_url:
                    continue

                cursor.execute(
                    "SELECT crawl_status, retry_count FROM job_state_catalog WHERE source = ? AND job_id = ?",
                    (source_key, raw_id),
                )
                row = cursor.fetchone()

                if row is None:
                    # Tin mới tinh -> Lưu DISCOVERED và đẩy vào Queue
                    cursor.execute(
                        """
                        INSERT INTO job_state_catalog 
                        (source, job_id, job_url, first_seen_at, last_seen_at, crawl_status, retry_count)
                        VALUES (?, ?, ?, ?, ?, ?, 0)
                        """,
                        (source_key, raw_id, raw_url, now_ts, now_ts, STATUS_DISCOVERED),
                    )
                    queue_items.append({
                        "source": source_key,
                        "job_id": raw_id,
                        "job_url": raw_url,
                        "dispatch_reason": "NEW_DISCOVERED",
                        "retry_count": 0,
                    })
                else:
                    status = row["crawl_status"]
                    retries = row["retry_count"]

                    if status == STATUS_SUCCESS:
                        # Đã cào thành công -> Bỏ qua, chỉ cập nhật last_seen_at
                        cursor.execute(
                            "UPDATE job_state_catalog SET last_seen_at = ? WHERE source = ? AND job_id = ?",
                            (now_ts, source_key, raw_id),
                        )
                        skipped_count += 1
                    elif status == STATUS_FAILED_RETRY:
                        # Kỳ trước bị lỗi -> Đẩy vào Queue cào bù
                        cursor.execute(
                            "UPDATE job_state_catalog SET last_seen_at = ? WHERE source = ? AND job_id = ?",
                            (now_ts, source_key, raw_id),
                        )
                        queue_items.append({
                            "source": source_key,
                            "job_id": raw_id,
                            "job_url": raw_url,
                            "dispatch_reason": "RETRY_PREVIOUS_FAILURE",
                            "retry_count": retries,
                        })
                    else:  # DISCOVERED nhưng chưa xong (dở dang)
                        queue_items.append({
                            "source": source_key,
                            "job_id": raw_id,
                            "job_url": raw_url,
                            "dispatch_reason": "PENDING_DISCOVERED",
                            "retry_count": retries,
                        })

            conn.commit()

        logger.info(
            "[%s] Phân bổ Hàng đợi hoàn tất: %d tin cần cào (Mới/Retry), %d tin trùng lặp đã bỏ qua",
            source_key,
            len(queue_items),
            skipped_count,
        )
        return queue_items, skipped_count

    def mark_job_success(
        self,
        source: str,
        job_id: str,
        output_batch_path: Optional[str] = None,
    ) -> None:
        """Đánh dấu job đã cào chi tiết thành công."""
        source_key = source.lower().strip()
        job_id_clean = str(job_id).strip()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE job_state_catalog
                SET crawl_status = ?,
                    output_batch_path = COALESCE(?, output_batch_path),
                    last_error = NULL
                WHERE source = ? AND job_id = ?
                """,
                (STATUS_SUCCESS, output_batch_path, source_key, job_id_clean),
            )
            conn.commit()

    def mark_job_failed_for_next_run(
        self,
        source: str,
        job_id: str,
        error_msg: str,
    ) -> None:
        """Đánh dấu job thất bại trong phiên, hoãn lại sang chu kỳ chạy tiếp theo để cào bù."""
        source_key = source.lower().strip()
        job_id_clean = str(job_id).strip()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE job_state_catalog
                SET crawl_status = ?,
                    retry_count = retry_count + 1,
                    last_error = ?
                WHERE source = ? AND job_id = ?
                """,
                (STATUS_FAILED_RETRY, str(error_msg)[:500], source_key, job_id_clean),
            )
            conn.commit()

        logger.warning(
            "[%s] Job %s ghi nhận hoãn cào (FAILED_RETRY_NEXT_RUN): %s",
            source_key,
            job_id_clean,
            error_msg,
        )

    def get_failed_retry_jobs(self, source: Optional[str] = None) -> list[dict[str, Any]]:
        """Lấy danh sách các jobs đang chờ cào bù cho chu kỳ kế tiếp."""
        query = "SELECT * FROM job_state_catalog WHERE crawl_status = ?"
        params: list[Any] = [STATUS_FAILED_RETRY]

        if source:
            query += " AND source = ?"
            params.append(source.lower().strip())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]

    def get_catalog_stats(self, source: Optional[str] = None) -> dict[str, int]:
        """Lấy thống kê tổng quan trạng thái trong Catalog."""
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN crawl_status = 'SUCCESS' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN crawl_status = 'FAILED_RETRY_NEXT_RUN' THEN 1 ELSE 0 END) as failed_retry_count,
                SUM(CASE WHEN crawl_status = 'DISCOVERED' THEN 1 ELSE 0 END) as discovered_count
            FROM job_state_catalog
        """
        params: tuple[Any, ...] = ()
        if source:
            query += " WHERE source = ?"
            params = (source.lower().strip(),)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            if row:
                return {
                    "total": row["total"] or 0,
                    "success": row["success_count"] or 0,
                    "failed_retry": row["failed_retry_count"] or 0,
                    "discovered": row["discovered_count"] or 0,
                }
            return {"total": 0, "success": 0, "failed_retry": 0, "discovered": 0}

    def sync_from_batches(
        self,
        data_dir: str | Path = "data",
        source: Optional[str] = None,
    ) -> dict[str, Any]:
        """Đồng bộ hóa dữ liệu lịch sử từ các file batch_*.json đã cào trên đĩa
        vào JobStateCatalog với trạng thái SUCCESS.

        Args:
            data_dir: Thư mục gốc chứa dữ liệu các nguồn (mặc định 'data').
            source: Nguồn cụ thể cần đồng bộ, hoặc None để đồng bộ tất cả.

        Returns:
            Dict tổng hợp: {
                "total_synced": int,
                "files_scanned": int,
                "by_source": dict[str, int],
            }
        """
        import json

        base_path = Path(data_dir)
        pattern = f"{source}/**/batch_*.json" if source else "**/batch_*.json"
        batch_files = sorted(base_path.glob(pattern))

        total_synced = 0
        by_source: dict[str, int] = {}
        now_ts = self._now_iso()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for bf in batch_files:
                try:
                    with open(bf, "r", encoding="utf-8") as f:
                        records = json.load(f)
                except Exception as exc:
                    logger.warning("Không thể đọc file batch %s: %s", bf, exc)
                    continue

                if not isinstance(records, list):
                    continue

                rel_batch_path = str(bf)

                for rec in records:
                    meta = rec.get("_meta", {})
                    src = (meta.get("source") or "").lower().strip()
                    job_id = str(meta.get("source_job_id") or meta.get("id") or "").strip()
                    job_url = meta.get("url") or meta.get("job_url") or ""
                    scraped_at = meta.get("scraped_at") or now_ts

                    if not src or not job_id:
                        continue

                    cursor.execute(
                        """
                        INSERT INTO job_state_catalog (
                            source, job_id, job_url, first_seen_at, last_seen_at,
                            crawl_status, retry_count, last_error, output_batch_path
                        ) VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?)
                        ON CONFLICT(source, job_id) DO UPDATE SET
                            crawl_status = excluded.crawl_status,
                            output_batch_path = excluded.output_batch_path,
                            last_seen_at = excluded.last_seen_at
                        """,
                        (src, job_id, job_url, scraped_at, scraped_at, STATUS_SUCCESS, rel_batch_path),
                    )
                    total_synced += 1
                    by_source[src] = by_source.get(src, 0) + 1

            conn.commit()

        logger.info(
            "Đồng bộ hóa State Catalog hoàn tất: %d jobs từ %d files. Chi tiết: %s",
            total_synced,
            len(batch_files),
            by_source,
        )
        return {
            "total_synced": total_synced,
            "files_scanned": len(batch_files),
            "by_source": by_source,
        }

