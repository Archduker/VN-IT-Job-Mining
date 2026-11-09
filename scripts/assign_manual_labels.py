#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script gán nhãn tay chuyên sâu cho 541 tin review C4b trong data/preprocessing/review/it_<nguồn>.csv.

Đặc tả: docs/spec/preprocessing/spec/P1_clean.md
Tiêu chí:
- 'it': Vị trí kỹ thuật hoặc sản phẩm công nghệ thông tin (Software, Data, Cloud/DevOps,
        Security, IT QA/QC, IT PO/PM/BA, IT Support/Helpdesk, UI/UX, Hardware/Embedded).
- 'non_it': Vị trí ngoài IT (Kinh doanh/Sales kể cả bán phần mềm, Kế toán, Nhân sự/Tuyển dụng kể cả IT Recruiter,
            Marketing, Giáo viên/Giảng dạy kể cả dạy tin học, Xây dựng, Cơ khí, Vận tải/Lái xe, Y tế, Pháp lý).
"""

import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = REPO_ROOT / "data" / "preprocessing" / "review"

SOURCES = [
    "careerviet",
    "glints",
    "itviec",
    "jobsgo",
    "topcv",
    "topdev",
    "vieclam24h",
    "vietnamworks",
]

FIELDS = ["job_id", "source_url", "job_title", "skills", "it_rule", "it_rule_level", "it_status", "nhan_tay"]


def evaluate_job(source: str, job_id: str, title: str, skills: str) -> Tuple[str, str]:
    """Đánh giá chi tiết từng công việc, trả về (nhãn, lý do)."""
    t_lower = title.lower().strip()
    s_lower = skills.lower().strip()

    # ========================== ITVIEC (22 tin) ==========================
    if source == "itviec":
        if "business-project-associate-china-market-preferred" in job_id:
            return "non_it", "Business development & market research mảng game thị trường TQ"
        return "it", "Vị trí kỹ thuật/sản phẩm công nghệ trên ITviec"

    # ========================== TOPDEV (80 tin) ==========================
    if source == "topdev":
        if "phát hiện gian lận" in t_lower and ("data" in s_lower or "mô hình" in t_lower):
            return "it", "Data Science / Xây dựng mô hình AI-Data phát hiện gian lận"
        return "non_it", "Crawler TopDev quét nhầm tin ngoài IT do API bỏ qua category_ids=1"

    # ========================== GLINTS (42 tin) ==========================
    if source == "glints":
        # Các vị trí IT rõ ràng
        it_matches = [
            "an toàn thông tin", "soc tier", "soc manager", "attt tier",
            "pci dss", "security content analyst", "back - end",
            "process quality assurance (pqa)", "ctv kiểm thử", "tester", "3d modeler"
        ]
        if any(m in t_lower for m in it_matches):
            return "it", "Kỹ thuật phần mềm / An toàn thông tin / Kiểm thử"
        return "non_it", "Vị trí phi công nghệ (cơ khí, sản xuất, kế toán, CSKH, may mặc...)"

    # ========================== CAREERVIET (77 tin) ==========================
    if source == "careerviet":
        # IT đích thực
        if "hệ thống ngân hàng lõi treasury" in t_lower:
            return "it", "Phát triển Core Banking / Khối CNTT"
        if "kiến trúc hệ thống" in t_lower:
            return "it", "System Architect / Khối Ngân hàng Số"
        if "phát triển ứng dụng" in t_lower and ("ngân hàng" in t_lower or "power platform" in t_lower):
            return "it", "Lập trình & phát triển ứng dụng phần mềm"
        if "kiểm thử ứng dụng" in t_lower:
            return "it", "Software Tester / QA"
        if "ruby on rails" in t_lower:
            return "it", "Senior Backend Ruby on Rails Developer"
        if "hạ tầng mạng" in t_lower or "quản lý kho và mô hình dữ liệu" in t_lower:
            return "it", "Data Warehouse / Network Architect"
        if "an ninh thông tin" in t_lower or "kiểm toán công nghệ thông tin" in t_lower:
            return "it", "Information Security / IT Auditor"
        if "phân tích nghiệp vụ" in t_lower and ("y tế" in t_lower or "dự án" in t_lower):
            return "it", "IT Business Analyst (BA)"
        if "business intelligence" in t_lower or "chuyên viên bi" in t_lower or "validation analyst (bi)" in t_lower:
            return "it", "Data BI Analyst"
        if "governance & compliance specialist" in t_lower and "it" in s_lower:
            return "it", "IT Governance & Compliance"
        if "kỹ sư giải pháp (pre-sales)" in t_lower:
            return "it", "Pre-sales Solutions Engineer"
        if "chuyên gia kiến trúc (sa)" in t_lower:
            return "it", "Solution Architect (SA)"
        if "mis specialist" in t_lower or "hệ thống thông tin quản lý" in t_lower:
            return "it", "MIS / SQL Specialist"
        return "non_it", "Vị trí phi IT (kinh doanh, kế toán, logistics, giáo viên, nhân sự...)"

    # ========================== JOBSGO (80 tin) ==========================
    if source == "jobsgo":
        if "artificial intelligence research intern" in t_lower:
            return "it", "AI Research Intern"
        if "senior brse" in t_lower:
            return "it", "Bridge Software Engineer (BrSE)"
        if "nhân viên trực vận hành" in t_lower and "hạ tầng - mạng" in s_lower:
            return "it", "Network Operation Center (NOC) / IT Operations"
        if "senior project manager" in t_lower and "it" in s_lower:
            return "it", "Senior IT Project Manager"
        if "chuyên viên quản lý dự án" in t_lower and "dự án it" in s_lower:
            return "it", "IT Project Manager"
        if "phân tích nghiệp vụ it" in t_lower:
            return "it", "IT Business Analyst (IT BA)"
        if "2d animator junior" in t_lower and "phát triển phần mềm" in s_lower:
            return "it", "Game Animator / Tech Art"
        return "non_it", "Vị trí phi IT (kinh doanh, bán hàng phần mềm, tuyển dụng IT, marketing...)"

    # ========================== TOPCV (80 tin) ==========================
    if source == "topcv":
        if "project manager" in t_lower and ("pm" in t_lower or "hạ tầng" in t_lower or "phần mềm" in s_lower or "hạ tầng" in s_lower):
            if "xây dựng" not in t_lower:
                return "it", "IT Project Manager / IT Infrastructure PM"
        if "kiến trúc hạ tầng mạng" in t_lower:
            return "it", "Network Infrastructure Architect"
        if "hạ tầng máy chủ" in t_lower:
            return "it", "System Engineer / Server Infrastructure"
        if "đảm bảo hoạt động hạ tầng thiết bị" in t_lower:
            return "it", "IT Infrastructure Support"
        if "computer vision" in t_lower:
            return "it", "Computer Vision / AI Engineer"
        if "3d animator" in t_lower or "3d render sử dụng maya" in t_lower:
            return "it", "Game 3D Art & Animation"
        if "vận hành cdp" in t_lower and "data labeling" in s_lower:
            return "it", "Customer Data Platform & Data Labeling Specialist"
        return "non_it", "Vị trí phi IT (Graphic Designer 2D, Sales phần mềm, Pre-sale bán hàng, Giảng viên...)"

    # ========================== VIECLAM24H (80 tin) ==========================
    if source == "vieclam24h":
        if "sửa máy tính" in t_lower or "sửa pc, laptop" in t_lower:
            return "it", "IT Hardware Support & Maintenance"
        if "ui & graphic designer (team erp)" in t_lower:
            return "it", "UI/UX Designer cho hệ thống ERP"
        return "non_it", "Vị trí phi IT (lái xe, giao hàng, telesales, CSKH, photocopy, dự toán xây dựng...)"

    # ========================== VIETNAMWORKS (80 tin) ==========================
    if source == "vietnamworks":
        if "tuyển dụng kỹ sư phát triển ứng dụng" in t_lower:
            return "it", "Software Application Developer (bị gắn nhầm nhãn do có chữ 'Tuyển dụng')"
        if "hr system & reporting specialist" in t_lower and "sql" in s_lower:
            return "it", "HR Tech / SQL & Power BI Data Specialist"
        if "data analyst" in t_lower:
            return "it", "Data Analyst (BI / Python / SQL)"
        if "kiến trúc sư phần mềm (sa)" in t_lower:
            return "it", "Software Architect (SA)"
        if "recruiting drone hardware development" in t_lower:
            return "it", "Drone Hardware Development Engineer"
        if "product director" in t_lower and "it" in s_lower:
            return "it", "IT Product Director"
        if "quản lý dự án" in t_lower and ("phần mềm" in s_lower or "scrum" in s_lower):
            return "it", "Software Project Manager (Scrum/Agile)"
        if "cybersecurity" in t_lower:
            return "it", "Cybersecurity, Tech Risk & Resilience Head"
        return "non_it", "Vị trí phi IT (General Accountant, HR, B2B Sales, Kỹ sư cơ khí, Logistics, Đấu thầu...)"

    # Fallback mặc định
    return "non_it", "Mặc định không phải IT"


def process_all() -> None:
    print("=" * 80)
    print("🚀 BẮT ĐẦU GÁN NHÃN TAY CHO TOÀN BỘ 8 NGUỒN (541 TIN REVIEW C4b)")
    print("=" * 80)

    summary: Dict[str, Dict[str, int]] = {}

    for src in SOURCES:
        path = REVIEW_DIR / f"it_{src}.csv"
        if not path.exists():
            print(f"⚠️ Không tìm thấy file {path}")
            continue

        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))

        it_count = 0
        non_it_count = 0

        for r in rows:
            label, reason = evaluate_job(src, r["job_id"], r["job_title"], r["skills"])
            r["nhan_tay"] = label
            if label == "it":
                it_count += 1
            else:
                non_it_count += 1

        summary[src] = {"total": len(rows), "it": it_count, "non_it": non_it_count}

        # Ghi đè lại file với UTF-8 BOM
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            for r in rows:
                writer.writerow({f: r.get(f, "") for f in FIELDS})

        print(f"✅ {src:<15}: Đã gán {len(rows)} tin -> IT: {it_count:>2}, Non-IT: {non_it_count:>2}")

    print("=" * 80)
    total_all = sum(s["total"] for s in summary.values())
    total_it = sum(s["it"] for s in summary.values())
    total_non_it = sum(s["non_it"] for s in summary.values())
    print(f"🎉 HOÀN TẤT GÁN NHÃN: {total_all} tin | IT: {total_it} | Non-IT: {total_non_it}")
    print("=" * 80)


if __name__ == "__main__":
    process_all()
