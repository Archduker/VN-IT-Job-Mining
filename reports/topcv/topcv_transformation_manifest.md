# BÁO CÁO BIẾN ĐỔI DỮ LIỆU & TỪ ĐIỂN ÁNH XẠ: TOPCV
> **Dự án:** Phân tích thị trường lao động IT Việt Nam (**VN-IT-Job-Mining**)  
> **Nguồn tuyển dụng:** `topcv`  
> **Thời điểm xuất bản:** `2026-10-25T18:03:05.235420+00:00`  
> **Tiêu chuẩn nghiệm thu:** DoD Level-4 (Zero Information Loss, Single Flat Table, Bộ 3 Deliverables)

---

## 1. Tóm Tắt Quy Trình Biến Đổi (Transformation Executive Summary)

```text
+----------------------------------------------------------------------------------------------------+
|                TIẾN TRÌNH BIẾN ĐỔI DỮ LIỆU NGUỒN: TOPCV                               |
+----------------------------------------------------------------------------------------------------+
| 1. Tổng số file quét (Raw Files)        : 1887                                             |
| 2. Tổng số envelope thô (Envelopes)     : 1887                                             |
| 3. Stub JD bị loại bỏ (Chính sách 1.B) : 252                                              |
| 4. Bản ghi phẳng hợp lệ (Clean Records) : 1626                                             |
| 5. Tỷ lệ có mức lương số (Salary Rate)  : 62.36% (1014 tin tuyển dụng)                         |
| 6. Lương bóc tách từ Header Regex      : 0                                                |
| 7. Lương ẩn bóc tách từ JD Regex       : 0                                                |
| 8. Bản ghi được GenAI bù khuyết        : 982 (60.39%)                                  |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Thống Kê Phân Phối Dải Lương (Salary Distribution)
- **Phân vị P1 (Ngưỡng cận dưới Winsorization):** 1,575,000 VNĐ
- **Phân vị Q1 (25% thị trường):** 15,000,000 VNĐ
- **Trung vị Median (50% thị trường):** 20,000,000 VNĐ
- **Phân vị Q3 (75% thị trường):** 30,000,000 VNĐ
- **Phân vị P99 (Ngưỡng cận trên Winsorization):** 70,000,000 VNĐ

---

## 3. Phân Phối 12 Job Family Chuẩn (SD2 Taxonomy)

| Mã Nhóm Job Family | Tên Nhóm Nghề Nghiệp | Số Lượng Bản Ghi | Tỷ Trọng (%) |
| :--- | :--- | :--- | :--- |
| `JF00_OTHER_IT` | 00 Other It | 345 | 21.22% |
| `JF11_UI_UX` | 11 Ui Ux | 317 | 19.5% |
| `JF10_PROD_BA` | 10 Prod Ba | 291 | 17.9% |
| `JF05_DEVOPS` | 05 Devops | 136 | 8.36% |
| `JF12_EMBEDDED` | 12 Embedded | 123 | 7.56% |
| `JF08_QA_QC` | 08 Qa Qc | 106 | 6.52% |
| `JF07_DATA_AI` | 07 Data Ai | 80 | 4.92% |
| `JF09_SECURITY` | 09 Security | 75 | 4.61% |
| `JF04_MOBILE` | 04 Mobile | 55 | 3.38% |
| `JF01_BACKEND` | 01 Backend | 39 | 2.4% |
| `JF03_FULLSTACK` | 03 Fullstack | 30 | 1.85% |
| `JF06_DATA_ENG` | 06 Data Eng | 25 | 1.54% |
| `JF02_FRONTEND` | 02 Frontend | 4 | 0.25% |

---

## 4. Từ Điển Dữ Liệu Bảng Phẳng Chuẩn (Data Dictionary)

| Tên Cột Chuẩn | Kiểu Dữ Liệu | Nguồn Gốc (Origin) | Mô Tả & Quy Tắc Xử Lý |
| :--- | :--- | :--- | :--- |
| `job_id_global` | `str` | Metadata | Mã định danh duy nhất xuyên hệ thống: `topcv_<id>` |
| `source_platform` | `str` | Metadata | Tên sàn tuyển dụng: `topcv` |
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
