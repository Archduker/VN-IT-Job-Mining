# -*- coding: utf-8 -*-
"""Chức danh -> chức danh chuẩn -> nhóm nghề (PH6 N15-N17). Luật if-else + rapidfuzz, không dùng model.

Nhóm nghề: đúng 12 nhóm của SPEC-01 mục 4.4 + `Other` (người dùng chốt phương án A, 10/11/2026).
`job_title_clean` không bao giờ bị đổi: mọi hàm ở đây chỉ trả giá trị mới.
Từ điển `preprocessing/dictionaries/job_titles.json`: chỉ nạp mục `approved: true` (người dùng duyệt).
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from preprocessing.common import REPO_ROOT
from preprocessing.normalization.text_cleaner import has_term

DICT_PATH = REPO_ROOT / "preprocessing" / "dictionaries" / "job_titles.json"
OTHER = "Other"
FUZZY_CUTOFF = 90  # K10: điểm khởi đầu, đo lại trên dữ liệu rồi mới chốt
FUZZY_MIN_LEN = 8  # tránh "ba", "qa", "it" khớp lung tung

JOB_FAMILIES_12 = [
    "Backend", "Frontend", "Fullstack", "Mobile", "DevOps/Cloud", "Data Engineer", "Data Science/AI",
    "QA/QC", "Security", "Product/Project", "System/Network", "Embedded/IoT",
]


def fold(text: Any) -> str:
    s = unicodedata.normalize("NFD", str(text or "").casefold().replace("đ", "d"))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


# Đặc thù trước, chung sau. Từ khóa đã fold (không dấu). Backend thu hẹp: bỏ developer, software engineer,
# lập trình viên, java, python, node... khỏi luật tiêu đề (chúng chỉ là tín hiệu kỹ năng ở bước 3).
# K9b: Data Analyst/BI/phân tích dữ liệu xếp Data Science/AI (SPEC-01 không có nhóm Analyst riêng; mặc định của agent).
_RULES_RAW: List[Tuple[str, List[str]]] = [
    ("Embedded/IoT", ["embedded", "firmware", "iot", "rtos", "fpga", "microcontroller", "mcu", "vi điều khiển", "nhúng", "bare-metal", "device driver"]),
    ("Security", ["security", "soc", "pentest", "pentester", "cyber", "cybersecurity", "an ninh mạng", "bảo mật", "infosec", "siem", "penetration tester", "appsec", "devsecops"]),
    ("QA/QC", ["tester", "qa", "qc", "quality assurance", "quality control", "automation test", "manual test", "kiểm thử", "test engineer", "test lead", "software testing", "sqa", "quality engineer"]),
    ("Product/Project", ["business analyst", "ba", "phân tích nghiệp vụ", "business analysis", "functional analyst", "system analyst",
                         "product manager", "product owner", "po", "project manager", "pm", "quản lý sản phẩm", "quản lý dự án",
                         "scrum master", "delivery manager", "agile coach", "project lead", "product specialist", "pmo"]),
    ("DevOps/Cloud", ["devops", "cloud", "sre", "infrastructure engineer", "ci/cd", "platform engineer", "site reliability", "kubernetes", "k8s"]),
    ("System/Network", ["network engineer", "system engineer", "systems engineer", "quản trị mạng", "quản trị hệ thống", "helpdesk", "help desk", "it support",
                        "cisco", "mạng máy tính", "network admin", "network administrator", "system admin", "system administrator", "sysadmin", "kỹ sư hệ thống"]),
    ("Data Engineer", ["data engineer", "big data", "etl", "data warehouse", "dwh", "kỹ sư dữ liệu", "data platform", "dataops"]),
    ("Data Science/AI", ["data scientist", "data science", "machine learning", "ai engineer", "ai developer", "ai researcher", "ml engineer", "deep learning",
                         "nlp", "computer vision", "trí tuệ nhân tạo", "khoa học dữ liệu", "data analyst", "data analytics", "phân tích dữ liệu",
                         "bi analyst", "bi developer", "business intelligence", "power bi", "tableau", "genai", "llm", "ai"]),
    ("Mobile", ["mobile", "flutter", "react native", "ios", "android", "swift", "kotlin"]),
    ("Fullstack", ["fullstack", "full-stack", "full stack", "toàn diện"]),
    ("Frontend", ["frontend", "front-end", "front end", "ui developer", "web frontend", "reactjs", "react developer", "vuejs", "angular developer"]),
    ("Backend", ["backend", "back-end", "back end", "server-side", "server side"]),
]
FAMILY_RULES_V2: List[Tuple[str, List[str]]] = [(fam, [fold(t) for t in terms]) for fam, terms in _RULES_RAW]

# Kỹ năng cổng (bước 3): chỉ khi MỘT nhóm duy nhất có >= 2 kỹ năng đặc trưng. Nhiều nhóm hòa -> Other (K11).
_SKILL_GATES: List[Tuple[str, set]] = [
    ("Embedded/IoT", {"RTOS", "Firmware", "Microcontroller", "Embedded C", "FreeRTOS", "ARM", "FPGA"}),
    ("QA/QC", {"Selenium", "Cypress", "Postman", "JMeter", "Appium", "Automation Test", "Unit Test"}),
    ("Security", {"Penetration Testing", "Firewall", "SIEM", "OWASP", "CISSP"}),
    ("Product/Project", {"Agile/Scrum", "Agile / Scrum", "Roadmapping", "UML", "BPMN", "User Story", "BRD"}),
    ("DevOps/Cloud", {"Docker", "Kubernetes", "AWS", "Google Cloud", "Microsoft Azure", "Azure", "GCP", "CI/CD", "Terraform", "Linux"}),
    ("System/Network", {"Cisco", "CCNA", "TCP/IP", "Windows Server", "Routing", "Switching"}),
    ("Data Engineer", {"Spark", "Kafka", "Airflow", "Hadoop", "ETL", "Data Engineering", "Big Data"}),
    ("Data Science/AI", {"Machine Learning", "Artificial Intelligence", "Natural Language Processing", "TensorFlow", "PyTorch", "Power BI", "Tableau"}),
    ("Mobile", {"Flutter", "React Native", "Swift", "Kotlin", "iOS", "Android", "Dart"}),
    ("Frontend", {"React", "Vue", "Vue.js", "Angular", "HTML/CSS", "Next.js", "TypeScript", "Svelte"}),
    ("Backend", {"Java", "Spring Boot", "Node.js", ".NET Core", "Django", "FastAPI", "Flask", "PHP", "Laravel", "Golang", "C#",
                 "Ruby", "REST API", "GraphQL", "PostgreSQL", "MySQL", "MongoDB", "Microservices", "gRPC"}),
]

_GENERIC_RE = re.compile(r"^(?:it|cntt|cong nghe thong tin)(?: (?:engineer|executive|staff|specialist|generalist|manager|officer|fulltime))?$")


# ---------------------------------------------------------------- N15 bỏ nhiễu
_PROMO = re.compile(r"^\s*(?:tuyển\s+gấp|tuyen\s+gap|hot|urgent|gấp)\s*[-–:!|]*\s*", re.I)
_BRACKET = re.compile(r"\[[^\]]*\]")
_PAREN = re.compile(r"\(([^()]*)\)")
_CODE = re.compile(r"\b[A-Za-z]*\d{4,}[A-Za-z0-9]*\b")
_SEP = re.compile(r"\s+[-–|]\s*|\s*[-–|]\s+|\s*\|\s*")
_SALARY_TAIL = re.compile(r"(?:\b(?:thu\s+nhập|lương|up\s*to|upto|tới|lên\s+đến)\b.*|\bđến\s+\d.*|\d+\s*[-–]\s*\d+\s*(?:tr|triệu|m)\b.*|\b\d+\s*(?:tr|triệu|\$|usd).*)$", re.I)
_PLACE_TAIL = re.compile(r"\b(?:tại|ở|làm\s+việc\s+tại)\s+.+$", re.I)
_PREFIX_ROLE = re.compile(r"^(?:nhân\s+viên|chuyên\s+viên)\s+(?=\S)", re.I)
_LEVEL_WORDS = [
    ("Intern/Fresher", r"thực\s+tập\s+sinh|thực\s+tập|intern(?:ship)?|trainee|fresher|mới\s+tốt\s+nghiệp"),
    ("Senior", r"senior|sr\.?"),
    ("Junior", r"junior|jr\.?"),
    ("Middle", r"middle|mid[- ]level|mid"),
    ("Lead/Manager", r"team\s+lead|tech\s+lead|leader|lead|trưởng\s+nhóm"),
    (None, r"all\s+levels?"),
]
_TECH_SPLIT = re.compile(r"\s*,\s*")


def _tech_hint(inside: str) -> List[str]:
    """Nội dung ngoặc là danh sách công nghệ nếu có >= 1 mục là kỹ năng đã biết (skills.json); ngược lại bỏ."""
    from preprocessing.normalization.text_cleaner import _get_skills_lookup

    items = [t.strip() for t in _TECH_SPLIT.split(inside) if t.strip()]
    lookup = _get_skills_lookup()
    if len(items) >= 2 and any(t.lower() in lookup for t in items) or (len(items) == 1 and items[0].lower() in lookup):
        return items
    return []


def core_title(title_clean: Optional[str]) -> Tuple[str, Optional[str], List[str]]:
    """N15a-N15f: (core, level, tech_hint). Không đổi `job_title_clean`."""
    s = str(title_clean or "").strip()
    if not s:
        return "", None, []
    s = _PROMO.sub("", s)                      # N15d
    s = _BRACKET.sub(" ", s)                   # N15a
    hints: List[str] = []

    def _paren(m: "re.Match[str]") -> str:    # N15f: giữ công nghệ trong ngoặc ở cột riêng
        h = _tech_hint(m.group(1))
        hints.extend(h)
        return " "

    s = _PAREN.sub(_paren, s)
    s = _CODE.sub(" ", s)                      # N15b
    parts = [p.strip() for p in _SEP.split(s) if p and p.strip()]
    level_re = "|".join(rf"(?:{rx})" for _, rx in _LEVEL_WORDS)
    first = next((p for p in parts if re.search(r"[^\W\d_]", p) and not re.fullmatch(rf"(?:{level_re}|\s)+", p, re.I)),
                 parts[0] if parts else "")
    s = _SALARY_TAIL.sub("", first)            # N15c
    s = _PLACE_TAIL.sub("", s).strip(" -–|,:;")
    # N15e: tách cấp bậc
    level: Optional[str] = None
    for label, rx in _LEVEL_WORDS:
        m = re.search(rf"(?<!\w)(?:{rx})(?!\w)", s, re.I)
        if not m:
            continue
        rest = re.sub(r"\s+", " ", (s[:m.start()] + " " + s[m.end():]).strip(" -–|,:;/"))
        if label == "Lead/Manager" and fold(rest) in ("", "tech", "team"):
            continue  # "Tech Lead" nguyên là tên việc
        if rest:
            s = rest
            level = level or label
    s = _PREFIX_ROLE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" -–|,:;/")
    return s, level, hints


def is_generic_title(core: str) -> bool:
    return bool(_GENERIC_RE.match(fold(core)))


# ---------------------------------------------------------------- N16 chức danh chuẩn
def load_title_dict(path=DICT_PATH) -> Dict[str, Any]:
    """Chỉ mục `approved: true`. Thiếu file hoặc không có mục duyệt -> từ điển rỗng."""
    entries: List[Dict[str, Any]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = [e for e in data.get("entries", []) if e.get("approved") is True and e.get("canonical")]
    except (OSError, ValueError):
        pass
    return build_title_dict(entries)


def build_title_dict(entries: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    exact: Dict[str, str] = {}
    family_of: Dict[str, Optional[str]] = {}
    alias_canon: List[Tuple[str, str]] = []
    for e in entries:
        canon = e["canonical"]
        family_of[canon] = e.get("family")
        for a in {canon, *(e.get("aliases") or [])}:
            f = fold(a)
            if f:
                exact.setdefault(f, canon)
                alias_canon.append((f, canon))
    fuzzy_list = [a for a, _ in alias_canon if len(a) >= FUZZY_MIN_LEN]
    return {"exact": exact, "family_of": family_of, "aliases": alias_canon,
            "fuzzy_list": fuzzy_list, "canon_of": dict(alias_canon)}


def canonical_title(core_fold: str, title_dict: Dict[str, Any], cutoff: int = FUZZY_CUTOFF
                    ) -> Tuple[Optional[str], str, Optional[float]]:
    """exact -> alias (has_term) -> fuzzy (rapidfuzz token_set_ratio). Trả (canonical|None, source, score|None)."""
    if not core_fold or not title_dict["exact"]:
        return None, "none", None
    if core_fold in title_dict["exact"]:
        return title_dict["exact"][core_fold], "exact", None
    for alias, canon in title_dict["aliases"]:
        if has_term(core_fold, [alias]):
            return canon, "alias", None
    if len(core_fold) >= FUZZY_MIN_LEN and title_dict["fuzzy_list"]:
        from rapidfuzz import fuzz, process

        m = process.extractOne(core_fold, title_dict["fuzzy_list"], scorer=fuzz.token_set_ratio, score_cutoff=cutoff)
        if m:
            return title_dict["canon_of"][m[0]], "fuzzy", float(m[1])
    return None, "none", None


# ---------------------------------------------------------------- N17 nhóm nghề
def family_from_title(core_fold: str, canonical: Optional[str], skills_std: Optional[Sequence[str]],
                      title_dict: Dict[str, Any], tech_hint: Sequence[str] = ()) -> Tuple[str, str]:
    """canonical -> từ khóa tiêu đề (thu hẹp) -> kỹ năng cổng -> Other. Trả (family, source)."""
    if canonical:
        fam = title_dict["family_of"].get(canonical)
        if fam:
            return fam, "canonical"
    for family, terms in FAMILY_RULES_V2:
        if has_term(core_fold, terms):
            return family, "title"
    skills = set(skills_std or []) | set(tech_hint or [])
    hits = [fam for fam, gate in _SKILL_GATES if len(skills & gate) >= 2]
    if len(hits) == 1:
        return hits[0], "skills"
    return OTHER, "none"
