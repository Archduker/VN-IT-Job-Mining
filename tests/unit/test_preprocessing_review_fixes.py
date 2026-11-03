# -*- coding: utf-8 -*-
"""Các lỗi tìm thấy khi review P2–P5 ngày 03/11/2026, mỗi test dùng đúng ví dụ sai trên dữ liệu thật."""

from __future__ import annotations

import json

import pytest

from preprocessing.common import api_cache
from preprocessing.common.jev_client import JevClient
from preprocessing.normalization.text_cleaner import classify_seniority
from preprocessing.transformation.salary_parser import parse_salary_cascade
from preprocessing.transformation.skill_extractor import extract_skills_from_text
from preprocessing.transformation.text_metrics import detect_jd_language
from preprocessing.transformation.translator import GeminiTranslator, split_chunks


@pytest.mark.parametrize("title", [
    "Chuyên viên Quản lý chất lượng dữ liệu (2026TD450981)",
    "Chuyên Viên Ứng Dụng Microsoft 365 & AI",
    "2 AI Engineer",
    "CVCC Bán Sản Phẩm Cho Vay - Bình Dương - TA186",
    "Chuyên viên cao cấp Quan hệ khách hàng Doanh nghiệp - Bậc 1 (RM)",
])
def test_title_numbers_without_money_unit_are_not_salary(title):
    r = parse_salary_cascade("Thỏa thuận", title=title, jd_text="")
    assert r["salary_source"] == "none" and r["salary_max_vnd"] is None


def test_title_salary_ignores_years_of_experience():
    r = parse_salary_cascade(None, title="Business Analyst (2+ Năm Kinh Nghiệm) - Upto 35 Triệu", jd_text="")
    assert (r["salary_source"], r["salary_min_vnd"], r["salary_max_vnd"]) == ("title", None, 35_000_000.0)


def test_salary_outside_monthly_bounds_is_suspect():
    r = parse_salary_cascade("300 - 900 triệu")
    assert r["salary_suspect"] is True and r["salary_min_vnd"] is None and r["salary_max_vnd"] is None


def test_single_letter_skill_needs_context():
    assert extract_skills_from_text("Nhân viên kinh doanh, làm việc tại tòa nhà C") == []
    assert "C" in extract_skills_from_text("Thành thạo C/C++ cho hệ nhúng")
    assert "Golang" not in extract_skills_from_text("Ready to go the extra mile")


def test_nhan_vien_is_not_a_level():
    assert classify_seniority("Nhân viên", "Kế toán tổng hợp", None) == (None, None)
    assert classify_seniority("Nhân Viên/Chuyên Viên", "Backend Developer", 3.0) == ("Middle", "kinh_nghiem")


def test_language_is_decided_on_jd_only():
    en = ("Responsibilities: design REST APIs with Python and maintain CI/CD pipelines for our platform. " * 8
          + "\nBằng cấp / Education: Bachelor degree in Computer Science.")
    topcv_header = "Chi tiết công việc Backend Developer tại Công ty Cổ phần ABC " + en
    assert detect_jd_language(en) == "en"
    assert detect_jd_language(topcv_header, "Backend Developer", "Công ty Cổ phần ABC") == "en"
    assert detect_jd_language("Tham gia phát triển hệ thống phần mềm quản lý cho khu du lịch.") == "vi"


def test_split_chunks_keeps_all_text():
    text = "a" * 2500 + "\n" + "b" * 1000 + "\n" + "c" * 7000
    chunks = split_chunks(text)
    assert max(len(c) for c in chunks) <= 3000
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


class _FakeResp:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class _FakeSession:
    def __init__(self, body):
        self.body, self.calls = body, 0

    def post(self, *a, **k):
        self.calls += 1
        return _FakeResp(self.body)


def test_global_budget_stops_calls_across_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    (tmp_path / "spend_google.json").write_text(json.dumps({"total_usd": api_cache.PROVIDER_CAP_USD["google"]}), encoding="utf-8")
    sess = _FakeSession({"candidates": [{"content": {"parts": [{"text": "bản dịch"}]}}]})
    tr = GeminiTranslator(use_api=True, dry_run=False, cache=api_cache.ApiCache("translate", root=tmp_path, provider="google"), session=sess)
    assert tr.translate_text("Build APIs") == (None, False)
    assert sess.calls == 0 and "trần chung" in tr.reason


def test_spend_ledger_accumulates(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "test")
    sess = _FakeSession({"answers": {"q": {"noul": 0.2}}, "usage": {"cost": 0.01}})
    jev = JevClient(use_api=True, dry_run=False, cache=api_cache.ApiCache("jev", root=tmp_path), session=sess)
    assert jev.noul("q", "i", "t", "f", {"title": "x"}) == 0.2
    assert api_cache.ApiCache("translate", root=tmp_path).total_spent() == pytest.approx(0.01)


def test_jev_disagreement_flags_label_for_review(tmp_path, monkeypatch):
    from preprocessing.normalization import run as norm

    monkeypatch.setenv("OPENCODE_API_KEY", "test")
    class _PerName(_FakeSession):
        def post(self, *a, json=None, **k):
            self.calls += 1
            name = next(iter(json["questions"]))
            return _FakeResp({"answers": {name: {"noul": 0.1}}, "usage": {"cost": 0}})

    jev = JevClient(use_api=True, dry_run=False, cache=api_cache.ApiCache("jev", root=tmp_path), session=_PerName(None))
    rec = {"job_title_clean": "Senior Backend Developer", "raw_seniority_text": None, "exp_min_years": None,
           "skills_clean": ["Java"], "company_name": "Cty A", "locations": [], "description_clean": "Java Spring"}
    rows, rep = norm.process_source_records("glints", [rec], jev, dry_run=True)
    r = rows[0]
    assert (r["seniority"], r["seniority_prob"], r["seniority_can_kiem"]) == ("Senior", 0.1, True)
    assert r["job_family_can_kiem"] is True
    assert next(x for x in rep.data["rules"] if x["id"] == "N2b")["rows_affected"] == 1


def test_header_with_thousand_separators():
    r = parse_salary_cascade("Up to 40.000.000 VND")
    assert (r["salary_max_vnd"], r["salary_suspect"]) == (40_000_000.0, False)


@pytest.mark.parametrize("text,lo,hi", [
    ("From 9.000.000 VND", 9_000_000.0, None),
    ("0 - 30000000 VND", None, 30_000_000.0),
    ("Trưởng nhóm 20 - 30", 20_000_000.0, 30_000_000.0),
])
def test_header_unit_and_zero_bounds(text, lo, hi):
    r = parse_salary_cascade(text)
    assert (r["salary_min_vnd"], r["salary_max_vnd"], r["salary_suspect"]) == (lo, hi, False)


def test_quan_ly_in_title_is_a_job_not_a_level():
    assert classify_seniority(None, "Kỹ Sư Quản Lý Dự Án - PC Junior", None) == ("Junior", "title")


def test_gemini_response_and_cost_from_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    body = {"candidates": [{"content": {"parts": [{"text": "nghĩ...", "thought": True}, {"text": "Xây dựng API bằng Python"}]}}],
            "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 1000, "thoughtsTokenCount": 1000}}
    sess = _FakeSession(body)
    cache = api_cache.ApiCache("translate", root=tmp_path, provider="google")
    tr = GeminiTranslator(use_api=True, dry_run=False, cache=cache, session=sess)
    assert tr.translate_text("Build APIs with Python") == ("Xây dựng API bằng Python", False)
    # 1.000 token vào x 0,75 + 2.000 token ra (kể cả thinking) x 3,75 trên 1 triệu
    assert cache.total_spent() == pytest.approx((1000 * 0.75 + 2000 * 3.75) / 1e6)
    assert not (tmp_path / "spend_opencode.json").exists()


def test_jev_prefetch_parallel_then_loop_reads_memo(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "test")

    class _Count(_FakeSession):
        def post(self, *a, json=None, **k):
            self.calls += 1
            name = next(iter(json["questions"]))
            return _FakeResp({"answers": {name: {"noul": 0.9 if "Java" in json["state"]["title"] else 0.1}}, "usage": {"cost": 0}})

    sess = _Count(None)
    jev = JevClient(use_api=True, dry_run=False, cache=api_cache.ApiCache("jev", root=tmp_path), session=sess)
    states = [{"title": f"Java {i}"} for i in range(10)] + [{"title": "Kế toán"}] * 5
    jev.prefetch("q", "i", "t", "f", states)
    assert sess.calls == 11  # trạng thái trùng chỉ gọi một lần
    assert jev.noul("q", "i", "t", "f", {"title": "Kế toán"}) == 0.1 and sess.calls == 11


def test_gemini_overload_503_stops_after_five_chunks(tmp_path, monkeypatch):
    """503 mãi không được treo: 5 đoạn liên tiếp hết lượt thử thì dừng gọi hẳn."""
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr("preprocessing.transformation.translator.time.sleep", lambda s: None)

    class _Busy:
        calls = 0

        def post(self, *a, **k):
            _Busy.calls += 1
            return type("R", (), {"status_code": 503})()

    tr = GeminiTranslator(use_api=True, dry_run=False, cache=api_cache.ApiCache("translate", root=tmp_path, provider="google"), session=_Busy())
    for i in range(8):
        tr.translate_text(f"Build APIs number {i}")
    assert _Busy.calls == 25 and "429/503" in tr.reason


def test_vietnamese_word_ai_is_not_machine_learning():
    from preprocessing.transformation.skill_extractor import extract_skills_from_text
    assert "Machine Learning" not in extract_skills_from_text("Ứng viên là ai cũng được, bất kỳ ai yêu thích lập trình")
    assert "Machine Learning" in extract_skills_from_text("Kinh nghiệm xây dựng mô hình trí tuệ nhân tạo")
