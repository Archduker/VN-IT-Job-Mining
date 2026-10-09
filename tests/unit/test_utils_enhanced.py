# -*- coding: utf-8 -*-
"""Unit tests cho các hàm helper utils nâng cao: detect_language, parse_salary, strip_html_tags."""

import pytest
from crawlers.common.utils import detect_language, parse_salary, strip_html_tags


class TestDetectLanguage:

    def test_vietnamese_text_with_accents(self):
        text = "Tuyển dụng kỹ sư phần mềm Python backend kinh nghiệm 2 năm tại Hồ Chí Minh"
        assert detect_language(text) == "vi"

    def test_vietnamese_text_with_short_tokens(self):
        text = "Yêu cầu công việc và quyền lợi hấp dẫn"
        assert detect_language(text) == "vi"

    def test_english_text(self):
        text = "Senior Fullstack Engineer with strong proficiency in React and Node.js"
        assert detect_language(text) == "en"

    def test_empty_or_none(self):
        assert detect_language("") == "vi"


class TestParseSalary:

    def test_salary_range_triệu_vnd(self):
        s_min, s_max, curr = parse_salary("15 - 35 triệu")
        assert s_min == 15.0
        assert s_max == 35.0
        assert curr == "VND"

    def test_salary_up_to(self):
        s_min, s_max, curr = parse_salary("Lên đến 50 triệu")
        assert s_min is None
        assert s_max == 50.0
        assert curr == "VND"

    def test_salary_from(self):
        s_min, s_max, curr = parse_salary("Từ 20 triệu")
        assert s_min == 20.0
        assert s_max is None
        assert curr == "VND"

    def test_salary_usd(self):
        s_min, s_max, curr = parse_salary("$1,500 - $3,000")
        assert s_min == 1500.0
        assert s_max == 3000.0
        assert curr == "USD"

    def test_salary_negotiable(self):
        assert parse_salary("Thoả thuận") == (None, None, None)
        assert parse_salary("Thương lượng") == (None, None, None)
        assert parse_salary("Negotiable") == (None, None, None)
        assert parse_salary(None) == (None, None, None)


class TestStripHtmlTags:

    def test_strip_basic_tags(self):
        html = "<p>Senior <strong>Backend</strong> Developer</p>"
        assert strip_html_tags(html) == "Senior Backend Developer"

    def test_newline_and_break(self):
        html = "<p>Yêu cầu:</p>AA,<br>BB"
        expected = "Yêu cầu:\nAA,\nBB"
        assert strip_html_tags(html) == expected

    def test_unescape_vietnamese_entities(self):
        html = "<p>L&iacute; do gia nhập</p>"
        assert strip_html_tags(html) == "Lí do gia nhập"


class TestParseSalaryDetail:

    def test_salary_detail_range_vnd(self):
        from crawlers.common.utils import parse_salary_detail
        res = parse_salary_detail("15 - 25 triệu/tháng")
        assert res["salary_min"] == 15.0
        assert res["salary_max"] == 25.0
        assert res["salary_currency"] == "VND"
        assert res["pay_period"] == "month"
        assert res["is_negotiable"] is False
        assert res["has_commission"] is False

    def test_salary_detail_with_commission(self):
        from crawlers.common.utils import parse_salary_detail
        res = parse_salary_detail("Lương cứng 10 - 15 triệu + Hoa hồng", title="Sales IT Solution")
        assert res["salary_min"] == 10.0
        assert res["salary_max"] == 15.0
        assert res["salary_currency"] == "VND"
        assert res["has_commission"] is True

    def test_salary_detail_negotiable_fallback_to_title(self):
        from crawlers.common.utils import parse_salary_detail
        res = parse_salary_detail("Thoả thuận", title="Product Development Engineer | Salary Up To 1,300 USD")
        assert res["salary_min"] is None
        assert res["salary_max"] == 1300.0
        assert res["salary_currency"] == "USD"
        assert res["pay_period"] == "month"
        assert res["is_negotiable"] is False

    def test_salary_detail_purely_negotiable(self):
        from crawlers.common.utils import parse_salary_detail
        res = parse_salary_detail("Thoả thuận", title="Senior SAP Consultant")
        assert res["salary_min"] is None
        assert res["salary_max"] is None
        assert res["salary_currency"] is None
        assert res["is_negotiable"] is True


class TestTextToCleanLines:

    def test_bullet_point_cleanup(self):
        from crawlers.common.utils import text_to_clean_lines
        content = """
        • Có 3-4 năm kinh nghiệm phát triển Web
        - Nắm vững OOP, SOLID
        1. Thành thạo SQL Server
        + Tiếng Anh giao tiếp tốt
        """
        lines = text_to_clean_lines(content)
        assert len(lines) == 4
        assert lines[0] == "Có 3-4 năm kinh nghiệm phát triển Web"
        assert lines[1] == "Nắm vững OOP, SOLID"
        assert lines[2] == "Thành thạo SQL Server"
        assert lines[3] == "Tiếng Anh giao tiếp tốt"

    def test_html_li_extraction(self):
        from crawlers.common.utils import text_to_clean_lines
        html = "<ul><li>Chế độ đãi ngộ tốt</li><li>Bảo hiểm sức khỏe PTI</li></ul>"
        lines = text_to_clean_lines(html)
        assert lines == ["Chế độ đãi ngộ tốt", "Bảo hiểm sức khỏe PTI"]


class TestClassifyJobTags:

    def test_classify_tags(self):
        from crawlers.common.utils import classify_job_tags
        tags = [
            "3 năm kinh nghiệm chuyên môn",
            "Đại Học trở lên",
            "Tuổi 26 - 35",
            "Bảo hiểm xã hội",
            "Fullstack Developer",
            "Vue",
            "C#"
        ]
        classified = classify_job_tags(tags)
        assert classified["attributes"]["experience"] == "3 năm kinh nghiệm chuyên môn"
        assert classified["attributes"]["education"] == "Đại Học trở lên"
        assert classified["attributes"]["age"] == "Tuổi 26 - 35"
        assert "Bảo hiểm xã hội" in classified["benefits"]
        assert "Fullstack Developer" in classified["job_roles"]
        assert "Vue" in classified["technical_skills"]
        assert "C#" in classified["technical_skills"]

