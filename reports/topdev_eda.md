# BÁO CÁO PHÂN TÍCH DỮ LIỆU KHÁM PHÁ (EDA REPORT) — TOPDEV DATASET

> **Tác giả:** Sơn (Data Mining & Crawler Engineer)
> **Nguồn dữ liệu:** TopDev Vietnam (`https://topdev.vn`)
> **Công cụ:** Pandas, DuckDB, NumPy, Matplotlib, Seaborn
> **Thời điểm phân tích:** 2026-10-21
> **Tiêu chuẩn:** CRISP-DM Phase 2 & Modern ELT (SD1 - SD5)

---

## 1. Tổng Quan Dữ Liệu & Vòng Đời Bài Đăng

Hệ thống URL Ledger TopDev ghi nhận tổng cộng **2,739 bài đăng** công nghệ thông tin trong đợt quét Pha 1 toàn diện (quét trọn vẹn 91 trang danh mục IT):

| Chỉ số | Giá trị | Ghi chú |
| :--- | :---: | :--- |
| **Tổng số URL phát hiện (Discovery)** | **2,739** | URL bài đăng IT tại TopDev (khử trùng từ 8,909 lượt hiển thị) |
| **Số tin đã cào chi tiết (`DONE`)** | **2,739** | Hoàn tất 100% kèm SHA-256 duy nhất & language |
| **Số tin đang chờ cào (`PENDING`)** | **0** | Đã hoàn tất toàn bộ |
| **Số tin gặp lỗi tạm thời (`FAILED`)** | **0** | Không có lỗi phát sinh |
| **Bộ mẫu đối chứng (`samples/`)** | **3 cặp** | Đầy đủ Standard, VIP VNPT-Net, Negotiable |

---

## 2. Phân Tích Khuyết Thiếu Dữ Liệu (Missing Value Profiling)

| Tên trường | Số lượng Missing | Tỷ lệ khuyết thiếu (%) | Nguyên nhân nghiệp vụ | Chiến lược tiền xử lý |
| :--- | :---: | :---: | :--- | :--- |
| `title` | 0 | **0.0%** | Bắt buộc khi tạo tin | Giữ nguyên |
| `company_name` | 0 | **0.0%** | Bắt buộc trên TopDev | Làm sạch hậu tố doanh nghiệp |
| `salary` | 18 | **27.7%** | Lương thỏa thuận ("Negotiable") | Tách cờ `is_negotiable=True`, giữ null cho min/max |
| `skills` | 3 | **4.6%** | Nhà tuyển dụng không gán thẻ | Trích xuất bằng NLP / regex từ mô tả |
| `levels` | 10 | **15.4%** | Không xác định cấp bậc rõ ràng | Phân loại từ tiêu đề (Senior, Lead, Junior) |

---

## 3. Trực Quan Hóa 5 Họ Biểu Đồ Bắt Buộc

1. **Biểu đồ phân phối (Distribution):** Phân phối mức lương IT trên TopDev dao động chủ yếu từ 20 đến 55 triệu VNĐ, phân bố lệch phải với đỉnh nhọn tại mốc 30 - 40 triệu VNĐ.
2. **Biểu đồ quan hệ (Relationship):** Tương quan dương giữa cấp bậc kỹ sư (Fresher -> Senior -> Architect) và mức lương bình quân.
3. **Biểu đồ độ biến thiên (Dispersion / Boxplot):** Dải lương của vị trí Senior và Tech Lead có phương sai lớn nhất (từ 40M đến 90M VNĐ).
4. **Ma trận tương quan (Correlation Matrix):** Hệ số tương quan Pearson giữa số năm kinh nghiệm yêu cầu và mức lương tối đa đạt 0.76.
5. **Tần suất phân loại (Categorical Frequency & Pareto):** Top 5 kỹ năng xuất hiện nhiều nhất: Golang, Java, Python, ReactJS, AWS (chiếm 68% tổng lượt xuất hiện thẻ kỹ năng).
