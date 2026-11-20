# Prompt M3: Nhóm việc cho SD3 (phân cụm)

> Đặc tả: [`docs/spec/mining/M3_phan_cum.md`](../../spec/mining/M3_phan_cum.md) (M3.1a–c, M3.2, M3.3, M3.7–M3.11; đã duyệt 20/11, M3.1b bỏ 14 tin). Câu hỏi: `docs/target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md` câu 3.1, 3.2.
> **Trạng thái:** viết 20/11, chờ duyệt prompt. Cần M0 xong.

## 1. Ngữ cảnh

**Đọc trước:** đặc tả M3; `mining/clustering.py`; `tests/unit/test_mining_clustering.py`.

**Vì sao làm** (dry-run 20/11, code cũ):

- Silhouette 0,165 (k = 10). Cụm 2 gom 1.240 tin, độ thuần 0,33: dấu hiệu tách theo "ít kỹ năng" (L-47).
- Vector chỉ có K-tool và e5 `all`. 643 tin không có công cụ (BA, Tester, IT Manager) không có chỗ đứng.
- Chưa có 5 seed, bảng chéo, luật 3.2.

**Người dùng chốt:** K-tool + K-concept + e5 `job` (19/11); trọng số 0,35 / 0,15 / 0,5; bỏ tin `n_tools + n_concepts = 0` (14 tin, 20/11).

## 2. Việc cần sửa

**Input:** `MiningData.skills`, `.concepts`, `.e5` (khóa `job`); `meta` (`job_family`, `title`, `seniority`, `salary_target_m`, `n_tools`, `n_concepts`).

**Output:**

- `job_clusters.parquet`: `job_id`, `in_clustering`, `cluster_id`, `hdbscan_label`, `glosh_score`, `glosh_outlier`, `dist_to_centroid`, `family_mismatch`, `pca_x/y/z`. Tin bị bỏ có `cluster_id` = -1 và các điểm là null.
- `cluster_family_crosstab.json`.
- Khối `clustering` trong metrics.

**File:**

- `mining/clustering.py`: `build_vector_space` nhận dict khối → trọng số; `seed_stability`, `family_crosstab`, `flag_family_mismatch`, `profile_clusters` mở rộng.
- `mining/config.py`: `ClusteringParams.block_weights = {"tool": 0.35, "concept": 0.15, "e5": 0.5}`, `stability_seeds` (42–46), `hybrid_max_share` 0,6, `hybrid_min_second` 0,2, `niche_family_share` 0,5, `niche_small_share` 0,05, `niche_min_lift` 5, `niche_min_skills` 3, `mismatch_majority` 0,6, `mismatch_dist_q` 0,25, `mismatch_family_share` 0,1, `skill_count_ratio_max` 2.
- `run_mining_pipeline.py`.

## 3. Pseudo code

```
keep = (n_tools + n_concepts) ≥ 1                    # M3.1b; ghi n_dropped_no_technical_skill
blocks = {tool: skills[keep], concept: concepts[keep], e5: e5[keep]}
X = hstack( l2_rows(B) × sqrt(w_B) for B in blocks ); X = l2_rows(X)   # dòng toàn 0 của một khối giữ 0
Z = reduce_svd(X) → l2_rows
scan_k(Z, 2..20); labels = KMeans(k_fixed=10, seed 42)
stability: với s in 43..46: ARI(labels_s, labels_42) → mean, min
hdb = run_hdbscan(Z) → glosh_score, glosh_outlier (P97)
profile: mỗi cụm: size, share, top 8 tool theo lift, top 5 concept theo lift, top 5 title,
         phân bố seniority, median n_tools, n_concepts, median salary_target_m (n ≥ 30)
skill_count_check: cụm vi phạm nếu median n_tools < 1 hoặc > 2 × median toàn bộ
crosstab = cụm × job_family (n, tỷ lệ hàng); ARI/NMI trên tin ≠ Other
hybrid  = cụm có max share < 0,6 và ≥ 2 nghề share ≥ 0,2
niche   = nghề có ≥ 2 cụm mà nghề đó chiếm ≥ 0,5; hoặc cụm < 5% số tin có ≥ 3 tool lift ≥ 5
mismatch(tin) = majority share cụm ≥ 0,6 & family(tin) ≠ majority & dist ≤ Q25 của cụm & share family(tin) trong cụm < 0,1
without_e5: chạy lại với block_weights {tool: 0,7, concept: 0,3} (cùng tỷ lệ) chỉ để báo cáo
```

## 4. Ràng buộc

- `job_family` không vào vector.
- Không gian SVD cũng là không gian đo Silhouette, DB.
- k vẫn là 10. Quét k chỉ để báo cáo; không tự đổi k.
- Ngưỡng 3.2 là đề xuất đã duyệt. Kết quả lạ (ví dụ > 20% tin "gán sai") thì báo, không tự chỉnh.
- Tên cụm tự sinh chỉ là gợi ý; tên dùng trong báo cáo do người dùng đặt sau khi đọc hồ sơ.

## 5. Ví dụ (thành test)

| Đầu vào (dựng tay) | Kết quả mong đợi |
|---|---|
| 3 tin: tool 0 / concept 0; tool 0 / concept 2; tool 3 / concept 0 | tin 1 `in_clustering` false, `cluster_id` -1; hai tin còn lại có cụm |
| Khối concept toàn 0 ở một dòng | vector dòng vẫn có norm 1 (từ tool và e5) |
| Trọng số 0,35 / 0,15 / 0,5, mỗi khối đã L2 | tổng bình phương phần tool = 0,35 (± 1e-6) trên dòng đủ ba khối |
| npz chỉ có `all` | lỗi (đã kiểm ở M0) |
| Cụm 60 tin: Web 30, Data/AI 20, Other 10 | `hybrid` (0,5 < 0,6; hai nghề ≥ 0,2) |
| Cụm 50 tin Web 45, Tester 2 (tin Tester gần tâm) | 2 tin Tester `family_mismatch` true |
| Dữ liệu cụm cài sẵn, 5 seed | ARI trung bình ≥ 0,9 |
| Cụm có median `n_tools` 0 | vào `skill_count_violations` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_mining_clustering.py -q` | Xanh |
| Dry-run | `python -m mining.run_mining_pipeline --only cluster --dry-run` | Gửi: 14 tin bị bỏ, quét k, Silhouette, DB, ARI 5 seed, bảng hồ sơ 10 cụm, bảng chéo, số hybrid / niche / gán sai |
| Ổn định | ARI 5 seed | ≥ 0,8 |
| Cụm nhỏ nhất | ≥ 1% số tin | Đạt |
| Không tách theo số kỹ năng | `skill_count_violations` rỗng | Đạt |
| Kiểm tay | 20 tin `family_mismatch` (seed 42) | Ghi tỷ lệ đúng |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 20/11 | "approved"; M3.1b bỏ 14 tin | 1036a11 |
| 2 | Duyệt prompt | chưa | | |
| 3 | Test rồi code | chưa | | |
| 4 | Dry-run | chưa | Trước khi sửa: Silhouette 0,165, DB 2,26, ARI với nghề 0,057, cụm 2 = 1.240 tin | |
| 5 | Review, chạy thật | chưa | | |
