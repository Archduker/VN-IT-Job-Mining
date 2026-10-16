# BÁO CÁO EDA SƠ BỘ TẠI NGUỒN (PRELIMINARY EDA REPORT)

> **Người thực hiện:** [Tên thành viên]  
> **Nguồn phân tích:** [Tên website]  
> **Kích thước mẫu phân tích:** [Số lượng dòng / cột]  
> **Notebook thực hiện:** `notebooks/eda_preliminary_[tenweb].ipynb`

---

## 1. Đánh Giá Khuyết Thiếu Dữ Liệu (Missing Values Analysis)

### 1.1. Bảng Tỷ Lệ Null Của Các Trường Quan Trọng:
| Tên trường | Số lượng Null | Tỷ lệ Null (%) | Đánh giá mức độ | Phương án xử lý đề xuất |
| :--- | :---: | :---: | :--- | :--- |
| Tiêu đề (`title`) | 0 | 0.0% | Tuyệt đối | Giữ nguyên |
| Mức lương (`salary`) | ... | ...% | [Thấp / TB / Cao] | Đánh dấu `is_negotiable`, trích regex từ tiêu đề |
| Kinh nghiệm (`experience`) | ... | ...% | [Thấp / TB / Cao] | Điền mặc định 0 năm nếu là Fresher/Intern |
| Địa điểm (`location`) | ... | ...% | [Thấp / TB / Cao] | Chuẩn hóa theo tỉnh thành chính |
| Thẻ kỹ năng (`tags`) | ... | ...% | [Thấp / TB / Cao] | Trích xuất bổ sung bằng AI/Regex từ JD |

---

## 2. Phân Tích Ngoại Lai (Outlier Analysis) Bằng Phương Pháp Giá Trị Số

### 2.1. Thống Kê Ngoại Lai Mức Lương (Triệu VNĐ/tháng):
| Chỉ số thống kê | Lương Tối Thiểu (`salary_min`) | Lương Tối Đa (`salary_max`) |
| :--- | :---: | :---: |
| Giá trị nhỏ nhất (Min) | ... | ... |
| Phân vị 25% ($Q_1$) | ... | ... |
| Trung vị (Median / $Q_2$) | ... | ... |
| Phân vị 75% ($Q_3$) | ... | ... |
| Giá trị lớn nhất (Max) | ... | ... |
| Khoảng phân vị ($\text{IQR} = Q_3 - Q_1$) | ... | ... |
| Giới hạn dưới ($\text{Lower Bound} = Q_1 - 1.5 \times \text{IQR}$) | ... | ... |
| Giới hạn trên ($\text{Upper Bound} = Q_3 + 1.5 \times \text{IQR}$) | ... | ... |
| **Số lượng bản ghi Outlier** | **... bản ghi** | **... bản ghi** |
| **Tỷ lệ Outlier (%)** | **... %** | **... %** |

### 2.2. Danh sách các bài đăng Outlier cực đoan phát hiện được:
1. `job_id`: ... — Tiêu đề: ... — Lương ghi nhận: ... (Nhận định: Gõ nhầm đơn vị USD sang VND / Nhầm lương năm sang tháng / Lỗi crawl).
2. `job_id`: ... — Tiêu đề: ... — Lương ghi nhận: ...

---

## 3. Khảo Sát Phân Bố & Tần Suất Giá Trị Phân Loại

### 3.1. Top 10 Kỹ Năng / Thẻ Tag Xuất Hiện Nhiều Nhất:
1. `...` (... lần xuất hiện)
2. `...` (... lần xuất hiện)
3. `...` (... lần xuất hiện)

### 3.2. Cơ Cấu Địa Điểm Làm Việc:
- TP. Hồ Chí Minh: ...%
- Hà Nội: ...%
- Đà Nẵng: ...%
- Remote / Khác: ...%

---

## 4. Hình Ảnh Trực Quan Hóa (Đính kèm đồ thị xuất ra từ Notebook)
- *Biểu đồ 1:* Histogram phân phối mức lương tối thiểu và tối đa.
- *Biểu đồ 2:* Boxplot lương phát hiện ngoại lai.
- *Biểu đồ 3:* Bar chart Top 15 Kỹ năng được yêu cầu nhiều nhất.
