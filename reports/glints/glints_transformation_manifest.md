# BÁO CÁO BIẾN ĐỔI DỮ LIỆU & TỪ ĐIỂN ÁNH XẠ: GLINTS
> **Dự án:** Phân tích thị trường lao động IT Việt Nam (**VN-IT-Job-Mining**)  
> **Nguồn tuyển dụng:** `glints`  
> **Thời điểm xuất bản:** `2026-10-25T18:03:00.740533+00:00`  
> **Tiêu chuẩn nghiệm thu:** DoD Level-4 (Zero Information Loss, Single Flat Table, Bộ 3 Deliverables)

---

## 1. Tóm Tắt Quy Trình Biến Đổi (Transformation Executive Summary)

```text
+----------------------------------------------------------------------------------------------------+
|                TIẾN TRÌNH BIẾN ĐỔI DỮ LIỆU NGUỒN: GLINTS                              |
+----------------------------------------------------------------------------------------------------+
| 1. Tổng số file quét (Raw Files)        : 331                                              |
| 2. Tổng số envelope thô (Envelopes)     : 331                                              |
| 3. Stub JD bị loại bỏ (Chính sách 1.B) : 0                                                |
| 4. Bản ghi phẳng hợp lệ (Clean Records) : 331                                              |
| 5. Tỷ lệ có mức lương số (Salary Rate)  : 77.64% (257 tin tuyển dụng)                         |
| 6. Lương bóc tách từ Header Regex      : 0                                                |
| 7. Lương ẩn bóc tách từ JD Regex       : 45                                               |
| 8. Bản ghi được GenAI bù khuyết        : 322 (97.28%)                                  |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Thống Kê Phân Phối Dải Lương (Salary Distribution)
- **Phân vị P1 (Ngưỡng cận dưới Winsorization):** 596,667 VNĐ
- **Phân vị Q1 (25% thị trường):** 12,000,000 VNĐ
- **Trung vị Median (50% thị trường):** 17,000,000 VNĐ
- **Phân vị Q3 (75% thị trường):** 30,000,000 VNĐ
- **Phân vị P99 (Ngưỡng cận trên Winsorization):** 100,000,000 VNĐ

---

## 3. Phân Phối 12 Job Family Chuẩn (SD2 Taxonomy)

| Mã Nhóm Job Family | Tên Nhóm Nghề Nghiệp | Số Lượng Bản Ghi | Tỷ Trọng (%) |
| :--- | :--- | :--- | :--- |
| `JF08_QA_QC` | 08 Qa Qc | 81 | 24.47% |
| `JF10_PROD_BA` | 10 Prod Ba | 70 | 21.15% |
| `JF00_OTHER_IT` | 00 Other It | 38 | 11.48% |
| `JF05_DEVOPS` | 05 Devops | 27 | 8.16% |
| `JF01_BACKEND` | 01 Backend | 25 | 7.55% |
| `JF09_SECURITY` | 09 Security | 22 | 6.65% |
| `JF06_DATA_ENG` | 06 Data Eng | 19 | 5.74% |
| `JF07_DATA_AI` | 07 Data Ai | 15 | 4.53% |
| `JF04_MOBILE` | 04 Mobile | 14 | 4.23% |
| `JF03_FULLSTACK` | 03 Fullstack | 10 | 3.02% |
| `JF02_FRONTEND` | 02 Frontend | 6 | 1.81% |
| `JF11_UI_UX` | 11 Ui Ux | 3 | 0.91% |
| `JF12_EMBEDDED` | 12 Embedded | 1 | 0.3% |

---

## 4. Từ Điển Dữ Liệu Bảng Phẳng Chuẩn (Data Dictionary)

| Tên Cột Chuẩn | Kiểu Dữ Liệu | Nguồn Gốc (Origin) | Mô Tả & Quy Tắc Xử Lý |
| :--- | :--- | :--- | :--- |
| `job_id_global` | `str` | Metadata | Mã định danh duy nhất xuyên hệ thống: `glints_<id>` |
| `source_platform` | `str` | Metadata | Tên sàn tuyển dụng: `glints` |
| `source_url` | `str` | Metadata | Đường dẫn URL gốc của bài đăng |
| `job_title` | `str` | Raw Payload | Tiêu đề bài đăng nguyên bản |
| `job_title_clean` | `str` | Transformation | Tiêu đề đã làm sạch bracket tags [HN], [HCM], lương đuôi |
| `company_name` | `str` | Raw Payload | Tên công ty tuyển dụng |
| `primary_city` | `str` | Normalization | Tỉnh/thành phố chuẩn hóa về 63 tỉnh thành |
| `job_seniority` | `str` | Normalization | Cấp bậc quy chuẩn về 6 bậc (Intern, Fresher, Junior, Middle, Senior, Lead/Manager) |
| `job_family` | `str` | Normalization | Phân loại về 12 Job Family chuẩn IT Việt Nam (SD2) |
| `raw_salary_text` | `str` | Raw Payload | Mức lương dạng chữ thô nguyên bản từ sàn |
| `salary_min_vnd` | `float` | Transformation | Lương tối thiểu chuẩn hóa về VNĐ/tháng (đã quy đổi USD và lương năm) |
| `salary_max_vnd` | `float` | Transformation | Lương tối đa chuẩn hóa về VNĐ/tháng |
| `salary_source` | `str` | Provenance | Nguồn bóc tách lương: `header_regex` hoặc `jd_regex` |
| `salary_log_max` | `float` | Normalization | Biến đổi log1p: `log(1 + salary_max_vnd)` đưa về phân phối chuẩn |
| `is_salary_negotiable_declared` | `int` | Transformation | Cờ 1 nếu bài đăng khai báo Thỏa thuận / Cạnh tranh / 0 |
| `skills_list` | `list[str]` | Integration & Imputer | Mảng danh sách kỹ năng công nghệ (Python, Java, React, Docker, ...) |
| `benefits_list` | `list[str]` | Integration | Mảng danh sách chế độ đãi ngộ (Bảo hiểm, Lương tháng 13, ...) |
| `jd_word_count` | `int` | Text Metrics | Số từ trong mô tả công việc (loại bỏ bài < 30 từ theo Chính sách 1.B) |
| `detected_language` | `str` | Text Metrics | Ngôn ngữ phát hiện: `vi` (Tiếng Việt) hoặc `en` (Tiếng Anh) |
| `is_imputed_by_genai` | `bool` | Imputer | Cờ True nếu bản ghi được GenAI đọc hiểu bù khuyết |
| `genai_imputed_fields` | `list[str]` | Imputer | Danh sách các trường được GenAI bù khuyết |
