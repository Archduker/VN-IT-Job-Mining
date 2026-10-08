# -*- coding: utf-8 -*-
"""Base crawler abstract class.

Định nghĩa interface chuẩn cho tất cả các crawlers trong hệ thống VN-IT-Job-Mining.
Mọi crawler nguồn phải kế thừa class này để đảm bảo tính nhất quán về:
- Cấu hình (source name, version, request limits)
- Quản lý checkpoint & tránh trùng lặp
- Ghi dữ liệu dạng JSONL phân vùng (partitioned)
- Chuẩn schema JobRecord (Pydantic)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Optional
import logging

from crawlers.common.checkpoint import CheckpointManager
from crawlers.common.json_writer import JsonWriter
from crawlers.common.schema import JobRecord

log = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """Abstract Base Class cho toàn bộ job crawlers."""

    source_name: str = ""
    crawler_version: str = "0.1.0"

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_items: Optional[int] = None,
        checkpoint_interval: int = 10,
    ) -> None:
        if not self.source_name:
            raise ValueError("source_name must be defined in crawler subclass")

        self.max_items = max_items
        self.checkpoint_interval = checkpoint_interval

        # Checkpoint manager
        self.checkpoint = CheckpointManager(
            source=self.source_name,
            checkpoint_dir=checkpoint_dir or f"data/{self.source_name}",
        )

        # Output writer
        out_base = output_dir if output_dir else "data"
        self.writer = JsonWriter(source=self.source_name, output_dir=out_base)
        from crawlers.common.utils import make_batch_id
        self.batch_id = make_batch_id(self.source_name, seq=self.writer.batch_seq, run_date=self.writer.run_date)

        self.crawled_count = 0
        self.skipped_count = 0
        self.error_count = 0

    @abstractmethod
    def fetch_items(self) -> Generator[Dict[str, Any], None, None]:
        """Fetch raw items từ listing/API nguồn.
        
        Yields:
            Dict[str, Any]: Dữ liệu thô đại diện cho 1 job hoặc 1 listing card.
        """
        pass

    @abstractmethod
    def parse_item(self, item: Dict[str, Any]) -> Optional[JobRecord]:
        """Parse và chuyển đổi raw item thành JobRecord hợp lệ theo schema.
        
        Args:
            item: Raw item từ fetch_items.
            
        Returns:
            JobRecord nếu hợp lệ, None nếu bỏ qua hoặc parse thất bại.
        """
        pass

    def run(self) -> Dict[str, Any]:
        """Thực thi pipeline thu thập dữ liệu với checkpointing và deduplication.
        
        Returns:
            Thống kê kết quả thu thập (crawled, skipped, errors, total_seen).
        """
        log.info(
            "Starting crawl for %s (max_items=%s, checkpoint_seen=%d)",
            self.source_name,
            self.max_items,
            len(self.checkpoint.seen_ids),
        )

        for raw_item in self.fetch_items():
            if self.max_items is not None and self.crawled_count >= self.max_items:
                log.info("Reached target max_items (%d). Stopping.", self.max_items)
                break

            try:
                record = self.parse_item(raw_item)
                if not record:
                    self.skipped_count += 1
                    continue

                job_id = record.meta.source_job_id
                if self.checkpoint.is_seen(job_id):
                    self.skipped_count += 1
                    continue

                # Write JSON
                self.writer.write(record)
                self.checkpoint.mark_seen(job_id)
                self.crawled_count += 1

                # Flush checkpoint periodically
                if self.crawled_count % self.checkpoint_interval == 0:
                    self.checkpoint.save()
                    log.info(
                        "[%s] Progress: %d crawled, %d skipped",
                        self.source_name,
                        self.crawled_count,
                        self.skipped_count,
                    )

            except Exception as exc:
                self.error_count += 1
                log.error("[%s] Error processing item: %s", self.source_name, exc, exc_info=True)

        # Finalize
        self.checkpoint.save()
        self.writer.close()

        stats = {
            "source": self.source_name,
            "crawled": self.crawled_count,
            "skipped": self.skipped_count,
            "errors": self.error_count,
            "total_seen": len(self.checkpoint.seen_ids),
            "output_file": str(self.writer.file_path) if self.writer.file_path else None,
        }
        log.info("[%s] Finished crawl batch: %s", self.source_name, stats)
        return stats
