# Khai phá dữ liệu tuyển dụng CNTT Việt Nam
**Building a Data Collection Pipeline and Mining IT Recruitment Data in Vietnam**

Dự án môn học Khai phá Dữ liệu (Data Mining) — Trường Đại học Giao thông vận tải TP.HCM (UTH).

---

## 📌 Tài liệu dự án

- 📄 [Đề cương chi tiết dự án (Tiếng Việt)](vietnam_it_recruitment_data_mining_project.md)
- 🕷️ [Cấu trúc Crawler & Phân công nguồn](crawlers/README.md)

---

## 👥 Phân công phụ trách nguồn thu thập

| Nguồn | Thư mục | Người phụ trách | Trạng thái |
|---|---|---|---|
| TopDev | `crawlers/sources/topdev/` | Sơn | Chưa bắt đầu |
| LinkedIn | `crawlers/sources/linkedin/` | Phúc | Chưa bắt đầu |
| CareerViet | `crawlers/sources/careerviet/` | Tài | Chưa bắt đầu |
| JobsGO | `crawlers/sources/jobsgo/` | Khoa | Chưa bắt đầu |
| ITviec | `crawlers/sources/itviec/` | Phát | Chưa bắt đầu |
| TopCV | `crawlers/sources/topcv/` | Thuận | Chưa bắt đầu |

---

## 🎯 Mục tiêu chính

- Thu thập định kỳ và xây dựng bộ dữ liệu sạch tối thiểu **10.000 tin tuyển dụng CNTT duy nhất** tại Việt Nam.
- Pipeline xử lý và lưu trữ dữ liệu nhiều tầng trên **AWS S3** (Raw → Staging → Curated).
- Phân tích khám phá dữ liệu (EDA), trực quan hóa nhu cầu kỹ năng, phân bố địa điểm, mức lương.
- Xây dựng mô hình học máy phân loại vị trí công việc (`role_group`) từ tiêu đề và mô tả tuyển dụng.
