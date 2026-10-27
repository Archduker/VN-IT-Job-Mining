# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.checkpoint_store
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Lưu trữ và phục hồi tiến trình chạy bất đồng bộ theo định dạng JSON Lines (.jsonl).

Mục tiêu kỹ thuật:
  - Append-only an toàn (atomic flush sau mỗi dòng).
  - Tải nhanh danh sách các job_id_global đã hoàn tất (load_completed_ids).
  - Khôi phục nguyên vẹn 100% dữ liệu đã chạy khi bị đứt mạng hoặc khởi động lại.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("CheckpointStore")

DEFAULT_CHECKPOINT_PATH = Path("data/staging/gemini_checkpoint.jsonl")


class CheckpointStore:
    """Quản lý tệp Checkpoint dạng JSON Lines."""

    def __init__(self, checkpoint_path: Path | str = DEFAULT_CHECKPOINT_PATH):
        self.checkpoint_path = Path(checkpoint_path)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._completed_ids: Optional[Set[str]] = None

    def get_processed_ids(self) -> Set[str]:
        """Alias cho load_completed_ids."""
        return self.load_completed_ids()

    def append(self, record: Dict[str, Any]) -> None:
        """Alias cho append_record."""
        return self.append_record(record)

    def load_all(self) -> List[Dict[str, Any]]:
        """Alias cho load_all_records."""
        return self.load_all_records()

    def load_completed_ids(self) -> Set[str]:
        """Đọc và trả về tập hợp các job_id_global đã lưu thành công trong checkpoint."""
        if self._completed_ids is not None:
            return set(self._completed_ids)

        completed: Set[str] = set()
        if not self.checkpoint_path.is_file():
            self._completed_ids = completed
            return completed

        with self.checkpoint_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    data = json.loads(clean_line)
                    jid = data.get("job_id_global")
                    if jid:
                        completed.add(jid)
                except Exception as exc:
                    logger.warning("Bỏ qua dòng %d bị lỗi cú pháp JSON trong checkpoint: %s", line_no, exc)

        self._completed_ids = completed
        logger.info("Đã nạp %d ID đã xử lý từ Checkpoint (%s)", len(completed), self.checkpoint_path)
        return set(self._completed_ids)

    def append_record(self, record: Dict[str, Any]) -> None:
        """Ghi nối tiếp một bản ghi vào tệp checkpoint và flush lập tức."""
        if not isinstance(record, dict):
            raise TypeError("record phải là dict")

        line = json.dumps(record, ensure_ascii=False)
        with self.checkpoint_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()

        jid = record.get("job_id_global")
        if jid:
            if self._completed_ids is None:
                self._completed_ids = set()
            self._completed_ids.add(jid)

    def load_all_records(self) -> List[Dict[str, Any]]:
        """Nạp toàn bộ các bản ghi trong checkpoint dưới dạng danh sách dict."""
        records: List[Dict[str, Any]] = []
        if not self.checkpoint_path.is_file():
            return records

        with self.checkpoint_path.open("r", encoding="utf-8") as f:
            for line in f:
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    records.append(json.loads(clean_line))
                except Exception:
                    pass
        return records

    def count(self) -> int:
        """Đếm số lượng bản ghi hiện có trong checkpoint."""
        return len(self.load_completed_ids())

    def clear(self) -> None:
        """Xóa trắng checkpoint (chỉ dùng cho testing hoặc reset)."""
        if self.checkpoint_path.is_file():
            self.checkpoint_path.unlink()
        self._completed_ids = set()
