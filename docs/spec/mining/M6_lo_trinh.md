# M6: Lộ trình học cho người mới (SD5)

> Code: **mới** `mining/recommend.py`: `priority_scores`, `learning_path`, `defer_list`, `coverage_at`, `split_check`, `run_recommend`. Dùng lại `coverage_at`, `NEWCOMER`, `BIG_FAMILIES` của `scripts/eval_skill_views.py` (chuyển phần dùng chung vào `mining/`, script import lại, không viết hai bản).
> Lệnh: `python -m mining.run_mining_pipeline --only bi,fp,salary,recommend [--dry-run]`.
> Câu hỏi: [`docs/target/05_sd5_lo_trinh_hoc.md`](../../target/05_sd5_lo_trinh_hoc.md). Trạng thái: **bản nháp 20/11, chờ duyệt; chưa có code.**

## 1. Mục đích

Với mỗi nghề đủ dữ liệu:

- 5.1 kỹ năng người mới nên ưu tiên, **hai danh sách** (công cụ K-tool; kỹ năng mềm và ngoại ngữ K-soft);
- 5.2 thứ tự học;
- 5.3 kỹ năng chưa nên đầu tư sớm;
- 5.4 học đủ top N thì đáp ứng bao nhiêu phần trăm tin người mới.

Mọi kỹ năng truy được về `demand` (M1), luật (M2), giá trị SHAP (M5). SD5 chỉ nói thị trường đòi gì, không đo khoảng cách của một người học cụ thể.

## 2. Luật

### 2.1. Đang chạy

Chưa có code. Số đo trước (`scripts/eval_skill_views.py`, 19/11, K-tool, top 10 theo tần suất, tin người mới, ngưỡng 70%): coverage@10 Web 0,127; Bridge 0,443; Data/AI 0,181; Tester 0,281; DevOps/Cloud 0,089; Security 0,109.

Một danh sách top 10 chung cho cả nghề Web chỉ đáp ứng 13% tin Web người mới, vì nghề Web gồm nhiều ngăn xếp (Java/Spring, .NET, PHP, JS/React, Mobile…).

### 2.2. Đề xuất, chờ duyệt

| Mã | Đề xuất | Lý do |
|---|---|---|
| M6.0 | **Phạm vi:** nghề có ≥ 30 tin người mới và khác Other: Web (514), Tester (123), Data/AI (98), Bridge (94), Security (64), DevOps/Cloud (45). Game (26), Design (26), IoT (6), Mobile (5): ghi "ít dữ liệu". Other (180): không làm lộ trình (không phải một nghề) | SD5 mục 7; ngưỡng 30 PRE-36 |
| M6.1 | 5.1: `điểm(k) = demand(k) × (1 + premium_chuẩn_hóa(k))`. `demand` từ M1.D (tin người mới của nghề). `premium_chuẩn_hóa(k)` = `delta_m(k)` (M5, phạm vi ALL) chia max |`delta_m`| trong các kỹ năng của nghề, thuộc [−1, 1]; kỹ năng M5 không định giá được (< 30 tin) thì 0. Chỉ xếp kỹ năng `demand` ≥ 5%. **Danh sách tool** dùng `premium`; **danh sách soft** chỉ theo `demand` (M5 không định giá soft) | SD5 câu 5.1; quyết định 2 |
| M6.2 | 5.2 **theo gói**: lấy luật M2 phạm vi "nghề × người mới" (fallback: phạm vi nghề, ghi rõ). Luật mạnh = conf ≥ 0,60 và lift ≥ 1,20, cả hai vế nằm trong top ưu tiên. Dựng đồ thị A ⇒ B; **gói** = thành phần liên thông; trong mỗi gói, bậc 1 = kỹ năng không là vế phải của luật mạnh nào trong gói, bậc sau theo thứ tự topo; chu trình thì cắt cạnh confidence thấp nhất. Kỹ năng không thuộc gói nào xếp riêng theo điểm. Mỗi bước ghi luật dẫn chứng (A ⇒ B, conf, lift) | SD5 câu 5.2; coverage của một danh sách chung thấp nên trình bày theo gói (ví dụ gói Java/Spring, gói JS/React trong Web) |
| M6.3 | 5.3: trong nghề, `share_senior_lead(k) / share_newcomer(k) ≥ 3` **và** `demand(k)` < 5% (theo SD5; ngưỡng 3 và 5% PRE-36). Ghi cả hai tỷ lệ | SD5 câu 5.3 |
| M6.4 | 5.4: `coverage@N` với N = 5, 10, 15 = tỷ lệ tin người mới của nghề mà top N kỹ năng (theo điểm M6.1, danh sách tool) đáp ứng ≥ 70% số K-tool tin đó đòi. Tin không có K-tool nào: **không tính vào mẫu số**, ghi số tin bị bỏ. **Baseline** = top N kỹ năng phổ biến nhất toàn thị trường (mọi tin, mọi nghề) | SD5 câu 5.4, mục 6 |
| M6.4b | Báo thêm `coverage@N` **theo gói** (tin người mới có ≥ 1 kỹ năng của gói, top N trong gói) cho nghề có ≥ 2 gói | Đo đúng cách trình bày theo gói của M6.2 |
| M6.5 | `split_check`: chia tin người mới của nghề 80/20 (seed 42, phân tầng theo nguồn nếu đủ), tính điểm trên 80%, đo coverage@10 trên 20%; chênh với coverage trên chính 80% ≤ 10 điểm phần trăm | SD5 mục 6 |
| M6.6 | Mỗi kỹ năng trong đầu ra có `demand`, `n_newcomer_jobs`, `premium` (hoặc "không định giá"), luật dẫn chứng (nếu có), và một câu mô tả có số, ví dụ "62% tin Web cho người mới đòi JavaScript" | SD5 mục 5, "truy được nguồn" |

## 3. Quy trình xử lý

1. Nhận `demand` (M1.D), luật (M2), `delta_m` (M5) — từ artifact hoặc tính trong bộ nhớ trong cùng lần chạy.
2. Với mỗi nghề trong phạm vi M6.0: `priority_scores` (hai danh sách).
3. `learning_path` theo gói (M6.2).
4. `defer_list` (M6.3).
5. `coverage_at` N = 5, 10, 15 cho nghề và theo gói; baseline toàn thị trường.
6. `split_check`.
7. Ghi `sd5_<nghề>.json` (bỏ qua nếu dry-run) và khối `recommend` trong metrics.

## 4. Input → Output

| Input | Dùng |
|---|---|
| `sd1_demand.json` (M1.D) | `demand` |
| `skill_association_rules.parquet` (M2, phạm vi nghề × người mới) | gói, thứ tự |
| `skill_salary_shap_values.parquet` (M5) | `premium` |
| `meta.seniority`, `meta.job_family`, `MiningData.skills` | 5.3, 5.4 |

| Output | Nội dung |
|---|---|
| `sd5_<nghề>.json` | `priority_tool`, `priority_soft`, `path` (gói → bậc → kỹ năng + luật), `defer`, `coverage` (N, nghề, baseline, theo gói), `split_check`, `notes` |
| `sd5_index.json` | danh sách nghề có lộ trình và nghề "ít dữ liệu" |
| `mining_metrics.json` khối `recommend` | coverage@10 so baseline theo nghề, lệch 80/20 |

## 5. Dữ liệu mẫu

Điền sau lần chạy thật.

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| coverage@10 của nghề > baseline toàn thị trường | mỗi nghề trong phạm vi |
| Lệch 80/20 | ≤ 10 điểm phần trăm (PRE-36) |
| Mọi kỹ năng có `demand`; kỹ năng có `premium` khác 0 phải có trong bảng SHAP | bắt buộc |
| Danh sách tool không có kỹ năng soft và ngược lại | test |
| Đọc tay lộ trình 2 nghề (đề xuất Web, Data/AI): bước ngược lẽ thường (ví dụ Docker trước ngôn ngữ) ghi lại | người dùng đọc |
| `pytest tests/unit/test_mining_recommend.py` (mới): điểm, bậc từ luật dựng tay, chu trình, defer, coverage, nghề < 30 tin | xanh |

## 7. Trạng thái, chỗ thiếu, việc mở

- Chưa có code (MINE-7). Phụ thuộc M1, M2 (phân tầng nghề × người mới), M5.
- Chờ duyệt M6.1 (soft chỉ theo demand), M6.2 (gói = thành phần liên thông), M6.4 (bỏ tin 0 công cụ khỏi mẫu số), M6.4b.
- PRE-35 (ít tin người mới), PRE-36, PRE-40.
