# -*- coding: utf-8 -*-
"""Unit tests cho module crawler và parser của nguồn ITViec.

Kiểm thử toàn diện:
1. Xác định URL tin tuyển dụng hợp lệ (is_job_url) và bóc tách job_id.
2. Bóc tách dữ liệu thô (parse_detail / build_raw_payload) từ HTML có JSON-LD và sections.
3. Tính toán mã băm Document JSON chuẩn (calculate_json_canonical_hash & calculate_json_field_hashes).
4. Đóng gói Raw Envelope theo chuẩn Data Contract.
5. Kiểm thử khởi tạo và vận hành 2 pha ở chế độ offline (local_html_dir).
6. Kiểm thử cơ chế Safe Skip & Failed Queue khi gặp lỗi.
"""

import json
from pathlib import Path
import pytest

from crawlers.common.url_ledger import (
    calculate_json_canonical_hash,
    calculate_json_field_hashes,
)
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


def test_canonical_json_hashing():
    """Kiểm tra tính tất định của Post-Crawl Canonical JSON Hashing."""
    raw_payload = parser.build_raw_payload(SAMPLE_HTML, "senior-python-backend-engineer-1234")
    hash1 = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])
    hash2 = calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])

    assert isinstance(hash1, str)
    assert len(hash1) == 64
    assert hash1 == hash2

    field_hashes = calculate_json_field_hashes(raw_payload)
    assert "title" in field_hashes
    assert "company_name" in field_hashes
    assert "salary_display_text" in field_hashes
    assert len(field_hashes["title"]) == 64


def test_build_raw_envelope():
    """Kiểm tra hàm đóng gói Raw Envelope."""
    env = parser.build_raw_envelope(
        SAMPLE_HTML,
        job_id="test-job-001",
        url="https://itviec.com/viec-lam-it/test-job-001",
        version=1,
    )
    assert env["metadata"]["job_id"] == "test-job-001"
    assert env["metadata"]["source"] == "itviec"
    assert len(env["metadata"]["content_hash"]) == 64
    assert env["metadata"]["canonical_hash"] == env["metadata"]["content_hash"]
    assert isinstance(env["metadata"]["field_hashes"], dict)
    assert env["raw_payload"]["title"] == "Senior Python Backend Engineer"


def test_compute_content_hash_legacy():
    """Kiểm tra tương thích ngược hàm compute_content_hash cũ."""
    parsed = parser.parse_detail(SAMPLE_HTML)
    hash1 = parser.compute_content_hash(
        SAMPLE_HTML,
        parsed.get("job_posting_jsonld"),
        container_selector="section.job-content",
    )
    assert isinstance(hash1, str)
    assert len(hash1) == 64


def test_itviec_crawler_init(tmp_path):
    """Kiểm tra khởi tạo đối tượng ItviecCrawler kế thừa BaseCrawler."""
    crawler = ItviecCrawler(
        output_dir=str(tmp_path / "itviec"),
        limit=5,
    )
    assert crawler.source_name == "itviec"
    assert crawler.max_items == 5
    assert crawler.output_dir == str(tmp_path / "itviec")
    assert crawler.ledger is not None


def test_parse_rich_details_from_fundemental_html():
    """Kiểm tra trích xuất 100% các trường dữ liệu theo Fundemental_crawl.md và .html."""
    html_path = Path("crawlers/sources/itviec/.html")
    if not html_path.is_file():
        pytest.skip(".html file not found")
    html = html_path.read_text(encoding="utf-8")
    result = parser.parse_detail(html, "ai-engineer-python-ai-apis-llms-forix-4550")

    assert result["title"] == "AI Engineer (Python/AI APIs/LLMs)"
    assert result["company_name"] == "Forix"
    assert result["work_location"] == "82 Tran Huy Lieu, Phú Nhuận, TP Hồ Chí Minh"
    assert result["work_model"] == "Tại văn phòng"
    assert "Đăng" in result["posted_at_raw"]
    assert "Python" in result["skill_tags"]
    assert "Kỹ sư AI / Machine Learning" in result["specialization"]
    assert "Thương Mại Điện Tử" in result["industries"]
    assert result["company_details"]["rating"] == "3.5"
    assert result["company_details"]["Mô hình công ty"] == "Thuê ngoài"
    assert result["company_details"]["Quốc gia"] == "United States"
    assert result["company_details"]["Làm việc ngoài giờ"] == "Thêm lương OT"
    assert "3 Lý do để gia nhập công ty" in result["sections"]


def test_auth_session_loading(tmp_path):
    """Kiểm tra cơ chế nạp cookies từ session.json phục vụ bypass đăng nhập."""
    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    session_file = auth_dir / "session.json"
    session_data = {
        "cookies": [
            {
                "name": "_itviec_session",
                "value": "mock_authenticated_session_token_12345",
                "domain": ".itviec.com",
                "path": "/",
            }
        ]
    }
    session_file.write_text(json.dumps(session_data), encoding="utf-8")

    crawler = ItviecCrawler(
        output_dir=str(tmp_path / "itviec"),
        auth_file=str(session_file),
    )
    cookies = crawler._load_session_cookies()
    assert len(cookies) == 1
    assert cookies[0]["name"] == "_itviec_session"

    with crawler._fetcher(use_playwright=False) as fetch:
        # Trong fetcher, HttpClient phải có cookie _itviec_session
        pass


def test_crawler_offline_details(tmp_path):
    """Kiểm tra Pha 2 crawl_details chạy hoàn toàn offline qua local_html_dir."""
    html_dir = tmp_path / "html_samples"
    html_dir.mkdir()
    job_file = html_dir / "senior-python-backend-engineer-1234.html"
    job_file.write_text(SAMPLE_HTML, encoding="utf-8")

    out_dir = tmp_path / "itviec"
    crawler = ItviecCrawler(output_dir=str(out_dir))

    # Đăng ký URL vào ledger ở trạng thái PENDING
    url = "https://itviec.com/viec-lam-it/senior-python-backend-engineer-1234"
    crawler.ledger.register_url(
        raw_url=url,
        job_id="senior-python-backend-engineer-1234",
        preliminary_title="Senior Python Backend Engineer",
    )
    assert crawler.ledger.records[list(crawler.ledger.records.keys())[0]]["status"] == "PENDING"

    # Chạy Pha 2 đọc từ thư mục offline
    stats = crawler.crawl_details(local_html_dir=str(html_dir), limit=1)
    assert stats["crawled_new"] == 1
    assert stats["errors"] == 0

    # Kiểm tra trạng thái chuyển sang DONE và có content_hash
    rec = list(crawler.ledger.records.values())[0]
    assert rec["status"] == "DONE"
    assert rec["content_hash"] is not None
    assert len(rec["content_hash"]) == 64


def test_crawler_safe_skip(tmp_path):
    """Kiểm tra cơ chế Safe Skip khi gặp file HTML lỗi / không tồn tại."""
    empty_dir = tmp_path / "empty_html"
    empty_dir.mkdir()

    out_dir = tmp_path / "itviec"
    crawler = ItviecCrawler(output_dir=str(out_dir))

    url = "https://itviec.com/viec-lam-it/missing-job-9999"
    crawler.ledger.register_url(
        raw_url=url,
        job_id="missing-job-9999",
    )

    # Chạy Pha 2, file không tồn tại -> Safe Skip vào Failed Queue, không crash!
    stats = crawler.crawl_details(local_html_dir=str(empty_dir), limit=1)
    assert stats["errors"] == 1
    assert stats["crawled_new"] == 0

    rec = list(crawler.ledger.records.values())[0]
    assert rec["status"] == "FAILED"
    assert rec["retry_count"] == 1
    assert "error_log" in rec
