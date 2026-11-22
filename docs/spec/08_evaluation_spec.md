# ĐẶC TẢ ĐÁNH GIÁ VÀ NGHIỆM THU

> **Dự án:** VN-IT-Job-Mining. Đề tài: "Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT".
> **Phiên bản:** 3.0.0, ngày 17/11/2026. **Trạng thái:** đã duyệt 17/11/2026 (chặng 4); mục 3, 4 cập nhật kết quả và chốt ngưỡng 22/11/2026.
> **Thay cho:** bản 2.0. Bản đó có "Skill Gap Matrix", chỉ số thâm hụt kỹ năng so với chương trình đại học, tỷ lệ qua bộ lọc CV giả lập, và coi model lương là "phần phụ, trọng số 0%".
> **Quan hệ với tài liệu khác:** tiêu chí "cách biết đã trả lời đúng" của từng SD nằm ở mục 6 của mỗi file trong [`docs/target/`](../target/00_de_tai.md). Spec này gom các tiêu chí đó lại, ghi cách đo bằng code nào, và hiện trạng. Bước được đo: [spec 05](05_preprocessing_spec.md), [06](06_processing_spec.md), [07](07_mining_spec.md).

## 0. Cách đọc

- **Ngưỡng:** chốt 22/11/2026 (L-60, đóng PRE-36): ngưỡng ở mục 3 là chính thức; mục nào ghi "chỉ báo cáo" thì không là cổng. Ngưỡng nào đã có trong code (`mining/config.py`) thì ghi rõ "trong code".
- **Hiện trạng:** mục 2 lấy từ lần chạy 10–11/11/2026 (4.671 tin); mục 3 và 4 lấy từ lần chạy thật 22/11/2026 (3.718 tin).
- Mỗi tiêu chí có một trong ba trạng thái: **Đạt**, **Chưa đạt** (đã đo, không qua), **Chưa đo** (chưa có code hoặc chưa chạy).

## 1. Nguyên tắc chung

1. **Số thật.** Mọi số dùng để nghiệm thu đến từ dữ liệu thật. Kết quả của `mining/synthetic.py` (`--synthetic`) chỉ dùng để test code, không bao giờ dùng để nghiệm thu (L-19).
2. **Dữ liệu sạch là điều kiện trước.** Một SD chỉ được nghiệm thu khi các cột nó dùng đã đạt tiêu chí sạch của PRE-35. Trước đó, kết quả chỉ là bản chạy thử.
3. **Tái lập.** Mỗi kết quả ghi kèm ngày chạy, `code_version`, sha256 của file đầu vào (`mining_metrics.json`) và `random_state` (42). Chạy lại phải ra cùng số.
4. **Ít dữ liệu.** Ô bảng có n < 30 ghi "ít dữ liệu", không ghi số.
5. **Không nói quá dữ liệu.** Dữ liệu chỉ có tin tuyển dụng, nên không kết luận về ứng viên, chương trình đào tạo, quan hệ nhân quả hay xu hướng theo thời gian (`docs/target/00_de_tai.md`).
6. **Kiểm tay có ghi lại.** Mỗi lần kiểm tay ghi mẫu (seed, danh sách `job_id`), người kiểm và kết quả, để người khác kiểm lại được.

## 2. Chất lượng dữ liệu đầu vào (Pre-processing, Processing)

Các tiêu chí này lấy từ thiết kế 13 bước cũ, nay ghi ở spec 05 và 06. Chúng là điều kiện của nguyên tắc 2.

| Bước | Tiêu chí | Cách đo | Ngưỡng | Hiện trạng |
|---|---|---|---|---|
| Mọi bước | Bảo toàn bản ghi: vào = ra + bỏ | `checks.rows_conserved` trong report | Bắt buộc | Đạt |
| 01 lọc IT | Độ đúng của luật IT trên nhãn tay | `extra.review` của report 01; `data/preprocessing/review/it_<nguồn>.csv` | ≥ 95%, kèm khoảng tin cậy (điều kiện cận dưới chưa chốt, PRE-12) | Chưa đạt: 92,4% trên 643 nhãn |
| 01 lọc IT | Kiểm tay 100 tin bị loại | Mẫu seed cố định | Loại nhầm < 5% | Chưa đo |
| 01b khử trùng | Precision trên 50 cặp gần ngưỡng | `scripts/build_dedup_pairs_sample.py` | ≥ 95% | Người dùng duyệt "ổn" 11/11, chưa chấm từng cặp |
| 03 làm sạch ký tự | Còn HTML, NFD, ký tự ẩn | `extra.text_quality` của report 03 | 0% | Đạt |
| 03 parser | Lương, kinh nghiệm, ngày, địa điểm, mỗi loại 50 chuỗi thật | Bộ gold hoặc mẫu tay | ≥ 95% mỗi parser | Chưa đo |
| 03 dịch | Kiểm tay 50 JD đã dịch | `scripts/build_translation_review_sample.py` | Không đổi kỹ năng, không đổi số liệu | Chưa đo; đã biết 222/1.274 tin `failed` và lỗi rơi dấu "+" (PRE-34) |
| 04 nhóm nghề | 50 tin gán tay (seed 42) | Mẫu tay | ≥ 90% | Chưa đo |
| 07 section | Độ đúng theo bullet trên bộ gold | `scripts/eval_gold_processing.py` | ≥ 90% | Chưa đạt: 84,5% |
| 08 kỹ năng | F1 micro trên bộ gold, `via = text` | `scripts/eval_gold_processing.py` | ≥ 0,85 | Chưa đạt: 0,27 (cách đo cần xem lại, PRE-33) |

## 3. Nghiệm thu theo SD

> **Chốt 22/11/2026 (L-60, đóng PRE-36):** người dùng giao Claude quyết. Các ngưỡng đề xuất trước đây thành ngưỡng chính thức, trừ hai chỉ số đổi thành "chỉ báo cáo": Silhouette/Davies–Bouldin (SD3) và R²/MAE tuyệt đối (SD4). Cột "Kết quả 22/11" lấy từ lần chạy thật 22/11 trên bảng 3.718 tin (Silver sha256_16 `60ac8d8b672d45eb`, `mining/artifacts/mining_metrics.json`). Kiểm tay do Claude làm 22/11, trừ mục ghi "người dùng".

### 3.1. SD1: Bức tranh thị trường (M1)

| Tiêu chí | Cách đo | Ngưỡng | Kết quả 22/11 |
|---|---|---|---|
| Mọi bảng có n và độ phủ; tổng khớp số tin bảng 04; tỷ lệ cộng đủ 100% | `mining/bi.py`, test `test_mining_bi` | Bắt buộc | **Đạt**: 23 bảng, `totals_ok` |
| Ô n < 30 ghi "ít dữ liệu" | Test | Bắt buộc | **Đạt**: 78 ô |
| Câu 1.2 tách cấp bậc gốc và cấp bậc suy ra | Đọc bảng `sd1_1_2.json` | Bắt buộc | **Đạt** |
| Câu 1.7 chỉ so cơ cấu; so tháng 9 chỉ trên nguồn ghi ngày đăng | Đọc bảng `sd1_1_7.json` | Bắt buộc | **Đạt** |
| Lương ước tính từ M5 không trộn với lương công khai | Cột riêng có nhãn "ước tính" | Bắt buộc | **Đạt** (`salary_estimates.parquet` riêng) |
| S-04, S-06 (mục 4) | `mining/sanity.py` | Pass, hoặc có giải thích | **Đạt**: S-04 10,0 < 15,5 < 22,5 < 37,5; S-06 HN 1,53, HCM 1,27 |

### 3.2. SD2: Gói kỹ năng (M2)

| Tiêu chí | Cách đo | Ngưỡng | Kết quả 22/11 |
|---|---|---|---|
| Mọi luật đủ support của phạm vi và lift ≥ 1,20 | Lọc trong `mine_rules` | support 0,05 (toàn bộ), 0,02 (nghề); confidence 0,60; lift 1,20 | **Đạt**: 12.642 luật (7.688 tập mục khác nhau) |
| Cặp hiển nhiên S-01, S-03 (S-02 chỉ báo cáo) | `mining/sanity.py` | Pass | **Đạt**: S-01 0,961; S-03 0,667; S-02 0,394 (báo cáo) |
| Kiểm tay 20 luật mạnh nhất | Đọc `sd2_hand_check.csv` | Không có luật vô nghĩa; có thì tìm nguyên nhân | **Đạt**: 20 luật là 4 tập mục (grafana–prometheus, postman–swagger–sql, cursor–claude_code, cpp–flask–django), đều đúng thực tế tuyển dụng; tập cuối là JD AI liệt kê nhiều framework. Kiểm thêm: không luật nào do một công ty đăng lặp (mẫu 800 luật, seed 42: mỗi luật ≥ 5 công ty, chỉ 0,1% luật có một công ty > 50% số tin) |
| Ổn định khi đổi support một bậc | Chạy lại với support × 0,5 và × 2 | Top luật trùng ≥ 80% | **Đạt**: × 0,5 trùng 98%; × 2 trùng 89% |
| Kỹ năng hiếm | `sd2_rare_skills.json` | < 2% số tin, và lift ≥ 2 hoặc ≥ 60% ở Senior/Lead | **Đạt**: 124 kỹ năng |

### 3.3. SD3: Nhóm việc và tin khác hoặc mới (M3, M4)

| Tiêu chí | Cách đo | Ngưỡng | Kết quả 22/11 |
|---|---|---|---|
| Độ ổn định | ARI giữa 5 lần chạy với 5 seed | ≥ 0,8 | **Đạt**: 0,826 (min 0,779), `n_init` 150 |
| Kích thước nhóm | Cụm nhỏ nhất / số tin | ≥ 1% | **Đạt**: 4,26% |
| Không tách theo số kỹ năng | Trung vị `n_tools` theo cụm | Không cụm nào trung vị 0 công cụ | **Đạt**. Cụm "Ít công cụ" (trung vị 1) được đặt tên riêng (M3.8b) |
| Độ tách nhóm | Silhouette, Davies–Bouldin trên SVD 60 chiều | **Chỉ báo cáo** (chốt 22/11): quét k 2–20 đều cho Silhouette 0,075–0,10, nên không ngưỡng nào phân biệt được k tốt hay xấu | Silhouette 0,075; DB 2,80 (k = 10) |
| Mức khớp với `job_family` | ARI, NMI trên tin khác Other | Báo cáo | ARI 0,209; NMI 0,316 (bỏ e5: 0,423 / 0,468) |
| Tin "có vẻ gán sai nghề" | Kiểm tay `sd3_mismatch_hand_check.csv` | Báo cáo | Người dùng chấm 3/10 đúng (21/11). 22/11: 13 tin, 6 là "IT Manager / Trưởng phòng CNTT" (luật N3e → Bridge, cụm → hạ tầng). Không dùng danh sách này để sửa nhãn |
| Tin khác hoặc mới | Kiểm tay 20 tin `sd3_anomaly_hand_check.csv` (seed 42) | Ghi tỷ lệ tin đúng là khác hoặc mới thật | 233 tin (6,27%). "khác" 8/8, "chưa rõ" 2/3, "mới" 2/9 (đa số là JD sơ sài). Kết luận: dùng "khác" để báo cáo; không kết luận có nghề mới |

### 3.4. SD4: Giá trị kỹ năng (M5)

| Tiêu chí | Cách đo | Ngưỡng | Kết quả 22/11 |
|---|---|---|---|
| Không rò rỉ | `assert_no_leakage`; các tin cùng `company_id` cùng một phía | Bắt buộc | **Đạt**: 869 công ty, 0 công ty ở cả hai phía |
| Phương án A thắng baseline | MAE test so với trung vị lương cấp × nghề | Thấp hơn ≥ 10% | **Đạt**: 6,105 so với 7,332 (hơn 16,7%) |
| CV ổn định | Độ lệch chuẩn R² qua GroupKFold theo công ty | ≤ 0,05 | **Đạt**: 0,029 |
| R² và MAE tuyệt đối | R² (log), MAE | **Chỉ báo cáo** (chốt 22/11): lương công bố chỉ 44% tin và thiếu không ngẫu nhiên ở cấp cao, nên ngưỡng 0,60 / 4,5 triệu không phản ánh chất lượng so với cách đoán sẵn có | R² 0,557; MAE 6,105 |
| Phương án B | macro-F1 | Chỉ chạy khi A không đạt | Không cần |
| Chỉ định giá kỹ năng đủ dữ liệu | Số tin có kỹ năng trong tập có lương | ≥ 30 tin | **Đạt**: 77 kỹ năng được định giá |
| Sanity S-04, S-05, S-06 | `mining/sanity.py` | Pass | **Đạt** |
| Giá trị kỹ năng cùng chiều với chênh lệch thô | So dấu SHAP với chênh trung vị thô | Báo cáo | 64,9% cùng dấu; phần ngược chiều do cấp và kinh nghiệm chia điểm (F10.6) |
| Lương ước tính của tin thỏa thuận | So phân bố với tập có lương | Ghi cảnh báo nhóm lệch | **Đạt**: cảnh báo ở cấp "Không rõ" (tỷ lệ 2,43) |

Giá trị SHAP là mức liên quan, không phải quan hệ nhân quả.

### 3.5. SD5: Lộ trình học (M6)

| Tiêu chí | Cách đo | Ngưỡng | Kết quả 22/11 |
|---|---|---|---|
| Chỉ làm lộ trình cho nghề đủ dữ liệu | Số tin Intern/Fresher + Junior của nghề | ≥ 30 tin | **Đạt**: 8 nghề (Game, IoT, Mobile ghi "ít dữ liệu"; Other không làm) |
| Độ phủ hơn baseline | coverage@10 so với "top 10 toàn thị trường" | Cao hơn | **Đạt** cả 8 nghề |
| Không học tủ | Tính điểm trên 80%, đo trên 20% còn lại | Lệch ≤ 10 điểm | **Đạt 4/8** (Bridge, Data/AI, Tester, Web). Design, DevOps/Cloud, Infra/Support, Security lệch 10,1–11,6 điểm: chốt 22/11 giữ lộ trình, gắn `reliability` "tham khảo" |
| Truy được nguồn | Mỗi kỹ năng có `demand`, luật SD2, giá trị SD4 | Bắt buộc | **Đạt** |
| Đọc tay | Đọc lộ trình 2 nghề | Bước ngược lẽ thường được ghi lại | **Đạt** (Claude đọc Web, 22/11): javascript, git, sql nền; html/css, react, typescript theo gói javascript; docker trước kubernetes; graphql, github_actions, jenkins để sau. Không có bước ngược |

## 4. Sanity S-01..S-06

Code: `mining/sanity.py` (`run_sanity_checks`), kết quả ghi vào `mining_metrics.json` (`sanity_checks`, `sanity_summary`). S-01..S-03 tính thẳng từ ma trận kỹ năng, không phụ thuộc ngưỡng support của FP-Growth.

| Mã | Kiểm tra | Tiêu chí pass | SD | Kết quả 11/11 | Dry-run 20/11 (dữ liệu 19/11, code cũ) | Kết quả 22/11 (3.718 tin) |
|---|---|---|---|---|---|---|
| S-01 | {Spring Boot} ⇒ {Java} | Confidence ≥ 0,85 và lift ≥ 1,5 | SD2 | Pass | Pass (0,961) | **Pass (0,961)** |
| S-02 | {Flutter} ⇒ {Dart} | Confidence ≥ 0,90. **Đổi, duyệt 20/11 (M0.7a):** chỉ báo cáo, không là cổng (quyết định 6: không tự suy kỹ năng JD không ghi) | SD2 | Fail (0,375) | 0,394 (n 66) | **Báo cáo (0,394, n 66)** |
| S-03 | {React} ⇒ {JavaScript} hoặc {TypeScript} | Confidence ≥ 0,80. **Đổi, duyệt 20/11 (M0.7b):** ≥ 0,60 (T2) | SD2 | Fail (0,654) | 0,671 (n 313) | **Pass (0,667)** |
| S-04 | Trung vị lương tăng dần theo cấp: Fresher < Junior < Middle < Senior | Đơn điệu. Lead/Manager ghi riêng kèm tỷ lệ thỏa thuận (MNAR, đề xuất M0.8) | SD1, SD4 | Fail (Senior < Middle) | Code báo fail nhưng **ánh xạ cấp lệch một bậc** (lỗi, M0.8). Tính đúng: 10,0 < 15,5 < 22,5 < 37,5 → pass | **Pass (10,0 < 15,5 < 22,5 < 37,5; Lead 30,0, 57,7% thỏa thuận)** |
| S-05 | Giá trị SHAP của AWS, Kubernetes hoặc System Design | φ > 0 | SD4 | Chưa đo (chưa có bảng SHAP) | Bỏ qua (không chạy SHAP) | **Pass (kubernetes φ 0,021; aws 0,006)** |
| S-06 | Trung vị lương HN và HCM so với tỉnh khác (trừ Remote) | Mỗi bên > 1,2 lần | SD1, SD4 | Fail | **Fail** sau M0 (HN 1,452; HCM 1,194), vì nay bỏ 86 tin `salary_outlier`. Người dùng chốt 20/11: giữ 1,2, ghi fail (code cũ: 1,45 / 1,25 khi chưa bỏ ngoại lai) | **Pass (HN 1,53; HCM 1,27)** |

22/11: cả 6 kiểm tra đạt (S-02 chỉ báo cáo). Sanity fail không có nghĩa là thuật toán sai. Có thể do dữ liệu (rút kỹ năng sai, lương parse sai, tỉnh sai) hoặc do ngưỡng kiểm. **Phải tìm nguyên nhân trước khi dùng kết quả** (MINE-1), và ghi nguyên nhân vào báo cáo.

## 5. Định nghĩa chỉ số

| Chỉ số | Định nghĩa | Dùng ở |
|---|---|---|
| Support(A ⇒ B) | Tỷ lệ tin có cả A và B | SD2 |
| Confidence(A ⇒ B) | Support(A ∪ B) / Support(A) | SD2, SD5 |
| Lift(A ⇒ B) | Confidence(A ⇒ B) / Support(B). Lớn hơn 1 nghĩa là A thật sự kéo B theo | SD2, SD5 |
| Conviction(A ⇒ B) | (1 − Support(B)) / (1 − Confidence). Càng cao thì luật càng ít ngoại lệ | SD2 |
| Silhouette | Trung bình (b − a) / max(a, b), với a là khoảng cách trung bình trong cụm, b là khoảng cách tới cụm gần nhất. Từ −1 đến 1, càng cao càng tách bạch | SD3 |
| Davies–Bouldin | Trung bình tỷ lệ độ phân tán trong cụm so với khoảng cách giữa cụm. Càng thấp càng tốt | SD3 |
| ARI, NMI | Mức khớp giữa hai cách chia. ARI: 1 là khớp hoàn toàn, 0 là ngẫu nhiên | SD3 |
| R², MAE | Trên tập test. MAE quy về triệu VNĐ/tháng (sau `expm1`) | SD4 phương án A |
| macro-F1 | Trung bình F1 của từng khung lương | SD4 phương án B |
| coverage@N | Tỷ lệ tin người mới của nghề mà top N kỹ năng đề xuất đáp ứng ≥ 70% số kỹ năng tin đòi | SD5 |

## 6. Đối chiếu với nguồn bên ngoài (tham khảo, không phải cổng)

Có thể đặt kết quả cạnh báo cáo thị trường công khai (ví dụ báo cáo thị trường IT, báo cáo lương do các trang tuyển dụng phát hành) để bàn luận trong báo cáo đồ án. Đây **không phải** tiêu chí nghiệm thu, vì phương pháp và mẫu của các báo cáo đó khác với dự án. Khi dẫn thì ghi tên báo cáo, năm, trang, và nói rõ chỗ khác về phương pháp. Bản 2.0 đặt ngưỡng "trùng ≥ 70% với danh sách kỹ năng lương cao của ITviec"; ngưỡng này đã bỏ.

## 7. Đã bỏ so với bản 2.0

| Mục cũ | Lý do bỏ |
|---|---|
| Skill Gap Matrix, chỉ số thâm hụt kỹ năng (SDS) so với chương trình đại học | Cần dữ liệu chương trình đào tạo. Dự án chỉ có tin tuyển dụng (`docs/target/00_de_tai.md`) |
| Tỷ lệ qua bộ lọc CV giả lập (ATS) | Cần dữ liệu CV |
| Thẻ điểm lộ trình theo "công sức học" | Không có dữ liệu về công sức học. Thay bằng M6 (SD5) |
| Trọng số 25/30/20/0/10/15% cho từng hạng mục | Nghiệm thu theo từng SD với tiêu chí đạt hay chưa đạt, không cộng điểm |
| Model lương "phần phụ, trọng số 0%" | Từ 16/11, M5 là bước chính thức của SD4 |
| `pytest tests/test_data_integrity.py` | File không tồn tại. Kiểm dữ liệu bằng report từng bước và các test trong `tests/` |

## 8. Bảng tổng hợp ngày 17/11/2026

| SD | Có code | Đã chạy thật | Nghiệm thu | Chặn bởi |
|---|---|---|---|---|
| SD1 | Chưa (M1) | — | Chưa | MINE-7, PRE-37, PRE-38, PRE-35 |
| SD2 | Một phần (M2) | 11/11 | Chưa đạt | MINE-1, MINE-7, PRE-33, PRE-40 |
| SD3 | Một phần (M3, M4) | 11/11 | Chưa đạt | MINE-1, MINE-7 |
| SD4 | Một phần (M5) | Chưa | Chưa đo | MINE-1, MINE-7, PRE-35 |
| SD5 | Chưa (M6) | — | Chưa | MINE-7; phụ thuộc SD1, SD2, SD4 |
