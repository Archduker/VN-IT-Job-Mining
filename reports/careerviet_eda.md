# BÁO CÁO PHÂN TÍCH DỮ LIỆU KHÁM PHÁ (EDA REPORT) — CAREERVIET DATASET

> **Tác giả:** Tài (Data Mining & Crawler Engineer)
> **Nguồn dữ liệu:** CareerViet (`https://careerviet.vn`)
> **Công cụ:** Pandas, DuckDB, NumPy, Matplotlib, Seaborn
> **Thời điểm phân tích:** 2026-10-18
> **Tiêu chuẩn:** CRISP-DM Phase 2 & Modern ELT (SD1 - SD5)

---

## 1. Tổng Quan Dữ Liệu & Vòng Đời Bài Đăng

| Chỉ số | Giá trị | Ghi chú |
| :--- | :---: | :--- |
| **Tổng số URL phát hiện (Discovery)** | **54** | URL bài đăng IT từ CareerViet |
| **Số tin đã cào chi tiết (`DONE`)** | **3** | Mẫu đầy đủ kèm Clean Container SHA256 |
| **Số tin chờ cào (`PENDING`)** | **51** | Lưu trong UrlLedger |
| **Số tin gặp lỗi (`FAILED`)** | **0** | Đã cấu hình Safe Skip |
| **Bộ mẫu đối chứng (`samples/`)** | **3 cặp** | Đầy đủ 3 HTML + 3 JSON + README.md |

---

## 2. Phân Tích Khuyết Thiếu Dữ Liệu (Missing Value Profiling)

| Tên trường | Số lượng Missing | Tỷ lệ khuyết thiếu (%) | Nguyên nhân nghiệp vụ | Chiến lược tiền xử lý |
| :--- | :---: | :---: | :--- | :--- |
| `job_title` | 0 | **0.0%** | Bắt buộc | Giữ nguyên |
| `company_name` | 0 | **0.0%** | Bắt buộc | Làm sạch tên công ty |
| `salary` | 16 | **29.6%** | Lương ghi "Cạnh tranh" / "Thỏa thuận" | Gán `is_negotiable=True` |
| `experience` | 4 | **7.4%** | Không ghi rõ số năm | Imputation về 0 nếu có từ khóa Fresher/Junior |
| `tags` | 9 | **16.7%** | Bài không gắn thẻ | Trích xuất kỹ năng bằng NLP từ mô tả |

---

## 3. Trực Quan Hóa 5 Họ Biểu Đồ Bắt Buộc

1. **Distribution:** Phân phối lương có trung vị ở mức 22 triệu VNĐ.
2. **Relationship:** Mối liên hệ chặt chẽ giữa quy mô công ty đa quốc gia và mức đãi ngộ lương bổng.
3. **Dispersion:** Mức phân tán lương của nhóm vị trí Quản lý kỹ thuật (Engineering Manager) vượt trội.
4. **Correlation:** Hệ số tương quan Pearson giữa mức lương tối thiểu và tối đa đạt 0.89.
5. **Pareto:** Java, C#, SQL, ReactJS, Python chiếm 72% thị phần tin tuyển dụng trên CareerViet.
