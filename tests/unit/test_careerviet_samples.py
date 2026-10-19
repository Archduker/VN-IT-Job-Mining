# -*- coding: utf-8 -*-
"""Unit test cho 3 bộ mẫu đã cam kết trong crawlers/sources/careerviet/samples/.

Mục đích: chứng minh mỗi cặp ({job_id}.html + {job_id}_v1.json) là
TÁI LẬP ĐƯỢC và TẤT ĐỊNH từ chính HTML thô, không phụ thuộc data/ cục bộ.

Khong goi mang, khong doc data/. Duong dan samples dinh vi theo __file__
(thu muc ngay trong repo), dung pathlib.
"""

import json
from pathlib import Path

import pytest

from crawlers.sources.careerviet.raw_envelope import (
    build_raw_envelope,
    container_text_for_hash,
    hash_container_text,
)

# samples/ nam trong repo: tests/unit/test_x.py -> parents[2] = goc repo
SAMPLES = Path(__file__).resolve().parents[2] / "crawlers" / "sources" / "careerviet" / "samples"

EXPECTED_METADATA_KEYS = {
    "job_id", "source", "source_url", "scraped_at",
    "scraper_version", "version", "content_hash", "source_category",
}
EXPECTED_PAYLOAD_KEYS = {
    "title", "job-company-name", "detail-box", "detail-row",
    "job-tags", "map", "Ngành nghề", "job-posting-schema",
}


def _sample_ids() -> list[str]:
    ids = sorted(p.stem for p in SAMPLES.glob("*.html"))
    assert ids, f"Khong tim thay sample HTML nao trong {SAMPLES}"
    return ids


def _load_stored(job_id: str) -> dict:
    fp = SAMPLES / f"{job_id}_v1.json"
    assert fp.exists(), f"Thieu envelope da luu: {fp}"
    return json.loads(fp.read_text(encoding="utf-8"))


def test_samples_dir_present_and_paired():
    """ Moi .html phai co .json tu ung, va nguoc lai (cau truc cap)."""
    html_ids = {p.stem for p in SAMPLES.glob("*.html")}
    json_ids = {p.stem[:-len("_v1")] for p in SAMPLES.glob("*_v1.json")}
    assert html_ids == json_ids
    assert len(html_ids) == 3


@pytest.mark.parametrize("job_id", _sample_ids())
def test_rebuild_metadata_keys(job_id):
    html = (SAMPLES / f"{job_id}.html").read_text(encoding="utf-8")
    env = build_raw_envelope(html, job_id, f"https://careerviet.vn/viec-lam/{job_id}.html")
    assert set(env["metadata"]) == EXPECTED_METADATA_KEYS
    assert env["metadata"]["job_id"] == job_id
    assert env["metadata"]["source"] == "careerviet"
    assert len(env["metadata"]["content_hash"]) == 64


@pytest.mark.parametrize("job_id", _sample_ids())
def test_rebuild_payload_keys(job_id):
    html = (SAMPLES / f"{job_id}.html").read_text(encoding="utf-8")
    env = build_raw_envelope(html, job_id, f"https://careerviet.vn/viec-lam/{job_id}.html")
    assert set(env["raw_payload"]) == EXPECTED_PAYLOAD_KEYS


@pytest.mark.parametrize("job_id", _sample_ids())
def test_hash_is_deterministic_two_runs(job_id):
    """Chay build_raw_envelope 2 lan -> content_hash giong het; ham rieng le cung vay."""
    html = (SAMPLES / f"{job_id}.html").read_text(encoding="utf-8")
    h1 = build_raw_envelope(html, job_id, "u")["metadata"]["content_hash"]
    h2 = build_raw_envelope(html, job_id, "u")["metadata"]["content_hash"]
    assert h1 == h2
    c1 = hash_container_text(container_text_for_hash(html))
    c2 = hash_container_text(container_text_for_hash(html))
    assert c1 == c2 == h1


@pytest.mark.parametrize("job_id", _sample_ids())
def test_stored_envelope_matches_rebuilt_from_html(job_id):
    """Envelope da luu phai tai lap duoc tu HTML tho (content_hash va cac khoa co dinh)."""
    stored = _load_stored(job_id)
    html = (SAMPLES / f"{job_id}.html").read_text(encoding="utf-8")
    rebuilt = build_raw_envelope(
        html, job_id, stored["metadata"]["source_url"],
        source_category=stored["metadata"]["source_category"],
    )
    assert stored["metadata"]["content_hash"] == rebuilt["metadata"]["content_hash"]
    assert stored["metadata"]["job_id"] == job_id
    assert stored["metadata"]["version"] == 1
    # source_category luu giu DUNG gia tri that trong file (khong doi, khong suy dien)
    assert stored["metadata"]["source_category"] == rebuilt["metadata"]["source_category"]
    assert set(stored["raw_payload"]) == EXPECTED_PAYLOAD_KEYS
