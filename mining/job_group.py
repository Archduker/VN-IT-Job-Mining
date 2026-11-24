# -*- coding: utf-8 -*-
"""SD3: 7 nhóm nghề (`job_group`) và vai trò con (`sub_role_title`) từ tiêu đề + `job_family` + công cụ.

Người dùng chốt 24/11/2026: 7 nhóm theo danh sách vai trò của người dùng, Data và AI chung một nhóm,
DBA vào Hạ tầng, IT Manager vào Product & Business, tin Infra/Support tiêu đề chung chung xếp theo công cụ,
tin không thuộc 7 nhóm vào "Khác" (nơi tìm tin mới). Chỉ dùng cho SD3 (M3); `job_family` 11 nhóm vẫn
dùng cho SD1, SD2, SD4, SD5. Luật if-else trên tiêu đề đã fold, không dùng model.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from preprocessing.normalization.job_title import fold
from preprocessing.normalization.text_cleaner import has_term

SOFTWARE, QA, DATA_AI, INFRA, SECURITY, PRODUCT, SUPPORT, OTHER = (
    "Software", "QA/QC", "Data & AI", "Hạ tầng", "Security", "Product & Business", "Support & Consulting", "Khác")
GROUPS = [SOFTWARE, QA, DATA_AI, INFRA, SECURITY, PRODUCT, SUPPORT]

FAMILY_TO_GROUP = {
    "Web": SOFTWARE, "Mobile": SOFTWARE, "Game": SOFTWARE, "IoT": SOFTWARE,
    "Tester": QA, "Data/AI": DATA_AI, "DevOps/Cloud": INFRA, "Security": SECURITY,
    "Bridge": PRODUCT, "Design": PRODUCT,
}

# Tiêu đề (đã fold: chữ thường, bỏ dấu). Thứ tự ưu tiên: DBA -> IT Manager -> Support -> nhóm theo job_family.
DBA_TITLE = ["dba", "database administrator", "database admin", "quan tri co so du lieu", "quan tri csdl"]
MANAGER_TITLE = ["it manager", "truong phong it", "truong phong cntt", "truong phong cong nghe thong tin",
                 "giam doc it", "giam doc cntt", "head of it", "it director"]
DEV_TITLE = ["developer", "lap trinh", "programmer", "dev", "abap", "software engineer", "phat trien phan mem",
             "backend", "frontend", "fullstack"]
# Nghề chuyên môn rõ: tiêu đề có ERP/CRM/SAP vẫn giữ nhóm cũ ("Data Analyst (ERP/SAP)" là Data, không là tư vấn ERP)
KEEP_FAMILY = {"Data/AI", "Tester", "Security"}
ERP_TITLE = ["erp", "crm", "sap", "odoo", "dynamics 365"]
SUPPORT_TITLE = ["helpdesk", "help desk", "it support", "technical support", "ho tro ky thuat", "ho tro it",
                 "technical writer", "solution architect", "it consultant", "tu van giai phap", "kien truc su giai phap"]
INFRA_TITLE = ["network", "system engineer", "systems engineer", "sysadmin", "system admin", "system administrator",
               "quan tri mang", "quan tri he thong", "ky su he thong", "data center", "noc"]
# Infra/Support tiêu đề chung chung: có >= 1 công cụ máy chủ/mạng thì vào Hạ tầng, còn lại vào Support.
# Bỏ linux, bash, powershell, windows: tin helpdesk cũng hay ghi (đo 24/11 trên 396 tin Infra/Support).
INFRA_TOOLS = {"windows_server", "vmware", "esxi", "hyperv", "proxmox", "redhat", "cisco", "juniper", "fortinet",
               "palo_alto", "sophos", "aruba", "active_directory", "group_policy", "entra_id", "veeam", "zabbix",
               "prtg", "cacti_solarwinds", "ansible", "aws", "azure", "gcp", "docker", "kubernetes", "prometheus",
               "grafana", "terraform"}

# Vai trò con theo danh sách của người dùng; trong mỗi nhóm, vai trò đầu tiên khớp tiêu đề thắng.
SUB_ROLES: dict[str, list[tuple[str, list[str]]]] = {
    SOFTWARE: [("Full-stack", ["fullstack", "full-stack", "full stack"]),
               ("Mobile", ["mobile", "ios", "android", "flutter", "react native"]),
               ("Game", ["game", "unity", "unreal"]),
               ("Embedded", ["embedded", "nhung", "firmware", "iot", "fpga"]),
               ("Frontend", ["frontend", "front-end", "front end", "reactjs", "react", "vuejs", "angular", "ui developer"]),
               ("Backend", ["backend", "back-end", "back end", "java", "golang", ".net", "dotnet", "php", "nodejs",
                            "node.js", "python", "c#", "ruby"])],
    QA: [("Automation Tester", ["automation", "auto test", "sdet"]),
         ("QA Engineer", ["qa engineer", "quality assurance", "qa lead", "sqa", "qa"]),
         ("Manual Tester / QC", ["manual", "qc", "tester", "kiem thu", "test engineer"])],
    DATA_AI: [("Data Scientist", ["data scientist", "data science", "khoa hoc du lieu"]),
              ("Data Engineer", ["data engineer", "ky su du lieu", "big data", "etl", "data platform"]),
              ("BI Developer", ["bi", "power bi", "business intelligence", "tableau"]),
              ("AI / ML Engineer", ["ai", "machine learning", "ml", "deep learning", "llm", "genai",
                                    "computer vision", "nlp", "agentic", "tri tue nhan tao"]),
              ("Data Analyst", ["data analyst", "phan tich du lieu", "data analytics", "analyst"])],
    INFRA: [("DevOps / SRE", ["devops", "sre", "site reliability", "platform engineer"]),
            ("Cloud Engineer", ["cloud", "aws", "azure", "gcp"]),
            ("DBA", DBA_TITLE + ["database engineer"]),
            ("Network Engineer", ["network", "quan tri mang", "noc", "cisco", "mang"]),
            ("SysAdmin", ["system", "sysadmin", "he thong", "server", "may chu", "quan tri", "it"])],
    SECURITY: [("SOC Analyst", ["soc", "siem", "giam sat an ninh"]),
               ("Pentester", ["pentest", "pentester", "penetration", "red team", "offensive"]),
               ("Security Consultant", ["consultant", "tu van", "grc", "audit", "iso 27001", "compliance"]),
               ("Security Engineer", ["security", "an toan thong tin", "an ninh mang", "bao mat", "cyber",
                                      "devsecops", "appsec"])],
    PRODUCT: [("Scrum Master", ["scrum master", "agile coach"]),
              ("PO / PM", ["product owner", "product manager", "po", "quan ly san pham"]),
              ("IT PM", ["project manager", "pm", "quan ly du an", "project lead", "delivery manager", "pmo"]
               + MANAGER_TITLE),
              ("UI/UX Designer", ["ui/ux", "ui ux", "ux", "ui designer", "designer", "thiet ke"]),
              ("Business Analyst", ["business analyst", "ba", "phan tich nghiep vu", "system analyst", "functional"])],
    SUPPORT: [("ERP / CRM Consultant", ERP_TITLE),
              ("Technical Writer", ["technical writer"]),
              ("IT Consultant / Solution Architect", ["solution architect", "kien truc su giai phap", "it consultant", "tu van", "consultant",
                                                      "presale", "presales"]),
              ("IT Helpdesk / Support", ["helpdesk", "help desk", "support", "ho tro", "ky thuat vien", "it"])],
}


def assign_group(title: str, job_family: str, tools: Iterable[str] = ()) -> tuple[str, str]:
    """Trả (nhóm, đường gán: title | family | skills | other)."""
    t = fold(title)
    if has_term(t, DBA_TITLE):
        return INFRA, "title"
    if has_term(t, MANAGER_TITLE):
        return PRODUCT, "title"
    if job_family not in KEEP_FAMILY and (has_term(t, ERP_TITLE) or has_term(t, SUPPORT_TITLE)):
        if has_term(t, DEV_TITLE):
            return SOFTWARE, "title"
        return SUPPORT, "title"
    if job_family == "Infra/Support":
        if has_term(t, INFRA_TITLE):
            return INFRA, "title"
        return (INFRA, "skills") if INFRA_TOOLS & set(tools) else (SUPPORT, "skills")
    if job_family in FAMILY_TO_GROUP:
        return FAMILY_TO_GROUP[job_family], "family"
    return OTHER, "other"


def sub_role_from_title(title: str, group: str) -> str | None:
    """Vai trò con đầu tiên trong nhóm có từ khóa khớp tiêu đề; None nếu không khớp."""
    t = fold(title)
    return next((name for name, terms in SUB_ROLES.get(group, []) if has_term(t, terms)), None)


def add_job_group(meta: pd.DataFrame, skills: pd.DataFrame) -> pd.DataFrame:
    """Thêm `job_group`, `job_group_source`, `sub_role_title` vào bản sao của meta (cùng thứ tự dòng với skills)."""
    meta = meta.reset_index(drop=True).copy()
    cols = [c for c in skills.columns if c.startswith("skill__")]
    S = skills.reset_index(drop=True)[cols].to_numpy() > 0
    names = [c[len("skill__"):] for c in cols]
    tools = [{names[j] for j in row.nonzero()[0]} for row in S]
    res = [assign_group(str(ti or ""), str(f), tl) for ti, f, tl in zip(meta["job_title"], meta["job_family"], tools)]
    meta["job_group"] = [g for g, _ in res]
    meta["job_group_source"] = [s for _, s in res]
    meta["sub_role_title"] = [sub_role_from_title(str(ti or ""), g) for ti, g in zip(meta["job_title"], meta["job_group"])]
    return meta
