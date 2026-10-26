# QUY CHUẨN KHAI PHÁ DỮ LIỆU HIỆN ĐẠI & QUẢN TRỊ TRÍ TUỆ NHÂN TẠO (DATA MINING & AI GOVERNANCE RULES)

> **Tài liệu quy chuẩn kỹ thuật số 02 (Project Core Rules 02)**  
> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Phạm vi áp dụng:** Bắt buộc (Non-negotiable) cho toàn bộ AI Agents, kỹ sư dữ liệu và các bước trong chuỗi tiền xử lý (Preprocessing), chuyển hóa (Transformation), bù khuyết & ngoại lai (Missing & Outlier), chuẩn hóa (Normalization) và tích hợp (Curated Golden Master).

---

## 1. QUY TẮC 1: TÍNH CHẤT VÒNG LẶP CỦA QUY TRÌNH DATA MINING HIỆN ĐẠI (MODERN CYCLIC FEEDBACK LOOPS)

### 1.1. Bản Chất Khoa Học
- Quy trình Data Mining hiện đại (dựa trên tinh thần **CRISP-DM nâng cao** kết hợp **Modern Data Stack / ELT**) **TUYỆT ĐỐI KHÔNG PHẢI LÀ MỘT QUY TRÌNH ĐƯỜNG THẲNG MỘT CHIỀU (NO RIGID WATERFALL)**.
- Khai phá dữ liệu thực chiến là một quá trình **tuần hoàn, lặp đi lặp lại (Iterative & Cyclic)**. Các bước tiền xử lý không chỉ thực thi một lần duy nhất rồi đóng lại, mà liên tục tiếp nhận phản hồi từ các bước phía sau để quay vòng tinh chỉnh (Feedback-driven Refinement).

### 1.2. Các Vòng Lặp Phản Hồi Bắt Buộc (Mandatory Feedback Loops)
1. **Vòng lặp Phát Hiện Ngoại Lai $\longrightarrow$ Tinh Chỉnh Bóc Tách (Step 3 $\longrightarrow$ Step 2 Loop):**
   - Khi chạy kiểm định phân vị IQR và khảo sát các mút giá trị cực đoan ($Min, Max$) ở Bước 3, nếu phát hiện các giá trị bất thường xuất phát từ lỗi Regex (ví dụ: bóc nhầm số điện thoại sau tên người liên hệ có chữ "Lương", nhầm mã che giấu `1*** USD`, hoặc nhầm dấu chấm phân tách phần nghìn), hệ thống được phép và khuyến khích quay lại tinh chỉnh luật bóc tách trong `salary_parser.py` hoặc kích hoạt bộ lọc làm sạch tiền kiểm định `scrub_salary_false_positives`.
2. **Vòng lặp Chuẩn Hóa Danh Mục $\longrightarrow$ Làm Sạch Văn Bản (Step 4 $\longrightarrow$ Step 2/3 Loop):**
   - Khi thực hiện phân loại chức danh (12 Job Families) hoặc ánh xạ kỹ năng (ESCO Taxonomy) ở Bước 4, nếu tỷ lệ nhãn không xác định (`JF00_OTHER_IT`) hoặc kỹ năng rác vượt quá ngưỡng 15%, hệ thống phải quay lại mở rộng từ điển Stopwords, bóc tách ký tự đặc biệt và làm giàu trường mô tả.
3. **Vòng lặp Khử Trùng Lặp $\longrightarrow$ Đánh Giá Độ Khuyết Thiếu (Step 4 $\longrightarrow$ Step 3 Loop):**
   - Khi hợp nhất các bản ghi trùng lặp xuyên sàn (Cross-Platform Entity Fusion), hồ sơ kỹ năng và mức lương được tổng hợp từ nhiều nguồn sẽ làm giảm tỷ lệ khuyết thiếu thực tế, đòi hỏi tái tính toán lại Bệnh án chất lượng dữ liệu (Quality Health Card).

### 1.3. Nguyên Tắc Bảo Toàn Trong Vòng Lặp
- Dù lặp lại bao nhiêu lần, dữ liệu tại **Bronze Zone (`data/<source>/raw/`)** luôn luôn là **BẤT BIẾN (IMMUTABLE)**.
- Mọi lần lặp đều phải được đánh dấu phiên bản và ghi nhật ký minh bạch trong tệp Manifest (`reports/<source>/<source>_transformation_manifest.md`).

---

## 2. QUY TẮC 2: QUẢN TRỊ TRÍ TUỆ NHÂN TẠO CÓ PHÊ DUYỆT CỦA NHÓM (HUMAN-IN-THE-LOOP AI GOVERNANCE)

### 2.1. Tuyên Ngôn Trách Nhiệm AI
- Trí tuệ nhân tạo (Generative AI, Large Language Models như Google Gemini, Zero-shot Classifiers, Text Embeddings) là **công cụ khuếch đại năng lực phân tích**, không được phép tự tung tự tác hoặc hoạt động như một "hộp đen" không có kiểm soát.
- Mọi can thiệp bằng mô hình AI làm thay đổi hoặc bổ sung giá trị dữ liệu đều phải tuân thủ nghiêm ngặt quy trình phê duyệt của con người (**Human-in-the-Loop - HITL**).

### 2.2. Giao Thức Phê Duyệt 3 Bước Bắt Buộc (Mandatory 3-Step Sign-off Protocol)

Trước khi thực thi bất kỳ tác vụ AI/LLM nào trên toàn bộ kho dữ liệu (9,824 bản ghi):

```text
+----------------------------------------------------------------------------------------------------+
|                         GIAO THỨC 3 BƯỚC PHÊ DUYỆT ỨNG DỤNG AI (AI SIGN-OFF)                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  BƯỚC 1: XÁC ĐỊNH BẢN ĐẶC TẢ KỸ THUẬT (SPECIFICATION DECLARATION)                                 |
|  * Khai báo rõ ràng:                                                                               |
|    - Mục tiêu can thiệp (ví dụ: bù khuyết số năm kinh nghiệm, phân loại 12 Job Family).            |
|    - Tên mô hình chính xác (ví dụ: `gemini-1.5-flash`, `all-MiniLM-L6-v2`).                         |
|    - Cấu trúc Prompt chi tiết (System Instruction + User Input + Output JSON Schema).              |
|    - Dự toán chi phí: Số lượng tokens ước tính, chi phí API (USD), thời gian chạy dự kiến.         |
|    - Cơ chế phòng thủ Fallback: Hành vi của hệ thống khi mất mạng, hết quota hoặc API lỗi.         |
|                                     │                                                              |
|                                     ▼                                                              |
|  BƯỚC 2: CHẠY THỬ NGHIỆM ĐỐI CHỨNG PILOT (BENCHMARK DRY-RUN)                                       |
|  * Rút trích mẫu ngẫu nhiên 20 - 30 bản ghi đại diện từ các sàn khác nhau.                         |
|  * Chạy thử nghiệm và xuất bản tệp báo cáo đối chiếu Song song:                                     |
|    - Bảng so sánh Trước (Before) vs Sau (After).                                                   |
|    - Tỷ lệ ảo giác (Hallucination Rate), độ tin cậy trung bình (`confidence_score`).               |
|    - Lưu tại: `reports/ai_governance/pilot_<task_name>_benchmark.md`.                              |
|                                     │                                                              |
|                                     ▼                                                              |
|  BƯỚC 3: XÁC NHẬN CHÍNH THỨC TỪ BẠN & TEAM (MANDATORY USER & TEAM SIGN-OFF)                        |
|  * AI Agent KHÔNG ĐƯỢC PHÉP tự động chạy batch hàng loạt nếu chưa nhận được lệnh đồng ý bằng văn bản|
|    hoặc tham số kích hoạt tường minh (`--approved` / `team_approved=True`).                        |
|  * Nếu chưa có phê duyệt, hệ thống mặc định kích hoạt bộ xử lý thuần tất định (Deterministic       |
|    Heuristic Fallback) để không làm gián đoạn pipeline.                                            |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 2.3. Minh Bạch Dấu Vết (Provenance & Auditability)
Mọi trường dữ liệu được tạo ra hoặc bổ sung bởi mô hình AI bắt buộc phải gắn các cờ kiểm toán:
1. `is_imputed_by_genai`: Kiểu `bool` (`True`/`False`).
2. `genai_model_name`: Chuỗi định danh mô hình (ví dụ: `"gemini-1.5-flash"`).
3. `genai_confidence_score`: Số thực từ `0.0` đến `1.0`.
4. `imputed_fields`: Mảng danh sách tên các trường mà AI đã can thiệp (ví dụ: `["min_experience_years", "skills_list"]`).

---

## 3. KHUNG RANH GIỚI ĐANH THÉP CHO TẤT CẢ CÁC BƯỚC XỬ LÝ (IRONCLAD BOUNDARY ENFORCEMENT)

Để đảm bảo trật tự và ngăn chặn hiện tượng Agent làm sai lệch phạm vi nhiệm vụ:

| Bước Xử Lý | Trách Nhiệm Cốt Lõi | Hành Động Được Cho Phép | Hành Động Tuyệt Đối Cấm | Giới Hạn Ứng Dụng AI |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1: Integration** | Ép phẳng JSON, ánh xạ schema chung | Ánh xạ tên cột, làm phẳng dict/list/jsonld, tạo `job_id_global` | **CẤM** parse số lương, đổi ngoại tệ, drop hàng, fillna | **CẤM DÙNG** (100% Deterministic) |
| **Step 2: Transformation** | Bóc tách kiểu dữ liệu, chuẩn hóa dải số & ngày tháng | Regex lương, quy đổi USD/SGD $\rightarrow$ VND, ISO dates, text metrics | **CẤM** xóa outlier, fill mean/median, log-scale | Fallback đơn lẻ khi regex JD quá phức tạp |
| **Step 3: Missing & Outlier** | Bóc trần null giả, bù khuyết, xử lý ngoại lai | Unmask 9+ null markers, scrub lương ảo (SĐT/masked), IQR & Winsorization P1-P99 | **CẤM** fill mean/median vào tin thỏa thuận (MNAR), CẤM drop bài có kỹ năng | **TRỌNG TÂM:** Bù khuyết JD text (Bắt buộc qua Giao thức Sign-off) |
| **Step 4: Normalization** | Chuẩn hóa phân phối, từ điển phân loại & khử trùng | Log-transform $y=\log(1+x)$, RobustScaler, 63 tỉnh, 6 cấp bậc, Deduplication | **CẤM** scale trước khi xử lý outlier, CẤM ghi đè làm mất trường văn bản gốc | Phân loại 12 Job Family & Embedding ESCO (Bắt buộc Pilot duyệt) |
| **Curated Master** | Xuất bản Bộ Dữ Liệu Vàng | Lọc bỏ tin rác siêu ngắn (Stub JD < 30 từ), xuất Parquet/CSV sạch | **CẤM** can thiệp làm biến dạng phân phối đã chuẩn hóa | Chỉ dùng để kiểm định chất lượng tổng thể |
