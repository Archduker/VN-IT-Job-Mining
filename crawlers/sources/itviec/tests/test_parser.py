# -*- coding: utf-8 -*-
"""Test parser ITviec với HTML mẫu dựng theo cấu trúc THỰC TẾ (probe 2026-10-05).

Không commit HTML thật của website vào Git — fixture chỉ mô phỏng cấu trúc.
Chạy:  python -m unittest discover -s crawlers/sources/itviec/tests -v
"""

import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import parser as job_parser  # noqa: E402

# ---------------------------------------------------------------- fixtures

LISTING_HTML = """
<html><body>
  <!-- link điều hướng menu, KHÔNG phải job -->
  <nav><a href="/viec-lam-it/it-support?click_source=Skill+tag">IT Support</a>
       <a href="/viec-lam-it/ha-noi">Hà Nội</a></nav>

  <div class="card-jobs-list">
    <!-- job card chuẩn: có slug data-attribute + h3 link -->
    <div class="job-card ipt-2 d-flex"
         data-search--job-selection-job-slug-value="senior-backend-java-fpt-0123">
      <span class="small-text text-dark-grey">Đăng 3 ngày trước</span>
      <h3 class="imt-3"><a href="https://itviec.com/viec-lam-it/senior-backend-java-fpt-0123?lab_feature=preview_jd_page">Senior Backend Java</a></h3>
      <div class="d-flex align-items-center salary text-rich-grey">Thương lượng</div>
      <a href="/nha-tuyen-dung/fpt?lab_feature=preview_jd_page">FPT</a>
      <a href="/viec-lam-it/java?click_source=Skill+tag">Java</a>
    </div>

    <!-- job card super-hot, không có data-slug → fallback h3 a -->
    <div class="job-card super-hot">
      <h3><a href="https://itviec.com/viec-lam-it/react-dev-vng-0456?utm_source=x">React Developer</a></h3>
    </div>

    <!-- card trùng slug với card 1 → phải bị khử -->
    <div class="job-card"
         data-search--job-selection-job-slug-value="senior-backend-java-fpt-0123">
      <h3><a href="https://itviec.com/viec-lam-it/senior-backend-java-fpt-0123">Senior Backend Java</a></h3>
    </div>

    <!-- card không có slug nào nhận dạng được (link ngoài /viec-lam-it/)
         → source_job_id phải là SHA-256 của URL chuẩn hóa (TASKS.md §4.2) -->
    <div class="job-card">
      <h3><a href="https://itviec.com/it-jobs/weird-link-999">Odd Layout Job</a></h3>
    </div>

    <!-- card hỏng hoàn toàn (không slug, không h3) → bỏ qua, không crash -->
    <div class="job-card"><span>?</span></div>
  </div>
</body></html>
"""

DESC_HTML = ('<p>Mô tả có <strong>HTML gốc</strong> với dấu tiếng Việt ề ~ ứ.</p>'
             '<ul><li>item 1</li></ul>')

# JSON-LD JobPosting dựng đúng cấu trúc thật (encode JSON hợp lệ)
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
        self.assertEqual(len(slugs), 3)  # card thứ 3 → hash fallback

    def test_dedup_within_page(self):
        self.assertEqual(len({j["source_job_id"] for j in self.jobs}), len(self.jobs))

    def test_urls_normalized_absolute(self):
        # 2 card slug chuẩn → URL /viec-lam-it/<slug>, đã cắt param tracking.
        # (card hash fallback có URL layout lạ — check riêng ở test_sha256_...)
        for j in self.jobs[:2]:
            self.assertTrue(j["url"].startswith("https://itviec.com/viec-lam-it/"))
            self.assertNotIn("?", j["url"])  # lab_feature/utm đã bị cắt

    def test_fallback_to_h3_link_when_no_data_slug(self):
        # card 2 không có data attribute → vẫn lấy được slug từ h3 a
        self.assertEqual(self.jobs[1]["source_job_id"], "react-dev-vng-0456")

    def test_sha256_hash_when_no_site_id(self):
        """Không có slug của site → source_job_id = SHA-256 URL chuẩn hóa."""
        expected = hashlib.sha256(
            b"https://itviec.com/it-jobs/weird-link-999").hexdigest()
        self.assertEqual(self.jobs[2]["source_job_id"], expected)
        self.assertEqual(self.jobs[2]["url"],
                         "https://itviec.com/it-jobs/weird-link-999")

    def test_stable_job_id_normalizes_before_hash(self):
        a = job_parser.stable_job_id("https://itviec.com/viec-lam-it/x?utm_source=q/")
        b = job_parser.stable_job_id("https://itviec.com/viec-lam-it/x")
        self.assertEqual(a, b)  # ổn định bất kể param tracking

    def test_broken_card_skipped(self):
        self.assertEqual(len(self.jobs), 3)  # card rỗng bị bỏ qua, không crash

    def test_empty_page(self):
        self.assertEqual(job_parser.parse_listing("<html></html>"), [])


class TestDetailParser(unittest.TestCase):
    def setUp(self):
        self.raw = job_parser.parse_detail(DETAIL_HTML)

    def test_core_fields(self):
        self.assertEqual(self.raw["title"], "Senior Backend Java")
        self.assertEqual(self.raw["company"], "FPT Software")
        self.assertEqual(self.raw["company_url"],
                         "https://itviec.com/nha-tuyen-dung/fpt-software")
        self.assertEqual(self.raw["employment_type_text"], "FULL_TIME")
        self.assertEqual(self.raw["posted_date_text"], "2026-10-01")
        self.assertIn("Hồ Chí Minh", self.raw["location_text"])

    def test_contract_keys_present(self):
        """Đủ 11 field hợp đồng TASKS.md §4.1, đúng tên."""
        contract = ["title", "company", "salary_text", "location_text",
                    "skills_text", "posted_date_text", "employment_type_text",
                    "seniority_text", "description_html", "description_text",
                    "requirements_text"]
        for key in contract:
            self.assertIn(key, self.raw, f"raw thiếu field hợp đồng {key}")

    def test_no_derived_or_duplicate_keys(self):
        """Không có field dẫn xuất/normalized/trùng lặp trong raw (nhóm B/C)."""
        for banned in ("skills", "company_slug", "url", "salary_min", "salary_max",
                       "role_group", "location"):
            self.assertNotIn(banned, self.raw, f"{banned} là dẫn xuất/curated — cấm ở RAW")

    def test_skills_text_verbatim(self):
        """skills_text là field contract — giữ nguyên văn chuỗi gốc."""
        self.assertEqual(self.raw["skills_text"], "Java, Spring Boot, MySQL")

    def test_text_fields_no_outer_whitespace(self):
        """Nguồn thừa dấu cách đầu/cuối → field text phải sạch whitespace."""
        html = DETAIL_HTML.replace('"title": "Senior Backend Java"',
                                   '"title": "  Senior Backend Java  "')
        raw = job_parser.parse_detail(html)
        self.assertEqual(raw["title"], "Senior Backend Java")

    def test_seniority_text_present_but_null(self):
        """TASKS.md §4.1 yêu cầu khóa seniority_text; ITviec không công khai
        → phải có mặt với giá trị None, KHÔNG suy diễn từ title/exp."""
        self.assertIn("seniority_text", self.raw)
        self.assertIsNone(self.raw["seniority_text"])

    def test_description_html_preserved_verbatim(self):
        # JSON-LD description phải được giữ ĐÚNG từng ký tự (kể cả tiếng Việt)
        self.assertEqual(self.raw["description_html"], DESC_HTML)
        self.assertIn("<strong>HTML gốc</strong>", self.raw["description_html"])
        self.assertNotIn("<", self.raw["description_text"])  # text thuần

    def test_salary_kept_raw_no_numeric_parsing(self):
        self.assertEqual(self.raw["salary_text"], "Đăng nhập để xem mức lương")
        # baseSalary JSON-LD trả về dict nguyên văn, KHÔNG tự suy ra con số
        self.assertEqual(self.raw["salary_jsonld"]["value"]["value"], "You'll love it")

    def test_requirements_and_benefits_from_rendered_sections(self):
        self.assertIn("2 năm kinh nghiệm Java", self.raw["requirements_html"])
        self.assertIn("Hybrid", self.raw["benefits_html"])
        # *_text phải sạch tag (plain text)
        self.assertNotIn("<", self.raw["requirements_text"])
        self.assertIn("2 năm kinh nghiệm Java", self.raw["requirements_text"])
        # sections_html giữ lại toàn bộ, không mất dữ liệu
        self.assertIn("Mô tả công việc", self.raw["sections_html"])

    def test_experience_requirements_passthrough(self):
        self.assertEqual(self.raw["experience_requirements_jsonld"]["monthsOfExperience"], 24)


class TestDetailParserMissingFields(unittest.TestCase):
    """Field không tồn tại → None/[], không crash, không bịa dữ liệu."""

    def setUp(self):
        html = "<html><body><h1>Chỉ có title</h1></body></html>"
        self.raw = job_parser.parse_detail(html)

    def test_no_jsonld_falls_back_to_h1(self):
        self.assertEqual(self.raw["title"], "Chỉ có title")

    def test_absent_fields_are_none_not_guessed(self):
        for key in ("company", "salary_text", "salary_jsonld", "location_text",
                    "employment_type_text", "seniority_text", "description_html",
                    "requirements_html",
                    "benefits_html", "posted_date_text"):
            self.assertIsNone(self.raw[key], f"{key} phải None khi source không có")
        self.assertEqual(self.raw["job_location"], [])


class TestValidateRecord(unittest.TestCase):
    def _record(self, **over):
        meta = {
            "source": "itviec", "source_job_id": "abc",
            "url": "https://itviec.com/viec-lam-it/abc",
            "dedup_key": "itviec:abc", "crawled_at": "2026-10-05T10:00:00+07:00",
            "batch_id": "2026-10-05_itviec_001", "crawler_version": "0.1.0",
        }
        raw = {"title": "A", "company": "B", "description_html": "<p>x</p>"}
        meta.update(over.pop("_meta", {}))
        raw.update(over)
        return {"_meta": meta, "raw": raw}

    def test_valid_record(self):
        self.assertEqual(job_parser.validate_record(self._record()), [])

    def test_missing_meta_key_rejected(self):
        rec = self._record()
        rec["_meta"]["dedup_key"] = ""
        self.assertIn("_meta.dedup_key thiếu", job_parser.validate_record(rec))

    def test_garbage_record_rejected(self):
        rec = self._record(title=None, description_html=None)
        errors = job_parser.validate_record(rec)
        self.assertTrue(any("title" in e for e in errors))

    def test_warnings_not_rejection(self):
        rec = self._record(company=None)
        self.assertEqual(job_parser.validate_record(rec), [])  # vẫn ghi
        self.assertEqual(job_parser.record_warnings(rec), ["company"])  # nhưng warn


if __name__ == "__main__":
    unittest.main()
