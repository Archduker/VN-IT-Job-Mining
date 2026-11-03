# -*- coding: utf-8 -*-
"""Gọi JEV qua OpenCode Console để hỏi có/không, có cache và trần chi phí (P0 mục 6).

Tài liệu: https://opencode.ai/v2/docs/console/models/ (mục Jev). jev-1.13-free miễn phí trong thời gian có hạn.
Khóa: OPENCODE_API_KEY trong .env, không in ra. Chỉ gửi nội dung tin tuyển dụng.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import requests

from preprocessing.common import REPO_ROOT
from preprocessing.common.api_cache import ApiCache

MODEL = "jev-1.13-free"
ENDPOINT = "https://opencode.ai/inference/systemone/v1/systemone"
# Giá bản trả phí jev-1.13 (OpenRouter: 476 token vào = 0,000019992 USD); bản -free dùng để ước tính trần khi hết miễn phí
USD_PER_INPUT_TOKEN = 0.000019992 / 476
MAX_CONSECUTIVE_ERRORS = 5
WORKERS = 8  # đo 03/11/2026: 8 luồng ~10 lần gọi/giây, tuần tự ~1,7 lần/giây


def _api_key() -> Optional[str]:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    return os.getenv("OPENCODE_API_KEY") or None


class JevClient:
    def __init__(self, use_api: bool, dry_run: bool, max_cost_usd: float = 0.30, cache: Optional[ApiCache] = None,
                 session: Any = None):
        self.cache = cache or ApiCache("jev")
        self.dry_run = dry_run
        self.use_api = use_api
        self.max_cost_usd = max_cost_usd
        self.key = _api_key() if use_api else None
        self.session = session or requests
        self.reason = None if self.key else ("không bật --use-api" if not use_api else "thiếu OPENCODE_API_KEY trong .env")
        self.would_call = 0
        self.est_tokens = 0
        self.errors = 0
        self._consecutive_errors = 0
        self._memo: Dict[str, Optional[float]] = {}
        self._lock = threading.Lock()

    def noul(self, name: str, instructions: str, true_desc: str, false_desc: str, state: Dict[str, Any]) -> Optional[float]:
        """Xác suất câu trả lời là 'có'. Không gọi được thì None (người hoặc luật quyết thay)."""
        question = {"type": "noul", "instructions": instructions, "criteria": {"true": true_desc, "false": false_desc}}
        key = self.cache.key(MODEL, name, question, state)
        if key in self._memo:  # đã gọi trong prefetch
            return self._memo[key]
        cached = self.cache.get(key)
        if cached is not None:
            return cached.get("noul")
        if self.dry_run and self.use_api:  # ước tính tiền, kể cả khi chưa có khóa
            self.would_call += 1
            self.est_tokens += (len(instructions) + len(true_desc) + len(false_desc) + len(str(state))) // 3 + 60
            return None
        if not self.key or self.dry_run:
            return None
        if self.cache.cost_usd >= self.max_cost_usd or self.cache.over_budget():
            self.reason = f"dừng gọi: đã tới trần {self.max_cost_usd} USD lần này hoặc trần chung của tài khoản"
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
        with self._lock:
            self._consecutive_errors = 0
            self.cache.put(key, {"noul": prob, "model": body.get("model")}, cost_usd=(body.get("usage") or {}).get("cost", 0))
        return prob

    def prefetch(self, name: str, instructions: str, true_desc: str, false_desc: str, states: List[Dict[str, Any]]) -> None:
        """Gọi song song cho nhiều state rồi nhớ kết quả; vòng lặp sau gọi noul() như cũ sẽ lấy ngay."""
        if not (self.key and self.use_api and not self.dry_run):
            return
        question = {"type": "noul", "instructions": instructions, "criteria": {"true": true_desc, "false": false_desc}}
        todo = {}
        for st in states:
            k = self.cache.key(MODEL, name, question, st)
            if k not in self._memo and k not in todo:
                todo[k] = st
        with ThreadPoolExecutor(WORKERS) as ex:
            for k, prob in zip(todo, ex.map(lambda st: self.noul(name, instructions, true_desc, false_desc, st), todo.values())):
                self._memo[k] = prob

    def report(self) -> Dict[str, Any]:
        out = self.cache.stats(MODEL)
        out["used"] = bool(self.key) and not self.dry_run
        out.update({"errors": self.errors, "reason": self.reason, "max_cost_usd": self.max_cost_usd})
        if self.dry_run:
            out.update({"would_call": self.would_call,
                        "estimated_cost_usd": round(self.est_tokens * USD_PER_INPUT_TOKEN, 4)})
        return out
