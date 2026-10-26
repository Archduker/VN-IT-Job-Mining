# -*- coding: utf-8 -*-
"""Service quản lý và đọc URL Ledger Catalog."""

from collections import Counter
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger("ledger_service")


class LedgerService:
    """Service đọc và thống kê URL Ledger Catalog."""

    def __init__(self):
        self.data_dir = settings.DATA_DIR

    def _find_catalog_file(self, source: str) -> Optional[Path]:
        """Tìm đường dẫn catalog_master.json của nguồn."""
        p1 = self.data_dir / source / "url_ledger" / "catalog_master.json"
        if p1.exists():
            return p1
        p2 = self.data_dir / "url_ledger" / source / "catalog_master.json"
        if p2.exists():
            return p2
        return None

    def get_system_enum_summary(self) -> Dict[str, Any]:
        """Thống kê chi tiết 5 trạng thái Enum vòng đời URL trên toàn bộ 8 sàn và phân bổ từng sàn."""
        from datetime import datetime, timezone

        totals = {
            "total": 0,
            "pending": 0,
            "done": 0,
            "recheck_due": 0,
            "closed": 0,
            "failed": 0,
        }
        by_source = {}

        now = datetime.now(timezone.utc)

        for src in settings.SUPPORTED_SOURCES:
            catalog_path = self._find_catalog_file(src)
            src_counts = {
                "total": 0,
                "pending": 0,
                "done": 0,
                "recheck_due": 0,
                "closed": 0,
                "failed": 0,
            }

            if catalog_path and catalog_path.exists():
                try:
                    with open(catalog_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    src_counts["total"] = len(data)
                    for r in data.values():
                        st = str(r.get("status", "PENDING")).upper()
                        # Xử lý các alias trạng thái
                        if st in ("PENDING", "NEW"):
                            src_counts["pending"] += 1
                        elif st in ("RECHECK_DUE", "DUE"):
                            src_counts["recheck_due"] += 1
                        elif st in ("CLOSED", "EXPIRED", "404"):
                            src_counts["closed"] += 1
                        elif st in ("FAILED", "ERROR"):
                            src_counts["failed"] += 1
                        elif st in ("DONE", "SCRAPED", "COMPLETED"):
                            # Kiểm tra xem có đến hạn tái cào 21 ngày chưa
                            scraped_at_str = r.get("last_scraped_at") or r.get("last_crawled_at") or r.get("scraped_at")
                            is_recheck = False
                            if scraped_at_str:
                                try:
                                    last_dt = datetime.fromisoformat(scraped_at_str)
                                    if last_dt.tzinfo is None:
                                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                                    if (now - last_dt).days >= 21:
                                        is_recheck = True
                                except Exception:
                                    pass

                            if is_recheck:
                                src_counts["recheck_due"] += 1
                            else:
                                src_counts["done"] += 1
                        else:
                            src_counts["pending"] += 1
                except Exception as exc:
                    logger.error("Lỗi phân tích enum summary cho nguồn %s: %s", src, exc)

            by_source[src] = src_counts
            for k in ("total", "pending", "done", "recheck_due", "closed", "failed"):
                totals[k] += src_counts[k]

        def _calc_pct(val: int, base: int) -> float:
            return round((val / max(base, 1)) * 100, 1)

        total_base = totals["total"]
        return {
            "total": total_base,
            "pending": {"count": totals["pending"], "pct": _calc_pct(totals["pending"], total_base)},
            "done": {"count": totals["done"], "pct": _calc_pct(totals["done"], total_base)},
            "recheck_due": {"count": totals["recheck_due"], "pct": _calc_pct(totals["recheck_due"], total_base)},
            "closed": {"count": totals["closed"], "pct": _calc_pct(totals["closed"], total_base)},
            "failed": {"count": totals["failed"], "pct": _calc_pct(totals["failed"], total_base)},
            "by_source": by_source,
            "generated_at": datetime.now().isoformat(),
        }

    def get_ledger_summary(self, source: str) -> Dict[str, Any]:
        """Thống kê tổng số và phân loại trạng thái URL trong Ledger."""
        catalog_path = self._find_catalog_file(source)
        if not catalog_path or not catalog_path.exists():
            return {
                "source": source,
                "total": 0,
                "counts": {"NEW": 0, "SCRAPED": 0, "SKIPPED": 0, "ERROR": 0, "REPOST": 0},
                "exists": False,
            }

        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            counts = Counter(r.get("status", "NEW") for r in data.values())
            reposts = sum(1 for r in data.values() if r.get("repost_of_url_hash"))
            if reposts > 0:
                counts["REPOST"] = reposts

            return {
                "source": source,
                "total": len(data),
                "counts": dict(counts),
                "exists": True,
                "path": str(catalog_path),
            }
        except Exception as exc:
            logger.error("Lỗi đọc ledger catalog nguồn %s: %s", source, exc)
            return {"source": source, "total": 0, "counts": {}, "error": str(exc), "exists": False}

    def list_ledger_items(
        self,
        source: str,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lấy danh sách các dòng trong Ledger có phân trang, tìm kiếm và lọc."""
        catalog_path = self._find_catalog_file(source)
        if not catalog_path or not catalog_path.exists():
            return {
                "source": source,
                "total": 0,
                "counts": {},
                "page": page,
                "page_size": page_size,
                "items": [],
            }

        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            counts = Counter(r.get("status", "NEW") for r in data.values())

            # Chuyển đổi thành danh sách bản ghi
            items = []
            for h, rec in data.items():
                item = {
                    "url_hash": h,
                    "job_id": str(rec.get("job_id")) if rec.get("job_id") is not None else None,
                    "job_title": rec.get("job_title") or rec.get("title") or rec.get("preliminary_title"),
                    "company": rec.get("company") or rec.get("preliminary_company"),
                    "url": rec.get("canonical_url") or rec.get("url"),
                    "status": rec.get("status", "NEW"),
                    "scraped_at": rec.get("last_scraped_at") or rec.get("scraped_at") or rec.get("discovered_at"),
                    "http_status": rec.get("http_status") or (200 if str(rec.get("status", "")).upper() in ("DONE", "SCRAPED") else None),
                    "content_hash": rec.get("content_hash"),
                    "repost_of_url_hash": rec.get("repost_of_url_hash"),
                }
                items.append(item)

            # Lọc theo trạng thái
            if status_filter and status_filter.upper() != "ALL":
                items = [it for it in items if it["status"] == status_filter.upper()]

            # Tìm kiếm theo job_id, url_hash, canonical_url, tiêu đề hoặc công ty
            if search_query:
                q = search_query.lower().strip()
                items = [
                    it
                    for it in items
                    if (it.get("job_id") and q in it["job_id"].lower())
                    or (it.get("url_hash") and q in it["url_hash"].lower())
                    or (it.get("url") and q in it["url"].lower())
                    or (it.get("content_hash") and q in it["content_hash"].lower())
                    or (it.get("job_title") and q in it["job_title"].lower())
                    or (it.get("company") and q in it["company"].lower())
                ]

            total_filtered = len(items)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_items = items[start_idx:end_idx]

            return {
                "source": source,
                "total": total_filtered,
                "counts": dict(counts),
                "page": page,
                "page_size": page_size,
                "items": paginated_items,
            }
        except Exception as exc:
            logger.error("Lỗi duyệt ledger items nguồn %s: %s", source, exc)
            return {
                "source": source,
                "total": 0,
                "counts": {},
                "page": page,
                "page_size": page_size,
                "items": [],
                "error": str(exc),
            }


ledger_service = LedgerService()
