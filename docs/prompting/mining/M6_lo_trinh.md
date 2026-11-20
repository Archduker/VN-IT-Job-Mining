# Prompt M6: Lộ trình học cho người mới (SD5)

> Đặc tả: [`docs/spec/mining/M6_lo_trinh.md`](../../spec/mining/M6_lo_trinh.md) (M6.0–M6.6; đã duyệt 20/11). Câu hỏi: `docs/target/05_sd5_lo_trinh_hoc.md`.
> **Trạng thái:** viết 20/11, chờ duyệt prompt. Cần M1, M2, M5 xong.

## 1. Ngữ cảnh

**Đọc trước:** đặc tả M6; target SD5 mục 4–6; `scripts/eval_skill_views.py` (`coverage_at`); `mining/association.py` (scope `<nghề>|newcomer` từ M2).

**Vì sao làm:** SD5 chưa có code. coverage@10 của một danh sách top 10 chung theo nghề rất thấp (Web 0,127; DevOps/Cloud 0,089), nên lộ trình trình bày **theo gói** dựng từ luật M2.

## 2. Việc cần sửa

**Input:**

- `demand` (M1.D);
- luật M2 (scope nghề × newcomer, fallback nghề);
- `delta_m` (M5);
- `meta.seniority`, `meta.job_family`, `MiningData.skills`.

**Output:**

- `sd5_<nghề_slug>.json`, `sd5_index.json`;
- khối `recommend` trong metrics.

**File:**

- **mới** `mining/recommend.py`;
- `mining/config.py` (`RecommendParams`: `min_newcomer_jobs` 30, `min_demand` 0,05, `strong_conf` 0,6, `strong_lift` 1,2, `defer_ratio` 3, `coverage_need` 0,7, `coverage_ns` (5, 10, 15), `split` 0,2);
- chuyển `coverage_at` vào `mining/recommend.py`, `scripts/eval_skill_views.py` import lại;
- `run_mining_pipeline.py` (bước `recommend` tự gọi M1, M2, M5 trong bộ nhớ nếu chưa có trong lần chạy).

## 3. Pseudo code

```
for fam in nghề có ≥ 30 tin newcomer, fam ≠ Other:            # M6.0; còn lại → index "ít dữ liệu"
    d = demand[fam]                                             # tool, soft
    prem = delta_m (ALL) / max |delta_m| trên kỹ năng của fam; không định giá → 0
    priority_tool = [k: d.tool[k] ≥ 0.05], score = d × (1 + prem), sort desc (hòa → slug)
    priority_soft = [k: d.soft[k] ≥ 0.05], score = d                   # M6.1
    R = luật scope fam|newcomer (thiếu → fam, note "fallback") với conf ≥ 0.6, lift ≥ 1.2,
        mọi kỹ năng của luật ∈ priority_tool; cạnh a→b cho mỗi a ∈ vế trái, b ∈ vế phải
    gói = thành phần liên thông (vô hướng) có ≥ 2 kỹ năng
    trong gói: bỏ chu trình (cắt cạnh conf thấp nhất tới khi DAG); bậc = topo level (bậc 1 = không có cạnh vào)
             mỗi kỹ năng bậc ≥ 2 ghi luật dẫn chứng (conf cao nhất)
    ngoài gói: danh sách "đơn lẻ" theo điểm
    defer = k: share_senior_lead(k) / max(share_newcomer(k), ε) ≥ 3 và d.tool[k] < 0.05
    coverage@N (N=5,10,15): tin newcomer của fam có ≥ 1 tool; ok ⇔ |top_N ∩ tools(tin)| / |tools(tin)| ≥ 0.7
    baseline@N: top N tool phổ biến nhất mọi tin; coverage theo gói (M6.4b)
    split: newcomer 80/20 seed 42; tính lại demand và priority trên 80%; |cov10(20%) − cov10(80%)| ≤ 0.10
    mỗi kỹ năng: demand, n_newcomer_jobs, premium hoặc "không định giá", luật, câu mô tả có số
```

## 4. Ràng buộc

- Không trộn soft vào danh sách tool và ngược lại.
- Câu mô tả chỉ dùng số trong đầu ra (không thêm khẳng định ngoài dữ liệu); ghi giả định "hay đi kèm" được dùng thay "học sau".
- `split_check` tính lại `demand` trên 80%, không dùng `demand` của M1 (để không rò).
- Không có câu nói về người học cụ thể hay chương trình đào tạo.

## 5. Ví dụ (thành test `tests/unit/test_mining_recommend.py`)

| Đầu vào (dựng tay) | Kết quả mong đợi |
|---|---|
| demand A 0,6, B 0,4, C 0,03 | C không trong danh sách ưu tiên |
| delta A = 2, B = -4 (max \|.\| 4) | prem A 0,5 → điểm 0,9; prem B -1 → điểm 0 |
| Luật A ⇒ B mạnh, B ⇒ C mạnh | một gói, bậc A 1, B 2, C 3 |
| Luật A ⇒ B (conf 0,9) và B ⇒ A (conf 0,7) | cắt B ⇒ A; A bậc 1 |
| Kỹ năng D ở 30% tin Senior/Lead, 2% người mới | trong `defer` |
| Nghề 20 tin người mới | không có file, `sd5_index` ghi "ít dữ liệu" |
| top 10 phủ 8/10 kỹ năng của tin | tin đạt (≥ 0,7) |
| Tin người mới không có công cụ | không vào mẫu số, đếm vào `n_excluded_no_tool` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_mining_recommend.py -q` | Xanh |
| Dry-run | `python -m mining.run_mining_pipeline --only bi,fp,salary,recommend --dry-run` | Gửi: 6 nghề × coverage@5/10/15 so baseline, số gói, lệch 80/20, lộ trình Web và Data/AI |
| Nghiệm thu | coverage@10 > baseline; lệch ≤ 10 điểm | Mỗi nghề trong phạm vi |
| Đọc tay | người dùng đọc lộ trình Web, Data/AI | Bước ngược lẽ thường ghi vào Log |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 20/11 | "approved" | 1036a11 |
| 2 | Duyệt prompt | chưa | | |
| 3 | Test rồi code | chưa | | |
| 4 | Dry-run | chưa | Trước khi làm (19/11, top 10 theo tần suất): coverage@10 Web 0,127, Bridge 0,443, Data/AI 0,181, Tester 0,281, DevOps/Cloud 0,089, Security 0,109 | |
| 5 | Review, chạy thật | chưa | | |
