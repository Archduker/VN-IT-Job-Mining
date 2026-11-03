# -*- coding: utf-8 -*-
"""Cache kết quả gọi API (JEV, LLM dịch) theo hash nội dung.

Chạy lại thì đọc cache: cùng kết quả, không tốn thêm tiền (P0 mục 6).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from preprocessing.common import REPO_ROOT

CACHE_ROOT = REPO_ROOT / "data" / "preprocessing" / "_cache"


class ApiCache:
    def __init__(self, kind: str, root: Optional[Path] = None):
        self.dir = (root or CACHE_ROOT) / kind
        self.calls = 0
        self.cache_hits = 0
        self.cost_usd = 0.0

    @staticmethod
    def key(*parts: Any) -> str:
        return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        path = self.dir / key[:2] / f"{key}.json"
        if not path.exists():
            return None
        self.cache_hits += 1
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, key: str, value: Dict[str, Any], cost_usd: float = 0.0) -> None:
        self.calls += 1
        self.cost_usd += float(cost_usd or 0)
        path = self.dir / key[:2] / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def stats(self, model: str) -> Dict[str, Any]:
        return {"used": True, "model": model, "calls": self.calls, "cache_hits": self.cache_hits,
                "cost_usd": round(self.cost_usd, 6)}
