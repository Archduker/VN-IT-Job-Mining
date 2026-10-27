---
marp: true
theme: gaia
_class: lead
paginate: true
backgroundColor: #0f172a
color: #f8fafc
style: |
  section {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 26px;
    padding: 40px;
  }
  h1 {
    color: #38bdf8;
    font-size: 1.8em;
  }
  h2 {
    color: #38bdf8;
    font-size: 1.4em;
    border-bottom: 2px solid #38bdf8;
    padding-bottom: 8px;
  }
  h3 {
    color: #93c5fd;
    font-size: 1.1em;
  }
  code {
    background: #1e293b;
    color: #38bdf8;
    font-size: 0.85em;
  }
  table {
    font-size: 0.72em;
    color: #f8fafc;
    border-collapse: collapse;
    width: 100%;
  }
  th {
    background-color: #1e293b;
    color: #38bdf8;
    border: 1px solid #334155;
    padding: 6px 10px;
  }
  td {
    border: 1px solid #334155;
    padding: 6px 10px;
    background-color: rgba(30, 41, 59, 0.5);
  }
  .highlight {
    color: #f59e0b;
    font-weight: bold;
  }
  .success {
    color: #10b981;
    font-weight: bold;
  }
  .badge {
    background: #0284c7;
    color: white;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.75em;
  }
  footer {
    font-size: 0.55em;
    color: #64748b;
  }
---

<!-- _class: lead -->
# KIẾN TRÚC TIỀN XỬ LÝ DỮ LIỆU ĐA NGUỒN & XÂY DỰNG BỘ DỮ LIỆU VÀNG
### Đề án: Phân tích thị trường lao động IT & Kỹ năng nghề nghiệp tại Việt Nam
**Môn học:** Khai phá Dữ liệu (Data Mining)  
**Quy mô:** 10,024 bài đăng thô $\rightarrow$ 8,967 bài đăng Golden Master  

<div style="margin-top: 40px; font-size: 0.8em; color: #94a3b8;">
  <span>Học viên thực hiện: Nhóm Nghiên cứu VN-IT-Job-Mining</span><br>
  <span>Thời gian: Tháng 10/2026</span>
</div>

<!-- note:
Chào thầy cô và các bạn. Hôm nay nhóm em xin trình bày về Kiến trúc Tiền xử lý Dữ liệu Đa nguồn cho đề tài Phân tích thị trường việc làm IT tại Việt Nam. Trọng tâm của bài báo cáo là phương pháp luận khoa học và giải pháp kỹ thuật để chuyển đổi hơn 10.000 bài đăng thô từ 8 sàn tuyển dụng lớn thành Bộ Dữ Liệu Vàng 8.967 bản ghi đạt chuẩn 100% PURE JSON RFC 8259.
-->

---

## 1. Bối Cảnh Thực Tế & Thách Thức Dữ Liệu IT

* **Quy mô thu thập:** 10,024 bài đăng từ **8 sàn tuyển dụng hàng đầu** (TopCV, TopDev, VietnamWorks, ITviec, CareerViet, Vieclam24h, Glints, JobsGO).
* **Đặc tính dữ liệu thực tế (Real-world Data Sins):**
  * **Cấu trúc dị thể nặng:** JSON lồng nhau 3-4 tầng, mảng tags, detail-box HTML, JSON-LD ngầm.
  * **Lương che giấu & Lương ẩn:** 65% ghi *"Thỏa thuận"*, nhưng lương thực tế nằm rải rác trong câu chữ mô tả công việc (JD).
  * **Sneaky Nulls:** 9+ dạng null trá hình (`"thỏa thuận"`, `"cạnh tranh"`, `0`, `[]`, `"null"`).
  * **Ngoại lai nhập liệu:** Bắt nhầm số điện thoại (SĐT `0243.936...` thành 243 triệu VND) hoặc chuỗi che giấu (`1*** USD`).
  * **Trùng lặp xuyên sàn:** Cùng 1 vị trí tuyển dụng nhưng được HR đăng đồng thời lên 3-4 sàn khác nhau.

<!-- note:
Khi tiếp cận dữ liệu việc làm thực tế tại Việt Nam, thách thức lớn nhất không phải là cào dữ liệu, mà là 'bệnh án' của dữ liệu thô. 65% bài đăng ghi lương thỏa thuận nhưng thực chất nhà tuyển dụng đã viết mức lương trong phần mô tả. Ngoài ra, các giá trị null giả mạo như số 0, chuỗi 'thỏa thuận' và lỗi bóc nhầm số điện thoại liên hệ thành lương hàng trăm triệu đòi hỏi một quy trình xử lý cực kỳ chặt chẽ.
-->

---

## 2. Kiến Trúc Pipeline Hiện Đại & Ranh Giới Đanh Thép

Quy trình tiền xử lý được chuẩn hóa theo **CRISP-DM nâng cấp ELT** với **4 Giai đoạn liên hoàn**:

```text
+----------------------------------------------------------------------------------------------------+
| [GĐ 1: INTEGRATION]       --> [GĐ 2: TRANSFORMATION]    --> [GĐ 3: MISSING & OUTLIER]              |
| * Ép phẳng JSON 8 sàn         * Cascade Salary Parser       * Bóc trần 9+ Sneaky Nulls (MNAR)      |
| * Schema Mapping 8 nhóm       * Quy đổi USD/SGD -> VND      * IQR & Winsorization P1-P99           |
| * Khóa `job_id_global`        * ISO 8601 & Parse Năm KN     * Gemini All-in-One + Market Anchor    |
+----------------------------------------------------------------------------------------------------+
                                               │
                                               ▼
+----------------------------------------------------------------------------------------------------+
| [GĐ 4: DEEP NORMALIZATION & TARGET SCHEMA]  --> [GĐ 5: QA PIPELINE AUDIT (5/5 PASSED)]             |
| * Khử trùng Cosine Sim >= 0.82 (loại 1,057)     * Check 1: Dòng dõi & Lưu vết File                 |
| * Target Schema Chuẩn 11 Root Keys              * Check 2: 100% PURE JSON RFC 8259 (Zero NaN)      |
| * 3-Tier Skills (Hard / Soft / Domain)          * Check 3-5: Golden Contract & Outlier Governance  |
+----------------------------------------------------------------------------------------------------+
```

* **Khế ước Ranh giới đanh thép (Ironclad Boundaries):** Bước trước không lấn sân bước sau (Integration cấm parse lương, Transformation cấm xóa outlier).

<!-- note:
Để tránh tình trạng chồng chéo chức năng giữa các module, chúng em thiết lập Ma trận Ranh giới đanh thép. Giai đoạn 1 chỉ thuần túy tích hợp cấu trúc, giai đoạn 2 chuyển đổi định dạng và bóc tách định lượng, giai đoạn 3 xử lý khuyết thiếu thống kê và ngoại lai, và giai đoạn 4 chuẩn hóa sâu để đóng gói Bộ Dữ Liệu Vàng.
-->

---

## 3. Giai Đoạn 1: Tích Hợp Schema & Ép Phẳng JSON

* **Mục tiêu:** Gom 8 nguồn dữ liệu hoàn toàn khác biệt về cấu trúc thành một Bảng phẳng Staging thống nhất (`raw_for_outlier.json`).
* **Kỹ thuật cốt lõi:**
  * **Recursive JSON Flattener:** Đệ quy giải mã dict lồng nhau, mảng đối tượng, thuộc tính DOM table và thẻ JSON-LD ngầm.
  * **Khóa toàn cục định danh duy nhất:**  
    $$\text{job\_id\_global} = \langle\text{source\_platform}\rangle\text{\_}\langle\text{source\_job\_id}\rangle$$
  * **Ánh xạ 8 Nhóm Thuộc Tính Cốt Lõi:**
    `company`, `địa điểm`, `skills`, `JD`, `salary`, `date`, `requirements`, `other`.
* **Nguyên tắc bất biến:** 100% Deterministic logic. Tuyệt đối **không** dùng AI, **không** xóa hàng, **không** fillna tại bước này.

<!-- note:
Ở giai đoạn 1, chúng em đối mặt với 8 cấu trúc JSON khác nhau: TopDev trả API phân cấp, CareerViet nhét mọi thứ vào bảng detail-box, còn Glints và ITViec giấu lương trong thẻ JSON-LD. Chúng em xây dựng thuật toán ép phẳng đệ quy để đưa toàn bộ 10.024 bản ghi về cấu trúc phẳng có khóa định danh duy nhất toàn cầu job_id_global.
-->

---

## 4. Giai Đoạn 2: Cascade Salary Parser & Bóc Tách Kiểu

* **Bài toán:** 65% bài đăng ghi *"Lương Thỏa thuận"* ở tiêu đề nhưng lại nêu mức lương cụ thể trong JD.
* **Giải pháp: Cascade Salary Extraction 3 Tầng**

```text
[Tầng 1: Header Regex] ----> (Nếu có số cụ thể) ----> [Gán salary_min / salary_max]
        │ (Nếu "Thỏa thuận" / null)
        ▼
[Tầng 2: JD Regex Scanner] -> (Quét mô tả & yêu cầu) -> [Bóc tách dải số lương ẩn]
        │ (Nếu phát hiện cụm từ 'Lương năm')
        ▼
[Tầng 3: Annual Normalizer] -> Chia cho 12 tháng để quy đồng về chuẩn tháng
```

* **Kết quả:** Gia tăng tỷ lệ có dữ liệu lương định lượng từ **35.2% lên 58.6%** mà không làm thay đổi bản chất thỏa thuận gốc (`is_salary_negotiable_declared = 1`).

<!-- note:
Cascade Salary Parser là một điểm sáng tạo kỹ thuật nổi bật của nhóm. Thay vì chấp nhận bỏ qua 65% tin lương thỏa thuận, hệ thống sẽ kích hoạt bộ quét regex thông minh trên văn bản mô tả để tìm các cụm từ như 'Mức lương từ 20 đến 35 triệu' hoặc 'Thu nhập lên đến 500 triệu/năm'. Nhờ đó, tỷ lệ bài đăng có lương tăng vọt từ 35% lên gần 60%.
-->

---

## 5. Giai Đoạn 2: Chuẩn Hóa Ngoại Tệ & Chu Kỳ Lương

* **Quy đổi ngoại tệ về VND:**
  * **USD:** Áp dụng tỷ giá tham chiếu dự án:  
    $$\text{Salary}_{\text{VND}} = \text{Salary}_{\text{USD}} \times 25,400\text{ VND}$$
  * **SGD (Đô la Singapore):** Tích hợp API lịch sử Frankfurter (`api.frankfurter.dev/v1`) lấy tỷ giá chéo SGD/USD theo ngày đăng tin $\times 25,400\text{ VND}$.
* **Chuẩn hóa chu kỳ trả lương:**
  * Lương năm $\rightarrow$ Chia 12 tháng: $\text{Salary}_{\text{Month}} = \text{Salary}_{\text{Year}} / 12$.
  * Lương giờ $\rightarrow$ Giả định 160 giờ/tháng (nếu có).
* **Minh bạch nguồn gốc (Data Lineage):** Lưu trữ đồng thời `salary_min_original`, `salary_max_original`, `salary_currency_original` và metadata tỷ giá.

<!-- note:
Thị trường IT có nhiều công ty đa quốc gia trả lương bằng USD và SGD. Để đưa về cùng một mặt bằng so sánh định lượng, nhóm áp dụng tỷ giá cố định 25.400 cho USD và gọi API Frankfurter lấy tỷ giá lịch sử cho SGD theo đúng ngày đăng tin. Toàn bộ giá trị gốc và loại tiền tệ gốc vẫn được lưu vết độc lập để đảm bảo tính minh bạch khoa học.
-->

---

## 6. Giai Đoạn 3: Bóc Trần 9+ Sneaky Null Markers

* **Hiện tượng:** Sàn tuyển dụng không để giá trị rỗng (`None`) mà điền các chuỗi ngụy trang, khiến các hàm `df.isna()` của Pandas hoàn toàn bị vô hiệu hóa!
* **Bóc trần 9+ Dạng Null Trá Hình:**
  * Dạng chữ: `"thỏa thuận"`, `"cạnh tranh"`, `"lương thương lượng"`, `"negotiable"`.
  * Dạng số / ký tự: `0`, `-1`, `"0.0"`, `"[]"`, `"{}"`, `"undefined"`, `"null"`.
* **Cơ chế khuyết thiếu MNAR (Missing Not At Random):**
  * Lương thỏa thuận **không phải** là thiếu ngẫu nhiên, mà là chiến lược bảo mật của doanh nghiệp.
  * **Giải pháp:** Reset giá trị số về `null`, đồng thời bật cờ bảo toàn:
    $$\text{is\_salary\_negotiable} = \text{True}$$
  * **Tuyệt đối CẤM:** Không được fill Mean/Median vào các ô này vì sẽ bóp méo toàn bộ bức tranh phân phối lương thị trường.

<!-- note:
Một trong những lỗi kinh điển khi tiền xử lý là nhầm lẫn giữa Missing At Random và Missing Not At Random. Lương thỏa thuận là hành vi có chủ đích của nhà tuyển dụng. Nếu ta dại dột điền Mean hoặc Median vào đây, phân phối lương sẽ bị biến dạng hoàn toàn. Nhóm bóc trần toàn bộ các null giả mạo và bảo vệ cờ is_negotiable = True.
-->

---

## 7. Giai Đoạn 3: Kiểm Định Ngoại Lai & Winsorization

* **Bản chất: Phân tích căn nguyên ngoại lai (Root Cause Analysis):**
  * **Lương cao vượt ngưỡng:** Vị trí cấp cao (*Senior, Tech Lead, Architect, FDI*) $\rightarrow$ Dữ liệu thực tế quý giá phản ánh đỉnh trần thị trường (SD2).
  * **Lương thấp bất thường:** Trợ cấp thực tập sinh (*Intern: 2 - 4 triệu*), part-time $\rightarrow$ Dữ liệu thực hợp lệ phân khúc sinh viên (SD4).
  * **Tin rác / Bóc nhầm SĐT:** Heuristic Scrubber reset lương về `null` $\rightarrow$ Vẫn giữ dòng để bảo toàn Kỹ năng (SD3).
* **Kiểm định IQR & Kỹ thuật Winsorization tại P1 - P99:**
  $$\text{IQR} = Q_3 - Q_1 \quad \Longrightarrow \quad \text{Salary}_{\text{capped}} = \min(\max(\text{Salary}, P_1), P_{99})$$
* **Chính sách Không Mất Bản Ghi (Zero Record Loss Policy):**
  * Tuyệt đối **không drop dòng**. Dải lương được khống chế an toàn trong khoảng **4 triệu $\rightarrow$ 120 triệu VND/tháng**, bảo toàn trọn vẹn 100% bản ghi cho khai phá kỹ năng.

<!-- note:
Tại sao chúng em KHÔNG XÓA DÒNG khi gặp outlier? Vì phương pháp luận khoa học đòi hỏi phải tìm hiểu TẠI SAO nó là outlier:
1. Nếu lương cao: Thường là Senior, Tech Lead, Solution Architect hoặc công ty FDI trả ngoại tệ. Đây là dữ liệu thực tế rất quý phản ánh đỉnh trần SD2.
2. Nếu lương thấp: Là trợ cấp Intern 2-4 triệu hoặc part-time sinh viên, phản ánh đúng dữ liệu nhập môn SD4.
3. Nếu là tin rác bóc nhầm SĐT: Bộ Heuristic Scrubber sẽ reset lương về null và bật cờ is_negotiable chứ vẫn không xóa dòng, vì bài đăng đó vẫn chứa đầy đủ danh mục Hard Skills.
Áp dụng Winsorization P1-P99 giúp khống chế phương sai mà bảo toàn 100% bản ghi.
-->

---

## 8. Giai Đoạn 3: Vòng Lặp Phản Hồi & Heuristic Scrubber

* **Phát hiện thực nghiệm:** Khảo sát sau khi parse lương phát hiện 2 lỗi dị biệt nghiêm trọng:
  1. *Bắt nhầm số điện thoại HR:* Câu JD có dạng *"Liên hệ Khánh Lương SĐT 0243.936.6990"* $\rightarrow$ Regex bắt nhầm thành lương **243 triệu VND**!
  2. *Bắt nhầm số che giấu:* Câu JD có dạng *"Lương từ 1\*\*\* USD"* $\rightarrow$ Bị bóc nhầm thành **25,400 VND** (1 USD)!
* **Cơ chế Phản hồi Vòng lặp (Cyclic Feedback Loop):**
  * Xây dựng bộ lọc **Heuristic Scrubber** trước khi tính toán phân vị:
  * Nhận diện pattern số điện thoại (đầu số 024, 028, 09x, 03x) và dấu sao che giấu `***`.
  * Tự động hoàn tác (reset) lương về `None` và kích hoạt lại cờ `is_salary_negotiable = True`.
* **Ý nghĩa:** Chứng minh quy trình Data Mining hiện đại là **vòng tròn phản hồi thích ứng**, không phải đường thẳng cứng nhắc.

<!-- note:
Đây là minh chứng rõ nhất cho việc Data Mining hiện đại không phải đường thẳng một chiều. Khi kiểm tra ngoại lai, chúng em phát hiện có những tin ghi 'Liên hệ Ms Khánh Lương SĐT 0243...' bị bóc nhầm thành lương 243 triệu. Nhóm đã kích hoạt vòng lặp hồi quy, viết bộ lọc Heuristic Scrubber để triệt tiêu toàn bộ lỗi này trước khi đưa vào tính toán thống kê.
-->

---

## 9. Giai Đoạn 3.5: Gemini All-in-One Preprocessing Agent

* **Sứ mệnh:** Đọc hiểu ngữ nghĩa sâu văn bản JD để giải quyết 4 bài toán lớn trong **một lần duyệt duy nhất**:

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 0.8em;">
<div>

### 1. Phân Loại Kỹ Năng 3 Lớp
* **Hard Skills:** Giữ nguyên tiếng Anh chuẩn (Python, Docker, AWS, React, Kubernetes).
* **Soft Skills:** Tiếng Việt (Giao tiếp, Làm việc nhóm, Giải quyết vấn đề).
* **Domain Skills:** Tiếng Việt (Fintech, E-commerce, EdTech, Logistics).

### 2. Làm Giàu Yêu Cầu (Requirements)
* `experience_years`: Chuẩn hóa số thực (0.0 cho Fresher/Intern).
* `standardized_seniority`: 7 bậc chuẩn.
* `standardized_education`: Đại học, Cao đẳng, Thạc sĩ, Không yêu cầu.
* `is_saturday_work`: Khai phá trạng thái làm T7.

</div>
<div>

### 3. Dự Đoán Lương Thị Trường Neo
* Neo vào ma trận Mean/Median `[Platform x Seniority]`.
* Đảm bảo **Zero-Null** có căn cứ (`salary_source = 'predicted'`).

### 4. Bản Địa Hóa & Dịch Thuật
* Dịch tiêu đề, JD, yêu cầu, quyền lợi từ tiếng Anh sang tiếng Việt thống nhất.

### 5. Resumable Checkpoint Store
* Lưu checkpoint JSONL từng dòng, tự động resume khi gặp sự cố mạng hoặc quota limit.

</div>
</div>

<!-- note:
Giai đoạn 3.5 là bước đột phá AI của hệ thống. Thay vì gọi nhiều prompt riêng lẻ tốn kém, nhóm xây dựng Gemini All-in-One Agent giải quyết 4 nhiệm vụ cùng lúc: phân loại kỹ năng 3 lớp Hard-Soft-Domain, trích xuất yêu cầu học vấn và làm thứ 7, dự đoán lương thị trường có cơ sở, và dịch thuật các JD tiếng Anh về tiếng Việt. Đi kèm là module CheckpointStore giúp tiến trình có thể tạm dừng và chạy tiếp bất cứ lúc nào.
-->

---

## 10. Giai Đoạn 3.5: Market Anchor Calculator

* **Vấn đề của LLM thuần túy:** Nếu để LLM tự đoán mức lương, nguy cơ xảy ra hiện tượng **ảo giác (Hallucination)** là rất cao!
* **Giải pháp: Khung Tham Chiếu Phân Tầng 4 Cấp (Hierarchical Market Anchors)**

```text
[Cấp 1: Khớp chính xác cả Sàn Tuyển Dụng & Cấp Bậc] (nếu n >= 15 mẫu có lương thực)
        │ (Nếu thiếu mẫu)
        ▼
[Cấp 2: Khớp theo Cấp Bậc toàn thị trường] (Seniority Overall Median)
        │ (Nếu không rõ cấp bậc)
        ▼
[Cấp 3: Khớp theo Trung vị Sàn Tuyển Dụng] (Platform Overall Median)
        │ (Fallback cuối cùng)
        ▼
[Cấp 4: Khung Lương Sàn Lý Thuyết IT Việt Nam] (Intern: 3-6M, Junior: 10-18M, Senior: 30-55M...)
```

* **Kết quả:** Lương được dự đoán luôn dao động trong **vùng an toàn thực tế của thị trường IT Việt Nam**, bảo toàn độ tin cậy khoa học.

<!-- note:
Để khống chế tuyệt đối hiện tượng ảo giác của mô hình ngôn ngữ lớn, nhóm phát minh cơ chế Market Anchor Calculator. Mọi dự đoán lương của Gemini đều phải lấy mỏ neo từ ma trận trung vị thực tế của sàn và cấp bậc. Nếu bài đăng là Junior trên TopCV, Gemini sẽ phải neo xung quanh mức 12 đến 20 triệu chứ không thể tùy tiện đoán 50 triệu hay 5 triệu.
-->

---

## 11. Giai Đoạn 4: Khử Trùng Lặp Ngữ Nghĩa Xuyên Sàn

* **Bản chất bài toán:** 1 vị trí tuyển dụng thường được nhà tuyển dụng đăng chéo trên TopCV, VietnamWorks, TopDev và ITviec với tiêu đề hơi khác nhau.
* **Quy trình Khử trùng lặp 2 Bước (Entity Resolution Pipeline):**
  1. **Lọc thô (Blocking):** Nhóm bài đăng theo `normalized_company` và `province` địa phương để giảm độ phức tạp từ $\mathcal{O}(N^2)$ xuống $\mathcal{O}(K \cdot M^2)$.
  2. **So khớp ngữ nghĩa sâu:** Tính khoảng cách **Cosine Similarity** trên vector nhúng văn bản mô tả công việc (Text Embeddings):
     $$\text{Cosine Sim}(u, v) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|} \ge 0.82$$
  3. **Hợp nhất Bản ghi Vàng (Golden Record Selection):** Giữ lại bài đăng có độ phong phú thông tin cao nhất.
* **Kết quả thực tế:** Phát hiện và loại bỏ chính xác **1,057 bài đăng trùng lặp** ($10.54\%$), bảo đảm tính nguyên bản cho các thuật toán Data Mining.

<!-- note:
Một đóng góp quan trọng ở Bước 4 là thuật toán khử trùng lặp xuyên sàn. Để không phải so sánh chéo 10.000 x 10.000 cặp bản ghi, chúng em dùng kỹ thuật Blocking theo tên công ty và tỉnh thành. Sau đó áp dụng Cosine Similarity trên vector ngữ nghĩa với ngưỡng thực nghiệm 0.82. Kết quả là hệ thống đã gộp thành công 1.057 bài đăng trùng chéo giữa các sàn.
-->

---

## 12. Giai Đoạn 4: Target Schema Chuẩn 11 Khóa Tinh Gọn

Toàn bộ các trường trung gian, cờ kỹ thuật và cột thô `raw_*` được loại bỏ hoàn toàn, đóng gói dữ liệu về **11 Khóa Gốc Chuẩn Mực**:

```json
{
  "job_id_global": "topcv_123456",
  "source_platform": "topcv",
  "source_url": "https://...",
  "job_info": { "title": "Senior Java Backend Engineer", "job_family": "backend", "work_type": "full_time", "is_remote": false },
  "company": { "name": "FPT Software", "industry": "IT - Phần mềm", "size": "1000+" },
  "locations": [ { "province": "Hà Nội", "district": "Cầu Giấy", "Details_address": "Duy Tân" } ],
  "salary": { "salary_min": 35000000.0, "salary_max": 50000000.0, "salary_currency": "VND", "salary_source": "original" },
  "skills": { "hard_skills": ["Java", "Spring Boot", "Docker", "Kafka"], "soft_skills": ["Làm việc nhóm"], "domain_skills": ["Fintech"] },
  "requirements": { "experience_years": 4.0, "standardized_seniority": "senior", "standardized_education": "bachelor", "is_saturday_work": false },
  "jd_text": { "language": "vi", "description": "...", "requirements": "...", "benefits": "..." },
  "date": { "posted_date": "2026-10-15", "expired_date": "2026-11-15" }
}
```

<!-- note:
Sau khi qua TargetSchemaFormatter, bộ dữ liệu đã được lột xác hoàn toàn: không còn bất kỳ cột thô mang tiền tố raw_, không còn các cờ kỹ thuật phục vụ debug. Toàn bộ 8.967 bản ghi đều chuẩn xác 11 khóa ở root level, cấu trúc lồng nhau được tinh giản gọn gàng, sẵn sàng nạp ngay vào DuckDB, Pandas hoặc các mô hình Machine Learning.
-->

---

## 13. Kiểm Định Chất Lượng Đường Ống (QA 5/5 PASSED)

Báo cáo kiểm định chất lượng tự động (`reports/qa/qa_pipeline_report.md`):

| Bộ Kiểm Định (Check Suite) | Mục Tiêu Kỹ Thuật | Kết Quả Đo Lường | Trạng Thái |
| :--- | :--- | :---: | :---: |
| **Check 1: Lineage & Integrity** | Bảo toàn ID từ F1 sang F2; tỷ lệ khử trùng F2 $\rightarrow$ F3 | $100\%$ ID preserved; Giảm $10.54\%$ trùng | <span class="success">PASSED (0 lỗi)</span> |
| **Check 2: PURE JSON RFC 8259** | Cấm Parquet/CSV, quét sâu đệ quy tìm hằng số `NaN` | `0` Parquet, `0` NaN (100% null RFC 8259) | <span class="success">PASSED (0 lỗi)</span> |
| **Check 3: Golden Master Contract** | Khớp 11 root keys, sạch tiền tố phúc lợi, zero `raw_*` | `0` bản ghi vi phạm cấu trúc | <span class="success">PASSED (0 lỗi)</span> |
| **Check 4: Domain Groups & MNAR** | 10 nhóm nghiệp vụ, bảo toàn MNAR lương thỏa thuận | $100\%$ tuân thủ MNAR & Zero-Null | <span class="success">PASSED (0 lỗi)</span> |
| **Check 5: Outlier Governance** | Tuân thủ luật chất lượng QR1-QR5, Winsorization | $100\%$ lương nằm trong vùng hợp lệ | <span class="success">PASSED (0 lỗi)</span> |

<!-- note:
Tính khoa học của đề tài được khẳng định qua Suite kiểm định QA tự động 5/5 PASSED. Chúng em kiểm tra khắt khe chuẩn RFC 8259: không cho phép bất kỳ hằng số NaN nào tồn tại trong JSON. Dòng dõi dữ liệu từ 10.024 bản ghi thô kế thừa chuẩn xác sang 8.967 bản ghi Golden Master, đảm bảo tính toàn vẹn 100%.
-->

---

## 14. Bảng So Sánh Chỉ Số Chất Lượng (Trước vs Sau)

| Tiêu Chí Đánh Giá | Dữ Liệu Thô Ban Đầu (Raw) | Bộ Dữ Liệu Vàng (Golden Master) | Mức Độ Cải Thiện |
| :--- | :---: | :---: | :---: |
| **Số lượng bản ghi** | 10,024 bản ghi (lẫn trùng lặp) | **8,967 bản ghi độc bản** | Loại bỏ 1,057 tin trùng lặp |
| **Độ phủ dữ liệu lương** | $35.2\%$ (đa phần thỏa thuận) | **$100.0\%$ (Original + Predicted)** | Tăng trưởng $+64.8\%$ |
| **Độ lệch phân phối lương (Skewness)** | $> 5.8$ (lệch phải nghiêm trọng) | **$0.42$ (chuẩn hóa Log-scale)** | Đưa về phân phối chuẩn đối xứng |
| **Độ phủ số năm kinh nghiệm** | $48.5\%$ | **$100.0\%$ (Zero-Null)** | Bù khuyết trọn vẹn qua GenAI |
| **Chuẩn hóa kỹ năng** | Văn bản thô, lẫn tag rác sàn | **3 lớp độc lập (Hard/Soft/Domain)** | Lọc bỏ 100% portal noise |
| **Chuẩn hóa địa bàn** | Chuỗi địa chỉ tự do | **Phân cấp Tỉnh/Thành 63 tỉnh** | Thống nhất 100% địa giới |

<!-- note:
Bảng đối chiếu trước và sau tiền xử lý là minh chứng rõ ràng nhất cho hiệu quả của hệ thống: Tỷ lệ phủ dữ liệu lương và kinh nghiệm đạt mức 100% tuyệt đối, độ lệch Skewness của mức lương từ 5.8 được kéo về mức 0.42 đạt chuẩn phân phối chuẩn, và toàn bộ kỹ năng công nghệ được phân loại rạch ròi 3 lớp.
-->

---

## 15. Kết Luận & Sẵn Sàng Cho 5 Mục Tiêu SD1 — SD5

* **Đóng góp chính của giai đoạn Tiền xử lý:**
  1. Thiết lập **Kiến trúc Pipeline 4 bước hiện đại** với ranh giới đanh thép và vòng lặp phản hồi.
  2. Hiện thực hóa **Cascade Salary Parser** và giải pháp **Winsorization Zero Record Loss**.
  3. Đột phá ứng dụng **Gemini All-in-One Preprocessing Agent** kết hợp **Market Anchor Calculator**.
  4. Xuất bản **Bộ Dữ Liệu Vàng 8,967 bản ghi** chuẩn 11 khóa tinh gọn, vượt qua 5/5 bài test QA.
* **Sẵn sàng trọn vẹn cho giai đoạn Khai phá Chuyên sâu (Data Mining Phase):**
  * **SD1:** Tích hợp dữ liệu thị trường $\rightarrow$ Hoàn thành xuất sắc.
  * **SD2:** Phân tích nhu cầu nghề nghiệp 12 Job Family & 7 Seniority levels.
  * **SD3:** Trí tuệ kỹ năng (Skill Intelligence) qua luật kết hợp FP-Growth & Co-occurrence.
  * **SD4 & SD5:** Phân tích khoảng cách đào tạo Đại học & Khuyến nghị lộ trình phát triển.

**XIN CHÂN THÀNH CẢM ƠN THẦY CÔ VÀ CÁC BẠN ĐÃ LẮNG NGHE!**

<!-- note:
Tóm lại, giai đoạn Preprocessing đã hoàn thành trọn vẹn sứ mệnh của mình: biến một tập dữ liệu thô hỗn loạn thành Bộ Dữ Liệu Vàng chuẩn mực cao, mở toang cánh cửa cho giai đoạn khai phá luật kết hợp FP-Growth và phân cụm kỹ năng ở các mục tiêu SD2 đến SD5 tiếp theo. Nhóm em xin chân thành cảm ơn thầy cô và rất mong nhận được những câu hỏi phản biện ạ!
-->
