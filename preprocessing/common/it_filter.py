# -*- coding: utf-8 -*-
"""Luật if-else 2 tầng phân loại tin IT (P1 C4a). Khớp theo từ nguyên vẹn, không theo chuỗi con (PRE-1).

Tầng 1 `classify`: từ khóa tiêu đề + kỹ năng raw → it | non_it | unknown.
Tầng 2 `classify_unknown`: chỉ cho tin tầng 1 ra unknown, xét nhóm nghề theo tiêu đề và số kỹ năng rút từ JD.
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
# ("Kỹ thuật bảo trì nhà máy", "Security (Nhân viên bảo an)"), nên ra unknown để tầng 2 quyết.
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
        return "unknown"  # "Kinh doanh phần mềm", "IT Recruiter": để tầng 2 quyết
    if strong:
        return "it"
    if non:
        return "non_it"
    if len(tech) >= MIN_TECH_SKILLS:
        return "it"
    return "unknown"  # chỉ có từ yếu hoặc không có gì: tầng 2 quyết


# Tầng 2: đo trên 227 tin "unknown" đã gán nhãn tay (03/11/2026) đúng 81,5%; ngưỡng 2 cho kết quả tốt nhất (2–6).
MIN_JD_SKILLS = 2


def classify_unknown(title: Any, skills_list: Any = None, jd_text: Any = None, company: Any = None) -> str:
    """it | non_it cho tin tầng 1 không quyết được: có nhóm nghề IT (12 nhóm) và ≥ MIN_JD_SKILLS kỹ năng."""
    # import trong hàm: common không phụ thuộc cứng vào transformation/normalization khi chỉ dùng tầng 1
    from preprocessing.normalization.text_cleaner import canonicalize_skills, classify_job_family_rule
    from preprocessing.transformation.skill_extractor import extract_skills

    skills = canonicalize_skills(extract_skills(skills_list if isinstance(skills_list, list) else None,
                                                str(jd_text or ""), company))
    family, _ = classify_job_family_rule(str(title or ""), skills)
    return "it" if family and len(skills) >= MIN_JD_SKILLS else "non_it"


# ---------------------------------------------------------------- Bộ lọc IT ba tầng (C4a, đặc tả 19/11)
# Đặc tả: docs/spec/preprocessing/01_clean.md dòng C4a và mục 2.1 (định nghĩa "vai trò IT").
# Từ khóa, ngoại lệ và ngưỡng nằm ở preprocessing/dictionaries/it_filter_v2.json; chỉ dùng khi approved = true.
# Tầng 2 đếm kỹ năng bằng matcher của bước 08 (processing.extraction.skills, từ điển skills_v2.json): phụ thuộc
# ngược từ pre-processing sang processing, chấp nhận vì matcher chỉ đọc từ điển (kế hoạch 19/11).
import json  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parents[1] / "dictionaries" / "it_filter_v2.json"


def load_config(path: Path = CONFIG_PATH, require_approved: bool = True) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if require_approved and cfg.get("_meta", {}).get("approved") is not True:
        raise ValueError(f"it_filter_v2.json chưa được duyệt ({path})")
    return cfg


@lru_cache(maxsize=None)
def _cached_pattern(words: tuple) -> re.Pattern:
    return _pattern(words)


def _hit(words, text: str) -> bool:
    words = tuple(w for w in words if w)
    return bool(words) and bool(_cached_pattern(words).search(text))


def reviewed_non_it(source: str, job_id: Any, cfg: dict) -> bool:
    """Tầng 0 theo từng tin: `<nguồn>:<job_id>` có trong `reviewed_non_it.jobs` (tin đã đọc JD, kết luận không IT)."""
    jobs = (cfg.get("reviewed_non_it") or {}).get("jobs") or {}
    return f"{source}:{job_id}" in jobs


def excluded_role(title: Any, cfg: dict) -> str | None:
    """Tầng 0: tên nhóm bị loại hoàn toàn (mục 2.1) hoặc None. Ngoại lệ chỉ áp cho nhóm được ghi trong cấu hình."""
    t = _norm(title)
    exc = cfg["exceptions"]
    for group, words in cfg["excluded_roles"].items():
        if not _hit(words, t):
            continue
        if group in exc.get("it_role_applies_to", []) and _hit(exc["it_role_terms"], t):
            continue
        if group in exc.get("embedded_applies_to", []) and _hit(exc["embedded_for_automation"], t):
            continue
        return group
    return None


def classify_tier1(title: Any, skills: Any, cfg: dict, matcher=None) -> str:
    """Như `classify`, với từ khóa sửa theo cfg["tier1"] (thêm/bớt từ IT mạnh, thêm từ không IT). Tag kỹ năng của sàn
    đếm qua alias của skills_v2 (nhóm lõi IT), thay danh sách TECH_SKILLS viết tay của luật cũ."""
    t1 = cfg["tier1"]
    strong = tuple(sorted(set(STRONG_IT) - set(t1["remove_strong_it"]) | set(t1["add_strong_it"])))
    non = tuple(sorted(set(NON_IT) | set(t1["add_non_it"])))
    t = _norm(title)
    is_strong, is_non = _hit(strong, t), _hit(non, t)
    if is_strong and is_non:
        return "unknown"
    if is_strong:
        return "it"
    if is_non:
        return "non_it"
    if not skills:
        return "unknown"
    m = matcher or default_matcher()
    core = set(cfg["tier2"]["core_groups"])
    tech = {sl for s in skills if isinstance(s, str) for sl in [m.meta_slug(s)] if sl and m.taxonomy[sl].get("group") in core}
    return "it" if len(tech) >= MIN_TECH_SKILLS else "unknown"


@lru_cache(maxsize=1)
def default_matcher():
    from processing.extraction.skills import load_skills_v2, matcher_from_v2
    return matcher_from_v2(load_skills_v2())


def it_signals(title: Any, jd: Any, category: Any, cfg: dict, matcher=None) -> dict:
    """Bốn tín hiệu tầng 2: core (kỹ năng nhóm lõi IT trong JD), sec (kỹ năng bảo mật), fam (nhóm nghề từ tiêu đề),
    cat (chuyên mục sàn có từ IT)."""
    from preprocessing.normalization.text_cleaner import classify_job_family_rule
    t2 = cfg["tier2"]
    m = matcher or default_matcher()
    slugs = {h.slug for h in m.find(str(jd or ""))}
    groups = [m.taxonomy[s].get("group") for s in slugs]
    family, _ = classify_job_family_rule(str(title or ""), [])
    return {"core": sum(g in t2["core_groups"] for g in groups),
            "sec": sum(g == t2["security_group"] for g in groups),
            "fam": bool(family),
            "cat": _hit(t2["category_terms"], _norm(category))}


def tier2_decide(sig: dict, source: str, rule: dict) -> str:
    k_fam, k_sec, k_core = rule.get("k_fam"), rule.get("k_sec"), rule.get("k_core")
    k_cat = (rule.get("k_cat_by_source") or {}).get(source, rule.get("k_cat"))
    it = ((k_fam is not None and sig["fam"] and sig["core"] >= k_fam)
          or (k_sec is not None and sig["sec"] >= k_sec)
          or (k_core is not None and sig["core"] >= k_core)
          or (k_cat is not None and sig["cat"] and sig["core"] >= k_cat))
    return "it" if it else "non_it"


def classify_it(title: Any, skills: Any, jd: Any, category: Any, source: str, cfg: dict, matcher=None) -> tuple[str, int]:
    """(it_status, it_rule_level) theo ba tầng. Tầng 0 thắng mọi tín hiệu khác."""
    if excluded_role(title, cfg):
        return "non_it", 0
    r = classify_tier1(title, skills, cfg, matcher)
    if r != "unknown":
        return r, 1
    return tier2_decide(it_signals(title, jd, category, cfg, matcher), source, cfg["tier2"]["rule"]), 2
