# BẢNG ÁNH XẠ TÍCH HỢP DỮ LIỆU ĐA NGUỒN (INTEGRATION MAPPING SHEET)

> **Người thực hiện:** [Tên thành viên]  
> **Nguồn phụ trách:** [Tên website]  
> **Dùng cho:** Cuộc họp Integration Summit thống nhất toàn nhóm.

---

## 1. Bảng Đối Chiếu Trường Của Nguồn Sang Common Target Schema

| STT | Trường đích (Common Target Schema) | Bắt buộc (Mandatory) | Tên trường tương ứng ở nguồn của bạn | Trạng thái nguồn | Quy tắc làm sạch / Chuyển đổi (Transformation Logic) |
| :---: | :--- | :---: | :--- | :---: | :--- |
| 1 | `job_id_global` | BẮT BUỘC | `...` | CÓ | Tạo UUID: `f"{source}_{id}"` |
| 2 | `job_title` | BẮT BUỘC | `...` | CÓ | Strip khoảng trắng, giữ nguyên hoa thường |
| 3 | `company_name` | BẮT BUỘC | `...` | CÓ | Strip khoảng trắng |
| 4 | `salary_min_vnd` | TÙY CHỌN | `...` | [CÓ / THIẾU] | Parse từ chuỗi ra float triệu VNĐ. Nếu USD nhân 25.4 |
| 5 | `salary_max_vnd` | TÙY CHỌN | `...` | [CÓ / THIẾU] | Parse từ chuỗi ra float triệu VNĐ. Nếu USD nhân 25.4 |
| 6 | `is_salary_negotiable` | BẮT BUỘC | `...` | CÓ | Gán 1 nếu lương là thỏa thuận, ngược lại 0 |
| 7 | `min_experience_years`| TÙY CHỌN | `...` | [CÓ / THIẾU] | Parse số năm ra float. "Không yêu cầu" $\rightarrow$ 0 |
| 8 | `work_location_city` | BẮT BUỘC | `...` | CÓ | Chuẩn hóa về: `"Hồ Chí Minh"`, `"Hà Nội"`, `"Đà Nẵng"`, `"Remote"` |
| 9 | `employment_type` | TÙY CHỌN | `...` | [CÓ / THIẾU] | Chuẩn hóa: Full-time, Part-time, Internship |
| 10 | `raw_skill_tags` | TÙY CHỌN | `...` | [CÓ / THIẾU] | Danh sách string các tag kỹ năng |
| 11 | `job_description_raw`| BẮT BUỘC | `...` | CÓ | Toàn văn mô tả (loại bỏ thẻ HTML rác) |
| 12 | `posted_date` | TÙY CHỌN | `...` | [CÓ / THIẾU] | Format về `YYYY-MM-DD` |
| 13 | `deadline_date` | TÙY CHỌN | `...` | [CÓ / THIẾU] | Format về `YYYY-MM-DD` |

---

## 2. Báo Cáo Trường Nguồn Có Mà Common Schema Chưa Có (Đặc thù)
*Những trường độc đáo của trang web bạn có thể đóng góp cho các phân tích mở rộng:*
1. Tên trường: `...` — Ý nghĩa: `...` $\rightarrow$ Đề xuất lưu vào `extended_attributes (JSONB)`.
2. Tên trường: `...` — Ý nghĩa: `...`

## 3. Báo Cáo Trường Nguồn Bị Thiếu (Gặp Khó Khăn Khi Map)
*Những trường trong Common Schema mà trang web của bạn hoàn toàn không có:*
1. Trường thiếu: `...` $\rightarrow$ Đề xuất: Điền `NULL` hoặc áp dụng trích xuất AI từ JD.
