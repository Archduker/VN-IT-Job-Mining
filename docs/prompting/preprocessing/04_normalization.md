# Prompt 04: Normalization + bảng Silver + Profiling cuối chuỗi

> Đặc tả: [`04_normalization.md`](../../spec/preprocessing/04_normalization.md) (mục 2.2 là luật mới), [`silver.md`](../../spec/preprocessing/silver.md), [`00_profiling.md`](../../spec/preprocessing/00_profiling.md). Bảng Silver: spec 05 mục 4.4.
> **Trạng thái:** viết ngày 18/11/2026, **chờ duyệt**. Chỉ làm sau khi bước 03 mới đã chạy thật.

## 1. Ngữ cảnh

**Đọc trước:**

- Đặc tả 04 (mục 2.1 luật đang chạy, mục 2.2 luật mới).
- `silver.md`; spec 05 mục 4.2 (`posted_month`), 4.3 (thiếu dữ liệu), 4.4 (bảng Silver).
- `jd_extraction.json` → `decisions`.
- `preprocessing/CLAUDE.md`: cấp bậc ↔ kinh nghiệm (L-39); chỉ sửa `FAMILY_MAP` khi đổi nhóm nghề (L-47).
- Code: `preprocessing/normalization/run.py` (`work_mode`, `process_source`), `preprocessing/missing_outlier/missing_rules.py` (`infer_experience_from_level`), test `tests/unit/test_normalization_step.py`, `tests/unit/test_ph6_ph7_normalization.py`.

**Vì sao làm:**

- Bảng 04 hiện là lần chạy 10–11/11, chưa có cột của 02 và 03 mới.
- `work_mode` đang mặc định onsite khi có tỉnh.
- Chưa có `silver.parquet`.
- Mục tiêu của đợt là "ra được dữ liệu silver như trong đặc tả" và chỉ ra bước nào còn thiếu.

## 2. Việc cần sửa

**Input:** `data/preprocessing/03_transformation/all.parquet` (bản mới, có T3b, T9).

**Output:**

- `data/preprocessing/04_normalization/all.parquet`;
- `anomalies.json`;
- `silver.parquet`;
- `reports/preprocessing/04_normalization/`;
- trang `04_normalization.html`, `silver_gap.html`;
- `samples/04_normalization.json`.

**Các việc:**

1. **N14 (sửa)** trong `normalization/run.py`. `work_mode` mới đi qua các bước theo thứ tự, dừng ở bước đầu tiên ra giá trị:

   | Thứ tự | Điều kiện | `work_mode` | `work_mode_source` |
   |---|---|---|---|
   | 1 | `work_mode_conflict` và `work_mode_jd_strong` | `work_mode_jd` | `jd_over_raw` |
   | 2 | Có `work_mode_raw` | `work_mode_raw` | `raw` |
   | 3 | Có `work_mode_jd` | `work_mode_jd` | `jd` |
   | 4 | Luật N14 cũ (địa điểm, tiêu đề) ra giá trị | giá trị đó | `location` |
   | 5 | Không bước nào ra | `unknown` | `unknown` |

   `tinh_status` (M7) đọc `work_mode` mới.
2. **N19**: `employment_type` = internship nếu tiêu đề có Intern (EI1, `employment_type_jd` = internship và nằm ở tiêu đề); nếu không thì `employment_type_raw`; nếu không thì `employment_type_jd`. Ghi `employment_type_source`.
3. **N2 (bổ sung)**: N2 chưa ra cấp mà `employment_type` = internship → Intern/Fresher, `seniority_source` = `employment_type`.
4. **M4 (sửa)**: chép `exp_min_years` của 03 sang `exp_min_years_parsed`. Chọn giá trị cuối:

   | Nguồn | Thứ tự lấy | `exp_source` |
   |---|---|---|
   | itviec | JD trước, rồi ô JSON-LD | `jd` / `jd_zero` / `itviec_jsonld` |
   | 7 nguồn còn lại | Ô của sàn trước, rồi JD | `raw` / `jd` / `jd_zero` |

   - Còn trống thì điền cận dưới theo cấp bậc như M4 cũ (`infer_experience_from_level`: chỉ khi cấp lấy từ ô của sàn hoặc tiêu đề), `exp_source` = `level_<cấp>`, `exp_inferred` = true.
   - Sửa tên luật M4 trong report cho đúng code: "Thiếu kinh nghiệm điền cận dưới theo cấp bậc".
   - `exp_conflict` khi ô và JD lệch ≥ 1 năm.
   - Đổi nhãn `given` thành `raw` và tìm mọi nơi đọc `exp_source` (Processing 10, Mining, Monitoring) để sửa theo.
5. **S1**: ghi `silver.parquet` theo spec 05 mục 4.4. Thiếu cột nguồn thì dừng và báo, không tạo cột rỗng. Sinh `silver_gap.html` (mỗi trường: có / thiếu cột / phủ thấp / lệch kiểu, bước gây ra, mã PRE).
6. **00 Profiling**: `python scripts/profile_sources.py --when both`, điền mục 5 của `00_profiling.md`.
7. Sinh trang 04, `samples/04_normalization.json`; điền mục 5 của `04_normalization.md`, `silver.md`, README tin mẫu.

## 3. Pseudo code

```text
for rec in 03:
    N1/N13 tỉnh
    wm = (rec.work_mode_jd if rec.work_mode_conflict and rec.work_mode_jd_strong else None) \
         or rec.work_mode_raw or rec.work_mode_jd or n14_old(locs, title, raw_location, tinh) or "unknown"
    M7 tinh_status(tinh, wm, ngoai_vn)
    et = "internship" if title_intern(rec) else rec.employment_type_raw or rec.employment_type_jd
    N2 cấp bậc (+ internship → Intern/Fresher) ; M3c ; 
    rec.exp_min_years_parsed = rec.exp_min_years
    exp, src = pick_exp(nguồn, parsed, rec.exp_min_years_jd, rec.exp_jd_kind)   # itviec: JD trước
    nếu exp None: exp, src = infer_experience_from_level(...)    # cận dưới theo cấp, src = level_<cấp>
    N2b ; N16 ; N3 ; N4 ; N5 ; N18 ; N6a → N6 → M5 → M6 → M8 → N7
ghi all.parquet, anomalies.json
silver = select_rename(all, SPEC05_4_4)   # thiếu cột → raise
assert len(silver) == len(all) and silver.job_id.is_unique
ghi silver.parquet ; silver_gap.html
```

## 4. Ràng buộc

- Không bỏ dòng. Không ghi đè cột `raw_*` hay cột parse của 03 (chép sang `*_parsed` trước khi chọn). N6 trước N7.
- Không bù lương bằng trung bình hay trung vị. Lương thỏa thuận giữ NaN.
- Không đổi nhóm nghề ngoài `FAMILY_MAP`.
- `employment_type` **không vào** Silver cho tới khi trích được 100% tin (người dùng chốt 18/11). Chỉ báo độ phủ.
- Silver chỉ chọn cột và đổi tên, không tính lại.
- Không đẩy R2 (`push_preprocessing_to_r2.py` chỉ chạy thử, khi người dùng yêu cầu). Không push git.

## 5. Ví dụ (thành test)

| Đầu vào | Kết quả mong đợi |
|---|---|
| `work_mode_raw` onsite, `work_mode_jd` remote, `strong` true (itviec "Remote - QA Engineer (Games)") | `work_mode` remote, `source` jd_over_raw |
| `work_mode_raw` onsite, `work_mode_jd` hybrid, `strong` false | onsite, raw |
| raw null, jd null, có tỉnh TP. Hà Nội, tiêu đề không có remote/hybrid | onsite, location |
| raw null, jd null, không tỉnh | unknown |
| itviec, `exp_min_years` (ô JSON-LD) 3,0, `exp_min_years_jd` 5,0 | `exp_min_years` 5,0, `exp_source` jd, `exp_conflict` true, `exp_min_years_parsed` 3,0 |
| topcv, ô 1,0, JD null (`topcv_2325743`) | 1,0, raw |
| topdev, ô null, JD 5,0 | 5,0, jd |
| ô null, JD null, `seniority` Intern/Fresher lấy từ tiêu đề | 0, `level_intern`, `exp_inferred` true |
| Tiêu đề "Oracle Consultant Intern", raw FULL_TIME | `employment_type` internship; `seniority` Intern/Fresher nếu N2 chưa ra cấp |
| Bảng 04 thiếu cột `posted_month` | S1 dừng, báo "thiếu cột posted_month (03 T3b)" |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_normalization_step.py tests/unit/test_ph6_ph7_normalization.py -q`; `make test-fast` | Xanh |
| Dry-run | `python scripts/run_preprocessing.py --step normalization --source all --dry-run` | Bảo toàn |
| `work_mode` | Phân bố `work_mode` × `work_mode_source` × nguồn | Số `jd_over_raw` khớp số ca lệch strong ở 03; `unknown` được giải thích |
| Kinh nghiệm | Phân bố `exp_source` × nguồn; topdev, itviec trước → sau | topdev tăng từ 28,2%; itviec phần lớn `jd` |
| Silver | `silver.parquet`: 22 cột, số dòng = bảng 04, `job_id` duy nhất; `silver_gap.html` | Không còn "thiếu cột"; "phủ thấp" có giải thích |
| Profiling | `reports/preprocessing/00_profiling/{before,after}_clean/` | 8/8 nguồn |
| Trang | 04, `silver_gap` ở 1100px và 390px | Không tràn ngang |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| — | Quyết định đầu vào | 17–18/11 | Bảng Silver 22 trường, bỏ `posted_month_source` (17/11). Quyết định chọn giá trị (18/11): itviec "Linh hoạt" → hybrid; tiêu đề và mẫu có số ngày thắng ô của sàn; itviec lấy kinh nghiệm từ JD trước; 7 nguồn còn lại giữ ô của sàn; `employment_type` chỉ vào Silver khi đủ 100% | `7aa63a2`, `adaa693` |
| 1 | Duyệt đặc tả | chưa | Đặc tả 04 mục 2.2, `silver.md` | — |
| 2 | Duyệt prompt | chưa | Prompt này | — |
| 3 | Test rồi code | chưa | | |
| 4 | Dry-run | chưa | | |
| 5 | Review, chạy thật | chưa | | |
