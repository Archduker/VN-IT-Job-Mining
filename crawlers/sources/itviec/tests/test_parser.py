# -*- coding: utf-8 -*-
"""Test parser ITviec — Data Contract v0.5.0 (cấu trúc tinh gọn).

Không commit HTML thật của website vào Git — fixture chỉ mô phỏng cấu trúc.
Chạy:  python -m pytest crawlers/sources/itviec/tests/test_parser.py -q
"""

import hashlib
import json
import os
import sys
import unittest

_itviec_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_repo_root = os.path.abspath(os.path.join(_itviec_dir, "..", "..", ".."))
sys.path.insert(0, _repo_root)
sys.path.insert(0, _itviec_dir)

import parser as job_parser  # noqa: E402

# ---------------------------------------------------------------- fixtures

LISTING_HTML = """
<html><body>
  <nav><a href="/viec-lam-it/it-support?click_source=Skill+tag">IT Support</a>
       <a href="/viec-lam-it/ha-noi">Hà Nội</a></nav>

  <div class="card-jobs-list">
    <div class="job-card ipt-2 d-flex"
         data-search--job-selection-job-slug-value="senior-backend-java-fpt-0123">
      <span class="small-text text-dark-grey">Đăng 3 ngày trước</span>
      <h3 class="imt-3"><a href="https://itviec.com/viec-lam-it/senior-backend-java-fpt-0123?lab_feature=preview_jd_page">Senior Backend Java</a></h3>
      <div class="d-flex align-items-center salary text-rich-grey">Thương lượng</div>
      <a href="/nha-tuyen-dung/fpt?lab_feature=preview_jd_page">FPT</a>
      <a href="/viec-lam-it/java?click_source=Skill+tag">Java</a>
    </div>

    <div class="job-card super-hot">
      <h3><a href="https://itviec.com/viec-lam-it/react-dev-vng-0456?utm_source=x">React Developer</a></h3>
    </div>

    <div class="job-card"
         data-search--job-selection-job-slug-value="senior-backend-java-fpt-0123">
      <h3><a href="https://itviec.com/viec-lam-it/senior-backend-java-fpt-0123">Senior Backend Java</a></h3>
    </div>

    <div class="job-card">
      <h3><a href="https://itviec.com/it-jobs/weird-link-999">Odd Layout Job</a></h3>
    </div>

    <div class="job-card"><span>?</span></div>
  </div>
</body></html>
"""

DESC_HTML = ('<p>Mô tả có <strong>HTML gốc</strong> với dấu tiếng Việt ề ~ ứ.</p>'
             '<ul><li>item 1</li></ul>')

_JOB_POSTING = {
    "@context": "http://schema.org", "@type": "JobPosting",
    "industry": "Information Technology",
    "title": "Senior Backend Java",
    "datePosted": "2026-10-01", "validThrough": "2026-10-30",
    "skills": "Java, Spring Boot, MySQL",
    "description": DESC_HTML,
    "employmentType": "FULL_TIME",
    "hiringOrganization": {"@type": "Organization", "name": "FPT Software"},
    "jobLocation": [{"@type": "Place", "address": {
        "@type": "PostalAddress", "addressLocality": "Quận 7",
        "addressRegion": "Hồ Chí Minh", "addressCountry": "VN"}}],
    "baseSalary": {"@type": "MonetaryAmount", "currency": "USD",
                   "value": {"@type": "QuantitativeValue", "unitText": "MONTH",
                             "value": "You'll love it"}},
    "jobBenefits": "<ul><li>Hybrid working</li></ul>",
    "experienceRequirements": {"@type": "OccupationalExperienceRequirements",
                               "monthsOfExperience": 24},
}

DETAIL_HTML = f"""
<html><body>
<script type="application/ld+json">{json.dumps(_JOB_POSTING, ensure_ascii=False)}</script>
<script type="application/ld+json">
{{"@context": "http://schema.org", "@type": "BreadcrumbList", "itemListElement": []}}
</script>

<h1>Senior Backend Java (bản render)</h1>
<div class="d-flex align-items-center salary"><a class="sign-in-view-salary">Đăng nhập để xem mức lương</a></div>
<a href="/nha-tuyen-dung/fpt-software?lab_feature=x">FPT Software</a>

<div class="imy-5 paragraph"><h2>Mô tả công việc</h2><p>section desc render</p></div>
<div class="imy-5 paragraph"><h2>Yêu cầu công việc</h2><ul><li>Có 2 năm kinh nghiệm Java</li></ul></div>
<div class="imy-5 paragraph"><h2>Tại sao bạn sẽ yêu thích làm việc tại đây</h2><ul><li>Hybrid</li></ul></div>
</body></html>
"""

# Các field GROUND TRUTH theo Data Contract v0.5.0 + language (parser internal)
GROUND_TRUTH_KEYS = {
    "title", "company", "description_list", "salary", "tags",
    "requirements_list", "benefits_list", "location_text", "deadline_text",
    "posted_date_text", "employment_type_text", "seniority_text", "extra",
    "language",
}

LEGACY_FIELDS = [
    "description_html", "description_text", "salary_text",
    "salary_min", "salary_max", "salary_currency",
    "skills_text", "requirements_text", "benefits_text",
    "salary_jsonld", "sections_html", "requirements_html",
    "benefits_html", "job_location", "industry",
    "valid_through_text", "experience_requirements_jsonld",
    "company_url",
]


class TestNormalizeUrl(unittest.TestCase):
    def test_strip_tracking_params_and_fragment(self):
        out = job_parser.normalize_url(
            "https://itviec.com/viec-lam-it/job-a?lab_feature=p&utm_source=g&click_source=Skill#x")
        self.assertEqual(out, "https://itviec.com/viec-lam-it/job-a")

    def test_keep_page_param_and_strip_trailing_slash(self):
        out = job_parser.normalize_url("https://itviec.com/viec-lam-it/?page=2")
        self.assertEqual(out, "https://itviec.com/viec-lam-it?page=2")

    def test_slug_from_url(self):
        self.assertEqual(
            job_parser.slug_from_url("https://itviec.com/viec-lam-it/abc-001?x=1"), "abc-001")
        self.assertIsNone(job_parser.slug_from_url("https://itviec.com/nha-tuyen-dung/fpt"))


class TestListingParser(unittest.TestCase):
    def setUp(self):
        self.jobs = job_parser.parse_listing(LISTING_HTML)

    def test_extracts_only_job_cards_not_nav_or_skill_links(self):
        slugs = [j["source_job_id"] for j in self.jobs]
        self.assertEqual(slugs[:2], ["senior-backend-java-fpt-0123", "react-dev-vng-0456"])
        self.assertEqual(len(slugs), 3)

    def test_dedup_within_page(self):
        self.assertEqual(len({j["source_job_id"] for j in self.jobs}), len(self.jobs))

    def test_urls_normalized_absolute(self):
        for j in self.jobs[:2]:
            self.assertTrue(j["url"].startswith("https://itviec.com/viec-lam-it/"))
            self.assertNotIn("?", j["url"])

    def test_fallback_to_h3_link_when_no_data_slug(self):
        self.assertEqual(self.jobs[1]["source_job_id"], "react-dev-vng-0456")

    def test_sha256_hash_when_no_site_id(self):
        expected = hashlib.sha256(
            b"https://itviec.com/it-jobs/weird-link-999").hexdigest()
        self.assertEqual(self.jobs[2]["source_job_id"], expected)

    def test_stable_job_id_normalizes_before_hash(self):
        a = job_parser.stable_job_id("https://itviec.com/viec-lam-it/x?utm_source=q/")
        b = job_parser.stable_job_id("https://itviec.com/viec-lam-it/x")
        self.assertEqual(a, b)

    def test_broken_card_skipped(self):
        self.assertEqual(len(self.jobs), 3)

    def test_empty_page(self):
        self.assertEqual(job_parser.parse_listing("<html></html>"), [])


class TestDetailParser(unittest.TestCase):
    def setUp(self):
        self.raw = job_parser.parse_detail(DETAIL_HTML)

    def test_core_fields(self):
        self.assertEqual(self.raw["title"], "Senior Backend Java")
        self.assertEqual(self.raw["company"], "FPT Software")
        self.assertEqual(self.raw["employment_type_text"], "FULL_TIME")
        self.assertEqual(self.raw["posted_date_text"], "2026-10-01")
        self.assertIn("Hồ Chí Minh", self.raw["location_text"])

    def test_ground_truth_keys_present(self):
        """Đủ field GROUND TRUTH Data Contract v0.5.0."""
        for key in GROUND_TRUTH_KEYS:
            self.assertIn(key, self.raw, f"raw thiếu field {key}")

    def test_no_legacy_fields(self):
        """KHÔNG có field legacy ở root raw."""
        for banned in LEGACY_FIELDS:
            self.assertNotIn(banned, self.raw,
                             f"{banned} là field legacy — cấm ở raw v0.5.0")

    def test_no_derived_or_duplicate_keys(self):
        for banned in ("skills", "company_slug", "url", "role_group", "location"):
            self.assertNotIn(banned, self.raw, f"{banned} là dẫn xuất — cấm ở RAW")

    def test_description_list_is_list_of_strings(self):
        self.assertIsInstance(self.raw["description_list"], list)
        self.assertTrue(len(self.raw["description_list"]) > 0)
        for item in self.raw["description_list"]:
            self.assertIsInstance(item, str)

    def test_requirements_list_is_list(self):
        self.assertIsInstance(self.raw["requirements_list"], list)
        self.assertTrue(any("2 năm kinh nghiệm Java" in r
                            for r in self.raw["requirements_list"]))

    def test_benefits_list_is_list(self):
        self.assertIsInstance(self.raw["benefits_list"], list)
        self.assertTrue(any("Hybrid" in b for b in self.raw["benefits_list"]))

    def test_salary_is_nested_dict(self):
        sal = self.raw["salary"]
        self.assertIsInstance(sal, dict)
        for key in ("salary_text", "salary_min", "salary_max",
                     "salary_currency", "pay_period",
                     "is_negotiable", "has_commission"):
            self.assertIn(key, sal, f"salary thiếu key {key}")

    def test_salary_gated_text_is_negotiable(self):
        """Salary 'Đăng nhập để xem mức lương' + JSON-LD non-numeric → negotiable."""
        sal = self.raw["salary"]
        self.assertIn("Đăng nhập", sal["salary_text"])
        self.assertIsNone(sal["salary_min"])
        self.assertIsNone(sal["salary_max"])
        self.assertIsNone(sal["salary_currency"])
        self.assertTrue(sal["is_negotiable"])

    def test_tags_is_nested_dict(self):
        tags = self.raw["tags"]
        self.assertIsInstance(tags, dict)
        for key in ("requirements", "benefits", "skills"):
            self.assertIn(key, tags)

    def test_tags_classified_from_skills(self):
        """JSON-LD skills='Java, Spring Boot, MySQL' → tags.skills có nội dung."""
        tags = self.raw["tags"]
        self.assertIsNotNone(tags["skills"])
        self.assertIsInstance(tags["skills"], list)
        self.assertTrue(len(tags["skills"]) > 0)

    def test_deadline_from_valid_through(self):
        self.assertEqual(self.raw["deadline_text"], "2026-10-30")

    def test_seniority_always_none(self):
        """ITviec không công bố seniority → luôn None."""
        self.assertIsNone(self.raw["seniority_text"])

    def test_extra_is_dict(self):
        extra = self.raw["extra"]
        self.assertIsInstance(extra, dict)
        self.assertIn("industry", extra)
        self.assertIn("company_url", extra)
        self.assertEqual(extra["industry"], "Information Technology")
        self.assertEqual(extra["company_url"],
                         "https://itviec.com/nha-tuyen-dung/fpt-software")

    def test_language_detected(self):
        self.assertIn(self.raw["language"], ("vi", "en"))

    def test_text_fields_no_outer_whitespace(self):
        html = DETAIL_HTML.replace('"title": "Senior Backend Java"',
                                   '"title": "  Senior Backend Java  "')
        raw = job_parser.parse_detail(html)
        self.assertEqual(raw["title"], "Senior Backend Java")


class TestDetailParserMissingFields(unittest.TestCase):
    """Field không tồn tại → defaults phù hợp, không crash."""

    def setUp(self):
        html = "<html><body><h1>Chỉ có title</h1></body></html>"
        self.raw = job_parser.parse_detail(html)

    def test_no_jsonld_falls_back_to_h1(self):
        self.assertEqual(self.raw["title"], "Chỉ có title")

    def test_absent_fields_have_defaults(self):
        self.assertIsNone(self.raw["company"])
        self.assertIsNone(self.raw["location_text"])
        self.assertIsNone(self.raw["employment_type_text"])
        self.assertIsNone(self.raw["seniority_text"])
        self.assertIsNone(self.raw["deadline_text"])
        self.assertIsInstance(self.raw["description_list"], list)
        self.assertTrue(len(self.raw["description_list"]) > 0)  # fallback = [title]
        self.assertIsInstance(self.raw["requirements_list"], list)
        self.assertIsInstance(self.raw["benefits_list"], list)
        self.assertIsInstance(self.raw["salary"], dict)
        self.assertIsInstance(self.raw["tags"], dict)


class TestSalaryParsing(unittest.TestCase):
    """Test bóc tách lương: _parse_base_salary và _build_salary."""

    def test_base_salary_numeric(self):
        jp = {"baseSalary": {"currency": "USD", "value": {"value": 1500}}}
        self.assertEqual(job_parser._parse_base_salary(jp), (1500.0, 1500.0, "USD"))

    def test_base_salary_range(self):
        jp = {"baseSalary": {"currency": "USD", "value": {
            "minValue": 1500, "maxValue": 2500, "value": 1500}}}
        self.assertEqual(job_parser._parse_base_salary(jp), (1500.0, 2500.0, "USD"))

    def test_base_salary_string_non_numeric(self):
        jp = {"baseSalary": {"currency": "USD",
                             "value": {"value": "You'll love it"}}}
        result = job_parser._parse_base_salary(jp)
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertEqual(result[2], "USD")

    def test_base_salary_missing(self):
        self.assertEqual(job_parser._parse_base_salary({}), (None, None, None))

    def test_build_salary_gated_text_with_non_numeric_jsonld(self):
        """Text 'Đăng nhập...' + JSON-LD non-numeric → negotiable, all null."""
        jp = {"baseSalary": {"currency": "USD",
                             "value": {"value": "You'll love it"}}}
        result = job_parser._build_salary("Đăng nhập để xem mức lương", jp)
        self.assertIsNone(result["salary_min"])
        self.assertIsNone(result["salary_max"])
        self.assertIsNone(result["salary_currency"])
        self.assertTrue(result["is_negotiable"])

    def test_build_salary_jsonld_numeric_overrides(self):
        """JSON-LD có số → ưu tiên override text parsing."""
        jp = {"baseSalary": {"currency": "USD", "value": {"value": 1500}}}
        result = job_parser._build_salary("Đăng nhập để xem mức lương", jp)
        self.assertEqual(result["salary_min"], 1500.0)
        self.assertEqual(result["salary_max"], 1500.0)
        self.assertEqual(result["salary_currency"], "USD")
        self.assertFalse(result["is_negotiable"])

    def test_build_salary_text_with_numbers(self):
        """Text có số '15 - 35 triệu' → parse từ text."""
        result = job_parser._build_salary("15 - 35 triệu", {})
        self.assertEqual(result["salary_min"], 15.0)
        self.assertEqual(result["salary_max"], 35.0)
        self.assertEqual(result["salary_currency"], "VND")
        self.assertFalse(result["is_negotiable"])

    def test_build_salary_no_input(self):
        """Không có thông tin lương nào → negotiable, all null."""
        result = job_parser._build_salary(None, {})
        self.assertIsNone(result["salary_min"])
        self.assertIsNone(result["salary_max"])
        self.assertIsNone(result["salary_currency"])
        self.assertTrue(result["is_negotiable"])


class TestLanguageDetection(unittest.TestCase):
    def test_vietnamese_content(self):
        raw = job_parser.parse_detail(DETAIL_HTML)
        # Nội dung có tiếng Việt → "vi"
        self.assertEqual(raw["language"], "vi")

    def test_english_content(self):
        self.assertEqual(job_parser.detect_language(
            "Senior Software Engineer required with 5 years experience in Python"), "en")


class TestPostedDateInference(unittest.TestCase):
    def test_date_posted_present(self):
        self.assertEqual(
            job_parser._infer_posted_date("2026-10-01", "2026-10-30"),
            "2026-10-01")

    def test_infer_from_valid_through(self):
        self.assertEqual(
            job_parser._infer_posted_date(None, "2026-10-30"),
            "2026-09-30")

    def test_both_missing(self):
        self.assertIsNone(job_parser._infer_posted_date(None, None))


class TestTagsClassify(unittest.TestCase):
    def test_classify_skills(self):
        result = job_parser.classify_job_tags(["Java", "Python", "Docker"])
        self.assertIsNotNone(result["skills"])
        self.assertIn("Java", result["skills"])

    def test_empty_tags(self):
        result = job_parser.classify_job_tags([])
        # Khi không có tag → skills = None
        self.assertIsNone(result.get("skills"))


class TestValidateRecord(unittest.TestCase):
    def _record(self, **over):
        meta = {
            "source": "itviec", "source_job_id": "abc",
            "url": "https://itviec.com/viec-lam-it/abc",
            "dedup_key": "itviec:abc", "crawled_at": "2026-10-05T10:00:00+07:00",
            "batch_id": "2026-10-05_itviec_001", "crawler_version": "0.5.0",
            "language": "vi",
        }
        raw = {
            "title": "A", "company": "B",
            "description_list": ["desc line"],
            "salary": {"salary_text": "Thỏa thuận", "salary_min": None,
                       "salary_max": None, "salary_currency": None,
                       "pay_period": None, "is_negotiable": True,
                       "has_commission": False},
            "tags": {"requirements": None, "benefits": None, "skills": None},
        }
        meta.update(over.pop("_meta", {}))
        raw.update(over)
        return {"_meta": meta, "raw": raw}

    def test_valid_record(self):
        self.assertEqual(job_parser.validate_record(self._record()), [])

    def test_missing_title(self):
        errors = job_parser.validate_record(self._record(title=""))
        self.assertTrue(any("title" in e for e in errors))

    def test_missing_meta_language(self):
        errors = job_parser.validate_record(
            self._record(_meta={"language": ""}))
        self.assertTrue(any("language" in e for e in errors))

    def test_description_list_not_list(self):
        errors = job_parser.validate_record(
            self._record(description_list="not a list"))
        self.assertTrue(any("description_list" in e for e in errors))


class TestRecordViaSchema(unittest.TestCase):
    """Test tạo JobRecord qua JobRecord.create() — không raise ValidationError."""

    def test_create_with_itviec_raw(self):
        from crawlers.common.schema import JobRecord
        raw_data = {
            "title": "Senior Backend Java",
            "company": "FPT Software",
            "description_list": ["Phát triển hệ thống backend Java/Spring Boot."],
            "salary": {
                "salary_text": "Đăng nhập để xem mức lương",
                "salary_min": None, "salary_max": None,
                "salary_currency": None, "pay_period": None,
                "is_negotiable": True, "has_commission": False,
            },
            "tags": {"requirements": None, "benefits": None,
                     "skills": ["Java", "Spring Boot"]},
            "requirements_list": ["2 năm kinh nghiệm Java"],
            "benefits_list": ["Hybrid working"],
            "location_text": "Hồ Chí Minh",
            "deadline_text": "2026-10-30",
            "posted_date_text": "2026-10-01",
            "employment_type_text": "FULL_TIME",
            "seniority_text": None,
            "extra": {"industry": "IT", "company_url": "https://itviec.com/nha-tuyen-dung/fpt"},
        }
        record = JobRecord.create(
            source="itviec",
            source_job_id="test-job-001",
            url="https://itviec.com/viec-lam-it/test-job-001",
            batch_id="2026-10-11_itviec_001",
            raw_data=raw_data,
            crawler_version="0.5.0",
            language="vi",
        )
        self.assertEqual(record.meta.source, "itviec")
        self.assertEqual(record.raw.title, "Senior Backend Java")
        self.assertTrue(record.raw.salary.is_negotiable)
        self.assertIsNone(record.raw.salary.salary_min)


if __name__ == "__main__":
    unittest.main()
