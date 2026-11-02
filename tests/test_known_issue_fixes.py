# -*- coding: utf-8 -*-
"""Tests for the Crawling page status, SSE log stream, and source flattener fixes."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
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
    data = crawler_module.crawler_service.get_weekly_crawl_schedule()
    assert {row["status"] for row in data["phase1_discovery"]} == {"UNKNOWN"}
    assert {row["scheduled_time"] for row in data["phase2_detail"]} == {"09, 14, 18, 21, 22h"}


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


def test_careerviet_tags_are_not_skills():
    assert flatten("careerviet", {"title": "AI Engineer", "job-tags": ["Kỹ sư viễn thông"]})["skills_list"] == []


def test_jobsgo_occupations_are_category_not_skills():
    flat = flatten("jobsgo", {"title": "Dev", "occupations": ["CNTT - Phần mềm"]})
    assert flat["skills_list"] == []
    assert flat["raw_category_text"] == "CNTT - Phần mềm"


def test_topdev_experience_and_level_from_html_payload():
    flat = flatten("topdev", {"title": "Dev", "experience": "3 năm", "seniority_text": "Senior"})
    assert flat["raw_experience_text"] == "3 năm"
    assert flat["raw_seniority_text"] == "Senior"


def test_topdev_experience_from_api_extra():
    flat = flatten("topdev", {"title": "Dev", "extra": {"experience": "2 năm"}, "job_levels_str": "Junior"})
    assert flat["raw_experience_text"] == "2 năm"
    assert flat["raw_seniority_text"] == "Junior"
