# -*- coding: utf-8 -*-
"""preprocessing.normalization.text_cleaner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Chuẩn hóa văn bản, địa danh và cấp bậc nghề nghiệp (Seniority).
"""

from __future__ import annotations

import re
from typing import Optional


def clean_job_title(title: Optional[str]) -> Optional[str]:
    """Làm sạch tiêu đề công việc (bỏ các tag tiền tố [HN], [HCM], ký tự thừa)."""
    if not title:
        return None

    s = str(title).strip()
    # Bỏ các tag địa danh trong ngoặc vuông đầu dòng: [HN], [HCM], [Hà Nội], [SG]
    s = re.sub(r"^\[(?:hn|hcm|hà nội|hồ chí minh|toàn quốc|sg|đn|dn)[\w\s/,|–-]*\]\s*", "", s, flags=re.IGNORECASE)
    # Bỏ thông tin mức lương chèn ở đuôi tiêu đề: Lương 20-25M, Thu nhập 15tr
    s = re.sub(r"[-–|]\s*(?:lương|thu nhập|upto|up to)\s*[\d\s.,Mmtrđ-]+$", "", s, flags=re.IGNORECASE)
    return s.strip() or title


def normalize_city(location_text: Optional[str]) -> str:
    """Chuẩn hóa chuỗi địa điểm về tên tỉnh/thành phố chuẩn (hoặc Remote)."""
    if not location_text:
        return "Không xác định"

    s = str(location_text).lower()

    if any(k in s for k in ["hồ chí minh", "hcm", "tp.hcm", "sài gòn", "quận 1", "bình thạnh", "tân bình"]):
        return "Hồ Chí Minh"
    if any(k in s for k in ["hà nội", "hn", "cầu giấy", "ba đình", "nam từ liêm", "đống đa"]):
        return "Hà Nội"
    if any(k in s for k in ["đà nẵng", "dn", "ngũ hành sơn"]):
        return "Đà Nẵng"
    if any(k in s for k in ["bình dương", "dĩ an", "thủ dầu một"]):
        return "Bình Dương"
    if any(k in s for k in ["đồng nai", "biên hòa"]):
        return "Đồng Nai"
    if any(k in s for k in ["hải phòng"]):
        return "Hải Phòng"
    if any(k in s for k in ["cần thơ"]):
        return "Cần Thơ"
    if any(k in s for k in ["remote", "từ xa", "toàn quốc", "online"]):
        return "Remote"

    return location_text.strip()


def normalize_seniority(seniority_text: Optional[str], title_text: Optional[str] = "") -> str:
    """Chuẩn hóa cấp bậc nghề nghiệp về 6 bậc chuẩn:

    Intern, Fresher, Junior, Middle, Senior, Lead/Manager.
    """
    combined = f"{seniority_text or ''} {title_text or ''}".lower()

    if any(k in combined for k in ["intern", "thực tập", "sinh viên", "trainee"]):
        return "Intern"
    if any(k in combined for k in ["fresher", "mới tốt nghiệp"]):
        return "Fresher"
    if any(k in combined for k in ["junior", "dưới 2 năm"]):
        return "Junior"
    if any(k in combined for k in ["lead", "trưởng nhóm", "manager", "quản lý", "giám đốc", "director", "head", "cto"]):
        return "Lead/Manager"
    if any(k in combined for k in ["senior", "chuyên viên cao cấp", "trên 4 năm"]):
        return "Senior"
    if any(k in combined for k in ["middle", "mid", "nhân viên", "chuyên viên"]):
        return "Middle"

    return "Chưa xác định"


def classify_job_family(title: Optional[str], skills_list: Optional[list] = None) -> str:
    """Phân loại chức danh công việc về 12 Job Family chuẩn ngành IT Việt Nam (SD2)."""
    text = f"{title or ''} {' '.join(skills_list or [])}".lower()

    if any(k in text for k in ["tester", "qa", "qc", "quality assurance", "automation test", "manual test", "kiểm thử", "selenium", "playwright"]):
        return "JF08_QA_QC"
    if any(k in text for k in ["mobile", "flutter", "react native", "ios", "android", "swift", "kotlin"]):
        return "JF04_MOBILE"
    if any(k in text for k in ["devops", "cloud", "sre", "sysadmin", "infrastructure", "hạ tầng", "kubernetes", "docker", "aws", "azure", "gcp", "linux", "system admin"]):
        return "JF05_DEVOPS"
    if any(k in text for k in ["data engineer", "big data", "etl", "data warehouse", "dwh", "spark", "kafka", "airflow", "hadoop", "kỹ sư dữ liệu"]):
        return "JF06_DATA_ENG"
    if any(k in text for k in ["data scientist", "data science", "machine learning", "ai engineer", "deep learning", "nlp", "computer vision", "trí tuệ nhân tạo", "khoa học dữ liệu", "data analyst", "phân tích dữ liệu"]):
        return "JF07_DATA_AI"
    if any(k in text for k in ["security", "soc", "pentest", "cyber", "an ninh mạng", "bảo mật", "infosec", "siem"]):
        return "JF09_SECURITY"
    if any(k in text for k in ["product manager", "product owner", "po", "business analyst", "ba", "quản lý sản phẩm", "scrum master", "chuyên viên phân tích nghiệp vụ"]):
        return "JF10_PROD_BA"
    if any(k in text for k in ["ui/ux", "ui ux", "designer", "thiết kế", "figma", "adobe xd", "user experience", "giao diện"]):
        return "JF11_UI_UX"
    if any(k in text for k in ["embedded", "iot", "firmware", "phần cứng", "nhúng", "vi điều khiển", "c/c++", "rtos", "plc", "tự động hóa", "robot"]):
        return "JF12_EMBEDDED"
    if any(k in text for k in ["fullstack", "full-stack", "full stack", "web developer"]):
        return "JF03_FULLSTACK"
    if any(k in text for k in ["frontend", "front-end", "front end", "react", "vue", "angular", "nextjs", "next.js", "html", "css", "ui developer"]):
        return "JF02_FRONTEND"
    if any(k in text for k in ["backend", "back-end", "back end", "java", "spring", "node", "nodejs", "python", "golang", "go", "php", ".net", "c#", "django", "fastapi", "laravel", "ruby", "rails", "c++", "developer", "lập trình viên", "software engineer", "kỹ sư phần mềm"]):
        return "JF01_BACKEND"

    return "JF00_OTHER_IT"
