# Báo Cáo Phân Tích Khám Phá Dữ Liệu (EDA) - Tuyển Dụng IT Vieclam24h

## 1. Giai Đoạn 1: EDA Sơ Bộ Tại Nguồn (Source-Level Preliminary EDA)

### 1.1. Bảng Kiểm Kê Trường & Tỷ Lệ Missing (Field Inventory)

| Field Name           | Data Type   |   Null Count |   Null Rate (%) |   Unique Count | Sample Value                                       |
|:---------------------|:------------|-------------:|----------------:|---------------:|:---------------------------------------------------|
| source_job_id        | object      |            0 |               0 |            414 | 200955877                                          |
| title                | object      |            0 |               0 |            399 | Nhân Viên Kỹ Sư Lập Trình Android - Lương 15Tr Đến |
| company              | object      |            0 |               0 |            292 | Công Ty Cổ Phần Viettronics Tân Bình               |
| salary_min_vnd       | float64     |            0 |               0 |             26 | 15.0                                               |
| salary_max_vnd       | float64     |            0 |               0 |             31 | 20.0                                               |
| is_negotiable        | bool        |            0 |               0 |              1 | False                                              |
| min_experience_years | int64       |            0 |               0 |              8 | 3                                                  |
| seniority_level      | object      |            0 |               0 |              1 | Nhân viên                                          |
| jd_word_count        | int64       |            0 |               0 |            178 | 96                                                 |
| total_skills_count   | int64       |            0 |               0 |             20 | 10                                                 |
| location             | object      |            0 |               0 |            363 | số 248A Nơ Trang Long, Bình Thạnh, TP.HCM, VN      |

### 1.2. Phát Hiện Ngoại Lai (Outlier Detection) Bằng Phương Pháp IQR

- **Mức Lương Tối Thiểu (`salary_min_vnd`):** Q1 = 8.0, Q3 = 14.0, IQR = 6.0, Ngưỡng trên = 23.0, Số lượng ngoại lai = 13 (2.32%).
- **Mức Lương Tối Đa (`salary_max_vnd`):** Q1 = 13.0, Q3 = 20.0, IQR = 7.0, Ngưỡng trên = 30.5, Số lượng ngoại lai = 59 (10.52%).
- **Số Năm Kinh Nghiệm (`min_experience_years`):** Q1 = 2.0, Q3 = 4.0, IQR = 2.0, Ngưỡng trên = 7.0, Số lượng ngoại lai = 1 (0.18%).

---

## 2. Trực Quan Hóa 5 Họ Biểu Đồ Bắt Buộc Trong EDA

### 2.1. Họ Biểu Đồ Phân Phối (Distribution Chart)
Phân phối dải lương và biểu đồ sau khi áp dụng phép biến đổi Logarit nhằm giảm độ lệch phải (Right-Skewed):

![Phân Phối Lương](images/salary_distribution.png)

### 2.2. Họ Biểu Đồ Quan Hệ (Relationship Chart)
Khảo sát mối quan hệ tuyến tính giữa số năm kinh nghiệm và mức lương tối đa của ứng viên:

![Quan Hệ Kinh Nghiệm và Lương](images/experience_vs_salary.png)

### 2.3. Họ Biểu Đồ Độ Biến Thiên (Dispersion Chart - IQR & Outliers)
Biểu đồ hộp (Boxplot) thể hiện độ phân tán và phát hiện các giá trị ngoại lai theo cấp bậc công việc:

![Biến Thiên Theo Cấp Bậc](images/salary_variance.png)

### 2.4. Ma Trận Tương Quan (Correlation Matrix Heatmap)
Hệ số tương quan hạng Spearman giữa các thuộc tính định lượng trong tập dữ liệu:

![Ma Trận Tương Quan](images/correlation_matrix.png)

### 2.5. Biểu Đồ Tần Suất & Pareto Kỹ Năng IT
Xác định các nhóm công nghệ trọng điểm theo quy luật Pareto:

![Tần Suất Kỹ Năng](images/skills_pareto.png)

---

## 3. Khung Quyết Định Tiền Xử Lý Dựa Trên Kết Quả EDA

1. **Lệch phải (Right-Skewed > 1.5):** Áp dụng Log Transformation ($y = \log(1+x)$) đối với các biến mức lương.
2. **Outlier lương cực đại:** Sử dụng phương pháp Winsorization (capping tại phân vị 99%).
3. **Missing Value Lương (Thỏa thuận):** Gán cờ nhị phân `is_salary_negotiable = 1`.
4. **Chuẩn hóa chuỗi text:** Làm sạch các ký tự đặc biệt trong mô tả và yêu cầu tuyển dụng.
