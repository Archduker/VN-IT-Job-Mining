# -*- coding: utf-8 -*-
"""Unit test cho raw envelope của CareerViet trong crawlers/sources/careerviet/crawler.py.

Dung HTML MINI trong tmp_path (khong phu thuoc data/ cuc bo), dung pathlib.
Bao dam:
- container_text_for_hash tuong thich calculate_container_html_hash (co False).
- Doi ngay -> hash KHONG doi (co True) va CO doi (co False).
- Doi noi dung JD -> hash DOI o ca hai co.
- Envelope dung metadata 8 khoa; JSON-LD nguyen ban; loc/missing JSON-LD -> None.
"""

import hashlib
from pathlib import Path

from bs4 import BeautifulSoup
from crawlers.common.url_ledger import calculate_container_html_hash
from crawlers.sources.careerviet.crawler import (
    CONTAINER_SELECTOR,
    build_raw_envelope,
    build_raw_payload,
    container_text_for_hash,
    extract_job_posting_jsonld,
)


def _html(update_date="15/10/2026", deadline_date="27/10/2026", jd_text="Build backend APIs"):
    return f"""<!DOCTYPE html><html><body>
<div class="job-detail-page">
  <h1 class="title">Senior Python Developer</h1>
  <a class="employer job-company-name">ABC Tech</a>
  <ul class="detail-box">
    <li><strong>Ngày cập nhật</strong><p>{update_date}</p></li>
    <li><strong>Lương</strong><p>Cạnh tranh</p></li>
    <li><strong>Kinh nghiệm</strong><p>2 - 3 Năm</p></li>
    <li><strong>Hết hạn nộp</strong><p>{deadline_date}</p></li>
  </ul>
  <div class="detail-row"><h2>Mô tả Công việc</h2><p>{jd_text}</p></div>
  <div class="map"><p><a>Hà Nội</a><a>Hồ Chí Minh</a></p></div>
  <div class="job-tags"><a class="tag-item">Python</a><a class="tag-item">Django</a></div>
  <script id="job-posting-schema" type="application/ld+json">
    {{"@context":"http://schema.org","@type":"JobPosting","title":"Senior Python Developer","skills":"Python, Django"}}
  </script>
</div>
</body></html>"""


def _write(tmp_path: Path, name: str, html: str) -> str:
    fp = tmp_path / name
    fp.write_text(html, encoding="utf-8")
    return fp.read_text(encoding="utf-8")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_flag_false_equivalent_to_shared_hash(tmp_path):
    html = _write(tmp_path, "job.html", _html())
    mine = _sha(container_text_for_hash(html, CONTAINER_SELECTOR, exclude_volatile_dates=False))
    shared = calculate_container_html_hash(html, container_selector=CONTAINER_SELECTOR)
    assert mine == shared


def test_date_change_hash_stable_when_flag_true_and_changes_when_false(tmp_path):
    html_a = _write(tmp_path, "a.html", _html(update_date="15/10/2026", deadline_date="27/10/2026"))
    html_b = _write(tmp_path, "b.html", _html(update_date="03/11/2026", deadline_date="15/12/2026"))

    # Cờ BẬT: chỉ đổi ngày -> hash không đổi
    assert _sha(container_text_for_hash(html_a, exclude_volatile_dates=True)) == _sha(
        container_text_for_hash(html_b, exclude_volatile_dates=True)
    )
    # Cờ TẮT: ngày vẫn nằm trong khối -> hash đổi
    assert _sha(container_text_for_hash(html_a, exclude_volatile_dates=False)) != _sha(
        container_text_for_hash(html_b, exclude_volatile_dates=False)
    )


def test_jd_content_change_breaks_hash_both_flags(tmp_path):
    html_x = _write(tmp_path, "x.html", _html(jd_text="Build backend APIs"))
    html_y = _write(tmp_path, "y.html", _html(jd_text="Design machine learning models"))

    assert _sha(container_text_for_hash(html_x, exclude_volatile_dates=True)) != _sha(
        container_text_for_hash(html_y, exclude_volatile_dates=True)
    )
    assert _sha(container_text_for_hash(html_x, exclude_volatile_dates=False)) != _sha(
        container_text_for_hash(html_y, exclude_volatile_dates=False)
    )


def test_envelope_metadata_and_payload(tmp_path):
    html = _write(tmp_path, "job.html", _html())
    env = build_raw_envelope(html, "35C8FFFF", "https://careerviet.vn/x.html", source_category="c1")

    meta = env["metadata"]
    assert set(meta) == {
        "job_id", "source", "source_url", "scraped_at",
        "scraper_version", "version", "content_hash", "canonical_hash", "field_hashes", "source_category",
    }
    assert meta["source"] == "careerviet"
    assert meta["source_category"] == "c1"
    assert meta["version"] == 1
    assert len(meta["content_hash"]) == 64
    assert len(meta["canonical_hash"]) == 64
    assert isinstance(meta["field_hashes"], dict)

    payload = env["raw_payload"]
    assert payload["title"] == "Senior Python Developer"
    assert payload["job-company-name"] == "ABC Tech"
    assert payload["map"] == "Hà Nội, Hồ Chí Minh"
    assert "Python" in payload["job-tags"]
    # "2 - 3 Năm" KHONG bi dinh lien (con khoang trang giua so va "Năm")
    joined = " ".join(payload["detail-box"])
    assert "Năm" in joined and "3Năm" not in joined


def test_jsonld_broken_or_missing_returns_none(tmp_path):
    broken = """<div class="job-detail-page">
      <h1 class="title">T</h1>
      <script id="job-posting-schema" type="application/ld+json">{ khong phai JSON }</script>
    </div>"""
    soup_broken = BeautifulSoup(broken, "html.parser")
    assert extract_job_posting_jsonld(soup_broken) is None

    missing = """<div class="job-detail-page">
      <h1 class="title">T</h1>
    </div>"""
    soup_missing = BeautifulSoup(missing, "html.parser")
    assert extract_job_posting_jsonld(soup_missing) is None

    # build_raw_envelope khong duoc crash khi JSON-LD hong
    env = build_raw_envelope(broken, "J1", "https://x/y", source_category=None)
    assert env["metadata"]["source_category"] is None
    assert "job-posting-schema" not in env["raw_payload"]
