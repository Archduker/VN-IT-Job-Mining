"""preprocessing/common: luật bảo toàn của báo cáo bước, ví dụ ổn định, cache API (P0)."""

import json

import pytest

from preprocessing.common.api_cache import ApiCache
from preprocessing.common.step_report import StepReport, StepReportError, merge_reports


def report(inp, out, dropped):
    r = StepReport("01_clean", "glints", dry_run=True)
    r.set_io(None, inp, None, out)
    r.rule("C1", "Giữ snapshot mới nhất", "drop", dropped)
    return r


def test_conserved_report_is_written(tmp_path):
    path = report(10, 7, 3).write(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["checks"]["rows_conserved"] is True
    assert data["dropped"] == [{"rule": "C1", "reason": "Giữ snapshot mới nhất", "rows": 3}]
    for key in ("step", "source", "mode", "generated_at", "code_version", "input", "output", "rules", "fields", "api"):
        assert key in data


def test_not_conserved_raises_and_writes_nothing(tmp_path):
    with pytest.raises(StepReportError):
        report(10, 7, 2).write(tmp_path)
    assert not any(tmp_path.rglob("*.json"))


def test_examples_keep_three_smallest_job_ids():
    r = StepReport("01_clean", "glints", dry_run=True)
    r.rule("C4a", "Phân loại IT", "flag", 5, [{"job_id": str(i)} for i in (5, 3, 1, 4, 2)])
    assert [e["job_id"] for e in r.data["rules"][0]["examples"]] == ["1", "2", "3"]


def test_merge_sums_sources():
    total = merge_reports("01_clean", [report(10, 7, 3), report(5, 5, 0)], dry_run=True)
    assert total.data["input"]["rows"] == 15 and total.data["output"]["rows"] == 12
    total.check_conserved()


def test_cache_hit_on_second_read(tmp_path):
    cache = ApiCache("jev", root=tmp_path)
    key = cache.key("typesafe/jev-1.13", "q", "text")
    assert cache.get(key) is None
    cache.put(key, {"p": 0.9}, cost_usd=0.00002)
    assert cache.get(key) == {"p": 0.9} and cache.cache_hits == 1 and cache.calls == 1
