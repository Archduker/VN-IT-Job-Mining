# -*- coding: utf-8 -*-
"""Tests for the Crawling page status, SSE log stream, and source flattener fixes."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "monitoring" / "backend"))

from app.services import crawler_service as crawler_module  # noqa: E402
from app.services.airflow_service import airflow_service  # noqa: E402
from app.services.crawler_service import CrawlerService, _discovery_status  # noqa: E402
from preprocessing.integration.json_flattener import flatten_raw_job_record  # noqa: E402


def collect(service, source):
    async def run():
        return [line async for line in service.stream_logs(source)]

    return asyncio.run(asyncio.wait_for(run(), timeout=2))


def flatten(source, payload):
    return flatten_raw_job_record({"metadata": {"source": source}, "raw_payload": payload}, source_fallback=source)


def test_discovery_status_uses_airflow_state():
    states = {"discover_topcv": "failed", "discover_itviec": "success", "discover_glints": None}
    assert _discovery_status(states, "discover_topcv") == "FAILED"
    assert _discovery_status(states, "discover_itviec") == "SUCCESS"
    assert _discovery_status(states, "discover_glints") == "SCHEDULED"
    assert _discovery_status(states, "discover_jobsgo") == "UNKNOWN"
    assert _discovery_status(None, "discover_topcv") == "UNKNOWN"


def test_weekly_schedule_does_not_claim_success_without_airflow(monkeypatch):
    monkeypatch.setattr(airflow_service, "get_latest_discovery_states", lambda: None)
    monkeypatch.setattr(airflow_service, "get_run_history", lambda days=14: None)
    data = crawler_module.crawler_service.get_weekly_crawl_schedule()
    assert {row["status"] for row in data["phase1_discovery"]} == {"UNKNOWN"}
    assert {row["status"] for row in data["phase2_detail"]} == {"UNKNOWN"}
    assert data["airflow_available"] is False


def test_phase2_status_comes_from_latest_dag_run(monkeypatch):
    from datetime import datetime

    runs = [
        {"dag_id": "crawler_detail_topcv", "state": "success", "start_date": datetime(2026, 11, 1, 9)},
        {"dag_id": "crawler_detail_topcv", "state": "failed", "start_date": datetime(2026, 11, 1, 14)},
        {"dag_id": "crawler_detail_itviec", "state": "success", "start_date": datetime(2026, 11, 1, 9)},
    ]
    monkeypatch.setattr(airflow_service, "get_latest_discovery_states", lambda: {})
    monkeypatch.setattr(airflow_service, "get_run_history", lambda days=14: runs)
    rows = {r["focal_source"]: r for r in crawler_module.crawler_service.get_weekly_crawl_schedule()["phase2_detail"]}
    assert rows["topcv"]["status"] == "FAILED"
    assert rows["itviec"]["status"] == "SUCCESS"
    assert rows["glints"]["status"] == "SCHEDULED"


def test_next_detail_slot_follows_router_rules():
    from datetime import datetime

    from app.services.crawler_service import VN_TZ, next_detail_slot

    monday_noon = datetime(2026, 11, 2, 12, tzinfo=VN_TZ)
    assert next_detail_slot(monday_noon) == datetime(2026, 11, 2, 21, tzinfo=VN_TZ)
    friday_late = datetime(2026, 11, 6, 21, 30, tzinfo=VN_TZ)
    assert next_detail_slot(friday_late) == datetime(2026, 11, 6, 22, tzinfo=VN_TZ)
    friday_night = datetime(2026, 11, 6, 22, 30, tzinfo=VN_TZ)
    assert next_detail_slot(friday_night) == datetime(2026, 11, 7, 9, tzinfo=VN_TZ)
    saturday_15h = datetime(2026, 11, 7, 15, tzinfo=VN_TZ)
    assert next_detail_slot(saturday_15h) == datetime(2026, 11, 7, 18, tzinfo=VN_TZ)


def test_stream_ends_when_source_has_no_process():
    assert collect(CrawlerService(), "topcv")[-1].startswith("[EOF]")


def test_stream_sends_lines_without_sse_prefix():
    service = CrawlerService()
    service.log_buffers["topcv"] = ["dòng 1\n"]
    service.active_processes["topcv"] = SimpleNamespace(returncode=0)
    lines = collect(service, "topcv")
    assert lines[0] == "dòng 1"
    assert not any(line.startswith("data:") for line in lines)


def test_stream_keeps_going_after_buffer_is_trimmed():
    service = CrawlerService()
    service.active_processes["topcv"] = SimpleNamespace(returncode=None)
    service.log_buffers["topcv"] = ["a", "b"]
    service.log_dropped["topcv"] = 0

    async def run():
        stream = service.stream_logs("topcv")
        seen = [await stream.__anext__(), await stream.__anext__()]
        service.log_buffers["topcv"].pop(0)
        service.log_dropped["topcv"] += 1
        service.log_buffers["topcv"].append("c")
        seen.append(await stream.__anext__())
        await stream.aclose()
        return seen

    assert asyncio.run(asyncio.wait_for(run(), timeout=2)) == ["a", "b", "c"]


def test_topdev_experience_and_level_from_html_payload():
    flat = flatten("topdev", {"title": "Dev", "experience": "3 năm", "seniority_text": "Senior"})
    assert flat["raw_experience_text"] == "3 năm"
    assert flat["raw_seniority_text"] == "Senior"


def test_topdev_experience_from_api_extra():
    flat = flatten("topdev", {"title": "Dev", "extra": {"experience": "2 năm"}, "job_levels_str": "Junior"})
    assert flat["raw_experience_text"] == "2 năm"
    assert flat["raw_seniority_text"] == "Junior"


def test_raw_page_warns_about_occupations_used_as_skills():
    from app.services.source_report_service import annotate_envelope

    envelope = {"metadata": {"source": "jobsgo", "job_id": "x"},
                "raw_payload": {"title": "Dev", "occupations": ["CNTT"], "requirements_bullets": ["Java"]}}
    note = {n["code"]: n for n in annotate_envelope("jobsgo", envelope)["notes"]}["F7"]
    assert note["status"] == "warn" and "occupations" in note["how"]


def test_stream_waits_for_reader_before_eof():
    service = CrawlerService()
    service.active_processes["topcv"] = SimpleNamespace(returncode=1)
    service.log_buffers["topcv"] = ["dòng 1"]
    service.log_dropped["topcv"] = 0
    service.log_done["topcv"] = False

    async def run():
        stream = service.stream_logs("topcv")
        seen = [await stream.__anext__()]
        # Tiến trình đã có returncode nhưng read_stream chưa ghi xong
        service.log_buffers["topcv"] += ["dòng cuối", "exit code: 1"]
        service.log_done["topcv"] = True
        seen += [line async for line in stream]
        return seen

    assert asyncio.run(asyncio.wait_for(run(), timeout=3)) == ["dòng 1", "dòng cuối", "exit code: 1", "[EOF] Quá trình cào đã hoàn tất."]


def test_backlog_counts_done_records_due_for_recrawl(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timedelta, timezone

    from app.services.ledger_service import ledger_service

    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    catalog = tmp_path / "catalog_master.json"
    catalog.write_text(json.dumps({
        "a": {"status": "DONE", "last_scraped_at": old},
        "b": {"status": "DONE", "last_scraped_at": fresh},
        "c": {"status": "PENDING"},
    }))
    monkeypatch.setattr(ledger_service, "_find_catalog_file", lambda source: catalog)
    monkeypatch.setattr(airflow_service, "get_latest_discovery_states", lambda: None)
    monkeypatch.setattr(airflow_service, "get_run_history", lambda days=14: None)
    assert ledger_service.get_queue_summary("topcv") == {"pending": 1, "recheck_due": 1, "done": 1, "closed": 0, "failed": 0}
    row = crawler_module.crawler_service.get_weekly_crawl_schedule()["phase2_detail"][0]
    assert (row["uncrawled_pending"], row["batches_needed"]) == (2, 1)


def test_topdev_detail_api_requests_experience_level_and_date():
    from collection.sources.topdev.crawler import DETAIL_FIELDS

    fields = DETAIL_FIELDS.split(",")
    assert {"experiences_str", "job_levels_str", "published"} <= set(fields)
    assert "refreshed" not in fields  # đổi mỗi lần làm mới tin, làm hash CDC đổi theo


def test_topdev_raw_hash_ignores_relative_publish_text():
    from collection.common.url_ledger import calculate_json_canonical_hash
    from collection.sources.topdev.crawler import build_raw_payload_from_api

    item = {"id": 1, "title": "Dev", "experiences_str": "1 năm", "job_levels_str": "Nhân viên",
            "published": {"date": "30-10-2026", "since": "3 ngày trước"}}
    later = {**item, "published": {"date": "30-10-2026", "since": "1 tuần trước"}}
    first = build_raw_payload_from_api(item)
    assert first["published"] == {"date": "30-10-2026"}
    assert calculate_json_canonical_hash(first) == calculate_json_canonical_hash(build_raw_payload_from_api(later))
    flat = flatten("topdev", first)
    assert flat["raw_experience_text"] == "1 năm" and flat["raw_seniority_text"] == "Nhân viên"


def test_experience_years_takes_lower_bound_of_range():
    from app.services.source_report_service import _experience_years

    assert _experience_years("Kinh nghiệm 1 - 10 Năm") == 1
    assert _experience_years("2 đến 5 năm") == 2
    assert _experience_years("3~5 years") == 3
    assert _experience_years("Trên 3 năm") == 3
    assert _experience_years("5+ years") == 5
    assert _experience_years("Không yêu cầu kinh nghiệm") == 0
    assert _experience_years("Senior") is None
