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
GLOBAL_CAP_USD = 0.95  # trần mặc định mỗi tài khoản (sổ riêng theo nhà cung cấp), cộng dồn mọi lần chạy
PROVIDER_CAP_USD = {"google": 9.0}  # khóa Gemini có 10 USD tín dụng (người dùng báo 03/11/2026); chừa 1 USD


class ApiCache:
    def __init__(self, kind: str, root: Optional[Path] = None, provider: str = "opencode"):
        self.dir = (root or CACHE_ROOT) / kind
        self.ledger = (root or CACHE_ROOT) / f"spend_{provider}.json"
        self.cap_usd = PROVIDER_CAP_USD.get(provider, GLOBAL_CAP_USD)
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
        if cost_usd:
            self.ledger.write_text(json.dumps({"total_usd": self.total_spent() + float(cost_usd)}), encoding="utf-8")

    def total_spent(self) -> float:
        """Tổng tiền đã tiêu qua mọi lần chạy với nhà cung cấp này (sổ _cache/spend_<provider>.json)."""
        if not self.ledger.exists():
            return 0.0
        return float(json.loads(self.ledger.read_text(encoding="utf-8")).get("total_usd", 0.0))

    def over_budget(self) -> bool:
        return self.total_spent() >= self.cap_usd

    def stats(self, model: str) -> Dict[str, Any]:
        return {"used": True, "model": model, "calls": self.calls, "cache_hits": self.cache_hits,
                "cost_usd": round(self.cost_usd, 6), "total_spent_usd": round(self.total_spent(), 6),
                "global_cap_usd": self.cap_usd}
