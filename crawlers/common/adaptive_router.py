# -*- coding: utf-8 -*-
"""Adaptive Dynamic Workload Router & Duty-Cycle Scheduler.

Điều phối nhịp cào tự động co giãn đàn hồi theo số lượng hàng đợi tồn đọng (pending backlog):
1. Khống chế cứng hạn ngạch: Đúng 30 tin / mỗi lần cào.
2. Tự động nhận diện 4 cấp độ tải:
   - IDLE (pending = 0): Skip ngay trong 0.05 giây.
   - NORMAL (pending <= 30): Ban ngày Skip, chỉ chạy 1 ca tối duy nhất (20:00 - 23:00) tiêu thụ sạch.
   - MODERATE (30 < pending < 300): Chạy 2-3 ca/ngày (trưa, chiều, tối).
   - SURGE (pending >= 300, e.g. TopCV 2,629 tin): Kích hoạt chu kỳ "Chạy 1 ca 30 tin - Nghỉ 1h Cooldown".
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from crawlers.common.url_ledger import UrlLedger

logger = logging.getLogger("crawlers.adaptive_router")

MAX_ITEMS_PER_BATCH = 30
COOLDOWN_MINUTES_SURGE = 55
VN_TZ = timezone(timedelta(hours=7))


class AdaptiveWorkloadRouter:
    """Quản lý trạng thái và ra quyết định phân tuyến co giãn đàn hồi theo backlog."""

    def __init__(self, source: str, base_dir: str = "data") -> None:
        self.source = source.lower().strip()
        self.base_dir = Path(base_dir)
        self.state_file = self.base_dir / self.source / "router_state.json"
        self._ledger: Optional[UrlLedger] = None

    @property
    def ledger(self) -> UrlLedger:
        if self._ledger is None:
            storage_dir = str(self.base_dir / self.source / "url_ledger")
            self._ledger = UrlLedger(self.source, storage_dir=storage_dir)
        return self._ledger

    def _load_state(self) -> dict[str, Any]:
        """Tải trạng thái ca chạy gần nhất từ file JSON."""
        if not self.state_file.exists():
            return {
                "source": self.source,
                "last_run_start": None,
                "last_run_end": None,
                "last_items_crawled": 0,
                "total_crawled_today": 0,
                "current_tier": "IDLE",
            }
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("[AdaptiveRouter] Không thể đọc state file %s: %s", self.state_file, e)
            return {"source": self.source}

    def _save_state(self, state: dict[str, Any]) -> None:
        """Lưu trạng thái an toàn atomic."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.state_file.with_suffix(".tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            tmp_file.replace(self.state_file)
        except Exception as e:
            logger.warning("[AdaptiveRouter] Không thể ghi state file %s: %s", self.state_file, e)
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)

    def evaluate(self, now: Optional[datetime] = None) -> dict[str, Any]:
        """Đánh giá xem thời điểm hiện tại có nên chạy cào hay nghỉ.

        Args:
            now: Thời điểm đánh giá (mặc định là datetime.now(timezone.utc)).

        Returns:
            Dict chứa:
                - should_run (bool): Quyết định chạy (True) hay nghỉ (False).
                - tier (str): Cấp độ tải ('IDLE', 'NORMAL', 'MODERATE', 'SURGE').
                - quota (int): Số tin tối đa được cào (luôn <= 30).
                - backlog (int): Số lượng pending + recheck_due.
                - reason (str): Diễn giải lý do bằng tiếng Việt.
        """
        now_utc = now or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        vn_now = now_utc.astimezone(VN_TZ)
        vn_hour = vn_now.hour

        summary = self.ledger.get_queue_summary()
        pending = summary.get("pending", 0)
        recheck_due = summary.get("recheck_due", 0)
        backlog = pending + recheck_due

        state = self._load_state()
        last_run_end_str = state.get("last_run_end")
        last_run_end: Optional[datetime] = None
        if last_run_end_str:
            try:
                last_run_end = datetime.fromisoformat(last_run_end_str)
                if last_run_end.tzinfo is None:
                    last_run_end = last_run_end.replace(tzinfo=timezone.utc)
            except Exception:
                last_run_end = None

        # 1. Cấp 1: Hàng đợi rỗng (Backlog == 0)
        if backlog == 0:
            return {
                "should_run": False,
                "tier": "IDLE",
                "quota": 0,
                "backlog": 0,
                "reason": "Hàng đợi rỗng (Pending = 0), nghỉ ngơi hoàn toàn.",
            }

        # 2. Cấp 4: Quá tải nặng (Backlog >= 300, e.g. TopCV 2,629 tin)
        # Chu kỳ: Chạy 1 ca 30 tin (mất 2 phút) -> Nghỉ tối thiểu 55-60 phút Cooldown
        if backlog >= 300:
            tier = "SURGE"
            if last_run_end:
                elapsed = now_utc - last_run_end
                if elapsed < timedelta(minutes=COOLDOWN_MINUTES_SURGE):
                    left_min = max(1, int((timedelta(minutes=COOLDOWN_MINUTES_SURGE) - elapsed).total_seconds() / 60))
                    return {
                        "should_run": False,
                        "tier": tier,
                        "quota": 0,
                        "backlog": backlog,
                        "reason": f"Đang trong thời gian nghỉ Cooldown 1h (còn {left_min} phút trước ca kế tiếp).",
                    }
            return {
                "should_run": True,
                "tier": tier,
                "quota": MAX_ITEMS_PER_BATCH,
                "backlog": backlog,
                "reason": f"Surge Duty-Cycle: Kích hoạt ca cào {MAX_ITEMS_PER_BATCH} tin (Backlog: {backlog}).",
            }

        # 3. Cấp 3: Vừa phải (30 < Backlog < 300)
        # Chạy 3 ca/ngày (trưa, chiều, tối), cách nhau tối thiểu 2.5 tiếng
        if backlog > 30:
            tier = "MODERATE"
            if last_run_end:
                elapsed = now_utc - last_run_end
                if elapsed < timedelta(minutes=150):
                    left_min = max(1, int((timedelta(minutes=150) - elapsed).total_seconds() / 60))
                    return {
                        "should_run": False,
                        "tier": tier,
                        "quota": 0,
                        "backlog": backlog,
                        "reason": f"Đang trong thời gian nghỉ giữa các ca Moderate (còn {left_min} phút).",
                    }
            if vn_hour in [11, 12, 13, 17, 18, 20, 21, 22]:
                return {
                    "should_run": True,
                    "tier": tier,
                    "quota": MAX_ITEMS_PER_BATCH,
                    "backlog": backlog,
                    "reason": f"Moderate Batch: Kích hoạt ca cào {MAX_ITEMS_PER_BATCH} tin (Khung {vn_hour}h, Backlog: {backlog}).",
                }
            return {
                "should_run": False,
                "tier": tier,
                "quota": 0,
                "backlog": backlog,
                "reason": f"Chờ khung giờ Moderate (12h, 17h, 20h-22h). Giờ hiện tại: {vn_hour}h.",
            }

        # 4. Cấp 2: Bình thường (0 < Backlog <= 30)
        # Chỉ chạy 1 ca tối duy nhất (sau 20:00 VN) để dọn sạch 30 tin
        tier = "NORMAL"
        if last_run_end:
            last_vn = last_run_end.astimezone(VN_TZ)
            # Nếu đã chạy trong ca tối hôm nay (giờ VN >= 20) hoặc vừa chạy cách đây dưới 4 tiếng
            if (last_vn.date() == vn_now.date() and last_vn.hour >= 20) or (now_utc - last_run_end < timedelta(hours=4)):
                return {
                    "should_run": False,
                    "tier": tier,
                    "quota": 0,
                    "backlog": backlog,
                    "reason": "Ca tối định kỳ hôm nay đã hoàn tất thành công.",
                }

        if vn_hour >= 20:
            quota = min(backlog, MAX_ITEMS_PER_BATCH)
            return {
                "should_run": True,
                "tier": tier,
                "quota": quota,
                "backlog": backlog,
                "reason": f"Normal Evening: Kích hoạt ca tối định kỳ dọn sạch {quota} tin tồn đọng.",
            }

        return {
            "should_run": False,
            "tier": tier,
            "quota": 0,
            "backlog": backlog,
            "reason": f"Chờ đến ca tối định kỳ (sau 20:00). Giờ hiện tại: {vn_hour}h.",
        }

    def record_start(self) -> None:
        """Ghi nhận thời điểm bắt đầu ca cào."""
        now_utc = datetime.now(timezone.utc)
        state = self._load_state()
        state["last_run_start"] = now_utc.isoformat()
        self._save_state(state)

    def record_finish(
        self,
        items_crawled: int,
        success: bool = True,
        finish_time: Optional[datetime] = None,
    ) -> None:
        """Ghi nhận hoàn tất ca cào để kích hoạt thời gian nghỉ (Cooldown)."""
        now_utc = finish_time or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        state = self._load_state()
        state["last_run_end"] = now_utc.isoformat()
        state["last_items_crawled"] = items_crawled
        state["total_crawled_today"] = state.get("total_crawled_today", 0) + items_crawled
        state["last_success"] = success
        self._save_state(state)
        logger.info(
            "[AdaptiveRouter] Đã ghi nhận ca cào %s: %d tin lúc %s. Bắt đầu tính Cooldown.",
            self.source.upper(),
            items_crawled,
            now_utc.isoformat(),
        )

    def get_state(self) -> dict[str, Any]:
        """Lấy toàn bộ trạng thái hiện tại."""
        return self._load_state()
