"""
crawlers.common.checkpoint
~~~~~~~~~~~~~~~~~~~~~~~~~~
Quản lý checkpoint và crawler state để hỗ trợ:
- Deduplication: không cào lại các job ID đã thấy
- Resume: tiếp tục từ page/cursor trước đó khi crawler bị ngắt (interrupt / crash)
- State persistence: lưu trữ atomic dưới dạng JSON file
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Set

from crawlers.common.logger import get_logger

logger = get_logger("checkpoint")


class CheckpointManager:
    """Quản lý trạng thái crawler (checkpoint) lưu dưới dạng JSON.

    Attributes:
        source: Tên nguồn crawler (ví dụ: 'topdev', 'careerviet').
        checkpoint_dir: Thư mục chứa file checkpoint (default: data/checkpoints).
        file_path: Đường dẫn đầy đủ tới file checkpoint JSON.
        last_page: Trang gần nhất đã hoàn thành.
        seen_ids: Tập hợp các ID đã cào (set of str).
        total_collected: Tổng số item đã ghi nhận.
        extra: Dữ liệu tuỳ biến khác (cursor, offset, cookies, etc.).
    """

    def __init__(
        self,
        source: str,
        checkpoint_dir: Optional[str | Path] = None,
        checkpoint_filename: Optional[str] = None,
    ) -> None:
        """Khởi tạo CheckpointManager.

        Args:
            source: Tên nguồn crawler.
            checkpoint_dir: Thư mục lưu checkpoint. Mặc định 'data/checkpoints'.
            checkpoint_filename: Tên file tuỳ chọn (mặc định '{source}_checkpoint.json').
        """
        self.source = source.lower().strip()
        self.checkpoint_dir = Path(checkpoint_dir or "data/checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        filename = checkpoint_filename or f"{self.source}_checkpoint.json"
        self.file_path = self.checkpoint_dir / filename

        self.last_page: int = 0
        self.seen_ids: Set[str] = set()
        self.total_collected: int = 0
        self.last_updated_at: Optional[str] = None
        self.extra: dict[str, Any] = {}

        self.load()

    def load(self) -> bool:
        """Đọc checkpoint từ disk nếu tồn tại.

        Returns:
            True nếu đọc thành công, False nếu file chưa tồn tại hoặc lỗi.
        """
        if not self.file_path.exists():
            logger.debug("[%s] Không tìm thấy file checkpoint tại %s, khởi tạo state mới", self.source, self.file_path)
            return False

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.last_page = data.get("last_page", 0)
            self.seen_ids = set(data.get("seen_ids", []))
            self.total_collected = data.get("total_collected", len(self.seen_ids))
            self.last_updated_at = data.get("last_updated_at")
            self.extra = data.get("extra", {})

            logger.info(
                "[%s] Đã nạp checkpoint: last_page=%d, seen_ids=%d",
                self.source,
                self.last_page,
                len(self.seen_ids),
            )
            return True
        except Exception as exc:
            logger.warning("[%s] Lỗi khi đọc checkpoint %s: %s", self.source, self.file_path, exc)
            return False

    def save(self) -> None:
        """Lưu state hiện tại vào file JSON một cách an toàn (atomic write qua temp file)."""
        self.last_updated_at = datetime.now(timezone.utc).isoformat()
        state = {
            "source": self.source,
            "last_page": self.last_page,
            "total_collected": self.total_collected,
            "seen_ids": sorted(list(self.seen_ids)),
            "last_updated_at": self.last_updated_at,
            "extra": self.extra,
        }

        # Atomic write: ghi ra file tạm rồi rename để tránh corrupt nếu bị crash giữa chừng
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self.checkpoint_dir),
            prefix=f"{self.source}_ckpt_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.file_path)
        except Exception as exc:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            logger.error("[%s] Gặp lỗi khi lưu checkpoint: %s", self.source, exc)
            raise

    def is_seen(self, item_id: str) -> bool:
        """Kiểm tra xem item_id đã được crawl trước đó hay chưa.

        Args:
            item_id: Mã ID định danh của job.

        Returns:
            True nếu đã thấy, False nếu chưa.
        """
        return str(item_id).strip() in self.seen_ids

    def mark_seen(self, item_id: str) -> bool:
        """Đánh dấu một ID là đã cào.

        Args:
            item_id: Mã ID của job.

        Returns:
            True nếu item mới được thêm vào, False nếu đã có sẵn.
        """
        clean_id = str(item_id).strip()
        if clean_id not in self.seen_ids:
            self.seen_ids.add(clean_id)
            self.total_collected += 1
            return True
        return False

    def update_page(self, page: int, auto_save: bool = False) -> None:
        """Cập nhật trang hiện tại.

        Args:
            page: Số thứ tự trang vừa hoàn thành.
            auto_save: Có lưu ngay vào disk hay không.
        """
        self.last_page = page
        if auto_save:
            self.save()

    def set_extra(self, key: str, value: Any, auto_save: bool = False) -> None:
        """Lưu thêm thông tin tuỳ biến vào checkpoint."""
        self.extra[key] = value
        if auto_save:
            self.save()

    def get_extra(self, key: str, default: Any = None) -> Any:
        """Lấy thông tin tuỳ biến từ checkpoint."""
        return self.extra.get(key, default)

    def reset(self) -> None:
        """Xoá toàn bộ state và xoá file checkpoint trên disk nếu có."""
        self.last_page = 0
        self.seen_ids.clear()
        self.total_collected = 0
        self.last_updated_at = None
        self.extra.clear()
        if self.file_path.exists():
            try:
                self.file_path.unlink()
                logger.info("[%s] Đã reset và xoá file checkpoint %s", self.source, self.file_path)
            except OSError as exc:
                logger.warning("[%s] Không thể xoá checkpoint %s: %s", self.source, self.file_path, exc)
