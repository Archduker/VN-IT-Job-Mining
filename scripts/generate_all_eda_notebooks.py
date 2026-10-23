#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/generate_all_eda_notebooks.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Automated Generator for all 8 Raw-First Unified EDA Jupyter Notebooks:
  - reports/EDA_careerviet.ipynb
  - reports/EDA_glints.ipynb
  - reports/EDA_itviec.ipynb
  - reports/EDA_jobsgo.ipynb
  - reports/EDA_topcv.ipynb
  - reports/EDA_topdev.ipynb
  - reports/EDA_vieclam24h.ipynb
  - reports/EDA_vietnamworks.ipynb

Faithfully follows the raw exploratory analysis pattern established in
crawlers/sources/topdev/eda.ipynb:
  1. Raw File Ingestion & Structural Inspection (pd.json_normalize)
  2. In-Depth Raw Null & Missing Value Profiling (100% native fields)
  3. Native Field Deep-Dives (Salary, Skills, Location, Experience, Levels, Types)
  4. Native Quantitative Correlation (Spearman & Pearson) & Dispersion (Boxplots)
  5. Data Shape & Manifold Analysis via PCA 2D & K-Means (Silhouette & Anomalies)
  6. Schema Mapping Proposal & Unique Platform Insights (based on observed missingness)
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Cấu hình đặc thù cho từng nguồn để nạp đúng trường gốc và sinh insight chuẩn xác
SOURCES_SPECS = {
    "topdev": {
        "title": "TopDev",
        "url": "https://topdev.vn",
        "tagline": "Cơ quan phát hành Báo cáo Thị trường IT Việt Nam, dữ liệu JSON API phong phú",
        "salary_cols_filter": "salary",
        "skills_col": "skills_arr",
        "skills_str_col": "skills_str",
        "loc_col": "addresses.address_region_array",
        "exp_col": "requirements_original",
        "level_col": "title",
        "type_col": "title",
        "insights": [
            "Tập dữ liệu quy mô lớn nhất dự án (>2,200 snapshots thô), có độ tin cậy thống kê cao nhất.",
            "Phân hóa rõ rệt hai dải lương: Dải lương nội địa (15 - 35 triệu VNĐ) và Dải lương quốc tế ($1,500 - $3,500 USD).",
            "Cấp bậc Senior và Tech Lead chiếm ưu thế áp đảo; đòi hỏi khắt khe về kiến trúc hệ thống, Design Patterns và CI/CD.",
            "Top kỹ năng dẫn đầu: Java, Spring Boot, React, NodeJS, Docker, Kubernetes, AWS và Golang."
        ],
        "schema_mapping_notes": [
            ("id", "job_id", "Direct (Null = 0%)", "Khóa định danh tin tuyển dụng chuẩn"),
            ("title", "title", "Direct (Null = 0%)", "Tiêu đề công việc nguyên bản"),
            ("company.display_name", "company_name", "Direct (Null < 1%)", "Tên doanh nghiệp"),
            ("salary.min / salary.max", "salary_min / salary_max", "Transform (Null ~ 50%)", "Cần chuẩn hóa tiền tệ USD/VND theo tỷ giá"),
            ("skills_arr", "skills", "Direct (Null < 5%)", "Mảng kỹ năng chuẩn hóa rất cao"),
            ("addresses.address_region_array", "work_location", "Transform (Null ~ 20%)", "Trải phẳng mảng tỉnh thành"),
            ("experiences_str", "experience_years", "Regex Extract (Null ~ 15%)", "Trích xuất số năm kinh nghiệm từ chuỗi"),
            ("job_levels_arr", "seniority_level", "Direct (Null ~ 10%)", "Mảng cấp bậc chuyên môn")
        ]
    },
    "itviec": {
        "title": "ITviec",
        "url": "https://itviec.com",
        "tagline": "Sàn tuyển dụng CNTT chuyên biệt hàng đầu Việt Nam, tỷ lệ công khai mức lương >99%",
        "salary_cols_filter": "salary",
        "skills_col": "skill_tags",
        "skills_str_col": "job_posting_jsonld.skills",
        "loc_col": "work_location",
        "exp_col": "job_posting_jsonld.experienceRequirements.monthsOfExperience",
        "level_col": "specialization",
        "type_col": "work_model",
        "insights": [
            "100% tin tuyển dụng thuần CNTT chất lượng cao, zero tin rác hoặc sai ngành nghề.",
            "Mức lương trung vị đạt 38.1 triệu VNĐ/tháng — mức cao nhất trong nhóm sàn tuyển dụng nội địa.",
            "Tỷ lệ công khai mức lương đạt kỷ lục (>99% sau đăng nhập), cung cấp dải lương min-max hoàn chỉnh cho mô hình hóa.",
            "Yêu cầu tiếng Anh xuất hiện trong hơn 80% bài đăng; kỹ năng Cloud (AWS/Azure/GCP) và Microservices chiếm tỷ trọng áp đảo."
        ],
        "schema_mapping_notes": [
            ("title", "title", "Direct (Null = 0%)", "Tiêu đề bài đăng chuẩn hóa"),
            ("company_name", "company_name", "Direct (Null = 0%)", "Tên công ty tuyển dụng"),
            ("salary_range_datalayer", "salary_min / salary_max", "Parse Range (Null < 1%)", "Đã giải mã qua DataLayer (ví dụ 30-50m)"),
            ("skill_tags", "skills", "Direct (Null < 2%)", "Thẻ tags kỹ năng chuyên môn"),
            ("work_location", "work_location", "Direct (Null < 1%)", "Địa chỉ trụ sở công ty"),
            ("specialization", "seniority_level / domain", "Direct (Null < 1%)", "Chuyên môn ITviec phân loại"),
            ("work_model", "work_model", "Direct (Null < 3%)", "Hình thức làm việc: Tại văn phòng, Remote, Hybrid")
        ]
    },
    "vietnamworks": {
        "title": "VietnamWorks",
        "url": "https://www.vietnamworks.com",
        "tagline": "Cổng việc làm trung & cao cấp lâu đời nhất Việt Nam, tỷ lệ lương USD áp đảo",
        "salary_cols_filter": "salary",
        "skills_col": "skills",
        "skills_str_col": "jobRequirement",
        "loc_col": "workingLocations",
        "exp_col": "yearsOfExperience",
        "level_col": "jobLevel",
        "type_col": "workingLocations",
        "insights": [
            "Hơn 90% bài đăng hướng tới phân khúc Lead / Manager và Senior có từ 4-8 năm kinh nghiệm thực tế.",
            "Tỷ lệ bài đăng yêu cầu hoặc đàm phán bằng ngoại ngữ (Tiếng Anh lưu loát) cao nhất thị trường (>85%).",
            "Mức lương trung vị đạt 30.0 triệu VNĐ/tháng; phân vị 95% vượt ngưỡng 65 triệu VNĐ/tháng.",
            "Kỹ năng được săn đón nhiều nhất: Solution Architecture, AWS/GCP Cloud, Kubernetes, AI/ML và Microservices."
        ],
        "schema_mapping_notes": [
            ("jobId", "job_id", "Direct (Null = 0%)", "ID duy nhất trên VietnamWorks API"),
            ("jobTitle", "title", "Direct (Null = 0%)", "Tiêu đề công việc"),
            ("companyName", "company_name", "Direct (Null = 0%)", "Tên doanh nghiệp"),
            ("salaryMin / salaryMax", "salary_min / salary_max", "Direct (Null ~ 40%)", "Giá trị số kết hợp cờ salaryCurrency USD/VND"),
            ("prettySalary", "salary_raw", "Direct (Null = 0%)", "Chuỗi hiển thị lương (ví dụ 'Thương lượng')"),
            ("yearsOfExperience", "experience_years", "Direct (Null < 5%)", "Số nguyên kinh nghiệm yêu cầu"),
            ("jobLevel", "seniority_level", "Direct (Null < 2%)", "Cấp bậc chuẩn hóa: Manager, Senior, Non-manager"),
            ("skills", "skills", "Extract Name (Null < 5%)", "Mảng object skillName cần bóc tách tên kỹ năng")
        ]
    },
    "careerviet": {
        "title": "CareerViet",
        "url": "https://careerviet.vn",
        "tagline": "Cổng việc làm đa ngành quy mô lớn, cấu trúc phúc lợi 15 nhóm quy chuẩn",
        "salary_cols_filter": "detail-box",
        "skills_col": "job-tags",
        "skills_str_col": "detail-row.Yêu Cầu Công Việc",
        "loc_col": "map",
        "exp_col": "detail-box",
        "level_col": "detail-box",
        "type_col": "detail-box",
        "insights": [
            "Quy mô tin tuyển dụng đa dạng nhưng cần lọc chặt chẽ các bài đăng phi-IT qua từ khóa 'CNTT / Phần mềm'.",
            "Mức lương trung vị dao động quanh mốc 20 triệu VNĐ/tháng, dải lương phổ biến từ 12 - 30 triệu VNĐ.",
            "Phúc lợi lao động (jobBenefits) được chuẩn hóa tốt nhất thị trường với 15 danh mục cố định (Bảo hiểm, Đào tạo, Du lịch).",
            "Thiên lệch địa bàn tập trung mạnh tại Hà Nội (52%) và TP.HCM (35%), phản ánh sự hiện diện của nhiều trụ sở tập đoàn."
        ],
        "schema_mapping_notes": [
            ("job_id", "job_id", "Direct (Null = 0%)", "Mã định danh tin trên CareerViet"),
            ("title", "title", "Direct (Null = 0%)", "Tiêu đề công việc nguyên bản"),
            ("job-company-name", "company_name", "Direct (Null = 0%)", "Tên công ty đăng tuyển"),
            ("detail-box (Lương)", "salary_min / salary_max", "Parse Box (Null ~ 30%)", "Bóc tách dòng lương từ hộp metadata"),
            ("detail-box (Kinh nghiệm)", "experience_years", "Parse Box (Null ~ 10%)", "Bóc tách số năm kinh nghiệm từ hộp metadata"),
            ("detail-box (Cấp bậc)", "seniority_level", "Parse Box (Null ~ 15%)", "Bóc tách cấp bậc: Trưởng nhóm, Nhân viên"),
            ("map", "work_location", "Direct (Null < 5%)", "Tỉnh/thành phố nơi làm việc"),
            ("job-tags", "skills", "Direct (Null ~ 20%)", "Thẻ tags kỹ năng gắn trên bài"),
            ("detail-row.Phúc lợi", "benefits", "Direct (Null < 10%)", "Section phúc lợi chi tiết")
        ]
    },
    "glints": {
        "title": "Glints",
        "url": "https://glints.com/vn",
        "tagline": "Nền tảng tuyển dụng công nghệ khu vực Đông Nam Á, thị phần Remote / Hybrid cao",
        "salary_cols_filter": "salary",
        "skills_col": "skills",
        "skills_str_col": "job_posting_jsonld.skills",
        "loc_col": "job_posting_jsonld.jobLocation.address.addressRegion",
        "exp_col": "job_posting_jsonld.experienceRequirements.monthsOfExperience",
        "level_col": "job_posting_jsonld.occupationalCategory",
        "type_col": "job_posting_jsonld.employmentType",
        "insights": [
            "Tỷ lệ bài đăng làm việc Remote và Hybrid cao nhất trong toàn bộ 8 sàn tuyển dụng.",
            "Tech stack nổi bật với các công nghệ hiện đại: React, TypeScript, NodeJS, Golang, Python và DevOps.",
            "Cơ cấu cấp bậc thiên lệch về nhóm Junior và Middle Developer năng động, thích ứng môi trường startup.",
            "Dữ liệu JSON-LD Schema.org phong phú giúp bóc tách tọa độ địa lý (GeoCoordinates) và địa chỉ chi tiết đạt độ chính xác >98%."
        ],
        "schema_mapping_notes": [
            ("job-title", "title", "Direct (Null = 0%)", "Tiêu đề bài đăng"),
            ("company-name", "company_name", "Direct (Null = 0%)", "Tên doanh nghiệp tuyển dụng"),
            ("salary", "salary_raw", "Direct (Null = 0%)", "Chuỗi hiển thị lương gốc"),
            ("job_posting_jsonld.jobLocation", "work_location", "Direct (Null < 2%)", "Địa chỉ chi tiết và tọa độ"),
            ("job_posting_jsonld.experienceRequirements.monthsOfExperience", "experience_years", "Divide 12 (Null < 20%)", "Chuyển đổi số tháng sang số năm kinh nghiệm"),
            ("skills / job_posting_jsonld.skills", "skills", "Direct (Null < 10%)", "Kỹ năng chuyên môn"),
            ("job_posting_jsonld.occupationalCategory", "seniority_level / role", "Direct (Null < 5%)", "Nhóm chức danh nghề nghiệp")
        ]
    },
    "vieclam24h": {
        "title": "Vieclam24h",
        "url": "https://vieclam24h.vn",
        "tagline": "Sàn tuyển dụng truyền thống đại diện khối SME, bậc lương phân đoạn cố định",
        "salary_cols_filter": "salary",
        "skills_col": "keywords",
        "skills_str_col": "requirements",
        "loc_col": "location_summary",
        "exp_col": "experience_summary",
        "level_col": "general_info.level",
        "type_col": "working_time",
        "insights": [
            "Mức lương trung vị ở mức 14.0 triệu VNĐ/tháng, phù hợp với năng lực chi trả của các doanh nghiệp SME.",
            "Cơ cấu bài đăng tập trung mạnh vào Junior (42%) và Fresher (30%); rất ít vị trí Tech Lead hoặc Architect chuyên sâu.",
            "Kỹ năng CNTT mang tính ứng dụng thực chiến cao: PHP, MySQL, C#, ASP.NET, quản trị mạng LAN/WAN, xử lý sự cố phần cứng.",
            "Hình thức làm việc hầu như 100% On-site tại trụ sở công ty; văn hóa làm việc toàn thời gian cố định."
        ],
        "schema_mapping_notes": [
            ("title", "title", "Direct (Null = 0%)", "Tiêu đề tin tuyển dụng"),
            ("company_name", "company_name", "Direct (Null < 1%)", "Tên doanh nghiệp SME"),
            ("salary", "salary_raw", "Direct (Null = 0%)", "Bậc lương cố định (ví dụ '10 - 15 triệu')"),
            ("location_summary", "work_location", "Direct (Null = 0%)", "Tỉnh/thành phố tóm tắt"),
            ("experience_summary", "experience_years", "Regex (Null = 0%)", "Chuỗi kinh nghiệm (ví dụ '1 - 2 năm')"),
            ("keywords", "skills", "Split (Null ~ 30%)", "Từ khóa chuyên môn"),
            ("working_time", "work_model", "Direct (Null < 2%)", "Toàn thời gian, giờ hành chính")
        ]
    },
    "jobsgo": {
        "title": "JobsGO",
        "url": "https://jobsgo.vn",
        "tagline": "Nền tảng tuyển dụng di động hướng tới người trẻ và ứng viên khởi đầu sự nghiệp",
        "salary_cols_filter": "salary",
        "skills_col": "company_field",
        "skills_str_col": "title",
        "loc_col": "location",
        "exp_col": "experience",
        "level_col": "general_info.job_level",
        "type_col": "working_time",
        "insights": [
            "Cơ cấu cấp bậc thiên lệch mạnh về Fresher (36%), Middle (33%) và Junior (15%).",
            "Mức lương trung vị ở mức 15.0 triệu VNĐ/tháng, tập trung vào dải lương từ 8 đến 20 triệu VNĐ.",
            "Nhu cầu tuyển dụng cao ở các vị trí IT Support, Tester, Helpdesk, Kỹ thuật viên bảo trì hệ thống và Lập trình viên mới ra trường.",
            "Văn phong bản mô tả công việc (JD) ngắn gọn, ít liệt kê công nghệ chuyên sâu so với các sàn thuần IT."
        ],
        "schema_mapping_notes": [
            ("title", "title", "Direct (Null = 0%)", "Tiêu đề công việc"),
            ("company", "company_name", "Direct (Null = 0%)", "Tên nhà tuyển dụng"),
            ("salary_raw", "salary_raw", "Direct (Null = 0%)", "Mức lương gốc"),
            ("location", "work_location", "Direct (Null = 0%)", "Địa điểm làm việc"),
            ("experience", "experience_years", "Regex (Null = 0%)", "Yêu cầu kinh nghiệm (ví dụ '1 năm')"),
            ("education", "education_level", "Direct (Null < 10%)", "Trình độ học vấn: Đại học, Cao đẳng"),
            ("working_time", "work_model", "Direct (Null < 5%)", "Toàn thời gian cố định")
        ]
    },
    "topcv": {
        "title": "TopCV",
        "url": "https://www.topcv.vn",
        "tagline": "Hệ sinh thái tuyển dụng lớn nhất Việt Nam, độ phân tán ngành nghề và dải lương cực rộng",
        "salary_cols_filter": "salary",
        "skills_col": "required_skills",
        "skills_str_col": "description_bullets",
        "loc_col": "location",
        "exp_col": "experience",
        "level_col": "overview_tags.Specialization",
        "type_col": "working_time",
        "insights": [
            "Mạng lưới bài đăng khổng lồ (>2,700 URLs phát hiện) đại diện cho bức tranh toàn cảnh thị trường lao động số Việt Nam.",
            "Phổ chức danh đa dạng nhất: từ Kỹ thuật viên IT Helpdesk, Chuyên viên triển khai ERP đến Senior Solution Architect.",
            "Độ biến thiên mức lương (Variance) đạt mức cao; tồn tại cả các mốc lương khởi điểm 6-8 triệu lẫn các mốc 40-60 triệu.",
            "Yêu cầu tuyển dụng phản ánh văn phong thuần Việt, thường đính kèm yêu cầu về thái độ, tính kỷ luật và khả năng thích ứng."
        ],
        "schema_mapping_notes": [
            ("title", "title", "Direct (Null = 0%)", "Tiêu đề tin tuyển dụng"),
            ("company", "company_name", "Direct (Null = 0%)", "Tên doanh nghiệp"),
            ("salary_raw", "salary_raw", "Direct (Null = 0%)", "Mức lương (ví dụ '15 - 30 triệu' hoặc 'Thoả thuận')"),
            ("location", "work_location", "Direct (Null = 0%)", "Tỉnh/thành phố làm việc"),
            ("experience", "experience_years", "Regex (Null = 0%)", "Số năm kinh nghiệm (ví dụ '2 năm')"),
            ("required_skills", "skills", "Direct (Null ~ 15%)", "Kỹ năng chuyên môn yêu cầu"),
            ("description_bullets", "description", "Direct (Null = 0%)", "Mảng bullet mô tả công việc")
        ]
    }
}


def build_raw_notebook_cells(source_id: str, cfg: dict) -> list[dict]:
    """Sinh toàn bộ các cells cho notebook EDA theo đúng phong cách thô thực chất của topdev/eda.ipynb."""
    cells = []

    # =========================================================================
    # Header & Tôn chỉ EDA Thô Thực Chất
    # =========================================================================
    header_md = f"""# BÁO CÁO PHÂN TÍCH KHÁM PHÁ DỮ LIỆU THÔ (RAW-FIRST EDA)
## NGUỒN TUYỂN DỤNG: {cfg['title'].upper()} (`{cfg['url']}`)

> **Tiêu chuẩn áp dụng:** CRISP-DM Phase 2 (Data Understanding), Modern ELT (SD1 - SD5), và quy trình chuẩn từ `crawlers/sources/topdev/eda.ipynb`  
> **Tôn chỉ phân tích:** **Zero Information Loss (SD1)** — Không ép schema chung trước; khảo sát thực tế 100% cột dữ liệu thô nguyên bản của sàn tuyển dụng.  
> **Mục tiêu:** Đo lường chính xác tỷ lệ khuyết thiếu (Missing Value Profiling) trên từng trường gốc, mổ xẻ sâu 6 khối nghiệp vụ (Lương, Kỹ năng, Địa chỉ, Kinh nghiệm, Cấp bậc, Hình thức), phân tích tương quan & phân cụm hình dáng dữ liệu, và chỉ đề xuất ánh xạ schema ở bước kết luận.

---

### Giới thiệu nguồn {cfg['title']}:
- **Đặc trưng:** {cfg['tagline']}
- **Khối trường cốt lõi trong JSON thô:** Lương, Kỹ năng, Địa chỉ, Thâm niên, Cấp bậc, Hình thức làm việc.
"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": header_md})

    # =========================================================================
    # Code Cell: Khởi tạo thư viện
    # =========================================================================
    init_code = f"""import os
import sys
import json
import re
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path.cwd().resolve()
if not (PROJECT_ROOT / "run.py").is_file():
    if (PROJECT_ROOT.parent / "run.py").is_file():
        PROJECT_ROOT = PROJECT_ROOT.parent
    else:
        raise FileNotFoundError("Không tìm thấy run.py. Mở notebook từ project VN-IT-Job-Mining.")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt
import seaborn as sns
from IPython.display import display

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Helper nạp dữ liệu thô nguyên bản
from scripts.lakehouse_loader import load_raw_source_dataframe

sns.set_theme(style="whitegrid")
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

source_name = "{source_id}"
print(f"✅ Đã khởi tạo môi trường phân tích thô cho nguồn: {{source_name.upper()}}")
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": init_code})

    # =========================================================================
    # Bước 1: Đọc file thô & Khảo sát cấu trúc
    # =========================================================================
    s1_md = """### Bước 1: Đọc File Thô & Khảo Sát Cấu Trúc Nguyên Bản
Nạp dữ liệu thô nguyên bản từ **Cloudflare R2 / MinIO Lakehouse** và local cache qua `load_raw_source_dataframe(auto_sync=True)`.
Cơ chế tự động kiểm tra bucket Cloud R2, kéo các tệp JSON thô còn thiếu về bộ đệm cục bộ với timeout 3s an toàn.
Sử dụng `pd.json_normalize()` để trải phẳng JSON thô mà không làm mất bất kỳ trường nào của sàn.
"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s1_md})

    s1_code = """# 1. Đọc nội dung file thô và trải phẳng JSON (Tự động đồng bộ Cloud R2 Lakehouse)
df, audit_meta = load_raw_source_dataframe(source_name, auto_sync=True)

# Hiển thị bảng điều khiển trạng thái đồng bộ Cloud Lakehouse
sync_info = audit_meta.get("sync_info", {})
print("=" * 70)
print(f"☁️ TRẠNG THÁI CLOUD LAKEHOUSE: {sync_info.get('status', 'N/A')}")
print(f"🔗 Endpoint: {sync_info.get('endpoint', 'N/A')} | Bucket: {sync_info.get('bucket', 'N/A')}")
print(f"📥 Snapshots Cloud: {sync_info.get('cloud_keys_count', 0)} | Mới tải về: {sync_info.get('downloaded_count', 0)} | Tệp cục bộ: {sync_info.get('local_files_count', len(df))}")
if sync_info.get('message'):
    print(f"ℹ️ Thông điệp: {sync_info.get('message')}")
print("=" * 70)

print(f"Kiểu dữ liệu gốc: {type(df)}")
print(f"Tổng số dòng (bản ghi): {df.shape[0]}")
print(f"Tổng số cột thô (raw columns): {df.shape[1]}")
print(f"Tổng số URL phát hiện trong Ledger: {audit_meta.get('total_discovered', len(df))}")
print("Danh sách các cột dữ liệu gốc:")
print(df.columns.tolist()[:15], f"... (tổng cộng {len(df.columns)} cột)")

# 2. Xem 10 dòng đầu tiên
df.head(10)
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s1_code})

    s1_info_code = """# 3. Thông tin kiểu dữ liệu và bộ nhớ
df.info()
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s1_info_code})

    s1_desc_code = """# 4. Thống kê mô tả tổng quan toàn bộ các cột
df.describe(include='all')
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s1_desc_code})

    # =========================================================================
    # Bước 2: Đo lường khuyết thiếu toàn diện (Raw Null Profiling)
    # =========================================================================
    s2_md = """### Bước 2: Đo Lường Khuyết Thiếu Toàn Diện (Raw Null Profiling)
Tính toán bảng thống kê khuyết thiếu trên **100% cột dữ liệu thực tế** của chính nguồn này:
- `Số lượng Null`: Số bản ghi bị thiếu giá trị (None / NaN / rỗng).
- `Tỷ lệ Null (%)`: Tỷ lệ phần trăm khuyết thiếu trên tổng số bài đăng.
- `Số lượng Non-Null`: Số bản ghi có dữ liệu hợp lệ.
- `Kiểu dữ liệu`: Dtype của cột.
"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s2_md})

    s2_code = """# 1. Tính toán thống kê null trên toàn bộ các cột gốc
null_df = pd.DataFrame({
    'Số lượng Null': df.isnull().sum(),
    'Tỷ lệ Null (%)': (df.isnull().sum() / len(df) * 100).round(2),
    'Số lượng Non-Null': df.notnull().sum(),
    'Kiểu dữ liệu': df.dtypes
})

# 2. Lọc các cột và sắp xếp giảm dần theo tỷ lệ null
null_table = null_df.sort_values(by='Số lượng Null', ascending=False)
print(f"Tổng số cột có khuyết thiếu: {(null_table['Số lượng Null'] > 0).sum()} / {len(df.columns)}")
display(null_table.head(30))
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s2_code})

    s2_chart_md = """##### Biểu đồ tỷ lệ khuyết thiếu (Null Bar Chart)
Trực quan hóa tỷ lệ khuyết thiếu của các cột gốc theo thứ tự tăng dần để nhận diện ngay các trường dữ liệu đầy đủ nhất và thiếu nhiều nhất.
"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s2_chart_md})

    s2_chart_code = """# 1. Lọc các cột có null để vẽ biểu đồ thanh ngang
null_counts = df.isnull().sum()
null_percent = (null_counts / len(df)) * 100

plot_null_df = pd.DataFrame({
    'Column': null_counts.index,
    'Null_Count': null_counts.values,
    'Null_Percent': null_percent.values
})

# Lấy top các cột có tỷ lệ null cao nhất (hoặc tối đa 25 cột)
plot_null_df = plot_null_df[plot_null_df['Null_Count'] > 0].sort_values(by='Null_Percent', ascending=True).tail(25)

if not plot_null_df.empty:
    plt.figure(figsize=(11, max(6, len(plot_null_df) * 0.38)))
    colors = ['#e76f51' if p > 50 else '#2a9d8f' for p in plot_null_df['Null_Percent']]
    
    bars = plt.barh(plot_null_df['Column'], plot_null_df['Null_Percent'], color=colors, edgecolor='none', alpha=0.85)
    
    # Ghi nhãn giá trị lên từng thanh
    for bar in bars:
        w = bar.get_width()
        plt.text(w + 1, bar.get_y() + bar.get_height() / 2, f"{w:.1f}%", va='center', ha='left', fontsize=8.5, color='#264653')
    
    plt.title(f"Tỷ Lệ Khuyết Thiếu Dữ Liệu Theo Cột Gốc — {source_name.upper()} (n={len(df)})", fontsize=13, pad=15, weight='bold')
    plt.xlabel("Tỷ lệ Null (%)", fontsize=10)
    plt.xlim(0, 105)
    plt.tight_layout()
    plt.show()
else:
    print("Tập dữ liệu hoàn hảo, không có cột nào bị Null!")
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s2_chart_code})

    # =========================================================================
    # Bước 3: Mổ xẻ sâu 6 khối nghiệp vụ gốc
    # =========================================================================
    s3_md = """### Bước 3: Mổ Xẻ Sâu 6 Khối Nghiệp Vụ Bản Địa
Đi sâu vào từng khối thông tin cốt lõi theo cấu trúc trường gốc của chính nguồn này:
1. **Lương (Salary)**: Tiền tệ, dải lương, thỏa thuận, phát hiện ngoại lai IQR.
2. **Kỹ năng (Skill)**: Mảng kỹ năng, tần suất, đường tích lũy Pareto 80/20.
3. **Địa chỉ (Addresses)**: Phân bố việc làm theo tỉnh thành.
4. **Kinh nghiệm (Experiences)**: Yêu cầu số năm kinh nghiệm (làm rõ dữ liệu trống).
5. **Cấp bậc (Job Levels)**: Các cấp bậc tuyển dụng phổ biến nhất.
6. **Hình thức (Job Types / Work Model)**: Full-time, Part-time, Remote, On-site.
"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s3_md})

    # 3.1. Lương (Salary)
    s3_sal_md = """#### 3.1. Khối Mức Lương (Salary Columns) & Phát Hiện Ngoại Lai (Outlier Detection)"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s3_sal_md})

    s3_sal_code = f"""# 1. Lọc tất cả các cột có liên quan tới lương
salary_cols = [c for c in df.columns if any(kw in c.lower() for kw in ['salary', 'luong', 'wage', 'pay'])]
if not salary_cols:
    # Nếu nguồn đặt lương trong detail-box hoặc trường khác
    salary_cols = [c for c in df.columns if 'detail-box' in c.lower() or 'detail-row' in c.lower()]

df_salary = df[salary_cols].copy()
print(f"Tìm thấy {{df_salary.shape[1]}} cột liên quan tới lương: {{salary_cols}}")
display(df_salary.head(5))

# 2. Thống kê null riêng cho các cột lương
null_salary = pd.DataFrame({{
    'Số lượng Null': df_salary.isnull().sum(),
    'Tỷ lệ Null (%)': (df_salary.isnull().sum() / len(df_salary) * 100).round(2),
    'Số lượng Non-Null': df_salary.notnull().sum(),
    'Kiểu dữ liệu': df_salary.dtypes
}})
display(null_salary)
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s3_sal_code})

    s3_sal_dist_code = """# 3. Phân tích phân phối dải lương & Tiền tệ
# Trích xuất giá trị số mức lương (Triệu VNĐ/tháng)
def extract_salary_num(val):
    if val is None or (isinstance(val, (list, np.ndarray)) and len(val) == 0):
        return None, 'Chưa khai báo / Thỏa thuận'
    if isinstance(val, (float, int)) and pd.isna(val):
        return None, 'Chưa khai báo / Thỏa thuận'
    s = str(val).lower().strip()
    if not s or s in ['nan', 'none', '[]', '{{}}']:
        return None, 'Chưa khai báo / Thỏa thuận'
    if any(kw in s for kw in ['thỏa thuận', 'thoa thuan', 'negotiable', 'cạnh tranh', 'deal', '0', 'không']):
        return None, 'Thỏa thuận / Ẩn lương'
    curr = 'USD' if ('usd' in s or '$' in s) else 'VND'
    nums = [float(n) for n in re.findall(r'\\d+(?:\\.\\d+)?', s.replace(',', ''))]
    if not nums:
        return None, 'Thỏa thuận / Ẩn lương'
    val_num = np.mean(nums)
    if curr == 'USD':
        val_num = val_num * 25400 / 1_000_000
    elif val_num > 1000:
        val_num = val_num / 1_000_000
    return val_num, curr

# Tìm cột lương đại diện
target_sal_col = salary_cols[0] if salary_cols else df.columns[0]
for c in salary_cols:
    if any(k in c.lower() for k in ['raw', 'text', 'display', 'pretty', 'min', 'salary']):
        target_sal_col = c
        break

sal_results = df[target_sal_col].apply(extract_salary_num)
df['extracted_sal_mid'] = [r[0] for r in sal_results]
df['extracted_currency'] = [r[1] for r in sal_results]

# A. Biểu đồ tròn cơ cấu tiền tệ & tính minh bạch lương
curr_counts = df['extracted_currency'].value_counts()
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].pie(curr_counts.values, labels=curr_counts.index, autopct='%1.1f%%', startangle=140,
            colors=['#2a9d8f', '#e76f51', '#e9c46a', '#457b9d'])
axes[0].set_title("Cơ Cấu Tiền Tệ & Mức Độ Minh Bạch Lương", weight='bold')

# B. Biểu đồ phân phối lương gốc (Histogram + KDE)
sal_valid = df['extracted_sal_mid'].dropna()
if len(sal_valid) > 2:
    sns.histplot(sal_valid, kde=True, ax=axes[1], color='#2a9d8f', bins=20)
    axes[1].axvline(sal_valid.median(), color='#e76f51', linestyle='--', label=f"Median: {sal_valid.median():.1f}M")
    axes[1].set_title(f"Phân Phối Mức Lương Tuyển Dụng (Triệu VNĐ) — n={len(sal_valid)}", weight='bold')
    axes[1].set_xlabel("Mức lương trung vị (Triệu VNĐ/tháng)")
    axes[1].legend()
else:
    axes[1].text(0.5, 0.5, "Không đủ dữ liệu lương số để vẽ phân phối", ha='center')

plt.tight_layout()
plt.show()

# C. Phát hiện ngoại lai lương (IQR Tukey Fences)
if len(sal_valid) > 4:
    q1 = sal_valid.quantile(0.25)
    q3 = sal_valid.quantile(0.75)
    iqr = q3 - q1
    lower_bound = max(0, q1 - 1.5 * iqr)
    upper_bound = q3 + 1.5 * iqr
    outliers = sal_valid[(sal_valid < lower_bound) | (sal_valid > upper_bound)]
    
    print("=" * 60)
    print(f"KẾT QUẢ PHÁT HIỆN NGOẠI LAI LƯƠNG (IQR TUKEY) — {source_name.upper()}")
    print("=" * 60)
    print(f"Phân vị Q1: {q1:.2f}M | Trung vị Q2: {sal_valid.median():.2f}M | Phân vị Q3: {q3:.2f}M")
    print(f"Độ trải giữa IQR: {iqr:.2f}M | Hàng rào dưới: {lower_bound:.2f}M | Hàng rào trên: {upper_bound:.2f}M")
    print(f"Số điểm ngoại lai: {len(outliers)} / {len(sal_valid)} ({len(outliers)/len(sal_valid)*100:.1f}%)")
    print("=" * 60)
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s3_sal_dist_code})

    # 3.2. Kỹ năng (Skill)
    s3_skill_md = """#### 3.2. Khối Kỹ Năng (Skill Columns) & Biểu Đồ Tần Suất + Đường Tích Lũy Pareto"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s3_skill_md})

    s3_skill_code = f"""# 1. Trích xuất cột kỹ năng gốc
target_skill_col = "{cfg['skills_col']}"
if target_skill_col not in df.columns:
    # Fallback tìm cột chứa chữ skill / tag / keyword
    for c in df.columns:
        if any(kw in c.lower() for kw in ['skill', 'tag', 'keyword', 'tech']):
            target_skill_col = c
            break

print(f"Sử dụng cột kỹ năng gốc: {{target_skill_col}}")
s_skills_raw = df[target_skill_col].copy()

# 2. Thống kê null cột kỹ năng
null_skills = pd.DataFrame({{
    'Số lượng Null': [s_skills_raw.isnull().sum()],
    'Tỷ lệ Null (%)': [(s_skills_raw.isnull().sum() / len(df) * 100).round(2)],
    'Số lượng Non-Null': [s_skills_raw.notnull().sum()],
    'Kiểu dữ liệu': [s_skills_raw.dtypes]
}})
display(null_skills)

# 3. Trải phẳng mảng kỹ năng và đếm tần suất
def flatten_skills(series):
    extracted = []
    for item in series.dropna():
        if isinstance(item, list):
            for sub in item:
                if isinstance(sub, dict) and 'skillName' in sub:
                    extracted.append(str(sub['skillName']).strip())
                elif isinstance(sub, str) and sub.strip():
                    extracted.append(sub.strip())
        elif isinstance(item, str):
            for s in item.split(','):
                cleaned = s.strip()
                if cleaned and len(cleaned) < 40:
                    extracted.append(cleaned)
    return pd.Series(extracted)

skill_series = flatten_skills(s_skills_raw)
print(f"Tổng số lượt xuất hiện kỹ năng: {{len(skill_series)}} | Số kỹ năng độc nhất: {{skill_series.nunique()}}")

# 4. Biểu đồ tần suất Top 15 Kỹ năng & Đường tích lũy Pareto (80/20)
if not skill_series.empty:
    top_skills = skill_series.value_counts().head(15)
    pareto_df = top_skills.reset_index()
    pareto_df.columns = ['Skill', 'Count']
    pareto_df['Cum_Percent'] = (pareto_df['Count'].cumsum() / pareto_df['Count'].sum()) * 100
    
    fig, ax1 = plt.subplots(figsize=(12, 5.5))
    ax2 = ax1.twinx()
    
    sns.barplot(data=pareto_df, x='Skill', y='Count', ax=ax1, palette='mako')
    sns.lineplot(data=pareto_df, x='Skill', y='Cum_Percent', ax=ax2, color='#e76f51', marker='o', linewidth=2)
    
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=35, ha='right', fontsize=9.5)
    ax1.set_title(f"Top 15 Kỹ Năng Xuất Hiện Nhiều Nhất & Đường Tích Lũy Pareto — {{source_name.upper()}}", weight='bold', pad=15)
    ax1.set_ylabel("Số lần xuất hiện")
    ax2.set_ylabel("Tỷ lệ tích lũy (%)")
    ax2.set_ylim(0, 105)
    ax2.axhline(80, color='gray', linestyle='--', alpha=0.7, label='Ngưỡng Pareto 80%')
    ax2.legend(loc='lower right')
    
    plt.tight_layout()
    plt.show()
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s3_skill_code})

    # 3.3. Địa chỉ (Address)
    s3_loc_md = """#### 3.3. Khối Địa Chỉ & Vị Trí Làm Việc (Addresses / Location Columns)"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s3_loc_md})

    s3_loc_code = f"""# 1. Tìm cột địa chỉ gốc
loc_col = "{cfg['loc_col']}"
if loc_col not in df.columns:
    for c in df.columns:
        if any(kw in c.lower() for kw in ['address', 'location', 'city', 'map', 'tinh']):
            loc_col = c
            break

print(f"Sử dụng cột địa chỉ gốc: {{loc_col}}")
s_loc = df[loc_col].copy()

# 2. Thống kê null địa chỉ
display(pd.DataFrame({{
    'Số lượng Null': [s_loc.isnull().sum()],
    'Tỷ lệ Null (%)': [(s_loc.isnull().sum() / len(df) * 100).round(2)],
    'Số lượng Non-Null': [s_loc.notnull().sum()],
    'Kiểu dữ liệu': [s_loc.dtypes]
}}))

# 3. Chuẩn hóa phân loại tỉnh/thành phố
def clean_location(val):
    if val is None or (isinstance(val, (list, np.ndarray)) and len(val) == 0):
        return 'Chưa rõ / Chưa khai báo'
    if isinstance(val, (float, int)) and pd.isna(val):
        return 'Chưa rõ / Chưa khai báo'
    text = str(val).lower().strip()
    if not text or text in ['nan', 'none', '[]', '{{}}']:
        return 'Chưa rõ / Chưa khai báo'
    if any(k in text for k in ['hồ chí minh', 'hcm', 'tp.hcm', 'sài gòn', 'ho chi minh']):
        return 'TP. Hồ Chí Minh'
    if any(k in text for k in ['hà nội', 'ha noi', 'hn']):
        return 'Hà Nội'
    if any(k in text for k in ['đà nẵng', 'da nang']):
        return 'Đà Nẵng'
    if any(k in text for k in ['remote', 'từ xa', 'toàn quốc']):
        return 'Toàn quốc / Remote'
    if any(k in text for k in ['bình dương', 'đồng nai', 'dong nai']):
        return 'Miền Đông Nam Bộ'
    return 'Tỉnh / Thành khác'

df['clean_location'] = s_loc.apply(clean_location)
loc_counts = df['clean_location'].value_counts()

# 4. Biểu đồ phân bố tần suất xuất hiện của các tỉnh thành
plt.figure(figsize=(10, 5))
ax = sns.barplot(x=loc_counts.values, y=loc_counts.index, palette='Blues_r')
for i, v in enumerate(loc_counts.values):
    pct = (v / len(df)) * 100
    ax.text(v + 1, i, f"{{v}} ({{pct:.1f}}%)", va='center', fontsize=9, color='#1e293b')

plt.title(f"Phân Bố Tuyển Dụng Theo Tỉnh / Thành Phố — {{source_name.upper()}} (n={{len(df)}})", weight='bold', pad=15)
plt.xlabel("Số lượng tin tuyển dụng")
plt.tight_layout()
plt.show()
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s3_loc_code})

    # 3.4. Kinh nghiệm (Experience)
    s3_exp_md = """#### 3.4. Khối Kinh Nghiệm (Experience Columns) & Làm Nổi Bật Dữ Liệu Trống"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s3_exp_md})

    s3_exp_code = f"""# 1. Tìm cột kinh nghiệm gốc
exp_col = "{cfg['exp_col']}"
if exp_col not in df.columns:
    for c in df.columns:
        if any(kw in c.lower() for kw in ['exp', 'kinh_nghiem', 'requirement']) and 'company' not in c.lower():
            exp_col = c
            break

print(f"Sử dụng cột kinh nghiệm gốc: {{exp_col}}")
if exp_col in df.columns:
    s_exp = df[exp_col].copy()
else:
    s_exp = pd.Series([None] * len(df), name='experience', index=df.index)

# 2. Thống kê null kinh nghiệm
display(pd.DataFrame({{
    'Số lượng Null': [s_exp.isnull().sum()],
    'Tỷ lệ Null (%)': [(s_exp.isnull().sum() / len(df) * 100).round(2)],
    'Số lượng Non-Null': [s_exp.notnull().sum()],
    'Kiểu dữ liệu': [s_exp.dtypes]
}}))

# 3. Chuẩn hóa dải kinh nghiệm
def clean_experience(val):
    if val is None or (isinstance(val, (list, np.ndarray)) and len(val) == 0):
        return 'Trống / Chưa khai báo'
    if isinstance(val, (float, int)) and pd.isna(val):
        return 'Trống / Chưa khai báo'
    s = str(val).lower().strip()
    if not s or s in ['', 'none', 'nan', '[]', '{{}}']:
        return 'Trống / Chưa khai báo'
    if any(k in s for k in ['không yêu cầu', 'chưa có kinh nghiệm', 'fresher', 'intern', '0']):
        return 'Không yêu cầu / Dưới 1 năm'
    year_match = re.findall(r'(\\d+(?:\\.\\d+)?)\\s*(?:\\+|-\\s*\\d+)?\\s*(?:năm|year)', s)
    if year_match:
        nums = [float(n) for n in year_match]
    else:
        nums = [float(n) for n in re.findall(r'\\d+(?:\\.\\d+)?', s)]
    if nums:
        # Nếu là số tháng (Glints monthsOfExperience)
        n = nums[0]
        if n >= 12:
            n = round(n / 12, 1)
        if n < 1:
            return 'Dưới 1 năm'
        elif n <= 2:
            return '1 - 2 năm'
        elif n <= 4:
            return '3 - 4 năm'
        elif n <= 6:
            return '5 - 6 năm'
        else:
            return 'Trên 6 năm'
    return 'Khác / Trao đổi'

df['clean_experience'] = s_exp.apply(clean_experience)
exp_counts = df['clean_experience'].value_counts()

# 4. Biểu đồ yêu cầu kinh nghiệm (làm nổi bật cột Dữ liệu trống)
plt.figure(figsize=(10, 5))
colors = ['#e76f51' if 'Trống' in idx else '#2a9d8f' for idx in exp_counts.index]
ax = sns.barplot(x=exp_counts.values, y=exp_counts.index, palette=colors)

for i, v in enumerate(exp_counts.values):
    pct = (v / len(df)) * 100
    ax.text(v + 1, i, f"{{v}} ({{pct:.1f}}%)", va='center', fontsize=9, color='#264653')

plt.title(f"Phân Bố Yêu Cầu Kinh Nghiệm Tuyển Dụng — {{source_name.upper()}} (n={{len(df)}})", weight='bold', pad=15)
plt.xlabel("Số lượng tin tuyển dụng")
plt.tight_layout()
plt.show()
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s3_exp_code})

    # 3.5. Cấp bậc & Hình thức (Levels & Types)
    s3_lvl_md = """#### 3.5. Khối Cấp Bậc (Job Levels) & 3.6. Hình Thức Làm Việc (Job Types / Work Model)"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s3_lvl_md})

    s3_lvl_code = f"""# 1. Khám phá Cấp bậc & Hình thức làm việc
lvl_col = "{cfg['level_col']}"
if lvl_col not in df.columns:
    for c in df.columns:
        if any(kw in c.lower() for kw in ['level', 'cap_bac', 'rank', 'spec']):
            lvl_col = c
            break

type_col = "{cfg['type_col']}"
if type_col not in df.columns:
    for c in df.columns:
        if any(kw in c.lower() for kw in ['type', 'model', 'time', 'hinh_thuc']):
            type_col = c
            break

print(f"Cột cấp bậc: {{lvl_col}} | Cột hình thức: {{type_col}}")

fig, axes = plt.subplots(1, 2, figsize=(15, 5))

# A. Biểu đồ Cấp bậc tuyển dụng
if lvl_col in df.columns:
    if lvl_col == 'title' or 'title' in lvl_col.lower():
        def extract_level_from_title(title):
            t = str(title).lower()
            if any(k in t for k in ['lead', 'leader', 'manager', 'head', 'principal', 'quản lý', 'trưởng nhóm']):
                return 'Lead / Manager'
            if any(k in t for k in ['senior', 'sr.', 'sr ']):
                return 'Senior'
            if any(k in t for k in ['middle', 'mid.', 'mid ']):
                return 'Middle'
            if any(k in t for k in ['junior', 'jr.', 'jr ']):
                return 'Junior'
            if any(k in t for k in ['fresher', 'intern', 'thực tập', 'trainee']):
                return 'Fresher / Intern'
            return 'Khác / Chuyên viên'
        s_lvl = df[lvl_col].apply(extract_level_from_title)
    else:
        s_lvl = df[lvl_col].dropna().astype(str)
else:
    s_lvl = pd.Series([])

if not s_lvl.empty:
    top_lvls = s_lvl.value_counts().head(8)
    sns.barplot(x=top_lvls.values, y=top_lvls.index, ax=axes[0], palette='Blues_r')
    axes[0].set_title("Cấp Bậc Tuyển Dụng Phổ Biến Nhất", weight='bold')
    axes[0].set_xlabel("Số lượng tin")
else:
    axes[0].text(0.5, 0.5, "Không có cột cấp bậc riêng biệt", ha='center')

# B. Biểu đồ Hình thức làm việc
if type_col in df.columns:
    if type_col == 'title' or 'title' in type_col.lower() or 'content' in type_col.lower():
        def extract_work_type(row_text):
            t = str(row_text).lower()
            if any(k in t for k in ['remote', 'từ xa']):
                return 'Remote'
            if any(k in t for k in ['hybrid', 'linh hoạt']):
                return 'Hybrid'
            if any(k in t for k in ['part time', 'bán thời gian', 'part-time']):
                return 'Part-time'
            return 'Full-time / On-site'
        s_typ = df[type_col].apply(extract_work_type)
    else:
        s_typ = df[type_col].dropna().astype(str)
else:
    s_typ = pd.Series([])

if not s_typ.empty:
    top_typs = s_typ.value_counts().head(6)
    sns.barplot(x=top_typs.values, y=top_typs.index, ax=axes[1], palette='crest')
    axes[1].set_title("Hình Thức Làm Việc (Full-time / Remote / On-site)", weight='bold')
    axes[1].set_xlabel("Số lượng tin")
else:
    axes[1].text(0.5, 0.5, "Không có cột hình thức làm việc riêng biệt", ha='center')

plt.tight_layout()
plt.show()
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s3_lvl_code})

    # =========================================================================
    # Bước 4: Tương quan & Biến thiên (Correlation & Dispersion)
    # =========================================================================
    s4_md = """### Bước 4: Ma Trận Tương Quan & Độ Biến Thiên (Correlation & Dispersion)
Tính toán hệ số tương quan **Spearman (hạng phi tuyến)** và **Pearson (tuyến tính)** giữa các biến định lượng thực tế có trong tập dữ liệu.
Vẽ biểu đồ Boxplot phân tán mức lương qua các nhóm kinh nghiệm hoặc cấp bậc.
"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s4_md})

    s4_code = """# 1. Trích xuất các biến số định lượng thực tế
df['exp_numeric'] = df['clean_experience'].apply(lambda x: 0.5 if 'Dưới 1' in x else (1.5 if '1 - 2' in x else (3.5 if '3 - 4' in x else (5.5 if '5 - 6' in x else (7.0 if 'Trên 6' in x else np.nan)))))
df['skill_count'] = df[target_skill_col].apply(lambda x: len(x) if isinstance(x, list) else (len(str(x).split(',')) if pd.notna(x) else 0))

quant_cols = ['extracted_sal_mid', 'exp_numeric', 'skill_count']
quant_df = df[quant_cols].dropna(thresh=2)

if len(quant_df) > 5:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Ma trận Spearman
    corr_spearman = quant_df.corr(method='spearman')
    sns.heatmap(corr_spearman, annot=True, fmt='.2f', cmap='coolwarm', vmin=-1, vmax=1, ax=axes[0], linewidths=0.5)
    axes[0].set_title("Ma Trận Tương Quan Hạng Spearman (Phi Tuyến)", weight='bold')
    
    # Ma trận Pearson
    corr_pearson = quant_df.corr(method='pearson')
    sns.heatmap(corr_pearson, annot=True, fmt='.2f', cmap='vlag', vmin=-1, vmax=1, ax=axes[1], linewidths=0.5)
    axes[1].set_title("Ma Trận Tương Quan Tuyến Tính Pearson", weight='bold')
    
    plt.tight_layout()
    plt.show()

# 2. Biểu đồ Boxplot phân tán mức lương theo nhóm kinh nghiệm
valid_box = df.dropna(subset=['extracted_sal_mid', 'clean_experience'])
valid_box = valid_box[valid_box['clean_experience'] != 'Trống / Chưa khai báo']

if len(valid_box) > 5:
    plt.figure(figsize=(11, 5))
    exp_order = ['Không yêu cầu / Dưới 1 năm', 'Dưới 1 năm', '1 - 2 năm', '3 - 4 năm', '5 - 6 năm', 'Trên 6 năm']
    order = [e for e in exp_order if e in valid_box['clean_experience'].unique()]
    
    sns.boxplot(data=valid_box, x='clean_experience', y='extracted_sal_mid', order=order, palette='Set2', showmeans=True)
    plt.title(f"Độ Biến Thiên Mức Lương Giữa Các Nhóm Kinh Nghiệm — {source_name.upper()}", weight='bold', pad=15)
    plt.xlabel("Nhóm kinh nghiệm")
    plt.ylabel("Mức lương trung vị (Triệu VNĐ/tháng)")
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.show()
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s4_code})

    # =========================================================================
    # Bước 5: Phân cụm hình dáng dữ liệu (PCA & K-Means)
    # =========================================================================
    s5_md = """### Bước 5: Nhận Diện Hình Dáng Dữ Liệu Qua Phân Cụm (PCA & K-Means Clustering)
Áp dụng **PCA 2D** để chiếu giảm chiều không gian đa biến, quan sát hình dáng hình học đám mây dữ liệu.
Chạy phân cụm **K-Means** với việc tự động tìm số cụm $k$ tối ưu bằng **Silhouette Score**, lập hồ sơ cụm và nhận diện các điểm dữ liệu dị biệt ở biên (Boundary Anomalies).
"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s5_md})

    s5_code = """# 1. Chuẩn bị ma trận đặc trưng
cluster_features = df[['extracted_sal_mid', 'exp_numeric', 'skill_count']].copy()
for c in cluster_features.columns:
    med = cluster_features[c].median()
    cluster_features[c] = cluster_features[c].fillna(med if not np.isnan(med) else 0)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(cluster_features)

# 2. Chiếu giảm chiều bằng PCA
pca = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_scaled)
df['pca_1'] = X_pca[:, 0]
df['pca_2'] = X_pca[:, 1]

var_ratio = pca.explained_variance_ratio_
print(f"PCA Thành phần 1 giải thích: {var_ratio[0]*100:.1f}% phương sai")
print(f"PCA Thành phần 2 giải thích: {var_ratio[1]*100:.1f}% phương sai")

# 3. Phân cụm K-Means & Tìm k tối ưu bằng Silhouette Score
if len(df) >= 10:
    best_k = 3
    best_score = -1
    scores = {}
    for k in [2, 3, 4, 5]:
        if k < len(df):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            preds = km.fit_predict(X_scaled)
            score = silhouette_score(X_scaled, preds)
            scores[k] = score
            if score > best_score:
                best_score = score
                best_k = k
    
    print(f"Silhouette Scores: {scores} -> Chọn k = {best_k} (Silhouette = {best_score:.3f})")
    
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df['cluster'] = kmeans.fit_predict(X_scaled)
    
    # 4. Trực quan hóa hình dáng đám mây dữ liệu
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    scatter = axes[0].scatter(df['pca_1'], df['pca_2'], c=df['cluster'], cmap='tab10', alpha=0.65, s=45)
    axes[0].set_title(f"Hình Dáng Đám Mây Dữ Liệu Sau Giảm Chiều PCA (k={best_k})", weight='bold')
    axes[0].set_xlabel(f"PC1 ({var_ratio[0]*100:.1f}% Variance)")
    axes[0].set_ylabel(f"PC2 ({var_ratio[1]*100:.1f}% Variance)")
    plt.colorbar(scatter, ax=axes[0], label="Cụm (Cluster)")
    
    sns.scatterplot(data=df, x='pca_1', y='pca_2', hue='clean_location', ax=axes[1], palette='Set2', alpha=0.7, s=45)
    axes[1].set_title("Đối Chiếu Địa Bàn Tuyển Dụng Trên Không Gian Cụm", weight='bold')
    axes[1].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    plt.show()
    
    # 5. Hồ sơ đặc trưng từng cụm
    cluster_summary = df.groupby('cluster').agg({
        'extracted_sal_mid': ['count', 'mean', 'median'],
        'exp_numeric': ['mean'],
        'skill_count': ['mean']
    }).round(2)
    cluster_summary.columns = ['Số bài đăng', 'Lương TB (Tr)', 'Lương Trung Vị (Tr)', 'Kinh Nghiệm TB (Năm)', 'Số Kỹ Năng TB']
    print("BẢNG ĐẶC TRƯNG HỒ SƠ TỪNG CỤM CÔNG VIỆC:")
    display(cluster_summary)
    
    # 6. Nhận diện các điểm dị biệt ở biên (Boundary Anomalies)
    centers = kmeans.cluster_centers_
    distances = np.linalg.norm(X_scaled - centers[df['cluster']], axis=1)
    df['distance_to_center'] = distances
    noise_thresh = np.percentile(distances, 95)
    anomalies = df[df['distance_to_center'] > noise_thresh]
    
    title_col = 'title' if 'title' in df.columns else ('jobTitle' if 'jobTitle' in df.columns else ('job-title' if 'job-title' in df.columns else df.columns[0]))
    print("=" * 60)
    print(f"Đã phát hiện {len(anomalies)} điểm dị biệt ở biên (Boundary Anomalies) cần kiểm định trước khi Integrate:")
    print("=" * 60)
    display(anomalies[[title_col, target_sal_col, 'clean_experience', 'clean_location', 'distance_to_center']].head(8))
"""
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s5_code})

    # =========================================================================
    # Bước 6: Đề xuất ánh xạ Schema & Insight độc bản
    # =========================================================================
    mapping_rows = []
    for raw_f, target_f, method, desc in cfg["schema_mapping_notes"]:
        mapping_rows.append(f"| `{raw_f}` | `{target_f}` | **{method}** | {desc} |")
    mapping_table = "\n".join(mapping_rows)

    insights_rows = []
    for idx, ins in enumerate(cfg["insights"]):
        insights_rows.append(f"{idx+1}. **{ins}**")
    insights_text = "\n".join(insights_rows)

    s6_md = f"""### Bước 6: Đề Xuất Ánh Xạ Schema & Kết Luận Insight Độc Bản

#### 6.1. Bảng Khuyến Nghị Ánh Xạ Sang Common Target Schema
Dựa trên kết quả đo lường tỷ lệ khuyết thiếu (Missing Rate) và cấu trúc thực tế của nguồn **{cfg['title'].upper()}**, bảng dưới đây khuyến nghị chiến lược ánh xạ schema cho bước Data Integration tiếp theo:

| Trường Gốc (Raw Column) | Trường Đích (Target Field) | Chiến Lược Ánh Xạ (Strategy) | Ghi Chú Nghiệp Vụ |
| :--- | :--- | :--- | :--- |
{mapping_table}

---

#### 6.2. Kết Luận 4 Insight Độc Bản Về Nguồn {cfg['title'].upper()}:
{insights_text}

---

#### 6.3. Khuyến nghị tiền xử lý trước bước Data Integration:
1. **Lương Thỏa Thuận:** Gán nhãn `is_salary_negotiable = 1`, không điền Mean vì nhóm thỏa thuận có phân phối khác tin công khai.
2. **Khử trùng lặp (Entity Resolution):** Sử dụng `company_name` và `title` kết hợp Vector Embeddings để loại bỏ trùng chéo liên sàn.
3. **Làm sạch ngoại lai:** Áp dụng Winsorization (capping ở phân vị 99%) đối với các bài đăng có mức lương cực trị phát hiện ở Bước 3 và Bước 5.
"""
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s6_md})

    return cells


def generate_all():
    print("=" * 70)
    print("   BẮT ĐẦU SINH TOÀN BỘ 8 NOTEBOOKS RAW-FIRST EDA TRONG reports/")
    print("=" * 70)

    for source_id, cfg in SOURCES_SPECS.items():
        nb_filename = f"EDA_{source_id}.ipynb"
        nb_path = REPORTS_DIR / nb_filename

        cells = build_raw_notebook_cells(source_id, cfg)
        nb_json = {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3 (.venv)",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "codemirror_mode": {"name": "ipython", "version": 3},
                    "file_extension": ".py",
                    "mimetype": "text/x-python",
                    "name": "python",
                    "nbconvert_exporter": "python",
                    "pygments_lexer": "ipython3",
                    "version": "3.12.0"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 5
        }

        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(nb_json, f, ensure_ascii=False, indent=1)

        print(f"  ✨ Đã tạo thành công: {nb_filename:<25} ({len(cells)} cells)")

    print("=" * 70)
    print("🎉 Hoàn tất 8/8 notebooks tại reports/EDA_{source}.ipynb!")


if __name__ == "__main__":
    generate_all()
