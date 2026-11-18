# -*- coding: utf-8 -*-
"""Kiểm thử Bước 03 Transformation (docs/spec/preprocessing/spec/P3_transformation.md).

Kiểm định:
- T2: Lương D2 (2,000 USD), D3 (Từ 15tr), D7 (title cascade), T2f (lương < 1M).
- T4: Kinh nghiệm (0-0, 1-2, 3-None, 0-1, 24 months).
- T3: Ngày tháng ISO / dd/mm/yyyy & cờ deadline_before_crawl.
- T8: Địa điểm 3 cấp.
- T7: Kỹ năng & phúc lợi song ngữ.
- T6b: Dịch thuật LLM Gemini Flash có cache và kiểm tra KEEP term.
- Hợp đồng output: Parquet có đủ cột mới, rows_conserved: true.
"""

from pathlib import Path
import pandas as pd
import pytest

from preprocessing.transformation import run as transformation
from preprocessing.transformation.date_parser import parse_date, process_dates
from preprocessing.transformation.experience_parser import parse_experience
from preprocessing.transformation.location_parser import split_location
from preprocessing.transformation.salary_parser import UniversalSalaryParser, parse_salary_cascade
from preprocessing.transformation.skill_extractor import extract_benefits, extract_skills, filter_metadata_skills
from preprocessing.common import step_report


def test_t2_salary_parser_d2_d3_d7_under_1m():
    # D2: "Up to 2,000 USD" không được ra 50.800 VND mà phải ra 50.800.000 VND
    p1 = UniversalSalaryParser.parse_text("Up to 2,000 USD")
    assert p1["salary_max_vnd"] == 2_000 * 25_400.0
    assert p1["salary_min_vnd"] is None

    # D3: "Từ 15 triệu" chỉ đặt min, max = None
    p2 = UniversalSalaryParser.parse_text("Từ 15 triệu")
    assert p2["salary_min_vnd"] == 15_000_000.0
    assert p2["salary_max_vnd"] is None

    # Khoảng chuẩn: "8.5 - 12 triệu"
    p3 = UniversalSalaryParser.parse_text("8.5 - 12 triệu")
    assert p3["salary_min_vnd"] == 8_500_000.0
    assert p3["salary_max_vnd"] == 12_000_000.0

    # T2f: Lương dưới 1 triệu -> cờ salary_under_1m
    p4 = UniversalSalaryParser.parse_text("0.5 - 1 triệu")
    assert p4["salary_min_vnd"] == 500_000.0
    assert p4["salary_under_1m"] is True

    # D7: Cascade title khi header thỏa thuận
    cas = parse_salary_cascade("Thỏa thuận", title="Senior Java Dev (15-20tr)")
    assert cas["salary_source"] == "title"
    assert cas["salary_min_vnd"] == 15_000_000.0
    assert cas["salary_max_vnd"] == 20_000_000.0


def test_t4_experience_parser():
    # Không yêu cầu
    assert parse_experience("Không yêu cầu kinh nghiệm") == (0.0, 0.0)
    assert parse_experience("Chưa có kinh nghiệm") == (0.0, 0.0)
    # Khoảng 1 - 2 năm
    assert parse_experience("1 - 2 năm") == (1.0, 2.0)
    assert parse_experience("1 to 2 years") == (1.0, 2.0)
    # Trên 3 năm
    assert parse_experience("Trên 3 năm") == (3.0, None)
    assert parse_experience("3+ years") == (3.0, None)
    # Dưới 1 năm
    assert parse_experience("Dưới 1 năm") == (0.0, 1.0)
    # Đơn vị tháng
    assert parse_experience("24 months") == (2.0, 2.0)
    assert parse_experience("6 tháng") == (0.5, 0.5)


def test_t3_date_parser_and_expiration():
    assert parse_date("2026-10-14T04:20:13.27873Z") == "2026-10-14"
    assert parse_date("15/10/2026") == "2026-10-15"
    assert parse_date("2026-11-01") == "2026-11-01"

    # Kiểm tra cờ deadline_before_crawl
    posted, deadline, is_expired = process_dates("2026-10-01", "2026-10-20", "2026-11-01")
    assert posted == "2026-10-01"
    assert deadline == "2026-10-20"
    assert is_expired is True

    _, _, not_expired = process_dates("2026-10-01", "2026-11-15", "2026-11-01")
    assert not_expired is False


def test_t8_split_location_3_tiers():
    # Địa chỉ đầy đủ 3 cấp
    res1 = split_location("Tòa nhà MB, 18 Lê Văn Lương, P. Thanh Xuân, Hà Nội")
    assert res1["dia_chi_cu_the"] == "Tòa nhà MB, 18 Lê Văn Lương"
    assert res1["phuong_xa"] == "Phường Thanh Xuân"
    assert "Hà Nội" in res1["tinh_thanh"]

    # Quận/huyện bị bỏ hẳn; phường cũ (Đội Cấn đã sáp nhập) không có trong danh mục mới -> None
    res2 = split_location("Quận 1, Hồ Chí Minh")
    assert res2["dia_chi_cu_the"] is None
    assert res2["phuong_xa"] is None
    assert "Hồ Chí Minh" in res2["tinh_thanh"]

    # Remote
    old = split_location("Số 54 Giang Văn Minh, Phường Đội Cấn, Quận Ba Đình, Thành phố Hà Nội, Việt Nam")
    assert (old["dia_chi_cu_the"], old["phuong_xa"], old["tinh_thanh"]) == ("Số 54 Giang Văn Minh", None, "TP. Hà Nội")

    # Phần trong ngoặc là thông tin cũ; tiền tố "Hà Nội :" bị bỏ
    paren = split_location("Hà Nội : Số 181 Nghi Tàm, Phường Tây Hồ (Quận Tây Hồ, Hà Nội cũ)")
    assert (paren["dia_chi_cu_the"], paren["phuong_xa"], paren["tinh_thanh"]) == ("Số 181 Nghi Tàm", "Phường Tây Hồ", "TP. Hà Nội")

    # Tên đường "Điện Biên Phủ" không phải tỉnh Điện Biên
    assert split_location("72 Điện Biên Phủ, Ba Đình, Hà Nội")["tinh_thanh"] == "TP. Hà Nội"

    res3 = split_location("Remote")
    assert res3["dia_chi_cu_the"] is None
    assert res3["phuong_xa"] is None
    assert res3["tinh_thanh"] is None
    assert res3["raw"] == "Remote"


def test_t7_skills_and_benefits_extraction():
    # T7a: Lọc tag metadata
    raw_tags = ["Java", "Việc làm TP.HCM", "java", "Có kinh nghiệm làm việc nhóm tốt"]
    clean_tags = filter_metadata_skills(raw_tags)
    assert clean_tags == ["Java"]

    # T7b: Rút từ JD
    jd_sample = "Thành thạo ReactJS, Spring Boot và có kiến thức về SQL, Docker."
    skills = extract_skills(["Java"], jd_sample)
    assert "React" in skills
    assert "SQL" in skills
    assert "Docker" in skills

    # T7c: Rút phúc lợi
    bens = extract_benefits(["13th month salary"], "Chế độ bảo hiểm sức khỏe cao cấp và khám sức khỏe định kỳ")
    assert "Lương tháng 13" in bens
    assert "Bảo hiểm" in bens
    assert "Khám sức khỏe" in bens


def test_transformation_pipeline_integration(tmp_path, monkeypatch):
    test_in = tmp_path / "data" / "preprocessing" / "02_integration"
    test_out = tmp_path / "data" / "preprocessing" / "03_transformation"
    test_rep = tmp_path / "reports" / "preprocessing"
    test_rev = tmp_path / "data" / "preprocessing" / "review"

    test_in.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(transformation, "IN_FILE", test_in / "all.parquet")
    monkeypatch.setattr(transformation, "OUT_FILE", test_out / "all.parquet")
    monkeypatch.setattr(step_report, "REPORTS_ROOT", test_rep)

    # Tạo data parquet đầu vào P2 mẫu
    rows_p2 = [
        {
            "job_id_global": "g1", "source_platform": "glints", "source_job_id": "1",
            "source_url": "https://g/1", "crawled_at": "2026-11-01",
            "it_rule": "it", "it_rule_level": 1, "it_status": "it", "dedup_key": "k1", "also_on": [],
            "job_title": "Java Dev (15-20tr)", "company_name": "Cty A", "company_address": None,
            "raw_category_text": None, "raw_location_text": "Hà Nội", "working_locations": ["Hà Nội"],
            "raw_posted_date": "2026-10-25", "raw_deadline": "2026-11-15",
            "raw_salary_text": "Thỏa thuận", "raw_employment_type": "Full-time",
            "raw_experience_text": "1 - 2 năm", "raw_seniority_text": "Junior",
            "raw_education_text": "0",  # Sneaky null T1
            "raw_headcount": "2 người", "skills_list": ["Java"], "benefits_list": ["13th month salary"],
            "raw_description_text": "Tuyển Java Dev làm việc với Spring Boot và SQL.",
            "raw_requirements_text": "Biết Docker là lợi thế.",
        }
    ]
    df_in = pd.DataFrame(rows_p2)
    df_in.to_parquet(test_in / "all.parquet", engine="pyarrow", index=False)

    reports = transformation.run(["glints"], dry_run=False)
    rep = reports["glints"]

    # 1. Kiểm tra bảo toàn dòng
    assert rep.data["input"]["rows"] == 1
    assert rep.data["output"]["rows"] == 1
    assert rep.data["checks"]["rows_conserved"] is True

    # 2. Đọc lại file parquet P3
    p3_file = test_out / "all.parquet"
    assert p3_file.exists()
    df_p3 = pd.read_parquet(p3_file)
    row = df_p3.iloc[0]

    # T1: Sneaky null
    assert row["raw_education_text"] is None
    # T2: Title cascade
    assert row["salary_min_vnd"] == 15_000_000.0
    assert row["salary_max_vnd"] == 20_000_000.0
    assert row["salary_source"] == "title"
    # T4: Kinh nghiệm
    assert row["exp_min_years"] == 1.0
    assert row["exp_max_years"] == 2.0
    # T5: Headcount
    assert row["headcount"] == 2
    # T7: Kỹ năng & phúc lợi
    assert "Spring Boot" in row["skills_clean"] or "Java" in row["skills_clean"]
    assert "Lương tháng 13" in row["benefits_std"]
    # T8: Địa điểm
    assert len(row["locations"]) == 1
    assert "Hà Nội" in row["locations"][0]["tinh_thanh"]


# ---------------------------------------------------------------- luật mới 18/11 (docs/spec/preprocessing/03_transformation.md mục 2.2)
from preprocessing.transformation import jd_extractor as jx  # noqa: E402


def test_t3b_posted_month_from_posted_date_or_first_crawl_in_vn_time():
    # topcv_2325743: không có ngày đăng, cào lần đầu 2026-10-20T18:44Z (21/10 giờ Việt Nam)
    assert transformation.posted_month(None, "2026-10-20T18:44:44.698712+00:00") == "2026-10"
    # 31/10 18:30 UTC là 01/11 01:30 giờ Việt Nam
    assert transformation.posted_month(None, "2026-10-31T18:30:00+00:00") == "2026-11"
    # itviec: có ngày đăng thì lấy ngày đăng
    assert transformation.posted_month("2026-09-29", "2026-10-20T00:00:00+00:00") == "2026-09"
    assert transformation.posted_month(None, None) is None


def test_t6_5_benefits_clean_nfc_and_drop_empty():
    import unicodedata
    nfd = unicodedata.normalize("NFD", "Bảo hiểm sức khỏe")
    out = transformation.clean_benefits([nfd, "  ", "Lương​ tháng 13 "])
    assert out == ["Bảo hiểm sức khỏe", "Lương tháng 13"]
    assert all(unicodedata.is_normalized("NFC", x) for x in out)
    assert transformation.clean_benefits(None) is None


def _rec(**kw):
    base = {"source_platform": "topcv", "job_title_clean": "", "description_clean": "", "requirements_clean": "",
            "raw_work_mode": None, "raw_employment_type": None}
    base.update(kw)
    return base


def test_t9a_title_signal_beats_raw_office():
    # itviec "Remote - QA Engineer (Games)", ô ghi Tại văn phòng
    out = jx.work_mode(_rec(source_platform="itviec", job_title_clean="Remote - QA Engineer (Games)", raw_work_mode="Tại văn phòng"))
    assert (out["work_mode_raw"], out["work_mode_jd"], out["work_mode_jd_strong"], out["work_mode_conflict"]) == \
        ("onsite", "remote", True, True)


def test_t9a_wfh_days_per_week_is_strong_hybrid():
    # glints "System/ Network Administration and Coordinator - French Speaking"
    out = jx.work_mode(_rec(source_platform="glints", job_title_clean="System/ Network Administration and Coordinator",
                            description_clean="Work from home 2 days/ week.", raw_work_mode="Làm tại công ty / Onsite"))
    assert out["work_mode_jd"] == "hybrid" and out["work_mode_jd_strong"] and "WH4" in out["work_mode_jd_rules"]


def test_t9a_noise_hybrid_cloud_and_factory_not_matched():
    # topcv "Kỹ Sư Triển Khai Giải Pháp An Toàn Thông Tin"
    a = jx.work_mode(_rec(requirements_clean="Có kinh nghiệm triển khai SOC trên On-Premise, Cloud hoặc Hybrid."))
    # vietnamworks "Kỹ Sư IT": "tại nhà máy" không phải "tại nhà"
    b = jx.work_mode(_rec(source_platform="vietnamworks",
                          description_clean="Ứng viên có thể chọn địa điểm làm việc tại nhà máy Hà Nội hoặc Hưng Yên"))
    assert a["work_mode_jd"] is None and b["work_mode_jd"] is None


def test_t9a_raw_maps_itviec_flexible_and_jobsgo_remote_type():
    assert jx.work_mode_raw("itviec", "Linh hoạt", None) == "hybrid"
    assert jx.work_mode_raw("topcv", "Làm việc tại văn phòng / Onsite, Kết hợp tại văn phòng và từ xa (Hybrid)", None) == "hybrid"
    assert jx.work_mode_raw("jobsgo", None, "Toàn thời gian, Remote") == "remote"
    assert jx.work_mode_raw("vietnamworks", None, "7") == "remote"
    assert jx.work_mode_raw("vietnamworks", None, "6") is None


def test_t9b_intern_title_conflicts_with_full_time_raw():
    out = jx.employment_type(_rec(source_platform="itviec", job_title_clean="Oracle Consultant Intern", raw_employment_type="FULL_TIME"))
    assert (out["employment_type_raw"], out["employment_type_jd"], out["employment_type_conflict"]) == \
        ("full_time", "internship", True)
    # jobsgo: "Không Hỗ Trợ Mộc Thực Tập" là nhiễu, không phải tin thực tập
    n = jx.employment_type(_rec(source_platform="jobsgo",
                                job_title_clean="Tư Vấn Triển Khai Phần Mềm Website Fulltime (Không Hỗ Trợ Mộc Thực Tập)",
                                raw_employment_type="Toàn thời gian"))
    assert n["employment_type_jd"] != "internship"
    # nhiều giá trị: giữ cả danh sách, bỏ Remote (là hình thức làm việc)
    assert jx.employment_types_raw("Toàn thời gian, Bán thời gian, Remote") == ["full_time", "part_time"]
    assert jx.employment_types_raw("6") == []


@pytest.mark.parametrize("line, lo, hi, kind", [
    ("Có tối thiểu 5 năm kinh nghiệm trong lĩnh vực an ninh mạng hoặc an toàn thông tin.", 5.0, None, "jd"),  # topdev
    ("5+ years of professional experience as a Product Owner, Business Analyst.", 5.0, None, "jd"),  # itviec
    ("Có từ 0-1 năm kinh nghiệm trong lĩnh vực An toàn thông tin, An ninh mạng.", 0.0, 1.0, "jd"),  # careerviet
    ("Sinh viên năm 4, hoặc mới tốt nghiệp trong lĩnh vực lập trình.", 0.0, None, "jd_zero"),  # itviec Thực tập sinh DEV
])
def test_t9c_experience_from_jd(line, lo, hi, kind):
    got = jx.experience_from_lines([line])
    assert (got["exp_min_years_jd"], got["exp_max_years_jd"], got["exp_jd_kind"]) == (lo, hi, kind)


def test_t9c_salary_review_years_is_noise():
    assert jx.experience_from_lines(["Review lương định kì vào tháng 3 hàng năm, thưởng sau 2 năm làm việc."]) is None


def test_t9_refuses_unapproved_dictionary(tmp_path):
    import json
    d = json.loads(jx.DICT_PATH.read_text(encoding="utf-8"))
    d["_meta"]["approved"] = False
    p = tmp_path / "jd.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(jx.DictionaryNotApproved):
        jx.load_rules(str(p))


def test_t7_skills_from_original_text_only():
    # Bản dịch không được thêm kỹ năng: code cũ nối *_vi vào văn bản rút kỹ năng
    rec = {"description_clean": "We build backend services.", "requirements_clean": "Good communication.",
           "description_vi": "Chúng tôi xây dựng dịch vụ backend bằng Docker.", "requirements_vi": None}
    assert "Docker" not in transformation.skill_source_text(rec)
