# -*- coding: utf-8 -*-
"""Unit tests cho module crawler và parser của nguồn ITViec.

Kiểm thử toàn diện:
1. Xác định URL tin tuyển dụng hợp lệ (is_job_url) và bóc tách job_id.
2. Bóc tách dữ liệu thô (parse_detail) từ HTML có JSON-LD và sections.
3. Tính toán mã băm nội dung lai (compute_content_hash) phát hiện thay đổi.
4. Kiểm thử khởi tạo và cấu hình của ITViecCrawler.
"""

import json
from pathlib import Path
import pytest

from crawlers.sources.itviec import config as C
from crawlers.sources.itviec import parser
from crawlers.sources.itviec.crawler import ItviecCrawler


SAMPLE_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    "title": "Senior Python Backend Engineer",
    "description": "<p>Phát triển hệ thống microservices backend với Python.</p>",
    "employmentType": "FULL_TIME",
    "hiringOrganization": {
      "@type": "Organization",
      "name": "Tech Corp Vietnam",
      "sameAs": "https://itviec.com/nha-tuyen-dung/tech-corp"
    },
    "baseSalary": {
      "@type": "MonetaryAmount",
      "currency": "USD",
      "value": {
        "@type": "QuantitativeValue",
        "minValue": 2000,
        "maxValue": 3500
      }
    },
    "skills": "Python, FastAPI, Docker, PostgreSQL"
  }
  </script>
</head>
<body>
  <div class="jd-header">
    <h1 class="job-details__title">Senior Python Backend Engineer</h1>
    <div class="employer-name">
      <a href="/nha-tuyen-dung/tech-corp">Tech Corp Vietnam</a>
    </div>
    <div class="job-details__salary">
      <span class="salary-text">2,000 - 3,500 USD</span>
    </div>
  </div>
  <div class="jd-main">
    <section class="job-content">
      <h2>Mô tả công việc</h2>
      <p>- Xây dựng các API backend hiệu năng cao bằng Python FastAPI.</p>
      <h2>Yêu cầu công việc</h2>
      <p>- Tối thiểu 3 năm kinh nghiệm với Python, Docker, PostgreSQL.</p>
      <h2>Tại sao bạn sẽ yêu thích làm việc tại đây</h2>
      <p>- Mức lương cạnh tranh, cấp MacBook Pro, bảo hiểm sức khỏe quốc tế.</p>
    </section>
  </div>
</body>
</html>"""


def test_is_job_url():
    """Kiểm tra nhận diện đúng URL tin tuyển dụng ITViec."""
    assert parser.is_job_url("https://itviec.com/viec-lam-it/senior-python-engineer-tech-corp-1234")
    assert parser.is_job_url("https://itviec.com/viec-lam-it/devops-engineer-fpt-5678")
    # Không phải tin tuyển dụng (trang danh mục / tag / search)
    assert not parser.is_job_url("https://itviec.com/viec-lam-it/python")
    assert not parser.is_job_url("https://itviec.com/viec-lam-it/ho-chi-minh")
    assert not parser.is_job_url("https://itviec.com/viec-lam-it")
    assert not parser.is_job_url("")


def test_extract_job_id():
    """Kiểm tra trích xuất job slug từ URL."""
    url = "https://itviec.com/viec-lam-it/senior-backend-engineer-vng-9876"
    assert parser.extract_job_id(url) == "senior-backend-engineer-vng-9876"


def test_parse_detail_with_jsonld():
    """Kiểm tra parser bóc tách đầy đủ thông tin từ HTML và JSON-LD."""
    result = parser.parse_detail(SAMPLE_HTML, "senior-python-backend-engineer-1234")

    assert result["title"] == "Senior Python Backend Engineer"
    assert result["company_name"] == "Tech Corp Vietnam"
    assert result["company_url"] == "/nha-tuyen-dung/tech-corp"
    assert "2,000 - 3,500 USD" in result["salary_display_text"]
    assert "Python, FastAPI, Docker, PostgreSQL" in result["skill_tags"]
    assert "Mô tả công việc" in result["sections"]
    assert "Yêu cầu công việc" in result["sections"]
    assert "Tại sao bạn sẽ yêu thích làm việc tại đây" in result["sections"]
    assert result["job_posting_jsonld"]["@type"] == "JobPosting"


def test_compute_content_hash():
    """Kiểm tra tính toán content_hash LAI (Clean Container + Canonical JSON-LD)."""
    parsed = parser.parse_detail(SAMPLE_HTML)
    hash1 = parser.compute_content_hash(
        SAMPLE_HTML,
        parsed.get("job_posting_jsonld"),
        container_selector="section.job-content",
    )
    assert isinstance(hash1, str)
    assert len(hash1) == 64

    # Hash phải không đổi khi HTML và JSON-LD giữ nguyên
    hash2 = parser.compute_content_hash(
        SAMPLE_HTML,
        parsed.get("job_posting_jsonld"),
        container_selector="section.job-content",
    )
    assert hash1 == hash2


def test_itviec_crawler_init(tmp_path):
    """Kiểm tra khởi tạo đối tượng ItviecCrawler kế thừa BaseCrawler."""
    crawler = ItviecCrawler(
        output_dir=str(tmp_path / "itviec"),
        max_items=5,
    )
    assert crawler.source_name == "itviec"
    assert crawler.max_items == 5
    assert crawler.output_dir == str(tmp_path / "itviec")
    assert crawler.ledger is not None
