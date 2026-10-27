# -*- coding: utf-8 -*-
"""tests.test_skill_processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Kiểm thử module Text & Skill Processing của Phát Nguyễn (Giai đoạn 3, Bước 3 — TASKS.md §6.3.3).

Chạy offline hoàn toàn: fixture tự chứa + 1 file raw thật trong repo
(`data/vietnamworks/raw/2026-10-16/raw_batch.json`, bỏ qua nếu thiếu).

Cover DoD §6.3.3:
  * 100% tiêu đề ánh xạ vào 1 trong 12 Job Family hoặc cờ `JF00_OTHER_IT`.
  * Không còn trùng lặp kỹ năng do hoa/thường hoặc ký tự dấu chấm.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from preprocessing.normalization.text_cleaner import (  # noqa: E402
    clean_job_title,
    clean_jd_text,
    detect_remote,
    normalize_city,
    normalize_work_locations,
    process_record_text,
)
from preprocessing.normalization.taxonomy_mapper import (  # noqa: E402
    JOB_FAMILIES,
    SENIORITY_LEVELS,
    classify_job_family,
    standardized_seniority,
)
from preprocessing.normalization.skill_normalizer import (  # noqa: E402
    SkillNormalizer,
    get_normalizer,
    normalize_skills,
    process_record_skills,
)


# ---------------------------------------------------------------------------
# 1. clean_job_title — bỏ tiền tố địa danh & đuôi quảng cáo lương
# ---------------------------------------------------------------------------

class TestCleanJobTitle:
    def test_prefix_location_tags(self):
        assert clean_job_title("[HN] Backend Java Developer") == "Backend Java Developer"
        assert clean_job_title("[HN][HCM] DevOps Engineer") == "DevOps Engineer"
        assert clean_job_title("(Hà Nội) React Frontend") == "React Frontend"

    def test_salary_suffix_ads(self):
        assert clean_job_title("Python Developer - Lương 20M") == "Python Developer"
        assert clean_job_title("Lap Trinh Vien | Thu nhập cao") == "Lap Trinh Vien"
        assert clean_job_title("Java Senior - Up to 30 triệu") == "Java Senior"

    def test_none_and_empty(self):
        assert clean_job_title(None) is None
        assert clean_job_title("") is None

    def test_emoji_stripped(self):
        assert clean_job_title("IT Support 🔥 🔥 tuyển gấp") == "IT Support tuyển gấp"


# ---------------------------------------------------------------------------
# 2. clean_jd_text — HTML sạch, bullet stitching, control chars (delegate Bước 2)
# ---------------------------------------------------------------------------

class TestCleanJdText:
    def test_strip_html_topdev_style(self):
        raw = '<p style="font-size:14px">Mô tả&nbsp;công việc</p><ul><li>Làm API</li></ul>'
        out = clean_jd_text(raw)
        assert "<" not in out and "font-size" not in out
        assert "Mô tả công việc" in out

    def test_bullet_stitching_vieclam24h_style(self):
        raw = "Có\nkinh nghiệm\nlàm việc\ntối thiểu 1 năm với Python"
        out = clean_jd_text(raw)
        assert "kinh nghiệm làm việc tối thiểu 1 năm với Python" in out.replace("\n", " ")

    def test_emoji_and_control_chars(self):
        raw = "Yêu cầu:\x0b - thành thạo React \U0001F600\u200b"
        out = clean_jd_text(raw)
        assert "\x0b" not in out and "\u200b" not in out and "\U0001F600" not in out
        assert "thành thạo React" in out

    def test_empty_inputs(self):
        assert clean_jd_text(None) is None
        assert clean_jd_text("   ") is None
        assert clean_jd_text([]) is None

    def test_list_input(self):
        out = clean_jd_text(["- Xây dựng web", "- chăm sóc UX"])
        assert "Xây dựng web" in out


# ---------------------------------------------------------------------------
# 3. Địa danh 63 tỉnh thành + cờ is_remote
# ---------------------------------------------------------------------------

class TestCityAndRemote:
    def test_accent_insensitive_real_data_cases(self):
        # 3 ca lỗi đo thật từ integration R2 26/10 (whitelist cũ lọt 17,8%)
        assert normalize_city("Ha Noi") == "Hà Nội"
        assert normalize_city("Ho Chi Minh") == "Hồ Chí Minh"
        assert normalize_city("Tỉnh Hưng Yên") == "Hưng Yên"
        assert normalize_city("Quận Một") == "Hồ Chí Minh"
        assert normalize_city("Long Thành") == "Đồng Nai"
        assert normalize_city("International") == "Quốc tế"
        # Chuỗi đa tỉnh: hub HCM/HN/DN thắng theo priority_hubs
        assert normalize_city("Ha Noi, Ho Chi Minh") == "Hồ Chí Minh"

    def test_district_to_province(self):
        assert normalize_city("Quận 1, TP.HCM") == "Hồ Chí Minh"
        assert normalize_city("Cầu Giấy, Hà Nội") == "Hà Nội"
        assert normalize_city("VSIP, Dĩ An") == "Hồ Chí Minh"  # NQ60/2025: Bình Dương sát nhập vào HCM từ 1/7/2025
        assert normalize_city("Nha Trang") == "Khánh Hòa"

    def test_number_word_district_vs_named_district(self):
        """TASK 2 (27/10): sửa lỗi logic `_WORD_NUMS` ghan 'Quận <tên riêng bắt
        đầu bằng số>' nhầm sang HCM. Đây là lỗi LÀM SAI DỮ LIỆU phân tích (xuyên
        thành phố), không phải lỗi hiển thị."""
        # T-B1/T-B2/T-B3: quận Hà Nội tên bắt đầu bằng từ-chỉ-số -> phải là Hà Nội
        assert normalize_city("Quận Ba Đình") == "Hà Nội"
        assert normalize_city("Quận Nam Từ Liêm") == "Hà Nội"
        assert normalize_city("Quận Bắc Từ Liêm") == "Hà Nội"
        # T-B4: quận đánh số (dạng số) của HCM -> giữ đúng
        assert normalize_city("Quận 3") == "Hồ Chí Minh"
        # T-B5: 'Quận Ba' = Quận 3 (HCM) khi từ số đứng CUỐI chuỗi -> alias hợp lệ
        assert normalize_city("Quận Ba") == "Hồ Chí Minh"
        assert normalize_city("Quận Bảy") == "Hồ Chí Minh"

    def test_multilocation_precedence(self):
        """HANH VI THAT (ghi nhan, khong doi luat — TASK 2 dong 130): chuoi nhieu
        dia danh -> luot 'alias dai nhat khop toan chuoi' thang truoc, priority_hubs
        chi dung khi KHONG alias nao khop. Day la diem can nhom quyet (xem report P-")."""
        # 'ho chi minh'(dai hon) thang 'ha noi'  -> khong phai do hub, ma do do dai alias
        assert normalize_city("Hà Nội và Hồ Chí Minh") == "Hồ Chí Minh"
        # ca hai cung ve mot don vi (Quang Nam sat nhap vao DN) -> DN
        assert normalize_city("làm việc tại Đà Nẵng, Quảng Nam") == "Đà Nẵng"
        # 'bac ninh'(8) dai hon 'ha noi'(6) -> ket qua BAC NINH, khong phai hub HN
        assert normalize_city("Hà Nội và Bắc Ninh") == "Bắc Ninh"

    def test_remote_and_tinh(self):
        assert normalize_city("Làm việc từ xa (Remote)") == "Remote"
        assert normalize_city("Toàn quốc") == "Toàn quốc"
        assert normalize_city(None) == "Không xác định"

    def test_preserve_unknown_label(self):
        # Ranh giới: không được xóa nhãn gốc của sàn khi không khớp từ điển
        assert normalize_city("Someowhere City") == "Someowhere City"

    def test_detect_remote_flag(self):
        # S-5 (26/10): "Toàn quốc" KHÔNG còn là remote — địa bàn rộng ≠ làm từ xa
        assert detect_remote("Toàn quốc") == 0
        assert detect_remote("Toàn quốc", None, "được phép làm việc remote 2 ngày/tuần") == 1
        assert detect_remote(None, "Hybrid/Remote", None) == 1
        assert detect_remote("Hà Nội", "Onsite", "làm việc tại văn phòng 5 ngày") == 0

    def test_normalize_work_locations_dicts(self):
        locs = [{"name": "Quận 7, HCM"}, "Hà Nội", {"city": "Đà Nẵng"}, "Quận 1, TP.HCM"]
        assert normalize_work_locations(locs) == ["Hồ Chí Minh", "Hà Nội", "Đà Nẵng"]


# ---------------------------------------------------------------------------
# 4. Taxonomy: 12 Job Family + 6 Seniority
# ---------------------------------------------------------------------------

class TestJobFamily:
    @pytest.mark.parametrize("title,expected", [
        ("Senior Backend Java Developer", "JF01_BACKEND"),
        ("ReactJS Frontend Developer", "JF02_FRONTEND"),
        ("Fullstack Node.js Developer", "JF03_FULLSTACK"),
        ("Flutter Mobile Developer", "JF04_MOBILE"),
        ("DevOps Engineer", "JF05_DEVOPS"),
        ("Data Engineer (Spark, Kafka)", "JF06_DATA_ENG"),
        ("Data Scientist / ML Engineer", "JF07_DATA_AI"),
        ("QA Automation Engineer", "JF08_QA_QC"),
        ("Cyber Security Specialist", "JF09_SECURITY"),
        ("IT Business Analyst", "JF10_PROD_BA"),
        ("UI/UX Designer", "JF11_UI_UX"),
        ("Embedded Firmware Engineer", "JF12_EMBEDDED"),
        ("Giáo viên tiếng Anh", "JF00_OTHER_IT"),
    ])
    def test_classification(self, title, expected):
        assert classify_job_family(title) == expected

    def test_javascript_not_hijacked_by_java(self):
        assert classify_job_family("JavaScript Developer") == "JF02_FRONTEND"

    def test_every_input_always_mapped(self):
        # DoD: 100% tiêu đề rơi vào 1 trong 12 family hoặc cờ Other IT
        for t in ["", None, "???@", "Nhân viên gò hàn"]:
            assert classify_job_family(t) in JOB_FAMILIES

    def test_skills_assist_generic_title(self):
        assert classify_job_family("Software Engineer", ["React", "Next.js"]) == "JF02_FRONTEND"


class TestSeniority:
    def test_six_standard_codes(self):
        assert SENIORITY_LEVELS == ["INTERN", "FRESHER", "JUNIOR", "MIDDLE", "SENIOR", "LEAD_MGR"]

    @pytest.mark.parametrize("declared,title,expected", [
        ("Thực tập sinh", "", "INTERN"),
        ("Không yêu cầu kinh nghiệm", "Lap trinh vien", "FRESHER"),
        ("Junior", "Java Dev", "JUNIOR"),
        ("Chuyên viên", "Backend Dev", "MIDDLE"),
        ("Senior", "Senior Data Engineer", "SENIOR"),
        ("Trưởng nhóm", "Team Lead", "LEAD_MGR"),
    ])
    def test_mapping(self, declared, title, expected):
        assert standardized_seniority(declared, title) == expected

    def test_experience_inference_fallback(self):
        assert standardized_seniority("", "Backend Developer", "5 năm kinh nghiệm") == "SENIOR"
        assert standardized_seniority("", "Backend Developer", "1 năm") == "JUNIOR"
        assert standardized_seniority("", "Backend Developer", None) == "UNKNOWN"


# ---------------------------------------------------------------------------
# 5. Skill Normalizer ESCO (SD3)
# ---------------------------------------------------------------------------

class TestSkillNormalizer:
    @pytest.fixture(scope="class")
    def norm(self):
        return SkillNormalizer()

    def test_alias_variants_collapse(self, norm):
        # DoD: không còn trùng do hoa/thường/ký tự dấu chấm
        out = norm.normalize_list(["ReactJS", "React.js", "REACT JS", "react"])
        assert out["skills_standardized"] == ["React"]

    def test_required_renames(self, norm):
        assert norm.normalize_list(["VueJS"])["skills_standardized"] == ["Vue.js"]
        assert norm.normalize_list(["Golang"])["skills_standardized"] == ["Go"]
        assert norm.normalize_list(["NodeJS"])["skills_standardized"] == ["Node.js"]

    def test_javascript_vs_java(self, norm):
        out = norm.normalize_list(["JavaScript", "Java", "TypeScript"])
        assert set(out["skills_standardized"]) == {"JavaScript", "Java", "TypeScript"}

    def test_three_groups(self, norm):
        out = norm.normalize_list(["Python", "Điện toán đám mây", "Kỹ năng làm việc nhóm"])
        assert "Python" in out["hard_skills"]
        assert "Cloud Computing" in out["domain_knowledge"]
        assert "Teamwork" in out["soft_skills"]

    def test_blacklist_noise_removed(self, norm):
        out = norm.normalize_list(["đi làm ngay", "quyền lợi", "Lương cứng", "Kubernetes"])
        assert out["skills_standardized"] == ["Kubernetes"]

    def test_multi_skill_tag_not_torn(self, norm):
        # "C/C++" và "UI/UX" là single ESCO skills — cấm xé đôi
        assert norm.normalize_list(["C/C++"])["skills_standardized"] == ["C++"]
        assert norm.normalize_list(["UI/UX"])["skills_standardized"] == ["UI/UX"]

    def test_multi_skill_tag_split(self, norm):
        out = norm.normalize_list(["Java/Spring Boot"])
        assert "Java" in out["skills_standardized"]
        assert "Spring Boot" in out["skills_standardized"]

    def test_typo_fuzzy_matched(self, norm):
        out = norm.normalize_list(["Reactj"])
        assert out["skills_standardized"] == ["React"]

    def test_unmatched_kept_with_flag(self, norm):
        # Tầng 3: kỹ năng thật ngoài từ điển phải ĐƯỢC GIỮ (ranh giới cấm mất nhãn gốc)
        out = norm.normalize_list(["Zephirrt"])
        assert out["skills_unmatched"] == ["Zephirrt"]
        assert out["esco_coverage_rate"] == 0.0

    def test_vi_phrase_not_fuzzy_hijacked(self, norm):
        out = norm.normalize_list(["Truyền thông nội bộ"])
        assert "Communication" not in out["skills_standardized"]

    def test_empty_and_none(self, norm):
        out = norm.normalize_list(None)
        assert out["skills_standardized"] == [] and out["esco_coverage_rate"] == 0.0


# ---------------------------------------------------------------------------
# 5b. Skill Extractor — boundary-aware JD scan (S-3, implemented-pending-review)
# ---------------------------------------------------------------------------

class TestSkillExtractor:
    def test_multi_skill_sentence_scan(self):
        from preprocessing.normalization.skill_extractor import extract_skills_from_text
        got = set(extract_skills_from_text("ReactJS và Node.js, biết Docker là lợi thế"))
        assert got == {"React", "Node.js", "Docker"}

    def test_slash_joined_tokens(self):
        from preprocessing.normalization.skill_extractor import extract_skills_from_text
        got = set(extract_skills_from_text("Thành thạo PHP/MySQL, Laravel"))
        assert got == {"PHP", "MySQL", "Laravel"}

    def test_spaced_variant_javascript_not_java(self):
        from preprocessing.normalization.skill_extractor import extract_skills_from_text
        got = set(extract_skills_from_text("java script và TypeScript cho web app"))
        assert got == {"JavaScript", "TypeScript"}

    def test_longest_alias_wins_no_substring_fp(self):
        from preprocessing.normalization.skill_extractor import extract_skills_from_text
        # 'GitLab CI' phai nuot 'Git'; 'chăm sóc' KHONG duoc tinh là SIEM
        assert set(extract_skills_from_text("Dùng GitLab CI cho pipeline")) == {"CI/CD"}
        assert "SIEM" not in extract_skills_from_text("chăm sóc khách hàng tận tâm")
        assert "ERP" not in extract_skills_from_text("sắp xếp lịch giao hàng")

    def test_short_aliases_never_scan(self):
        from preprocessing.normalization.skill_extractor import extract_skills_from_text
        # 'go' (2 ky tu) bi cam scan text -> khong mo tin 'Go' tu chu tieu thuong
        assert "Go" not in extract_skills_from_text("we go to office daily")

    def test_augment_record_only_when_sparse(self):
        from preprocessing.normalization.skill_extractor import augment_record
        rich = {"skills_standardized": ["Python", "Django", "MySQL"], "jd_clean_text": "..."}
        out = augment_record(dict(rich))
        assert out["skills_standardized"] == rich["skills_standardized"]
        assert out["skills_source"] == "tags"

        poor = {"skills_standardized": [], "hard_skills": [], "domain_knowledge": [],
                "soft_skills": [], "jd_clean_text": "Yêu cầu: thành thạo Excel và PowerPoint",
                "requirements_clean_text": "", "benefits_list": []}
        out2 = augment_record(poor)
        assert "Office Software" in out2["skills_standardized"]
        assert out2["skills_source"] == "jd_scan"
        assert out2["skills_extracted_from_jd"] == ["Office Software"]


# ---------------------------------------------------------------------------
# 6. process_record_text — integration cấp bản ghi phẳng (giữ cột gốc)
# ---------------------------------------------------------------------------

class TestProcessRecord:
    def test_generates_new_columns_without_touching_originals(self):
        flat = {
            "job_title": "[HN] Senior Python Developer - Lương 40M",
            "raw_description_text": "<p>Xây dựng API</p><p>bằng Python</p>",
            "raw_requirements_text": "- 3 năm kinh nghiệm",
            "raw_location_text": "Cầu Giấy, HN",
            "raw_work_mode": "Hybrid",
            "raw_seniority_text": "Senior",
            "raw_experience_text": "3 năm",
            "skills_list": ["Python", "Django", "đi làm ngay"],
        }
        original_title = flat["job_title"]
        out = process_record_text(flat)

        assert out["job_title"] == original_title          # CẤM ghi đè nhãn gốc
        assert out["job_title_clean"] == "Senior Python Developer"
        assert "<p>" not in (out["jd_clean_text"] or "")
        assert out["primary_city"] == "Hà Nội"
        assert out["standardized_job_family"] == "JF01_BACKEND"
        assert out["standardized_seniority"] == "SENIOR"

        out = process_record_skills(out)
        assert out["skills_standardized"] == ["Python", "Django"]  # tag rác bị loại


# ---------------------------------------------------------------------------
# 7. Smoke test dữ liệu THẬT (VietnamWorks raw batch trong repo, bỏ qua nếu thiếu)
# ---------------------------------------------------------------------------

class TestRealDataSmoke:
    RAW = ROOT / "data" / "vietnamworks" / "raw" / "2026-10-16" / "raw_batch.json"

    def test_flatten_then_normalize_real_records(self):
        if not self.RAW.exists():
            pytest.skip("Chưa có raw data thật trong repo (9,390 files nằm trên R2)")
        from preprocessing.integration.json_flattener import flatten_raw_job_record

        records = json.loads(self.RAW.read_text(encoding="utf-8"))
        if isinstance(records, dict):
            records = records.get("records") or [records]
        assert records, "raw_batch.json rỗng"

        normalized = 0
        for rec in records[:50]:
            flat = flatten_raw_job_record(rec, source_fallback="vietnamworks")
            flat = process_record_text(flat)
            flat = process_record_skills(flat)

            # DoD: mọi bản ghi đều có family (khớp hoặc cờ Other IT)
            assert flat["standardized_job_family"] in JOB_FAMILIES
            # Nhãn gốc không bị mất
            assert flat["job_title"] is None or "job_title" in flat
            normalized += 1

        assert normalized > 0
