# Prompt M1: BI cho SD1

> Đặc tả: [`docs/spec/mining/M1_bi.md`](../../spec/mining/M1_bi.md) (M1.0a–M1.0e, câu 1.1–1.7, M1.B, M1.D; đã duyệt 20/11). Câu hỏi: `docs/target/01_sd1_buc_tranh_thi_truong.md`.
> **Trạng thái:** viết 20/11, chờ duyệt prompt. Cần M0 xong.

## 1. Ngữ cảnh

**Đọc trước:** đặc tả M1; target SD1 mục 4, 6; `processing/extraction/skills.skill_view`; `scripts/eval_skill_views.py` (`NEWCOMER`, `BIG_FAMILIES`).

**Vì sao làm:** SD1 chưa có code. Trang Insights đọc Postgres nạp từ bảng legacy. M1 còn cấp **baseline lương cấp × nghề** cho M5 và **`demand`** cho M6.

**Số đã đo** (20/11): thỏa thuận 2.192/3.916; lương dùng được 1.644 tin; trung vị theo cấp 10,0 / 15,5 / 22,5 / 37,5 / Lead 30,0; T11 chỉ 20 tin.

## 2. Việc cần sửa

**Input:**

- `MiningData` (M0);
- `data/processing/08_skills/job_skills.parquet`.

**Output** trong `mining/artifacts/`:

- `sd1_1_1.json` … `sd1_1_7.json`;
- `sd1_baseline_salary.json`, `sd1_demand.json`;
- khối `bi` trong metrics.

**File:**

- **mới** `mining/bi.py`;
- `mining/config.py` (`BIParams`: `min_cell` 30, `mnar_share` 0,55, `top_provinces` 10, `top_benefits` 15, `month_compare_sources` 6 nguồn, `NEWCOMER`, `MIDDLE_PLUS`);
- `run_mining_pipeline.py` (bước `bi`, ghi artifact);
- chuyển `NEWCOMER`, `BIG_FAMILIES` từ `scripts/eval_skill_views.py` vào `mining/config.py`; script import lại.

## 3. Pseudo code

```
table(df, by, value=None, stat="count"):
    nhóm theo by (null → "Không rõ"); mỗi ô: n, value (tỷ lệ / median, p25, p75)
    n < min_cell → value = None, note = "ít dữ liệu"
    trả {"by", "rows", "n_total", "coverage"}

salary_ok = meta[salary_target_m notna & !salary_outlier]
q1_1: count(job_family); crosstab(source × job_family) tỷ lệ theo hàng
q1_2: count(seniority); crosstab(seniority × job_family); count(seniority × seniority_inferred)
q1_3: top 10 province + "Khác" + "Không rõ"; crosstab(work_mode × job_family)
q1_4: has_salary = salary_target_m notna; tỷ lệ theo source, job_family, seniority;
      ghi riêng số tin negotiable & có số; median/IQR trên salary_ok theo family × seniority, theo province top 10;
      seniority có negotiable share ≥ mnar_share → note MNAR
q1_5: nhóm = newcomer / middle_plus; exp median (exp_inferred = false); n_tools median;
      top 15 tool, top 10 soft (job_skills + skill_view, tỷ lệ tin); % language == "en"; median lương
q1_6: benefits explode; top 15 (tỷ lệ trên tin có ≥ 1 phúc lợi); crosstab top 5 × seniority, × family
q1_7: tỷ lệ family, seniority theo posted_month; bảng so T9 vs T10–T11 chỉ trên 6 nguồn
baseline: median salary_ok theo family × seniority; ô n < 30 → median theo seniority → median toàn bộ, ghi "fallback"
demand: với family có ≥ 30 tin newcomer: tỷ lệ tin newcomer có k, theo view tool / concept / soft
kiểm: tổng count mỗi bảng toàn bộ = n_jobs; tỷ lệ cộng 100 ± 0,1
```

## 4. Ràng buộc

- Không bù lương thiếu; không dùng lương ước tính của M5 ở M1.
- Không viết "tăng/giảm/xu hướng" trong JSON.
- `demand` tính trên `job_skills` + `skill_view`, không đọc lại ma trận kỹ năng theo cách khác.
- JSON có thứ tự ổn định (sắp theo n giảm dần, hòa thì theo nhãn) để chạy lại ra cùng file.

## 5. Ví dụ (thành test `tests/unit/test_mining_bi.py`)

| Đầu vào (dựng tay) | Kết quả mong đợi |
|---|---|
| 40 tin Web, 10 tin Game, 2 tin family null | `q1_1` tổng 52, có dòng "Không rõ" = 2 |
| Ô Game × Senior có 3 tin | `value` None, `note` "ít dữ liệu", `n` = 3 |
| Lương 35 tin Web Junior gồm 1 tin `salary_outlier` | median tính trên 34 tin |
| Senior 10 có lương / 30 thỏa thuận | note MNAR ở Senior |
| Tin `exp_inferred = true` | không vào trung vị kinh nghiệm 1.5 |
| 1.5 top tool không có `english`; top soft không có `python` | đúng view |
| topcv 50 tin T10, itviec 40 T9 + 40 T10 | bảng so tháng chỉ dùng itviec |
| Ô baseline Data/AI × Senior 5 tin | lùi về median Senior, `fallback` = "seniority" |
| Nghề 20 tin người mới | không có trong `demand` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_mining_bi.py -q` | Xanh |
| Dry-run | `python -m mining.run_mining_pipeline --only bi --dry-run` | `totals_ok` true; gửi bảng 1.1, 1.2, 1.4b, 1.5 |
| Đối chiếu tay | 20 tin (seed 42) so trang gốc | ≥ 18/20 |
| Chạy lại | hai lần chạy thật, so JSON bỏ `generated_at` | Trùng |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 20/11 | "approved" | 1036a11 |
| 2 | Duyệt prompt | chưa | | |
| 3 | Test rồi code | chưa | | |
| 4 | Dry-run | chưa | | |
| 5 | Review, chạy thật | chưa | | |
