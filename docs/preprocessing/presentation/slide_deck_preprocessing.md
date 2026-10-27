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
**Quy mô:** 10,456 bài đăng thô $\rightarrow$ 8,959 bài đăng Golden Master  

<div style="margin-top: 40px; font-size: 0.8em; color: #94a3b8;">
  <span>Học viên thực hiện: Nhóm Nghiên cứu VN-IT-Job-Mining</span><br>
  <span>Thời gian: Tháng 10/2026</span>
</div>

<!-- note:
Chào thầy cô và các bạn. Hôm nay nhóm em xin trình bày về Kiến trúc Tiền xử lý Dữ liệu Đa nguồn cho đề tài Phân tích thị trường việc làm IT tại Việt Nam. Trọng tâm của bài báo cáo là phương pháp luận khoa học và giải pháp kỹ thuật để chuyển đổi 10.456 bài đăng thô từ 8 sàn công nghệ lớn thành Bộ Dữ Liệu Vàng 8.959 bản ghi đạt chuẩn 100% PURE JSON RFC 8259.
-->

---

## 1. Bối Cảnh Thực Tế & Thách Thức Dữ Liệu IT

* **Quy mô thu thập:** 10,456 bài đăng từ **8 sàn tuyển dụng hàng đầu** (TopCV, TopDev, VietnamWorks, ITviec, CareerViet, Vieclam24h, Glints, JobsGO).
* **Đặc tính dữ liệu thực tế (Real-world Data Sins):**
  * **Cấu trúc dị thể nặng:** JSON lồng nhau 3-4 tầng, mảng tags, detail-box HTML, JSON-LD ngầm.
  * **Lương che giấu & Lương ẩn:** 65% ghi *"Thỏa thuận"*, nhưng lương thực tế nằm rải rác trong câu chữ mô tả công việc (JD).
  * **Sneaky Nulls:** 9+ dạng null trá hình (`"thỏa thuận"`, `"cạnh tranh"`, `0`, `[]`, `"null"`).
  * **Ngoại lai nhập liệu:** Bắt nhầm số điện thoại (SĐT `0243.936...` thành 243 triệu VND) hoặc chuỗi che giấu (`1*** USD`).
  * **Trùng lặp xuyên sàn:** Cùng 1 vị trí tuyển dụng nhưng được HR đăng đồng thời lên 3-4 sàn khác nhau (768 cụm trùng).

<!-- note:
Khi tiếp cận dữ liệu việc làm thực tế tại Việt Nam, thách thức lớn nhất không phải là cào dữ liệu, mà là 'bệnh án' của dữ liệu thô. 65% bài đăng ghi lương thỏa thuận nhưng thực chất nhà tuyển dụng đã viết mức lương trong phần mô tả. Ngoài ra, các giá trị null giả mạo như số 0, chuỗi 'thỏa thuận' và lỗi bóc nhầm số điện thoại liên hệ thành lương hàng trăm triệu đòi hỏi một quy trình xử lý cực kỳ chặt chẽ.
-->

---

## 2. Kiến Trúc Pipeline Hiện Đại & Ranh Giới Đanh Thép

Quy trình tiền xử lý được chuẩn hóa theo **CRISP-DM nâng cấp ELT** với **5 Giai đoạn liên hoàn**:

```text
+----------------------------------------------------------------------------------------------------+
| [GĐ 1: INTEGRATION]       --> [GĐ 2: TRANSFORMATION]    --> [GĐ 3: MISSING & OUTLIER]              |
| * Ép phẳng JSON 8 sàn         * Cascade Salary Parser       * Bóc trần 9+ Sneaky Nulls (MNAR)      |
| * Schema Mapping 8 nhóm       * Quy đổi USD/SGD -> VND      * IQR & Winsorization P1-P99           |
| * Khóa `job_id_global`        * ISO 8601 & Parse Năm KN     * Cyclic Loop & Heuristic Scrubber     |
+----------------------------------------------------------------------------------------------------+
                                               │
                                               ▼
+----------------------------------------------------------------------------------------------------+
| [GĐ 4: DEEP NORMALIZATION] --> [GĐ 4.5: GEMINI ALL-IN-ONE AGENT] --> [GĐ 5: QA AUDIT (5/5 PASSED)]  |
| * Khử trùng Cosine >= 0.82     * 2-Tier Decision Gate (Tiết kiệm)    * Check 1: Dòng dõi & Lưu vết   |
| * Gộp 1,136 tin trùng (768 cụm)* Ground-Truth Realism (Giữ null MNAR)* Check 2: 100% PURE JSON       |
| * Loại bỏ 361 tin Stub JDs     * Market Anchor Calculator 4 cấp      * Check 3-5: Golden Contract    |
+----------------------------------------------------------------------------------------------------+
```

* **Khế ước Ranh giới đanh thép (Ironclad Boundaries):** Bước trước không lấn sân bước sau (Integration cấm parse lương, Transformation cấm xóa outlier).

<!-- note:
Hệ thống tiền xử lý được thiết kế theo 5 giai đoạn liên hoàn: Giai đoạn 1 tích hợp cấu trúc, Giai đoạn 2 chuyển hóa định dạng & Cascade regex, Giai đoạn 3 xử lý khuyết thiếu và ngoại lai thống kê, Giai đoạn 4 chuẩn hóa sâu & khử trùng lặp thực thể, và Giai đoạn 4.5 ứng dụng Gemini All-in-One với cơ chế 2-Tier Decision Gate thông minh, bảo toàn Ground-Truth Realism.
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

## 9. Giai Đoạn 4: Khử Trùng Lặp Ngữ Nghĩa Xuyên Sàn (Deduplication)

* **Bản chất bài toán:** 1 vị trí tuyển dụng thường được nhà tuyển dụng đăng chéo trên TopCV, VietnamWorks, TopDev và ITviec với tiêu đề hơi khác nhau.
* **Quy trình Khử trùng lặp 2 Bước (Entity Resolution Pipeline):**
  1. **Lọc thô (Blocking):** Nhóm bài đăng theo `normalized_company` và `province` địa phương để giảm độ phức tạp từ $\mathcal{O}(N^2)$ xuống $\mathcal{O}(K \cdot M^2)$.
  2. **So khớp ngữ nghĩa sâu:** Tính khoảng cách **Cosine Similarity** trên vector nhúng văn bản mô tả công việc (Text Embeddings):
     $$\text{Cosine Sim}(u, v) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|} \ge 0.82$$
  3. **Hợp nhất Bản ghi Vàng (Golden Record Selection):** Giữ lại bài đăng có độ chi tiết cao nhất.
* **Kết quả thực tế:**
  * Phát hiện và gộp chính xác **1,136 bài đăng trùng lặp trong 768 cụm** xuyên sàn ($10.86\%$).
  * Loại trừ **361 tin Stub JDs** quá ngắn (< 30 từ), đưa dữ liệu về **8,959 bản ghi tinh hoa**.

<!-- note:
Ở Bước 4, hệ thống giải quyết triệt để bài toán trùng lặp xuyên sàn. Để không phải tính toán 50 triệu cặp, chúng em dùng Blocking gom cụm công ty và địa phương, sau đó đo Cosine Similarity ngưỡng 0.82. Kết quả là gộp thành công 1.136 bài trùng trong 768 cụm và loại bỏ 361 tin rác stub JD.
-->

---

## 10. Giai Đoạn 4.5: Gemini All-in-One Agent & 2-Tier Decision Gate

* **Sứ mệnh:** Đọc hiểu ngữ nghĩa sâu văn bản JD kết hợp cơ chế kiểm soát chi phí thông minh:
* **Bộ Lọc Quyết Định 2 Tầng (2-Tier Decision Gate):**
  * **Tier 1 (Heuristic Engine):** Quét nhanh Hard Skills qua bộ từ khóa công nghệ không tốn token.
  * **Tier 2 (Gemini 1.5 Flash):** Chỉ kích hoạt khi: (1) Cần dịch thuật JD tiếng Anh sang tiếng Việt (`is_english_job` với dấu tiếng Việt < 2.5%), (2) Tier 1 không tìm thấy skill (`len == 0`), hoặc (3) Bật cờ `--force-ai`.

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 0.78em;">
<div>

### 4 Nhiệm Vụ Single-Pass của Gemini:
1. **Phân loại 3 lớp:** Hard skills (EN), Soft & Domain skills (VN).
2. **Làm giàu yêu cầu:** Bổ sung học vấn, kinh nghiệm, làm T7.
3. **Bản địa hóa:** Dịch tiêu đề, JD, quyền lợi sang tiếng Việt.
4. **Dự đoán lương:** Neo theo ma trận `[Platform x Seniority]`.

</div>
<div>

### Cơ Chế Phục Hồi & Tối Ưu:
* **Checkpoint Store (JSONL):** Tự động lưu từng dòng, phục hồi tức thì khi mất mạng hoặc quota limit.
* **Độc lập Offline:** Hỗ trợ Fallback Heuristic và Mock Mode không cần internet/API key.

</div>
</div>

<!-- note:
Giai đoạn 4.5 là bước đột phá AI với cơ chế 2-Tier Decision Gate. Để không lãng phí token cho 10.000 bài, Tier 1 Heuristic quét từ khóa trước. Chỉ khi bài viết bằng tiếng Anh cần dịch thuật hoặc không bóc được kỹ năng thì Gemini mới được kích hoạt. Đi kèm là CheckpointStore giúp tiến trình bền bỉ chạy tiếp bất cứ lúc nào.
-->

---

## 11. Giai Đoạn 4.5: Ground-Truth Realism & Market Anchor

* **Vấn đề ảo giác của LLM:** Nếu để LLM tự đoán lương, nguy cơ sinh số ảo rất cao!
* **Giải pháp: Khung Mỏ Neo Phân Tầng 4 Cấp (Market Anchor Calculator):**
  * *Cấp 1:* Trung vị thực tế của cặp `[Sàn Tuyển Dụng x Cấp Bậc]` ($N \ge 15$ mẫu).
  * *Cấp 2:* Trung vị cấp bậc toàn thị trường $\rightarrow$ *Cấp 3:* Trung vị toàn sàn $\rightarrow$ *Cấp 4:* Khung sàn lý thuyết IT (Intern 3-6M, Junior 12-20M, Senior 35-55M...).
* **Nguyên tắc Tôn trọng Thực tế Tuyệt đối (Ground-Truth Realism):**
  * **Bảo toàn cơ chế MNAR:** Nếu bài đăng gốc ghi *"Thỏa thuận"* và không có lương cụ thể trong JD, hệ thống **bảo toàn nguyên trạng**:
    $$\text{salary\_min} = \text{null}, \quad \text{salary\_max} = \text{null}, \quad \text{is\_salary\_negotiable} = \text{True}$$
  * Tuyệt đối **không bịa đặt số liệu giả mạo** khi bài đăng không có cơ sở!

<!-- note:
Chúng em đề cao nguyên tắc Ground-Truth Realism: nếu một bài đăng thực sự là lương thỏa thuận, hệ thống sẽ bảo toàn null kèm cờ is_salary_negotiable = True, chứ không bịa đặt số lương giả mạo. Đồng thời, Market Anchor Calculator 4 cấp đảm bảo mọi dự đoán đều nằm vững chắc trong biên độ trung vị thực tế của thị trường.
-->

---

## 12. Giai Đoạn 5: Target Schema Chuẩn 11 Khóa Tinh Gọn

Toàn bộ các trường trung gian, cờ kỹ thuật và cột thô `raw_*` được loại bỏ hoàn toàn, đóng gói dữ liệu về **11 Khóa Gốc Chuẩn Mực**:

```json
{
  "job_id_global": "topcv_123456",
  "source_platform": "topcv",
  "source_url": "https://...",
  "job_info": { "title": "Senior Java Backend Engineer", "job_family": "backend", "work_type": "full_time", "is_remote": false },
  "company": { "name": "FPT Software", "industry": "IT - Phần mềm", "size": "1000+" },
  "locations": [ { "province": "Hà Nội", "district": "Cầu Giấy", "Details_address": "Duy Tân" } ],
  "salary": { "salary_min": 35000000.0, "salary_max": 50000000.0, "salary_currency": "VND", "is_salary_negotiable": false, "salary_source": "explicit_range" },
  "skills": { "hard_skills": ["Java", "Spring Boot", "Docker", "Kafka"], "soft_skills": ["Làm việc nhóm"], "domain_skills": ["Fintech"] },
  "requirements": { "experience_years": 4.0, "standardized_seniority": "senior", "standardized_education": "bachelor", "is_saturday_work": false },
  "jd_text": { "language": "vi", "description": "...", "requirements": "...", "benefits": ["Thưởng dự án", "Bảo hiểm PVI"] },
  "date": { "posted_date": "2026-10-15", "expired_date": "2026-11-15" }
}
```

<!-- note:
Sau khi qua TargetSchemaFormatter, bộ dữ liệu đã được lột xác hoàn toàn: không còn bất kỳ cột thô mang tiền tố raw_, không còn các cờ kỹ thuật phục vụ debug. Toàn bộ 8.959 bản ghi đều chuẩn xác 11 khóa ở root level, cấu trúc lồng nhau được tinh giản gọn gàng, sẵn sàng nạp ngay vào DuckDB, Pandas hoặc các mô hình Machine Learning.
-->

---

## 13. Kiểm Định Chất Lượng Đường Ống (QA 5/5 PASSED)

Báo cáo kiểm định chất lượng tự động (`reports/qa/qa_pipeline_report.md`):

| Bộ Kiểm Định (Check Suite) | Mục Tiêu Kỹ Thuật | Kết Quả Đo Lường | Trạng Thái |
| :--- | :--- | :---: | :---: |
| **Check 1: Lineage & Integrity** | Bảo toàn ID từ F1 sang F2; tỷ lệ khử trùng F2 $\rightarrow$ F3 | $100\%$ ID preserved; Giảm $14.32\%$ mẫu dư thừa | <span class="success">PASSED (0 lỗi)</span> |
| **Check 2: PURE JSON RFC 8259** | Cấm Parquet/CSV, quét sâu đệ quy tìm hằng số `NaN` | `0` Parquet, `0` NaN (100% null RFC 8259) | <span class="success">PASSED (0 lỗi)</span> |
| **Check 3: Golden Master Contract** | Khớp 11 root keys, sạch tiền tố phúc lợi, zero `raw_*` | `0` bản ghi vi phạm cấu trúc | <span class="success">PASSED (0 lỗi)</span> |
| **Check 4: Domain Groups & MNAR** | 10 nhóm nghiệp vụ, bảo toàn MNAR lương thỏa thuận | $100\%$ tuân thủ MNAR & Zero-Null học vấn | <span class="success">PASSED (0 lỗi)</span> |
| **Check 5: Outlier Governance** | Tuân thủ luật chất lượng QR1-QR5, Winsorization | $100\%$ lương nằm trong vùng hợp lệ [4M - 120M] | <span class="success">PASSED (0 lỗi)</span> |

<!-- note:
Tính khoa học của đề tài được khẳng định qua Suite kiểm định QA tự động 5/5 PASSED. Chúng em kiểm tra khắt khe chuẩn RFC 8259: không cho phép bất kỳ hằng số NaN nào tồn tại trong JSON. Dòng dõi dữ liệu từ 10.456 bản ghi thô kế thừa chuẩn xác sang 8.959 bản ghi Golden Master, đảm bảo tính toàn vẹn 100%.
-->

---

## 14. Bảng So Sánh Chỉ Số Chất Lượng (Trước vs Sau)

| Tiêu Chí Đánh Giá | Dữ Liệu Thô Ban Đầu (Raw) | Bộ Dữ Liệu Vàng (Golden Master) | Mức Độ Cải Thiện |
| :--- | :---: | :---: | :---: |
| **Số lượng bản ghi** | 10,456 bản ghi (lẫn trùng lặp) | **8,959 bản ghi độc bản** | Loại bỏ 1,136 bài trùng + 361 stubs |
| **Bảo toàn lương Ground-Truth** | 65% thỏa thuận bị che giấu | **Bảo toàn MNAR + Dải số minh bạch** | Phân định rõ explicit vs negotiable |
| **Độ lệch phân phối lương (Skewness)** | $> 4.01$ (lệch phải nghiêm trọng) | **$-0.66$ (chuẩn hóa Log-scale)** | Đưa về phân phối chuẩn đối xứng |
| **Độ phủ số năm kinh nghiệm** | $48.5\%$ | **$100.0\%$ (Zero-Null)** | Bù khuyết trọn vẹn qua Heuristic/AI |
| **Chuẩn hóa kỹ năng** | Văn bản thô, lẫn tag rác sàn | **3 lớp độc lập (Hard/Soft/Domain)** | Lọc bỏ 2,173 portal noise tags |
| **Chuẩn hóa học vấn** | Chuỗi tự do, nhiều ô trống | **8,621 bản ghi chuẩn hóa** | Phân cấp Đại học/Cao đẳng/Thạc sĩ |
| **Chuẩn hóa địa bàn** | Chuỗi địa chỉ tự do | **Phân cấp Tỉnh/Thành 63 tỉnh** | Thống nhất 100% địa giới |

<!-- note:
Bảng đối chiếu trước và sau tiền xử lý chứng minh hiệu quả toàn diện: từ 10.456 bài thô ban đầu, hệ thống đã tinh gọn về 8.959 bài độc bản, độ lệch phân phối lương Skewness từ 4.01 được đưa về -0.66 gần đối xứng chuẩn, độ phủ kinh nghiệm đạt 100% và 8.621 bài có học vấn chuẩn hóa.
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
