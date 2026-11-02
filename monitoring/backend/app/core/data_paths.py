# -*- coding: utf-8 -*-
"""Định vị dữ liệu cục bộ của từng nguồn (URL Ledger, raw, staging, reports)."""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger("data_paths")


def require_source(source: str) -> str:
    """FastAPI dependency: chuẩn hóa và kiểm tra tên nguồn trên đường dẫn."""
    normalized = source.lower()
    if normalized not in settings.SUPPORTED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Nguồn '{source}' không tồn tại")
    return normalized


def find_catalog_file(source: str) -> Optional[Path]:
    """Tìm catalog_master.json của nguồn, gồm cả vị trí cũ data/url_ledger/<source>."""
    for path in (
        settings.DATA_DIR / source / "url_ledger" / "catalog_master.json",
        settings.DATA_DIR / "url_ledger" / source / "catalog_master.json",
    ):
        if path.exists():
            return path
    return None


def load_catalog_records(source: str) -> List[Dict[str, Any]]:
    """Đọc các bản ghi ledger; catalog hỏng được coi như không có."""
    path = find_catalog_file(source)
    if not path:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Không đọc được catalog %s: %s", path, exc)
        return []
    records = data.get("records", data) if isinstance(data, dict) else data
    if isinstance(records, dict):
        records = records.values()
    return [r for r in records if isinstance(r, dict)]


def iter_raw_files(source: str) -> Iterator[Tuple[Optional[date], Path]]:
    """Duyệt file raw JSON, kèm ngày lấy từ thư mục raw/<YYYY-MM-DD>/ nếu có."""
    raw_dir = settings.DATA_DIR / source / "raw"
    if not raw_dir.exists():
        return
    for path in sorted(raw_dir.rglob("*.json")):
        try:
            day = date.fromisoformat(path.parent.name)
        except ValueError:
            day = None
        yield day, path


def read_raw_envelopes(path: Path) -> List[Dict[str, Any]]:
    """Đọc một file raw: có thể là một envelope hoặc một batch nhiều envelope."""
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Không đọc được raw %s: %s", path, exc)
        return []
    items = content if isinstance(content, list) else [content]
    return [i for i in items if isinstance(i, dict) and ("raw_payload" in i or "raw" in i)]


def load_json_report(path: Path) -> Optional[Dict[str, Any]]:
    """Đọc file báo cáo JSON; thiếu hoặc hỏng thì trả None."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
