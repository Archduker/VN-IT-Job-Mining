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
