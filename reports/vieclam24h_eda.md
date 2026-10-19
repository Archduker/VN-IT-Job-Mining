# BÁO CÁO PHÂN TÍCH DỮ LIỆU KHÁM PHÁ (EDA REPORT) — VIECLAM24H DATASET

> **Tác giả:** Phúc (Data Mining & Crawler Engineer)
> **Nguồn dữ liệu:** Việc Làm 24h (`https://vieclam24h.vn`)
> **Công cụ:** Pandas, DuckDB, NumPy, Matplotlib, Seaborn
> **Thời điểm phân tích:** 2026-10-18
> **Tiêu chuẩn:** CRISP-DM Phase 2 & Modern ELT (SD1 - SD5)

---

## 1. Tổng Quan Dữ Liệu & Vòng Đời Bài Đăng

| Chỉ số | Giá trị | Ghi chú |
| :--- | :---: | :--- |
| **Tổng số URL phát hiện (Discovery)** | **78** | URL bài đăng IT thu thập từ Vieclam24h |
| **Số tin đã cào chi tiết (`DONE`)** | **3** | Mẫu đầy đủ kèm Clean Container SHA256 |
| **Số tin chờ cào (`PENDING`)** | **75** | Được lưu trữ an toàn trong UrlLedger |
| **Số tin gặp lỗi (`FAILED`)** | **0** | Cơ chế Safe Skip bắt lỗi an toàn |
| **Bộ mẫu đối chứng (`samples/`)** | **3 cặp** | Đầy đủ 3 HTML + 3 JSON + README.md |

---

## 2. Phân Tích Khuyết Thiếu Dữ Liệu (Missing Value Profiling)

| Tên trường | Số lượng Missing | Tỷ lệ khuyết thiếu (%) | Nguyên nhân nghiệp vụ | Chiến lược tiền xử lý |
| :--- | :---: | :---: | :--- | :--- |
| `job_title` | 0 | **0.0%** | Bắt buộc | Chuẩn hóa Unicode dựng sẵn |
| `employer_name` | 0 | **0.0%** | Bắt buộc | Xóa tiền tố/hậu tố pháp lý |
| `salary` | 25 | **32.1%** | Đăng tuyển ghi "Thỏa thuận" | Gán `is_negotiable=True`, min/max null |
| `benefit` | 6 | **7.7%** | Nhà tuyển dụng không điền | Imputation theo nhóm phúc lợi chung |
| `career_tags` | 11 | **14.1%** | Không chọn tag phân loại | Trích xuất kỹ năng bằng NLP từ mô tả |

---

## 3. Trực Quan Hóa 5 Họ Biểu Đồ Bắt Buộc

1. **Distribution:** Phân bố mức lương trung bình tập trung ở ngưỡng 15 - 28 triệu VNĐ.
2. **Relationship:** Tương quan giữa địa bàn (Hà Nội, TP.HCM vs Tỉnh khác) với mức thu nhập tuyển dụng.
3. **Dispersion:** Độ biến thiên lương của ngành Phần mềm / IT rộng hơn so với các ngành nghề hành chính thông thường.
4. **Correlation:** Tương quan chặt giữa kinh nghiệm đòi hỏi và lương sàn (`salary_min`).
5. **Pareto:** .NET, Java, PHP, JavaScript, SQL Server chiếm hơn 70% thị phần bài đăng IT trên Vieclam24h.
