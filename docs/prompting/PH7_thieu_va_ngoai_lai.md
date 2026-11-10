# Prompt PH7: dữ liệu thiếu và ngoại lai (bước 04, luật M1-M9)

> **Nháp, chờ bạn duyệt.** Làm sau khi PH6 được duyệt và code xong (cần 5 cấp bậc, `job_family`, `work_mode`, `tinh_chinh` đã sửa). Các điểm **[CẦN CHỐT]** `X1`-`X12` trong spec phải chốt trước, nhất là X3 (khoảng lương), X4 (winsorize), X6 (ngưỡng số năm sang cấp bậc). Chỗ nào ghi "[ĐỀ XUẤT]" là mặc định nếu bạn không đổi.

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/PH7_thieu_va_ngoai_lai.md` (mục 2 hiện trạng đo; 3 luật; 6 điểm chờ chốt) và `PH6_chuan_hoa_truong.md` (nhất là 3.3).
- `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` bước 6 và mục 3.4 (bảng chiến lược thiếu).
- `docs/spec/preprocessing/spec/P3_transformation.md` (T2e, T2f), `P4_normalization.md` (N2, N6, N7, mục 8).
- Code: `preprocessing/normalization/run.py` (`apply_global_salary_normalizations`), `missing_outlier/outlier_handler.py` (`detect_iqr_outliers`, `winsorize_series`, `fix_common_salary_input_errors`), `missing_outlier/sneaky_null_detector.py`, `transformation/salary_parser.py` (`MONTHLY_MIN_VND`, `MONTHLY_MAX_VND`), `common/step_report.py`.

Hiện tại (đo 10/11/2026 cùng cách với PH6, 5.076 tin):
- Cột `is_negotiable` có; 29 tin vừa `is_negotiable` vừa có số; 23 tin không số và không negotiable.
- Cấp bậc: 44,4% nhãn (2.256) do luật số năm tạo ra mà không có cờ `level_inferred`; sau PH6 chỉ còn raw+title.
- Kinh nghiệm: không có luật suy; itviec 100% thiếu, topdev 74,4%. Phân phối theo cấp: chỉ Intern/Fresher chặt (trung vị 0); Senior 3-5 (tối đa 7), Lead/Manager 3-5 (tối đa 20).
- Lương: khoảng đang chạy 1-500 triệu (N6a, 22 `salary_suspect`); IQR gộp chung (73 tin); winsorize 1-99% ra cột `*_capped`; 1 tin `min > max`; 4 tin `exp_min >= 15`.
- Tỉnh thiếu không ngẫu nhiên: itviec chiếm 719/843.

## 2. Việc cần sửa

Input: bảng sau luật PH6 trong bước 04. Output: `data/preprocessing/04_normalization/all.parquet` (thêm cột, giữ cột cũ).

1. `preprocessing/missing_outlier/missing_rules.py` (mới), hàm thuần (không đọc/ghi file): `salary_status`, `infer_level_from_experience`, `infer_experience_from_level`, `tinh_status`, `range_flags`.
2. `preprocessing/missing_outlier/outlier_handler.py`: thêm `iqr_flags_by_group(values, groups, min_n=30) -> DataFrame` dùng `detect_iqr_outliers` đã có (không viết IQR thứ hai). Bỏ lời gọi/nhánh sai của `fix_common_salary_input_errors` nếu PH6 chưa bỏ (kiểm trước).
3. `normalization/run.py`: sau vòng luật PH6 và **trước** N7 (log), gọi các hàm trên:
   - M1, M2: `salary_negotiable` (bản sao của `is_negotiable`, X2), `salary_status`, cờ `salary_negotiable_with_value`.
   - M3c: cấp bậc trống + `exp_min_years` có -> `seniority` theo ngưỡng X6, `level_inferred=True`, `seniority_source="kinh_nghiem"`. **Chỉ chạy khi `seniority` null.** Cấp từ raw/title: `level_inferred=False`.
   - M4: `exp_min_years` null và `seniority == "Intern/Fresher"` với `seniority_source in {"raw","title"}` -> `exp_min_years=0`, `exp_inferred=True`, `exp_source="level_intern_fresher"`; cấp khác: `exp_source="unknown"`, không điền. **Không** dùng cấp có `seniority_source="kinh_nghiem"`.
   - M5: `salary_out_of_range` (ngoài 2-200 triệu, X3), giữ N6a (NaN hóa ngoài 1-500, `salary_suspect`). Không sửa số.
   - M6: `salary_iqr_outlier_by_level`, `salary_iqr_scope` in {`level`, `pooled`, `not_enough_data`}. Giữ `is_outlier_salary` và `*_capped` (X4).
   - M7: `tinh_status` in {`ok`, `remote`, `foreign`, `unknown`}.
   - M8: `salary_min_gt_max`, `exp_out_of_range`; không hoán đổi, không sửa.
4. M9: `extra.missing_strategy` (bảng mục 3.6 của spec, số lấy từ dữ liệu), `extra.missing_matrix` (trường x nguồn, trước và sau), `extra.outliers`, `extra.inference`.
5. Cập nhật `KEY_FIELDS` để báo cáo độ phủ thấy các cột mới.

## 3. Pseudo code

```text
# trước khi chạy PH7: snapshot
before = fill_matrix(rows)          # % có giá trị theo trường x nguồn

for rec in rows:                                     # M1, M2
    rec.salary_negotiable = bool(rec.is_negotiable)
    has_num = notna(rec.salary_min_vnd) or notna(rec.salary_max_vnd)
    rec.salary_status = "value" if has_num else ("negotiable" if rec.salary_negotiable else "not_stated")
    rec.salary_negotiable_with_value = has_num and rec.salary_negotiable

    # M3c  cấp bậc trống -> số năm (ngưỡng X6)
    rec.level_inferred = False
    if rec.seniority is None and notna(rec.exp_min_years):
        rec.seniority = level_by_years(rec.exp_min_years)   # 0 Intern/Fresher; 1 Junior; 2-4 Middle; >=5 Senior  (X6)
        rec.seniority_source, rec.level_inferred = "kinh_nghiem", True

    # M4  kinh nghiệm trống
    rec.exp_inferred, rec.exp_source = False, ("given" if notna(rec.exp_min_years) else "unknown")
    if isnull(rec.exp_min_years) and rec.seniority == "Intern/Fresher" and rec.seniority_source in ("raw","title"):
        rec.exp_min_years, rec.exp_inferred, rec.exp_source = 0.0, True, "level_intern_fresher"

    rec.tinh_status = "remote" if rec.work_mode=="remote" else ("foreign" if any ngoai_vn else ("ok" if rec.tinh_chinh else "unknown"))

# M5-M6 trên cả bảng gộp (sau khi cấp bậc đã có)
sal = salary_max.combine_first(salary_min)
df.salary_out_of_range = (sal < 2e6) | (sal > 200e6)
flags = iqr_flags_by_group(sal, df.seniority, min_n=30)    # tin cấp null -> pooled
df.salary_iqr_outlier_by_level, df.salary_iqr_scope = flags
df.salary_min_gt_max = salary_min > salary_max
df.exp_out_of_range = (exp_min >= 15) | (exp_max > 20)

report.extra.missing_matrix = {"before": before, "after": fill_matrix(rows)}
```

## 4. Ràng buộc

- Không xóa dòng (`rows_out = rows_in`), không xóa ngoại lai, không sửa `raw_*`, không sửa giá trị gốc `salary_min/max_vnd` và `exp_min_years` đã có (chỉ điền ô null, có cờ).
- **Không điền lương**, không dùng mean/median/mode, không model (không KNN, MICE, Gemini). Không điền kinh nghiệm cho Junior/Middle/Senior/Lead.
- Không suy kinh nghiệm từ cấp bậc có `seniority_source="kinh_nghiem"` (tránh vòng).
- Log (N7) và mọi biến đổi phải chạy sau M5-M6.
- Giữ `is_outlier_salary`, `salary_min_vnd_capped`, `salary_max_vnd_capped`, `log_salary_*`, `is_negotiable` (Monitoring và test cũ). Không đổi tên cột đã có.
- Không R2, không cài gói, không commit. Báo cáo không chứa nội dung JD.
- Test dùng chuỗi/dòng thật (từ `data/preprocessing/01_clean/*.jsonl` hoặc fixtures), ghi `job_id` nguồn; các giá trị ngoại lai tự dựng chỉ được lấy bằng biến đổi của giá trị thật (ví dụ nhân 10 một lương thật), có ghi chú.
- Sửa test cũ nào khẳng định hành vi sai (nhãn từ số năm không cờ; winsorize bị coi là "xử lý outlier") và ghi lý do.
- Sau khi xong ghi `docs/issue_log.md`: nhãn cấp bậc từ số năm không cờ (44,4%), chia 12 theo chữ "năm".

## 5. Ví dụ (thành test)

| Đầu vào (thật) | Kết quả mong đợi |
|---|---|
| tin `is_negotiable=True`, không số (itviec, vietnamworks) | `salary_status="negotiable"`, `salary_min/max` vẫn null |
| tin không số, `is_negotiable=False` | `salary_status="not_stated"` |
| tin vừa `is_negotiable` vừa có số (29 tin) | `salary_status="value"`, `salary_negotiable_with_value=True` |
| `seniority=None`, `exp_min=1` | `Junior`, `level_inferred=True`, `source="kinh_nghiem"` |
| `seniority="Senior"` (title), `exp_min=1` | giữ `Senior`, `level_inferred=False` |
| `seniority=None`, `exp_min=None` | `seniority=None`, `source="none"`, `level_inferred=False` |
| `seniority="Intern/Fresher"` (raw), `exp_min=None` | `exp_min=0`, `exp_inferred=True` |
| `seniority="Senior"` (title), `exp_min=None` | `exp_min=None`, `exp_source="unknown"` |
| `seniority="Junior"`, `source="kinh_nghiem"`, `exp_min=None` | không xảy ra (vì `kinh_nghiem` chỉ gán khi có `exp_min`); test chặn vòng: hàm M4 từ chối `source="kinh_nghiem"` |
| vietnamworks `8000 - 9000 USD` (203,2-228,6 triệu) | giữ số; `salary_out_of_range=True`; không bị chia 12 |
| thực tập `raw_salary_text` ~ `0.5 - 1 triệu` (thật, 15 tin `salary_under_1m`) | giữ số; `salary_out_of_range=True` (< 2 triệu); không NaN (>= 1 triệu hoặc theo N6a hiện có) |
| lương 450.000.000 (vietnamworks `0 - 450000000 VND`) | trong 1-500: giữ; `salary_out_of_range=True`; cờ IQR theo cấp |
| lương 600.000.000 | N6a NaN + `salary_suspect` (như hiện tại) |
| cấp có 12 tin có lương | `salary_iqr_scope="not_enough_data"`, không cờ riêng |
| 1 tin `salary_min > salary_max` | `salary_min_gt_max=True`, giá trị không đổi |
| `exp_min=20` (thật) | `exp_out_of_range=True` |
| `raw_location_text` itviec không ra tỉnh | `tinh_status="unknown"`, `tinh_chinh=None` (không điền "Hà Nội") |
| chạy 2 lần | cùng kết quả; `rows_out = rows_in`, `dropped = 0` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit -q`, `tests/integration/test_preprocessing_steps_api.py` | xanh |
| Bảo toàn | `python scripts/run_preprocessing.py --step normalization --source all --dry-run` | `rows_in = rows_out`, `dropped = 0` |
| Ma trận thiếu | `extra.missing_matrix` trước/sau | khớp bảng 2.2 của spec (trước); sau chỉ đổi ở trường được điền (cấp bậc, kinh nghiệm Intern/Fresher) |
| Suy luận | `extra.inference` | `level_inferred` theo nguồn; cảnh báo nếu suy > thật |
| Chống vòng | truy vấn: có tin `exp_source="level_intern_fresher"` mà `seniority_source="kinh_nghiem"` | 0 |
| Đọc tay | bạn xem 20 tin `level_inferred=True` từ số năm, 20 tin cờ IQR theo cấp, 29 tin negotiable+số (seed 42) | tin suy cấp từ tiêu đề đúng >= 90% (nếu có luật M3b); các nhóm còn lại báo cáo, không ép |
| Lương | so `salary_min/max_vnd` trước/sau PH7 trên 5.076 tin | khác nhau chỉ ở tin N6a NaN hóa (giữ như cũ); 6 tin vietnamworks không còn chia 12 |
| Bảng chiến lược | `extra.missing_strategy` | đủ 7 dòng, số khớp ma trận |
| Git | `git status`, `git diff --stat` | không đụng `collection/`, R2, raw, `monitoring/` (trừ khi bạn yêu cầu X12); không file dữ liệu trong git |
