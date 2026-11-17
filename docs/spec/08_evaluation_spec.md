# ĐẶC TẢ ĐÁNH GIÁ VÀ NGHIỆM THU

> **Dự án:** VN-IT-Job-Mining. Đề tài: "Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT".
> **Phiên bản:** 3.0.0, ngày 17/11/2026. **Trạng thái:** đã duyệt 17/11/2026 (chặng 4).
> **Thay cho:** bản 2.0. Bản đó có "Skill Gap Matrix", chỉ số thâm hụt kỹ năng so với chương trình đại học, tỷ lệ qua bộ lọc CV giả lập, và coi model lương là "phần phụ, trọng số 0%".
> **Quan hệ với tài liệu khác:** tiêu chí "cách biết đã trả lời đúng" của từng SD nằm ở mục 6 của mỗi file trong [`docs/target/`](../target/00_de_tai.md). Spec này gom các tiêu chí đó lại, ghi cách đo bằng code nào, và hiện trạng. Bước được đo: [spec 05](05_preprocessing_spec.md), [06](06_processing_spec.md), [07](07_mining_spec.md).

## 0. Cách đọc

- **Ngưỡng:** mọi ngưỡng nghiệm thu của SD1–SD5 là **đề xuất, chờ chốt ở PRE-36**. Bảng dưới vẫn ghi con số để có cái mà chốt. Ngưỡng nào đã có trong code (`mining/config.py`) thì ghi rõ "trong code".
- **Hiện trạng** lấy từ lần chạy thật gần nhất (10–11/11/2026, 4.671 tin; `docs/issue_log.md` L-46, L-47; report `reports/preprocessing/`, `reports/processing/`).
- Mỗi tiêu chí có một trong ba trạng thái: **Đạt**, **Chưa đạt** (đã đo, không qua), **Chưa đo** (chưa có code hoặc chưa chạy).

## 1. Nguyên tắc chung

1. **Số thật.** Mọi số dùng để nghiệm thu đến từ dữ liệu thật. Kết quả của `mining/synthetic.py` (`--synthetic`) chỉ dùng để test code, không bao giờ dùng để nghiệm thu (L-19).
2. **Dữ liệu sạch là điều kiện trước.** Một SD chỉ được nghiệm thu khi các cột nó dùng đã đạt tiêu chí sạch của PRE-35. Trước đó, kết quả chỉ là bản chạy thử.
3. **Tái lập.** Mỗi kết quả ghi kèm ngày chạy, `code_version`, sha256 của file đầu vào (`mining_metrics.json`) và `random_state` (42). Chạy lại phải ra cùng số.
4. **Ít dữ liệu.** Ô bảng có n < 30 ghi "ít dữ liệu", không ghi số (PRE-36).
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

### 3.1. SD1: Bức tranh thị trường (M1)

| Tiêu chí | Cách đo | Ngưỡng | Hiện trạng |
|---|---|---|---|
| Mọi bảng có n và độ phủ; tổng khớp số tin bảng 04; tỷ lệ cộng đủ 100% | Test cho `mining/bi.py` | Bắt buộc | Chưa đo (chưa có code) |
| Ô n < 30 ghi "ít dữ liệu" | Test | Bắt buộc | Chưa đo |
| Câu 1.2 tách cấp bậc gốc và cấp bậc suy ra (`level_inferred`) | Đọc bảng | Bắt buộc | Chưa đo |
| Câu 1.7 chỉ so cơ cấu; tháng 9 tách theo `posted_month_source` | Đọc bảng | Bắt buộc | Chưa đo (thiếu `posted_month`, PRE-37) |
| Lương ước tính từ M5 không trộn với lương công khai | Cột riêng có nhãn "ước tính" | Bắt buộc | Chưa đo |
| S-04, S-06 (mục 4) | `mining/sanity.py` | Pass, hoặc có giải thích | Chưa đạt: cả hai fail 11/11 |

### 3.2. SD2: Gói kỹ năng (M2)

| Tiêu chí | Cách đo | Ngưỡng | Hiện trạng |
|---|---|---|---|
| Mọi luật báo cáo đủ support của phạm vi và lift ≥ 1,20 | Lọc trong `mine_rules` | Trong code: support 0,05 (toàn bộ), 0,02 (nghề); confidence 0,60; lift 1,20 | Đạt (13.514 luật) |
| Cặp hiển nhiên S-01, S-02, S-03 | `mining/sanity.py` | Pass | Chưa đạt: S-02 (0,375), S-03 (0,654) fail |
| Kiểm tay 20 luật mạnh nhất | Người làm nghề đọc | Không có luật vô nghĩa; có thì tìm nguyên nhân | Chưa đo |
| Ổn định khi đổi support một bậc | Chạy lại với ngưỡng thấp hơn và cao hơn | Luật mạnh nhất không đổi lớn | Chưa đo |
| Kỹ năng hiếm (2.4) | Code chưa có | < 2% số tin, và lift ≥ 2 hoặc ≥ 60% xuất hiện ở tin Senior/Lead (PRE-36) | Chưa đo |

### 3.3. SD3: Nhóm việc và tin khác hoặc mới (M3, M4)

| Tiêu chí | Cách đo | Ngưỡng | Hiện trạng |
|---|---|---|---|
| Độ tách nhóm | Silhouette, Davies–Bouldin trên không gian SVD | Chưa có đề xuất (PRE-36). Trong code: Silhouette 0,28, DB 1,80 (`ClusteringParams`), chỉ để tham khảo | Silhouette 0,1015, DB 2,49 (k = 10) |
| Độ ổn định | ARI giữa 5 lần chạy với 5 seed | ≥ 0,8 (PRE-36) | Chưa đo |
| Kích thước nhóm | Cụm nhỏ nhất / số tin (trừ nhóm "để riêng" của HDBSCAN) | ≥ 1% (PRE-36) | Chưa đo |
| Không tách theo số kỹ năng | Trung vị số kỹ năng theo cụm | Không cụm nào chỉ phản ánh tin nhiều hay ít kỹ năng | Chưa đạt: cụm 1 chứa 292/293 tin không có kỹ năng; cụm 9 trung vị 15 kỹ năng (L-47). Đã chốt loại tin không có kỹ năng khỏi phân cụm (spec 07 mục 4), chưa chạy lại |
| Mức khớp với `job_family` (để đọc, không phải cổng) | ARI, NMI trên tin khác Other | Báo cáo, không đặt ngưỡng | ARI 0,071, NMI 0,144 |
| Tin khác hoặc mới | Kiểm tay 20 tin ngẫu nhiên | Ghi tỷ lệ tin đúng là khác hoặc mới thật, so với tin do parse lỗi | Chưa đo; 282 tin bị gắn cờ (6,04%) |

### 3.4. SD4: Giá trị kỹ năng (M5)

| Tiêu chí | Cách đo | Ngưỡng | Hiện trạng |
|---|---|---|---|
| Không rò rỉ | `assert_no_leakage`; các tin cùng `company_key` nằm cùng một phía | Bắt buộc | Chưa đạt: code đang nhóm theo `dup_group_id` |
| Phương án A thắng baseline | MAE trên tập test so với trung vị lương cấp × nghề (từ M1) | Thấp hơn ít nhất 10% (PRE-36) | Chưa đo |
| Phương án A đạt ngưỡng trong code | R² (log), MAE, độ lệch chuẩn R² qua CV theo công ty | Trong code: R² ≥ 0,60; MAE ≤ 4,5 triệu; std ≤ 0,05 (cần chốt lại, PRE-36) | Chưa đo (model chưa chạy trên dữ liệu thật) |
| Phương án B (khi A không đạt) | macro-F1 và accuracy so với baseline "luôn đoán khung đông nhất" | Thắng baseline | Chưa đo (chưa có code) |
| Chỉ định giá kỹ năng đủ dữ liệu | Số tin có kỹ năng trong tập có lương | ≥ 30 tin (trong code: `min_skill_sample`; PRE-36) | Chưa đo |
| Sanity S-04, S-05, S-06; mức đóng góp của cấp bậc tăng dần từ Intern/Fresher đến Lead/Manager | `mining/sanity.py`, SHAP | Pass, hoặc có giải thích | S-04 và S-06 fail; S-05 chưa đo |
| Giá trị kỹ năng cùng chiều với chênh lệch trung vị thô (M1) | So từng kỹ năng phổ biến | Kỹ năng ngược chiều thì giải thích hoặc ghi lại | Chưa đo |
| Lương ước tính của tin thỏa thuận | Không dùng để chấm model. Nhóm có phân bố lệch nhiều so với tập có lương phải ghi cảnh báo | Bắt buộc | Chưa đo (chưa có code) |

Model không thắng baseline thì **không báo cáo giá trị kỹ năng**. Giá trị SHAP là mức liên quan, không phải quan hệ nhân quả (MINE-6).

### 3.5. SD5: Lộ trình học (M6)

| Tiêu chí | Cách đo | Ngưỡng | Hiện trạng |
|---|---|---|---|
| Chỉ làm lộ trình cho nghề đủ dữ liệu | Số tin Intern/Fresher + Junior của nghề | ≥ 30 tin (PRE-36); thiếu thì ghi "ít dữ liệu" | Chưa đo |
| Độ phủ hơn baseline | coverage@10 của nghề so với "top 10 kỹ năng toàn thị trường" | Phải cao hơn | Chưa đo |
| Không học tủ | Tính điểm trên 80% tin người mới, đo coverage@N trên 20% còn lại | Lệch ≤ 10 điểm phần trăm (PRE-36) | Chưa đo |
| Truy được nguồn | Mỗi kỹ năng trong lộ trình có `demand`, luật SD2, giá trị SD4 | Bắt buộc | Chưa đo |
| Đọc tay | Người làm nghề đọc lộ trình của 2 nghề | Bước ngược lẽ thường được ghi lại và tìm nguyên nhân | Chưa đo |

## 4. Sanity S-01..S-06

Code: `mining/sanity.py` (`run_sanity_checks`), kết quả ghi vào `mining_metrics.json` (`sanity_checks`, `sanity_summary`). S-01..S-03 tính thẳng từ ma trận kỹ năng, không phụ thuộc ngưỡng support của FP-Growth.

| Mã | Kiểm tra | Tiêu chí pass | SD | Kết quả 11/11 |
|---|---|---|---|---|
| S-01 | {Spring Boot} ⇒ {Java} | Confidence ≥ 0,85 và lift ≥ 1,5 | SD2 | Pass |
| S-02 | {Flutter} ⇒ {Dart} | Confidence ≥ 0,90 | SD2 | Fail (0,375) |
| S-03 | {React} ⇒ {JavaScript} hoặc {TypeScript} | Confidence ≥ 0,80 | SD2 | Fail (0,654) |
| S-04 | Trung vị lương tăng dần theo cấp: Fresher < Junior < Middle < Senior | Đơn điệu | SD1, SD4 | Fail (Senior < Middle) |
| S-05 | Giá trị SHAP của AWS, Kubernetes hoặc System Design | φ > 0 | SD4 | Chưa đo (chưa có bảng SHAP) |
| S-06 | Trung vị lương HN và HCM so với tỉnh khác (trừ Remote) | Mỗi bên > 1,2 lần | SD1, SD4 | Fail |

Sanity fail không có nghĩa là thuật toán sai. Có thể do dữ liệu (rút kỹ năng sai, lương parse sai, tỉnh sai) hoặc do ngưỡng kiểm. **Phải tìm nguyên nhân trước khi dùng kết quả** (MINE-1), và ghi nguyên nhân vào báo cáo.

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
