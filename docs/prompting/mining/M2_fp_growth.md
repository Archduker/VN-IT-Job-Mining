# Prompt M2: Gói kỹ năng cho SD2 (FP-Growth)

> Đặc tả: [`docs/spec/mining/M2_fp_growth.md`](../../spec/mining/M2_fp_growth.md) (M2.1, M2.2a–b, 2.1, 2.3, 2.4, M2.5, M2.6; đã duyệt 20/11). Câu hỏi: `docs/target/02_sd2_goi_ky_nang.md`.
> **Trạng thái:** viết 20/11, chờ duyệt prompt. Cần M0 xong.

## 1. Ngữ cảnh

**Đọc trước:** đặc tả M2; `mining/association.py`; `tests/unit/test_mining_association.py`.

**Vì sao làm** (dry-run 20/11):

- 15.565 luật, nhưng nhóm nhỏ nổ luật: Security 188 giỏ → 5.846 luật, support 2% = 4 tin.
- Chưa có top 15 ba bảng, chưa có nghề × cấp, kỹ năng hiếm, kiểm ổn định, mẫu kiểm tay.
- 672 tin giỏ rỗng.

## 2. Việc cần sửa

**Input:**

- `MiningData.skills` (K-tool), `meta.job_family`, `meta.seniority`;
- `job_skills.parquet` + `skill_view`.

**Output:**

- `skill_association_rules.parquet` (thêm cột `n_support`, `scope` dạng `ALL` / `<nghề>` / `<nghề>|newcomer` / `<nghề>|middle_plus`);
- `sd2_top_skills.json`, `sd2_rare_skills.json`, `sd2_hand_check.csv`;
- khối `association` trong metrics.

**File:**

- `mining/association.py`: `min_support_for`, `top_skills_by_family`, `rare_skills`, `support_stability`, `hand_check_rules`;
- `mining/config.py` (`AssociationParams.min_support_count` 10, `rare_max_df` 0,02, `rare_min_lift` 2, `rare_senior_share` 0,6, `stability_factors` (0,5, 2), `stability_top` 20, `hand_check_n` 20);
- `run_mining_pipeline.py`.

## 3. Pseudo code

```
baskets = skills; empty = rows sum 0 → bỏ, ghi n_jobs_without_tool tổng và theo nghề
min_support_for(n, base) = max(base, min_support_count / n)
rules_all = mine_rules(baskets, macro_min_support)
for scope in nghề, rồi nghề × {newcomer, middle_plus}:
    nếu n_giỏ < min_group_size → skipped
    rules += mine_rules(baskets[scope], min_support_for(n, micro_min_support))
rules.n_support = round(support × n_giỏ của scope)
top_skills_by_family: với mỗi view ∈ (tool, concept, soft) và scope ∈ ALL + nghề:
    tỷ lệ tin có k trong scope, top 15; nghề < 30 tin → "ít dữ liệu"
rare_skills: k với df(k) < 2% số giỏ ALL và (max lift của luật chứa k ≥ 2 hoặc share Senior/Lead của k ≥ 0,6)
    ghi n, luật mạnh nhất (lift cao nhất), senior_share
support_stability: với f ∈ (0,5, 2): chạy lại ALL và từng nghề với support × f;
    overlap = |top20_gốc ∩ top20_mới| / 20 (xếp lift, conf, rồi chuỗi luật)
hand_check_rules: top 20 luật (lift giảm dần, n_support ≥ 10, mỗi scope ≤ 5 luật) → csv có cột dung, ghi_chu;
    file đã có cột dung được điền → không ghi đè
```

## 4. Ràng buộc

- Giỏ chỉ là K-tool. Bảng 2.1 lấy ba view từ `job_skills`; không đưa `concept`/`soft` vào luật.
- So sánh newcomer / middle_plus chỉ trên nghề mà cả hai nhóm đủ `min_group_size`. Không đủ thì ghi `skipped` với số giỏ.
- Không tăng `max_len`, không đổi `min_confidence`/`min_lift`.
- Thời gian: giữ dưới khoảng 2 phút cho cả bước (dry-run cũ 15 giây). Nếu ổn định ×0,5 nổ số luật thì báo, không tự đổi ngưỡng.

## 5. Ví dụ (thành test)

| Đầu vào (dựng tay) | Kết quả mong đợi |
|---|---|
| Scope 150 giỏ, `micro_min_support` 0,02 | support dùng = max(0,02; 10/150) = 0,0667 |
| Luật có support × n = 4 tin | không có trong kết quả |
| Web 200 giỏ newcomer, 50 giỏ middle_plus | scope `Web|newcomer` có luật; `Web|middle_plus` `skipped` |
| Kỹ năng x ở 1% giỏ, 8/10 lần ở Senior/Lead | trong `rare_skills`, `senior_share` 0,8 |
| Kỹ năng y 1%, không luật lift ≥ 2, senior 20% | không hiếm |
| `english` là soft | không có trong bảng `tool` |
| Hai lần chạy cùng dữ liệu | top 20 trùng 100% |
| `sd2_hand_check.csv` đã có `dung` điền | không bị ghi đè |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_mining_association.py -q` | Xanh |
| Dry-run | `python -m mining.run_mining_pipeline --only fp --dry-run` | Gửi: số luật theo scope, `n_jobs_without_tool`, top 15 tool của 6 nghề lớn, số kỹ năng hiếm, overlap ổn định |
| Sanity | S-01 pass, S-03 ≥ 0,60, S-02 info | Đạt |
| Ổn định | overlap ×0,5 và ×2 | ≥ 70% |
| Kiểm tay | người dùng điền `sd2_hand_check.csv` | ≥ 16/20 |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 20/11 | "approved" | 1036a11 |
| 2 | Duyệt prompt | 20/11 | "continue" sau khi nhận bộ prompt | e230f28 |
| 3 | Test rồi code | 20/11 | 7 test mới trong `test_mining_association.py` (sàn 10 tin, luật 4 tin bị bỏ, nghề × nhóm cấp và `skipped`, kỹ năng hiếm, ba bảng top, ổn định tất định, file kiểm tay không ghi đè). Code: `min_support_for`, `mine_stratified_rules(level_group=, support_factor=)`, `compare_levels`, `top_skills_by_family`, `rare_skills`, `support_stability`, `hand_check_rules`, `write_hand_check`, `run_association`; cột luật mới `level_group`, `n_support`. 89 test mining xanh. **Đi khác prompt:** scope ghi hai cột (`job_family_scope` + `level_group`) thay `Web|newcomer`, để `scripts/load_mart_from_parquet.py` vẫn lọc theo nghề | (commit này) |
| 4 | Dry-run | 20/11 | Trước khi sửa: 15.565 luật, 672 giỏ rỗng. Sau: 8.650 luật; chỉ Web và Other đủ 100 giỏ người mới; 87 kỹ năng hiếm; ổn định × 0,5 = 0,75, × 2 = 0,31 (không đạt 0,70); S-01 0,961, S-02 0,394 info, S-03 0,671 | |
| 5 | Review, chạy thật | chưa | | |
