# Bước 04: Normalization

> Code: `preprocessing/normalization/run.py` (`work_mode` (N14), `_fallback_tinh` (N13), `process_source`, `run`), `location_normalizer.py`, `job_title.py` (`FAMILY_MAP`, `family_from_title`), `skill_normalizer.py`, `company_key.py`, `log_transformer.py`; `preprocessing/missing_outlier/missing_rules.py` (`infer_level_from_experience` (M3c), `infer_experience_from_level` (M4), `tinh_status` (M7), `range_flags` (M8)), `outlier_handler.py`; từ điển `provinces_34.json`, `wards_34.json`, `job_titles.json`, `skills.json`, `skills_taxonomy.json`.
> Lệnh: `python scripts/run_preprocessing.py --step normalization --source all [--dry-run]`.
> Dữ liệu mẫu: [`samples/04_normalization.json`](samples/04_normalization.json) (chạy thật 19/11/2026 trên bảng 03 sau bộ lọc IT ba tầng và dịch lại).
> Prompt: [`docs/prompting/preprocessing/04_normalization.md`](../../prompting/preprocessing/04_normalization.md).
>
> **Trạng thái của file này:** mục 2.1 và 2.2 là luật đang chạy (duyệt và chạy thật 19/11). Mục 2.2: chọn giá trị cuối cho `work_mode`, `employment_type`, `exp_min_years` từ các cột T9 của bước 03.

## 1. Mục đích

- Đưa giá trị về **danh mục chuẩn chung cho 8 sàn**, để BI và mô hình đếm và so sánh được: 34 tỉnh, 5 cấp bậc, 11 nhóm nghề + Other, kỹ năng chuẩn, khóa công ty.
- Chọn **giá trị cuối** khi bước 03 để lại hai nguồn (ô của sàn và JD).
- Xử lý thiếu và ngoại lai bằng **cờ**, không xóa dòng, không điền trung bình.
- Tiêu chí: consistency, completeness, accuracy. Phục vụ cả 5 SD.
- Ranh giới: không bỏ dòng, trừ luật cách ly Q1 (tin chuyển sang `quarantine.parquet`, có bảo toàn `vào = ra + cách ly`); không ghi đè cột gốc (`raw_*`, cột parse của 03); không bù lương bằng trung bình hay trung vị. N6 (cap) chạy trước N7 (log).

## 2. Luật

### 2.1. Luật đang chạy (số lần chạy 19/11, đếm trên 3.997 tin vào, trước khi Q1 cách ly 81 tin)

| Mã | Luật | Hành động | Số tin |
|---|---|---|---|
| N1 | Tỉnh: bỏ dấu, chữ thường, bỏ "tp", "tỉnh", "thành phố", rồi tra bí danh trong `provinces_34.json`. Tên cũ đổi sang tên mới, giữ tên cũ ở `tinh_cu` (Bình Dương → TP. Hồ Chí Minh). "Remote" → `remote` = true. Tên nước ngoài → `ngoai_vn` = true. `tinh_chinh` là tỉnh đầu tiên khác null | modify | 3.924 |
| N13 | `locations` không ra tỉnh thì lấy từ `raw_location_text`, rồi từ `company_address` (`tinh_source`) | modify | 629 |
| N14 | `work_mode` chỉ từ địa điểm và tiêu đề: remote → hybrid → onsite (khi có tỉnh) → unknown. **Từ 19/11 chỉ còn là bậc 3 của N14 mới (mục 2.2)** | modify | 1.708 tin dùng bậc này (`work_mode_source` = `location`) |
| M7 | `tinh_status` (`ok`, `remote`, `ngoai_vn`, `unknown`) | flag | 65 unknown (bảng 3.916 tin) |
| N2 | Cấp bậc lấy từ `raw_seniority_text`, rồi từ tiêu đề, theo từ nguyên vẹn. "Nhân viên", "Chuyên viên" không tính là cấp | modify | 3.707 |
| M3c | Cấp bậc còn trống thì suy từ số năm kinh nghiệm: [0,1) Intern/Fresher, [1,2) Junior, [2,4) Middle, [4,5) Senior; từ 5 năm trở lên để trống (L-39). Gắn `level_inferred` | flag | 2.120 |
| M4 | Thiếu kinh nghiệm thì điền cận dưới theo cấp bậc (Intern/Fresher 0, Junior 1, Middle 2, Senior 4, Lead/Manager 5), **chỉ khi cấp lấy từ ô của sàn hoặc tiêu đề**, không lấy cấp suy từ số năm (chống vòng với M3c). Gắn `exp_inferred`, `exp_source` = `level_<cấp>` (ví dụ `level_intern`); có sẵn thì `given`. Tên luật trong report vẫn ghi "Intern/Fresher … điền 0", hẹp hơn code (đã sửa tên luật 19/11) | flag | 54 |
| N2b | Senior hoặc Trưởng nhóm mà kinh nghiệm < 2 năm, hoặc Thực tập hoặc Mới tốt nghiệp mà ≥ 3 năm → `seniority_can_kiem`. Có nhóm nghề mà JD không có kỹ năng → `job_family_can_kiem` | flag | 441 (cộng hai cờ) |
| N16 | Chức danh chuẩn từ `job_titles.json` (exact, alias, fuzzy) | modify | 1.744 |
| N3 | Nhóm nghề: chức danh lõi → chức danh chuẩn → nhóm, gộp về 10 nhóm qua `FAMILY_MAP`. Luật không ra thì Other. **Thay bằng N3a–N3d (mục 2.3) từ 21/11** | modify | 3.462 khác Other (bảng 3.916 tin: 3.390; Web 1.536, Other 526, Bridge 479, Data/AI 388, Tester 382, DevOps/Cloud 234, Security 231, Design 61, Game 43, Mobile 26, IoT 10) |
| N4 | Kỹ năng về tên chuẩn ("ReactJS", "React.js" → "React"), bỏ trùng → `skills_std` | modify | 3.540 |
| N5 | `company_norm`: bỏ "Công ty Cổ phần", "TNHH", … | modify | 3.996 |
| N18 | `company_key`: rapidfuzz `token_sort_ratio` ≥ 90 và quan hệ tập con | modify | 3.915 (tính trên bảng không cách ly) |
| N6a | Lương tháng ngoài 1–500 triệu: bỏ số, gắn `salary_suspect` (trước IQR) | flag | 12 |
| N6 | IQR toàn bộ → `is_outlier_salary`; winsorize 1–99% ra `*_capped` | modify | 87 |
| M5 | Lương ngoài 2–100 triệu/tháng → `salary_out_of_range` | flag | 59 |
| M6 | IQR theo cấp bậc → `salary_iqr_outlier_by_level` | flag | 109 |
| M8 | min > max, kinh nghiệm ngoài khoảng → cờ | flag | 4 |
| N7 | `log1p` lương, sau N6 | modify | 1.685 |

Nhóm nghề sau L-47: Web 1.853, Other 707, Bridge 533, Data/AI 430, Tester 429, DevOps/Cloud 258, Security 254, Design 78, Game 61, IoT 38, Mobile 30.

### 2.2. Luật mới (người dùng duyệt 19/11: N14, N19, N2, M4, S1 "oke tui thấy duyệt được á"; Q1 "oke")

Các luật này dùng quyết định của người dùng ngày 18/11, ghi trong `jd_extraction.json` → `decisions`.

| Mã | Luật | Hành động | Cột |
|---|---|---|---|
| **N14 (sửa)** | `work_mode` lấy theo thứ tự: (1) `work_mode_raw`, nhưng nếu `work_mode_conflict` và `work_mode_jd_strong` thì lấy `work_mode_jd`; (2) `work_mode_jd`; (3) luật N14 cũ (địa điểm, tiêu đề); (4) `unknown` | modify | `work_mode`, `work_mode_source` (`raw`, `jd`, `jd_over_raw`, `location`, `unknown`) |
| **N19** | `employment_type`: tiêu đề có Intern (EI1) → internship; nếu không thì `employment_type_raw`; trống thì `employment_type_jd` | modify | `employment_type`, `employment_type_source` |
| **N2 (bổ sung)** | Tiêu đề có Intern hoặc `employment_type` = internship mà N2 chưa ra cấp → Intern/Fresher, `seniority_source` = `employment_type` | modify | `seniority` |
| **M4 (sửa)** | `exp_min_years` cuối: itviec lấy JD trước (`exp_min_years_jd`), ô JSON-LD làm dự phòng; 7 nguồn còn lại lấy ô của sàn trước, JD bù chỗ trống; còn trống thì điền cận dưới theo cấp bậc như M4 cũ. `exp_conflict` khi ô và JD lệch ≥ 1 năm. Giá trị parse của 03 giữ ở `exp_min_years_parsed` để truy vết | modify | `exp_min_years`, `exp_source` (`raw`, `jd`, `jd_zero`, `itviec_jsonld`, `level_*`, `unknown`; `raw` thay cho `given` cũ), `exp_conflict`, `exp_min_years_parsed` |
| **S1** | Ghi `silver.parquet` (26 cột, gồm `employment_type` và 3 cờ `seniority_inferred`, `exp_inferred`, `salary_outlier`; bổ sung 18/11): chọn cột, đổi tên sang tiếng Anh, không tính lại (xem [`silver.md`](silver.md)) | — | — |
| **Q1** | **Cách ly tin chưa xử lý xong** (người dùng chốt 19/11: "loại khỏi silver và lưu các tin failed ở một trạng thái khác", "loại cả mining và silver", "đồng nhất phần silver và cho processing và mining"). Tin có `translation_status` = `failed` (sau khi đã dịch lại, PRE-34) **không vào `all.parquet`** mà ghi sang `data/preprocessing/04_normalization/quarantine.parquet`: cùng cột với `all.parquet`, thêm `quarantine_reason` (`TRANSLATION_FAILED`). Vì Silver (S1), Processing 07–10 và Mining đều đọc `all.parquet`, cả ba có cùng tập tin, không nơi nào phải tự lọc. Bảo toàn: `vào = all.parquet + quarantine.parquet`. Report ghi số tin cách ly theo nguồn và lý do (luật `Q1`, hành động drop trong report để kiểm bảo toàn). Tin cách ly vẫn qua mọi luật của từng tin nên có đủ cột; các phép thống kê trên cả bảng (N6 IQR, winsorize, N18 `company_key`) **chỉ tính trên tin không cách ly**, để số Mining dùng không bị tin cách ly kéo lệch. Dịch lại được thì chạy lại 03 → 04, tin tự quay về | cách ly | `quarantine_reason` |

**Ghi chú khi code (19/11):**

- Code: `preprocessing/normalization/final_values.py` (`final_work_mode`, `final_employment_type`, `select_experience`, `quarantine_reason`), nối vào `run.py`. Test: `tests/unit/test_normalization_final_values.py`.
- N19 dùng đúng mẫu EI1 của `jd_extraction.json` (cùng định nghĩa với bước 03), khớp từ nguyên vẹn ("International" không khớp "intern").
- Thứ tự trong một tin: N19 → M4 chọn (ô/JD) → N2 (ô, tiêu đề) → N2 bổ sung (internship) → M3c (số năm) → M4 điền theo cấp bậc (chỉ khi cấp từ ô hoặc tiêu đề, như M4 cũ).
- `level_inferred` (Silver `seniority_inferred`) theo nghĩa ở spec 05 mục 4.4: true khi cấp bậc do bước 04 suy ra từ tiêu đề, số năm hoặc loại hợp đồng; false khi lấy từ ô của sàn. Trước đây chỉ true khi suy từ số năm, nên số tin `level_inferred` sẽ tăng.
- `exp_max_years` giữ giá trị của bước 03 (luật M4 chỉ nói `exp_min_years`); lệch với `exp_min_years` lấy từ JD thì M8 gắn cờ.
- Report thêm luật `N14`, `N19`, `N2c`, `M4s` (lấy từ JD khi ô trống), `M4c` (`exp_conflict`), `Q1`; `extra` thêm `quarantine`, phân bố `employment_type`, `work_mode_source`, `exp_source`, `seniority_source`.

### 2.3. Luật nhóm nghề mới (PRE-44, người dùng chốt 21/11: "1.b 2 (lớp JD) 3.a 4.a", "5.a 6.a")

Lý do: N3 cũ tra `job_titles.json` **trước** từ khóa tiêu đề, mà từ điển gán thẳng các chức danh chung ("IT" 394 tin, "Developer" 317, "Lập Trình" 146, "IT Engineer" 81, "CNTT", "Kỹ Thuật", "Technical") vào Web. Mọi tiêu đề có chữ "IT" thành Web ("IT Security Analyst", "IT Helpdesk", "IT Business Analyst"); "AI Engineer" khớp gần đúng "IT Engineer" thành Web (73 tin); luật từ khóa cụ thể không bao giờ được xét. Mô phỏng chỉ đọc trên bảng 3.916 tin ngày 21/11: 873 tin đổi nghề.

| Mã | Luật | Hành động | Cột |
|---|---|---|---|
| **N3a** | Thứ tự (quyết định 1.B): (1) chức danh chuẩn **cụ thể** trong `job_titles.json` → nhóm của nó; (2) từ khóa tiêu đề (`FAMILY_RULES_V2`); (3) chức danh chuẩn **chung về lập trình** (`GENERIC_DEV_TITLES`: Developer, Lập Trình, Lập Trình Viên, Software Engineer, Software Developer, Phát Triển Phần Mềm) → nhóm của nó (Web); (4) chức danh **chung về IT** (`GENERIC_IT_TITLES`: IT, CNTT, Công Nghệ Thông Tin, Kỹ Thuật, Technical, IT Engineer, IT Staff, Kỹ Sư IT, KỸ THUẬT VIÊN IT PHẦN MỀM, Kỹ Thuật IT) không quyết định nhóm, sang N3b; (5) kỹ năng cổng (≥ 2 kỹ năng của đúng một nhóm); (6) Other | modify | `job_family`, `job_family_source` (`canonical`, `title`, `canonical_generic`, `jd`, `skills`, `none`) |
| **N3b** | **Lớp JD** (quyết định 2, chỉ cho tiêu đề chung về IT không có từ khóa nghề): đếm tín hiệu từng nhóm trong `description_fold` + `requirements_fold` (từ khóa tiêu đề của nhóm, bỏ các từ quá chung `JD_WEAK_TERMS` như "bảo mật", "ai", "pm", "cloud"; nhóm Infra/Support thêm từ vựng hỗ trợ `INFRA_JD_TERMS` như "máy tính", "máy in", "mạng lan", "helpdesk") cộng số kỹ năng cổng trong `skills_std`. Nhóm có nhiều tín hiệu nhất thắng nếu ≥ 2 tín hiệu và hơn nhóm thứ hai ≥ 1; không thì sang kỹ năng cổng rồi Other (quyết định 5.A). Không áp dụng cho chức danh chung về lập trình (JD đẩy "Backend Developer" sang DevOps vì nhắc docker, aws) | modify | `job_family_source` = `jd` |
| **N3c** | Nhóm mới **`Infra/Support`** (hiển thị "IT hạ tầng & hỗ trợ"; quyết định 3.A, 6.A): `FAMILY_MAP["System/Network"]` = `Infra/Support` thay cho Security. Có 11 nhóm + Other | modify | `job_family` |
| **N3d** | Sửa nhóm trong `job_titles.json` (quyết định 4.A): Thiết Kế, Product Designer, Designer POD, Thiết Kế 2D → Design; Agentic Engineer → Data/AI; Odoo Developer → Bridge; Quản Trị Cơ Sở Dữ Liệu DBA → Data/AI | modify | từ điển |

| **N16b** | Khớp gần đúng (L-58): bỏ ứng viên khi mỗi bên có một từ viết tắt nghề IT (`TITLE_ACRONYMS`: it, ai, bi, ba, qa, qc, ui, ux, ml, pm, po, dba, sre, erp, crm, sap, seo, hr) mà bên kia không có ("ai specialist" ≠ "it specialist", "bi engineer" ≠ "it engineer"), xét ứng viên kế tiếp. Từ khóa Data/AI thêm "bi engineer" | modify | `title_canonical`, `title_canonical_source` |

Mô phỏng 21/11 (trước → sau): Web 1.536 → 795, Other 526 → 611, Bridge 479 → 539, Data/AI 388 → 517, Infra/Support 0 → 405, Tester 382 → 395, DevOps/Cloud 234 → 253, Security 231 → 145, Design 61 → 109, Mobile 26 → 92, Game 43, IoT 10 → 12. Lớp JD trên 306 tin tiêu đề chung về IT: Infra/Support 183, Web 16, Bridge 9, Data/AI 5, DevOps/Cloud 5, Security 2, Tester 1, không rõ 85 (→ Other).

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

- **Trạng thái:** có code cho 2.1 và 2.2 (trừ S1). **Chạy thật 19/11:** 3.997 vào → `all.parquet` 3.916 + `quarantine.parquet` 81 (itviec 49, glints 9, vietnamworks 9, topcv 5, jobsgo 4, careerviet 3, topdev 2), bảo toàn đạt. Luật mới: N14 lấy từ ô 2.119 / JD 52 / JD thắng ô 7 / địa điểm 1.708 / unknown 30; N19 có giá trị 3.738 (trống 253, phần lớn topdev; internship 192); M4 nguồn: ô 2.919, JD 664, JSON-LD itviec 144, JD "không yêu cầu" 54, theo cấp 51, trống 84; `exp_conflict` 724 (itviec 424 vì JSON-LD chỉ 3 mức); N2c 0 (tin internship đều đã ra Intern/Fresher từ tiêu đề). `level_inferred` (Silver `seniority_inferred`) true ở 2.978/3.916 tin: cấp từ ô của sàn chỉ 653 tin. S1 (Silver) chạy sau bước 08: `python -m preprocessing.normalization.silver`, 3.916 dòng, 26 trường, kiểm đạt (19/11, `silver.md` mục 7).
- **Chỗ thiếu (lần chạy 19/11):**
  - 285/3.916 tin (7,3%) thiếu cấp bậc;
  - 65 tin `tinh_unknown`;
  - 441 tin có cờ cần kiểm (`seniority_can_kiem` hoặc `job_family_can_kiem`);
  - 87/140 mục `job_titles.json` chưa duyệt;
  - tỉnh có thể lấy từ trụ sở công ty thay vì nơi làm việc (PRE-38);
  - `work_mode` theo địa điểm (mặc định onsite khi có tỉnh) vẫn là nguồn của 1.708 tin không có ô và JD.
- **Việc mở:** PRE-33, PRE-35, PRE-37 (việc 3), PRE-38, PRE-39.
