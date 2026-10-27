# -*- coding: utf-8 -*-
"""Unit tests for GeminiAllInOneAgent (Bước 3)."""

from unittest.mock import MagicMock, patch
import pytest

from preprocessing.missing_outlier.gemini_all_in_one_agent import GeminiAllInOneAgent


@pytest.fixture
def agent():
    """Tạo instance GeminiAllInOneAgent ở chế độ mock offline."""
    return GeminiAllInOneAgent(mock_mode=True, usd_vnd_rate=25400.0)


def test_heuristic_fallback_enrichment(agent):
    """Kiểm tra heuristic fallback trích xuất đúng 3 tầng kỹ năng và yêu cầu."""
    rec = {
        "job_title": "Senior Python Backend Developer (HN)",
        "source_platform": "topcv",
        "raw_description_text": (
            "Chúng tôi cần tuyển Senior Python Developer phát triển hệ thống Ngân hàng số.\n"
            "Sử dụng Docker, PostgreSQL, AWS và FastAPI.\n"
            "Thời gian làm việc: Thứ 2 - Thứ 6 (nghỉ thứ 7 và Chủ nhật)."
        ),
        "raw_requirements_text": (
            "Yêu cầu tối thiểu 3 năm kinh nghiệm lập trình Python.\n"
            "Tốt nghiệp đại học chuyên ngành CNTT.\n"
            "Kỹ năng giao tiếp và làm việc nhóm tốt."
        ),
        "raw_salary_text": "Thỏa thuận",
        "salary_min": None,
        "salary_max": None,
    }
    anchor = {
        "mean_min": 30000000.0,
        "mean_max": 50000000.0,
        "median_min": 28000000.0,
        "median_max": 48000000.0,
    }

    res = agent.enrich_record(rec, market_anchor=anchor)

    # 1. Kiểm tra 3 tầng kỹ năng
    skills = res["skills"]
    assert "Python" in skills["hard_skills"]
    assert "Docker" in skills["hard_skills"]
    assert "PostgreSQL" in skills["hard_skills"]
    assert "FastAPI" in skills["hard_skills"]
    assert "Kỹ năng giao tiếp" in skills["soft_skills"]
    assert "Làm việc nhóm" in skills["soft_skills"]
    assert "Ngân hàng" in skills["domain_skills"]

    # 2. Kiểm tra yêu cầu
    reqs = res["requirements"]
    assert reqs["experience_years"] == 3.0
    assert reqs["standardized_seniority"] == "senior"
    assert reqs["standardized_education"] == "bachelor"
    assert reqs["is_saturday_work"] is False

    # 3. Kiểm tra lương (Ground-Truth Realism: giữ nguyên null khi lương thỏa thuận)
    sal = res["salary"]
    assert sal["salary_min"] is None
    assert sal["salary_max"] is None
    assert sal["is_salary_negotiable"] is True
    assert sal["salary_currency"] == "VND"
    assert sal["salary_source"] == "negotiable"


def test_salary_usd_to_vnd_conversion(agent):
    """Kiểm tra lương USD được quy đổi chính xác sang VND theo tỷ giá 25,400."""
    rec = {
        "job_title": "Fullstack React Node.js Developer",
        "source_platform": "itviec",
        "raw_description_text": "Working on US enterprise project.",
        "raw_requirements_text": "At least 2 years experience with Node.js and React.",
        "raw_salary_text": "$1,000 - $2,000 USD",
        "salary_min": 1000.0,
        "salary_max": 2000.0,
        "salary_currency": "USD",
    }

    res = agent.enrich_record(rec)
    sal = res["salary"]

    assert sal["salary_currency"] == "VND"
    assert sal["salary_source"] == "original"
    assert sal["salary_min"] == pytest.approx(25400000.0, abs=10000)
    assert sal["salary_max"] == pytest.approx(50800000.0, abs=10000)


def test_saturday_work_positive_detection(agent):
    """Kiểm tra nhận diện đúng lịch làm việc có thứ 7."""
    rec = {
        "job_title": "Junior Java Developer",
        "source_platform": "vietnamworks",
        "raw_description_text": "Thời gian làm việc: Thứ 2 đến Thứ 6 và sáng Thứ 7 hàng tuần.",
        "raw_requirements_text": "1 năm kinh nghiệm Java.",
    }

    res = agent.enrich_record(rec)
    assert res["requirements"]["is_saturday_work"] is True


def test_english_translation_flagging(agent):
    """Kiểm tra nhận diện ngôn ngữ tiếng Anh và cờ bản dịch."""
    rec = {
        "job_title": "Senior Frontend Engineer",
        "source_platform": "itviec",
        "language": "en",
        "raw_description_text": (
            "We are looking for a Senior Frontend Engineer to build high-performance web applications. "
            "You will collaborate with backend developers and product designers."
        ),
        "raw_requirements_text": (
            "At least 4 years of experience with React, TypeScript, and modern frontend architecture. "
            "Strong communication skills and team collaboration."
        ),
        "benefits_list": ["Competitive salary", "Macbook Pro provided"],
    }

    res = agent.enrich_record(rec)
    assert res["jd_text"]["is_translated"] is True
    assert res["jd_text"]["language"] == "vi"
    assert "TypeScript" in res["skills"]["hard_skills"]
    assert "React" in res["skills"]["hard_skills"]


def test_mocked_gemini_api_call():
    """Kiểm tra gọi API Gemini (được mock) trả về kết quả hợp lệ với cờ imputed_by_agent=True."""
    mock_agent = GeminiAllInOneAgent(api_key="fake-key-for-test", mock_mode=False)

    fake_api_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": """{
                                "hard_skills": ["Golang", "Kubernetes", "gRPC"],
                                "soft_skills": ["Giải quyết vấn đề"],
                                "domain_skills": ["Tài chính công nghệ (Fintech)"],
                                "experience_years": 2.5,
                                "standardized_seniority": "middle",
                                "standardized_education": "bachelor",
                                "is_saturday_work": false,
                                "salary_min": null,
                                "salary_max": null,
                                "salary_currency": "VND",
                                "salary_source": "negotiable",
                                "translated_title": "Kỹ sư Backend Golang",
                                "translated_description": "Mô tả công việc Golang...",
                                "translated_requirements": "Yêu cầu 2.5 năm Golang...",
                                "translated_benefits": ["Bảo hiểm sức khỏe cao cấp"]
                            }"""
                        }
                    ]
                }
            }
        ]
    }

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = fake_api_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        rec = {
            "job_title": "Golang Engineer",
            "source_platform": "topcv",
            "raw_description_text": "Golang Kubernetes backend",
            "raw_requirements_text": "2+ years experience",
        }

        res = mock_agent.enrich_record(rec)

        assert res["agent_metadata"]["imputed_by_agent"] is True
        assert res["skills"]["hard_skills"] == ["Golang", "Kubernetes", "gRPC"]
        assert res["skills"]["soft_skills"] == ["Giải quyết vấn đề"]
        assert res["skills"]["domain_skills"] == ["Tài chính công nghệ (Fintech)"]
        assert res["requirements"]["experience_years"] == 2.5
        assert res["requirements"]["standardized_seniority"] == "middle"
        assert res["salary"]["salary_source"] == "negotiable"
        assert res["salary"]["salary_min"] is None
        assert res["salary"]["salary_max"] is None
        assert res["salary"]["is_salary_negotiable"] is True


def test_hidden_salary_extraction_from_jd(agent):
    """Kiểm tra trích xuất lương ẩn từ thân văn bản JD."""
    rec = {
        "job_title": "Frontend Vue.js Developer",
        "source_platform": "topcv",
        "raw_description_text": (
            "Phát triển giao diện ứng dụng web.\n"
            "Mức thu nhập: 18 - 28 triệu/tháng tùy theo năng lực."
        ),
        "raw_requirements_text": "Ít nhất 2 năm kinh nghiệm Vue.js.",
        "raw_salary_text": "Thỏa thuận",
        "salary_min": None,
        "salary_max": None,
    }

    res = agent.enrich_record(rec)
    sal = res["salary"]

    assert sal["salary_min"] == 18000000.0
    assert sal["salary_max"] == 28000000.0
    assert sal["salary_source"] == "jd_extracted"
    assert sal["is_salary_negotiable"] is False
