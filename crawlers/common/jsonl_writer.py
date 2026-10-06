"""
crawlers.common.jsonl_writer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Ghi dữ liệu JSONL an toàn, tuân thủ schema và cấu trúc phân vùng:
`data/<source>/dt=YYYY-MM-DD/batch_XXX.jsonl`
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional, Union

from crawlers.common.logger import get_logger
from crawlers.common.schema import JobRecord, validate_record

logger = get_logger("jsonl_writer")


class JsonlWriter:
    """Class hỗ trợ ghi JobRecord vào file JSONL với schema validation và tự động phân vùng.

    Attributes:
        source: Nguồn crawl (ví dụ: 'topdev').
        output_dir: Thư mục gốc lưu trữ dữ liệu (mặc định: 'data').
        run_date: Ngày chạy dùng cho partition dt=YYYY-MM-DD (mặc định: hôm nay).
        batch_seq: Số thứ tự batch (mặc định: 1).
        file_path: Đường dẫn đầy đủ tới file JSONL đích.
        records_written: Số bản ghi đã ghi thành công.
        bytes_written: Tổng số byte đã ghi.
        flush_per_record: Ghi flush ngay lập tức sau mỗi dòng.
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
    ) -> None:
        """Khởi tạo JsonlWriter.

        Args:
            source: Tên nguồn crawler (ví dụ: 'topdev').
            output_dir: Thư mục gốc lưu dữ liệu. Default: 'data'.
            run_date: Ngày chạy phân vùng. Default: date.today().
            batch_seq: Số thứ tự batch (1 -> batch_001.jsonl).
            filename_override: Ghi đè tên file nếu muốn đặt tên riêng.
            flush_per_record: Flush buffer ngay sau mỗi bản ghi.
            validate_schema: Kiểm tra tính hợp lệ của bản ghi trước khi ghi.
        """
        self.source = source.lower().strip()
        self.run_date = run_date or date.today()
        self.batch_seq = batch_seq
        self.flush_per_record = flush_per_record
        self.validate_schema = validate_schema

        base_dir = Path(output_dir or "data")
        partition_dir = base_dir / self.source / f"dt={self.run_date.isoformat()}"
        partition_dir.mkdir(parents=True, exist_ok=True)

        filename = filename_override or f"batch_{self.batch_seq:03d}.jsonl"
        self.file_path = partition_dir / filename

        self._file = None
        self.records_written: int = 0
        self.bytes_written: int = 0

    def open(self) -> "JsonlWriter":
        """Mở file ở chế độ append (hoặc tạo mới)."""
        if self._file is None or self._file.closed:
            self._file = open(self.file_path, "a", encoding="utf-8")
            logger.debug("[%s] Mở file JSONL: %s", self.source, self.file_path)
        return self

    def write(self, record: Union[JobRecord, dict[str, Any]]) -> bool:
        """Ghi một JobRecord (hoặc dict) vào file JSONL.

        Args:
            record: Đối tượng JobRecord hoặc dict thỏa mãn schema.

        Returns:
            True nếu ghi thành công, False nếu thất bại do schema validation hoặc ghi lỗi.
        """
        if self._file is None or self._file.closed:
            self.open()

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

        line = json.dumps(data_dict, ensure_ascii=False) + "\n"
        byte_len = self._file.write(line)
        if self.flush_per_record:
            self._file.flush()

        self.records_written += 1
        self.bytes_written += byte_len
        return True

    def flush(self) -> None:
        """Flush buffer xuống disk."""
        if self._file and not self._file.closed:
            self._file.flush()

    def close(self) -> None:
        """Đóng file writer."""
        if self._file and not self._file.closed:
            self._file.flush()
            self._file.close()
            logger.info(
                "[%s] Đã đóng JSONL writer %s: %d bản ghi (%d bytes)",
                self.source,
                self.file_path,
                self.records_written,
                self.bytes_written,
            )

    def __enter__(self) -> "JsonlWriter":
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
