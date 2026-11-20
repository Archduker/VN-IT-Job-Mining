# M3: Nhóm việc cho SD3 (câu 3.1, 3.2)

> Code: `mining/clustering.py` (`build_vector_space`, `reduce_svd`, `scan_k`, `choose_k`, `fit_labels`, `run_hdbscan`, `profile_clusters`, `cluster_jobs`). Hàm mới đề xuất: `seed_stability`, `family_crosstab`, `flag_family_mismatch`.
> Lệnh: `python -m mining.run_mining_pipeline --only cluster [--dry-run]`.
> Câu hỏi: [`docs/target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md`](../../target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md). Trạng thái: **đã duyệt 20/11 (người dùng: "approved").**

## 1. Mục đích

- 3.1: chỉ từ nội dung JD và kỹ năng, thị trường chia thành mấy nhóm việc, mỗi nhóm là việc gì?
- 3.2: nhóm máy tìm khớp hay lệch với `job_family` (luật) ở đâu: nghề lai, nghề ngách, tin có vẻ bị gán sai.

`job_family` **không** vào vector; chỉ dùng để so sánh.

## 2. Luật

### 2.1. Đang chạy (code hiện tại, dry-run 20/11)

| Mã | Luật | Số 20/11 |
|---|---|---|
| M3.1 | Vector = khối kỹ năng (290 cột K-tool, trọng số 0,5) + e5 khóa `all` (`e5_weight` 0,5), chuẩn hóa L2; TF-IDF tắt (`tfidf_weight` 0) | Không lọc tin: 3.916 tin, gồm 672 tin không có cột K-tool nào |
| M3.2 | TruncatedSVD giữ ~80% phương sai, tối đa 60 thành phần, chuẩn hóa L2 lại | 60 thành phần, giải thích 73,3% |
| M3.3 | K-Means `k_fixed` = 10; vẫn quét k = 2–20 | Silhouette k=10: 0,165; DB 2,26. Silhouette tăng gần như đều theo k (0,089 ở k=2 → 0,207 ở k=20), không có "khuỷu" rõ |
| M3.4 | HDBSCAN `min_cluster_size` 25, cờ GLOSH trên P97 | 12 cụm, 69,7% tin là nhiễu, 3,0% cờ GLOSH |
| M3.5 | ARI/NMI với `job_family` trên tin khác Other | 3.390 tin: ARI 0,057, NMI 0,179. Không e5: Silhouette 0,169, ARI 0,095 |
| M3.6 | Hồ sơ cụm: 8 kỹ năng theo lift, nghề chiếm đa số, độ thuần | Xem bảng dưới |

Cụm 20/11 (code cũ):

| Cụm | Tên tự sinh | Số tin | Nghề đa số | Độ thuần |
|---|---|---|---|---|
| 0 | Web · css/html | 286 | Web | 0,82 |
| 1 | Web · ios/android | 164 | Web | 0,51 |
| 2 | Web · windows/linux | 1.240 | Web | 0,33 |
| 3 | Other · ms_word/powerpoint | 171 | Other | 0,28 |
| 4 | Web · sql/power_bi | 248 | Web | 0,26 |
| 5 | Web · spring_boot/mongodb | 497 | Web | 0,67 |
| 6 | Web · ms_office/windows | 210 | Web | 0,55 |
| 7 | Bridge · confluence/jira | 225 | Bridge | 0,49 |
| 8 | DevOps/Cloud · terraform/ansible | 407 | DevOps/Cloud | 0,44 |
| 9 | Data/AI · python/power_bi | 468 | Data/AI | 0,38 |

Cụm 2 (1.240 tin, 32%, độ thuần 0,33) gom phần lớn tin ít công cụ: đây là dấu hiệu cụm tách theo "thiếu kỹ năng" như L-47, cần đo ở M3.8.

### 2.2. Đề xuất, đã duyệt 20/11 (chưa có code)

| Mã | Đề xuất | Lý do |
|---|---|---|
| M3.1a | **Vector = `skill__` (K-tool) + `concept__` (K-concept) + e5 `job`.** Bỏ ba cột `__other_skill`. Mỗi khối chuẩn hóa L2 theo dòng rồi nhân √trọng số. **Trọng số đề xuất 0,35 / 0,15 / 0,5** (tool / concept / e5) | Người dùng chốt 19/11 (thay quyết định 3 ngày 17/11). Concept giúp 643 tin không có công cụ (BA, Tester, IT Manager, presales; trung vị 8 khái niệm/tin) có vị trí đúng; e5 `job` không có phúc lợi |
| M3.1b | **Tập tin:** giữ tin có `n_tools + n_concepts ≥ 1`. 20/11 bỏ **14 tin**. Ghi `n_dropped_no_technical_skill` | Kế hoạch ghi "bỏ 1 tin" là số tin không có kỹ năng nào (`n_skills = 0`); theo đúng định nghĩa "kỹ năng kỹ thuật" (tool + concept) là 14 tin. **Người dùng duyệt 20/11: bỏ 14 tin** |
| M3.1c | Gỡ TF-IDF (M0.6) | Quyết định 1 |
| M3.2 | Giữ SVD ~80%, tối đa 60; báo phương sai giải thích | — |
| M3.3 | Giữ k = 10 (đã chốt 11/11) và quét 2–20 để báo cáo. Nếu duyệt đổi k thì ghi ở đây | — |
| M3.7 | `seed_stability`: chạy K-Means với 5 seed (42, 43, 44, 45, 46) trên cùng không gian; ARI từng cặp với seed 42; báo trung bình và nhỏ nhất | Spec 08: ARI ≥ 0,8 (PRE-36) |
| M3.8 | Hồ sơ cụm thêm: trung vị `n_tools`, `n_concepts`; top 5 tiêu đề (`title`); phân bố cấp; trung vị `salary_target_m` (n ≥ 30, M1.0b). **Kiểm "không tách theo số kỹ năng"**: không cụm nào có trung vị `n_tools` < 1 hoặc > 2 × trung vị toàn bộ (đề xuất) | SD3 mục 6, L-47 |
| M3.9 | Artifact `cluster_family_crosstab.json`: bảng chéo cụm × `job_family` (số tin và tỷ lệ theo hàng) | SD3 câu 3.2 |
| M3.10 | Luật 3.2 (ngưỡng đề xuất): **nghề lai** = cụm không có nghề nào > 60% và có ≥ 2 nghề ≥ 20%; **nghề ngách** = một nghề có ≥ 2 cụm mà nghề đó chiếm ≥ 50% cụm, hoặc cụm nhỏ (< 5% số tin) có ≥ 3 công cụ lift ≥ 5; **có vẻ gán sai** = tin có `job_family` ≠ nghề đa số của cụm (nghề đa số chiếm ≥ 60%), khoảng cách tới tâm cụm ≤ P25 của cụm, và nghề của tin chiếm < 10% cụm | SD3 câu 3.2; trước đây chỉ có bảng hồ sơ, không có luật |
| M3.11 | `job_clusters.parquet` thêm cột `in_clustering` (false cho tin bị bỏ ở M3.1b), `family_mismatch` (M3.10), `dist_to_centroid` | M4 dùng GLOSH; Monitoring vẽ |

## 3. Quy trình xử lý

1. Lấy `skills`, `concepts`, e5 `job` từ M0; lọc tin theo M3.1b.
2. `build_vector_space`: ba khối, chuẩn hóa, nhân trọng số, ghép.
3. `reduce_svd` → L2.
4. `scan_k` (2–20), `fit_labels` với `k_fixed` = 10.
5. `seed_stability` (5 seed).
6. `run_hdbscan` → điểm GLOSH, cờ P97.
7. `profile_clusters` (M3.8), PCA 3 thành phần để vẽ.
8. `family_crosstab`, ARI/NMI trên tin khác Other, `flag_family_mismatch` (M3.10).
9. So với không gian không có e5 (giữ khối `without_e5` để báo cáo).
10. Ghi artifact (bỏ qua nếu dry-run).

## 4. Input → Output

| Input | Dùng |
|---|---|
| `MiningData.skills`, `.concepts`, `.e5` (khóa `job`) | vector |
| `meta.job_family`, `title`, `seniority`, `salary_target_m`, `n_tools`, `n_concepts` | so sánh, hồ sơ |

| Output | Nội dung |
|---|---|
| `job_clusters.parquet` | `job_id`, `in_clustering`, `cluster_id`, `hdbscan_label`, `glosh_score`, `glosh_outlier`, `dist_to_centroid`, `family_mismatch`, `pca_x/y/z` |
| `cluster_family_crosstab.json` | M3.9 + nhãn nghề lai / ngách (M3.10) |
| `mining_metrics.json` khối `clustering` | tham số, trọng số khối, `n_dropped_no_technical_skill`, quét k, Silhouette, DB, ARI 5 seed, ARI/NMI với nghề, hồ sơ cụm, số tin gán sai |

## 5. Dữ liệu mẫu

Điền sau lần chạy thật.

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Ổn định: ARI trung bình 5 seed | ≥ 0,8 (PRE-36) |
| Cụm nhỏ nhất | ≥ 1% số tin (PRE-36) |
| Không tách theo số kỹ năng (M3.8) | không cụm nào vi phạm (đề xuất) |
| Silhouette, DB | chỉ báo cáo (chưa có ngưỡng, PRE-36) |
| Kiểm tay 20 tin "có vẻ gán sai" (seed 42) | ghi tỷ lệ đúng; chưa có ngưỡng |
| Đọc tên cụm: mỗi cụm có top công cụ, top khái niệm, top tiêu đề | bắt buộc |
| `pytest tests/unit/test_mining_clustering.py` (sửa theo ba khối, khóa `job`) | xanh |

## 7. Trạng thái, chỗ thiếu, việc mở

- Có code phân cụm; thiếu khối concept, khóa `job`, lọc tin, 5 seed, bảng chéo, luật 3.2 (MINE-7).
- Đã duyệt 20/11: M3.1b bỏ 14 tin; trọng số 0,35 / 0,15 / 0,5; ngưỡng M3.8, M3.10.
- MINE-1 (Silhouette thấp), PRE-36.
