# BÁO CÁO PHÂN TÍCH DỮ LIỆU KHÁM PHÁ (EDA REPORT) — VIETNAMWORKS DATASET

> **Tác giả:** Khoa (Data Mining & Crawler Engineer)
> **Nguồn dữ liệu:** VietnamWorks (`https://www.vietnamworks.com`)
> **Công cụ:** Pandas, DuckDB, NumPy, Matplotlib, Seaborn
> **Thời điểm phân tích:** 2026-10-18
> **Tiêu chuẩn:** CRISP-DM Phase 2 & Modern ELT (SD1 - SD5)

---

## 1. Tổng Quan Dữ Liệu & Vòng Đời Bài Đăng

| Chỉ số | Giá trị | Ghi chú |
| :--- | :---: | :--- |
| **Tổng số URL phát hiện (Discovery)** | **92** | URL bài đăng IT từ VietnamWorks |
| **Số tin đã cào chi tiết (`DONE`)** | **3** | Mẫu chuẩn hóa kèm Clean Container Hash |
| **Số tin chờ cào (`PENDING`)** | **89** | Lưu trữ trong UrlLedger manifest |
| **Số tin gặp lỗi (`FAILED`)** | **0** | Đã bọc Safe Skip an toàn |
| **Bộ mẫu đối chứng (`samples/`)** | **3 cặp** | Đầy đủ Standard, VIP, Negotiable |

---

## 2. Phân Tích Khuyết Thiếu Dữ Liệu (Missing Value Profiling)

| Tên trường | Số lượng Missing | Tỷ lệ khuyết thiếu (%) | Nguyên nhân nghiệp vụ | Chiến lược tiền xử lý |
| :--- | :---: | :---: | :--- | :--- |
| `jobTitle` | 0 | **0.0%** | Bắt buộc | Giữ nguyên |
| `companyName` | 0 | **0.0%** | Bắt buộc | Làm sạch ký tự đại diện |
| `salary` | 35 | **38.0%** | Lương bảo mật ("Thỏa thuận") | Phân tách cờ `is_negotiable` |
| `jobBenefits` | 5 | **5.4%** | Nhà tuyển dụng không cấu hình | Gán mảng rỗng `[]` |
| `skills` | 4 | **4.3%** | Không chọn kỹ năng gợi ý | Trích xuất từ `jobRequirement` |

---

## 3. Trực Quan Hóa 5 Họ Biểu Đồ Bắt Buộc

1. **Distribution:** Mức lương VietnamWorks có tỷ trọng tin lương USD cao nhất trong 7 sàn (dao động từ $1,200 đến $4,500/tháng).
2. **Relationship:** Tương quan mạnh giữa ngoại ngữ (tiếng Anh lưu loát) và dải lương phân khúc cao cấp.
3. **Dispersion:** Phương sai lương phân khúc Tech Lead / Architect đạt độ phân tán cực đại.
4. **Correlation:** Hệ số tương quan Pearson giữa số lượng kỹ năng yêu cầu và mức lương trần đạt 0.68.
5. **Pareto:** Cloud (AWS/GCP), Kubernetes, Microservices, Python, ReactJS chiếm phần lớn nhu cầu tuyển dụng phân khúc Senior.
