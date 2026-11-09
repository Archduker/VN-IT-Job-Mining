# -*- coding: utf-8 -*-
"""scripts/report_raw_problems_r2.py: chọn file raw và snapshot mới nhất (không chạm mạng)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import report_raw_problems_r2 as rr  # noqa: E402


def test_keep_key_skips_sub_dirs_and_non_json():
    assert rr.keep_key("raw/topcv/2026-10-20/123_v1.json")
    assert not rr.keep_key("raw/topcv/2026-10-20/_manifest/run_1.json")
    assert not rr.keep_key("raw/topcv/_index/2026-10-20/run_1.json")
    assert not rr.keep_key("raw/jobsgo/2026-10-20/_listing/page_0001.html")
    assert not rr.keep_key("raw/.keep")


def _env(job_id, scraped_at, version):
    return {"metadata": {"job_id": job_id, "scraped_at": scraped_at, "version": version}}


def test_latest_per_job_prefers_newest_scrape_then_version():
    snaps = [("a", _env("1", "2026-10-20T00:00:00", 1)), ("b", _env("1", "2026-11-01T00:00:00", 2)),
             ("c", _env("2", "2026-10-20T00:00:00", 1)), ("d", _env("", "2026-10-20T00:00:00", 1))]
    got = {e["metadata"]["job_id"]: e["metadata"]["version"] for e in rr.latest_per_job(snaps)}
    assert got == {"1": 2, "2": 1}
