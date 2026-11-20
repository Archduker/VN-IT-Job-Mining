# M2: Gói kỹ năng cho SD2 (FP-Growth)

> Code: `mining/association.py` (`mine_rules`, `mine_stratified_rules`, `format_rules`, `find_skill`, `pair_stats`; mlxtend FP-Growth). Hàm mới đề xuất: `top_skills_by_family`, `rare_skills`, `support_stability`.
> Lệnh: `python -m mining.run_mining_pipeline --only fp [--dry-run]`.
> Câu hỏi: [`docs/target/02_sd2_goi_ky_nang.md`](../../target/02_sd2_goi_ky_nang.md). Trạng thái: **đã duyệt 20/11 (người dùng: "approved").**

## 1. Mục đích

- 2.1 top 15 kỹ năng theo nghề, **ba bảng riêng**: K-tool, K-concept, K-soft;
- 2.2 gói kỹ năng (luật A, B ⇒ C);
- 2.3 khác biệt gói giữa nghề và giữa nhóm cấp;
- 2.4 kỹ năng hiếm.

Luật theo nghề × người mới là đầu vào thứ tự học của M6.

## 2. Luật

### 2.1. Đang chạy (code hiện tại, dry-run 20/11)

| Mã | Luật | Số 20/11 |
|---|---|---|
| M2.1 | Giỏ = các cột `skill__*` (K-tool) của tin, bỏ `skill__other_skill`; tin có giỏ rỗng bị bỏ | 672 tin giỏ rỗng (643 tin `n_tools = 0` + 29 tin chỉ có công cụ hiếm đã gom); 3.244 giỏ |
| M2.2 | `AssociationParams`: `macro_min_support` 0,05 (ALL), `micro_min_support` 0,02 (theo nghề), `min_confidence` 0,60, `min_lift` 1,20, `max_len` 3, `min_group_size` 100 | — |
| M2.3 | Phân tầng chỉ theo `job_family` | 15.565 luật: ALL 15; Web 700 (1.335 giỏ), DevOps/Cloud 6.813 (230), Security 5.846 (188), Data/AI 1.000 (340), Tester 880 (291), Other 177 (406), Bridge 134 (344). Design (52), Game (29), Mobile (23), IoT (6) < 100 giỏ, `skipped` |
| M2.4 | Không có bảng top 15, không có kỹ năng hiếm, không có kiểm ổn định | — |

Nhận xét trên số 20/11: luật lift cao nhất đều ở Security / DevOps với ít giỏ (ví dụ `{ceph, cisco} ⇒ {kvm}`, support 0,021 = 4 tin, lift 47). Support 2% của nhóm 188 giỏ chỉ là 4 tin, nên số luật nổ lên ở nhóm nhỏ.

### 2.2. Đề xuất, đã duyệt 20/11 (chưa có code)

| Mã | Đề xuất | Lý do |
|---|---|---|
| M2.1 | Giữ giỏ = K-tool (M0.3). Ghi `n_jobs_without_tool` và phân theo nghề | Quyết định 1 (19/11): gói kỹ năng là công cụ |
| M2.2a | **Support tối thiểu theo số tin**: mỗi phạm vi dùng `max(micro_min_support, 10 / n_giỏ)` (đề xuất: ít nhất 10 tin) | Tránh luật dựa trên 4 tin ở nhóm nhỏ |
| M2.2b | Giữ `min_confidence` 0,60, `min_lift` 1,20, `max_len` 3, `min_group_size` 100 | Đã dùng ở SD5 (luật mạnh) |
| 2.1 | `top_skills_by_family`: với mỗi nghề, tỷ lệ tin có kỹ năng k trong tin của nghề, top 15, **ba bảng** (tool, concept, soft) từ `job_skills` + `skill_view`. Thêm phạm vi ALL. Nghề < 30 tin ghi "ít dữ liệu" | Quyết định 2 (17/11), spec 07 mục 4 |
| 2.3 | `mine_stratified_rules` thêm phân tầng **nghề × nhóm cấp** (người mới / Middle+), áp `min_group_size` 100. So từng cặp: luật chỉ có ở người mới, chỉ ở Middle+, ở cả hai | SD2 câu 2.3 |
| 2.4 | `rare_skills`: K-tool có DF < 2% số giỏ **và** (nằm trong một luật lift ≥ 2 **hoặc** ≥ 60% số lần xuất hiện ở tin Senior/Lead). Mỗi kỹ năng ghi: số tin, luật mạnh nhất chứa nó, tỷ lệ tin cấp cao. Ngưỡng 2%, 2, 60% là đề xuất PRE-36 | 20/11: 217/290 cột K-tool có DF < 2%, nên điều kiện thứ hai là chính |
| M2.5 | `support_stability`: chạy lại phạm vi ALL và từng nghề với support × 0,5 và × 2 (một bậc); đo tỷ lệ trùng của top 20 luật (xếp theo lift, rồi confidence) so với ngưỡng gốc | Spec 08: luật mạnh không đổi lớn khi đổi support |
| M2.6 | Xuất `sd2_hand_check.csv`: 20 luật mạnh nhất (top lift trong luật có support ≥ ngưỡng M2.2a), có cột `dung`/`ghi_chu` để người dùng điền. Đã điền thì không ghi đè | Spec 08: kiểm tay 20 luật |

## 3. Quy trình xử lý

1. Lấy ma trận `skills` (K-tool) từ M0; bỏ giỏ rỗng, ghi số tin bị bỏ theo nghề.
2. `top_skills_by_family` cho ba view (từ `job_skills`, không cần giỏ).
3. `mine_rules` phạm vi ALL (support 0,05).
4. `mine_stratified_rules` theo nghề, rồi theo nghề × nhóm cấp, support theo M2.2a.
5. `rare_skills` dùng luật của bước 3–4 và cột `seniority`.
6. `support_stability` (×0,5, ×2).
7. Sanity S-01, S-02 (info), S-03 trên ma trận K-tool (M0.7).
8. Ghi artifact (bỏ qua nếu dry-run).

## 4. Input → Output

| Input | Dùng |
|---|---|
| `MiningData.skills` (K-tool), `meta.job_family`, `meta.seniority` | luật, kỹ năng hiếm |
| `job_skills.parquet` + `skill_view` | 2.1 (ba bảng) |

| Output | Nội dung |
|---|---|
| `skill_association_rules.parquet` | `scope` (ALL / nghề / nghề × nhóm cấp), `antecedents`, `consequents`, support, confidence, lift, conviction, cosine, `n_support` (số tin) |
| `sd2_top_skills.json` | 2.1: theo nghề → `tool`, `concept`, `soft`, mỗi mục (kỹ năng, n, tỷ lệ) |
| `sd2_rare_skills.json` | 2.4 |
| `sd2_hand_check.csv` | 20 luật để kiểm tay |
| `mining_metrics.json` khối `association` | số luật theo phạm vi, `n_jobs_without_tool`, độ ổn định, tham số |

## 5. Dữ liệu mẫu

Điền sau lần chạy thật.

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Mọi luật báo cáo có lift ≥ 1,20, confidence ≥ 0,60, `n_support` ≥ 10 tin | bắt buộc (M2.2a) |
| S-01 Spring Boot ⇒ Java | conf ≥ 0,85, lift ≥ 1,5 (20/11: 0,961, pass) |
| S-03 React ⇒ JS/TS | ≥ 0,60 (đề xuất M0.7b; 20/11: 0,671) |
| S-02 Flutter ⇒ Dart | chỉ báo cáo (đề xuất M0.7a; 20/11: 0,394) |
| Độ ổn định top 20 luật khi support ×0,5 / ×2 | trùng ≥ 70% (đề xuất PRE-36) |
| Kiểm tay 20 luật | ≥ 16/20 hợp lý (đề xuất) |
| Bảng 2.1 không có kỹ năng mềm trong bảng tool và ngược lại | test |
| `pytest tests/unit/test_mining_association.py` | xanh |

**Dry-run 20/11** (`run_association` trên Silver + features + job_skills, cùng sha256 như M0; 43 giây):

| Mục | Kết quả |
|---|---|
| Giỏ | 3.244 giỏ; 672 tin không có công cụ (Web 201, Bridge 135, Other 120, Tester 91, Data/AI 48, Security 43…) |
| Luật | 8.650 (trước M2.2a: 15.565). ALL 15; Web 700, DevOps/Cloud 2.643, Data/AI 505, Security 307, Tester 286, Other 133, Bridge 77; Design, Game, IoT, Mobile < 100 giỏ |
| Nghề × nhóm cấp | Chỉ **Web người mới** (427 giỏ, 339 luật) và Other người mới (133, 3 luật) đủ 100 giỏ. Bridge 70, Data/AI 82, Tester 87, Security 55, DevOps/Cloud 44 giỏ người mới: `skipped`. Middle+ đủ ở 7 nghề. So Web: 171 luật chỉ ở người mới, 911 chỉ ở Middle+, 168 chung |
| Kỹ năng hiếm (2.4) | 87 / 201 công cụ có DF < 2% (ví dụ k6, wireshark, nessus, prtg, katalon, way4) |
| Ổn định (M2.5) | support × 0,5: trùng top 20 trung bình 0,75 (nhỏ nhất 0); × 2: 0,31 (nhỏ nhất 0). **Không đạt 0,70 ở × 2** |
| S-01 / S-02 / S-03 | như M0: 0,961 pass / 0,394 info / 0,671 pass |
| Kiểm tay | 20 luật trong `sd2_hand_check.csv`; chưa điền |

Nhận xét: top 20 xếp theo lift nghiêng về luật support thấp (lift cao nhất ở cặp hiếm), nên khi tăng support thì phần lớn top 20 biến mất. Luật đối xứng (A ⇒ B và B ⇒ A) chiếm hai chỗ trong mẫu kiểm tay.

## 7. Trạng thái, chỗ thiếu, việc mở

- **Có code đủ 2.1–2.4, M2.5, M2.6 từ 20/11.** Chờ người dùng xem: ổn định × 2 = 0,31 (< 0,70); 5/6 nghề lớn không đủ 100 giỏ người mới (M6 sẽ lùi về luật của cả nghề); kiểm tay 20 luật.
- Đi khác prompt: phạm vi nghề × nhóm cấp ghi bằng hai cột `job_family_scope` (nghề) + `level_group` (all / newcomer / middle_plus), không gộp `Web|newcomer`, để Mart vẫn lọc theo nghề.
- Đã duyệt 20/11: M2.2a (10 tin), ngưỡng ổn định 70%, 16/20.
- MINE-1 (S-02, S-03), PRE-36 (ngưỡng kỹ năng hiếm).
