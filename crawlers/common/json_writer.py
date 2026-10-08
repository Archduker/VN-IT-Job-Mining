"""
crawlers.common.json_writer
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Ghi dữ liệu JSON an toàn dạng mảng [ ... ], tuân thủ schema và cấu trúc phân vùng:
`data/<source>/dt=YYYY-MM-DD/batch_XXX.json`

Sử dụng kỹ thuật Atomic Write:
1. Giữ records trong buffer bộ nhớ (self.records = []).
2. Khi flush/close, ghi toàn bộ mảng ra file tạm .json.tmp với indent=2, ensure_ascii=False,
   rồi dùng os.replace đổi tên thành .json để đảm bảo an toàn tuyệt đối, không lo corrupt file khi crash/mất điện.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Optional, Union

from crawlers.common.logger import get_logger
from crawlers.common.schema import JobRecord, validate_record

logger = get_logger("json_writer")


class JsonWriter:
    """Class hỗ trợ ghi JobRecord vào file JSON dạng mảng [ ... ] với schema validation và tự động phân vùng.

    Attributes:
        source: Nguồn crawl (ví dụ: 'topdev').
        output_dir: Thư mục gốc lưu trữ dữ liệu (mặc định: 'data').
        run_date: Ngày chạy dùng cho partition dt=YYYY-MM-DD (mặc định: hôm nay).
        batch_seq: Số thứ tự batch (mặc định: 1).
        file_path: Đường dẫn đầy đủ tới file JSON đích.
        records: Danh sách bản ghi dạng dict trong bộ nhớ.
        records_written: Số bản ghi đã ghi thành công.
        bytes_written: Tổng số byte của file JSON trên đĩa.
        flush_per_record: Ghi flush mảng JSON ra đĩa ngay sau mỗi bản ghi.
        validate_schema: Kiểm tra tính hợp lệ của bản ghi trước khi ghi.
        indent: Indent cho file JSON (mặc định: 2).
    """

    def __init__(
        self,
        source: str,
        output_dir: Optional[str | Path] = None,
        run_date: Optional[date] = None,
        batch_seq: int = 1,
        filename_override: Optional[str] = None,
        flush_per_record: bool = True,
        validate_schema: bool = True,
        indent: int = 2,
    ) -> None:
        """Khởi tạo JsonWriter.

        Args:
            source: Tên nguồn crawler (ví dụ: 'topdev').
            output_dir: Thư mục gốc lưu dữ liệu. Default: 'data'.
            run_date: Ngày chạy phân vùng. Default: date.today().
            batch_seq: Số thứ tự batch (1 -> batch_001.json).
            filename_override: Ghi đè tên file nếu muốn đặt tên riêng.
            flush_per_record: Flush mảng JSON xuống đĩa ngay sau mỗi bản ghi.
            validate_schema: Kiểm tra tính hợp lệ của bản ghi trước khi ghi.
            indent: Số khoảng trắng thụt lề JSON (mặc định: 2).
        """
        self.source = source.lower().strip()
        self.run_date = run_date or date.today()
        self.batch_seq = batch_seq
        self.flush_per_record = flush_per_record
        self.validate_schema = validate_schema
        self.indent = indent

        base_dir = Path(output_dir or "data")
        partition_dir = base_dir / self.source / f"dt={self.run_date.isoformat()}"
        partition_dir.mkdir(parents=True, exist_ok=True)

        filename = filename_override or f"batch_{self.batch_seq:03d}.json"
        self.file_path = partition_dir / filename

        self.records: list[dict[str, Any]] = []

        # Nếu file đã tồn tại và hợp lệ, nạp dữ liệu cũ để tiếp tục ghi (hỗ trợ append)
        if self.file_path.exists() and self.file_path.stat().st_size > 0:
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if isinstance(existing, list):
                        self.records = existing
            except Exception as exc:
                logger.warning("[%s] Không thể đọc file JSON hiện có %s: %s", self.source, self.file_path, exc)

        self.records_written: int = len(self.records)
        self.bytes_written: int = self.file_path.stat().st_size if self.file_path.exists() else 0
        self._closed: bool = False

    def open(self) -> "JsonWriter":
        """Mở writer (đảm bảo thư mục đích tồn tại)."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        return self

    def write(self, record: Union[JobRecord, dict[str, Any]]) -> bool:
        """Ghi một JobRecord (hoặc dict) vào mảng JSON.

        Args:
            record: Đối tượng JobRecord hoặc dict thỏa mãn schema.

        Returns:
            True nếu ghi thành công, False nếu thất bại do schema validation hoặc ghi lỗi.
        """
        if self._closed:
            raise ValueError("Không thể ghi vào JsonWriter đã đóng")

        # Validate schema
        if isinstance(record, JobRecord):
            data_dict = record.to_jsonl_dict()
        elif isinstance(record, dict):
            if self.validate_schema:
                try:
                    validated_record = validate_record(record)
                    data_dict = validated_record.to_jsonl_dict()
                except Exception as exc:
                    logger.error("[%s] Record không thỏa schema: %s | data=%s", self.source, exc, record)
                    return False
            else:
                data_dict = record
        else:
            logger.error("[%s] Kiểu dữ liệu không hợp lệ: %s", self.source, type(record))
            return False

        self.records.append(data_dict)
        self.records_written = len(self.records)

        if self.flush_per_record:
            self.flush()

        return True

    def flush(self) -> None:
        """Atomic write: Ghi toàn bộ mảng self.records ra file tạm .tmp rồi rename sang file_path."""
        tmp_path = self.file_path.with_name(f"{self.file_path.name}.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.records, f, indent=self.indent, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.file_path)
            self.bytes_written = self.file_path.stat().st_size
        except Exception as exc:
            logger.error("[%s] Lỗi atomic flush file JSON %s: %s", self.source, self.file_path, exc)
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise

    def close(self) -> None:
        """Đóng writer và flush dữ liệu xuống đĩa."""
        if not self._closed:
            self.flush()
            self._closed = True
            logger.info(
                "[%s] Đã đóng JSON writer %s: %d bản ghi (%d bytes)",
                self.source,
                self.file_path,
                self.records_written,
                self.bytes_written,
            )

    def __enter__(self) -> "JsonWriter":
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
