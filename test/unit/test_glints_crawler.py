# -*- coding: utf-8 -*-
"""Unit tests for GlintsCrawler. These tests do not call the real Glints site."""

import json
import unittest
from unittest.mock import patch

from crawlers.sources.glints.crawler import (
    GlintsCrawler,
    detect_language,
    extract_jobposting,
    format_amount,
    html_to_text,
    html_to_text_list,
    slugify,
)


class FakeResponse:
    def __init__(self, *, data=None, text="", status_code=200, headers=None):
        self._data = data
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class FakeHttpClient:
    def __init__(self, *, listing_data=None, html=""):
        self.listing_data = listing_data or {}
        self.html = html
        self.post_calls = []
        self.get_calls = []

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(data=self.listing_data, headers={"Content-Type": "application/json"})

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse(text=self.html, headers={"Content-Type": "text/html; charset=utf-8"})


class GlintsCrawlerTests(unittest.TestCase):
    def setUp(self):
        self.html = (
            '<!DOCTYPE html><html><head>'
            '<script type="application/ld+json" data-next-head="">'
            + json.dumps({
                "@context": "https://schema.org/",
                "@type": "JobPosting",
                "title": "Kỹ sư phần mềm",
                "description": (
                    "<p>Giới thiệu công việc</p>"
                    "<p><strong>Yêu cầu</strong></p>"
                    "<ul><li>Python</li><li>SQL</li></ul>"
                ),
                "datePosted": "2026-10-01T00:00:00Z",
                "validThrough": "2026-11-01",
                "hiringOrganization": {"@type": "Organization", "name": "Công ty Ví dụ"},
                "baseSalary": {
                    "@type": "MonetaryAmount",
                    "currency": "VND",
                    "value": {"minValue": 9000000, "maxValue": 20000000, "unitText": "MONTH"},
                },
                "skills": "Python, SQL",
                "jobBenefits": "career growth",
                "employmentType": "FULL_TIME",
                "jobLocationType": "TELECOMMUTE",
            }, ensure_ascii=False)
            + '</script></head><body></body></html>'
        )
        listing = {
            "data": {
                "searchJobsV3": {
                    "jobsInPage": [
                        {
                            "id": "job-123",
                            "title": "Software Engineer",
                            "createdAt": "2026-10-01T00:00:00Z",
                            "company": {"id": "company-1", "name": "Example Ltd"},
                            "location": {"formattedName": "Ho Chi Minh City"},
                            "country": {"name": "Vietnam"},
                            "salaries": [],
                            "skills": [
                                {"mustHave": True, "skill": {"name": "Python"}},
                                {"mustHave": False, "skill": {"name": "SQL"}},
                            ],
                            "type": "FULL_TIME",
                        }
                    ],
                    "hasMore": False,
                }
            }
        }
        self.http = FakeHttpClient(listing_data=listing, html=self.html)
        self.crawler = GlintsCrawler(max_items=2, http_client=self.http)

    def test_extract_jobposting_from_jsonld(self):
        posting = extract_jobposting(self.html)
        self.assertEqual(posting["title"], "Kỹ sư phần mềm")
        self.assertEqual(posting["validThrough"], "2026-11-01")

    def test_html_to_text_removes_tags_and_keeps_line_breaks(self):
        source = "<p>Intro</p><ul><li>AA</li><li>BB</li></ul>"
        result = html_to_text(source)
        self.assertNotIn("<p>", result)
        self.assertNotIn("<li>", result)
        self.assertIn("Intro", result)
        self.assertIn("- AA\n- BB", result)
        self.assertEqual(html_to_text_list(source), ["Intro", "- AA", "- BB"])

    def test_format_amount_avoids_scientific_notation(self):
        self.assertEqual(format_amount(9_000_000.0), "9,000,000")
        self.assertEqual(format_amount(20_000_000.0), "20,000,000")

    def test_slugify_vietnamese_title(self):
        self.assertEqual(slugify("Chuyên Viên Ứng Dụng AI"), "chuyen-vien-ung-dung-ai")

    def test_detect_language(self):
        self.assertEqual(detect_language("Nhân viên kế toán", "Công ty A", "Mô tả công việc và yêu cầu ứng viên."), "vi")
        self.assertEqual(detect_language("Software Engineer", "Example Ltd", "Responsibilities and requirements for this role with experience."), "en")

    def test_fetch_items_paginates_response(self):
        jobs = list(self.crawler.fetch_items())
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], "job-123")
        self.assertEqual(len(self.http.post_calls), 1)
        self.assertIn("CountryCode", self.http.post_calls[0][1]["json"]["variables"]["data"])

    def test_fetch_jobposting_details_gets_jsonld(self):
        posting = self.crawler.fetch_jobposting_details("https://glints.com/example")
        self.assertEqual(posting.get("title"), "Kỹ sư phần mềm")
        self.assertEqual(len(self.http.get_calls), 1)

    def test_posted_date_fallback_from_days_left_and_deadline(self):
        job = {
            "id": "job-date-fallback",
            "title": "Software Engineer",
            "company": {"name": "Example Ltd"},
            "skills": [],
        }
        posting = {
            "@type": "JobPosting",
            "title": "Software Engineer",
            "description": "Responsibilities. 14 days left",
            "validThrough": "2026-11-10",
            "hiringOrganization": {"name": "Example Ltd"},
        }
        with patch.object(self.crawler, "fetch_jobposting_details", return_value=posting):
            with patch("crawlers.sources.glints.crawler.JobRecord.create", return_value="record") as create:
                self.crawler.parse_item(job)
        raw = create.call_args.kwargs["raw_data"]
        self.assertEqual(raw["posted_date_text"], "2026-10-27")

    def test_parse_item_normalizes_schema_and_description(self):
        job = {
            "id": "job-123",
            "title": "Software Engineer",
            "createdAt": "2026-10-01T00:00:00Z",
            "company": {"id": "company-1", "name": "Example Ltd"},
            "location": {"formattedName": "Ho Chi Minh City"},
            "country": {"name": "Vietnam"},
            "salaries": [],
            "skills": [
                {"mustHave": True, "skill": {"name": "Python"}},
                {"mustHave": False, "skill": {"name": "SQL"}},
            ],
            "type": "FULL_TIME",
        }
        with patch.object(self.crawler, "fetch_jobposting_details", return_value=extract_jobposting(self.html)):
            with patch("crawlers.sources.glints.crawler.JobRecord.create", return_value="record") as create:
                result = self.crawler.parse_item(job)

        self.assertEqual(result, "record")
        payload = create.call_args.kwargs
        self.assertEqual(payload["source"], "glints")
        self.assertEqual(payload["source_job_id"], "job-123")
        raw = payload["raw_data"]
        self.assertTrue(raw["extra"]["description_available"])
        self.assertIn("<p>", raw["description_html"])
        self.assertNotIn("<p>", raw["description_text"])
        self.assertEqual(raw["salary"]["salary_min"], 9000000.0)
        self.assertEqual(raw["salary"]["salary_text"], "9,000,000 - 20,000,000 VND / month")
        self.assertEqual(raw["deadline_text"], "2026-11-01")
        self.assertIn("Python", raw["tags"]["skills"])
        self.assertEqual(payload["language"], "vi")


if __name__ == "__main__":
    unittest.main()
