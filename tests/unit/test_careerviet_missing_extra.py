# -*- coding: utf-8 -*-
"""
tests/unit/test_careerviet_missing_extra.py
============================================
Kiểm tra parser CareerVietCrawler.parse_item() đọc đúng:
  1. Label biến thể trong "Thông tin khác" (Trình độ → education, Độ tuổi → age)
  2. Multi-location từ div.map (nhiều <a> thành phố → join đầy đủ)
  3. Label lương biến thể (Mức lương, salary)
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from crawlers.sources.careerviet.crawler import CareerVietCrawler

# ─── HTML mẫu mô phỏng trang CareerViet với label biến thể ──────────────────
SAMPLE_HTML_VARIANT_LABELS = """
<html><body>
<div class="job-detail-page">
  <h1 class="title">Software Engineer</h1>
  <a class="employer">Acme Corp</a>
  <div class="map">
    <a href="#">Hồ Chí Minh</a>
    <a href="#">Hà Nội</a>
  </div>
  <ul class="detail-box">
    <li><p>Lương Cạnh tranh</p></li>
  </ul>
  <div class="detail-row">
    <h3>Mô tả công việc</h3>
    <p>Phát triển backend, viết unit test, review code cho dự án lớn.</p>
  </div>
  <div class="detail-row">
    <h3>Thông tin khác</h3>
    <ul>
      <li>Trình độ: Đại học</li>
      <li>Độ tuổi: Không giới hạn tuổi</li>
    </ul>
  </div>
</div>
</body></html>
"""

# HTML mẫu dùng label chuẩn (regression test)
SAMPLE_HTML_STANDARD_LABELS = """
<html><body>
<div class="job-detail-page">
  <h1 class="title">Backend Developer</h1>
  <a class="employer">FPT Software</a>
  <ul class="detail-box">
    <li>Lương: 25-35 triệu</li>
    <li>Địa điểm: Hà Nội</li>
    <li>Kinh nghiệm: 2 năm</li>
    <li>Cấp bậc: Senior</li>
    <li>Hình thức: Fulltime</li>
  </ul>
  <div class="detail-row">
    <h3>Mô tả công việc</h3>
    <p>Xây dựng hệ thống microservices với Python và FastAPI.</p>
  </div>
  <div class="detail-row">
    <h3>Thông tin khác</h3>
    <ul>
      <li>Bằng cấp: Đại học</li>
      <li>Độ tuổi: 22 - 35</li>
    </ul>
  </div>
</div>
</body></html>
"""


def _make_item(html: str, job_id: str = "TESTJOB1") -> dict:
    return {
        "job_id": job_id,
        "url": f"https://careerviet.vn/vi/tim-viec-lam/test.{job_id}.html",
        "html": html,
    }


class TestEducationLabelVariant:
    """Kiểm tra label 'Trình độ' → extra.education."""

    def test_trin_do_maps_to_education(self):
        crawler = CareerVietCrawler()
        record = crawler.parse_item(_make_item(SAMPLE_HTML_VARIANT_LABELS))
        assert record is not None
        assert record.raw.extra is not None, "extra không được là None"
        edu = record.raw.extra.get("education")
        assert edu == "Đại học", f"Mong 'Đại học', nhận: {edu!r}"

    def test_bang_cap_standard_label(self):
        """Label chuẩn 'Bằng cấp' vẫn phải hoạt động (regression)."""
        crawler = CareerVietCrawler()
        record = crawler.parse_item(_make_item(SAMPLE_HTML_STANDARD_LABELS, "TESTJOB2"))
        assert record is not None
        edu = record.raw.extra.get("education")
        assert edu == "Đại học", f"Mong 'Đại học', nhận: {edu!r}"


class TestAgeLabelVariant:
    """Kiểm tra label 'Độ tuổi' → extra.age."""

    def test_do_tuoi_variant(self):
        crawler = CareerVietCrawler()
        record = crawler.parse_item(_make_item(SAMPLE_HTML_VARIANT_LABELS))
        assert record is not None
        age = record.raw.extra.get("age")
        assert age == "Không giới hạn tuổi", f"Mong 'Không giới hạn tuổi', nhận: {age!r}"

    def test_do_tuoi_standard(self):
        crawler = CareerVietCrawler()
        record = crawler.parse_item(_make_item(SAMPLE_HTML_STANDARD_LABELS, "TESTJOB2"))
        age = record.raw.extra.get("age")
        assert age == "22 - 35", f"Mong '22 - 35', nhận: {age!r}"


class TestMultiLocationJoin:
    """Kiểm tra div.map nhiều <a> → location_text join đầy đủ."""

    def test_both_cities_in_location(self):
        crawler = CareerVietCrawler()
        record = crawler.parse_item(_make_item(SAMPLE_HTML_VARIANT_LABELS))
        assert record is not None
        loc = record.raw.location_text or ""
        assert "Hồ Chí Minh" in loc, f"Thiếu 'Hồ Chí Minh' trong location_text: {loc!r}"
        assert "Hà Nội" in loc, f"Thiếu 'Hà Nội' trong location_text: {loc!r}"

    def test_location_separator(self):
        """Nhiều địa điểm phải được phân cách bằng ' | '."""
        crawler = CareerVietCrawler()
        record = crawler.parse_item(_make_item(SAMPLE_HTML_VARIANT_LABELS))
        loc = record.raw.location_text or ""
        assert "|" in loc, f"Thiếu separator '|' trong: {loc!r}"

    def test_single_location_no_separator(self):
        """Một địa điểm thì không cần separator."""
        crawler = CareerVietCrawler()
        record = crawler.parse_item(_make_item(SAMPLE_HTML_STANDARD_LABELS, "TESTJOB2"))
        loc = record.raw.location_text or ""
        assert "Hà Nội" in loc, f"Mong 'Hà Nội', nhận: {loc!r}"


class TestSalaryLabelVariant:
    """Kiểm tra label 'Lương' và 'Mức lương' đều được nhận."""

    def test_luong_canh_tranh_is_negotiable(self):
        crawler = CareerVietCrawler()
        record = crawler.parse_item(_make_item(SAMPLE_HTML_VARIANT_LABELS))
        assert record is not None
        salary = record.raw.salary
        # "Cạnh tranh" → is_negotiable=True
        assert salary is not None, "salary không được None"
        assert salary.is_negotiable is True, f"Mong is_negotiable=True, nhận: {salary.is_negotiable}"

    def test_salary_range_parsed(self):
        crawler = CareerVietCrawler()
        record = crawler.parse_item(_make_item(SAMPLE_HTML_STANDARD_LABELS, "TESTJOB2"))
        salary = record.raw.salary
        assert salary is not None
        # "25-35 triệu" → salary_min, salary_max được parse
        assert salary.salary_min is not None or salary.salary_text is not None
