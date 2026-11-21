# -*- coding: utf-8 -*-
"""tests.unit.test_normalization_step
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Kiểm thử Bước 04 Normalization theo đặc tả docs/prompting/P4_normalization.md:
- N1: 34 tỉnh/thành sau sáp nhập, tên cũ, remote, ngoại quốc
- N2: 6 cấp bậc tiếng Việt (raw -> title -> exp -> JEV)
- N3: 12 nhóm nghề IT (khớp từ nguyên vẹn PRE-1, title -> skills -> JEV)
- N4: Ánh xạ kỹ năng chuẩn theo skills.json (ReactJS, React.js -> React)
- N5: Chuẩn hóa tên công ty (normalize_company_name)
- N6 & N7: Outlier IQR, Winsorize 1-99% và log1p
- N8: Gộp 8 nguồn thành all.parquet và copy sang data/curated/
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from preprocessing.common import province
from preprocessing.normalization.cross_deduplicator import normalize_company_name
from preprocessing.normalization.run import (
    _normalize_locations,
    apply_global_salary_normalizations,
    process_source_records,
)
from preprocessing.normalization.text_cleaner import (
    canonicalize_skills,
    classify_seniority,
    has_term,
)
from preprocessing.normalization.job_title import build_title_dict, core_title, family_from_title, fold


def test_n1_province_mapping_and_locations():
    """Kiểm tra N1: 34 tỉnh sau sáp nhập, tên cũ, remote và foreign."""
    cases = [
        ({"tinh_thanh": "Ha Noi", "raw": "Ha Noi"}, "TP. Hà Nội", "ha_noi", None, False, False),
        ({"tinh_thanh": "Bình Dương", "raw": "Bình Dương"}, "TP. Hồ Chí Minh", "ho_chi_minh", "Bình Dương", False, False),
        ({"tinh_thanh": "Quảng Nam", "raw": "Quảng Nam"}, "TP. Đà Nẵng", "da_nang", "Quảng Nam", False, False),
        ({"tinh_thanh": "Hà Giang", "raw": "Hà Giang"}, "Tuyên Quang", "tuyen_quang", "Hà Giang", False, False),
        ({"tinh_thanh": None, "raw": "Remote"}, None, None, None, True, False),
        ({"tinh_thanh": None, "raw": "Tokyo, Japan"}, None, None, None, False, True),
    ]

    for loc_in, exp_name, exp_key, exp_old, exp_rem, exp_forg in cases:
        norm_locs, primary = _normalize_locations([loc_in])
        assert len(norm_locs) == 1
        l = norm_locs[0]
        assert l["tinh_thanh"] == exp_name
        assert l["tinh_key"] == exp_key
        if exp_old:
            assert l["tinh_cu"] == exp_old
        assert l["remote"] == exp_rem
        assert l["ngoai_vn"] == exp_forg
        assert primary == exp_name


def test_n2_seniority_classification_order_and_edge_cases():
    """N2 (PH6 N12): 5 cấp, chỉ hai tầng raw -> title; số năm không còn tạo nhãn (chuyển PH7, có cờ)."""
    assert classify_seniority(raw_seniority="Trưởng phòng", title="Software Engineer") == ("Lead/Manager", "raw")
    assert classify_seniority(raw_seniority=None, title="Senior Java Developer") == ("Senior", "title")
    assert classify_seniority(raw_seniority="Thực Tập Sinh") == ("Intern/Fresher", "raw")
    assert classify_seniority(raw_seniority="Nhân viên", title="Senior DevOps Engineer") == ("Senior", "title")
    # K6 (người dùng chốt): Project/Product Manager là Lead/Manager
    assert classify_seniority(None, "Project Manager") == ("Lead/Manager", "title")
    # International Business Analyst không bị nhận thành Intern (khớp từ nguyên vẹn)
    assert classify_seniority(None, "International Business Analyst") == (None, None)
    # Tham số số năm bị bỏ qua: không suy cấp ở PH6
    assert classify_seniority("Nhân viên", "Backend Developer", 3.0) == (None, None)


def test_n3_job_family_12_groups_plus_other():
    """N3 (PH6 N17): 10 nhóm (Web, Mobile, Game, Bridge, DevOps/Cloud, Tester, Security, IoT, Design, Data/AI) + Other."""
    d = build_title_dict([])

    def fam(title, skills=()):
        core, _, hint = core_title(title)
        return family_from_title(fold(core), None, skills, d, hint)

    assert fam("BackEnd Engineer (Java, Spring Boot)")[0] == "Web"
    assert fam("Middle/Senior Embedded Software Engineer (C++,C)")[0] == "IoT"
    assert fam("International Business Analyst")[0] == "Bridge"
    assert fam("Lead QA Tester")[0] == "Tester"
    assert fam("DevOps Cloud Engineer")[0] == "DevOps/Cloud"
    assert fam("Senior Data Scientist (AI/ML)")[0] == "Data/AI"
    assert fam("Data Engineer")[0] == "Data/AI"
    assert fam("Product Owner")[0] == "Bridge"
    assert fam("Nhân Viên Thiết Kế") == ("Other", "none")      # thiết kế đồ họa không phải UI/UX
    assert fam("Software Engineer") == ("Other", "none")        # từ chung: cần kỹ năng xác nhận
    assert fam("Technical Lead", ["React", "Vue"]) == ("Web", "skills")
    assert fam("Technical Lead", ["React", "Java"]) == ("Other", "none")  # hai nhóm hòa: K11


def _pre44_dict():
    """Từ điển nhỏ dựng tay theo các mục thật của job_titles.json (PRE-44)."""
    return build_title_dict([
        {"canonical": "IT", "family": "Web", "aliases": ["it"], "approved": True},
        {"canonical": "IT Engineer", "family": "Web", "aliases": ["it engineer"], "approved": True},
        {"canonical": "Developer", "family": "Web", "aliases": ["developer"], "approved": True},
        {"canonical": "Data Engineer", "family": "Data/AI", "aliases": ["data engineer"], "approved": True},
    ])


def _fam44(title, skills=(), jd=""):
    from preprocessing.normalization.job_title import canonical_title
    d = _pre44_dict()
    core, _, hint = core_title(title)
    canon = canonical_title(fold(core), d)[0]
    return family_from_title(fold(core), canon, list(skills), d, hint, jd_text=fold(jd))


def test_n3a_title_keywords_beat_generic_dictionary_titles():
    """PRE-44 N3a (1.B): chức danh chung trong từ điển không chặn từ khóa tiêu đề cụ thể."""
    assert _fam44("IT Security Analyst") == ("Security", "title")
    assert _fam44("IT Business Analyst") == ("Bridge", "title")
    assert _fam44("AI Engineer") == ("Data/AI", "title")          # từng khớp gần đúng "IT Engineer" → Web
    assert _fam44("Flutter Developer") == ("Mobile", "title")     # từng khớp "Developer" → Web
    assert _fam44("Data Platform Engineer")[0] == "Data/AI"       # chức danh cụ thể vẫn đứng trước từ khóa ("platform engineer")
    assert _fam44("Developer") == ("Web", "canonical_generic")    # chức danh chung về lập trình vẫn là Web


def test_n3c_system_network_is_infra_support():
    """PRE-44 N3c (3.A, 6.A): helpdesk, quản trị mạng là nhóm Infra/Support, không còn gộp vào Security."""
    assert _fam44("IT Helpdesk") == ("Infra/Support", "title")
    assert _fam44("Network Engineer") == ("Infra/Support", "title")
    assert _fam44("Penetration Tester")[0] == "Security"


def test_n3b_generic_it_title_uses_jd_then_other():
    """PRE-44 N3b (2, 5.A): tiêu đề chung về IT đọc JD; JD không đủ tín hiệu thì Other, không mặc định Web."""
    jd_support = "Hỗ trợ người dùng, cài đặt phần mềm, sửa chữa máy tính, máy in, quản trị mạng LAN."
    assert _fam44("Nhân Viên IT", jd=jd_support) == ("Infra/Support", "jd")
    assert _fam44("Nhân Viên IT", jd="Làm việc trong môi trường năng động.") == ("Other", "none")
    # từ quá chung ("bảo mật", "ai") không đủ để thắng
    assert _fam44("Chuyên Viên IT", jd="Bảo mật thông tin công ty, ứng dụng AI.") == ("Other", "none")
    # hòa giữa hai nhóm → không chọn
    assert _fam44("Nhân Viên IT", jd="helpdesk, máy in, tester, kiểm thử")[0] == "Other"


def test_n3b_jd_layer_not_used_for_developer_titles():
    """Tiêu đề chung về lập trình giữ Web theo tiêu đề dù JD nhắc docker, kubernetes, ci/cd."""
    assert _fam44("Developer", ["Docker", "Kubernetes"], jd="devops, ci/cd, kubernetes, docker") == ("Web", "canonical_generic")


def _fam44b(title, skills=(), jd=""):
    """Như _fam44 nhưng truyền tiêu đề đầy đủ và cấp (N3e, PRE-44 vòng 2)."""
    from preprocessing.normalization.job_title import canonical_title
    d = build_title_dict([
        {"canonical": "IT", "family": "Web", "aliases": ["it"], "approved": True},
        {"canonical": "Công Nghệ Thông Tin", "family": "Web", "aliases": ["cong nghe thong tin"], "approved": True},
        {"canonical": "Technical", "family": "Web", "aliases": ["technical"], "approved": True},
        {"canonical": "Developer", "family": "Web", "aliases": ["developer"], "approved": True},
    ])
    core, level, hint = core_title(title)
    canon = canonical_title(fold(core), d)[0]
    return family_from_title(fold(core), canon, list(skills), d, hint, jd_text=fold(jd), title_fold=fold(title), title_level=level)


def test_n3e_manager_and_dev_titles():
    """Người dùng chấm 22/11: trưởng nhóm IT chung là Bridge; tiêu đề IT chung nhắc lập trình là Web."""
    assert _fam44b("Trưởng Nhóm Công Nghệ Thông Tin", jd="helpdesk, máy in, mạng lan, server") == ("Bridge", "title_manager")
    assert _fam44b("Trưởng Nhóm IT")[0] == "Bridge"
    assert _fam44b("Trưởng Nhóm Hạ Tầng Công Nghệ Thông Tin")[0] != "Bridge"   # hạ tầng giữ Infra/JD
    assert _fam44b("Technical Lead")[0] != "Bridge"                             # Tech Lead không phải quản lý IT chung
    assert _fam44b("Nhân Viên IT - Lập Trình & Quản Trị Hệ Thống", jd="helpdesk, máy in, server") == ("Web", "title_full")


def test_n3e_paren_and_new_keywords():
    assert _fam44b("System Admin (AI Automation/Devops)") == ("DevOps/Cloud", "title_paren")
    assert _fam44b("DevSecOps Engineer (DevOps, AWS)")[0] == "Security"
    assert _fam44b("Thực Tập Sinh Đảm Bảo Chất Lượng (QA Intern)") == ("Tester", "title_paren")
    assert _fam44b("IT Infrastructure Lead")[0] == "Infra/Support"
    assert _fam44b("Infrastructure Lead (Cloud)")[0] != "Infra/Support"
    assert _fam44b("Nhân Viên Quản Trị Hệ Thống An Ninh Mạng")[0] == "Infra/Support"
    assert _fam44b("Chuyên Viên An Ninh Thông Tin (ISO)")[0] == "Security"
    assert _fam44b("Senior Test Automation Engineer")[0] == "Tester"
    assert _fam44b("Data Governance Specialist")[0] == "Data/AI"
    assert _fam44b("Chuyên Viên Triển Khai Phần Mềm")[0] == "Bridge"
    assert _fam44b("IT Planning & Governance Analyst")[0] == "Bridge"


def test_n3b_jd_margin_two():
    """JD_MARGIN = 2: JD lưỡng lự giữa hai nghề (hơn nhau 1 tín hiệu) không quyết định."""
    from preprocessing.normalization.job_title import jd_family
    assert jd_family(fold("helpdesk, máy in, mạng lan, kiểm thử"), []) == "Infra/Support"
    assert jd_family(fold("helpdesk, máy in, tester, kiểm thử"), []) is None


def test_n16_fuzzy_rejects_swapped_acronym():
    """L-58: khớp gần đúng không ghép hai tiêu đề chỉ khác nhau ở từ viết tắt ngắn (AI/BI ↔ IT)."""
    from preprocessing.normalization.job_title import canonical_title
    d = build_title_dict([
        {"canonical": "IT Specialist", "family": "Bridge", "aliases": ["it specialist"], "approved": True},
        {"canonical": "IT Engineer", "family": "Web", "aliases": ["it engineer"], "approved": True},
        {"canonical": "Quản Trị Cơ Sở Dữ Liệu DBA", "family": "Data/AI", "aliases": [], "approved": True},
        {"canonical": "Software Engineer", "family": "Web", "aliases": ["software engineer"], "approved": True},
    ])
    assert canonical_title(fold("AI Specialist"), d)[0] is None
    assert canonical_title(fold("BI Engineer"), d)[0] is None
    # vẫn khớp khi chỉ một bên thiếu từ ngắn (không phải đổi từ này lấy từ kia)
    assert canonical_title(fold("quan tri du lieu"), d)[0] == "Quản Trị Cơ Sở Dữ Liệu DBA"
    # âm tiết tiếng Việt ngắn ("ky su", "cao cap") không phải từ viết tắt
    assert canonical_title(fold("ky su quan tri co so du lieu"), d)[0] == "Quản Trị Cơ Sở Dữ Liệu DBA"
    assert canonical_title(fold("software development engineer in test"), d)[0] == "Software Engineer"


def test_n3_ai_specialist_and_bi_engineer_are_data_ai():
    """L-58: "AI Specialist" từng thành Bridge (khớp "IT Specialist"), "BI Engineer" từng thành Other."""
    d = build_title_dict([
        {"canonical": "IT Specialist", "family": "Bridge", "aliases": ["it specialist"], "approved": True},
        {"canonical": "IT Engineer", "family": "Web", "aliases": ["it engineer"], "approved": True},
    ])
    from preprocessing.normalization.job_title import canonical_title
    for title in ("AI Specialist", "BI Engineer"):
        core = fold(core_title(title)[0])
        assert family_from_title(core, canonical_title(core, d)[0], [], d)[0] == "Data/AI", title


def test_n4_canonical_skills():
    """Kiểm tra N4: Ánh xạ kỹ năng về tên chuẩn theo skills.json và loại bỏ trùng lặp."""
    input_skills = ["ReactJS", "React.js", "Java", "Docker", "react"]
    res = canonicalize_skills(input_skills)
    assert res == ["React", "Java", "Docker"]

    input_skills_2 = ["python", "Python3"]
    assert canonicalize_skills(input_skills_2) == ["Python"]


def test_n5_company_name_normalization():
    """Kiểm tra N5: Chuẩn hóa tên công ty loại bỏ tiền tố/hậu tố pháp nhân."""
    c1 = normalize_company_name("CÔNG TY CỔ PHẦN CÔNG NGHỆ KIOTVIET")
    assert "kiotviet" in c1
    assert "công ty" not in c1
    assert "cổ phần" not in c1


def test_n6_n7_salary_outliers_winsorize_and_log():
    """Kiểm tra N6 & N7: Outlier IQR, Winsorize 1-99% và log1p(x)."""
    # Tạo dải dữ liệu 100 tin lương bình thường (10tr - 50tr) và 1 tin 2 tỷ
    normal_salaries = [float(x * 1_000_000) for x in range(10, 51)] * 3  # 123 rows
    outlier_salary = 400_000_000.0  # 400 triệu: trong ngưỡng cứng nhưng là ngoại lai IQR

    test_rows = []
    for s in normal_salaries:
        test_rows.append({"salary_min_vnd": s * 0.8, "salary_max_vnd": s, "description_clean": ""})
    test_rows.append({"salary_min_vnd": outlier_salary, "salary_max_vnd": outlier_salary, "description_clean": ""})
    test_rows.append({"salary_min_vnd": 2.026e9, "salary_max_vnd": 2.026e9, "description_clean": ""})  # mã tin đọc nhầm

    updated_rows, stats = apply_global_salary_normalizations(test_rows)

    # Ngoài 1–500 triệu/tháng: bỏ số, gắn cờ salary_suspect
    bogus = updated_rows[-1]
    assert bogus["salary_suspect"] is True and math.isnan(bogus["salary_max_vnd"])
    assert stats["salary_suspect_count"] == 1

    # Tin 400 triệu phải bị gắn cờ is_outlier_salary = True
    last_row = updated_rows[-2]
    assert last_row["is_outlier_salary"] is True

    # Capped value không được vượt quá mức 99%
    assert last_row["salary_max_vnd_capped"] < outlier_salary
    assert last_row["salary_max_vnd_capped"] <= stats["winsorize_q99_max"]

    # Kiểm tra log1p cho mức 20,000,000 VND ~ 16.81
    sal_20m = 20_000_000.0
    expected_log = math.log1p(sal_20m)
    assert round(expected_log, 2) == 16.81

    # Kiểm tra hàng có salary 20m có log_salary_max gần 16.81
    row_20m = next(r for r in updated_rows if r["salary_max_vnd"] == 20_000_000.0)
    assert abs(row_20m["log_salary_max"] - 16.8112) < 0.01


def test_n3e_erp_consultant_vs_erp_developer():
    """ERP/SAP tư vấn, triển khai -> Bridge; lập trình ERP/SAP không bị kéo sang Bridge."""
    assert _fam44b("ERP Solution Consultant")[0] == "Bridge"
    assert _fam44b("Chuyên Viên SAP (SAP FICO)")[0] == "Bridge"
    assert _fam44b("ERP Developer (Odoo, Python, API, PostgreSQL)")[0] != "Bridge"
    assert _fam44b("SAP Fiori Developer")[0] != "Bridge"
