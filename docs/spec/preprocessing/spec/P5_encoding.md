# P5. Encoding: đổi bộ golden sang bảng số cho mô hình

> **Cập nhật 10/11/2026: dự án bỏ JEV, OpenJev, Qwen và Gemini.** Phân loại và chuẩn hóa chỉ dùng luật if-else. Model duy nhất được dùng: `VietAI/envit5-translation` để dịch JD tiếng Anh sang tiếng Việt (P3 T6b), chạy local. Mọi đoạn nói về JEV, LLM, GenAI, `--use-api`, sổ tiền API đã hết hiệu lực. Xem `docs/spec/preprocessing/spec/P0_pipeline_contract.md` mục 6 và `docs/issue_log.md` L-28.

> Trạng thái: **đặc tả, chờ duyệt** (sửa 03/11/2026: tỉnh theo 34 tỉnh mới; 10/11/2026: bỏ cột xác suất JEV). Cần P4 xong trước.
> Prompt: `docs/prompting/P5_encoding.md`.

## 1. Ngữ cảnh

- Pipeline cũ dừng ở bảng chữ đã chuẩn hóa, chưa có bước mã hóa. Các bước phân tích sau (phân cụm, dự đoán lương, luật kết hợp kỹ năng) cần bảng số.
- Bộ golden (output P4) vẫn là bản cho người đọc. Encoding chỉ đọc bộ golden, không sửa nó.

## 2. Input

`data/preprocessing/04_normalization/all.parquet`.

## 3. Output

- `data/preprocessing/05_encoding/features.parquet`: mỗi dòng một tin, khóa `job_id_global`, chỉ có cột số.
- `data/preprocessing/05_encoding/encoding_dictionary.json`: với mỗi cột mã hóa, ghi cột gốc, cách mã hóa, danh sách giá trị → mã, và giá trị nào gom vào `other`.

## 4. Hướng xử lý

| Mã | Cột gốc | Cách | Ví dụ |
|---|---|---|---|
| E1 | `seniority` | ordinal 0–4 theo thứ tự Intern/Fresher → Lead/Manager, "Chưa rõ" = -1 | "Junior" → 1 |
| E2 | `job_family`, `source_platform`, `raw_employment_type` (đã chuẩn hóa) | one-hot; tên cột dùng mã không dấu, từ điển giữ nhãn tiếng Việt | "Backend" → `job_family__backend=1` |
| E3 | `locations[].tinh_key` (34 tỉnh) | multi-hot cho 10 tỉnh nhiều tin nhất, còn lại `tinh__other`; thêm `remote`, `ngoai_vn` 0/1 | `["ha_noi","da_nang"]` → 2 cột = 1 |
| E4 | `skills_std` | multi-hot cho K kỹ năng phổ biến nhất (đề xuất K = 200, hoặc kỹ năng có ≥ 20 tin), còn lại đếm vào `skills__other_count` | |
| E5 | `log_salary_min`, `log_salary_max`, `exp_min_years`, `exp_max_years`, `headcount` | giữ số; null giữ NaN, thêm cột `<cột>__missing` 0/1 | |
| E6 | `is_negotiable`, `is_outlier_salary` → 0/1; `it_status` → one-hot (`it`, `non_it`, `can_kiem`) | | |
| E7 | Ngày | `posted_month`, `days_to_deadline` | |
| E8 | `it_prob`, `seniority_prob`, `job_family_prob` | giữ số; null giữ NaN + `__missing` | |

- Không bù NaN bằng mean/median ở bước này. Mô hình nào cần thì tự xử lý, và cột `__missing` cho biết chỗ thiếu.
- Văn bản JD không mã hóa ở đây (TF-IDF/embedding làm ở phần phân tích).

### 4b. Chọn đặc trưng và xây đặc trưng (Processing, thêm 10/11/2026)

Giai đoạn Processing của dự án gồm 4 bước feature engineering (selection, extraction, transformation, construction) cùng encoding. Extraction và transformation đã nằm ở P3, P4; encoding là phần 4 ở trên. Hai bước còn lại:

- **Chọn đặc trưng (feature selection):** bỏ kỹ năng xuất hiện dưới 5 lần. Tiêu chí chọn khác: chưa chốt.
- **Xây đặc trưng (feature construction):** danh sách đặc trưng mới tạo: chưa chốt.

Chi tiết từng bước nằm ở `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` (bước 10b, 10c, 10d).

## 5. Ranh giới

- Không đổi giá trị đã chuẩn hóa, không bỏ dòng (`rows_out = rows_in`).
- Ngưỡng K, top 10 tỉnh ghi trong `encoding_dictionary.json`, không viết cứng ở chỗ khác.

## 6. Monitoring thấy gì

- Số cột theo nhóm (one-hot, multi-hot, số, cờ), tổng số cột.
- Tỉ lệ ô bằng 0 (độ thưa) của phần multi-hot kỹ năng.
- Top kỹ năng được mã hóa và số tin rơi vào `other`.

## 7. Tiêu chí xong và cách review

- Mọi cột trong `features.parquet` là số; số dòng bằng bộ golden.
- Giải mã ngược 5 dòng ngẫu nhiên bằng từ điển ra đúng giá trị trong bộ golden.
- Test: E1 ánh xạ đúng thứ tự bậc; E3, E4 giá trị ngoài top vào `other`; cột `__missing` khớp NaN.
