"""Deterministic classifier for the 12 Job Families in Duy's task handbook."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

JOB_FAMILIES: tuple[str, ...] = (
    "Backend", "Frontend", "Fullstack", "Mobile", "DevOps/Cloud", "Data/AI",
    "QA/QC", "Security", "BA", "Product", "System", "Embedded",
)


def _fold(value: Any) -> str:
    value = "" if value is None else str(value)
    value = value.casefold().replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value).strip()


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


# Specific domains precede generic software development roles.
_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Embedded", (r"\bembedded\b", r"\bfirmware\b", r"\brtos\b", r"microcontroller", r"\bmcu\b", r"bare[- ]metal", r"device driver", r"\bfpga\b")),
    ("Security", (r"\bsecurity\b", r"\bsoc\b", r"\bpentest\b", r"\bcybersecurity\b", r"an ninh mang", r"bao mat", r"\binfosec\b", r"\bsiem\b", r"devsecops")),
    ("QA/QC", (r"\btester\b", r"\bqa\b", r"\bqc\b", r"quality assurance", r"automation test", r"manual test", r"kiem thu", r"\bsqa\b", r"test engineer", r"quality engineer")),
    ("BA", (r"business analyst", r"\bba\b", r"phan tich nghiep vu", r"system analyst", r"business systems analyst")),
    ("Product", (r"product manager", r"project manager", r"scrum master", r"\bproduct owner\b", r"\bpo\b", r"\bpm\b", r"quan ly du an", r"quan ly san pham", r"product specialist")),
    ("DevOps/Cloud", (r"\bdevops\b", r"\bcloud\b", r"\bsre\b", r"infrastructure engineer", r"ci\s*/\s*cd", r"site reliability", r"platform engineer")),
    ("System", (r"system engineer", r"systems engineer", r"network engineer", r"ky su he thong", r"quan tri mang", r"helpdesk", r"network administrator", r"system administrator", r"\bsysadmin\b", r"\bit support\b", r"\bnetwork admin\b")),
    ("Data/AI", (r"data engineer", r"data analyst", r"data scientist", r"machine learning", r"deep learning", r"artificial intelligence", r"\bnlp\b", r"business intelligence", r"\bbi developer\b", r"computer vision", r"\bai engineer\b", r"\bai developer\b", r"\bml engineer\b")),
    ("Mobile", (r"\bmobile\b", r"\bandroid\b", r"\bios\b", r"\bflutter\b", r"react native", r"\bswift\b", r"\bkotlin\s+developer\b")),
    ("Frontend", (r"front\s*end", r"front-end", r"frontend", r"web client", r"reactjs developer", r"vue developer")),
    ("Backend", (r"back\s*end", r"back-end", r"backend", r"server-side", r"java developer", r"java dev", r"golang dev", r"\.net dev")),
)
_BACKEND_SKILLS = {
    "Java", "Spring Boot", "Node.js", ".NET Core", "Django", "FastAPI", "Flask", "PHP",
    "Laravel", "Go", "Python", "SQL", "C#", "C++", "Ruby", "REST API", "GraphQL",
    "PostgreSQL", "MySQL", "MongoDB", "Microservices", "gRPC",
}
_FRONTEND_SKILLS = {
    "React", "Next.js", "Vue.js", "Angular", "JavaScript", "TypeScript", "HTML/CSS", "Svelte", "jQuery",
}
_IT_CATEGORY_PATTERNS = (
    r"\bit\b", r"information technology", r"cong nghe thong tin", r"software", r"technology",
)
_SKILL_GATES: tuple[tuple[str, set[str]], ...] = (
    ("QA/QC", {"Selenium", "Cypress", "Postman", "JMeter", "Appium"}),
    ("Security", {"Penetration Testing", "Firewall", "SIEM", "OWASP", "CISSP"}),
    ("BA", {"UML", "BPMN", "User Story", "BRD", "Jira", "SQL"}),
    ("Product", {"Agile / Scrum", "Roadmapping"}),
    ("DevOps/Cloud", {"Docker", "Kubernetes", "AWS", "Google Cloud", "Microsoft Azure", "CI/CD", "Terraform", "Linux"}),
    ("System", {"Cisco", "CCNA", "TCP/IP", "Windows Server", "Routing", "Switching"}),
    ("Data/AI", {"Python", "SQL", "Spark", "Machine Learning", "Artificial Intelligence", "Natural Language Processing", "TensorFlow", "PyTorch", "Power BI"}),
    ("Mobile", {"Flutter", "React Native", "Swift", "Kotlin", "iOS", "Android"}),
    ("Embedded", {"C", "C++", "RTOS", "Firmware", "Microcontroller"}),
)


def classify_job_family(job_title: Any = "", skills: Iterable[str] | None = None,
                        job_context: Any = "", category: Any = None) -> str | None:
    """Classify a job; generic-title skill fallback requires an IT category."""
    title = _fold(job_title)
    context = _fold(job_context)
    category_text = _fold(category)
    skill_set = {str(skill).strip() for skill in (skills or []) if skill is not None}

    is_fullstack = _has(title, r"\bfull\s*stack\b", r"\bfull-stack\b", r"\bfullstack\b", r"toan dien")
    has_backend = bool(skill_set & _BACKEND_SKILLS)
    has_frontend = bool(skill_set & _FRONTEND_SKILLS)
    if is_fullstack:
        if has_backend and has_frontend:
            return "Fullstack"
        if has_backend:
            return "Backend"
        if has_frontend:
            return "Frontend"
        return None

    for family, patterns in _FAMILY_RULES:
        if _has(title, *patterns):
            return family

    if _has(title, r"\bai\b") and _has(
        f"{title} {context}", r"machine learning", r"deep learning", r"data scientist",
        r"artificial intelligence", r"\bllm\b", r"computer vision", r"\bnlp\b",
    ):
        return "Data/AI"

    if _has(category_text, *_IT_CATEGORY_PATTERNS):
        for family, gate in _SKILL_GATES:
            if len(skill_set & gate) >= 2:
                return family
        if has_backend and not has_frontend and _has(context, r"backend", r"server[- ]side"):
            return "Backend"
        if has_frontend and not has_backend and _has(context, r"frontend", r"front[- ]end", r"web client"):
            return "Frontend"
    return None


def get_job_families() -> list[str]:
    return list(JOB_FAMILIES)
