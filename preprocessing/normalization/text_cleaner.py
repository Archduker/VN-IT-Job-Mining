# -*- coding: utf-8 -*-
"""preprocessing.normalization.text_cleaner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Chuẩn hóa văn bản, cấp bậc (Seniority), nhóm nghề (Job Family) và kỹ năng chuẩn (N1-N4).
Áp dụng cơ chế khớp từ nguyên vẹn (PRE-1) để tránh so khớp chuỗi con.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd

from preprocessing.common import REPO_ROOT

SENIORITY_LABELS = [
    "Thực tập",
    "Mới tốt nghiệp",
    "Junior",
    "Middle",
    "Senior",
    "Trưởng nhóm/Quản lý",
]

JOB_FAMILIES = [
    "Backend",
    "Frontend",
    "Fullstack",
    "Mobile",
    "Data/AI",
    "DevOps/Cloud",
    "Kiểm thử (QA/QC)",
    "Bảo mật",
    "Hệ thống/Mạng",
    "Phân tích nghiệp vụ (BA)",
    "Quản lý sản phẩm/dự án",
    "Thiết kế UI/UX",
]

FAMILY_RULES = [
    (
        "Kiểm thử (QA/QC)",
        ["tester", "qa", "qc", "quality assurance", "automation test", "manual test", "kiểm thử", "test engineer", "test lead", "software testing", "sqa"],
        {"Automation Test", "Unit Test"}
    ),
    (
        "Bảo mật",
        ["security", "soc", "pentest", "cyber", "an ninh mạng", "bảo mật", "infosec", "siem", "cybersecurity", "penetration tester", "appsec", "devsecops"],
        set()
    ),
    (
        "Mobile",
        ["mobile", "flutter", "react native", "ios", "android", "swift", "kotlin"],
        {"Swift", "Kotlin", "Dart"}
    ),
    (
        "DevOps/Cloud",
        ["devops", "cloud", "sre", "sysadmin", "infrastructure", "hạ tầng", "kubernetes", "k8s", "docker", "aws", "azure", "gcp", "linux", "system admin", "ci/cd", "platform engineer", "site reliability"],
        {"Docker", "Kubernetes", "AWS", "Azure", "GCP", "CI/CD", "Linux"}
    ),
    (
        "Data/AI",
        ["data engineer", "big data", "etl", "data warehouse", "dwh", "spark", "kafka", "airflow", "hadoop", "kỹ sư dữ liệu", "data scientist", "data science", "machine learning", "ai engineer", "deep learning", "nlp", "computer vision", "trí tuệ nhân tạo", "khoa học dữ liệu", "data analyst", "phân tích dữ liệu", "bi analyst", "power bi", "tableau", "genai", "llm"],
        {"Machine Learning", "Data Engineering", "Big Data", "Kafka"}
    ),
    (
        "Hệ thống/Mạng",
        ["network engineer", "system engineer", "quản trị mạng", "helpdesk", "it support", "cisco", "mạng máy tính", "it helpdesk", "network admin"],
        set()
    ),
    (
        "Phân tích nghiệp vụ (BA)",
        ["business analyst", "ba", "chuyên viên phân tích nghiệp vụ", "phân tích nghiệp vụ", "business analysis", "functional analyst"],
        set()
    ),
    (
        "Quản lý sản phẩm/dự án",
        ["product manager", "product owner", "po", "project manager", "pm", "quản lý sản phẩm", "quản lý dự án", "scrum master", "delivery manager", "agile coach", "project lead"],
        {"Agile/Scrum"}
    ),
    (
        "Thiết kế UI/UX",
        ["ui/ux", "ui ux", "ui", "ux", "designer", "thiết kế", "figma", "adobe xd", "user experience", "user interface", "giao diện", "product designer", "ux writer"],
        set()
    ),
    (
        "Fullstack",
        ["fullstack", "full-stack", "full stack"],
        set()
    ),
    (
        "Frontend",
        ["frontend", "front-end", "front end", "ui developer", "web frontend"],
        {"React", "Vue", "Angular", "HTML/CSS"}
    ),
    (
        "Backend",
        ["backend", "back-end", "back end", "software engineer", "developer", "lập trình viên", "kỹ sư phần mềm", "web developer", "java", "spring", "spring boot", "node", "nodejs", "python", "golang", "go", "php", ".net", "c#", "django", "fastapi", "laravel", "ruby", "rails", "c++"],
        {"Python", "Java", "Node.js", "C#", "C++", "Golang", "PHP", "Ruby", "SQL", "NoSQL", "GraphQL", "REST API", "Microservices"}
    ),
]


def has_term(text: str, terms: Iterable[str]) -> bool:
    """True nếu text chứa một trong các cụm từ dưới dạng từ nguyên vẹn (cho phép đuôi số nhiều 's').

    Tránh so khớp chuỗi con làm 'ba' khớp trong 'backend' hay 'intern' khớp trong 'international'.
    """
    if not text:
        return False
    return any(re.search(rf"(?<!\w){re.escape(term)}s?(?!\w)", text, re.IGNORECASE) for term in terms)


def clean_job_title(title: Optional[str]) -> Optional[str]:
    """Làm sạch tiêu đề công việc (bỏ các tag tiền tố [HN], [HCM], ký tự thừa)."""
    if not title:
        return None

    s = str(title).strip()
    s = re.sub(r"^\[(?:hn|hcm|hà nội|hồ chí minh|toàn quốc|sg|đn|dn)[\w\s/,|–-]*\]\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[-–|]\s*(?:lương|thu nhập|upto|up to)\s*[\d\s.,Mmtrđ-]+$", "", s, flags=re.IGNORECASE)
    return s.strip() or title


def normalize_city(location_text: Optional[str]) -> str:
    """Hàm tương thích ngược chuẩn hóa chuỗi địa điểm về tên tỉnh/thành phố hoặc Remote."""
    if not location_text:
        return "Không xác định"

    s = str(location_text).lower()
    if has_term(s, ["hồ chí minh", "hcm", "tp.hcm", "sài gòn", "quận 1", "bình thạnh", "tân bình"]):
        return "Hồ Chí Minh"
    if has_term(s, ["hà nội", "hn", "cầu giấy", "ba đình", "nam từ liêm", "đống đa"]):
        return "Hà Nội"
    if has_term(s, ["đà nẵng", "dn", "ngũ hành sơn"]):
        return "Đà Nẵng"
    if has_term(s, ["bình dương", "dĩ an", "thủ dầu một"]):
        return "Bình Dương"
    if has_term(s, ["đồng nai", "biên hòa"]):
        return "Đồng Nai"
    if has_term(s, ["hải phòng"]):
        return "Hải Phòng"
    if has_term(s, ["cần thơ"]):
        return "Cần Thơ"
    if has_term(s, ["remote", "từ xa", "toàn quốc", "online"]):
        return "Remote"

    return location_text.strip()


def classify_seniority(
    raw_seniority: Optional[str] = None,
    title: Optional[str] = None,
    exp_min_years: Optional[float] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Phân loại cấp bậc nghề nghiệp (N2) theo thứ tự ưu tiên:
    1. Luật từ nguyên vẹn trên raw_seniority_text -> source = 'raw'
    2. Luật từ nguyên vẹn trên job_title_clean -> source = 'title'
    3. Phân loại theo số năm kinh nghiệm tối thiểu -> source = 'kinh_nghiem'
    """
    # 1. Tra trên raw_seniority_text
    if raw_seniority and str(raw_seniority).strip():
        s_raw = str(raw_seniority).strip()
        if has_term(s_raw, ["thực tập", "thực tập sinh", "sinh viên", "trainee", "intern", "internship"]):
            return "Thực tập", "raw"
        if has_term(s_raw, ["mới tốt nghiệp", "fresher", "entry level"]):
            return "Mới tốt nghiệp", "raw"
        if has_term(s_raw, ["trưởng nhóm", "trưởng/phó phòng", "trưởng phòng", "phó phòng", "quản lý", "giám sát", "lead", "leader", "manager", "giám đốc", "director", "head", "cto", "tech lead"]):
            return "Trưởng nhóm/Quản lý", "raw"
        if has_term(s_raw, ["senior", "chuyên viên cao cấp", "trên 4 năm", "trên 5 năm"]):
            return "Senior", "raw"
        if has_term(s_raw, ["junior", "dưới 2 năm"]):
            return "Junior", "raw"
        # "Nhân viên"/"Chuyên viên" không nói cấp bậc: để luật tiêu đề và kinh nghiệm quyết
        if has_term(s_raw, ["middle", "mid", "mid-level"]):
            return "Middle", "raw"

    # 2. Tra trên job_title_clean
    if title and str(title).strip():
        s_title = str(title).strip()
        if has_term(s_title, ["intern", "internship", "thực tập", "thực tập sinh", "trainee"]):
            return "Thực tập", "title"
        if has_term(s_title, ["fresher", "mới tốt nghiệp", "entry level"]):
            return "Mới tốt nghiệp", "title"
        # "quản lý" trong tiêu đề thường là tên việc ("Quản Lý Dự Án", "Quản Lý Vận Hành"), không phải cấp bậc
        if has_term(s_title, ["lead", "leader", "tech lead", "team lead", "trưởng nhóm", "manager", "giám đốc", "director", "head of", "cto", "engineering manager", "trưởng phòng", "phó phòng"]):
            return "Trưởng nhóm/Quản lý", "title"
        if has_term(s_title, ["senior", "chuyên viên cao cấp", "sr.", "sr"]):
            return "Senior", "title"
        if has_term(s_title, ["junior", "jr.", "jr"]):
            return "Junior", "title"
        if has_term(s_title, ["middle", "mid-level", "mid level", "mid"]):
            return "Middle", "title"

    # 3. Theo số năm kinh nghiệm
    if exp_min_years is not None and not (isinstance(exp_min_years, float) and pd.isna(exp_min_years)):
        try:
            y = float(exp_min_years)
            if y == 0.0:
                return "Mới tốt nghiệp", "kinh_nghiem"
            elif 1.0 <= y <= 2.0:
                return "Junior", "kinh_nghiem"
            elif 3.0 <= y <= 4.0:
                return "Middle", "kinh_nghiem"
            elif y >= 5.0:
                return "Senior", "kinh_nghiem"
        except (ValueError, TypeError):
            pass

    return None, None


def normalize_seniority(seniority_text: Optional[str], title_text: Optional[str] = "") -> str:
    sen, _ = classify_seniority(seniority_text, title_text)
    return sen or "Chưa rõ"


def classify_job_family_rule(
    title: Optional[str],
    skills_std: Optional[List[str]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Phân loại nhóm nghề N3 theo luật từ nguyên vẹn trên tiêu đề và skills chuẩn.

    Trả về (family, source) hoặc (None, None).
    """
    s_title = str(title or "").strip()
    skills_set = set(skills_std or [])

    # 1. So khớp trên tiêu đề trước (chính xác nhất)
    if s_title:
        for family, terms, _ in FAMILY_RULES:
            if has_term(s_title, terms):
                return family, "title"

    # 2. So khớp phụ qua kỹ năng chuẩn nổi bật
    if skills_set:
        for family, _, fam_skills in FAMILY_RULES:
            if fam_skills and (skills_set & fam_skills):
                return family, "skills"

    return None, None


def classify_job_family(title: Optional[str], skills_list: Optional[list] = None) -> str:
    fam, _ = classify_job_family_rule(title, skills_list)
    return fam or "Khác"


_SKILLS_LOOKUP: Optional[Dict[str, str]] = None


def _get_skills_lookup() -> Dict[str, str]:
    global _SKILLS_LOOKUP
    if _SKILLS_LOOKUP is None:
        dict_path = REPO_ROOT / "preprocessing" / "dictionaries" / "skills.json"
        lookup = {}
        if dict_path.exists():
            data = json.loads(dict_path.read_text(encoding="utf-8"))
            for canon, variants in data.items():
                lookup[canon.lower()] = canon
                for v in variants:
                    lookup[v.lower()] = canon
        _SKILLS_LOOKUP = lookup
    return _SKILLS_LOOKUP


def canonicalize_skills(skills: Any) -> List[str]:
    """N4: Ánh xạ kỹ năng về tên chuẩn theo skills.json và loại bỏ trùng lặp."""
    if skills is None:
        return []
    if isinstance(skills, (list, tuple)):
        items = skills
    elif hasattr(skills, "tolist"):
        items = skills.tolist()
    else:
        return []

    lookup = _get_skills_lookup()
    seen: Set[str] = set()
    result: List[str] = []

    for s in items:
        if not s:
            continue
        s_clean = str(s).strip()
        canon = lookup.get(s_clean.lower(), s_clean)
        if canon.lower() not in seen:
            seen.add(canon.lower())
            result.append(canon)

    return result
