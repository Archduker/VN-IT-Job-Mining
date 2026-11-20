# M1: BI cho SD1 (bức tranh thị trường)

> Code: **mới** `mining/bi.py`, mỗi câu một hàm `q1_1` … `q1_7`, hàm chung `run_bi(data) -> dict[câu, bảng]`. Gọi từ `run_pipeline` bước `bi`.
> Lệnh: `python -m mining.run_mining_pipeline --only bi [--dry-run]`.
> Câu hỏi: [`docs/target/01_sd1_buc_tranh_thi_truong.md`](../../target/01_sd1_buc_tranh_thi_truong.md). Trạng thái: **bản nháp 20/11, chờ duyệt; chưa có code.**

## 1. Mục đích

Trả lời câu 1.1–1.7 của SD1 bằng **đếm, tỷ lệ, bảng chéo, trung vị, tứ phân vị** trên Silver. M1 còn là:

- **baseline lương** cho M5 (trung vị `salary_target_m` theo cấp × nghề);
- nguồn **`demand(k)`** cho M6 (tỷ lệ tin người mới của nghề có kỹ năng k).

Tiêu chí: completeness (tổng mỗi bảng = 3.916, có dòng "Không rõ"), accuracy (đối chiếu tay 20 tin), tái lập.

## 2. Luật

### 2.1. Đang chạy

Chưa có. Trang Insights hiện đọc Postgres (`curated_jobs`) do `scripts/load_mart_from_parquet.py` nạp từ bảng legacy.

### 2.2. Đề xuất, chờ duyệt

**Quy tắc chung cho mọi bảng:**

| Mã | Luật |
|---|---|
| M1.0a | Mỗi bảng ghi `n` (số tin của ô) và `coverage` (tỷ lệ tin có giá trị ở cột đang đếm). Giá trị null đếm vào dòng **"Không rõ"**, không bỏ |
| M1.0b | Ô có n < 30 (PRE-36, đề xuất) vẫn ghi `n` nhưng giá trị thống kê (tỷ lệ, trung vị) thay bằng `null` kèm `"note": "ít dữ liệu"` |
| M1.0c | Lương: chỉ tin có `salary_target_m` (bước 10) và `salary_outlier = false`. **Không bù** lương thiếu. Thống kê là trung vị, P25, P75 (triệu VNĐ/tháng) |
| M1.0d | Cấp có tỷ lệ thỏa thuận ≥ 55% (đề xuất) ghi chú "MNAR: lương công bố ít, trung vị có thể thấp hơn thực tế" (quyết định 3, 19/11). 20/11: Senior 73,0%, Lead/Manager 58,1%, chưa rõ cấp 73,3% |
| M1.0e | Không có câu chữ "tăng", "giảm", "xu hướng" trong đầu ra |

**Từng câu:**

| Câu | Bảng | Cột Silver | Ghi chú |
|---|---|---|---|
| 1.1 | Đếm `job_family`; bảng chéo `job_family` × `source`, tỷ lệ theo hàng của nguồn | `job_family`, `source` | 11 nhóm (gồm Other) |
| 1.2 | Đếm `seniority` (5 nhãn + Không rõ); bảng chéo `seniority` × `job_family`; tách `seniority_inferred` true/false | `seniority`, `seniority_inferred` | 20/11: 2.978/3.916 tin (76%) có cấp suy ra |
| 1.3 | Top 10 tỉnh + "Khác" + "Không rõ"; bảng chéo `work_mode` × `job_family` | `province`, `work_mode` | `work_mode` 20/11: onsite 3.665, hybrid 181, remote 40, unknown 30 |
| 1.4a | Tỷ lệ có lương theo `source`, `job_family`, `seniority` | `salary_negotiable`, `salary_target_m` | "Có lương" = `salary_target_m` khác null. 20/11: 1.731 có số, 2.192 thỏa thuận, trong đó 20 tin vừa thỏa thuận vừa có số (đếm vào "có lương", ghi riêng) |
| 1.4b | Trung vị, IQR `salary_target_m` theo `job_family` × `seniority` và theo tỉnh (top 10) | + `salary_outlier` | n lương dùng được 20/11: 1.644 |
| 1.5 | Người mới vs Middle+: (1) trung vị `exp_min_years` chỉ trên `exp_inferred = false`; (2) trung vị `n_tools`; (3) top 15 K-tool và top 10 K-soft của mỗi nhóm (hai bảng riêng); (4) % `language = "en"`; (5) trung vị lương | `seniority`, `exp_*`, `language`, `n_tools` (bước 10), `job_skills` (bước 08, `skill_view`) | `n_tools` trung vị 20/11: người mới 4, Middle+ 5. Không dùng `n_skills` (lẫn soft) cho chỉ số "bao nhiêu kỹ năng" |
| 1.6 | Top 15 phúc lợi; bảng chéo top 5 phúc lợi × `seniority` và × `job_family` | `benefits` | Tỷ lệ trên số tin có ít nhất một phúc lợi |
| 1.7 | Tỷ lệ `job_family` và `seniority` trong từng `posted_month`; **bảng so sánh T9 với T10–T11 chỉ trên 6 nguồn** (vietnamworks, careerviet, vieclam24h, itviec, glints, jobsgo) | `posted_month`, `source` | 20/11: T9 863, T10 3.033, T11 20 (T11 < 30 → "ít dữ liệu"). topcv chỉ 10 tin T9, topdev 0 |

**Baseline cho M5 và `demand` cho M6** (ghi trong `sd1_1_4.json` và `sd1_demand.json`):

| Mã | Luật |
|---|---|
| M1.B | `baseline_salary[family][seniority]` = trung vị `salary_target_m` trên tập lương dùng được. Ô n < 30 lùi về trung vị theo cấp, rồi trung vị toàn bộ; ghi rõ ô nào lùi |
| M1.D | `demand[family][k]` = tỷ lệ tin người mới của nghề có kỹ năng k, tính riêng ba view (tool, concept, soft) từ `job_skills` + `skill_view`. Chỉ cho nghề có ≥ 30 tin người mới |

## 3. Quy trình xử lý

1. Nhận `MiningData` từ M0 (meta Silver đã đổi tên cột, `n_tools`, `salary_target_m`).
2. Đọc `job_skills.parquet`, lọc theo `skill_view` (tool, soft) cho câu 1.5 và M1.D.
3. Chạy `q1_1` … `q1_7` theo thứ tự; mỗi hàm trả `{"question", "tables": [...], "n_total", "notes"}`.
4. Tính `baseline_salary` (M1.B), `demand` (M1.D).
5. Kiểm tổng mỗi bảng = 3.916 (hoặc số tin của tập con có ghi rõ), tỷ lệ cộng ra 100% (sai số làm tròn ≤ 0,1).
6. Ghi `mining/artifacts/sd1_<câu>.json` (bỏ qua nếu dry-run) và khối `bi` trong `mining_metrics.json` (số bảng, số ô "ít dữ liệu", kết quả kiểm tổng).

## 4. Input → Output

| Input | Dùng |
|---|---|
| `MiningData.meta` (Silver) | mọi câu |
| `features.parquet`: `n_tools`, `salary_target_m` | 1.4, 1.5 |
| `job_skills.parquet` + `skill_view` | 1.5, M1.D |

| Output | Nội dung |
|---|---|
| `sd1_1_1.json` … `sd1_1_7.json` | Mỗi file: danh sách bảng, mỗi bảng có `rows` (nhãn, `n`, giá trị), `n_total`, `coverage`, `notes` |
| `sd1_baseline_salary.json` | M1.B (cho M5) |
| `sd1_demand.json` | M1.D (cho M6) |
| `mining_metrics.json` khối `bi` | `n_tables`, `n_cells_low_data`, `totals_ok` |

## 5. Dữ liệu mẫu

Điền sau lần chạy thật. Số đo trước (pandas, 20/11, Silver + features nối theo id):

| Cấp | Tỷ lệ thỏa thuận | n lương dùng được | Trung vị `salary_target_m` (triệu) |
|---|---|---|---|
| Intern/Fresher | 43,7% | 291 | 10,0 |
| Junior | 47,4% | 339 | 15,5 |
| Middle | 52,8% | 552 | 22,5 |
| Senior | 73,0% | 140 | 37,5 |
| Lead/Manager | 58,1% | 260 | 30,0 |
| Không rõ | 73,3% | 62 | 35,0 |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Tổng mỗi bảng toàn bộ = 3.916; có dòng "Không rõ" khi cột có null | bắt buộc |
| Ô n < 30 không có số thống kê | bắt buộc |
| Trung vị lương 4 cấp Intern/Fresher < Junior < Middle < Senior (S-04 sau khi sửa ở M0) | pass |
| Đối chiếu tay 20 tin ngẫu nhiên (seed 42): nghề, cấp, tỉnh, lương khớp trang gốc | ≥ 18/20 (đề xuất) |
| Chạy lại ra cùng JSON (trừ `generated_at`) | bắt buộc |
| `pytest tests/unit/test_mining_bi.py` (mới): bảng nhỏ dựng tay, kiểm tổng, "ít dữ liệu", lương bỏ ngoại lai, bảng 1.7 bỏ topcv/topdev | xanh |

## 7. Trạng thái, chỗ thiếu, việc mở

- Chưa có code (MINE-7). Chờ duyệt M1.0a–M1.0e, M1.B, M1.D, ngưỡng 55% của M1.0d và 18/20 ở mục 6.
- Trang Insights đọc JSON này là việc của Monitoring (spec 09), không thuộc M1.
- PRE-36 (ngưỡng n < 30), PRE-38 (tỉnh).
