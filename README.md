# Khai phá dữ liệu tuyển dụng CNTT Việt Nam

**Building a Data Collection Pipeline and Mining IT Recruitment Data in Vietnam**

Dự án môn học Khai phá Dữ liệu (Data Mining) — Trường Đại học Giao thông vận tải TP.HCM (UTH).

---

## 📌 Tài liệu dự án

- 📋 [**Phân công công việc (TASKS.md)**](TASKS.md) — Ai làm gì, deadline, checklist
- 📄 [Đề cương chi tiết dự án](docs/vietnam_it_recruitment_data_mining_project.md)
- 🏗️ [Thiết kế kiến trúc kỹ thuật](docs/kien_truc_co_the.md)
- 🕷️ [Cấu trúc Crawler & Phân công nguồn](crawlers/README.md)

---

## 🏗️ Kiến trúc triển khai

```text
6 thành viên viết code crawler → Push GitHub → Thuận pull về EC2
                                                     ↓
                                    Cron chạy 6 crawler tự động (batching)
                                                     ↓
                                    JSONL local → S3 Raw Zone → Telegram báo cáo
                                                     ↓
                                    ELT: Raw → Staging → Curated (Parquet)
                                                     ↓
                                    EDA + Trực quan hóa + Machine Learning
```

---

## 👥 Phân công nguồn thu thập

| Nguồn | Thư mục | Người phụ trách | Công cụ | Trạng thái |
|---|---|---|---|---|
| TopDev | `crawlers/sources/topdev/` | Sơn | requests + BS4 | ⬜ Chưa bắt đầu |
| CareerViet | `crawlers/sources/careerviet/` | Tài | requests + BS4 | ⬜ Chưa bắt đầu |
| ITviec | `crawlers/sources/itviec/` | Phát | requests + BS4 | ⬜ Chưa bắt đầu |
| VietnamWorks | `crawlers/sources/vietnamworks/` | Khoa | requests + BS4 | ⬜ Chưa bắt đầu |
| TopCV | `crawlers/sources/topcv/` | Thuận | Playwright / Browser Use | ⬜ Chưa bắt đầu |
| _Chưa chốt_ | — | Phúc | _Tùy nguồn_ | ⚠️ Cần chọn nguồn |

> **Nhánh thử nghiệm:** Thuận + Phát phối hợp thử Browser Use + Ollama trên 1.000 tin (ITviec + TopCV).

---

## 🎯 Mục tiêu chính

- Thu thập và xây dựng bộ dữ liệu sạch tối thiểu **10.000 tin tuyển dụng CNTT duy nhất** tại Việt Nam.
- Pipeline xử lý ELT và lưu trữ dữ liệu nhiều tầng trên **AWS S3** (Raw → Staging → Curated).
- Hệ thống chạy tự động trên **EC2/VPS** theo lịch (cron + batching).
- Phân tích khám phá dữ liệu (EDA), trực quan hóa nhu cầu kỹ năng, phân bố địa điểm, mức lương.
- Xây dựng mô hình học máy phân loại vị trí công việc (`role_group`) từ tiêu đề và mô tả tuyển dụng.

---

## ⏰ Mốc quan trọng

| Mốc | Thời gian | Nội dung |
|---|---|---|
| 🎯 Demo T4 | Tuần 1 | Mẫu dữ liệu từ 6 nguồn trên S3, sơ đồ kiến trúc |
| 🎯 Đủ 10.000 tin | Tuần 5 | Dừng cào, kiểm tra chất lượng |
| 🎯 Thuyết trình cuối kỳ | Tuần 9 | Dashboard, ML model, báo cáo tổng kết |
