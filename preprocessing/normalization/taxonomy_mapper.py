# -*- coding: utf-8 -*-
"""preprocessing.normalization.taxonomy_mapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Chuẩn hóa chức danh về 12 Job Family chuẩn ngành IT Việt Nam (SD2) và
cấp bậc nghề nghiệp về 6 bậc chuẩn (Intern -> Lead/Manager).

Đầu vào : Cột chuỗi thô từ Staging (`job_title`, `raw_seniority_text`,
          `raw_experience_text`, `skills_list`).
Đầu ra  : `standardized_job_family` (mã JF00-JF12), `standardized_seniority`
          (INTERN/FRESHER/JUNIOR/MIDDLE/SENIOR/LEAD_MGR/UNKNOWN).

Ranh giới (Ironclad Boundaries — docs/preprocessing/normalization/04):
  - CẤM ghi đè nhãn gốc: mọi hàm chỉ SINH cột mới, không sửa cột input.
  - 100% tiêu đề phải rơi vào 1 trong 12 Job Family hoặc cờ `JF00_OTHER_IT`.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# 1. TAXONOMY 12 JOB FAMILY CHUẨN (SD2) — docs/preprocessing/normalization/04 §3
# ---------------------------------------------------------------------------

JOB_FAMILIES: Dict[str, str] = {
    "JF01_BACKEND": "Backend Development",
    "JF02_FRONTEND": "Frontend Development",
    "JF03_FULLSTACK": "Fullstack Development",
    "JF04_MOBILE": "Mobile App Development",
    "JF05_DEVOPS": "DevOps / Cloud / SRE / SysAdmin",
    "JF06_DATA_ENG": "Data Engineering & Big Data",
    "JF07_DATA_AI": "Data Science / AI / Machine Learning",
    "JF08_QA_QC": "Software QA / QC / Automation Test",
    "JF09_SECURITY": "Cyber Security / InfoSec",
    "JF10_PROD_BA": "Product Management / Business Analyst",
    "JF11_UI_UX": "UI/UX Design",
    "JF12_EMBEDDED": "Embedded Systems / IoT / Hardware",
    "JF00_OTHER_IT": "Other IT (chưa ánh xạ)",
}

# Thứ tự cascade quyết định: từ đặc thù hẹp -> rộng dần (tránh "Java" cướp
# "JavaScript", "ios" cướp "vision", ...). Từ khớp theo token boundary.
_JF_CASCADE: List[tuple] = [
    ("JF09_SECURITY", [
        "security engineer", "cyber security", "cybersecurity", "infosec", "pentest",
        "penetration test", "soc analyst", "security operations", "an ninh mạng",
        "bảo mật thông tin", "information security", "siem", "malware analyst",
    ]),
    ("JF11_UI_UX", [
        "ui/ux", "ui ux", "ux designer", "ui designer", "thiết kế giao diện",
        "product designer", "ux/ui", "figma", "wireframe", "giao diện người dùng",
    ]),
    ("JF12_EMBEDDED", [
        "embedded", "firmware", "iot engineer", "internet of things", "nhúng",
        "vi điều khiển", "microcontroller", "rtos", "plc", "scada", "tự động hóa",
        "hardware", "vũ khí", "electronics engineer", "cơ điện tử",
        "rf engineer", "transmission engineer", "optical", "physical design",
        "asic", "vlsi", "pcb", "npi engineer", "verification engineer",
    ]),
    ("JF08_QA_QC", [
        "tester", "test engineer", "qa", "qc", "quality assurance", "quality control",
        "automation test", "test automation", "manual test", "kiểm thử", "sqa",
        "selenium", "playwright", "postman", "quản lý chất lượng",
    ]),
    ("JF04_MOBILE", [
        "mobile developer", "mobile app", "app developer", "flutter", "react native",
        "ios developer", "android developer", "lập trình di động", "swift", "kotlin",
        "android/ios", "ios/android", "developer mobile",
    ]),
    ("JF05_DEVOPS", [
        "devops", "sre", "site reliability", "cloud engineer", "infrastructure",
        "sysadmin", "system administrator", "network administrator", "quản trị mạng",
        "hạ tầng", "kubernetes", "docker", "terraform", "hệ thống", "it support",
        "it helpdesk", "it operator", "network engineer",
    ]),
    ("JF07_DATA_AI", [
        "data scientist", "data science", "machine learning", "ml engineer",
        "ai engineer", "artificial intelligence", "deep learning", "nlp",
        "computer vision", "data analyst", "business intelligence", "bi analyst",
        "khoa học dữ liệu", "trí tuệ nhân tạo", "phân tích dữ liệu",
        "llm", "genai",
    ]),
    ("JF06_DATA_ENG", [
        "data engineer", "big data", "etl", "elt", "data warehouse", "dwh", "spark",
        "kafka", "airflow", "hadoop", "kỹ sư dữ liệu", "data pipeline", "lakehouse",
        "databricks", "quản trị dữ liệu", "database administrator", "dba",
    ]),
    ("JF10_PROD_BA", [
        "product manager", "product owner", "business analyst", "ba", "pm",
        "scrum master", "project manager", "quản lý sản phẩm", "project leader",
        "chuyên viên phân tích nghiệp vụ", "it business", "product owner",
        "presales", "pre-sales", "solution engineer", "solution consultant",
        "it manager", "trưởng phòng it", "head of it", "it director",
    ]),
    ("JF03_FULLSTACK", [
        "fullstack", "full-stack", "full stack", "web developer", "lập trình web",
        "mern", "mevn", "web programer",
    ]),
    ("JF02_FRONTEND", [
        "frontend", "front-end", "front end", "react", "vue", "angular", "nextjs",
        "next.js", "html", "css", "ui developer", "javascript developer",
        "trình duyệt web", "web designer",
    ]),
    ("JF01_BACKEND", [
        "backend", "back-end", "back end", "java", "spring", "node", "nodejs",
        "python", "golang", "go developer", "php", ".net", "c#", "c++", "django",
        "fastapi", "laravel", "ruby", "rails", "api developer", "core java",
        "software engineer", "lập trình viên", "kỹ sư phần mềm", "programmer",
        "developer", "engineer it", "it engineer",
    ]),
]

_JF_WORD = re.compile(r"[^\w+#./-]+", re.UNICODE)


def _kw_hit(keyword: str, text: str) -> bool:
    """Khớp keyword theo RANH GIỚI TỪ (\b) — chặn 'java' khớp trong 'javascript',
    'ba' khớp trong 'database', 'go' khớp trong 'logo'."""
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) is not None


def _tokenize_for_family(text: Optional[str]) -> str:
    """Chuẩn hóa chuỗi so khớp: bỏ dấu nặng nhẹ khoảng trắng, giữ token . / + #."""
    if not text:
        return ""
    return _JF_WORD.sub(" ", str(text).lower()).strip()


def classify_job_family(title: Optional[str], skills_list: Optional[list] = None) -> str:
    """Phân loại chức danh về 12 Job Family chuẩn ngành IT Việt Nam (SD2).

    Args:
        title: Tiêu đề công việc thô (`job_title`).
        skills_list: Mảng kỹ năng hỗ trợ phân loại khi tiêu đề chung chung.

    Returns:
        Mã JF (ví dụ ``"JF01_BACKEND"``). 100% đầu vào luôn trả về một mã;
        không ánh xạ được thì gắn cờ ``"JF00_OTHER_IT"`` theo DoD §6.3.3.
    """
    # Tiêu đề được ưu tiên gấp 3 lần kỹ năng khi xét độ phủ từ khóa
    head = _tokenize_for_family(title)
    tail = _tokenize_for_family(" ".join(str(s) for s in skills_list or []))
    text = f"{head} {head} {tail}"

    for code, keywords in _JF_CASCADE:
        for kw in keywords:
            if _kw_hit(kw, text):
                return code
    return "JF00_OTHER_IT"


def job_family_name(code: str) -> str:
    """Tra tên tiếng Anh chuẩn của một mã Job Family."""
    return JOB_FAMILIES.get(code, JOB_FAMILIES["JF00_OTHER_IT"])


# ---------------------------------------------------------------------------
# 2. CHUẨN HÓA 6 BẬC SENIORITY — docs/preprocessing/normalization/04 §4
# ---------------------------------------------------------------------------

SENIORITY_LEVELS: List[str] = ["INTERN", "FRESHER", "JUNIOR", "MIDDLE", "SENIOR", "LEAD_MGR"]

# Nhãn hiển thị tương thích ngược với text_cleaner.normalize_seniority cũ
# (tests/test_preprocessing_pipeline.py & run_staging_integration_pipeline.py
#  đang assert chuỗi "Intern"/"Lead/Manager"/"Chưa xác định").
_SENIORITY_DISPLAY: Dict[str, str] = {
    "INTERN": "Intern",
    "FRESHER": "Fresher",
    "JUNIOR": "Junior",
    "MIDDLE": "Middle",
    "SENIOR": "Senior",
    "LEAD_MGR": "Lead/Manager",
    "UNKNOWN": "Chưa xác định",
}

_LEAD_MGR_TERMS = [
    "trưởng nhóm", "team lead", "technical lead", "tech lead", "leader",
    "manager", "quản lý", "giám đốc", "director", "head of", "chief", "cto", "cio",
    "trưởng phòng", "trưởng ban", "supervisor", "lead",
]
_SENIOR_TERMS = ["senior", "sr.", "sr ", "chuyên viên cao cấp", "cấp cao", "trên 4 năm", "trên 5 năm", "experienced"]
_INTERN_TERMS = ["intern", "thực tập", "sinh viên", "trainee", "internship", "fresher intern"]
_FRESHER_TERMS = ["fresher", "mới tốt nghiệp", "chưa có kinh nghiệm", "không yêu cầu kinh nghiệm", "dưới 1 năm"]
_JUNIOR_TERMS = ["junior", "jr.", "jr ", "trợ lý", "phó viên", "dưới 2 năm", "1 - 2 năm", "1-2 năm", "hơn 1 năm"]
_MIDDLE_TERMS = ["middle", "mid-level", "mid level", "chuyên viên", "nhân viên", " 2 năm", "2-4 năm", "2 - 4 năm", "hơn 2 năm", "3 năm", "3-4 năm", "3 - 4 năm"]


def map_seniority_code(
    seniority_text: Optional[str],
    title_text: Optional[str] = "",
    experience_text: Optional[str] = None,
) -> str:
    """Ánh xạ cấp bậc về mã chuẩn 6 bậc (INTERN..LEAD_MGR, UNKNOWN).

    Ưu tiên nguồn: `raw_seniority_text` -> `job_title` -> `raw_experience_text`
    (Kinh nghiệm chỉ dùng suy luận bổ trợ khi 2 trường đầu mù thông tin).
    """
    declared = f"{seniority_text or ''}".lower()
    title = f"{title_text or ''}".lower()

    for terms, code in (
        (_INTERN_TERMS, "INTERN"),
        (_LEAD_MGR_TERMS, "LEAD_MGR"),
        (_SENIOR_TERMS, "SENIOR"),
        (_FRESHER_TERMS, "FRESHER"),
        (_JUNIOR_TERMS, "JUNIOR"),
        (_MIDDLE_TERMS, "MIDDLE"),
    ):
        if any(t in declared for t in terms):
            return code

    for terms, code in (
        (_INTERN_TERMS, "INTERN"),
        (_LEAD_MGR_TERMS, "LEAD_MGR"),
        (_SENIOR_TERMS, "SENIOR"),
        (_FRESHER_TERMS, "FRESHER"),
        (_JUNIOR_TERMS, "JUNIOR"),
    ):
        if any(t in title for t in terms):
            return code

    # Suy luận từ chuỗi kinh nghiệm thô (Khoa chưa parse thì tự bóc regex)
    exp = f"{experience_text or ''}".lower()
    years = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:\+)?\s*(?:năm|yrs?|years?)", exp)
    if years:
        val = float(years.group(1).replace(",", "."))
        if val <= 0:
            return "FRESHER"
        if val < 1:
            return "FRESHER"
        if val < 2:
            return "JUNIOR"
        if val < 4:
            return "MIDDLE"
        if val < 7:
            return "SENIOR"
        return "LEAD_MGR"
    if any(t in exp for t in ["không yêu cầu", "chưa kinh nghiệm", "dưới 1"]):
        return "FRESHER"

    return "UNKNOWN"


def normalize_seniority(seniority_text: Optional[str], title_text: Optional[str] = "") -> str:
    """Tương thích ngược: trả nhãn hiển thị cũ (Intern/Middle/.../Chưa xác định)."""
    return _SENIORITY_DISPLAY[map_seniority_code(seniority_text, title_text)]


def standardized_seniority(
    seniority_text: Optional[str],
    title_text: Optional[str] = "",
    experience_text: Optional[str] = None,
) -> str:
    """API mới theo DoD §6.3.3: trả mã uppercase 6 bậc chuẩn hoặc UNKNOWN."""
    return map_seniority_code(seniority_text, title_text, experience_text)
