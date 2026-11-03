# -*- coding: utf-8 -*-
"""Luật từ khóa phân loại tin IT (P1 C4a). Khớp theo từ nguyên vẹn, không theo chuỗi con (PRE-1).

Kết quả chỉ là một nửa của it_status; nửa kia là JEV (preprocessing/common/jev_client.py).
Không tự bỏ tin: quyết bỏ nằm ở preprocessing/clean/it_policy.json do người dùng duyệt.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

# Khớp trên chữ thường có dấu (NFC): "ít" (tiếng Việt) không bị nhận là "IT".
STRONG_IT = [
    "it", "cntt", "công nghệ thông tin", "developer", "dev", "lập trình", "lap trinh", "programmer", "software",
    "phần mềm", "phan mem", "data", "dữ liệu", "tester", "qa", "qc", "devops", "sre", "cloud", "backend", "back-end",
    "frontend", "front-end", "fullstack", "full-stack", "full stack", "mobile", "android", "ios", "web", "ai",
    "machine learning", "ml", "deep learning", "game", "unity", "product owner", "business analyst", "ba", "scrum",
    "erp", "sap", "odoo", "database", "dba", "ui/ux", "ux", "ui", "automation test", "embedded", "blockchain",
    "python", "java", "javascript", "typescript", ".net", "dotnet", "php", "react", "reactjs", "angular", "vue",
    "node", "nodejs", "golang", "c++", "c#", "kotlin", "flutter", "swift", "helpdesk", "it support", "cyber security",
    "phân tích nghiệp vụ", "hệ thống thông tin", "phát triển ứng dụng", "kiến trúc hệ thống", "mis",
    "ngân hàng lõi", "core banking", "kỹ sư giải pháp", "solution engineer", "bảo mật", "an ninh mạng", "network", "quản trị mạng", "quản trị hệ thống", "system admin", "sysadmin",
    "solution architect", "tech lead", "technical lead", "cto", "kỹ sư phần mềm", "salesforce", "crm developer",
]
# Từ như "kỹ thuật", "engineer", "security" cố ý không có ở đây: một mình không đủ kết luận
# ("Kỹ thuật bảo trì nhà máy", "Security (Nhân viên bảo an)"), nên ra unknown để JEV và người quyết.
NON_IT = [
    "kế toán", "ke toan", "accountant", "accounting", "kiểm toán", "tài xế", "lái xe", "driver", "giáo viên",
    "giảng viên", "giảng dạy", "teacher", "gia sư", "nhân sự", "hr", "tuyển dụng", "recruiter", "marketing",
    "bán hàng", "ban hang", "sales", "kinh doanh", "telesales", "tuyển sinh", "giao hàng", "shipper", "hành chính",
    "logistics", "xuất nhập khẩu", "thu ngân", "chăm sóc khách hàng", "cskh", "lễ tân", "bảo vệ", "bảo an", "tạp vụ",
    "phục vụ", "đầu bếp", "bếp", "thủ kho", "kho", "kỹ sư xây dựng", "công trình", "cơ khí", "điện công nghiệp", "điện lạnh", "may mặc",
    "dược", "y tá", "điều dưỡng", "bác sĩ", "luật", "pháp chế", "thư ký", "trợ lý giám đốc", "content writer", "content creator",
    "sáng tạo nội dung", "seo",
    "thiết kế đồ họa", "graphic designer", "kiến trúc sư", "nội thất", "bất động sản", "bảo hiểm",
    "giao dịch viên", "tư vấn khách hàng", "tín dụng", "thu mua", "purchasing", "sản xuất", "công nhân", "vận hành máy", "nhà hàng", "khách sạn",
]
# Kỹ năng công nghệ: từ MIN_TECH_SKILLS kỹ năng trở lên mới tính là IT (chuyên gia định phí cũng dùng SQL).
# shortcut: danh sách ngắn viết tay; P3 thay bằng preprocessing/dictionaries/skills.json
MIN_TECH_SKILLS = 2
TECH_SKILLS = {
    "python", "java", "javascript", "typescript", "sql", "mysql", "postgresql", "mongodb", "redis", "react", "reactjs",
    "angular", "vue", "vuejs", "nodejs", "node.js", "php", "laravel", "golang", "go", "c#", ".net", "c++", "kotlin",
    "swift", "flutter", "android", "ios", "docker", "kubernetes", "aws", "azure", "gcp", "linux", "git", "devops",
    "spring", "spring boot", "django", "html", "css", "machine learning", "ai", "data analysis", "power bi", "tableau",
    "tester", "testing", "selenium", "automation test", "qa", "qc", "sap", "erp", "odoo", "blockchain", "unity",
    "network", "security", "cloud", "microservices", "rest api", "api", "big data", "spark", "hadoop", "etl",
}


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(text or "")).lower()).strip()


def _pattern(words: Iterable[str]) -> re.Pattern:
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<![\w+#]){'(?:' + alts + ')'}(?![\w+#])")


_STRONG, _NON = _pattern(STRONG_IT), _pattern(NON_IT)


def classify(title: Any, skills: Any = None) -> str:
    """it | non_it | unknown."""
    t = _norm(title)
    tech = {_norm(s) for s in (skills or []) if isinstance(s, str)} & TECH_SKILLS
    strong, non = bool(_STRONG.search(t)), bool(_NON.search(t))
    if strong and non:
        return "unknown"  # "Kinh doanh phần mềm", "IT Recruiter": để người và JEV quyết
    if strong:
        return "it"
    if non:
        return "non_it"
    if len(tech) >= MIN_TECH_SKILLS:
        return "it"
    return "unknown"  # chỉ có từ yếu hoặc không có gì: can_kiem
