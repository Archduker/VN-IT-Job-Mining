"""Giai đoạn A của khử trùng đa sàn: Blocking Key Partitioning (docs/spec/05_preprocessing_spec.md mục 3.2.A).

    Blocking_Key = Slug(Company_Norm) + "_" + Location_Code + "_" + Title_Group

Mục đích: giảm không gian so sánh từ O(N^2) (~12,9 triệu cặp trên 5.077 tin) xuống chỉ còn
vài nghìn cặp trong cùng block, đúng như đặc tả yêu cầu.

Dùng lại `normalize_company_name` của bước 04 (đã được 01 Clean mượn tương tự) rồi bóc thêm
các hậu tố nghề nghiệp "Software", "Technology", "Solutions", "Services" mà danh sách cũ chưa phủ.
"""

from __future__ import annotations

import re

from preprocessing.common import province
from preprocessing.deduplication.text_norm import clean_text, fold
from preprocessing.normalization.cross_deduplicator import normalize_company_name

# Hậu tố pháp lý/ngành nghề đặc thù IT chưa có trong normalize_company_name (bước 04)
EXTRA_LEGAL = re.compile(
    r"\b(software(?:s)?|technologies|technology|tech|solutions|services|system(?:s)?|"
    r"consulting|international|tnhh(?: mtv)?|trach nhiem huu han)\b",
    re.IGNORECASE,
)

# Nhóm chức danh: thụt đầu theo mức đặc thù, mỗi nhóm là các từ khóa đã bỏ dấu (fold)
TITLE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fullstack", ("fullstack", "full stack", "full-stack", "lap trinh vien full")),
    ("backend", ("backend", "back end", "back-end", "server engineer", "api developer")),
    ("frontend", ("frontend", "front end", "front-end", "web ui develop")),
    ("mobile", ("mobile", "ios", "android", "flutter", "react native", "kotlin", "swift developer")),
    ("embedded", ("embedded", "firmware", "iot", "hardware engineer")),
    ("data", ("data engineer", "data scientist", "data analyst", "big data", "machine learning",
              "ai engineer", "business intelligence", "bi analyst", "data platform")),
    ("devops", ("devops", "sre", "site reliability", "platform engineer", "cloud engineer",
                "infrastructure", "sysadmin", "system administrator", "it support", "network engineer")),
    ("qa", ("qa", "qc", "tester", "test engineer", "automation test", "manual test", "kiem thu")),
    ("security", ("security", "infosec", "cyber", "penetration test")),
    ("game", ("game", "unity", "unreal")),
    ("pm", ("product manager", "project manager", "scrum master", "product owner", "business analyst")),
    ("uiux", ("ui/ux", "ui ux", "designer", "graphic")),
    ("manage", ("cto", "vp engineering", "engineering manager", "team leader", "truong nhom", "quan ly ky thuat")),
    ("web", ("web developer", "web designer", "wordpress", "shopify", "ecommerce")),
    ("brse", ("brse", "bridge", "ky su cau noi")),
)

# Từ khóa ngôn ngữ/framework đứng một mình trong tiêu đề (đặt sau các nhóm chức danh)
LANGUAGE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("java", ("java",)), ("python", ("python", "django")), ("php", ("php", "laravel")),
    ("dotnet", (".net", "c#", "c .net")), ("cpp", ("c++", "c/c++")), ("golang", ("golang", "go developer")),
    ("nodejs", ("node", "nodejs")), ("react", ("react", "angular", "vue")), ("scala", ("scala", "spark")),
)

UNKNOWN_CITY = "na"


def company_slug(name: str | None) -> str:
    """Tên công ty đã chuẩn hóa + bỏ hậu tố ngành + bỏ dấu + bỏ ký tự đặc biệt."""
    base = fold(EXTRA_LEGAL.sub(" ", normalize_company_name(name)))
    return re.sub(r"[^a-z0-9]", "", base)


def location_code(flat: dict) -> str:
    """Mã tỉnh viết tắt từ khóa tỉnh đã chuẩn hóa: ha_noi->HN, ho_chi_minh->HCM, da_nang->DN."""
    loc = flat.get("working_locations") or []
    first = (loc[0] if isinstance(loc, list) and loc else None) or flat.get("raw_location_text")
    key = province.key(first)
    if not key:
        return UNKNOWN_CITY
    parts = [p for p in key.split("_") if p not in {"tp", "thanh", "pho", "tinh", "thx"}]
    return "".join(p[0] for p in parts)[:3].upper() or UNKNOWN_CITY


def title_group(title: str | None) -> str:
    """Chức danh rút gọn (SPEC-05: vd `backend`, `frontend`, `java`, `qa`)."""
    g = fold(clean_text(title))
    if not g:
        return "unknown"
    for name, keys in TITLE_GROUPS:
        if any(k in g for k in keys):
            return name
    for name, keys in LANGUAGE_GROUPS:
        if any(re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", g) for k in keys):
            return name
    return "other"


def blocking_key(flat: dict) -> str:
    return f"{company_slug(flat.get('company_name'))}_{location_code(flat)}_{title_group(flat.get('job_title'))}"
