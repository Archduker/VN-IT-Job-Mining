"""Luật 7 nhóm nghề SD3 (mining/job_group.py, người dùng chốt 24/11/2026)."""

import pandas as pd
import pytest

from mining.job_group import (
    DATA_AI, INFRA, OTHER, PRODUCT, QA, SOFTWARE, SUPPORT, add_job_group, assign_group, sub_role_from_title,
)


@pytest.mark.parametrize("title,family,tools,group,source", [
    ("Database Administrator (DBA)", "Data/AI", (), INFRA, "title"),
    ("Quản trị cơ sở dữ liệu", "Other", (), INFRA, "title"),
    ("Trưởng phòng IT", "Infra/Support", (), PRODUCT, "title"),
    ("IT Manager", "Bridge", (), PRODUCT, "title"),
    ("SAP Consultant", "Bridge", (), SUPPORT, "title"),
    ("Odoo Developer", "Bridge", (), SOFTWARE, "title"),
    ("Senior Software Engineer (ODOO)", "Web", (), SOFTWARE, "title"),
    ("Data Analyst (ERP/SAP)", "Data/AI", (), DATA_AI, "family"),
    ("Solution Architect", "DevOps/Cloud", (), SUPPORT, "title"),
    ("[Hà Nội] CVCC Kiến trúc sư giải pháp", "Other", (), SUPPORT, "title"),
    ("Network Engineer", "Infra/Support", (), INFRA, "title"),
    ("Nhân viên IT", "Infra/Support", ("windows_server", "ms_office"), INFRA, "skills"),
    ("Nhân viên IT", "Infra/Support", ("windows", "ms_office", "linux"), SUPPORT, "skills"),
    ("Manual Tester", "Tester", (), QA, "family"),
    ("Giám đốc công nghệ (CTO)", "Other", (), OTHER, "other"),
])
def test_assign_group_rules(title, family, tools, group, source):
    assert assign_group(title, family, tools) == (group, source)


@pytest.mark.parametrize("title,group,role", [
    ("Senior Fullstack Developer (Java)", SOFTWARE, "Full-stack"),
    ("Frontend Engineer (ReactJS)", SOFTWARE, "Frontend"),
    ("Data Engineer (AI project)", DATA_AI, "Data Engineer"),
    ("AI Engineer (LLM)", DATA_AI, "AI / ML Engineer"),
    ("Automation Tester", QA, "Automation Tester"),
    ("Product Owner", PRODUCT, "PO / PM"),
    ("Kỹ sư phần mềm", SOFTWARE, None),
])
def test_sub_role_from_title(title, group, role):
    assert sub_role_from_title(title, group) == role


def test_add_job_group_keeps_rows_and_uses_tool_columns():
    meta = pd.DataFrame({"job_title": ["Nhân viên IT", "Nhân viên IT"], "job_family": ["Infra/Support"] * 2})
    skills = pd.DataFrame({"skill__vmware": [1, 0], "skill__ms_office": [1, 1]})
    out = add_job_group(meta, skills)
    assert list(out["job_group"]) == [INFRA, SUPPORT]
    assert list(out["job_group_source"]) == ["skills", "skills"]
    assert "job_group" not in meta
