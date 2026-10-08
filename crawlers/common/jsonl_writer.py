"""
crawlers.common.jsonl_writer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Backward compatibility wrapper cho JsonWriter.
Định dạng đầu ra đã được chuẩn hóa sang .json mảng đối tượng:
`data/<source>/dt=YYYY-MM-DD/batch_XXX.json`
"""

from __future__ import annotations

from crawlers.common.json_writer import JsonWriter

# Alias tương thích ngược
JsonlWriter = JsonWriter

__all__ = ["JsonWriter", "JsonlWriter"]
