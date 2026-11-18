# Bước 04: Normalization

> Code: `preprocessing/normalization/run.py` (`work_mode` (N14), `_fallback_tinh` (N13), `process_source`, `run`), `location_normalizer.py`, `job_title.py` (`FAMILY_MAP`, `family_from_title`), `skill_normalizer.py`, `company_key.py`, `log_transformer.py`; `preprocessing/missing_outlier/missing_rules.py` (`infer_level_from_experience` (M3c), `infer_experience_from_level` (M4), `tinh_status` (M7), `range_flags` (M8)), `outlier_handler.py`; từ điển `provinces_34.json`, `wards_34.json`, `job_titles.json`, `skills.json`, `skills_taxonomy.json`.
> Lệnh: `python scripts/run_preprocessing.py --step normalization --source all [--dry-run]`.
> Dữ liệu mẫu: chưa có. Bảng 04 trên máy chưa được dựng lại từ 03 ngày 18/11. Report trong git là lần chạy 10–11/11.
> Prompt: [`docs/prompting/preprocessing/04_normalization.md`](../../prompting/preprocessing/04_normalization.md).
>
> **Trạng thái của file này:** mục 2.1 là luật đang chạy (số lần chạy 10–11/11). Mục 2.2 là luật mới **chờ duyệt**: chọn giá trị cuối cho `work_mode`, `employment_type`, `exp_min_years` từ các cột T9 của bước 03.

## 1. Mục đích

- Đưa giá trị về **danh mục chuẩn chung cho 8 sàn**, để BI và mô hình đếm và so sánh được: 34 tỉnh, 5 cấp bậc, 10 nhóm nghề + Other, kỹ năng chuẩn, khóa công ty.
- Chọn **giá trị cuối** khi bước 03 để lại hai nguồn (ô của sàn và JD).
- Xử lý thiếu và ngoại lai bằng **cờ**, không xóa dòng, không điền trung bình.
- Tiêu chí: consistency, completeness, accuracy. Phục vụ cả 5 SD.
- Ranh giới: không bỏ dòng; không ghi đè cột gốc (`raw_*`, cột parse của 03); không bù lương bằng trung bình hay trung vị. N6 (cap) chạy trước N7 (log).

## 2. Luật

### 2.1. Luật đang chạy (số lần chạy 10–11/11)

| Mã | Luật | Hành động | Số tin |
|---|---|---|---|
| N1 | Tỉnh: bỏ dấu, chữ thường, bỏ "tp", "tỉnh", "thành phố", rồi tra bí danh trong `provinces_34.json`. Tên cũ đổi sang tên mới, giữ tên cũ ở `tinh_cu` (Bình Dương → TP. Hồ Chí Minh). "Remote" → `remote` = true. Tên nước ngoài → `ngoai_vn` = true. `tinh_chinh` là tỉnh đầu tiên khác null | modify | 4.574 |
| N13 | `locations` không ra tỉnh thì lấy từ `raw_location_text`, rồi từ `company_address` (`tinh_source`) | modify | 656 |
| N14 | `work_mode` chỉ từ địa điểm và tiêu đề: remote → hybrid → onsite (khi có tỉnh) → unknown | modify | 4.671 |
| M7 | `tinh_status` (`ok`, `remote`, `ngoai_vn`, `unknown`) | flag | 94 unknown |
| N2 | Cấp bậc lấy từ `raw_seniority_text`, rồi từ tiêu đề, theo từ nguyên vẹn. "Nhân viên", "Chuyên viên" không tính là cấp | modify | 4.283 |
| M3c | Cấp bậc còn trống thì suy từ số năm kinh nghiệm: [0,1) Intern/Fresher, [1,2) Junior, [2,4) Middle, [4,5) Senior; từ 5 năm trở lên để trống (L-39). Gắn `level_inferred` | flag | 2.516 |
| M4 | Thiếu kinh nghiệm thì điền cận dưới theo cấp bậc (Intern/Fresher 0, Junior 1, Middle 2, Senior 4, Lead/Manager 5), **chỉ khi cấp lấy từ ô của sàn hoặc tiêu đề**, không lấy cấp suy từ số năm (chống vòng với M3c). Gắn `exp_inferred`, `exp_source` = `level_<cấp>` (ví dụ `level_intern`); có sẵn thì `given`. Tên luật trong report vẫn ghi "Intern/Fresher … điền 0", hẹp hơn code (mục 7) | flag | 192 |
| N2b | Senior hoặc Trưởng nhóm mà kinh nghiệm < 2 năm, hoặc Thực tập hoặc Mới tốt nghiệp mà ≥ 3 năm → `seniority_can_kiem`. Có nhóm nghề mà JD không có kỹ năng → `job_family_can_kiem` | flag | 115 + 258 |
| N16 | Chức danh chuẩn từ `job_titles.json` (exact, alias, fuzzy) | modify | 2.091 |
| N3 | Nhóm nghề: chức danh lõi → chức danh chuẩn → nhóm, gộp về 10 nhóm qua `FAMILY_MAP`. Luật không ra thì Other | modify | 3.964 khác Other |
| N4 | Kỹ năng về tên chuẩn ("ReactJS", "React.js" → "React"), bỏ trùng → `skills_std` | modify | 4.337 |
| N5 | `company_norm`: bỏ "Công ty Cổ phần", "TNHH", … | modify | 4.668 |
| N18 | `company_key`: rapidfuzz `token_sort_ratio` ≥ 90 và quan hệ tập con | modify | 4.668 |
| N6a | Lương tháng ngoài 1–500 triệu: bỏ số, gắn `salary_suspect` (trước IQR) | flag | 15 |
| N6 | IQR toàn bộ → `is_outlier_salary`; winsorize 1–99% ra `*_capped` | modify | 104 |
| M5 | Lương ngoài 2–100 triệu/tháng → `salary_out_of_range` | flag | 74 |
| M6 | IQR theo cấp bậc → `salary_iqr_outlier_by_level` | flag | 150 |
| M8 | min > max, kinh nghiệm ngoài khoảng → cờ | flag | 5 |
| N7 | `log1p` lương, sau N6 | modify | 2.081 |

Nhóm nghề sau L-47: Web 1.853, Other 707, Bridge 533, Data/AI 430, Tester 429, DevOps/Cloud 258, Security 254, Design 78, Game 61, IoT 38, Mobile 30.

### 2.2. Luật mới (đề xuất 18/11, chờ duyệt)

Các luật này dùng quyết định của người dùng ngày 18/11, ghi trong `jd_extraction.json` → `decisions`.

| Mã | Luật | Hành động | Cột |
|---|---|---|---|
| **N14 (sửa)** | `work_mode` lấy theo thứ tự: (1) `work_mode_raw`, nhưng nếu `work_mode_conflict` và `work_mode_jd_strong` thì lấy `work_mode_jd`; (2) `work_mode_jd`; (3) luật N14 cũ (địa điểm, tiêu đề); (4) `unknown` | modify | `work_mode`, `work_mode_source` (`raw`, `jd`, `jd_over_raw`, `location`, `unknown`) |
| **N19** | `employment_type`: tiêu đề có Intern (EI1) → internship; nếu không thì `employment_type_raw`; trống thì `employment_type_jd` | modify | `employment_type`, `employment_type_source` |
| **N2 (bổ sung)** | Tiêu đề có Intern hoặc `employment_type` = internship mà N2 chưa ra cấp → Intern/Fresher, `seniority_source` = `employment_type` | modify | `seniority` |
| **M4 (sửa)** | `exp_min_years` cuối: itviec lấy JD trước (`exp_min_years_jd`), ô JSON-LD làm dự phòng; 7 nguồn còn lại lấy ô của sàn trước, JD bù chỗ trống; còn trống thì điền cận dưới theo cấp bậc như M4 cũ. `exp_conflict` khi ô và JD lệch ≥ 1 năm. Giá trị parse của 03 giữ ở `exp_min_years_parsed` để truy vết | modify | `exp_min_years`, `exp_source` (`raw`, `jd`, `jd_zero`, `itviec_jsonld`, `level_*`, `unknown`; `raw` thay cho `given` cũ), `exp_conflict`, `exp_min_years_parsed` |
| **S1** | Ghi `silver.parquet`: chọn cột, đổi tên sang tiếng Anh, không tính lại (xem [`silver.md`](silver.md)) | — | — |

## 3. Quy trình xử lý

Thứ tự trong `process_source` (đọc code khi viết phần mới):

1. Địa điểm: N1 trên `locations` → `tinh_chinh`, `tinh_cu`, `tinh_key`. Thiếu thì N13.
2. **N14** → `work_mode` (bản mới: dùng cột T9 trước), rồi **M7** `tinh_status`.
3. Cấp bậc: **N2** → **M3c** → **M4**, rồi **N2b**.
4. Chức danh: **N16**. Nhóm nghề: **N3**.
5. Kỹ năng: **N4**. Công ty: **N5**, **N18**.
6. Lương: **N6a** → **N6** → **M5** → **M6** → **M8** → **N7**.
7. Ghi `anomalies.json` (mọi tin bị gắn cờ, kèm `job_id`, nguồn, loại cờ). Luật bảo toàn. Ghi `all.parquet`, rồi **S1** ghi `silver.parquet`.

## 4. Input → Output

| | Đường dẫn |
|---|---|
| Input | `data/preprocessing/03_transformation/all.parquet` |
| Output | `data/preprocessing/04_normalization/all.parquet` (bảng 04 = Golden Master, giữ mọi cột trước đó và thêm cột của bước này); `anomalies.json`; `silver.parquet` (S1) |
| Report | `reports/preprocessing/04_normalization/`; `extra.global_salary_stats`, `extra.anomalies_by_kind`, `extra.company_pairs_pending`, `extra.work_mode_distribution` |

**Cột thêm:**

| Nhóm | Cột |
|---|---|
| Địa điểm | `tinh_chinh`, `tinh_cu`, `tinh_key`, `tinh_source`, `tinh_status`, `remote`, `ngoai_vn` |
| Hình thức làm việc | `work_mode` (+ `work_mode_source` mới) |
| Cấp bậc | `seniority`, `seniority_level` (0–4), `seniority_source`, `level_inferred`, `seniority_can_kiem` |
| Nhóm nghề | `job_family`, `job_family_source`, `job_family_can_kiem`, `job_family_generic_title`, `job_title_core`, `title_canonical`, `title_match_score`, `title_tech_hint` |
| Kỹ năng | `skills_std` |
| Công ty | `company_norm`, `company_key` |
| Kinh nghiệm | `exp_min_years` (cuối), `exp_inferred`, `exp_source` (+ `exp_conflict`, `exp_min_years_parsed` mới) |
| Lương | `salary_min_vnd_capped`, `salary_max_vnd_capped`, `log_salary_min`, `log_salary_max`, `is_outlier_salary`, `salary_status`, `salary_out_of_range`, `salary_iqr_outlier_by_level`, `salary_iqr_scope`, `salary_iqr_upper` |
| Loại hình (mới) | `employment_type`, `employment_type_source` |

## 5. Dữ liệu mẫu

Điền sau khi chạy 04 trên bảng 03 mới (`python scripts/build_step_samples.py --step 04_normalization`). Với tin mẫu `topcv_2325743`, kỳ vọng:

| Cột | Kỳ vọng | Luật |
|---|---|---|
| `tinh_chinh` | TP. Hà Nội | N1 |
| `work_mode` / `work_mode_source` | onsite / raw | N14 mới |
| `seniority` | Junior. "Nhân viên" không tính là cấp, nên suy từ 1 năm kinh nghiệm | M3c |
| `exp_min_years` / `exp_source` | 1,0 / raw | M4 mới |
| `job_family` | Web (chức danh Backend Developer) | N3 |
| `employment_type` | full_time / raw | N19 |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Không bỏ dòng | vào = ra |
| N6 chạy trước N7 | Thứ tự trong report |
| Mọi tỉnh cũ tra ra đúng tỉnh mới; không còn hai cách viết của một tỉnh | 0 lỗi |
| Nhóm nghề trên 50 tin gán tay (seed 42) | ≥ 90% (chưa đo) |
| Bảng chéo `raw_seniority_text` × `seniority` (VietnamWorks, TopCV) | Đọc tay |
| `work_mode_source`, `exp_source` có đủ giá trị và đếm theo nguồn | Khớp số đo của `review_jd_dictionary.py` |
| Test | `pytest tests/unit/test_normalization_step.py tests/unit/test_ph6_ph7_normalization.py` (thêm test N14 mới, N19, M4 mới) |

## 7. Trạng thái, chỗ thiếu, việc mở

- **Trạng thái:** có code cho 2.1, chạy thật 10–11/11. Luật mới 2.2 chờ duyệt. Chưa chạy lại trên dữ liệu 18/11.
- **Chỗ thiếu (lần chạy 10–11/11):**
  - 8,3% thiếu cấp bậc;
  - 94 tin `tinh_unknown`;
  - 258 tin `job_family_can_kiem`;
  - 87/140 mục `job_titles.json` chưa duyệt;
  - tỉnh có thể lấy từ trụ sở công ty thay vì nơi làm việc (PRE-38);
  - `work_mode` mặc định onsite khi có tỉnh (sửa bằng N14 mới).
- **Lệch tên luật:** report ghi M4 là "Intern/Fresher thiếu kinh nghiệm điền 0", nhưng `infer_experience_from_level` điền cận dưới cho mọi cấp. Sửa chuỗi tên luật khi chạy lại 04.
- **Việc mở:** PRE-33, PRE-35, PRE-37 (việc 3), PRE-38, PRE-39.
