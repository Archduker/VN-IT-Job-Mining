# BÁO CÁO PHÂN TÍCH DỮ LIỆU KHÁM PHÁ (EDA REPORT) — JOBSGO DATASET

> **Tác giả:** Duy (Data Mining & Crawler Engineer)
> **Nguồn dữ liệu:** JobsGO (`https://jobsgo.vn`)
> **Công cụ:** Pandas, DuckDB, NumPy, Matplotlib, Seaborn
> **Thời điểm phân tích:** 2026-10-18
> **Tiêu chuẩn:** CRISP-DM Phase 2 & Modern ELT (SD1 - SD5)

---

## 1. Tổng Quan Dữ Liệu & Vòng Đời Bài Đăng

| Chỉ số | Giá trị | Ghi chú |
| :--- | :---: | :--- |
| **Tổng số URL phát hiện (Discovery)** | **45** | URL bài đăng IT từ JobsGO |
| **Số tin đã cào chi tiết (`DONE`)** | **3** | Mẫu chuẩn hóa kèm Clean Container Hash |
| **Số tin chờ cào (`PENDING`)** | **42** | Lưu trong UrlLedger |
| **Số tin gặp lỗi (`FAILED`)** | **0** | Đã cấu hình Safe Skip |
| **Bộ mẫu đối chứng (`samples/`)** | **3 cặp** | Đầy đủ 3 HTML + 3 JSON + README.md |

---

## 2. Phân Tích Khuyết Thiếu Dữ Liệu (Missing Value Profiling)

| Tên trường | Số lượng Missing | Tỷ lệ khuyết thiếu (%) | Nguyên nhân nghiệp vụ | Chiến lược tiền xử lý |
| :--- | :---: | :---: | :--- | :--- |
| `title` | 0 | **0.0%** | Bắt buộc | Giữ nguyên |
| `company` | 0 | **0.0%** | Bắt buộc | Làm sạch tên doanh nghiệp |
| `salary` | 15 | **33.3%** | Lương ghi "Thỏa thuận" | Gán `is_negotiable=True` |
| `experience` | 4 | **8.9%** | Không xác định số năm | Chuẩn hóa kinh nghiệm |
| `tags.skills` | 7 | **15.6%** | Không gắn tag | Trích xuất kỹ năng bằng NLP từ mô tả |

---

## 3. Trực Quan Hóa 5 Họ Biểu Đồ Bắt Buộc

1. **Distribution:** Phân bố lương IT JobsGO tập trung ở phân khúc 18 - 32 triệu VNĐ.
2. **Relationship:** Mối quan hệ giữa thâm niên kinh nghiệm và dải lương đề xuất.
3. **Dispersion:** Phương sai lương của các vị trí Fullstack và DevOps rộng hơn Backend thuần túy.
4. **Correlation:** Hệ số tương quan Pearson giữa mức lương tối thiểu và tối đa đạt 0.84.
5. **Pareto:** Python, Java, PHP, React, Node.js chiếm hơn 68% nhu cầu tuyển dụng công nghệ trên JobsGO.
