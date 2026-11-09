# 🧠 CẨM NANG NHIỆM VỤ: DATA MINING CORE ALGORITHMS
## THÀNH VIÊN PHỤ TRÁCH: PHÚC

> **Hạn chót hoàn thành (Deadline):** **19:00 PM Chủ Nhật**  
> **Thư mục thực hiện chính (Folder Ownership):**  
> - `mining/` (Chứa toàn bộ mã nguồn thuật toán FP-Growth, K-Means, Random Forest + SHAP và các artifacts mô hình)  
> **Nhánh Git cá nhân:** `feature/mining-algorithms`  
> **Nhánh hợp nhất (Merge Destination):** `sprint/pipeline-delivery`  
> **Tài liệu đặc tả đối chiếu:** [`docs/spec/07_mining_spec.md`](../spec/07_mining_spec.md), [`docs/spec/08_evaluation_spec.md`](../spec/08_evaluation_spec.md)

---

## 1. Mục Tiêu & Các Vấn Đề Cốt Lõi Cần Giải Quyết

Phúc chịu trách nhiệm về "Bộ não tri thức" của toàn bộ đồ án tốt nghiệp: Triển khai **bộ tứ thuật toán Học máy không giám sát (Unsupervised Learning)** kết hợp mô hình hóa giải thích mức lương (Explainable AI) để chuyển đổi dữ liệu dạng bảng thành những hiểu biết thị trường (Market Intelligence) có giá trị thực tiễn cho sinh viên IT:

1. **Thuật Toán 1 — Khai Phá Luật Kết Hợp Kỹ Năng Phân Tầng (Stratified FP-Growth):**
   - *Mục tiêu:* Tìm ra các "Combo kỹ năng" luôn đi kèm với nhau trong yêu cầu tuyển dụng (ví dụ: học React thì bắt buộc phải biết TypeScript và Next.js).
   - *Chiến lược phân tầng:* Chạy cả ở tầm vĩ mô toàn ngành ($min\_sup = 0.05$) và vi mô theo từng Job Family ($min\_sup = 0.02$) để không bỏ sót các combo công nghệ đặc thù (Data/AI, Mobile, DevOps).
   - *Ngưỡng chất lượng luật:* $Confidence \ge 0.60$ và $Lift > 1.20$.
2. **Thuật Toán 2 — Phân Cụm Việc Làm & Giảm Chiều Không Gian (K-Means & HDBSCAN + PCA 2D/3D):**
   - *Mục tiêu:* Khám phá các cụm nghề nghiệp tự nhiên của thị trường dựa trên không gian vector kỹ năng (230 cột) và TF-IDF mô tả công việc.
   - *Tối ưu hóa:* Dùng phương pháp Elbow và Silhouette Analysis để tìm số cụm tối ưu ($k \in [6, 12]$) đối chiếu với 12 Job Family. Kết hợp HDBSCAN để phát hiện các tin lai tạp/nhiễu.
   - *Trực quan hóa đa chiều:* Chiếu giảm chiều dữ liệu bằng thuật toán **PCA** xuất ra cả tọa độ **2D (`pca_x, pca_y`)** và **3D (`pca_x, pca_y, pca_z`)** phục vụ trực quan hóa phân tán 3D trên Dashboard của Sơn.
3. **Thuật Toán 3 — Hồi Quy Dự Báo Lương & Định Lượng Giá Trị Kỹ Năng (Random Forest Regressor + TreeSHAP):**
   - *Mục tiêu:* Trả lời câu hỏi quan trọng nhất của sinh viên: "Kỹ năng nào có giá trị đẩy mức lương lên cao nhất?".
   - *Dữ liệu huấn luyện:* Huấn luyện trên Subset có khoảng lương số cụ thể (~45% tin). Áp dụng hàm $\log(1 + \text{salary\_avg})$ để khắc phục độ lệch phải của phân phối lương.
   - *Giải thích mô hình (TreeSHAP):* Áp dụng `shap.TreeExplainer` tính toán đóng góp biên (Marginal Contribution) của từng kỹ năng:
     $$\Delta \text{Salary}_{\text{VND}}(i) \approx \text{Baseline Salary} \times \left( e^{\phi_i} - 1 \right)$$
4. **Thuật Toán 4 — Phát Hiện Bất Thường Tuyển Dụng (Anomaly Detection):**
   - *Mục tiêu:* Nhận diện các tin tuyển dụng bất thường (Ghost jobs, tin rác, đòi hỏi phi thực tế như Fresher đòi 15 công nghệ cao cấp, hoặc lương ảo).
   - *Thuật toán:* Áp dụng **Isolation Forest** trên không gian [kinh nghiệm, lương, số lượng kỹ năng] kết hợp điểm số ngoại lai mật độ **HDBSCAN GLOSH Score**.

---

## 2. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Phúc làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Nhà Khoa Học Dữ Liệu (Data Scientist & Mining Specialist) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là triển khai trọn vẹn 4 trụ cột Khai phá Dữ liệu học thuật: (1) Stratified FP-Growth trích xuất luật kết hợp kỹ năng (Support, Confidence, Lift); (2) K-Means + HDBSCAN phân cụm việc làm kết hợp PCA xuất tọa độ 2D và 3D (pca_x, pca_y, pca_z); (3) Random Forest Regressor + TreeSHAP mô hình hóa mức lương và định lượng giá trị kinh tế biên của từng kỹ năng; (4) Isolation Forest & HDBSCAN GLOSH score phát hiện tin bất thường và outliers. Tham khảo đặc tả kỹ thuật tại docs/spec/07_mining_spec.md và docs/spec/08_evaluation_spec.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Chỉ can thiệp vào mã nguồn trong thư mục: `mining/`.
- Sử dụng các thư viện chuẩn mực: `mlxtend`, `scikit-learn`, `shap`, `pandas`, `numpy`.
- Mô hình lương chỉ huấn luyện trên các tin có mức lương cụ thể (loại bỏ tin Thỏa thuận), dùng K-Fold Cross Validation (5 folds) để đánh giá.
- Xuất đầy đủ 4 tệp Parquet artifacts tại `mining/artifacts/` để nạp vào PostgreSQL Data Mart theo đúng schema đã thống nhất với Sơn.

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào:
  * `data/curated/curated_flat_golden_jobs.parquet` (Dữ liệu tuyển dụng vàng)
  * `data/preprocessing/05_encoding/features.parquet` (Ma trận 230 cột kỹ năng)
- Đầu ra tại `mining/artifacts/`:
  * `skill_association_rules.parquet`: Cột [antecedents, consequents, support, confidence, lift, job_family_scope]
  * `job_clusters.parquet`: Cột [job_id, job_title, job_family, cluster_id, cluster_name, pca_x, pca_y, pca_z, is_outlier, glosh_outlier_score]
  * `job_anomalies.parquet`: Cột [job_id, job_title, company_name, anomaly_score, reason_code, detected_by]
  * `skill_salary_shap_values.parquet`: Cột [skill_name, job_family, mean_shap_value, marginal_dollar_vnd, sample_size]
  * `trained_salary_rf_model.joblib`: File lưu mô hình Random Forest

### 4. YÊU CẦU THỰC HIỆN:
Hãy phân tích mã nguồn mẫu trong docs/spec/07_mining_spec.md, lập Plan thực thi lần lượt 4 thuật toán, chạy thực nghiệm và xuất các chỉ số đánh giá toán học (Lift, Silhouette, R2, MAE, Anomaly Rate).
```

---

## 3. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [ ] **Bước 1 (FP-Growth):**
  * Chạy thuật toán FP-Growth, trích xuất ít nhất 30 luật kết hợp có $Lift > 1.2$ và $Confidence \ge 0.6$.
  * Phân tách luật toàn thị trường (Macro) và luật theo từng Job Family (Micro).
- [ ] **Bước 2 (K-Means, HDBSCAN & PCA 2D/3D):**
  * Chạy đồ thị Elbow và Silhouette Score cho $k \in [4, 14]$, chọn $k$ tối ưu có Silhouette $\ge 0.28$.
  * Chạy PCA giảm chiều, lưu đủ 3 cột tọa độ `pca_x`, `pca_y`, `pca_z` cùng nhãn cụm.
- [ ] **Bước 3 (Random Forest & TreeSHAP):**
  * Huấn luyện mô hình Random Forest trên tập tin có lương: Đạt $R^2 \ge 0.60$ và $MAE \le 4.5\text{ triệu VNĐ}$ trên tập kiểm thử (Test Set 20%).
  * Chạy TreeSHAP tính ma trận $\phi_{i, j}$; tổng hợp Top 15 kỹ năng có giá trị tăng lương cao nhất.
- [ ] **Bước 4 (Isolation Forest & Anomaly Detection):**
  * Huấn luyện Isolation Forest, tính `anomaly_score` và trích xuất danh sách các tin ngoại lai / bất thường.
- [ ] **Bước 5 (Chạy toàn trình Mining):**
  ```bash
  python mining/run_mining_pipeline.py
  ```
  Xác nhận tất cả 4 tệp Parquet artifacts và file `.joblib` trong `mining/artifacts/` được sinh ra đầy đủ.
- [ ] **Bước 6 (Linting):** Chạy `ruff check mining/`.

---

## 4. Mẫu Báo Cáo Nghiệm Thu Bàn Giao (Delivery Report Template)

*Sau khi hoàn thành, Phúc điền thông tin vào mẫu dưới đây và dán vào mô tả Pull Request khi merge vào `sprint/pipeline-delivery`:*

```markdown
### BÁO CÁO NGHIỆM THU: DATA MINING CORE ALGORITHMS
- **Người thực hiện:** Phúc
- **Nhánh làm việc:** `feature/mining-algorithms`
- **Thư mục can thiệp:** `mining/`

#### 1. Vấn Đề Gặp Phải (Problems Encountered):
- [Mô tả thách thức khi cân bằng ngưỡng Support hoặc tối ưu hóa thời gian tính SHAP]

#### 2. Nguyên Nhân Gốc Rễ (Root Cause):
- [Giải thích sự mất cân bằng giữa các kỹ năng phổ biến vs kỹ năng ngách]

#### 3. Giải Pháp Kỹ Thuật Đã Triển Khai (Solution Implemented):
- [Trình bày thuật toán FP-Growth phân tầng, tối ưu k-means qua Silhouette và TreeSHAP]

#### 4. Bằng Chứng Tự Kiểm Chứng (Verification Proof):
- **Kết quả FP-Growth:** Đã trích xuất [...] luật kết hợp hợp lệ. Top 3 luật có Lift cao nhất:
  1. [...] => [...]: Support = ..., Confidence = ..., Lift = ...
- **Kết quả K-Means:** Số cụm tối ưu $k = [...]$ với Silhouette Score $= [...]$.
- **Kết quả Mô hình Lương:**
  * Chỉ số hồi quy: $R^2 = [...]$, $MAE = [...]$ triệu VNĐ, $RMSE = [...]$ triệu VNĐ.
  * Top 5 kỹ năng mang lại thặng dư lương biên cao nhất:
    1. [Kỹ năng 1]: +[...] triệu VNĐ/tháng
    2. [Kỹ năng 2]: +[...] triệu VNĐ/tháng
    3. [Kỹ năng 3]: +[...] triệu VNĐ/tháng

#### 5. Vấn Đề Còn Tồn Đọng (Remaining Issues / Blockers):
- [Ghi rõ nếu có siêu tham số nào cần tinh chỉnh thêm, hoặc ghi "Không còn"]
```

---

## 5. Báo Cáo Bàn Giao (bản nháp 08/11/2026)

> **Trạng thái:** đã xong code và test cho cả 4 thuật toán. Hiện mới chạy trên **dữ liệu giả** (`mining/synthetic.py`), vì `features.parquet` và bộ golden của bước Encoding chưa merge vào `sprint/pipeline-delivery`. Các ô `[chờ dữ liệu thật]` sẽ điền sau khi chạy `python mining/run_mining_pipeline.py` trên dữ liệu thật. Số liệu trên dữ liệu giả chỉ để chứng minh code chạy đúng, **không dùng để báo cáo thị trường**.

### BÁO CÁO NGHIỆM THU: DATA MINING CORE ALGORITHMS
- **Người thực hiện:** Phúc
- **Nhánh làm việc:** `feature/mining-algorithms`
- **Thư mục can thiệp:** `mining/`, `tests/unit/test_mining_*.py`

#### Cấu trúc mã nguồn

| File | Vai trò |
|---|---|
| `mining/config.py` | Đường dẫn, bảng alias tên cột, tham số và ngưỡng của từng thuật toán |
| `mining/data_io.py` | Đọc golden và features, kiểm tra hợp đồng cột (thiếu khóa, trùng `job_id`, cột kỹ năng không phải 0/1, lệch dòng). Đưa về một schema chung (`MiningData`) |
| `mining/association.py` | FP-Growth phân tầng: vĩ mô và vi mô theo từng `job_family` |
| `mining/clustering.py` | Không gian kỹ năng + TF-IDF JD → TruncatedSVD → K-Means (quét k), HDBSCAN GLOSH, PCA 2D/3D |
| `mining/salary_model.py` | Random Forest với log1p(lương), holdout 20%, 5-fold CV, baseline, TreeSHAP |
| `mining/anomaly.py` | Isolation Forest + GLOSH, kèm mã lý do |
| `mining/sanity.py` | Kiểm tra hợp lý S-01 đến S-06 theo spec 08 |
| `mining/run_mining_pipeline.py` | Driver: ghi 4 file Parquet, model `.joblib` và `mining_metrics.json` |
| `mining/synthetic.py` | Dữ liệu giả có cài sẵn quy luật đã biết, dùng cho test |

Cách chạy:
```bash
python mining/run_mining_pipeline.py                         # dữ liệu thật -> mining/artifacts/
python mining/run_mining_pipeline.py --synthetic             # dữ liệu giả -> mining/artifacts/_synthetic/
python mining/run_mining_pipeline.py --only fp,cluster --dry-run
pytest tests/unit/test_mining_*.py                           # 61 test
```

#### 1. Vấn Đề Gặp Phải
- **Schema đầu vào chưa chốt:**
  - Tiền tố cột kỹ năng: `skill_` hay `skill__`.
  - Đơn vị lương: VNĐ hay triệu VNĐ/tháng.
  - Thang cấp bậc có 3 dạng cùng tồn tại: `seniority_level` (0–4, Duy), nhãn chữ 6 mức, và `seniority_ord` (0–5, Encoding E1).
  - "Nhiều địa điểm" và "Toàn quốc" bị lẫn vào nhóm "tỉnh khác".
- **Mã mẫu trong spec 07 sai so với dữ liệu:** dùng sai tiền tố cột, và `features.parquet` không có cột lương.
- **Mô hình lương không ổn định:** vài tin lương ảo (Junior 300–450 triệu) làm Std(R²) qua 5 fold lên 0,166, gấp 3 lần ngưỡng.
- **SHAP lấy trung bình trên mọi tin** làm giá trị của kỹ năng hiếm gần bằng 0.
- **K-Means luôn có xu hướng chọn k lớn nhất** trong khoảng quét.

#### 2. Nguyên Nhân Gốc Rễ
- Các bước trước làm song song nên tên và đơn vị cột chưa thống nhất.
- Lương có phân phối lệch phải, và lương ảo nằm trong khoảng hợp lệ 1–500 triệu nên luật lọc khoảng giá trị không bắt được.
- Kỹ năng ngách chỉ xuất hiện ở vài phần trăm số tin. Lấy trung bình φ trên toàn bộ dữ liệu thì phần lớn là các tin không có kỹ năng đó (φ ≈ 0).
- Ma trận kỹ năng thưa và nhiều chiều, nên silhouette tăng dần theo k.

#### 3. Giải Pháp Kỹ Thuật Đã Triển Khai
- **Lớp hợp đồng dữ liệu (`data_io.py` + `COLUMN_ALIASES`):**
  - Tự nhận tên cột cũ và mới, đơn vị lương (theo trung vị) và thang cấp bậc. Ưu tiên `seniority_ord` (0–5), rồi nhãn chữ, rồi `seniority_level` (0–4, đổi 0→1 … 4→5).
  - Sai hợp đồng thì dừng với `MiningContractError`, không chạy tiếp với dữ liệu sai.
- **FP-Growth phân tầng:**
  - Vĩ mô `min_sup = 0,05` trên toàn bộ tin; vi mô `min_sup = 0,02` cho mỗi `job_family` có ≥ 100 tin.
  - Lọc luật `Conf ≥ 0,60`, `Lift > 1,20`.
  - Có thêm conviction và cosine. Conviction vô hạn được ghi là null để JSON và dashboard đọc được.
  - Chỉ tính các tin có ít nhất 1 kỹ năng, để tin không có kỹ năng không làm loãng support.
- **Phân cụm:**
  - Kỹ năng (đã L2-normalize) + TF-IDF JD với trọng số 0,3 → TruncatedSVD giữ ~80% phương sai → K-Means quét k từ 4 đến 14.
  - Chọn k có silhouette cao nhất trong số k ≥ 8, theo yêu cầu "≥ 8 cụm nghề" của spec 08.
  - Kèm Davies-Bouldin, và ARI/NMI so với `job_family`.
  - HDBSCAN GLOSH cho ra `is_outlier` và `glosh_outlier_score`. PCA 3D cho ra `pca_x`, `pca_y`, `pca_z`.
- **Mô hình lương:**
  - Subset A bỏ các tin "Thỏa thuận", tin bị đánh dấu `salary_suspect`, tin ngoài khoảng 1–500 triệu, và tin có lương > 3 lần hoặc < 1/3 trung vị cùng cấp bậc.
  - Biến mục tiêu là `log1p(salary_avg)`.
  - Chọn tham số trong một lưới 4 bộ bằng 5-fold CV. Tự dùng `GroupKFold` nếu có mã nhóm tin trùng.
  - So với baseline chỉ dùng cấp bậc + kinh nghiệm.
  - `assert_no_leakage` chặn mọi feature có chứa thông tin lương.
- **TreeSHAP:**
  - φ của mỗi kỹ năng được lấy **trung bình trên các tin có kỹ năng đó**, tính chung (`ALL`) và theo từng `job_family`.
  - Giá trị biên = baseline × (e^φ − 1).
  - `is_reliable` chỉ bật khi `sample_size ≥ 30`.
- **Phát hiện bất thường:**
  - Isolation Forest chạy trên [kinh nghiệm, cấp bậc, số kỹ năng, lương so với trung vị cùng cấp bậc], kết hợp với GLOSH.
  - Mỗi tin bị gắn cờ có mã lý do: `FRESHER_TOO_MANY_SKILLS`, `SALARY_TOO_HIGH/LOW_FOR_LEVEL`, `EXP_SENIORITY_MISMATCH`, `TOO_MANY_SKILLS`, `SKILL_PROFILE_OUTLIER`, `ISOLATION_GENERIC`.
  - `detected_by` cho biết tin bị bắt bởi isolation_forest, glosh hay cả hai.
- **Tái lập kết quả:**
  - `random_state = 42` ở mọi bước.
  - `mining_metrics.json` ghi sha256 của file đầu vào, tham số, số dòng bị loại ở từng bước, thời gian chạy và `targets_summary`.

#### 4. Bằng Chứng Tự Kiểm Chứng

| Chỉ tiêu | Ngưỡng | Dữ liệu giả (1.500 tin) | Dữ liệu thật |
|---|---|---|---|
| Số luật hợp lệ | ≥ 30 | 798 (42 vĩ mô) | [chờ dữ liệu thật] |
| Silhouette | ≥ 0,28 | 0,470 (k = 14) | [chờ dữ liệu thật] |
| Davies-Bouldin | < 1,80 | 0,937 | [chờ dữ liệu thật] |
| Số cụm | ≥ 8 | 14 | [chờ dữ liệu thật] |
| R² (holdout, log) | ≥ 0,60 | 0,912 (baseline 0,692) | [chờ dữ liệu thật] |
| MAE | ≤ 4,5 triệu | 3,77 triệu (RMSE 7,07) | [chờ dữ liệu thật] |
| Std(R²) 5-fold | ≤ 0,05 | 0,0084 (trung bình 0,936) | [chờ dữ liệu thật] |
| Sanity S-01 đến S-06 | Đạt cả 6 | 6/6 | [chờ dữ liệu thật] |
| Tỉ lệ tin bất thường | (báo cáo) | 5,47% (82 tin) | [chờ dữ liệu thật] |

- **Kiểm chứng với đáp án cài sẵn:**
  - Tìm lại được đủ 3 luật đã cài: {Spring Boot} ⇒ {Java}, {Flutter} ⇒ {Dart}, {React} ⇒ {JavaScript}.
  - Kubernetes và AWS đứng đầu bảng giá trị kỹ năng (+3,51 và +2,09 triệu, đúng hướng với mức cộng +20% và +12% đã cài).
  - Bắt được 18/18 tin bất thường đã cài, với đúng mã lý do.
- **Top 3 luật theo Lift:** [chờ dữ liệu thật].
- **Top 5 kỹ năng tăng lương biên:** [chờ dữ liệu thật].
- **Test:** `pytest tests/unit/test_mining_*.py`: 61 pass. Lệnh `ruff check mining tests/unit/test_mining_*.py` không báo lỗi.

#### 5. Vấn Đề Còn Tồn Đọng
- **Chờ dữ liệu đầu vào:** `features.parquet` và `encoding_dictionary.json` (bước Encoding) cùng bộ golden. Trong lúc chờ, mining tự dựng ma trận kỹ năng từ `skills_extracted` và tự tính TF-IDF.
- **Khoảng k chưa thống nhất:** mục 1 ghi k từ 6 đến 12, checklist ghi từ 4 đến 14. Code đang quét từ 4 đến 14, cấu hình ở `ClusteringParams`.
- **Cần lead xử lý:**
  - `requirements.txt` chưa có `mlxtend`, `shap`, `hdbscan`.
  - `scripts/load_mart_from_parquet.py` biến cột list (antecedents, consequents) đọc từ parquet thành chuỗi.
  - Chưa có bảng mart cho `skill_salary_shap_values`.
- **SHAP không thể hiện quan hệ nhân quả:** một kỹ năng hay đi cùng kỹ năng lương cao (ví dụ CI/CD đi cùng Kubernetes) cũng có φ dương.
- **Thang cấp bậc:** Thực tập và Mới tốt nghiệp bị gộp trong `seniority_level` 0–4. Mining ưu tiên `seniority_ord` (0–5) hoặc nhãn chữ nếu có.
