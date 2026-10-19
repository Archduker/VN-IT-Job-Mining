# BÁO CÁO PHÂN TÍCH DỮ LIỆU KHÁM PHÁ (EDA REPORT) — GLINTS DATASET

> **Tác giả:** Duy (Data Mining & Crawler Engineer)
> **Nguồn dữ liệu:** Glints Vietnam (`https://glints.com/vn`)
> **Công cụ:** Pandas, DuckDB, NumPy, Matplotlib, Seaborn
> **Thời điểm phân tích:** 2026-10-18
> **Tiêu chuẩn:** CRISP-DM Phase 2 & Modern ELT (SD1 - SD5)

---

## 1. Tổng Quan Dữ Liệu & Vòng Đời Bài Đăng

| Chỉ số | Giá trị | Ghi chú |
| :--- | :---: | :--- |
| **Tổng số URL phát hiện (Discovery)** | **37** | URL bài đăng IT từ Glints |
| **Số tin đã cào chi tiết (`DONE`)** | **37** | Đã thu thập đầy đủ snapshot |
| **Số tin lỗi (`FAILED`)** | **0** | Đã xử lý an toàn với Safe Skip |
| **Bộ mẫu đối chứng (`samples/`)** | **3 cặp** | Đầy đủ Standard, VIP, Negotiable |

---

## 2. Phân Tích Khuyết Thiếu Dữ Liệu (Missing Value Profiling)

| Tên trường | Số lượng Missing | Tỷ lệ khuyết thiếu (%) | Nguyên nhân nghiệp vụ | Chiến lược tiền xử lý |
| :--- | :---: | :---: | :--- | :--- |
| `title` | 0 | **0.0%** | Bắt buộc | Giữ nguyên |
| `company` | 0 | **0.0%** | Bắt buộc | Làm sạch ký tự đặc biệt |
| `salary_text` | 16 | **43.2%** | Lương thỏa thuận | Tách cờ `is_negotiable=True` |
| `skill_tags_raw` | 8 | **21.6%** | Không gắn thẻ kỹ năng | Trích xuất bằng NLP từ `description` |
| `min_experience_years` | 0 | **0.0%** | Bắt buộc trên form Glints | Giá trị 0 tương ứng không yêu cầu |

---

## 3. Trực Quan Hóa 5 Họ Biểu Đồ Bắt Buộc

1. **Distribution:** Phân bố dải lương tập trung mạnh ở phân khúc 25 - 45 triệu VNĐ, phản ánh xu hướng công nghệ trẻ và startup quốc tế.
2. **Relationship:** Tỷ lệ công việc cho phép Remote / Hybrid chiếm trên 40%, tỷ lệ thuận với mức đãi ngộ.
3. **Dispersion:** Độ biến thiên lương giữa các kỹ năng Web (Frontend) hẹp hơn so với kỹ năng AI/Data.
4. **Correlation:** Hệ số tương quan Pearson giữa số năm kinh nghiệm và mức lương sàn đạt 0.72.
5. **Pareto:** React, TypeScript, Node.js, Python, Golang chiếm hơn 65% tổng số kỹ năng được yêu cầu.
