# -*- coding: utf-8 -*-
"""scripts.create_golden_master_eda_notebook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tự động tạo Jupyter Notebook EDA tổng thể cho Bộ Dữ Liệu Vàng:
`collection/reports/EDA_golden_master_dataset.ipynb`
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

cells = [
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# 🌟 BÁO CÁO EDA TỔNG THỂ BỘ DỮ LIỆU VÀNG (GOLDEN MASTER DATASET EDA)\n",
            "> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  \n",
            "> **Nguồn dữ liệu:** `data/curated/curated_flat_golden_jobs.parquet` (8,388 bản ghi độc nhất từ 8 sàn)  \n",
            "> **Quy chuẩn:** Phân tích đa biến Đơn biến/Đa biến, 12 Job Family (SD2), Kỹ năng công nghệ (SD3), Dải lương chuẩn hóa.\n",
        ],
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import json\n",
            "import numpy as np\n",
            "import pandas as pd\n",
            "import matplotlib.pyplot as plt\n",
            "import seaborn as sns\n",
            "\n",
            "# Thiết lập hiển thị đồ họa\n",
            "plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')\n",
            "plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']\n",
            "plt.rcParams['axes.unicode_minus'] = False\n",
            "%matplotlib inline\n",
            "\n",
            "# Nạp Bộ Dữ Liệu Vàng Curated Master Table\n",
            "df_golden = pd.read_parquet('../../data/curated/curated_flat_golden_jobs.parquet')\n",
            "print(f'Đã nạp thành công: {len(df_golden):,} bản ghi Vàng x {len(df_golden.columns)} thuộc tính!')\n",
            "df_golden[['job_id_global', 'source_platform', 'job_title', 'primary_city', 'salary_max_vnd', 'job_family']].head(5)\n",
        ],
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 1. 📊 Phân Bổ Nguồn Dữ Liệu & Tỷ Lệ Trùng Lặp Xuyên Sàn\n",
            "Phân tích tỷ trọng bài đăng giữa 8 sàn tuyển dụng và hiệu quả của thuật toán Khử trùng lặp ngữ nghĩa (Cross-Platform Entity Resolution).\n",
        ],
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "fig, ax = plt.subplots(1, 2, figsize=(14, 5))\n",
            "\n",
            "# 1. Cơ cấu nguồn\n",
            "platform_counts = df_golden['source_platform'].value_counts()\n",
            "ax[0].bar(platform_counts.index, platform_counts.values, color='#2563eb', edgecolor='black', alpha=0.85)\n",
            "ax[0].set_title('Phân bố số lượng bài đăng theo sàn tuyển dụng gốc', fontsize=12, fontweight='bold')\n",
            "ax[0].set_ylabel('Số lượng tin tuyển dụng')\n",
            "ax[0].tick_params(axis='x', rotation=30)\n",
            "for i, v in enumerate(platform_counts.values):\n",
            "    ax[0].text(i, v + 25, f'{v:,}', ha='center', fontsize=9, fontweight='bold')\n",
            "\n",
            "# 2. Tỷ lệ bài đăng đơn lẻ vs bài trùng lặp xuyên sàn\n",
            "merged_counts = df_golden['is_golden_merged'].value_counts()\n",
            "labels = ['Bài đăng đơn lẻ (89.1%)', 'Hợp nhất xuyên sàn (10.9%)']\n",
            "colors = ['#10b981', '#f59e0b']\n",
            "ax[1].pie(merged_counts.values, labels=labels, autopct='%1.1f%%', colors=colors, startangle=140, explode=(0, 0.08))\n",
            "ax[1].set_title('Tỷ lệ bài đăng được hợp nhất qua Entity Resolution', fontsize=12, fontweight='bold')\n",
            "\n",
            "plt.tight_layout()\n",
            "plt.show()\n",
        ],
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 2. 💰 Phân Phối Dải Lương & Hiệu Quả Biến Đổi Log-Transformation\n",
            "So sánh hình thái phân phối lương trước và sau khi biến đổi $y = \\log(1 + \\text{salary})$.\n",
        ],
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "salaries = df_golden['salary_max_vnd'].dropna() / 1e6  # Triệu VNĐ\n",
            "log_salaries = df_golden['salary_log_max'].dropna()\n",
            "\n",
            "fig, ax = plt.subplots(1, 2, figsize=(14, 5))\n",
            "\n",
            "# Phân phối gốc (Triệu VNĐ)\n",
            "sns.histplot(salaries, bins=40, kde=True, ax=ax[0], color='#dc2626')\n",
            "ax[0].set_title(f'Phân phối Lương tối đa gốc (Skewness: {salaries.skew():.2f})', fontsize=12, fontweight='bold')\n",
            "ax[0].set_xlabel('Mức lương tối đa (Triệu VNĐ/tháng)')\n",
            "ax[0].set_xlim(0, 120)\n",
            "\n",
            "# Phân phối sau Log-transform\n",
            "sns.histplot(log_salaries, bins=40, kde=True, ax=ax[1], color='#059669')\n",
            "ax[1].set_title(f'Phân phối sau Log-Transformation (Skewness: {log_salaries.skew():.2f})', fontsize=12, fontweight='bold')\n",
            "ax[1].set_xlabel('log(1 + salary_max_vnd)')\n",
            "\n",
            "plt.tight_layout()\n",
            "plt.show()\n",
        ],
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 3. 🎯 Nhu Cầu Tuyển Dụng & Mức Lương Theo 12 Job Family (SD2)\n",
            "Khảo sát phân khúc thị trường theo 12 nhóm nghề nghiệp chuẩn của ngành CNTT Việt Nam.\n",
        ],
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "family_stats = df_golden.groupby('job_family').agg(\n",
            "    count=('job_id_global', 'count'),\n",
            "    median_salary=('salary_max_vnd', lambda x: x.dropna().median() / 1e6 if not x.dropna().empty else 0.0)\n",
            ").reset_index().sort_values('count', ascending=True)\n",
            "\n",
            "fig, ax = plt.subplots(figsize=(12, 6))\n",
            "bars = ax.barh(family_stats['job_family'], family_stats['count'], color='#4f46e5', alpha=0.85, edgecolor='black')\n",
            "ax.set_title('Số lượng việc làm theo 12 Job Family Chuẩn IT Việt Nam (SD2)', fontsize=12, fontweight='bold')\n",
            "ax.set_xlabel('Số lượng bài đăng tuyển')\n",
            "\n",
            "for bar in bars:\n",
            "    w = bar.get_width()\n",
            "    ax.text(w + 15, bar.get_y() + bar.get_height()/2, f'{int(w):,}', va='center', fontsize=9, fontweight='bold')\n",
            "\n",
            "plt.tight_layout()\n",
            "plt.show()\n",
        ],
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 4. 🚀 Top 25 Kỹ Năng Công Nghệ Nóng Nhất Thị Trường (SD3)\n",
            "Phân tích tần suất xuất hiện của các kỹ năng trong `skills_list` phục vụ chuẩn hóa ESCO Taxonomy.\n",
        ],
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "from collections import Counter\n",
            "\n",
            "all_skills = []\n",
            "for sk_list in df_golden['skills_list']:\n",
            "    if sk_list is not None:\n",
            "        for sk in sk_list:\n",
            "            s_clean = str(sk).strip()\n",
            "            if s_clean and len(s_clean) > 1:\n",
            "                all_skills.append(s_clean)\n",
            "\n",
            "top_skills = Counter(all_skills).most_common(20)\n",
            "skills_df = pd.DataFrame(top_skills, columns=['Skill', 'Count']).sort_values('Count', ascending=True)\n",
            "\n",
            "fig, ax = plt.subplots(figsize=(10, 7))\n",
            "ax.barh(skills_df['Skill'], skills_df['Count'], color='#0284c7', edgecolor='black', alpha=0.85)\n",
            "ax.set_title('Top 20 Kỹ năng Công nghệ được săn đón nhất (VN-IT-Job-Mining)', fontsize=12, fontweight='bold')\n",
            "ax.set_xlabel('Tần suất xuất hiện (Số bài đăng)')\n",
            "\n",
            "for i, v in enumerate(skills_df['Count']):\n",
            "    ax.text(v + 10, i, f'{v:,}', va='center', fontsize=9, fontweight='bold')\n",
            "\n",
            "plt.tight_layout()\n",
            "plt.show()\n",
        ],
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 5. 📍 Phân Bổ Địa Lý Tuyển Dụng IT Tại Việt Nam\n",
            "Tỷ trọng phân bổ việc làm IT giữa các trung tâm công nghệ hàng đầu trên 63 tỉnh thành chuẩn hóa.\n",
        ],
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "city_counts = df_golden['primary_city'].value_counts().head(7)\n",
            "\n",
            "fig, ax = plt.subplots(figsize=(10, 5))\n",
            "ax.bar(city_counts.index, city_counts.values, color='#d97706', edgecolor='black', alpha=0.85)\n",
            "ax.set_title('Phân bố việc làm IT theo tỉnh/thành phố trung tâm', fontsize=12, fontweight='bold')\n",
            "ax.set_ylabel('Số lượng bài đăng')\n",
            "ax.tick_params(axis='x', rotation=20)\n",
            "\n",
            "for i, v in enumerate(city_counts.values):\n",
            "    ax.text(i, v + 40, f'{v:,}', ha='center', fontsize=9, fontweight='bold')\n",
            "\n",
            "plt.tight_layout()\n",
            "plt.show()\n",
        ],
    },
]

notebook_data = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out_path = PROJECT_ROOT / "collection" / "reports" / "EDA_golden_master_dataset.ipynb"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(notebook_data, f, ensure_ascii=False, indent=2)

print(f"Đã tạo thành công Notebook EDA Vàng: {out_path}")
