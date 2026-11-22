# SD4 · Kỹ năng nào đáng tiền

> Tầng 3: train model (có giám sát). Đề tài và bối cảnh: [00_de_tai.md](00_de_tai.md).

## 1. Bài toán nói đơn giản

Ai cũng biết Senior lương cao hơn Junior, và Hà Nội hay TP.HCM khác tỉnh lẻ. Câu hỏi khó hơn là: **cùng nghề, cùng cấp, cùng kinh nghiệm, cùng tỉnh, biết thêm một kỹ năng thì lương ghi trên tin cao hơn bao nhiêu?**

SD1 chỉ cho biết lương trung bình của từng nhóm. Muốn tách được phần đóng góp riêng của từng kỹ năng thì cần **train một model đoán lương**, rồi đọc ngược model để xem mỗi yếu tố kéo con số lên hay xuống bao nhiêu.

SD4 dùng hai tập tin:

- **Tin công khai lương:** dùng để dạy và chấm model.
- **Tin ghi "thỏa thuận":** đưa model đã dạy vào để **ước tính** khoảng lương.

## 2. Câu hỏi cần trả lời

| Mã | Câu hỏi |
|---|---|
| 4.1 | Trong cấp bậc, kinh nghiệm, tỉnh, nhóm nghề và kỹ năng, yếu tố nào ảnh hưởng lương công bố nhiều nhất? |
| 4.2 | Khi các yếu tố khác giữ nguyên, mỗi kỹ năng làm lương công bố tăng hoặc giảm khoảng bao nhiêu triệu VNĐ/tháng? |
| 4.3 | Model đoán đúng đến đâu? Với nhóm tin nào (nghề, cấp, trang) thì không nên tin model? |
| 4.4 | Tin ghi "thỏa thuận" ước tính được lương khoảng bao nhiêu? Ước tính này đáng tin tới đâu? |

## 3. Dữ liệu dùng

| Tập | Điều kiện | Vai trò |
|---|---|---|
| **Tập có lương** | Có lương > 0, không đánh dấu "thỏa thuận", không bị đánh dấu đáng ngờ, nằm trong khoảng lương hợp lệ. Có thể loại thêm tin lệch quá 3 lần so với trung vị cùng cấp (`select_training_subset` trong `mining/salary_model.py`) | Train và test |
| **Tập thỏa thuận** | `salary_status` là thỏa thuận, hoặc không có lương | Chỉ đưa vào model để ước tính |

- **Đặc trưng đầu vào** (`build_salary_features`): cấp bậc (mã hóa theo thứ tự), `exp_min_years`, nhóm địa điểm (`LOCATION_FEATURE_GROUPS`), `job_family`, ma trận kỹ năng.
- **Không được đưa vào đặc trưng:** bất kỳ cột nào chứa chính lương. `assert_no_leakage` sẽ chặn những cột này.
- **Mục tiêu đoán:** log(1 + lương giữa khoảng), đơn vị triệu VNĐ/tháng. Dùng log vì lương lệch phải mạnh: vài tin rất cao.

Lương hiện chỉ phủ khoảng 40–45% số tin, và còn lỗi sanity (PRE-35). SD4 chỉ chạy chính thức khi tập có lương đạt tiêu chí sạch.

## 4. Cách trả lời

### Phương án A: đoán ra con số lương (hồi quy)

1. **Chia dữ liệu:**
   - Tách 80% để train, 20% để test, phân tầng theo cấp bậc.
   - Các tin cùng một công ty (`company_key`) phải nằm cùng một phía. Nếu không, model chỉ "nhớ" lương của công ty thay vì học quy luật (`_groups`).
2. **Train Random Forest:**
   - Model gồm nhiều cây quyết định. Mỗi cây học một cách chia tin theo các yếu tố, sau đó lấy trung bình kết quả các cây.
   - Chọn tham số bằng kiểm định chéo 5 phần, cũng nhóm theo công ty (`_cv_scores`).
3. **Chấm điểm (4.3):**
   - **R²:** model giải thích được bao nhiêu phần sự khác nhau về lương.
   - **MAE:** trung bình đoán lệch bao nhiêu triệu.
   - **Baseline để so:** đoán bằng trung vị lương theo cấp × nghề (lấy từ SD1).
   - Báo thêm MAE riêng theo từng nghề, cấp và trang, để chỉ ra nhóm nào model đoán kém.
4. **Đọc model bằng SHAP (4.1, 4.2):**
   - SHAP chia con số model đoán cho một tin thành phần đóng góp của từng yếu tố.
   - Lấy trung bình phần đóng góp của kỹ năng X trên các tin có X, quy đổi ra triệu VNĐ (`skill_values_from_shap`). Kết quả là con số "biết X thì lương công bố hơn khoảng bao nhiêu".
   - Xếp hạng các yếu tố theo mức đóng góp trung bình (lấy trị tuyệt đối) để trả lời 4.1.
5. **Ước tính cho tin thỏa thuận (4.4):**
   - Đưa tập thỏa thuận vào model đã train.
   - Lưu kết quả ở cột riêng `salary_estimated_vnd`, kèm cờ `salary_is_estimated = true`.
   - Lưu khoảng dao động, tức phân vị 10% và 90% của dự đoán từ các cây trong Random Forest.

**Phương án A đạt** khi cả hai điều kiện đúng:

- MAE trên tập test **thấp hơn baseline ít nhất 10%**. Ngưỡng 10% đã chốt 22/11 (L-60); 22/11 đạt 16,7%.
- Đạt các ngưỡng đang có trong `mining/config.py`: R² (log) ≥ 0,60, MAE ≤ 4,5 triệu, độ lệch chuẩn R² qua các lần kiểm định chéo ≤ 0,05.

### Phương án B (dự phòng): đoán khung lương (phân lớp)

Dùng khi phương án A không đạt.

- Chia lương công khai thành 4 khung theo phân vị của chính tập có lương. Ví dụ dưới 10 triệu, 10–20, 20–35, trên 35 triệu; ranh giới thật chốt theo số liệu lúc chạy.
- Train Random Forest phân lớp để đoán tin thuộc khung nào. Đặc trưng đầu vào và cách chia dữ liệu giữ như phương án A.
- **Chấm điểm:** macro-F1 (trung bình độ đúng của từng khung, không thiên về khung đông) và accuracy. So với baseline luôn đoán khung đông nhất.
- SHAP vẫn dùng được, nhưng đọc là "kỹ năng X đẩy tin lên khung cao hơn bao nhiêu", không quy ra triệu VNĐ.
- Tin thỏa thuận được gán **khung lương ước tính** thay cho con số.

### Kiểm tra trước khi ước tính

So phân bố cấp bậc, nghề và trang giữa tập có lương và tập thỏa thuận. Với nhóm nào mà tập thỏa thuận lệch nhiều (ví dụ tỷ lệ Senior gấp đôi), lương ước tính của nhóm đó phải ghi cảnh báo, vì model ít được dạy trên kiểu tin này.

## 5. Đầu ra

| Đầu ra | Dạng |
|---|---|
| Chỉ số model (4.3) | JSON: phương án dùng (A/B), số tin train và test, R²/MAE hoặc macro-F1, baseline, đạt ngưỡng hay không, MAE theo nhóm |
| Xếp hạng yếu tố (4.1) | Bảng: yếu tố, mức đóng góp trung bình |
| Giá trị kỹ năng (4.2) | Bảng: kỹ năng, số tin có kỹ năng, mức cộng/trừ (triệu VNĐ hoặc bậc khung), khoảng tin cậy |
| Lương ước tính (4.4) | Cột `salary_estimated_vnd` (hoặc `salary_band_estimated`), `salary_is_estimated`, khoảng dao động, cờ cảnh báo, gắn theo `job_id` |
| Biểu đồ | Cột ngang: top 20 kỹ năng theo mức cộng lương. SHAP summary. Điểm: lương thật so với lương đoán trên tập test |

## 6. Cách biết đã trả lời đúng

- Model phải thắng baseline (mục 4). Nếu không thắng thì không báo cáo giá trị kỹ năng.
- Kiểm định chéo theo nhóm công ty: độ lệch chuẩn của R² giữa các lần ≤ 0,05. Nếu không, model thiếu ổn định.
- **Sanity:**
  - Mức đóng góp của cấp bậc phải tăng dần từ Intern/Fresher lên Lead/Manager.
  - Mức cộng lương của các kỹ năng phổ biến phải cùng chiều với chênh lệch trung vị thô ở SD1. Kỹ năng nào ngược chiều thì giải thích được, hoặc ghi lại.
- Lương ước tính của tin thỏa thuận không được dùng để chấm model, vì không có đáp án đúng.

## 7. Những gì không trả lời được

- **Quan hệ nhân quả:** SHAP cho biết model dùng kỹ năng X thế nào để đoán, không chứng minh "học X sẽ được tăng lương" (MINE-6).
- **Lương thật nhận được:** chỉ là lương ghi trên tin.
- **Tin thỏa thuận chắc chắn lương bao nhiêu:** ước tính dựa trên giả định tin thỏa thuận giống tin công khai lương có cùng đặc điểm. Giả định này có thể sai, ví dụ tin thỏa thuận thường là vị trí cao. Vì vậy luôn ghi nhãn "ước tính".
- **Kỹ năng hiếm:** kỹ năng có dưới khoảng 30 tin (chốt 22/11, L-60) trong tập có lương thì không đủ dữ liệu để định giá. Chỉ ghi "ít dữ liệu".

## 8. Code và spec liên quan

- Code:
  - `mining/salary_model.py`: `select_training_subset`, `build_salary_features`, `assert_no_leakage`, `train_salary_model`, `skill_values_from_shap`.
  - `mining/config.py`: ngưỡng R², MAE, độ lệch chuẩn CV.
- Spec cần sửa cho khớp:
  - Đã sửa 17/11: `docs/spec/07_mining_spec.md` mục 3.5 (M5, kèm danh sách còn thiếu), `docs/spec/08_evaluation_spec.md` mục 3.4.
  - Đã sửa 17/11: spec 05 và spec 06 (mục 4) ghi bước chia train/test là bắt buộc cho SD4 và nằm trong M5. Spec 06 mục 2.2 ghi các đặc trưng không được dùng làm đầu vào model lương.
- Chất lượng dữ liệu cần cho SD4: PRE-35, MINE-1, MINE-5, MINE-6 trong `docs/KNOWN_ISSUED.md`.
