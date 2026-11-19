"""Bộ lọc IT ba tầng (C4a, đặc tả 01 mục 2, 2.1; prompt 01_clean_it_filter mục 5). Tiêu đề lấy từ nhãn C4b thật."""
import copy
import json

import pytest

from preprocessing.common import it_filter as F

RAW = F.load_config(require_approved=False)


@pytest.fixture
def cfg():
    c = copy.deepcopy(RAW)
    c["_meta"]["approved"] = True
    c["tier2"]["rule"].update(k_fam=1, k_sec=4, k_cat=2)
    return c


def test_unapproved_config_stops(tmp_path):
    p = tmp_path / "it_filter_v2.json"
    p.write_text(json.dumps({**RAW, "_meta": {"approved": False}}), encoding="utf-8")
    with pytest.raises(ValueError, match="it_filter_v2.json chưa được duyệt"):
        F.load_config(p)


@pytest.mark.parametrize("title", [
    "Business Development",                                              # sales thuần
    "Business Development Manager (IT/Software)",                        # có từ IT vẫn loại
    "Kỹ Sư Thiết Kế Điện",
    "Nhân Viên Thiết Kế Hệ Thống Điện, Điện Nhẹ, Hệ Thống Bms / Scada",
    "Cloud Technical Sales / PreSales",                                  # Q1
    "Trưởng Nhóm Presales",                                              # Q1
    "Phụ Trách Bảo Vệ Dữ Liệu (Data Protection Officer)",               # Q2
    "Kỹ Sư Cấu Hình triển khai hệ thống AV (Audio Visual)",             # Q3
    "Kỹ Sư IoT (IoT Engineer)",                                          # Q4
    "Research and Teaching Assistant (RTA) in Business Analytics",      # Q7
    "Operations Manager",                                                # Q8
    "Generative Game Artist (Intern)",
    "AI ENGINEER (PCB SECTION – PRODUCTION)",                            # H2
    "Kỹ Sư Lập Trình PLC Cho Máy Tự Động",                               # bác đề xuất 376
])
def test_tier0_excluded(cfg, title):
    st, level = F.classify_it(title, [], "", "", "topcv", cfg, matcher=None)
    assert (st, level) == ("non_it", 0)


def test_category_cannot_rescue_excluded(cfg):
    st, level = F.classify_it("Nhân Viên Thiết Kế Hệ Thống Điện, Điện Nhẹ", [], "Python SQL Docker Kubernetes",
                              "IT Phần cứng - Mạng", "vieclam24h", cfg, matcher=None)
    assert (st, level) == ("non_it", 0)


@pytest.mark.parametrize("title", [
    "Sales Business Intelligence Specialist",            # ngoại lệ vai trò IT
    "Kỹ Sư Embedded Software Cho Mảng Tự Động Hoá",      # H6
    "[Da Nang] UI/UX Designer",                           # H1: không thuộc nhóm đồ họa
])
def test_exceptions_not_excluded(cfg, title):
    assert not F.excluded_role(title, cfg)


@pytest.mark.parametrize("title,expected", [
    ("Chuyên viên An Toàn Thông tin", "it"),
    ("Chuyên viên An ninh thông tin - Pentester", "it"),
    ("Backend Developer", "it"),
    ("Kế Toán Tổng Hợp", "non_it"),
])
def test_tier1(cfg, title, expected):
    st, level = F.classify_it(title, [], "", "", "careerviet", cfg, matcher=None)
    assert (st, level) == (expected, 1)


def test_tier2_security_signal(cfg):
    jd = ("Khảo sát, tư vấn, thiết kế giải pháp bảo mật: firewall, IDS/IPS, DLP, antivirus, SIEM, WAF, "
          "phòng chống DDoS cho hệ thống CNTT của khách hàng.")
    st, level = F.classify_it("Postsale Security Engineer", [], jd, "", "careerviet", cfg)
    assert (st, level) == ("it", 2)


def test_tier2_no_signal_is_non_it(cfg):
    st, level = F.classify_it("Chuyên Viên Kỹ Thuật", [], "Kiểm tra máy móc nhà xưởng, báo cáo ca.", "", "glints", cfg)
    assert (st, level) == ("non_it", 2)


def test_old_rule_untouched():
    """Luật cũ vẫn chạy được để đo trước/sau (eval_it_filter --rule old)."""
    assert F.classify("Backend Developer") == "it"
    assert F.classify("Embedded Engineer") == "it"


def test_tier2_dense_core_skills_without_family_or_category():
    sig = {"core": 17, "sec": 0, "fam": False, "cat": False}   # "Technical Leader" (topcv), JD 17 kỹ năng lõi
    assert F.tier2_decide(sig, "topcv", {"k_fam": 2, "k_sec": 4, "k_core": 10, "k_cat": None}) == "it"
    assert F.tier2_decide(sig, "topcv", {"k_fam": 2, "k_sec": 4, "k_core": None, "k_cat": None}) == "non_it"
