# -*- coding: utf-8 -*-
"""Unit tests cho các Crawler nguồn độc lập (TopDev, VietnamWorks, CareerViet, ViecLam24h, TopCV).
"""

from unittest.mock import MagicMock, patch
import pytest

from crawlers.common.schema import JobRecord
from crawlers.sources.topdev.crawler import TopDevCrawler
from crawlers.sources.vietnamworks.crawler import VietnamWorksCrawler
from crawlers.sources.careerviet.crawler import CareerVietCrawler
from crawlers.sources.vieclam24h.crawler import ViecLam24hCrawler
from crawlers.sources.topcv.crawler import TopCVCrawler


def test_topdev_crawler_parse_item():
    crawler = TopDevCrawler(max_items=1)
    raw_item = {
        "id": 999999,
        "title": "Senior Python Developer",
        "slug": "senior-python-developer",
        "company": {"display_name": "Tech Corp"},
        "salary": {"is_negotiable": "0", "min": "20000000", "max": "35000000", "currency": "VND"},
        "skills": [{"name_vi": "Python"}, {"name_vi": "Django"}],
        "addresses": {"address_region_list": "TP. Hồ Chí Minh"},
        "content": "<p>Tuyển Senior Python Developer</p>",
        "published_at": "2026-10-06T10:00:00Z",
        "requirements_original": "<p>Y&ecirc;u cầu 3 năm kinh nghiệm</p>",
        "benefits_v2": [
            {
                "name": "Bảo hiểm",
                "description": "<p>Chế độ ch&iacute;nh s&aacute;ch: Lương thưởng cạnh tranh tr&ecirc;n thị trường</p>",
            }
        ],
    }
    record = crawler.parse_item(raw_item)
    assert record is not None
    assert isinstance(record, JobRecord)
    assert record.meta.source == "topdev"
    assert record.meta.source_job_id == "999999"
    assert record.raw.title == "Senior Python Developer"
    assert record.raw.company == "Tech Corp"
    assert "Python, Django" in (record.raw.skills_text or "")
    assert record.raw.description_text == "Tuyển Senior Python Developer"
    assert record.raw.requirements_text == "Yêu cầu 3 năm kinh nghiệm"
    assert "Chế độ chính sách: Lương thưởng cạnh tranh trên thị trường" in (record.raw.benefits_text or "")
    assert "<p>" not in (record.raw.benefits_text or "")


def test_vietnamworks_crawler_parse_item():
    crawler = VietnamWorksCrawler(max_items=1)
    raw_item = {
        "jobId": 888888,
        "jobTitle": "DevOps Engineer",
        "jobUrl": "https://www.vietnamworks.com/devops-engineer-888888-jv",
        "companyName": "Cloud Solutions Ltd",
        "prettySalary": "1500 - 2500 USD",
        "jobDescription": "<div>Deploy Kubernetes and Docker</div>",
        "jobRequirement": "<div>3+ years experience</div>",
        "skills": [{"skillName": "Kubernetes"}, {"skillName": "Docker"}],
        "locations": [{"cityName": "Hà Nội"}],
        "createdOn": "2026-10-06T08:00:00Z",
    }
    record = crawler.parse_item(raw_item)
    assert record is not None
    assert record.meta.source == "vietnamworks"
    assert record.meta.source_job_id == "888888"
    assert record.raw.title == "DevOps Engineer"
    assert record.raw.company == "Cloud Solutions Ltd"
    assert "Kubernetes, Docker" in (record.raw.skills_text or "")
    assert record.raw.salary_text == "1500 - 2500 USD"


def test_careerviet_crawler_parse_item():
    crawler = CareerVietCrawler(max_items=1)
    raw_item = {
        "job_id": "35C11223",
        "url": "https://careerviet.vn/vi/tim-viec-lam/frontend-engineer.35C11223.html",
        "html": """
        <html>
            <head><title>Frontend Engineer tại VNG</title></head>
            <body>
                <div class="job-detail-page">
                    <h2>Frontend Engineer</h2>
                    <a class="employer">VNG Corporation</a>
                    <strong>Thương lượng</strong>
                    <div class="detail-row">
                        <h2>Mô tả Công việc</h2>
                        <p>Lập trình ReactJS và Next.js</p>
                    </div>
                </div>
            </body>
        </html>
        """,
    }
    record = crawler.parse_item(raw_item)
    assert record is not None
    assert record.meta.source == "careerviet"
    assert record.meta.source_job_id == "35C11223"
    assert record.raw.title == "Frontend Engineer"
    assert record.raw.company == "VNG Corporation"
    assert "ReactJS" in record.raw.description_text


def test_vieclam24h_crawler_parse_item():
    crawler = ViecLam24hCrawler(max_items=1)
    raw_item = {
        "id": 777777,
        "title": "Kỹ Sư Phần Mềm",
        "title_slug": "ky-su-phan-mem",
        "employer_info": {"name": "FPT Software"},
        "job_requirement_html": "<p>Phát triển hệ thống microservices</p>",
        "salary_min": 15000000,
        "salary_max": 25000000,
        "places": [{"city_name": "Đà Nẵng"}],
    }
    record = crawler.parse_item(raw_item)
    assert record is not None
    assert record.meta.source == "vieclam24h"
    assert record.meta.source_job_id == "777777"
    assert record.raw.title == "Kỹ Sư Phần Mềm"
    assert record.raw.company == "FPT Software"
    assert "microservices" in record.raw.description_text


def test_topcv_crawler_parse_item():
    crawler = TopCVCrawler(max_items=1)
    raw_item = {
        "job_id": "666666",
        "url": "https://www.topcv.vn/viec-lam/data-analyst/666666.html",
        "title": "Data Analyst (SQL / PowerBI)",
        "company": "Shopee",
        "salary": "20 - 30 triệu",
        "html_snippet": "<div>Phân tích số liệu thương mại điện tử</div>",
    }
    record = crawler.parse_item(raw_item)
    assert record is not None
    assert record.meta.source == "topcv"
    assert record.meta.source_job_id == "666666"
    assert record.meta.language == "vi"
    assert record.raw.title == "Data Analyst (SQL / PowerBI)"
    assert record.raw.company == "Shopee"
    assert record.raw.salary_min == 20.0
    assert record.raw.salary_max == 30.0
    assert record.raw.salary_currency == "VND"


def test_base_crawler_writes_json_array(tmp_path):
    class DummyCrawler(TopDevCrawler):
        def fetch_items(self):
            yield {
                "id": 111,
                "title": "Python Dev",
                "slug": "python-dev",
                "company": {"display_name": "Company A"},
                "salary": {"currency": "VND"},
                "skills": [],
                "content": "<p>Content A</p>",
            }

    crawler = DummyCrawler(output_dir=tmp_path, checkpoint_dir=tmp_path, max_items=1)
    stats = crawler.run()
    assert stats["crawled"] == 1
    out_file = stats["output_file"]
    assert out_file.endswith(".json")

    import json
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["_meta"]["source"] == "topdev"
