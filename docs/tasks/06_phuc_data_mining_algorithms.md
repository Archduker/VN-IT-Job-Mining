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

Phúc chịu trách nhiệm về "Bộ não tri thức" của toàn bộ đồ án tốt nghiệp: Triển khai bộ ba thuật toán Khai phá Dữ liệu học thuật chuẩn mực để chuyển đổi dữ liệu dạng bảng thành những hiểu biết thị trường (Market Intelligence) có giá trị thực tiễn cho sinh viên IT:

1. **Thuật Toán 1 — Khai Phá Luật Kết Hợp Kỹ Năng (FP-Growth Association Rule Mining):**
   - *Mục tiêu:* Tìm ra các "Combo kỹ năng" luôn đi kèm với nhau trong yêu cầu tuyển dụng (ví dụ: học React thì bắt buộc phải biết TypeScript và Next.js).
   - *Thuật toán:* Dùng `fpgrowth` và `association_rules` từ thư viện `mlxtend`.
   - *Ngưỡng tham số:*
     * Ngưỡng Support vĩ mô: $min\_sup = 0.05$ (toàn thị trường) và vi mô $min\_sup = 0.02$ (theo từng nhóm nghề).
     * Ngưỡng chất lượng luật: $Confidence \ge 0.60$ và $Lift > 1.20$ (chứng minh mối quan hệ tương hỗ thật sự, không phải ngẫu nhiên).
2. **Thuật Toán 2 — Phân Cụm Vị Trí Nghề Nghiệp Khách Quan (K-Means Clustering + PCA):**
   - *Mục tiêu:* Khám phá các cụm nghề nghiệp tự nhiên của thị trường dựa trên không gian vector kỹ năng và TF-IDF mô tả công việc (không bị bó hẹp bởi tiêu đề do nhà tuyển dụng tự đặt).
   - *Tối ưu hóa:* Dùng phương pháp Elbow (WCSS/Inertia) và Silhouette Analysis để tìm số cụm tối ưu ($k \in [6, 12]$) đối chiếu với 12 Job Family.
   - *Trực quan hóa:* Chiếu giảm chiều xuống không gian 2D bằng thuật toán **PCA** (Principal Component Analysis) để phục vụ vẽ biểu đồ phân tán cụm trên Dashboard.
3. **Thuật Toán 3 — Hồi Quy Dự Báo Lương & Định Lượng Giá Trị Kỹ Năng (Random Forest Regressor + TreeSHAP):**
   - *Mục tiêu:* Trả lời câu hỏi quan trọng nhất của sinh viên: "Kỹ năng nào có giá trị đẩy mức lương lên cao nhất?".
   - *Dữ liệu huấn luyện:* Huấn luyện trên Subset có khoảng lương số cụ thể (~45% tin). Áp dụng hàm $\log(1 + \text{salary\_avg})$ để khắc phục độ lệch phải của phân phối lương.
   - *Biến giải thích ($X$):* Số năm kinh nghiệm, Cấp bậc (Seniority), Địa phương (Hà Nội, TP.HCM, Khác) và 230 biến nhị phân kỹ năng.
   - *Giải thích mô hình (Explainable AI - XAI):* Áp dụng **TreeSHAP** (`shap.TreeExplainer`) từ lý thuyết trò chơi hợp tác để tính toán đóng góp biên (Marginal Contribution) của từng kỹ năng:
     $$\Delta \text{Salary}_{\text{VND}}(i) \approx \text{Baseline Salary} \times \left( e^{\phi_i} - 1 \right)$$
     Chỉ ra cụ thể: Thành thạo Docker giúp lương tăng thêm bao nhiêu triệu VNĐ/tháng so với mặt bằng chung cùng số năm kinh nghiệm.

---

## 2. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Phúc làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Nhà Khoa Học Dữ Liệu (Data Scientist & Mining Specialist) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là triển khai trọn vẹn Bộ ba thuật toán Khai phá Dữ liệu học thuật: (1) FP-Growth trích xuất luật kết hợp kỹ năng (Support, Confidence, Lift); (2) K-Means + PCA phân cụm vị trí việc làm (Silhouette Score); (3) Random Forest Regressor + TreeSHAP mô hình hóa mức lương và định lượng giá trị kinh tế biên của từng kỹ năng. Tham khảo đặc tả kỹ thuật tại docs/spec/07_mining_spec.md và docs/spec/08_evaluation_spec.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Chỉ được can thiệp vào mã nguồn trong thư mục: `mining/`.
- Sử dụng các thư viện chuẩn mực: `mlxtend`, `scikit-learn`, `shap`, `pandas`, `numpy`.
- Mô hình lương chỉ huấn luyện trên các tin có mức lương cụ thể (loại bỏ tin Thỏa thuận), dùng K-Fold Cross Validation (5 folds) để đánh giá.
- Xuất kết quả luật kết hợp, nhãn phân cụm và giá trị SHAP ra định dạng Parquet/JSON tại `mining/artifacts/` để nạp vào PostgreSQL Data Mart và hiển thị biểu đồ trên Dashboard.

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào:
  * `data/curated/curated_flat_golden_jobs.parquet` (Dữ liệu tuyển dụng vàng)
  * `data/preprocessing/05_encoding/features.parquet` (Ma trận 230 cột kỹ năng)
- Đầu ra tại `mining/artifacts/`:
  * `skill_association_rules.parquet` (Bảng luật kết hợp FP-Growth)
  * `job_clusters.parquet` (Tọa độ PCA 2D và nhãn cụm K-Means)
  * `skill_salary_shap_values.parquet` (Giá trị thặng dư kinh tế từng kỹ năng)
  * `trained_salary_rf_model.joblib` (Mô hình Random Forest đã lưu)

### 4. YÊU CẦU THỰC HIỆN:
Hãy phân tích mã nguồn mẫu trong docs/spec/07_mining_spec.md, lập Plan thực thi lần lượt 3 thuật toán, chạy thực nghiệm và xuất các chỉ số đánh giá toán học (Lift, Silhouette, R2, MAE).
```

---

## 3. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [ ] **Bước 1 (FP-Growth):**
  * Chạy thuật toán FP-Growth, trích xuất ít nhất 30 luật kết hợp có $Lift > 1.2$ và $Confidence \ge 0.6$.
  * Kiểm tra tính hợp lý thực tế: Các luật tìm được phải mang ý nghĩa công nghệ rõ ràng (ví dụ: `{Flutter} => {Dart}`, `{Kubernetes, Docker} => {CI/CD}`).
- [ ] **Bước 2 (K-Means & Silhouette):**
  * Chạy vẽ đồ thị Elbow (Inertia) và Silhouette Score cho $k \in [4, 14]$.
  * Chọn $k$ tối ưu có Silhouette Score cao nhất (mục tiêu: $\ge 0.28$).
  * Chạy PCA 2D, lưu tọa độ $(x, y)$ và nhãn cụm của từng bài đăng.
- [ ] **Bước 3 (Random Forest & SHAP):**
  * Huấn luyện mô hình Random Forest trên tập tin có lương: Đạt $R^2 \ge 0.60$ và $MAE \le 4.5\text{ triệu VNĐ}$ trên tập kiểm thử (Test Set 20%).
  * Chạy TreeSHAP tính ma trận $\phi_{i, j}$; tổng hợp Top 15 kỹ năng có giá trị tăng lương cao nhất thị trường.
- [ ] **Bước 4 (Chạy toàn trình Mining):**
  ```bash
  python mining/run_mining_pipeline.py
  ```
  Xác nhận tất cả 4 tệp artifacts trong `mining/artifacts/` được sinh ra đầy đủ.
- [ ] **Bước 5 (Linting):** Chạy `ruff check mining/`.

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
