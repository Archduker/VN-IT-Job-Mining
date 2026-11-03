# -*- coding: utf-8 -*-
"""Gọi JEV (typesafe/jev-1.13) qua OpenRouter để phân loại, có cache và trần chi phí (P0 mục 6).

Tài liệu: https://openrouter.ai/docs/guides/community/jev-tutorial
Khóa: OPENROUTER_API_KEY trong .env, không in ra. Chỉ gửi nội dung tin tuyển dụng.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from preprocessing.common import REPO_ROOT
from preprocessing.common.api_cache import ApiCache

MODEL = "typesafe/jev-1.13"
ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
# Ví dụ trong tài liệu: 476 token đầu vào = 0,000019992 USD; output không tính tiền
USD_PER_INPUT_TOKEN = 0.000019992 / 476
MAX_CONSECUTIVE_ERRORS = 5


def _api_key() -> Optional[str]:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    return os.getenv("OPENROUTER_API_KEY") or None


class JevClient:
    def __init__(self, use_api: bool, dry_run: bool, max_cost_usd: float = 0.30, cache: Optional[ApiCache] = None,
                 session: Any = None):
        self.cache = cache or ApiCache("jev")
        self.dry_run = dry_run
        self.use_api = use_api
        self.max_cost_usd = max_cost_usd
        self.key = _api_key() if use_api else None
        self.session = session or requests
        self.reason = None if self.key else ("không bật --use-api" if not use_api else "thiếu OPENROUTER_API_KEY trong .env")
        self.would_call = 0
        self.est_tokens = 0
        self.errors = 0
        self._consecutive_errors = 0

    def noul(self, name: str, instructions: str, true_desc: str, false_desc: str, state: Dict[str, Any]) -> Optional[float]:
        """Xác suất câu trả lời là 'có'. Không gọi được thì None (người hoặc luật quyết thay)."""
        question = {"type": "noul", "instructions": instructions, "criteria": {"true": true_desc, "false": false_desc}}
        key = self.cache.key(MODEL, name, question, state)
        cached = self.cache.get(key)
        if cached is not None:
            return cached.get("noul")
        if self.dry_run and self.use_api:  # ước tính tiền, kể cả khi chưa có khóa
            self.would_call += 1
            self.est_tokens += (len(instructions) + len(true_desc) + len(false_desc) + len(str(state))) // 3 + 60
            return None
        if not self.key or self.dry_run:
            return None
        if self.cache.cost_usd >= self.max_cost_usd:
            self.reason = f"dừng gọi: đã tới trần {self.max_cost_usd} USD"
            return None
        if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            return None
        try:
            resp = self.session.post(ENDPOINT, timeout=30,
                                     headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                                     json={"model": MODEL, "state": state, "questions": {name: question}})
            resp.raise_for_status()
            body = resp.json()
            prob = float(body["answers"][name]["noul"])
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            self.errors += 1
            self._consecutive_errors += 1
            if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                self.reason = f"dừng gọi sau {MAX_CONSECUTIVE_ERRORS} lỗi liên tiếp: {type(exc).__name__}"
            return None
        self._consecutive_errors = 0
        self.cache.put(key, {"noul": prob, "model": body.get("model")}, cost_usd=(body.get("usage") or {}).get("cost", 0))
        return prob

    def report(self) -> Dict[str, Any]:
        out = self.cache.stats(MODEL)
        out["used"] = bool(self.key) and not self.dry_run
        out.update({"errors": self.errors, "reason": self.reason, "max_cost_usd": self.max_cost_usd})
        if self.dry_run:
            out.update({"would_call": self.would_call,
                        "estimated_cost_usd": round(self.est_tokens * USD_PER_INPUT_TOKEN, 4)})
        return out
