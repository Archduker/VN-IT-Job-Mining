# ĐẶC TẢ THUẬT TOÁN & PHƯƠNG PHÁP KHAI PHÁ DỮ LIỆU (MINING SPECIFICATION)
## DỰ ÁN: HỆ THỐNG KHAI PHÁ DỮ LIỆU TUYỂN DỤNG IT VIỆT NAM (VN-IT-JOB-MINING)

> **Mã tài liệu:** `SPEC-07`  
> **Phiên bản:** `1.0.0`  
> **Ngày cập nhật:** 05/11/2026  
> **Trạng thái:** Chính thức ban hành  
> **Nền tảng kỹ thuật:** Python 3.10+, Scikit-learn, Mlxtend, SHAP, Scipy, Pandas, PyArrow.

---

## 1. Tổng Quan Kiến Trúc Khai Phá (Mining Architecture Overview)

Giai đoạn Mô hình hóa Khai phá (Data Mining) tiếp nhận dữ liệu đầu vào là ma trận đặc trưng `data/preprocessing/05_encoding/features.parquet` và bộ dữ liệu vàng `data/curated/curated_flat_golden_jobs.parquet` để giải quyết 3 trụ cột kỹ thuật:

```mermaid
flowchart TD
    InFeatures["Dữ Liệu Đầu Vào\nfeatures.parquet & curated_golden.parquet"] --> Engine1
    InFeatures --> Engine2
    InFeatures --> Engine3

    subgraph MiningEngines["3 TRỤ CỘT THUẬT TOÁN KHAI PHÁ DỮ LIỆU"]
        direction TB
        
        subgraph Engine1["1. Khai Phá Mẫu Kỹ Năng Phổ Biến & Luật Kết Hợp"]
            FP["Thuật toán FP-Growth (Frequent Pattern Growth)\n• Xây dựng FP-Tree\n• Sinh Frequent Itemsets\n• Trích xuất Association Rules\n(Support, Confidence, Lift, Conviction)"]
        end

        subgraph Engine2["2. Phân Cụm Công Việc & Khám Phá Nhóm Nghề"]
            CL["Phân Cụm Đa Chiều (K-Means & HDBSCAN)\n• Không gian Kỹ năng (Binary Multi-Hot) + TF-IDF JD\n• Tối ưu k bằng Elbow (WCSS) & Silhouette Analysis\n• HDBSCAN lọc nhiễu & phát hiện Niche Job Roles"]
        end

        subgraph Engine3["3. Mô Hình Hóa Mức Lương & Định Lượng Kỹ Năng"]
            RF["Hồi Quy Phi Tuyến & Giải Thích SHAP\n• Random Forest Regressor dự đoán log(Salary_VND)\n• TreeSHAP tính toán đóng góp biên (Marginal Value)\n• Quy đổi giá trị thặng dư kinh tế từng công nghệ (VNĐ)"]
        end
    end

    Engine1 --> Out1["Bảng Combo Kỹ Năng & Khuyến Nghị ATS"]
    Engine2 --> Out2["Bản Đồ Phân Cụm Công Việc Thị Trường"]
    Engine3 --> Out3["Bảng Định Giá Biên Kỹ Năng (Skill Pricing Matrix)"]
```

---

## 2. Trụ Cột 1: Khai Phá Tập Phổ Biến & Luật Kết Hợp Kỹ Năng (FP-Growth)

### 2.1. Động lực học thuật: Tại sao chọn FP-Growth thay vì Apriori?
Trong bài toán khai phá giỏ thị trường kỹ năng tuyển dụng (Skill Market Basket Analysis), mỗi tin tuyển dụng được xem như một giao dịch ($Transaction$) chứa một tập hợp các kỹ năng ($Items$). 
- **Hạn chế của thuật toán Apriori:** Apriori sử dụng nguyên lý sinh ứng viên tầng bậc ($Candidate\ Generation\ and\ Test$). Với danh mục hơn 300 kỹ năng công nghệ chuẩn hóa, số lượng tập ứng viên $k$-itemsets có thể bùng nổ tổ hợp lên tới $\binom{300}{k} \approx O(2^{|I|})$, đồng thời đòi hỏi quét lại toàn bộ cơ sở dữ liệu sau mỗi vòng lặp $k$. Điều này gây tắc nghẽn bộ nhớ và thời gian thực thi nghiêm trọng.
- **Ưu thế vượt trội của FP-Growth (Frequent Pattern Growth):**
  1. Chỉ quét cơ sở dữ liệu đúng **2 lần**: Lần 1 đếm tần suất đơn lẻ để sắp xếp thứ tự ưu tiên; Lần 2 nén toàn bộ giao dịch vào một cây tiền tố cấu trúc cao (**FP-Tree**).
  2. Không sinh tập ứng viên trung gian: Khai phá trực tiếp các tập phổ biến thông qua việc phân chia cơ sở dữ liệu thành các cơ sở mẫu có điều kiện (**Conditional Pattern Bases**).
  3. Tốc độ thực thi nhanh hơn Apriori từ 10 đến 100 lần trên tập dữ liệu tuyển dụng thưa.

### 2.2. Cơ sở toán học & Các chỉ số đánh giá luật
Gọi $I = \{i_1, i_2, \dots, i_m\}$ là tập hợp tất cả các kỹ năng chuẩn hóa. Cơ sở dữ liệu giao dịch $D = \{T_1, T_2, \dots, T_n\}$, trong đó mỗi giao dịch $T_k \subseteq I$. Một luật kết hợp có dạng:
$$X \Rightarrow Y \quad \text{với } X, Y \subset I \text{ và } X \cap Y = \emptyset$$
Trong đó $X$ là tiền đề (Antecedent) và $Y$ là hệ quả (Consequent).

Chất lượng và độ tin cậy của luật được đo lường thông qua 4 chỉ số thống kê:

#### 1. Độ hỗ trợ (Support)
Tỷ lệ các tin tuyển dụng chứa đồng thời cả tập kỹ năng $X$ và $Y$:
$$Support(X \Rightarrow Y) = P(X \cup Y) = \frac{|\{T \in D \mid (X \cup Y) \subseteq T\}|}{|D|}$$

#### 2. Độ tin cậy (Confidence)
Xác suất có điều kiện một tin tuyển dụng yêu cầu kỹ năng $Y$ khi đã biết tin đó yêu cầu kỹ năng $X$:
$$Confidence(X \Rightarrow Y) = P(Y \mid X) = \frac{Support(X \cup Y)}{Support(X)}$$

#### 3. Độ nâng (Lift)
Tỷ số giữa độ tin cậy thực tế của luật so với độ tin cậy kỳ vọng nếu $X$ và $Y$ hoàn toàn độc lập thống kê:
$$Lift(X \Rightarrow Y) = \frac{P(X \cup Y)}{P(X) \cdot P(Y)} = \frac{Confidence(X \Rightarrow Y)}{Support(Y)}$$
- $Lift = 1$: $X$ và $Y$ hoàn toàn độc lập (xuất hiện cùng nhau chỉ là ngẫu nhiên).
- $Lift < 1$: $X$ và $Y$ có quan hệ thay thế hoặc triệt tiêu lẫn nhau (Negative dependency).
- $Lift > 1$: $X$ và $Y$ có quan hệ tương hỗ mạnh mẽ (Positive dependency). Trong bài toán kỹ năng IT, chỉ chấp nhận các luật có **$Lift \ge 1.2$**.

#### 4. Độ tin chắc (Conviction)
Tỷ số đo lường mức độ sai lệch của luật nếu giả định $X$ và $Y$ độc lập:
$$Conviction(X \Rightarrow Y) = \frac{1 - Support(Y)}{1 - Confidence(X \Rightarrow Y)}$$
- $Conviction = 1$: $X$ và $Y$ độc lập.
- $Conviction \to \infty$: Mọi tin có $X$ đều luôn luôn xuất hiện $Y$ (Luật tất yếu hoàn hảo).

### 2.3. Chiến lược phân tầng ngưỡng Support (Stratified Support Strategy)
Do sự mất cân bằng tần suất tự nhiên giữa các nhóm công nghệ, hệ thống áp dụng chiến lược phân tầng hai cấp độ:
1. **Phân tích Vĩ mô Toàn ngành (Macro Market):** Áp dụng $min\_sup = 0.05$ (5%), $min\_conf = 0.50$ để phát hiện các combo kỹ năng phổ quát cốt lõi (Core Industry Stacks).
2. **Phân tích Vi mô theo Nhóm nghề (Domain Micro Analysis):** Chạy FP-Growth riêng rẽ trên từng phân tập của 12 Job Families với $min\_sup = 0.02$ (2%) để không bỏ sót các combo công nghệ chuyên sâu (ví dụ: trong mảng Data/AI: `{PyTorch, HuggingFace} => {Transformers}`).

---

## 3. Trụ Cột 2: Phân Cụm Công Việc Đa Chiều (Job Clustering: K-Means & HDBSCAN)

### 3.1. Không gian biểu diễn vector (Vector Feature Space)
Mỗi tin tuyển dụng $j$ được ánh xạ thành một vector đặc trưng đa chiều $\mathbf{v}_j = [\mathbf{s}_j \parallel \mathbf{t}_j]$:
- **Ma trận kỹ năng nhị phân $\mathbf{s}_j \in \{0, 1\}^M$:** Đại diện cho sự hiện diện của $M$ kỹ năng chuẩn hóa trong từ điển.
- **Vector ngữ nghĩa văn bản $\mathbf{t}_j \in \mathbb{R}^K$:** Trích xuất từ trường mô tả công việc (JD Text) bằng kỹ thuật **TF-IDF (Term Frequency - Inverse Document Frequency)** kết hợp loại bỏ stopwords tiếng Việt và tiếng Anh kỹ thuật, giữ lại $K = 100$ đặc trưng n-gram quan trọng nhất.
- Vector $\mathbf{v}_j$ được chuẩn hóa theo chuẩn L2: $\|\mathbf{v}_j\|_2 = 1$.

### 3.2. Thuật toán K-Means & Tối ưu hóa số cụm $k$
K-Means phân chia $N$ tin tuyển dụng thành $k$ cụm $C = \{C_1, C_2, \dots, C_k\}$ nhằm tối thiểu hóa tổng bình phương khoảng cách nội cụm (Within-Cluster Sum of Squares - WCSS hay Inertia):
$$J(C) = \sum_{l=1}^k \sum_{\mathbf{v}_j \in C_l} \|\mathbf{v}_j - \boldsymbol{\mu}_l\|^2$$
Trong đó $\boldsymbol{\mu}_l$ là trọng tâm (centroid) của cụm $C_l$.

#### Phương pháp xác định số cụm tối ưu $k \in [3, 15]$:
1. **Phương pháp Điểm gãy (Elbow Method):** Vẽ đồ thị đường cong $J(k)$ theo số cụm $k$. Điểm uốn nơi tốc độ giảm của WCSS chậm lại đáng kể được chọn làm ứng viên.
2. **Phân tích Hệ số Silhouette (Silhouette Analysis):**
   Với mỗi mẫu $i$, gọi $a(i)$ là khoảng cách trung bình từ $i$ đến các mẫu khác trong cùng cụm; $b(i)$ là khoảng cách trung bình từ $i$ đến các mẫu trong cụm gần nhất khác cụm của $i$:
   $$s(i) = \frac{b(i) - a(i)}{\max(a(i), b(i))}, \quad s(i) \in [-1, 1]$$
   Hệ số Silhouette trung bình $\overline{s} = \frac{1}{N} \sum_{i=1}^N s(i)$. Giá trị $k$ tối ưu được chọn là giá trị tối đại hóa $\overline{s}$ và không có cụm nào bị điểm Silhouette âm chiếm đa số.

```mermaid
graph TD
    Data["Vector Không Gian Kỹ Năng + TF-IDF"] --> Loop["Thực Nghiệm k từ 3 đến 15"]
    Loop --> Metric1["Tính Toán WCSS (Elbow)"]
    Loop --> Metric2["Tính Hệ Số Silhouette s(k)"]
    Metric1 --> PickK["Xác Định k Tối Ưu (VD: k = 8 hoặc 12)"]
    Metric2 --> PickK
    PickK --> TrainKM["Huấn Luyện K-Means Cuối Cùng"]
    TrainKM --> Profile["Gán Nhãn Ngữ Nghĩa Cụm (Cluster Profiling)"]
```

### 3.3. Thuật toán HDBSCAN: Phân cụm dựa trên mật độ phân cấp
Nhược điểm của K-Means là giả định các cụm có dạng hình cầu đồng nhất và bắt buộc mọi điểm dữ liệu phải thuộc về một cụm, kể cả dữ liệu nhiễu. Dự án triển khai song song thuật toán **HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise)**:
- **Cơ chế:** Dựa trên khoảng cách tương hỗ (Mutual Reachability Distance) và xây dựng cây khung nhỏ nhất (Minimum Spanning Tree) để tìm các cụm có mật độ tập trung tự nhiên.
- **Xử lý tin lai tạp & ngoại lai:** Các tin tuyển dụng "Fullstack kiêm DevOps kiêm Tester" hoặc các tin viết cẩu thả được HDBSCAN gán nhãn là điểm nhiễu ($Noise = -1$), giúp tinh lọc các cụm nghề cốt lõi có độ thuần khiết (Purity) cao nhất.

---

## 4. Trụ Cột 3: Mô Hình Hóa Mức Lương & Định Lượng Kỹ Năng (Random Forest + SHAP)

### 4.1. Thiết lập bài toán hồi quy định giá lương
Mục tiêu là dự đoán giá trị trung vị của mức lương hàng tháng bằng VNĐ ($Salary\_Midpoint\_VND$). Do phân phối mức lương thực tế bị lệch phải mạnh (Right-skewed), biến mục tiêu được chuẩn hóa logarit:
$$y = \log(1 + Salary\_Midpoint\_VND)$$
Tập đặc trưng đầu vào bao gồm:
$$\mathbf{x} = [\mathbf{s}_{skills}, x_{exp}, \mathbf{x}_{seniority}, \mathbf{x}_{location}, \mathbf{x}_{job\_family}]$$
- $\mathbf{s}_{skills}$: Vector One-Hot/Multi-Hot của các kỹ năng công nghệ.
- $x_{exp}$: Số năm kinh nghiệm yêu cầu (float).
- $\mathbf{x}_{seniority}$: Cấp bậc tuyển dụng (Ordinal/One-Hot: Intern=0, Fresher=1, Junior=2, Middle=3, Senior=4, Lead=5).
- $\mathbf{x}_{location}$: Địa bàn làm việc chính (One-Hot: Hà Nội, TP.HCM, Đà Nẵng, Remote...).
- $\mathbf{x}_{job\_family}$: Nhóm nghề IT (One-Hot của 12 Job Families).

### 4.2. Mô hình Random Forest Regressor
Random Forest được lựa chọn vì những ưu điểm vượt bậc so với Hồi quy Tuyến tính (OLS) hay Mạng Neural trên dữ liệu bảng dạng này:
1. Tự động nắm bắt các mối quan hệ phi tuyến tính và tương tác phức tạp giữa các đặc trưng (ví dụ: Kỹ năng `Kubernetes` đi kèm với `Senior` có giá trị vượt bậc, nhưng đi kèm với `Intern` thì không tác động nhiều).
2. Cơ chế Bagging (Bootstrap Aggregating) kết hợp chọn tập con đặc trưng ngẫu nhiên giúp chống hiện tượng quá khớp (Overfitting) trên các ma trận kỹ năng thưa.
3. Không đòi hỏi giả định phân phối chuẩn nghiêm ngặt đối với các biến độc lập.

Hàm dự đoán là trung bình kết quả của $B$ cây quyết định độc lập:
$$\hat{y}(\mathbf{x}) = \frac{1}{B} \sum_{b=1}^B T_b(\mathbf{x})$$

### 4.3. Định lượng giá trị biên kỹ năng bằng lý thuyết trò chơi SHAP
Để biến mô hình Random Forest từ một "hộp đen" thành công cụ định giá kinh tế minh bạch, hệ thống áp dụng phương pháp **SHAP (SHapley Additive exPlanations)** dựa trên lý thuyết trò chơi hợp tác của Lloyd Shapley (giải Nobel Kinh tế).

#### Công thức tính giá trị Shapley:
Giá trị đóng góp biên $\phi_i$ của đặc trưng (kỹ năng) thứ $i$ được tính bằng giá trị kỳ vọng đóng góp khi thêm $i$ vào tất cả các tập con đặc trưng có thể có $S \subseteq F \setminus \{i\}$:
$$\phi_i(\mathbf{x}) = \sum_{S \subseteq F \setminus \{i\}} \frac{|S|!(|F| - |S| - 1)!}{|F|!} \left[ f_{\mathbf{x}}(S \cup \{i\}) - f_{\mathbf{x}}(S) \right]$$
Trong đó $F$ là toàn bộ tập đặc trưng, và $f_{\mathbf{x}}(S)$ là dự đoán của mô hình khi chỉ có tập đặc trưng $S$.

Mô hình đảm bảo tính chất cộng hoàn hảo (Additive Efficiency):
$$\hat{y}(\mathbf{x}) = \phi_0 + \sum_{i=1}^{|F|} \phi_i(\mathbf{x})$$
Với $\phi_0 = \mathbb{E}[f(\mathbf{x})]$ là giá trị dự đoán cơ sở (trung bình toàn tập dữ liệu).

#### Quy đổi Giá trị Thặng dư Kinh tế (Marginal Dollar Value in VNĐ):
Vì mô hình dự đoán theo thang đo logarit $\log(Salary)$, giá trị SHAP $\phi_i$ của một kỹ năng phản ánh tỷ lệ phần trăm thay đổi mức lương. Mức tăng lương thặng dư biên bằng tiền VNĐ được tính theo công thức:
$$\Delta Salary_i = \mathbb{E}[Salary] \cdot \left( e^{\phi_i} - 1 \right)$$
Ví dụ: Nếu một kỹ sư phần mềm nắm vững kỹ năng `Go` có giá trị SHAP trung bình $\phi_{Go} = +0.12$, với mức lương trung bình thị trường là $25.000.000\text{ VNĐ}$, thì giá trị thặng dư kinh tế biên của kỹ năng `Go` là:
$$\Delta Salary_{Go} = 25.000.000 \cdot (e^{0.12} - 1) \approx 3.187.000\text{ VNĐ/tháng}$$

---

## 5. Thiết Kế Thực Nghiệm & Pipeline Mã Nguồn Tham Chiếu (Reference Pipeline)

Dưới đây là thiết kế module mã nguồn Python chuẩn mực triển khai trọn vẹn 3 thuật toán khai phá:

```python
"""
Module: src/mining/pipeline_runner.py
Mục đích: Thực thi toàn diện chuỗi khai phá dữ liệu VN-IT-Job-Mining
Thư viện: pandas, numpy, scikit-learn, mlxtend, shap
"""

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import fpgrowth, association_rules
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import shap

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class MiningEngine:
    def __init__(self, golden_path: str, features_path: str):
        self.golden_df = pd.read_parquet(golden_path)
        self.features_df = pd.read_parquet(features_path)
        logger.info(f"Loaded Golden DF: {self.golden_df.shape}, Features DF: {self.features_df.shape}")

    # =========================================================================
    # 1. FP-GROWTH: KHAI PHÁ TẬP PHỔ BIẾN & LUẬT KẾT HỢP KỸ NĂNG
    # =========================================================================
    def run_fpgrowth(self, min_support: float = 0.03, min_confidence: float = 0.50):
        logger.info(f"Starting FP-Growth with min_support={min_support}, min_confidence={min_confidence}...")
        
        # Lọc các cột kỹ năng nhị phân (tiền tố 'skill_')
        skill_cols = [c for c in self.features_df.columns if c.startswith("skill_")]
        skill_df = self.features_df[skill_cols].astype(bool)
        # Đổi tên cột bỏ tiền tố 'skill_' để báo cáo trực quan
        skill_df.columns = [c.replace("skill_", "") for c in skill_cols]

        # 1. Sinh tập phổ biến bằng FP-Growth
        frequent_itemsets = fpgrowth(skill_df, min_support=min_support, use_colnames=True)
        frequent_itemsets["length"] = frequent_itemsets["itemsets"].apply(lambda x: len(x))
        logger.info(f"Generated {len(frequent_itemsets)} frequent itemsets.")

        # 2. Sinh luật kết hợp
        rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=min_confidence)
        # Lọc luật chất lượng cao với Lift >= 1.2
        high_lift_rules = rules[rules["lift"] >= 1.2].sort_values(by="lift", ascending=False)
        logger.info(f"Extracted {len(high_lift_rules)} association rules with Lift >= 1.2.")

        return frequent_itemsets, high_lift_rules

    # =========================================================================
    # 2. K-MEANS: PHÂN CỤM CÔNG VIỆC TRÊN KHÔNG GIAN KỸ NĂNG
    # =========================================================================
    def run_job_clustering(self, max_k: int = 12):
        logger.info("Executing K-Means Clustering on Skill Features Space...")
        skill_cols = [c for c in self.features_df.columns if c.startswith("skill_")]
        X = self.features_df[skill_cols].values

        metrics = []
        best_k = 3
        best_score = -1.0

        for k in range(3, max_k + 1):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(X)
            sil = silhouette_score(X, labels, sample_size=2000, random_state=42)
            metrics.append({"k": k, "inertia": float(km.inertia_), "silhouette": float(sil)})
            logger.info(f"Evaluated k={k}: Inertia={km.inertia_:.2f}, Silhouette={sil:.4f}")

            if sil > best_score:
                best_score = sil
                best_k = k

        # Huấn luyện mô hình tối ưu
        final_km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
        self.features_df["cluster_label"] = final_km.fit_predict(X)
        logger.info(f"Optimal cluster selected: k={best_k} (Silhouette: {best_score:.4f})")

        return pd.DataFrame(metrics), final_km

    # =========================================================================
    # 3. RANDOM FOREST + SHAP: HỒI QUY ĐỊNH GIÁ LƯƠNG & GIÁ TRỊ BIÊN
    # =========================================================================
    def run_salary_valuation(self):
        logger.info("Training Random Forest Regressor & Computing TreeSHAP values...")
        
        # Chỉ lấy các tin có mức lương cụ thể
        salary_mask = self.features_df["salary_midpoint_vnd"].notnull() & (self.features_df["salary_midpoint_vnd"] > 0)
        df_valid = self.features_df[salary_mask].copy()
        
        # Biến mục tiêu chuẩn hóa logarit
        y = np.log1p(df_valid["salary_midpoint_vnd"].values)
        
        # Tập biến độc lập
        feature_cols = [c for c in df_valid.columns if c.startswith(("skill_", "exp_", "sen_", "loc_", "jf_"))]
        X = df_valid[feature_cols]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        rf = RandomForestRegressor(n_estimators=150, max_depth=15, random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train)

        # Đánh giá trên tập test
        y_pred = rf.predict(X_test)
        mae = mean_absolute_error(np.expm1(y_test), np.expm1(y_pred))
        r2 = r2_score(y_test, y_pred)
        logger.info(f"Salary Model Trained -> MAE: {mae:,.0f} VND, R2 Score: {r2:.4f}")

        # Tính toán giá trị TreeSHAP
        explainer = shap.TreeExplainer(rf)
        shap_values = explainer.shap_values(X_test)

        # Tính toán giá trị thặng dư biên trung bình của từng kỹ năng
        mean_base_salary = np.mean(np.expm1(y_train))
        shap_importance = pd.DataFrame({
            "feature": feature_cols,
            "mean_shap_value": np.mean(shap_values, axis=0),
            "abs_mean_shap": np.mean(np.abs(shap_values), axis=0)
        })
        shap_importance["marginal_dollar_vnd"] = mean_base_salary * (np.exp(shap_importance["mean_shap_value"]) - 1)
        shap_importance = shap_importance.sort_values(by="abs_mean_shap", ascending=False)

        return rf, shap_importance, {"mae_vnd": mae, "r2": r2}
```
