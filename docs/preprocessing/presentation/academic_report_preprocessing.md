# BÁO CÁO KHOA HỌC: QUY TRÌNH TIỀN XỬ LÝ DỮ LIỆU ĐA NGUỒN & XÂY DỰNG BỘ DỮ LIỆU VÀNG (GOLDEN MASTER DATASET)
## Đề án: Khai Phá Thị Trường Lao Động IT & Nhu Cầu Kỹ Năng Nghề Nghiệp Tại Việt Nam (VN-IT-Job-Mining)

> **Môn học:** Khai phá Dữ liệu (Data Mining) & Khoa học Dữ liệu (Data Science)  
> **Bộ dữ liệu thực nghiệm:** 10,024 bản ghi thô từ 8 sàn tuyển dụng $\rightarrow$ 8,967 bản ghi Bộ Dữ Liệu Vàng  
> **Trạng thái kiểm định chất lượng:** **PASSED (5/5 Check Suites - 100% PURE JSON RFC 8259)**

---

## MỤC LỤC TỔNG QUAN
1. [Chương 1: Đặt Vấn Đề & Bối Cảnh Nghiên Cứu](#chương-1-đặt-vấn-đề--bối-cảnh-nghiên-cứu)
2. [Chương 2: Khung Kiến Trúc Tiền Xử Lý & Ma Trận Ranh Giới Đanh Thép](#chương-2-khung-kiến-trúc-tiền-xử-lý--ma-trận-ranh-giới-đanh-thép)
3. [Chương 3: Cơ Sở Toán Học & Phương Pháp Thống Kê Chuyên Sâu](#chương-3-cơ-sở-toán-học--phương-pháp-thống-kê-chuyên-sâu)
4. [Chương 4: Hiện Thực Hóa Kỹ Thuật & Các Module Đột Phá](#chương-4-hiện-thực-hóa-kỹ-thuật--các-module-đột-phá)
5. [Chương 5: Báo Cáo Thực Nghiệm & Kiểm Định Chất Lượng QA Pipeline](#chương-5-báo-cáo-thực-nghiệm--kiểm-định-chất-lượng-qa-pipeline)
6. [Chương 6: Kết Luận & Định Hướng Giai Đoạn Khai Phá Hạ Nguồn](#chương-6-kết-luận--định-hướng-giai-đoạn-khai-phá-hạ-nguồn)

---

## Chương 1: Đặt Vấn Đề & Bối Cảnh Nghiên Cứu

### 1.1. Thực Trạng Thị Trường Việc Làm IT Việt Nam
Thị trường Công nghệ Thông tin (IT) tại Việt Nam đang trải qua giai đoạn chuyển dịch cơ cấu mạnh mẽ với sự hội tụ của Điện toán đám mây, Trí tuệ nhân tạo (AI/GenAI) và Phát triển phần mềm hiện đại. Tuy nhiên, việc nắm bắt bức tranh toàn cảnh về nhu cầu tuyển dụng, cơ cấu mức lương và yêu cầu kỹ năng thực tế vẫn gặp nhiều rào cản do dữ liệu bị phân mảnh trên nhiều sàn tuyển dụng trực tuyến khác nhau.

Để giải quyết bài toán này, dự án **VN-IT-Job-Mining** được thiết kế nhằm thu thập, chuẩn hóa và khai phá dữ liệu việc làm IT trên diện rộng, hướng tới 5 mục tiêu nghiệp vụ chiến lược:
* **SD1 — Labor Market Data Integration:** Thu thập thô nguyên bản từ 8 sàn tuyển dụng hàng đầu (TopCV, TopDev, VietnamWorks, ITviec, CareerViet, Vieclam24h, Glints, JobsGO), xử lý phiên bản thay đổi (CDC), làm sạch và hợp nhất thành Bảng Phẳng Chuẩn Vàng (Golden Master Dataset).
* **SD2 — Occupational Demand Analysis:** Phân tích nhu cầu ngành nghề: phân loại vào 12 Job Family chuẩn IT và 7 cấp bậc Seniority (`intern` đến `manager`).
* **SD3 — Skill Intelligence:** Khai phá trí tuệ kỹ năng: phân loại 3 lớp (Hard/Soft/Domain skills), lập ma trận đồng xuất hiện (Co-occurrence Matrix) và phân tích luật kết hợp FP-Growth.
* **SD4 — Education–Industry Skill Gap Analysis:** Đối chiếu giữa chuẩn đầu ra của khối ngành CNTT tại các trường Đại học với yêu cầu thực tế của nhà tuyển dụng.
* **SD5 — Career & Skill Development Recommendations:** Dự báo kỹ năng mới nổi (Emerging Skills) và đề xuất lộ trình nâng cao năng lực cho người học.

### 1.2. Vị Trí Cốt Lõi Của Tiền Xử Lý Dữ Liệu
Trong quy trình Khai phá Tri thức từ Dữ liệu (KDD), chất lượng của mô hình khai phá phụ thuộc trực tiếp vào chất lượng của dữ liệu đầu vào (*"Garbage In, Garbage Out"*). Dữ liệu tuyển dụng IT cào từ web (Web-scraped data) tồn tại những khiếm khuyết nghiêm trọng:
1. **Dị thể cấu trúc (Structural Heterogeneity):** 8 sàn sử dụng 8 cấu trúc lưu trữ hoàn toàn khác biệt (JSON API phân cấp, DOM table chuỗi, JSON-LD ngầm).
2. **Nhiễu dữ liệu & Lương ẩn (Hidden Salaries):** Trên 65% bài đăng ghi mức lương "Thỏa thuận" ở phần tổng quan, nhưng thực tế mức lương lại được ghi ngầm trong phần văn bản mô tả (JD).
3. **Giá trị khuyết thiếu giả tạo (Sneaky Nulls):** Sàn sử dụng chuỗi văn bản `"thỏa thuận"`, `"cạnh tranh"`, số `0`, hoặc mảng rỗng `[]` thay cho giá trị null thực sự, làm vô hiệu hóa các công cụ kiểm tra dữ liệu tiêu chuẩn.
4. **Ngoại lai do bóc tách sai lệch (Extraction Artifacts):** Lỗi nhận diện nhầm số điện thoại liên hệ thành mức lương hàng trăm triệu đồng, hoặc nhầm ký tự che giấu `1*** USD` thành mức lương 25,400 VND.
5. **Trùng lặp xuyên sàn (Cross-platform Duplication):** Cùng một vị trí tuyển dụng được một doanh nghiệp đăng tải đồng thời trên nhiều sàn khác nhau với câu từ bị biến tấu.

Do đó, giai đoạn Tiền xử lý dữ liệu (Preprocessing) không đơn thuần là việc làm sạch bề mặt bằng các câu lệnh pandas cơ bản, mà phải là một **Hệ thống Kỹ thuật Dữ liệu Hoàn Chỉnh (Data Engineering Pipeline)** được trang bị đầy đủ cơ sở toán học, mô hình thống kê và thuật toán thông minh để tạo ra **Bộ Dữ Liệu Vàng (Golden Master Dataset)**.

---

## Chương 2: Khung Kiến Trúc Tiền Xử Lý & Ma Trận Ranh Giới Đanh Thép

### 2.1. Kiến Trúc Pipeline 4 Giai Đoạn Nâng Cấp ELT
Khác với mô hình ETL truyền thống (vốn làm sạch dữ liệu ngay trong quá trình cào), đề án áp dụng triệt để mô hình **Modern ELT (Extract - Load - Transform)** kết hợp quy trình chuẩn **CRISP-DM**:
* Dữ liệu cào về được đóng gói bất biến dạng `RawJobEnvelope` (Zero Information Loss).
* Đường ống tiền xử lý hoạt động độc lập tuyệt đối với 4 giai đoạn nối tiếp có vòng lặp phản hồi:

```text
+----------------------------------------------------------------------------------------------------+
|                         BẢN ĐỒ TỔNG THỂ ĐƯỜNG ỐNG TIỀN XỬ LÝ (PREPROCESSING PIPELINE)              |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ĐẦU VÀO]: 10,024 bản ghi thô nguyên bản từ 8 sàn (data/transformation/raw_for_outlier.json)      |
|                                     │                                                              |
|                                     ▼                                                              |
|  [GIAI ĐOẠN 1: INTEGRATION - TÍCH HỢP SCHEMA & ÉP PHẲNG JSON]                                      |
|  * Recursive JSON Flattener: Ép phẳng cấu trúc lồng nhau 8 sàn về bảng Staging duy nhất.           |
|  * Khóa định danh toàn cục: job_id_global = <source_platform>_<source_job_id>.                     |
|  * Ánh xạ Canonical 8 nhóm thuộc tính nghiệp vụ. Thuần túy Deterministic logic (Zero AI).          |
|                                     │                                                              |
|                                     ▼                                                              |
|  [GIAI ĐOẠN 2: TRANSFORMATION - CHUYỂN HÓA KIỂU & BÓC TÁCH LƯƠNG CASCADE]                          |
|  * Cascade Salary Parser: Header Regex -> JD Regex Scanner (bóc lương ẩn) -> Annual Normalizer.     |
|  * Quy đổi ngoại tệ: USD (25,400 cố định), SGD (API Frankfurter tỷ giá lịch sử chéo theo ngày).    |
|  * Ép kiểu định lượng: float, int, datetime ISO 8601 YYYY-MM-DD.                                   |
|                                     │                                                              |
|                                     ▼                                                              |
|  [GIAI ĐOẠN 3: MISSING & OUTLIERS - BÓC TRẦN NULL TRÁ HÌNH & WINSORIZATION]                         |
|  * Bóc trần 9+ Sneaky Null Markers; bảo vệ cờ is_salary_negotiable = True (cơ chế MNAR).           |
|  * Cyclic Feedback Loop & Heuristic Scrubber: Khắc phục nhầm lẫn số điện thoại / chuỗi che giấu.   |
|  * Kiểm định khoảng tứ phân vị IQR & Winsorization tại P1 - P99 (Zero Record Loss Policy).         |
|                                     │                                                              |
|                                     ▼                                                              |
|  [GIAI ĐOẠN 3.5: GEMINI ALL-IN-ONE AGENT & MARKET ANCHOR PREDICTION]                               |
|  * Gemini 1.5 Flash: Phân loại kỹ năng 3 lớp (Hard/Soft/Domain), bổ sung yêu cầu, dịch thuật.      |
|  * Market Anchor Calculator: Khung mỏ neo 4 cấp [Platform x Seniority] triệt tiêu ảo giác (Zero-Null)|
|  * Resumable Checkpoint Store: Tự phục hồi tiến trình từng dòng JSONL khi ngắt quãng mạng/quota.   |
|                                     │                                                              |
|                                     ▼                                                              |
|  [GIAI ĐOẠN 4: DEEP NORMALIZATION & TARGET SCHEMA 11 KEYS]                                         |
|  * Khử trùng lặp thực thể xuyên sàn (Entity Resolution): Blocking -> Cosine Sim >= 0.82.          |
|  * Target Schema Formatter: Chuẩn hóa chính xác 11 root keys, loại bỏ 100% cột thô raw_* và cờ rác.|
|  * Đóng gói đầu ra: data/curated/golden_master.json (8,967 bản ghi Golden Master).                 |
|                                     │                                                              |
|                                     ▼                                                              |
|  [GIAI ĐOẠN 5: KIỂM ĐỊNH CHẤT LƯỢNG QA PIPELINE AUDIT (5/5 PASSED)]                                |
|  * Check 1: Dòng dõi & Lưu vết File  * Check 2: 100% PURE JSON RFC 8259 (Zero NaN)                |
|  * Check 3: Golden Master Contract   * Check 4: Domain Groups & MNAR   * Check 5: QR1-QR5 Quality  |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 2.2. Ma Trận Ranh Giới Đanh Thép (Ironclad Boundaries Matrix)
Để ngăn chặn hiện tượng rò rỉ chức năng (scope creep) hoặc agent tự ý can thiệp sai giai đoạn, hệ thống áp dụng khế ước ranh giới bất biến:

| Giai Đoạn | Trách Nhiệm Duy Nhất | ĐƯỢC PHÉP LÀM (DO) | TUYỆT ĐỐI CẤM (DO NOT DO) | Ứng Dụng AI / LLM |
| :--- | :--- | :--- | :--- | :--- |
| **GĐ 1: Integration** | Đồng nhất cấu trúc đa sàn về bảng phẳng Staging | - Đọc `RawJobEnvelope`<br>- Ép phẳng JSON lồng nhau<br>- Sinh `job_id_global`<br>- Ánh xạ 8 nhóm trường | - CẤM bóc tách dải lương số<br>- CẤM quy đổi tiền tệ<br>- CẤM drop dòng<br>- CẤM fillna | **TUYỆT ĐỐI KHÔNG** (Pure Deterministic) |
| **GĐ 2: Transformation** | Bóc tách kiểu định lượng & trích xuất lương | - Regex bóc lương Header & JD text<br>- Quy đổi USD/SGD sang VND<br>- Ép kiểu float/int/datetime<br>- Chia lương năm về tháng (/12) | - CẤM xóa dòng outlier<br>- CẤM điền mean/median vào ô null<br>- CẤM log-transform sớm | Hỗ trợ fallback bóc tách regex câu phức tạp |
| **GĐ 3: Missing & Outlier** | Bóc trần null giả mạo, chặn ngoại lai | - Bóc trần 9+ sneaky null markers<br>- Bảo toàn cờ `is_negotiable=1`<br>- Heuristic Scrubber sửa sai regex<br>- Winsorization tại $P_1$ và $P_{99}$ | - CẤM fill mean vào lương thỏa thuận<br>- CẤM xóa bỏ dòng (Zero Record Loss)<br>- CẤM gán số thiếu căn cứ | Heuristic Scrubber kết hợp Pilot đối chứng |
| **GĐ 3.5: Gemini Agent** | Làm giàu ngữ nghĩa & dự đoán lương neo | - Phân loại 3-tier skills (Hard/Soft/Domain)<br>- Bổ sung học vấn, làm thứ 7<br>- Dự đoán lương neo [Platform x Seniority]<br>- Dịch thuật JD tiếng Anh sang tiếng Việt | - CẤM dự đoán không có mỏ neo<br>- CẤM chạy không có Checkpoint<br>- CẤM bỏ qua lỗi schema | **TRỌNG TÂM:** Gemini 1.5 Flash có khống chế mỏ neo |
| **GĐ 4: Normalization** | Khử trùng lặp & đóng gói Target Schema | - Blocking theo công ty & tỉnh thành<br>- Cosine Similarity $\ge 0.82$<br>- Đóng gói 11 Root Keys<br>- Loại bỏ 100% cột `raw_*` và cờ tạm | - CẤM giữ lại các trường trung gian<br>- CẤM lưu các đối tượng legacy | Zero-shot classification nếu có |

---

## Chương 3: Cơ Sở Toán Học & Phương Pháp Thống Kê Chuyên Sâu

### 3.1. Phân Tích Cơ Chế Khuyết Thiếu Dữ Liệu (Missing Data Mechanisms)
Trong lý thuyết thống kê của Rubin (1976), dữ liệu khuyết thiếu được phân loại thành 3 cơ chế:
1. **MCAR (Missing Completely At Random):** Xác suất một quan sát bị khuyết hoàn toàn độc lập với cả biến quan sát được và biến chưa quan sát được ($P(M | Y_{obs}, Y_{mis}) = P(M)$).
2. **MAR (Missing At Random):** Xác suất khuyết thiếu phụ thuộc vào các biến quan sát được khác nhưng không phụ thuộc vào chính giá trị bị khuyết ($P(M | Y_{obs}, Y_{mis}) = P(M | Y_{obs})$).
3. **MNAR (Missing Not At Random):** Xác suất khuyết thiếu phụ thuộc trực tiếp vào chính giá trị của biến đó ($P(M | Y_{obs}, Y_{mis}) = P(M | Y_{mis})$).

**Ý nghĩa thực tiễn trong VN-IT-Job-Mining:**
* Mức lương "Thỏa thuận" trong tuyển dụng IT Việt Nam là một trường hợp kinh điển của **MNAR**: Doanh nghiệp chủ động che giấu mức lương đối với các vị trí tuyển dụng cấp cao (Senior/Lead) để tối ưu hóa chi phí đàm phán, hoặc che giấu mức lương thấp đối với các vị trí entry-level để thu hút hồ sơ ứng tuyển.
* **Sai lầm học thuật phổ biến:** Rất nhiều nghiên cứu áp dụng các phương pháp đơn giản như Mean Imputation hoặc Median Imputation lên cột lương. Việc này vi phạm nghiêm trọng giả định thống kê, làm co cụm phương sai nhân tạo ($\text{Var}(Y) \downarrow$), bóp méo hình dạng phân phối và dẫn tới các kết luận thiên lệch (biased estimates).
* **Giải pháp của đề án:** Nhóm bảo toàn trạng thái khuyết thiếu có chủ đích bằng cờ nhị phân `is_salary_negotiable = True` để mô hình hóa hành vi thỏa thuận như một đặc trưng độc lập, đồng thời chỉ áp dụng dự đoán lương có kiểm soát qua mô hình mỏ neo thị trường kết hợp GenAI ở một trường riêng biệt (`salary_source = 'predicted'`).

### 3.2. Phương Pháp Kiểm Định Ngoại Lai IQR & Kỹ Thuật Winsorization
Dữ liệu mức lương tuyển dụng trên thực tế luôn tồn tại các giá trị cực đoan do sai số nhập liệu của nhà tuyển dụng hoặc sai số của bộ parser (ví dụ: bóc nhầm số điện thoại).

#### Nhận Diện Ngoại Lai Bằng Khoảng Tứ Phân Vị (IQR)
Khoảng tứ phân vị được xác định thông qua phân vị thứ nhất ($Q_1$ hay $P_{25}$) và phân vị thứ ba ($Q_3$ hay $P_{75}$):
$$\text{IQR} = Q_3 - Q_1$$
Các ranh giới ngoại lai của Tukey được xác lập:
$$\text{Lower Fence} = Q_1 - 1.5 \times \text{IQR}$$
$$\text{Upper Fence} = Q_3 + 1.5 \times \text{IQR}$$

#### Kỹ Thuật Winsorization & Chính Sách Không Mất Bản Ghi (Zero Record Loss Policy)
Trong giáo trình khai phá dữ liệu cơ bản, giải pháp thông thường khi gặp ngoại lai là **loại bỏ bản ghi (Trimming / Dropping rows)**. Tuy nhiên, trong đề án VN-IT-Job-Mining, chính sách xóa dòng cơ học bị bác bỏ dựa trên **Phân tích Căn nguyên Ngoại lai (Root Cause Analysis)**:
1. **Ngoại lai cao (High Outliers - 100M - 250M VND):** Xuất phát từ các vị trí cấp cao (**Senior Lead, Tech Lead, Solution Architect, Director, CTO**) hoặc các doanh nghiệp FDI công nghệ chi trả đãi ngộ lớn bằng ngoại tệ. Đây là dữ liệu thực tế cực kỳ giá trị, phản ánh đúng trần thu nhập của thị trường IT Việt Nam. Nếu xóa dòng, ta sẽ làm mất toàn bộ mẫu của nhóm nhân sự tinh hoa này và bóp méo kết quả phân tích cấp bậc ở mục tiêu SD2.
2. **Ngoại lai thấp (Low Outliers - 1M - 4M VND):** Xuất phát từ các vị trí **Intern / Thực tập sinh** nhận tiền hỗ trợ phụ cấp thực tập hoặc sinh viên làm part-time. Đây là giá trị thực tế hợp lệ ở phân khúc nhập môn, phản ánh đúng đối tượng nghiên cứu sinh viên mới tốt nghiệp ở mục tiêu SD4.
3. **Ngoại lai do Lỗi Kỹ thuật / Tin rác (Noise & Extraction Artifacts):** Xuất phát từ việc bóc nhầm số điện thoại (ví dụ: `0243...` thành 243 triệu) hoặc ký tự ẩn (`1*** USD`). Đối với trường hợp này, hệ thống sử dụng **Heuristic Scrubber** để reset trường lương về `null` và bật cờ `is_salary_negotiable = True` chứ **vẫn không xóa dòng**, bởi vì bài đăng đó vẫn chứa đầy đủ danh mục Kỹ năng công nghệ (Hard Skills) mà thị trường đang tìm kiếm.

Do đó, nhóm áp dụng **Kỹ thuật Winsorization tại phân vị 1% ($P_1$) và 99% ($P_{99}$)**. Mọi giá trị mức lương $y_i$ được biến đổi theo hàm chặn:
$$\widetilde{y}_i = \begin{cases} 
P_{1}, & \text{nếu } y_i < P_{1} \\
y_i, & \text{nếu } P_{1} \le y_i \le P_{99} \\
P_{99}, & \text{nếu } y_i > P_{99} 
\end{cases}$$
Qua thực nghiệm, kỹ thuật này đã khống chế dải lương trong khoảng an toàn từ **4,000,000 VND đến 120,000,000 VND/tháng**, triệt tiêu toàn bộ ảnh hưởng của các điểm cực trị mà vẫn **bảo toàn 100% số lượng bản ghi** cho toàn hệ thống.

### 3.3. Biến Đổi Phân Phối Phi Tuyến (Log-Transformation)
Phân phối mức lương trong thị trường lao động luôn có hiện tượng **lệch phải rất nặng (Positive Skewness)** do phần lớn các vị trí tập trung ở khoảng lương phổ thông (10M - 35M VND), trong khi một số ít vị trí cấp cao kéo dài đuôi phân phối về phía bên phải.

Hệ số độ lệch (Skewness) được tính bằng mô-men chuẩn hóa bậc ba:
$$\gamma_1 = \mathbb{E}\left[\left(\frac{Y - \mu}{\sigma}\right)^3\right] = \frac{\sum_{i=1}^N (y_i - \bar{y})^3}{(N - 1) s^3}$$
* Trên tập dữ liệu thô ban đầu, độ lệch của mức lương đạt $\gamma_1 > 5.8$, vi phạm nghiêm trọng giả định về phân phối chuẩn của các mô hình tuyến tính, K-Means và mạng nơ-ron.
* Nhóm áp dụng phép biến đổi Log-transform cơ số tự nhiên:
  $$y_{\text{log}} = \ln(1 + y)$$
* **Kết quả:** Độ lệch Skewness sau biến đổi giảm xuống còn $\gamma_1 = 0.42$ (nằm hoàn hảo trong khoảng $[-0.5, 0.5]$), đưa phân phối lương về dạng gần chuẩn đối xứng (Approximately Normal Distribution).

### 3.4. Mô Hình Không Gian Vector & Khoảng Cách Cosine Trong Khử Trùng Lặp
Bài toán Khử trùng lặp thực thể xuyên sàn (Cross-Platform Entity Resolution) nhằm phát hiện xem hai bài đăng tuyển dụng $d_A$ (trên sàn A) và $d_B$ (trên sàn B) có cùng mô tả một vị trí công việc thực tế hay không.

#### Kỹ Thuật Phân Cụm Lọc Thô (Blocking)
Nếu so sánh cặp đôi toàn bộ $N = 10,024$ bản ghi, số lượng phép so sánh sẽ là:
$$\binom{N}{2} = \frac{N(N - 1)}{2} \approx 50.2 \times 10^6 \text{ phép tính}$$
Chi phí tính toán $\mathcal{O}(N^2)$ là quá lớn. Nhóm áp dụng cơ chế **Blocking**:
$$\text{Block}(d) = \langle\text{normalize\_company}(d.\text{company}), \text{normalize\_city}(d.\text{location})\rangle$$
Chỉ những bài đăng nằm trong cùng một Block (cùng công ty đã chuẩn hóa chuỗi và cùng tỉnh thành) mới được đưa vào bước so khớp sâu. Kỹ thuật này giảm số phép tính toán xuống dưới 1% tổng số cặp ban đầu.

#### So Khớp Ngữ Nghĩa Qua Vector Nhúng & Cosine Similarity
Văn bản mô tả công việc (JD) của mỗi bài đăng được mã hóa thành một vector đặc trưng ngữ nghĩa $\mathbf{u}, \mathbf{v} \in \mathbb{R}^d$ thông qua mô hình ngôn ngữ Sentence-Transformer (`all-MiniLM-L6-v2` hoặc Gemini Embeddings). Độ tương đồng ngữ nghĩa được xác định bởi góc giữa hai vector trong không gian nhiều chiều:
$$\text{Cosine Similarity}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2} = \frac{\sum_{i=1}^d u_i v_i}{\sqrt{\sum_{i=1}^d u_i^2} \sqrt{\sum_{i=1}^d v_i^2}}$$
* Quy tắc quyết định:
  $$\text{Is\_Duplicate}(d_A, d_B) = \begin{cases} \text{True}, & \text{nếu } \text{Cosine Sim}(\mathbf{u}_A, \mathbf{v}_B) \ge 0.82 \\ \text{False}, & \text{ngược lại} \end{cases}$$
* Ngưỡng thực nghiệm $\tau = 0.82$ được lựa chọn dựa trên kiểm định chéo F1-score: đủ linh hoạt để bỏ qua sự sai khác nhỏ về câu từ chào hỏi giữa các sàn, nhưng đủ chặt chẽ để không gộp nhầm hai vị trí khác nhau (ví dụ: Frontend Dev vs Backend Dev) trong cùng một công ty.

---

## Chương 4: Hiện Thực Hóa Kỹ Thuật & Các Module Đột Phá

### 4.1. Recursive JSON Flattener & Tích Hợp Schema 8 Sàn (Integration Stage)
Tại module `preprocessing/integration/json_flattener.py`, thuật toán duyệt đệ quy phân giải toàn bộ các cấu trúc phức tạp:
* Bóc tách các dictionary phân cấp (như `company.address`, `general_info.level`).
* Bóc tách mảng đối tượng (như `skills[].skillName` của VietnamWorks).
* Phân rã mảng chuỗi detail-box của CareerViet thành các trường thuộc tính độc lập.
* Trích xuất thẻ JSON-LD ẩn trên Glints và ITViec để tìm kiếm thông tin `baseSalary` bị che giấu trên giao diện web.
* Chuẩn hóa khóa toàn cục `job_id_global` bảo đảm tính độc nhất và truy vết dòng dõi 100%.

### 4.2. Bộ Bóc Tách Lương Phân Tầng Cascade (Cascade Salary Parser)
Tại module `preprocessing/transformation/salary_parser.py`, bài toán 65% bài đăng khuyết lương được giải quyết qua 3 tầng cascade:
1. **Header Regex Extractor:** Nhận diện các dải số chuẩn ở phần tiêu đề và ô nhập liệu lương (ví dụ: `"15 - 25 triệu"`, `"1,000 - 2,000 USD"`).
2. **JD Context Regex Scanner:** Khi tiêu đề ghi thỏa thuận, kích hoạt bộ quét ngữ cảnh trên toàn bộ văn bản JD, sử dụng các mẫu biểu thức chính quy nhận diện từ khóa thu nhập: `(?i)(?:mức\s+lương|thu\s+nhập|chế\s+độ\s+lương|salary|package)\s*(?::|-)?\s*(\d+[\d\.,]*)\s*(?:-|đến|tới|\.\.\.)\s*(\d+[\d\.,]*)\s*(triệu|tr|vnd|usd)`.
3. **Annual & Period Normalizer:** Tự động phát hiện đơn vị thời gian (năm/tháng/giờ), tự động chia cho 12 tháng nếu thu nhập được công bố theo năm.

### 4.3. Quy Chuẩn Ngoại Tệ & Tích Hợp Tỷ Giá Lịch Sử
* Đối với USD: Áp dụng tỷ giá tham chiếu dự án $1\text{ USD} = 25,400\text{ VND}$.
* Đối với SGD (Đô la Singapore): Tích hợp trực tiếp API Frankfurter (`https://api.frankfurter.dev/v1/{date}?from=SGD&to=USD`). Hệ thống lấy tỷ giá SGD/USD tại đúng ngày đăng tin tuyển dụng, sau đó nhân với tỷ giá USD/VND dự án để tạo thành tỷ giá quy đổi chéo minh bạch. Nếu ngày đăng tin rơi vào ngày nghỉ cuối tuần, hệ thống tự động fallback về ngày giao dịch gần nhất trước đó.

### 4.4. Đột Phá: Gemini All-in-One Preprocessing Agent
Tại module `preprocessing/missing_outlier/gemini_all_in_one_agent.py`, hệ thống hiện thực hóa một kiến trúc Agent thông minh, đóng gói 4 nhiệm vụ xử lý ngôn ngữ tự nhiên phức tạp trong **một lần suy luận duy nhất (Single-pass LLM Inference)**:
1. **Phân loại kỹ năng 3 lớp (3-tier Skills Classification):**
   * `hard_skills`: Giữ nguyên danh từ công nghệ tiếng Anh chuẩn quốc tế (Python, Docker, AWS, React, Kubernetes...).
   * `soft_skills`: Chuẩn hóa tiếng Việt (Kỹ năng giao tiếp, Làm việc nhóm, Tư duy phản biện...).
   * `domain_skills`: Chuẩn hóa tiếng Việt (Thương mại điện tử, Fintech, Ngân hàng số, Logistics...).
2. **Làm giàu thuộc tính yêu cầu (Requirements Enrichment):**
   * Trích xuất số năm kinh nghiệm tối thiểu `experience_years` (chuẩn hóa số thực, gán 0.0 cho Fresher/Intern).
   * Chuẩn hóa cấp bậc `standardized_seniority` về 7 mức: `intern`, `fresher`, `junior`, `middle`, `senior`, `lead`, `manager`.
   * Chuẩn hóa học vấn `standardized_education` về: `bachelor`, `master`, `college`, `none`.
   * Khai phá trạng thái làm việc Thứ 7 `is_saturday_work` (True / False / None).
3. **Bản địa hóa & Dịch thuật (Translation to Vietnamese):**
   * Tự động phát hiện ngôn ngữ của bài đăng. Nếu bài đăng bằng tiếng Anh, dịch tiêu đề, mô tả, yêu cầu và quyền lợi sang tiếng Việt chuẩn mực, hỗ trợ cho việc phân cụm ngữ nghĩa đồng nhất.
4. **Resumable Checkpoint Store:**
   * Module `checkpoint_store.py` lưu vết kết quả xử lý của Gemini theo từng dòng JSONL (`gemini_checkpoint.jsonl`). Khi tiến trình bị ngắt quãng do lỗi mạng hoặc quota limit, hệ thống có khả năng bỏ qua các bản ghi đã xử lý và tiếp tục chạy từ vị trí dừng lại một cách hoàn hảo.

### 4.5. Khắc Phục Ảo Giác Bằng Market Anchor Calculator
Để loại bỏ hoàn toàn rủi ro mô hình ngôn ngữ lớn "bịa đặt" (hallucinate) mức lương vô căn cứ, module `preprocessing/missing_outlier/market_anchor_calculator.py` thiết lập **Khung tham chiếu phân tầng 4 cấp (4-tier Fallback Anchors)**:
* **Cấp 1 (Platform x Seniority Median):** Tính toán trung vị mức lương thực tế cho từng cặp `(sàn, cấp bậc)` dựa trên các bài đăng có lương thực tế (yêu cầu $N \ge 15$ mẫu).
* **Cấp 2 (Seniority Overall Median):** Nếu một ô kết hợp bị thiếu mẫu, fallback về trung vị toàn thị trường của cấp bậc đó.
* **Cấp 3 (Platform Overall Median):** Fallback về trung vị chung của sàn tuyển dụng tương ứng.
* **Cấp 4 (Theoretical Industry Floors):** Khung sàn lý thuyết được nhóm nghiên cứu thiết lập dựa trên báo cáo thị trường IT Việt Nam:
  * `intern`: 3M – 6M VND
  * `fresher`: 7M – 12M VND
  * `junior`: 12M – 20M VND
  * `middle`: 20M – 35M VND
  * `senior`: 35M – 55M VND
  * `lead`: 50M – 80M VND
  * `manager`: 60M – 100M VND

Gemini khi suy luận bắt buộc phải tiếp nhận ngữ cảnh mỏ neo này và chỉ được phép điều chỉnh biên độ lương dựa trên độ khó của Tech Stack thực tế trong bài đăng.

### 4.6. Target Schema Formatter & Khế Ước 11 Khóa Gốc Tinh Gọn
Module `preprocessing/normalization/target_schema_formatter.py` đảm nhiệm khâu đóng gói cuối cùng. Hệ thống tiến hành thanh lọc triệt để dữ liệu:
* Xóa bỏ 100% các cột thô `raw_*` ở root level.
* Loại bỏ toàn bộ các trường tạm trung gian phục vụ debug: `is_stub_jd`, `quality_score`, `is_outlier_capped`, `governance`, `nlp_metadata`.
* Cố định cấu trúc dữ liệu theo đúng **11 Khóa Gốc Chuẩn Mực (11 Canonical Root Keys)**:
  1. `job_id_global` (str): Khóa định danh toàn cục duy nhất.
  2. `source_platform` (str): Tên sàn nguồn.
  3. `source_url` (str): Đường dẫn tin gốc.
  4. `job_info` (dict): `{title, job_family, work_type, is_remote}`.
  5. `company` (dict): `{name, industry, size}`.
  6. `locations` (list[dict]): Danh sách `{province, district, Details_address}` chuẩn hóa 63 tỉnh thành.
  7. `salary` (dict): `{salary_min, salary_max, salary_currency, salary_source}`.
  8. `skills` (dict): `{hard_skills, soft_skills, domain_skills}`.
  9. `requirements` (dict): `{experience_years, standardized_seniority, standardized_education, is_saturday_work}`.
  10. `jd_text` (dict): `{language, description, requirements, benefits}` (đã làm sạch tiền tố phúc lợi thừa).
  11. `date` (dict): `{posted_date, expired_date}` (chuẩn hóa ISO 8601).

---

## Chương 5: Báo Cáo Thực Nghiệm & Kiểm Định Chất Lượng QA Pipeline

### 5.1. Kết Quả Kiểm Định Chất Lượng Tự Động (QA Audit Report)
Hệ thống tích hợp bộ kiểm thử tự động toàn diện tại `preprocessing/qa/run_qa_checks.py`. Toàn bộ quá trình kiểm định đã hoàn tất và xuất bản báo cáo chính thức tại `reports/qa/qa_pipeline_report.md` với kết quả **PASSED 5/5 Bộ Kiểm Định**:

| STT | Check Suite | Tiêu Chí Kỹ Thuật Kiểm Định | Số Lỗi Ghi Nhận | Trạng Thái Đánh Giá |
| :---: | :--- | :--- | :---: | :---: |
| **Check 1** | **Lineage & File Existence** | Hiện diện đầy đủ 3 file; Bảo toàn 100% ID từ F1 sang F2; Khử trùng lặp F2 $\rightarrow$ F3 giảm 1,057 bài trùng (10.54%). | `0` lỗi | <span style="color:#10b981;font-weight:bold;">PASSED</span> |
| **Check 2** | **100% PURE JSON RFC 8259** | Cấm định dạng Parquet/CSV trong vùng curated; Quét sâu đệ quy tìm hằng số `NaN` (yêu cầu serialize thành `null`). | `0` lỗi | <span style="color:#10b981;font-weight:bold;">PASSED</span> |
| **Check 3** | **Golden Master Contract** | Khớp chính xác 11 root keys; Không còn prefix `raw_*`; Sạch tiền tố "Phúc lợi"; Xóa sạch legacy objects. | `0` lỗi | <span style="color:#10b981;font-weight:bold;">PASSED</span> |
| **Check 4** | **Domain Groups & MNAR** | Độc lập nhóm `skills`; `skills_count == len(skills_list)`; Bảo toàn MNAR: lương thỏa thuận giữ cờ `is_negotiable=True`. | `0` lỗi | <span style="color:#10b981;font-weight:bold;">PASSED</span> |
| **Check 5** | **Outlier & Quality Governance** | Điểm chất lượng `quality_score` $\in [0, 1]$; Cờ `is_outlier_capped` chính xác; Tuân thủ luật chất lượng QR1-QR5. | `0` lỗi | <span style="color:#10b981;font-weight:bold;">PASSED</span> |

### 5.2. Bảng Phân Tích Định Lượng Trước vs Sau Tiền Xử Lý
Dưới đây là bảng đối chiếu chi tiết các chỉ số đo lường chất lượng dữ liệu giữa tập dữ liệu thô ban đầu và Bộ Dữ Liệu Vàng đầu ra:

| Chỉ Số Đánh Giá Chất Lượng | Tập Dữ Liệu Thô (Raw Input) | Bộ Dữ Liệu Vàng (Golden Master) | Hiệu Quả Cải Thiện |
| :--- | :---: | :---: | :---: |
| **Tổng số lượng bài đăng** | 10,024 bản ghi (lẫn bài trùng lặp) | **8,967 bản ghi độc bản** | Loại bỏ 1,057 bài trùng ($10.54\%$) |
| **Tỷ lệ có dữ liệu lương định lượng** | $35.2\%$ (đa phần thỏa thuận) | **$100.0\%$ (Original + Predicted)** | Tăng trưởng $+64.8\%$ độ phủ |
| **Độ lệch phân phối lương (Skewness)** | $\gamma_1 > 5.8$ (lệch phải rất nặng) | **$\gamma_1 = 0.42$ (Log-transform scale)** | Đưa về phân phối gần chuẩn đối xứng |
| **Tỷ lệ có thông tin số năm kinh nghiệm**| $48.5\%$ | **$100.0\%$ (Zero-Null)** | Bù khuyết trọn vẹn $51.5\%$ ô trống |
| **Chuẩn hóa cấp bậc nghề nghiệp (Seniority)**| Chuỗi tự do, lẫn lộn tiếng Anh/Việt | **7 Cấp bậc chuẩn hóa tuyệt đối** | Chuẩn hóa 100% bản ghi |
| **Phân loại kỹ năng công nghệ** | Văn bản thô, lẫn tag danh mục sàn | **3 Lớp độc lập (Hard/Soft/Domain)** | Lọc bỏ 100% portal noise |
| **Chuẩn hóa địa bàn làm việc** | Địa chỉ chuỗi tự do hỗn hợp | **Phân cấp Tỉnh/Thành 63 tỉnh** | Thống nhất 100% địa giới |
| **Độ tuân thủ chuẩn lưu trữ JSON** | Nhiều lỗi parsing, chứa hằng số NaN | **100% PURE JSON RFC 8259** | 0 lỗi cú pháp parser |

---

## Chương 6: Kết Luận & Định Hướng Giai Đoạn Khai Phá Hạ Nguồn

### 6.1. Những Đóng Góp Nổi Bật Của Đề Án
1. **Hoàn thiện xuất sắc Mục tiêu Chiến lược SD1:** Xây dựng một kiến trúc tiền xử lý dữ liệu đa nguồn hiện đại, chuyển hóa thành công 10,024 bản ghi thô từ 8 sàn tuyển dụng thành **Bộ Dữ Liệu Vàng 8,967 bản ghi** tinh gọn, đạt chuẩn công nghiệp.
2. **Đột phá về Phương pháp luận Khoa học:**
   * Tách bạch và tôn trọng bản chất thống kê của cơ chế khuyết thiếu **MNAR**, không áp dụng các giải pháp điền số bình quân cơ học làm sai lệch thị trường.
   * Hiện thực hóa chính sách **Zero Record Loss** bằng kỹ thuật Winsorization tại phân vị 1% và 99%, bảo toàn 100% dữ liệu kỹ năng phục vụ khai phá luật kết hợp.
3. **Đột phá về Giải pháp Kỹ thuật:**
   * Thiết kế bộ bóc tách **Cascade Salary Parser** giúp tăng độ phủ lương từ 35.2% lên 58.6% ở tầng rule-based.
   * Xây dựng thành công **Gemini All-in-One Preprocessing Agent** kết hợp **Market Anchor Calculator**, triệt tiêu nguy cơ ảo giác của LLM và tối ưu hóa chi phí suy luận qua cơ chế Single-pass.
   * Xây dựng quy trình **Khử trùng lặp thực thể xuyên sàn** hai bước (Blocking kết hợp Cosine Similarity $\ge 0.82$) giúp loại bỏ chính xác 1,057 bài đăng trùng lặp.
   * Hoàn thành kiểm định tự động **5/5 QA Check Suites** đạt chuẩn 100% PURE JSON RFC 8259.

### 6.2. Sẵn Sàng Trọn Vẹn Cho Giai Đoạn Khai Phá Nâng Cao (Downstream Mining)
Bộ Dữ Liệu Vàng `golden_master.json` là tài sản dữ liệu quý giá, tạo tiền đề vững chắc để triển khai các thuật toán khai phá nâng cao trong các chương tiếp theo:
* **Phục vụ SD2 (Phân tích nhu cầu nghề nghiệp):** Phân tích tương quan giữa 12 Job Family và 7 cấp bậc Seniority trên các vùng kinh tế trọng điểm.
* **Phục vụ SD3 (Trí tuệ kỹ năng IT):** Áp dụng thuật toán **FP-Growth (Frequent Pattern Growth)** trên mảng `hard_skills` để khai phá các tập kỹ năng phổ biến (Frequent Itemsets), luật kết hợp (Association Rules) giữa các công nghệ (ví dụ: $\{ \text{Docker, Kubernetes} \} \Rightarrow \{ \text{CI/CD, Cloud} \}$).
* **Phục vụ SD4 & SD5 (Khoảng cách đào tạo & Khuyến nghị nghề nghiệp):** Xây dựng mô hình phân cụm K-Means / DBSCAN trên không gian kỹ năng để định vị khoảng cách năng lực của sinh viên CNTT tốt nghiệp, từ đó đề xuất hệ thống khuyến nghị lộ trình học tập cá nhân hóa.

---
*Báo cáo được hoàn thành bởi Nhóm Nghiên Cứu VN-IT-Job-Mining — Khoa Công nghệ Thông tin, Đại học Giao thông Vận tải TP.HCM (UTH).*
