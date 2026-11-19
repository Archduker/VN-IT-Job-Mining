# Bước 10: Features (10, 10b, 10c, 10d)

> Code: `processing/encoding/features.py` (`build_features`, `run`, `_onehot`, `_numeric`, `employment_class`); `processing/transformation/discretize.py` (`discretize`, `exp_bin`, 10); `processing/selection/sparsity.py` (`reduce_sparsity`, 10b); `processing/construction/features.py` (`construct`, `salary_ref_m`, 10c). Hằng `SENIORITY_MAP`, `TOP_PROVINCES_K`, `to_col_slug` ở `processing/encoding/constants.py` (F10.4, 19/11).
> Lệnh: `python scripts/run_preprocessing.py --step features --source all [--dry-run]` (hoặc `--step 10_features`).
> Dữ liệu mẫu: điền khi chạy lại trên bảng 04 mới.
> **Làm lại 19/11/2026 (P3 của kế hoạch yêu cầu dữ liệu, `docs/target/06_yeu_cau_du_lieu.md`)**: ba khối kỹ năng, bỏ bước 09, F10.1, F10.3 (thay bằng `n_tools`/`n_concepts`/`n_soft`), F10.4, F10.5. Chạy thật 19/11 trên bảng 04: 3.916 tin, 994 cột.

## 1. Mục đích

Một **ma trận số**, mỗi tin một dòng, dùng chung cho mọi bước Mining.

| Nhóm cột | SD dùng |
|---|---|
| `skill__*` (multi-hot, **K-tool**) | SD2 (giỏ kỹ năng), SD3 (ghép với e5), SD4 (đặc trưng model lương), SD5 |
| `concept__*` (K-concept), `soft__*` (K-soft) | SD2 bảng riêng, SD3 mô tả cụm, SD4 đặc trưng phụ, SD5 bảng kỹ năng mềm |
| `seniority_ord`, `exp_min_years`, `fam__*`, `tinh__*`, `wm__*`, `src__*` | SD3 (mô tả cụm, Isolation Forest), SD4 (model lương) |
| `n_tools`, `n_concepts`, `n_soft`, `n_skills`, `n_required`, `required_ratio`, `n_tokens`, `n_benefits` | SD3 (tìm tin "khác"; mã lý do M4 dùng `n_tools`), SD1 câu 1.5 (`n_tools`) |
| `salary_target_m` | Mục tiêu SD4 (chỉ tham chiếu, không làm đầu vào) |
| Cột suy từ lương (`salary_bin_*`, `salary_mid`, `salary_range_ratio`) | **Không dùng cho model lương** (mục 2.3) |

- Tiêu chí: **consistency** (cùng kiểu số cho mọi tin), **completeness** (thiếu thì đánh dấu, không điền bừa).
- Ranh giới: giữ đúng số dòng của bảng 04; không điền trung bình hay trung vị; cờ `seniority_can_kiem` giữ thành cột, Mining tự lọc; không có cột `it_status` (hằng) và không có `*_prob`.

## 2. Luật

### 2.1. Luật đang chạy

**Bước 10, rời rạc hóa** (`discretize.py`; thiếu giá trị thì -1):

| Cột | Cách tính |
|---|---|
| `salary_bin_range` | Lương tham chiếu (trung bình hai cận có số, triệu/tháng) chia theo mốc 10, 20, 35, 60 triệu (`SALARY_EDGES_M`, đề xuất): <10, 10–20, 20–35, 35–60, ≥60 |
| `salary_bin_eqfreq5` | 5 nhóm đều tần suất trên tin có lương (cần ≥ 5 tin có lương) |
| `exp_bin` | 0: dưới 1 năm; 1: 1–2; 2: 3–5; 3: trên 5 |

**Bước 10b, chọn kỹ năng** (`skill_block` + `sparsity.py`): ba khối lấy bằng `skill_view` của bước 08: `skill__` = K-tool (`type = tool`), `concept__` = K-concept, `soft__` = K-soft (soft, language). Kỹ năng kỹ thuật chưa có nhãn `type` không vào khối nào. Mỗi khối gom kỹ năng có DF < `min_df` = 15 tin (người dùng chốt 19/11 cho cả ba khối) vào `<khối>__other_skill`. Số tin không đổi. **Chạy 19/11:** `skill__` 291 cột (290 + other; gom 243 kỹ năng), `concept__` 562 (gom 312), `soft__` 63 (gom 12). Lần chạy 10/11 (từ điển 230, một khối): 171 cột.

**Bước 10c, xây đặc trưng** (`construction/features.py`; thiếu thì NaN):

| Cột | Cách tính |
|---|---|
| `n_skills` | Số kỹ năng khác nhau của tin trong bảng 08 (mọi loại) |
| `n_tools`, `n_concepts`, `n_soft` | Số kỹ năng của tin theo `skill_view` tool, concept, soft (trung vị 19/11: 5, 14, 5) |
| `n_required` | Số kỹ năng `required` |
| `required_ratio` | `n_required / n_skills` (NaN nếu không có kỹ năng) |
| `n_tokens` | Số từ (tách theo khoảng trắng) của `description_clean` + `requirements_clean`; bước 09 đã bỏ khỏi chuỗi (19/11). Trung vị 326 |
| `n_benefits` | Số phần tử của `benefits_std` |
| `salary_mid` | Trung bình `salary_min_vnd`, `salary_max_vnd` (triệu), chỉ khi có cả hai cận |
| `salary_range_ratio` | `(max − min) / mid`, chỉ khi có cả hai cận và `mid > 0` |
| `salary_target_m` | Mục tiêu SD4 (quyết định 4, 19/11): trung bình các cận có số của `salary_*_vnd_capped` (như Silver), triệu/tháng; một cận thì lấy cận đó. 1.731 tin có giá trị, trung vị 21,5. Chỉ tham chiếu: tên chứa "salary" nên `assert_no_leakage` chặn |

**Bước 10d, mã hóa:**

| Nhóm cột | Cách mã hóa |
|---|---|
| `skill__<slug>`, `concept__<slug>`, `soft__<slug>` | Multi-hot từ 08 theo ba khối, sau 10b |
| `seniority_ord` | Ordinal 0–4 theo `SENIORITY_MAP`; chưa rõ = -1 |
| `fam__*` | One-hot 10 nhóm nghề + Other (`FAMILY_MAP` ở `preprocessing/normalization/job_title.py`) |
| `src__*` | One-hot nguồn |
| `wm__*` | One-hot `work_mode` (onsite, remote, hybrid) + `wm__unknown` |
| `emp__*` | One-hot cột `employment_type` của bảng 04 (luật N19): full_time, part_time, internship, contract; null thì `emp__unknown` (F10.5, 19/11). Bỏ `employment_class` |
| `tinh__*`, `loc_remote`, `loc_ngoai_vn` | Multi-hot 10 tỉnh nhiều tin nhất (`TOP_PROVINCES_K`), xét mọi địa điểm của tin; còn lại `tinh__other`; không có tỉnh `tinh__unknown`. Tin mà `locations` không ra tỉnh thì dùng `tinh_chinh` |
| `log_salary_min`, `log_salary_max`, `exp_min_years`, `exp_max_years`, `headcount` | Giữ số; thiếu thì NaN kèm cột `__missing` |
| `pm__2026_09`, `pm__2026_10`, `pm__2026_11`, `pm__unknown` | One-hot cột `posted_month` (`YYYY-MM`) của bảng 04 (F10.1, 19/11). Bỏ cột số tháng 1–12 lấy từ `posted_date` |
| `days_to_deadline`, `days_to_deadline__missing` | Hạn nộp trừ `crawled_at` (ngày) |
| `salary_status__value`, `salary_status__unknown`, `is_negotiable`, `is_outlier_salary`, `seniority_can_kiem` | Cờ 0/1. Lương thỏa thuận và lương không ghi gộp vào `salary_status__unknown` (người dùng chốt 11/11) |

Báo cáo 10/11 ghi 242 cột; L-47 (11/11) 243 cột; **19/11: 994 cột** (ba khối kỹ năng 916).

### 2.2. Luật đề xuất (chờ người dùng duyệt)

| Mã | Đề xuất | Lý do |
|---|---|---|
| **F10.1** (**duyệt 18/11, làm 19/11**) | `posted_month` đổi sang cột `posted_month` (`YYYY-MM`) của bảng 04. Mã hóa one-hot `pm__2026_09`, `pm__2026_10`, `pm__2026_11` (từ 18/11 bước 01 đã bỏ tin trước 09/2026, C9) | PRE-37 việc 4: cột hiện tại lấy tháng từ `posted_date`, thiếu 36,2% (topcv 0%). Nếu chỉ lấy số tháng 1–12 thì mất thông tin năm. Người dùng: "tui thống nhất dùng cột bằng tháng đăng" |
| **F10.2** | **Mở rộng 10b thành bước chọn đặc trưng thật:** (a) loại cột hằng hoặc gần hằng (một giá trị chiếm > 99,5% tin); (b) loại cột trùng thông tin (ví dụ `log_salary_min`/`log_salary_max` với `salary_mid`); (c) ghi `selected: true/false` kèm lý do cho từng cột vào `encoding_dictionary.json`. Không xóa cột khỏi file, chỉ đánh dấu, để Mining tự chọn theo SD | Hiện 10b chỉ gom kỹ năng DF < 15. Spec 06 mục 3.4 ghi các tiêu chí chọn khác chưa chốt (PRE-34). Ngưỡng 99,5% là đề xuất |
| **F10.3** (**làm 19/11, thay bằng ba cột theo `skill_view`**) | Thêm cột `n_skills_technical` và `n_skills_soft` ở 10c, dùng cờ `soft` của bước 08 (K8.8). Thực hiện: `n_tools`, `n_concepts`, `n_soft` | `n_skills` hiện lẫn kỹ năng mềm (communication 677 tin) nên SD3 dễ phân cụm theo số kỹ năng (L-47) |
| **F10.4** (**làm 19/11**: `processing/encoding/constants.py`; `preprocessing/encoding/run.py` import lại) | Đặt hằng `SENIORITY_MAP`, `TOP_PROVINCES_K`, `to_col_slug` vào `processing/` | PRE-39: để dọn được `preprocessing/encoding/` |
| **F10.5** (**duyệt 18/11, làm 19/11**) | `emp__*` mã hóa one-hot từ cột `employment_type` của bảng 04 (luật N19: tiêu đề Intern → ô của sàn → JD), bỏ `employment_class` đoán lại bằng từ khóa trên `raw_employment_type`. Chưa rõ thì `emp__unknown` | Hiện loại hợp đồng được tính hai lần, bằng hai luật khác nhau: 180 tin tiêu đề thực tập mà ô của sàn ghi Full-time sẽ ra `internship` ở bảng 04/Silver nhưng `emp__full_time` ở bước 10 |
| **F10.6** (**người dùng chốt 18/11: phương án A**) | SD4 giữ nguyên `exp_min_years` (kể cả phần bước 04 điền từ cấp bậc, `exp_inferred`) cùng với cấp bậc. Không làm thí nghiệm B, C. Khi đọc SHAP ở SD4/SD5 phải ghi chú: điểm của cấp bậc và kinh nghiệm chia nhau một phần thông tin | Rừng ngẫu nhiên ít bị ảnh hưởng về độ chính xác bởi hai cột trùng thông tin, nhưng SHAP chia điểm quan trọng giữa cấp bậc và kinh nghiệm, nên SD4/SD5 có thể đọc sai "kinh nghiệm đáng tiền bao nhiêu". Làm sau khi chạy lại 04 và 10 |

### 2.3. Cột không được đưa vào model lương (SD4)

`salary_bin_range`, `salary_bin_eqfreq5`, `salary_mid`, `salary_range_ratio` được tính từ chính lương, nên **không được làm đầu vào** của model SD4 (spec 06 mục 2.2). `mining/salary_model.py` chặn bằng `assert_no_leakage`: mọi cột có tên chứa một trong `salary`, `luong`, `lương`, `negotiable`, `log_sal`, `suspect`, `outlier` (`LEAKAGE_TOKENS`) bị chặn, trừ cột bắt đầu bằng `skill__`. Nhờ vậy `log_salary_min`, `log_salary_max`, `salary_status__*`, `is_negotiable` và `is_outlier_salary` cũng bị chặn. Cột mới thêm vào bước 10 mà mang thông tin lương nhưng tên không chứa các từ này sẽ lọt qua, nên đặt tên cột theo quy ước đó.

### 2.4. Chọn đặc trưng và giảm chiều

- **Chọn đặc trưng:** hiện chỉ có 10b (gom kỹ năng hiếm). Mở rộng theo F10.2. Việc chọn tập cột cho từng SD (SD2 chỉ `skill__*`; SD3 `skill__*` + e5 + vài cột mô tả, không có `fam__*`; SD4 như mục 2.3) nằm ở `mining/`, không nằm ở đây.
- **Giảm chiều:** không nằm ở Processing. Thuộc M3 (`mining/clustering.py`, `reduce_svd`, SVD/PCA), chạy ngay trước K-Means và HDBSCAN.
- **Fit:** `min_df` (10b) và bin đều tần suất (10) được fit trên toàn bộ tin. Đúng cho phần không giám sát. Với SD4 thì M5 phải fit lại trong `sklearn.Pipeline` chỉ trên tập train (spec 06 mục 2.2). Cột `skill__*` chọn bằng `min_df` trên toàn bộ dữ liệu có rò rỉ nhẹ (chỉ là số tin có kỹ năng, không dính tới lương); M5 phải ghi rõ hoặc tính lại `min_df` trên tập train.

## 3. Quy trình xử lý

Thứ tự trong `build_features` (`processing/encoding/features.py`):

1. Đặt lại chỉ số; tính `ref = salary_ref_m(df)` (trung bình hai cận, triệu/tháng).
2. **10c:** `construct(df, skills)` → các cột mục 2.1 (10c). **10:** `discretize(df, ref)` → `salary_bin_range`, `salary_bin_eqfreq5`, `exp_bin`.
3. **10b:** với từng khối (`SKILL_BLOCKS`), `skill_block` lấy `skill_view`, `reduce_sparsity(rows, n, {}, min_df=15, mode="other")` gom kỹ năng hiếm vào `other_skill`; `crosstab` thành ma trận 0/1 và `reindex` theo thứ tự tin; đặt tên `<khối>__<slug>`.
4. **10d:** `seniority_ord`; one-hot `fam__`, `src__`, `wm__`; `emp__` từ `employment_type`; `pm__` từ `posted_month`; tỉnh multi-hot (tính top K theo mọi địa điểm), `loc_remote`, `loc_ngoai_vn`; số giữ nguyên kèm `__missing`; `days_to_deadline`; các cờ 0/1.
5. Nối mọi phần theo cột, ghi cách mã hóa từng cột vào `encoding_dictionary.json` (`method`, `source_column`).
6. `run` ghi `features.parquet` và `encoding_dictionary.json`; ghi report theo nguồn và `_all`; kiểm `rows_conserved`.

## 4. Input → Output

| | Chi tiết |
|---|---|
| Input | Bảng 04; `data/processing/08_skills/job_skills.parquet` (cần cột `type`, skills_v2 ≥ 2.1.0). Không đọc bước 09 |
| Output | `data/processing/10_features/features.parquet` (đúng số tin của bảng 04, khóa `job_id_global`); `encoding_dictionary.json` (mỗi cột: cách mã hóa, cột nguồn) |
| Report | `reports/processing/10_features/`; `extra`: `n_cols`, `min_df`, `n_skill_cols`, `n_cols_by_block`, `n_skills_folded` (theo khối) |

## 5. Dữ liệu mẫu

Điền khi chạy lại trên bảng 04 mới: một tin mẫu với giá trị từng nhóm cột; bảng 10 giá trị `salary_bin_*` đầu tiên; danh sách kỹ năng bị gom vào `other_skill`.

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách | Kết quả gần nhất |
|---|---|---|
| Số dòng bằng bảng 04 | `checks.rows_conserved` | Đạt (19/11, 3.916) |
| Mọi cột có trong `encoding_dictionary.json` | Test `test_build_features_numeric_conserved_and_decodable`; đo trên dữ liệu thật 19/11 | Đạt (994/994) |
| Không có NaN ngoài các cột số đã ghi | Đếm NaN theo cột (19/11) | Đạt: NaN chỉ ở `required_ratio` (1 tin không kỹ năng), cột lương, `exp_*`, `headcount`, `days_to_deadline`. Cột hằng: `required_ratio` (mọi kỹ năng đang `required`, PRE-40) và `pm__unknown` |
| Test | `tests/unit/test_processing_10_12.py` | Pass |

## 7. Trạng thái, chỗ thiếu, việc mở

| Trạng thái | Làm lại và chạy thật 19/11 (3.916 tin, 994 cột). Chưa có đánh giá cho 10–12 (PRE-34) |
|---|---|

| Chỗ thiếu | Ảnh hưởng | Mã |
|---|---|---|
| Chọn đặc trưng chỉ có 10b | Ma trận còn cột hằng, cột trùng; mỗi SD tự chọn trong `mining/` | PRE-34, F10.2 |
| `min_df` chưa chốt; mốc bin lương `SALARY_EDGES_M` là đề xuất | Số cột kỹ năng và bin đổi theo | PRE-33, PRE-34 |
| Report `rules` rỗng | Monitoring không thấy luật 10b | PRE-40 |
| Mining chưa đọc `concept__`, `soft__`, `n_tools`; `mining/config.py` còn trỏ bảng cũ | Ba khối chỉ dùng được khi làm Mining (kế hoạch sau P4) | PRE-39 |
