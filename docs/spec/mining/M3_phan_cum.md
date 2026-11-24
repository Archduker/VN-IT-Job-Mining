# M3: Nhóm việc cho SD3 (câu 3.1, 3.2)

> Code: `mining/clustering.py` (`build_vector_space`, `reduce_svd`, `scan_k`, `choose_k`, `fit_labels`, `run_hdbscan`, `profile_clusters`, `cluster_jobs`). Hàm mới đề xuất: `seed_stability`, `family_crosstab`, `flag_family_mismatch`.
> Lệnh: `python -m mining.run_mining_pipeline --only cluster [--dry-run]`.
> Câu hỏi: [`docs/target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md`](../../target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md). Trạng thái: **đã duyệt 20/11 (người dùng: "approved").**

> **Thay đổi 24–25/11/2026 (L-62):** cách chạy hiện hành là `cluster_by_group`, không còn là `cluster_jobs` (k = 10) mô tả ở mục 2.1, 2.2, 5, 7.
> - **Nhóm:** mỗi tin vào 1 trong 7 nhóm nghề (`mining/job_group.py`) hoặc nhóm Khác.
> - **Cụm con:** K-Means riêng mỗi nhóm, k = số vai trò con liệt kê, trên công cụ + khái niệm (0,5 / 0,5, **không e5**), chỉ tin có ≥ 2 công cụ.
> - **Tin ít công cụ:** vào mục "Khác (JD ít thông tin)" của nhóm.
> - **Nhóm Khác:** xét bằng luật chốt nghề mới (`classify_other`).
>
> Xem mục 8.

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

### 2.2. Đề xuất, đã duyệt 20/11 (code xong 20/11; chỉnh sau review ở cuối bảng)

| Mã | Đề xuất | Lý do |
|---|---|---|
| M3.1a | **Vector = `skill__` (K-tool) + `concept__` (K-concept) + e5 `job`.** Bỏ ba cột `__other_skill`. Mỗi khối chuẩn hóa L2 theo dòng rồi nhân √trọng số. Trọng số duyệt ban đầu 0,35 / 0,15 / 0,5; **sau review 20/11 (1.D) đổi thành 0,15 / 0,15 / 0,7** (tool / concept / e5) | Người dùng chốt 19/11 (thay quyết định 3 ngày 17/11). Concept giúp 643 tin không có công cụ (BA, Tester, IT Manager, presales; trung vị 8 khái niệm/tin) có vị trí đúng; e5 `job` không có phúc lợi |
| M3.1b | **Tập tin:** giữ tin có `n_tools + n_concepts ≥ 1`. 20/11 bỏ **14 tin**. Ghi `n_dropped_no_technical_skill` | Kế hoạch ghi "bỏ 1 tin" là số tin không có kỹ năng nào (`n_skills = 0`); theo đúng định nghĩa "kỹ năng kỹ thuật" (tool + concept) là 14 tin. **Người dùng duyệt 20/11: bỏ 14 tin** |
| M3.1c | Gỡ TF-IDF (M0.6) | Quyết định 1 |
| M3.2 | Giữ SVD ~80%, tối đa 60; báo phương sai giải thích | — |
| M3.3 | Giữ k = 10 (đã chốt 11/11) và quét 2–20 để báo cáo. Nếu duyệt đổi k thì ghi ở đây | — |
| M3.7 | `seed_stability`: chạy K-Means với 5 seed (42, 43, 44, 45, 46) trên cùng không gian; ARI từng cặp với seed 42; báo trung bình và nhỏ nhất | Spec 08: ARI ≥ 0,8 (chốt 22/11, L-60) |
| M3.8 | Hồ sơ cụm thêm: trung vị `n_tools`, `n_concepts`; top 5 tiêu đề (`title`); phân bố cấp; trung vị `salary_target_m` (n ≥ 30, M1.0b). **Kiểm "không tách theo số kỹ năng"**: không cụm nào có trung vị `n_tools` < 1 hoặc > 2 × trung vị toàn bộ (đề xuất) | SD3 mục 6, L-47 |
| M3.8b | **22/11 (L-60):** tên cụm = `<tiền tố> · <2 công cụ lift cao nhất>`; tiền tố "Ít công cụ" khi trung vị `n_tools` ≤ 1, "Hỗn hợp" khi nghề đa số < 40% cụm, còn lại là tên nghề đa số (`name_few_tools_median`, `name_min_purity`) | Tên cũ luôn lấy nghề đa số nên cụm 24% Web vẫn tên "Web" |
| M3.9 | Artifact `cluster_family_crosstab.json`: bảng chéo cụm × `job_family` (số tin và tỷ lệ theo hàng) | SD3 câu 3.2 |
| M3.10 | Luật 3.2 (ngưỡng đề xuất): **nghề lai** = cụm không có nghề nào > 60% và có ≥ 2 nghề ≥ 20%; **nghề ngách** = một nghề có ≥ 2 cụm mà nghề đó chiếm ≥ 50% cụm, hoặc cụm nhỏ (< 5% số tin) có ≥ 3 công cụ lift ≥ 5; **có vẻ gán sai** = tin có `job_family` ≠ nghề đa số của cụm (nghề đa số chiếm ≥ 60%), khoảng cách tới tâm cụm ≤ P25 của cụm, và nghề của tin chiếm < 10% cụm | SD3 câu 3.2; trước đây chỉ có bảng hồ sơ, không có luật |
| M3.11 | `job_clusters.parquet` thêm cột `in_clustering` (false cho tin bị bỏ ở M3.1b), `family_mismatch` (M3.10), `dist_to_centroid` | M4 dùng GLOSH; Monitoring vẽ |
| M3.1a' | **Quyết định 1.D (20/11, sau dry-run):** trọng số 0,15 / 0,15 / 0,7 | Bộ 0,35 / 0,15 / 0,5 gom 928 tin (24%) có trung vị 0 công cụ vào một cụm (vi phạm M3.8). Đo 4 bộ: 0,25/0,25/0,5 (NMI 0,292, vi phạm 3 cụm), 0,2/0,2/0,6 (vi phạm 1 cụm), 0,15/0,15/0,7 (không vi phạm, cụm lớn nhất 19,2%) |
| M3.7' | **Quyết định 2.B (20/11):** K-Means `n_init` 50 cho lần fit chính và 5 seed (quét k giữ `n_init` 10, chỉ để báo cáo) | `n_init` 10: ARI 5 seed 0,73; `n_init` 50: 0,826 (k = 10, giữ k đã chốt). Đã đo thêm: k = 8 với SVD 30 chiều cho ARI 0,925, không đổi vì k = 10 đã chốt. **22/11 (L-59, 3.718 tin):** `n_init` 50 chỉ còn 0,791 nên nâng lên 150: ARI 0,826 (min 0,779) |
| M3.8' | **Quyết định 3.B (20/11):** chỉ kiểm phía dưới (trung vị `n_tools` < 1); `skill_count_ratio_max` = None | Phía trên (> 2 × 5) gắn cờ nhầm cụm Backend (12) và DevOps (11) thật |

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

Chạy thật 20/11 (`--only bi,fp,cluster`; sha256 đầu vào như M0). 3.902 tin vào phân cụm, 14 tin bị bỏ (ví dụ "Nhân Viên Lập Trình CNC", "NHÂN VIÊN QC - NHÀ MÁY NHÔM", 3 tin "Phòng Dữ Liệu - Tiếng Nhật N2").

| Cụm | Tên (nghề đa số · 2 công cụ lift cao) | Số tin | Độ thuần | Trung vị `n_tools` / `n_concepts` | Nội dung |
|---|---|---|---|---|---|
| 0 | Web · aws/git | 707 | 0,45 | 6 / 18 | Kỹ sư phần mềm chung (Data Engineer, AI Engineer, QA Engineer) |
| 1 | Web · sql/aws | 296 | 0,41 | 5 / 15 | Hỗn hợp (Tester, vận hành, Software Engineer) |
| 2 | Web · spring_boot/redis | 536 | 0,80 | 10 / 14 | Backend, Fullstack |
| 3 | Web · figma/ios | 810 | 0,25 | 1 / 8 | Tin ít công cụ: Game Designer, Product Owner, CNC |
| 4 | Web · windows/vmware | 394 | 0,62 | 3 / 15 | IT Support, Helpdesk, hệ thống |
| 5 | Data/AI · tableau/power_bi | 335 | 0,46 | 4 / 15 | Data Analyst, BI |
| 6 | DevOps/Cloud · argocd/helm | 215 | 0,70 | 14 / 24 | DevOps, SRE |
| 7 | Web · pytorch/tensorflow | 190 | 0,54 | 8 / 18 | AI Engineer (Web 103, Data/AI 63) |
| 8 | Tester · ms_word/powerpoint | 190 | 0,26 | 2 / 6 | Văn phòng, QC, PM |
| 9 | Bridge · confluence/jira | 229 | 0,48 | 5 / 17 | BA, PO, Scrum, Manual Tester lead |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Ổn định: ARI trung bình 5 seed | ≥ 0,8 (chốt 22/11) |
| Cụm nhỏ nhất | ≥ 1% số tin (chốt 22/11) |
| Không tách theo số kỹ năng (M3.8) | không cụm nào có trung vị `n_tools` < 1 (3.B) |
| Silhouette, DB | chỉ báo cáo (chốt 22/11, L-60: quét k 2–20 đều 0,075–0,10) |
| Kiểm tay tin "có vẻ gán sai" | ghi tỷ lệ đúng; không dùng để sửa nhãn. 21/11 người dùng chấm 3/10; 22/11: 6/13 là IT Manager (luật → Bridge, cụm → hạ tầng) |
| Đọc tên cụm: mỗi cụm có top công cụ, top khái niệm, top tiêu đề | bắt buộc |
| `pytest tests/unit/test_mining_clustering.py` (sửa theo ba khối, khóa `job`) | xanh |

## 7. Trạng thái, chỗ thiếu, việc mở

- **Chạy thật 20/11** với 1.D, 2.B, 3.B: k = 10, Silhouette 0,084, DB 2,49 (chỉ báo cáo, không đạt mục tiêu cũ 0,25 / < 1,5). **ARI 5 seed trung bình 0,826, nhỏ nhất 0,779 (đạt ≥ 0,8)**; cụm nhỏ nhất 4,9% (đạt); không cụm vi phạm M3.8 (đạt). Không e5 (0,15 / 0,15): Silhouette 0,089, NMI với nghề 0,344; có e5: NMI 0,218. HDBSCAN: 3 cụm, 82% nhiễu; GLOSH ngưỡng P97 = 0,492.
- 3.2: nghề lai cụm 3, 7, 8, 9; Web bị tách ở cụm 2, 4, 7; cụm nhỏ chuyên biệt 7 (AI), 8; **8 tin "có vẻ gán sai"** (4 IT Manager / Trưởng phòng CNTT mang Bridge nằm ở cụm IT hệ thống; 2 Solution Architect mang DevOps/Cloud ở cụm Backend; 1 SRE mang Web ở cụm DevOps; 1 AI Full Stack). Mẫu kiểm tay `mining/artifacts/sd3_mismatch_hand_check.csv` chỉ có 8 dòng (ít hơn 20). **Kiểm tay còn mở.**
- Còn yếu: cụm 3 (810 tin, trung vị 1 công cụ, độ thuần 0,25) vẫn gom tin ít công cụ; qua luật 3.B vì trung vị = 1. Cụm 7 là AI Engineer nhưng 103/190 tin mang `job_family` Web: luật nghề xếp AI Engineer vào Web (PRE-44).
- Tên cột `job_clusters.parquet` giữ `is_outlier`, `glosh_outlier_score` (tên Mart) thay `glosh_outlier`, `glosh_score` của mục 4.
- Đóng 22/11 (L-60): Silhouette chỉ báo cáo; tên cụm theo M3.8b. Kết quả cuối: spec 08 mục 3.3.

## 8. Bản 24–25/11: 7 nhóm nghề, cụm con, nhóm Khác (L-62)

| Bước | Luật | Code |
|---|---|---|
| Gán nhóm | 7 nhóm từ `job_family` + luật tiêu đề (DBA → Hạ tầng, IT Manager → Product & Business, ERP/Solution Architect/helpdesk → Support; Infra/Support chung chung theo công cụ máy chủ/mạng). Còn lại: Khác | `job_group.add_job_group` |
| Không gian | Khối công cụ + khái niệm, trọng số 0,5 / 0,5; e5 trọng số 0 (gom theo ngôn ngữ JD); SVD 60 chiều | `ClusteringParams.group_block_weights` |
| Tập tin | `n_tools` ≥ 2 (`group_min_tools`); tin ít công cụ ở mục "Khác (JD ít thông tin)" của nhóm | `cluster_by_group` |
| k | Số vai trò con trong `SUB_ROLES`, hạ nếu trung bình < 30 tin/cụm | `group_min_per_cluster` |
| Tên cụm | Vai trò con nếu ≥ 30% tin của cụm khớp tiêu đề; trùng tên thì thêm 2 công cụ lift cao nhất; không khớp thì ghi theo công cụ | `subrole_min_share` |
| Nhóm Khác | Luật chốt nghề mới: không chung chung, chưa có trong danh sách, ≥ 3 tin / ≥ 2 công ty (toàn bộ dữ liệu), ≥ 50% tin xa mọi cụm (> P90 khoảng cách tin–tâm), ≥ 2 công cụ riêng → nghề mới; tin trải ≥ 2 nhóm → nghề lai; còn lại tên gọi khác hoặc theo dõi | `classify_other` |

**Nghiệm thu (25/11):**

| Kiểm tra | Ngưỡng | Kết quả |
|---|---|---|
| ARI 5 seed theo nhóm | ≥ 0,8 | trung bình 0,97, thấp nhất 0,89 (Security) |
| Cụm nhỏ nhất | ≥ 1% số tin **của nhóm** (đổi 25/11 sau khi xem kết quả) | 7,4% |
| Không gom theo số công cụ | không cụm nào trung vị `n_tools` < 1 | đạt |
| Không gom theo ngôn ngữ JD | 0 cụm ≥ 90% JD tiếng Anh | đạt |
| Mỗi tin đều có chỗ | cụm con + mục Khác của nhóm + nhóm Khác = 3.718 | 2.620 + 744 + 354 |
| Silhouette | chỉ báo cáo | 0,07 |

**Đầu ra mới:**
- `job_clusters.parquet` thêm cột `job_group`, `job_group_source`, `sub_role_title`, `sub_role`, `title_core`, `other_status`, `nearest_cluster`.
- Metrics: `clustering.by_group`, `coverage`, `other`.
- File `sd3_other_roles.json`.
