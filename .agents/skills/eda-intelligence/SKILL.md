---
name: eda-intelligence
description: >-
  Chuyên gia phân tích dữ liệu khám phá (Exploratory Data Analysis - EDA) sơ bộ và chuyên sâu.
  Thành thạo phân tích khuyết thiếu (Missing Value Profiling), ngoại lai (Outliers via IQR, Z-Score, Isolation Forest),
  và trực quan hóa 5 họ biểu đồ bắt buộc: Phân phối (Distribution), Quan hệ (Relationship), Độ biến thiên (Dispersion/Variance),
  Ma trận tương quan (Correlation Matrix - Pearson & Spearman), Tần suất phân loại (Categorical Frequency & Pareto).
  Đưa ra cơ sở khoa học để quyết định kỹ thuật điều chỉnh và tiền xử lý dữ liệu trước bước Data Integration.
---

# EDA Intelligence Skill

Kỹ năng này cung cấp cho AI Agent quy trình khoa học để phân tích, đánh giá chất lượng và trực quan hóa dữ liệu tuyển dụng IT từ cấp độ nguồn đơn lẻ (EDA sơ bộ) đến cấp độ toàn hệ thống (EDA chính).

---

## 1. Giai Đoạn 1: EDA Sơ Bộ Tại Nguồn (Source-Level Preliminary EDA)

Trước khi tiến hành ghép nối dữ liệu, Agent phải đánh giá 3 trụ cột chất lượng của tập dữ liệu vừa cào:

### 1.1. Bảng Kiểm Kê Trường & Tỷ Lệ Missing (Field Inventory)
Sinh bảng tổng hợp chất lượng trường:
```python
import pandas as pd

def generate_field_inventory(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    total_rows = len(df)
    
    for col in df.columns:
        null_count = df[col].isnull().sum() + (df[col] == "").sum()
        null_rate = (null_count / total_rows) * 100
        sample_val = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
        
        records.append({
            "Field Name": col,
            "Data Type": str(df[col].dtype),
            "Null Count": null_count,
            "Null Rate (%)": round(null_rate, 2),
            "Unique Count": df[col].nunique(),
            "Sample Value": str(sample_val)[:50]
        })
        
    return pd.DataFrame(records).sort_values(by="Null Rate (%)")
```

### 1.2. Phát Hiện Ngoại Lai (Outlier Detection) Bằng Phương Pháp Giá Trị Số
Áp dụng cho các trường định lượng: Mức lương tối thiểu, Mức lương tối đa, Số năm kinh nghiệm:
```python
import numpy as np

def detect_outliers_iqr(series: pd.Series) -> dict:
    clean_s = series.dropna()
    q1 = clean_s.quantile(0.25)
    q3 = clean_s.quantile(0.75)
    iqr = q3 - q1
    lower_bound = max(0, q1 - 1.5 * iqr)
    upper_bound = q3 + 1.5 * iqr
    
    outliers = clean_s[(clean_s < lower_bound) | (clean_s > upper_bound)]
    return {
        "Q1": q1, "Q3": q3, "IQR": iqr,
        "Lower_Bound": lower_bound, "Upper_Bound": upper_bound,
        "Outlier_Count": len(outliers),
        "Outlier_Rate (%)": round((len(outliers) / len(clean_s)) * 100, 2),
        "Max_Value": clean_s.max(),
        "Min_Value": clean_s.min()
    }
```

---

## 2. 5 Họ Biểu Đồ Bắt Buộc Trong EDA Chính

Agent có nhiệm vụ tạo mã Python (Seaborn / Matplotlib) chuẩn để render 5 họ biểu đồ sau:

### 2.1. Biểu đồ Phân Phối (Distribution Plots)
- Histogram kết hợp KDE cho biến Lương và Kinh nghiệm.
- Đánh giá độ lệch (Skewness) và độ nhọn (Kurtosis).

```python
import matplotlib.pyplot as plt
import seaborn as sns

def plot_salary_distribution(df: pd.DataFrame, save_path: str):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Biểu đồ lương gốc
    sns.histplot(df["salary_min_vnd"].dropna(), kde=True, ax=axes[0], color="skyblue")
    axes[0].set_title("Phân phối Mức Lương Tối Thiểu (Triệu VNĐ)")
    
    # Biểu đồ log transform nếu bị lệch phải nặng
    log_salary = np.log1p(df["salary_min_vnd"].dropna())
    sns.histplot(log_salary, kde=True, ax=axes[1], color="salmon")
    axes[1].set_title("Phân phối Sau Log Transformation: log(1 + Salary)")
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
```

### 2.2. Biểu đồ Quan Hệ (Relationship Plots)
- Scatter plot giữa Kinh Nghiệm vs Mức Lương.
- Thêm đường hồi quy tuyến tính và dải tin cậy 95%.

```python
def plot_experience_vs_salary(df: pd.DataFrame, save_path: str):
    plt.figure(figsize=(10, 6))
    sns.regplot(
        data=df, x="min_experience_years", y="salary_max_vnd",
        scatter_kws={"alpha": 0.3, "color": "teal"},
        line_kws={"color": "red", "linewidth": 2}
    )
    plt.title("Mối Quan Hệ Giữa Số Năm Kinh Nghiệm và Mức Lương Tối Đa")
    plt.xlabel("Số Năm Kinh Nghiệm Tối Thiểu (Năm)")
    plt.ylabel("Mức Lương Tối Đa (Triệu VNĐ/tháng)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.savefig(save_path, dpi=300)
    plt.close()
```

### 2.3. Biểu đồ Độ Biến Thiên / Phân Tán (Dispersion & Variance Plots)
- Boxplot & Violin plot so sánh phân tán lương theo Cấp bậc (Seniority) và Job Family.

```python
def plot_salary_variance_by_seniority(df: pd.DataFrame, save_path: str):
    plt.figure(figsize=(12, 6))
    order = ["Intern", "Fresher", "Junior", "Middle", "Senior", "Lead / Manager"]
    valid_df = df[df["seniority_level"].isin(order)]
    
    sns.boxplot(data=valid_df, x="seniority_level", y="salary_max_vnd", order=order, palette="Set2")
    plt.title("Độ Biến Thiên Mức Lương Giữa Các Cấp Bậc Seniority")
    plt.ylabel("Lương Tối Đa (Triệu VNĐ)")
    plt.xticks(rotation=15)
    plt.savefig(save_path, dpi=300)
    plt.close()
```

### 2.4. Ma Trận Tương Quan (Correlation Matrix Heatmap)
- Tính hệ số tương quan Pearson và Spearman cho toàn bộ các biến định lượng.

```python
def plot_correlation_matrix(df: pd.DataFrame, save_path: str):
    num_cols = ["salary_min_vnd", "salary_max_vnd", "min_experience_years", "jd_word_count", "total_skills_count"]
    corr = df[num_cols].corr(method="spearman")
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(corr, annot=True, cmap="coolwarm", vmin=-1, vmax=1, fmt=".2f", linewidths=0.5)
    plt.title("Ma Trận Tương Quan Hạng Spearman (Quantitative Attributes)")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
```

### 2.5. Tần Suất Giá Trị Phân Loại (Categorical Frequency & Pareto)
- Top 20 Kỹ năng có tần suất xuất hiện cao nhất.
- Đường cong tích lũy Pareto (80/20 rule).

```python
def plot_top_skills_pareto(skill_series: pd.Series, save_path: str):
    top_skills = skill_series.value_counts().head(20)
    df_pareto = top_skills.reset_index()
    df_pareto.columns = ["Skill", "Count"]
    df_pareto["Cum_Percent"] = (df_pareto["Count"].cumsum() / df_pareto["Count"].sum()) * 100
    
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    
    sns.barplot(data=df_pareto, x="Skill", y="Count", ax=ax1, palette="viridis")
    sns.lineplot(data=df_pareto, x="Skill", y="Cum_Percent", ax=ax2, color="crimson", marker="o")
    
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=45, ha="right")
    ax2.set_ylabel("Tỷ Lệ Tích Lũy (%)")
    ax2.axhline(80, color="gray", linestyle="--")
    plt.title("Top 20 Kỹ Năng IT Hàng Đầu & Đường Tích Lũy Pareto")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
```

---

## 3. Khung Quyết Định Tiền Xử Lý Dựa Trên Kết Quả EDA

Agent khuyến nghị các kỹ thuật biến đổi dữ liệu cụ thể:
1. **Lệch phải (Right-Skewed > 1.5):** Dùng Log Transformation ($y = \log(1+x)$) để ổn định phương sai trước khi mô hình hóa.
2. **Outlier lương cực đại:** Dùng Winsorization (capping ở phân vị 99%), không drop bản ghi để bảo toàn các tag kỹ năng.
3. **Missing Value Lương (Thỏa thuận):** Gán cờ `is_salary_negotiable = 1`. Tuyệt đối không fill bằng Mean của toàn bộ tập vì tin thỏa thuận có phân phối khác tin công khai lương.
4. **Chuẩn hóa chuỗi text:** Làm sạch bullet `•`, `-`, mã HTML, ký tự đặc biệt trước khi đưa vào pipeline trích xuất kỹ năng bằng AI.
