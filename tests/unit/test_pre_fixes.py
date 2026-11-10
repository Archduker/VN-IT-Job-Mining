from preprocessing.clean.run import dedup_key
from preprocessing.transformation.skill_extractor import extract_benefits


def test_dedup_key_ignores_crawl_week():
    a = {"job_title": "Python Dev", "company_name": "ACME", "raw_location_text": "Hà Nội", "crawled_at": "2026-11-02"}
    b = {**a, "crawled_at": "2026-11-09"}
    assert dedup_key(a) == dedup_key(b)


def test_benefits_ignores_duties_outside_benefit_section():
    jd = "Mô tả:\nBảo trì hệ thống máy tính văn phòng, cài laptop, training nhân viên.\n"
    assert extract_benefits(None, jd) == []


def test_benefits_reads_benefit_section_with_word_boundary():
    jd = "Mô tả:\nRemote debugging.\nQuyền lợi:\n- Thưởng tháng 13\n- Làm việc hybrid\n"
    got = extract_benefits(None, jd)
    assert "Lương tháng 13" in got and "Làm việc linh hoạt" in got
    assert extract_benefits(None, "Quyền lợi:\n- Hybridization lab") == []
