# Đặc tả chi tiết từng bước Mining (M0–M6)

> **Quan hệ với spec 07:** [`07_mining_spec.md`](../07_mining_spec.md) giữ hợp đồng chung (ba tầng, chuỗi bước, đầu vào chung, quyết định đã chốt, đầu ra và bên đọc). Các file ở đây là **đặc tả chi tiết** của từng bước: luật, quy trình theo thứ tự code, input → output, dữ liệu mẫu, kiểm tra. Mỗi luật chỉ ghi chi tiết ở một chỗ, là file của bước đó. Tiêu chí nghiệm thu chung ở [spec 08](../08_evaluation_spec.md); câu hỏi của từng SD ở [`docs/target/`](../../target/00_de_tai.md); điều kiện dữ liệu ở [`06_yeu_cau_du_lieu.md`](../../target/06_yeu_cau_du_lieu.md).
>
> **Ngày viết:** 20/11/2026. **Trạng thái:** người dùng duyệt cả bộ 20/11 ("approved"), gồm mọi đề xuất ở mục 2.2 và M3.1b bỏ 14 tin. Tiếp theo: viết prompt ở `docs/prompting/mining/` (giai đoạn B), rồi mới code (giai đoạn C).
>
> **Số "hiện trạng"** là của lần dry-run chỉ đọc ngày 20/11/2026 trên dữ liệu Processing 19/11 (3.916 tin), bằng code `mining/` chưa sửa (commit df14148). Lệnh: gọi `run_pipeline(..., ["fp","cluster","anomaly","salary"], dry_run=True, compute_shap=False)` từ một script trong thư mục scratch, không ghi `mining/artifacts/`. Code đó tự đọc bảng 04 `all.parquet` vì bảng legacy `data/curated/` không còn trên máy. Số đếm trên Silver lấy bằng pandas, nối Silver với `features.parquet` theo `job_id` (hai file **không cùng thứ tự dòng**).
>
> **Chạy lại 21/11/2026 sau L-57 (PRE-44, sửa luật nhóm nghề, thêm nhóm `Infra/Support`):** số theo nghề ở mục 5–7 của M1–M6 là của lần chạy 20/11, **chưa cập nhật**. Số mới nằm ở `mining/artifacts/mining_metrics.json` (Silver sha256_16 `bbf404d7b0870f4b`) và dashboard. Thay đổi chính: NMI cụm × nghề 0,218 → 0,313; cụm AI Engineer nay đa số Data/AI (độ thuần 0,75), cụm windows/vmware là Infra/Support (0,72); tin gán sai nghề M3 8 → 15; kỹ năng hiếm M2 87 → 121; M5 thắng baseline 10,65%, R²(log) 0,608; M6 có lộ trình cho 8 nghề (thêm Infra/Support 205 tin người mới, Design 53), lệch 80/20 chưa đạt ở Design, DevOps/Cloud, Security; M4 không đổi (246 tin). Chạy lại lần nữa cùng ngày sau L-58 (3 tin đổi nghề sang Data/AI; Silver sha256_16 `8e11e389c5aab7b1`): NMI 0,3141, tin gán sai M3 14, các số khác không đổi.

> **Chạy lại 22/11/2026 sau L-59 (PRE-44 vòng 2: lọc tin không phải IT, luật nghề N3e; bảng 3.718 tin, Silver sha256_16 `60ac8d8b672d45eb`):** sanity S-01..S-06 đạt; FP-Growth 12.642 luật, 124 kỹ năng hiếm; K-Means k = 10 silhouette 0,075, NMI 0,316, ARI với nghề 0,209, tin gán sai 13 (chấm tay 3/10 đúng); ổn định 5 seed 0,826 sau khi nâng `n_init` 150 (50 chỉ còn 0,791); M4 233 tin (6,27%: mới 102, khác 97, chưa rõ 34); M5 MAE 6,105 so baseline 7,332 (hơn 16,7%), R²(log) 0,557, CV R² 0,589; M6 lệch 80/20 đạt ở Bridge, Data/AI, Tester, Web, còn Design, DevOps/Cloud, Infra/Support, Security ghi "tham khảo".

## Mục lục

| Bước | File | Code | SD | Trạng thái |
|---|---|---|---|---|
| M0 Chuẩn bị | [`M0_chuan_bi.md`](M0_chuan_bi.md) | `mining/config.py`, `data_io.py`, `run_mining_pipeline.py`, `sanity.py` | chung | Đã duyệt, chưa sửa code |
| M1 BI | [`M1_bi.md`](M1_bi.md) | **mới** `mining/bi.py` | SD1 | Đã duyệt, chưa có code |
| M2 Gói kỹ năng | [`M2_fp_growth.md`](M2_fp_growth.md) | `mining/association.py` | SD2 | Đã duyệt, chưa sửa code |
| M3 Nhóm việc | [`M3_phan_cum.md`](M3_phan_cum.md) | `mining/clustering.py` | SD3 (3.1, 3.2) | Chạy thật 20/11 (1.D, 2.B, 3.B) |
| M4 Tin khác hoặc mới | [`M4_tin_khac_moi.md`](M4_tin_khac_moi.md) | `mining/anomaly.py` | SD3 (3.3) | Chạy thật 20/11 (1.B, 2.A) |
| M5 Lương và SHAP | [`M5_luong_shap.md`](M5_luong_shap.md) | `mining/salary_model.py` | SD4 | Chạy thật 20/11 (1.B, 2.A) |
| M6 Lộ trình | [`M6_lo_trinh.md`](M6_lo_trinh.md) | **mới** `mining/recommend.py` | SD5 | Chạy thật 20/11 (1.B, 2.A, 3.B, 4.B) |

## Khuôn của mỗi file

Giống [`docs/spec/processing/`](../processing/README.md), 7 mục theo thứ tự:

1. **Mục đích**: SD, câu hỏi, tiêu chí.
2. **Luật**: 2.1 đang chạy (code hiện tại); 2.2 **đề xuất** (bộ này đã duyệt 20/11). Ngưỡng chưa chốt ghi "đề xuất", không ghi như đã chốt.
3. **Quy trình xử lý**: các bước đánh số theo thứ tự sẽ thực thi.
4. **Input → Output**: đường dẫn, schema, metrics.
5. **Dữ liệu mẫu**: điền sau lần chạy thật.
6. **Kiểm tra và nghiệm thu**: test, lệnh, ngưỡng, kết quả.
7. **Trạng thái, chỗ thiếu, việc mở**: mã trong `docs/KNOWN_ISSUED.md`.

## Chuỗi bước

```text
Silver  data/preprocessing/04_normalization/silver.parquet   (26 trường, 3.916 tin)
10      data/processing/10_features/features.parquet          (skill__ / concept__ / soft__, n_tools, salary_target_m…)
08      data/processing/08_skills/job_skills.parquet          (slug, level, kind, type → skill_view)
12_e5   data/processing/12_e5/job_emb.npz                     (khóa job = mô tả + yêu cầu)
  ▼ M0  nạp và kiểm hợp đồng (MiningData: meta + 3 ma trận + e5 job)
  ▼ M1  bi         → sd1_<câu>.json                     (baseline lương cho M5, demand cho M6)
  ▼ M2  fp         → skill_association_rules.parquet, sd2_*.json
  ▼ M3  cluster    → job_clusters.parquet, cluster_family_crosstab.json
  ▼ M4  anomaly    → job_anomalies.parquet               (dùng GLOSH của M3)
  ▼ M5  salary     → skill_salary_shap_values.parquet, salary_estimates.parquet
  ▼ M6  recommend  → sd5_<nghề>.json                     (dùng M1, M2, M5)
mining/artifacts/  + mining_metrics.json (sha256 đầu vào, sanity, targets)
```

- Lệnh: `python -m mining.run_mining_pipeline [--only bi,fp,…] [--dry-run]`. Dry-run tính đủ nhưng không ghi `mining/artifacts/`.
- Mining **chỉ đọc** file trên máy; không đụng R2, PostgreSQL, Airflow.
- `random_state` 42 cho mọi thuật toán; dữ liệu thật; `--synthetic` chỉ cho test, không lấy số báo cáo (L-19).
- Mining **không sửa** giá trị của Silver hay của Processing. Thiếu gì thì ghi chỗ thiếu, không tự điền.

## Đầu vào chung và quy ước

| Đầu vào | Dùng | Ghi chú |
|---|---|---|
| Silver | M1–M6 (meta) | Người dùng chốt: Silver là đầu vào chung của Processing và Mining. Thay `curated_flat_golden_jobs.parquet` (legacy, PRE-39) |
| `features.parquet` | M2–M5 | Nối theo `job_id_global` = `job_id` của Silver, không theo thứ tự dòng |
| `job_skills.parquet` | M1 (top theo view), M2 (bảng 2.1), M6 | Dùng `processing.extraction.skills.skill_view`; không định nghĩa lại K-tool |
| `job_emb.npz` khóa `job` | M3 | Không dùng khóa `all` (có phúc lợi) |

**Ba góc nhìn kỹ năng** (`docs/target/06_yeu_cau_du_lieu.md` mục 2): K-tool = cột `skill__*`; K-concept = `concept__*`; K-soft = `soft__*`. Cột `<khối>__other_skill` là kỹ năng hiếm đã gom (DF < 15), không phải một kỹ năng: không đưa vào luật, xếp hạng, hay vector phân cụm.

**Người mới** = `seniority` ∈ {Intern/Fresher, Junior} (1.181 tin). **Middle+** = {Middle, Senior, Lead/Manager}. `seniority` null (285 tin) không thuộc nhóm nào.

**Sáu nghề lớn** (≥ 30 tin người mới, khác Other): Web 514, Tester 123, Data/AI 98, Bridge 94, Security 64, DevOps/Cloud 45 (số tin người mới). Other 180 không làm lộ trình; Game 26, Design 26, IoT 6, Mobile 5 ghi "ít dữ liệu".

## Đầu ra và bên đọc

| File trong `mining/artifacts/` | Bước | Bên đọc |
|---|---|---|
| `sd1_<câu>.json` | M1 | Monitoring Insights; M5 (baseline cấp × nghề); M6 (`demand`) |
| `skill_association_rules.parquet`, `sd2_top_skills.json`, `sd2_rare_skills.json` | M2 | Monitoring, Mart, M6 |
| `job_clusters.parquet`, `cluster_family_crosstab.json` | M3 | Monitoring, Mart, M4 |
| `job_anomalies.parquet` | M4 | Monitoring, Mart |
| `skill_salary_shap_values.parquet`, `salary_estimates.parquet`, `trained_salary_rf_model.joblib` | M5 | Monitoring, M6 |
| `sd5_<nghề>.json` | M6 | Monitoring |
| `mining_metrics.json` | tất cả | spec 08, Monitoring |

`mining/artifacts/` không vào git. Dẫn số vào báo cáo thì ghi ngày chạy và sha256 đầu vào lấy từ `mining_metrics.json`.

## Quy trình làm mỗi bước (người dùng chốt 19/11)

1. Duyệt đặc tả (file ở đây). 2. Duyệt prompt (`docs/prompting/mining/`). 3. Viết test, rồi code. 4. Dry-run, gửi bảng số. 5. Cùng review theo mục 6; đạt thì chạy thật, ghi số vào mục 5–6 và Log của prompt, commit.
