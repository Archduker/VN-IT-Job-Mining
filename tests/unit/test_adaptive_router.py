# -*- coding: utf-8 -*-
"""Unit tests for AdaptiveWorkloadRouter and AdaptiveRouteCheckOperator."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from airflow.exceptions import AirflowSkipException

from crawlers.common.adaptive_router import (
    AdaptiveWorkloadRouter,
    MAX_ITEMS_PER_BATCH,
    COOLDOWN_MINUTES_SURGE,
    VN_TZ,
)


@pytest.fixture
def router(tmp_path):
    """Create an AdaptiveWorkloadRouter pointing to a temporary directory."""
    r = AdaptiveWorkloadRouter(source="test_source", base_dir=str(tmp_path))
    # Mock ledger
    mock_ledger = MagicMock()
    mock_ledger.get_queue_summary.return_value = {
        "total": 0,
        "pending": 0,
        "recheck_due": 0,
        "done": 0,
        "closed": 0,
        "failed": 0,
    }
    r._ledger = mock_ledger
    return r


def test_quota_never_exceeds_30(router):
    """Ensure MAX_ITEMS_PER_BATCH is 30 and quota never exceeds it."""
    assert MAX_ITEMS_PER_BATCH == 30

    router.ledger.get_queue_summary.return_value = {"pending": 5000, "recheck_due": 0}
    decision = router.evaluate()
    assert decision["quota"] <= 30


def test_idle_tier_when_backlog_zero(router):
    """When backlog is 0, router returns IDLE tier and should_run is False."""
    router.ledger.get_queue_summary.return_value = {"pending": 0, "recheck_due": 0}
    decision = router.evaluate()
    assert decision["should_run"] is False
    assert decision["tier"] == "IDLE"
    assert decision["quota"] == 0
    assert "Pending = 0" in decision["reason"]


def test_normal_tier_behavior(router):
    """For small backlog (<= 30), skip during daytime and run during evening window."""
    router.ledger.get_queue_summary.return_value = {"pending": 25, "recheck_due": 0}

    # 1. Daytime: 14:00 VN time (07:00 UTC) -> Skip
    day_time_utc = datetime(2026, 10, 22, 7, 0, tzinfo=timezone.utc)
    dec_day = router.evaluate(now=day_time_utc)
    assert dec_day["should_run"] is False
    assert dec_day["tier"] == "NORMAL"
    assert "Chờ đến ca tối" in dec_day["reason"]

    # 2. Evening: 20:30 VN time (13:30 UTC) -> Run with quota=25
    evening_time_utc = datetime(2026, 10, 22, 13, 30, tzinfo=timezone.utc)
    dec_evening = router.evaluate(now=evening_time_utc)
    assert dec_evening["should_run"] is True
    assert dec_evening["tier"] == "NORMAL"
    assert dec_evening["quota"] == 25

    # 3. If already ran tonight -> Skip
    router.record_finish(items_crawled=25)
    dec_again = router.evaluate(now=evening_time_utc + timedelta(minutes=10))
    assert dec_again["should_run"] is False
    assert "đã hoàn tất" in dec_again["reason"]


def test_surge_tier_duty_cycle_and_cooldown(router):
    """For high backlog (>= 300, e.g. 2629), execute 30 items then enforce 55-60m cooldown."""
    router.ledger.get_queue_summary.return_value = {"pending": 2629, "recheck_due": 0}

    t0 = datetime(2026, 10, 22, 2, 0, tzinfo=timezone.utc)  # 09:00 VN time

    # First session -> Run (30 items)
    dec1 = router.evaluate(now=t0)
    assert dec1["should_run"] is True
    assert dec1["tier"] == "SURGE"
    assert dec1["quota"] == 30

    # Simulate finish session at t0 + 2m
    with patch("crawlers.common.adaptive_router.datetime") as mock_dt:
        mock_dt.now.return_value = t0 + timedelta(minutes=2)
        mock_dt.fromisoformat = datetime.fromisoformat
        router.record_finish(items_crawled=30)

    # Check 20 minutes later -> Should be SKIPPED (Cooldown active)
    t_20m = t0 + timedelta(minutes=22)
    dec_cooldown = router.evaluate(now=t_20m)
    assert dec_cooldown["should_run"] is False
    assert dec_cooldown["tier"] == "SURGE"
    assert "Cooldown" in dec_cooldown["reason"]

    # Check 60 minutes after finish -> Should be ALLOWED to run again!
    t_65m = t0 + timedelta(minutes=65)
    dec_next = router.evaluate(now=t_65m)
    assert dec_next["should_run"] is True
    assert dec_next["tier"] == "SURGE"
    assert dec_next["quota"] == 30


def test_adaptive_route_check_operator_execution(tmp_path):
    """Test AdaptiveRouteCheckOperator raises AirflowSkipException on skip, pushes XCom on run."""
    import sys
    plugins_dir = str(Path(__file__).resolve().parents[2] / "airflow" / "plugins")
    if plugins_dir not in sys.path:
        sys.path.insert(0, plugins_dir)

    from crawler_operators import AdaptiveRouteCheckOperator

    operator = AdaptiveRouteCheckOperator(
        task_id="check_route_test",
        source="topcv",
    )

    # Case A: Router returns should_run = False -> Raises AirflowSkipException
    mock_context = {"ti": MagicMock()}
    with patch("crawler_operators.AdaptiveWorkloadRouter") as mock_router_cls:
        mock_inst = MagicMock()
        mock_inst.evaluate.return_value = {
            "should_run": False,
            "tier": "IDLE",
            "quota": 0,
            "backlog": 0,
            "reason": "Test idle skip",
        }
        mock_router_cls.return_value = mock_inst

        with pytest.raises(AirflowSkipException):
            operator.execute(mock_context)

    # Case B: Router returns should_run = True -> Executes and pushes dynamic_max_items
    with patch("crawler_operators.AdaptiveWorkloadRouter") as mock_router_cls:
        mock_inst = MagicMock()
        mock_inst.evaluate.return_value = {
            "should_run": True,
            "tier": "SURGE",
            "quota": 30,
            "backlog": 2500,
            "reason": "Test surge run",
        }
        mock_router_cls.return_value = mock_inst

        result = operator.execute(mock_context)
        assert result["should_run"] is True
        mock_context["ti"].xcom_push.assert_called_with(key="dynamic_max_items", value=30)
