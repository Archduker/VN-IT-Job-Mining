# -*- coding: utf-8 -*-
"""Adaptive Dynamic Workload Router & Duty-Cycle Scheduler.

Điều phối nhịp cào tự động co giãn đàn hồi theo số lượng hàng đợi tồn đọng (pending backlog):
1. Khống chế cứng hạn ngạch: Đúng 30 tin / mỗi lần cào.
2. Chiến lược cào tiết kiệm tài nguyên EC2 On-Demand:
   - Phase 1 (Daily Discovery): Chạy cố định 05:00 sáng mỗi ngày, lấy URL mới nhất (sort=new) lưu vào Ledger.
   - Phase 2 (Detail Extraction): Tập trung xả hàng đợi vào cuối tuần (Thứ 7 & Chủ Nhật) qua các ca 09h, 14h, 18h, 21h, 22h.
   - Ngày trong tuần (Thứ 2 đến Thứ 6): Ban ngày Skip hoàn toàn (0.05s, 0 tải EC2); chỉ chạy 1 ca tối duy nhất (21:00) bảo trì dọn 30 tin.
   - An toàn tuyệt đối: Cooldown tối thiểu 55 phút giữa các ca, tự động dừng ngay khi hàng đợi rỗng.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from collection.common.url_ledger import UrlLedger

logger = logging.getLogger("collection.adaptive_router")

MAX_ITEMS_PER_BATCH = 30
COOLDOWN_MINUTES_SURGE = 55
VN_TZ = timezone(timedelta(hours=7))


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class AdaptiveWorkloadRouter:
    """Quản lý trạng thái và ra quyết định phân tuyến co giãn đàn hồi theo backlog."""

    def __init__(self, source: str, base_dir: str = "data") -> None:
        self.source = source.lower().strip()
        b_path = Path(base_dir)
        self.base_dir = b_path if b_path.is_absolute() else (PROJECT_ROOT / b_path)
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
        is_weekend = vn_now.weekday() in (5, 6)

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

        # 1. Cấp 1: Hàng đợi rỗng (Backlog == 0) -> Nghỉ ngơi tuyệt đối
        if backlog == 0:
            return {
                "should_run": False,
                "tier": "IDLE",
                "quota": 0,
                "backlog": 0,
                "reason": "Hàng đợi rỗng (Pending = 0), không có tin mới để cào.",
            }

        # 2. Quy tắc Ngày trong tuần (Thứ 2 đến Thứ 6):
        # Ban ngày tạm hoãn cào chi tiết để tiết kiệm EC2 On-Demand và dồn tải vào cuối tuần.
        # Chỉ duy nhất ca tối (sau 20:00 VN) chạy bảo trì 1 lần tối đa 30 tin.
        if not is_weekend:
            if vn_hour < 20:
                return {
                    "should_run": False,
                    "tier": "WEEKDAY_PAUSE",
                    "quota": 0,
                    "backlog": backlog,
                    "reason": "Ngày trong tuần (T2-T6 ban ngày): Tạm dừng cào chi tiết, dồn hàng đợi để xả vào cuối tuần.",
                }

            # Ca tối ngày thường (sau 20:00 VN)
            if last_run_end:
                last_vn = last_run_end.astimezone(VN_TZ)
                # Đã chạy ca tối hôm nay hoặc vừa chạy cách đây chưa đủ 3 tiếng
                if (last_vn.date() == vn_now.date() and last_vn.hour >= 20) or (now_utc - last_run_end < timedelta(hours=3)):
                    return {
                        "should_run": False,
                        "tier": "WEEKDAY_MAINTENANCE",
                        "quota": 0,
                        "backlog": backlog,
                        "reason": "Ca tối bảo trì ngày thường hôm nay đã hoàn tất. Chờ phiên cuối tuần.",
                    }

            quota = min(backlog, MAX_ITEMS_PER_BATCH)
            return {
                "should_run": True,
                "tier": "WEEKDAY_MAINTENANCE",
                "quota": quota,
                "backlog": backlog,
                "reason": f"Ca tối bảo trì ngày thường: Kích hoạt cào {quota} tin tồn đọng (Backlog: {backlog}).",
            }

        # 3. Quy tắc Cuối tuần (Thứ 7 & Chủ Nhật) - WEEKEND FLUSH MODE:
        # Cào tập trung dọn sạch hàng đợi tồn đọng theo các ca 09h, 14h, 18h, 21h, 22h.
        # Khống chế cứng 30 tin / ca và kiểm tra Cooldown an toàn để chống block bot.
        if last_run_end:
            elapsed = now_utc - last_run_end
            cooldown_required = timedelta(minutes=COOLDOWN_MINUTES_SURGE)
            if elapsed < cooldown_required:
                left_min = max(1, int((cooldown_required - elapsed).total_seconds() / 60))
                return {
                    "should_run": False,
                    "tier": "WEEKEND_COOLDOWN",
                    "quota": 0,
                    "backlog": backlog,
                    "reason": f"Cuối tuần: Đang trong thời gian nghỉ Cooldown an toàn (còn {left_min} phút trước ca kế tiếp).",
                }

        quota = min(backlog, MAX_ITEMS_PER_BATCH)
        tier = "WEEKEND_SURGE" if backlog >= 300 else ("WEEKEND_MODERATE" if backlog > 30 else "WEEKEND_NORMAL")
        return {
            "should_run": True,
            "tier": tier,
            "quota": quota,
            "backlog": backlog,
            "reason": f"Cuối tuần ({tier}): Kích hoạt ca cào xả hàng đợi {quota} tin (Backlog: {backlog}).",
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
