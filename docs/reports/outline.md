# Outline tiểu luận

**Đề tài:** Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT

**Cách dùng outline này:**
- Pipeline có 4 giai đoạn: Thu thập → Tiền xử lý → Xử lý đặc trưng → Khai phá.
- Mỗi giai đoạn là một mục lớn và có mặt ở cả Chương 2 và Chương 3 với cùng số thứ tự: 2.1 ↔ 3.3.1 là Thu thập, 2.2 ↔ 3.3.2 là Tiền xử lý, 2.3 ↔ 3.3.3 là Xử lý đặc trưng, 2.4 ↔ 3.3.4 là Khai phá.
- **Chương 2** nói về lý thuyết đã áp dụng vào pipeline: nguyên lý, thuật toán, luồng hoạt động.
- **Chương 3** viết mã giả, kèm đường dẫn tới code thật để gắn vào bài.
- **Chương 4** đánh giá bằng thực nghiệm và nhận xét.

Số liệu trong ngoặc lấy từ lần chạy thật 22/11/2026 (3.718 tin), xem `docs/spec/08_evaluation_spec.md`.

---

## MỞ ĐẦU

- Lý do chọn đề tài: sinh viên IT thiếu bức tranh thực tế về nhu cầu tuyển dụng; tin tuyển dụng nằm rải rác trên nhiều sàn.
- Mục tiêu: 5 câu hỏi SD1–SD5 (`docs/target/00_de_tai.md`).
- Đối tượng và phạm vi:
  - 8 sàn: TopCV, TopDev, VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO.
  - Tin đăng tháng 9–11/2026.
  - Chỉ có phía nhà tuyển dụng.
- Bố cục tiểu luận.

---

## CHƯƠNG 1: CƠ SỞ LÝ THUYẾT

### 1.1. Tổng quan về khai phá dữ liệu
- Định nghĩa; quy trình KDD và CRISP-DM.
- Ánh xạ CRISP-DM vào dự án (`docs/spec/03_data_mining_lifecycle.md`).

### 1.2. Các khái niệm cơ bản
- **Tích hợp dữ liệu** (data integration) và kiến trúc ELT.
- **Lakehouse phân tầng:** Bronze (raw), Silver (bảng sạch), Gold.
- **Năm tiêu chí chất lượng dữ liệu:** completeness, accuracy, consistency, timeliness, uniqueness.
- **Biểu diễn dữ liệu văn bản:**
  - Giỏ kỹ năng (transaction).
  - Ma trận multi-hot.
  - Vector nhúng ngữ nghĩa (embedding).

### 1.3. Phân loại kỹ thuật khai phá dữ liệu
- **1.3.1. Thống kê mô tả và BI:** phân phối, trung vị, IQR, dữ liệu thiếu không ngẫu nhiên (MNAR).
- **1.3.2. Luật kết hợp:** support, confidence, lift; Apriori và FP-Growth.
- **1.3.3. Phân cụm:** K-Means, HDBSCAN; các độ đo Silhouette, Davies–Bouldin, ARI, NMI.
- **1.3.4. Phát hiện bất thường:** Isolation Forest, GLOSH.
- **1.3.5. Giảm chiều:** TruncatedSVD, PCA.
- **1.3.6. Học có giám sát và giải thích mô hình:** Random Forest, SHAP; chia dữ liệu theo nhóm để tránh rò rỉ.

### 1.4. Mối quan hệ giữa các kỹ thuật
- Sơ đồ: BI (SD1) → không giám sát (SD2, SD3) → có giám sát (SD4) → tổng hợp (SD5).
- Kết quả bước trước làm đầu vào cho bước sau: luật SD2 và giá trị SHAP của SD4 dùng để xếp lộ trình SD5.

### 1.5. Các nghiên cứu và hệ thống liên quan *(tùy chọn)*
- Phân tích tin tuyển dụng, phân loại nghề, trích kỹ năng.
- Điểm khác của đề tài: dữ liệu Việt Nam, 8 nguồn, chỉ dùng luật đã duyệt cho phân loại.

---

## CHƯƠNG 2: THUẬT TOÁN, NGUYÊN LÝ VÀ LUỒNG HOẠT ĐỘNG CỦA PIPELINE

> Mỗi mục lớn tương ứng một giai đoạn của pipeline. Mỗi thuật toán trình bày theo khuôn: nguyên lý → các bước → flow (sơ đồ).

### 2.1. Thu thập dữ liệu (Collection)
- **2.1.1. Nguyên lý cào hai pha**
  - Discovery: quét danh sách, chuẩn hóa URL.
  - Detail: lấy trang chi tiết.
  - Sổ cái URL (URL Ledger) làm hợp đồng giữa hai pha.
- **2.1.2. Phát hiện thay đổi (CDC) bằng hàm băm**
  - Băm SHA-256 trên JSON đã chuẩn hóa khóa.
  - Phiên bản `_v<N>`; chu kỳ cào lại.
- **2.1.3. Lưu trữ bất biến:** RawJobEnvelope (metadata + raw_payload) trên Cloudflare R2.
- **2.1.4. Cào lịch sự và chịu lỗi:**
  - Nghỉ ngẫu nhiên 2–4,5 giây giữa các lần gọi.
  - Safe Skip: bỏ qua trang lỗi mà không dừng tiến trình.
  - Giả lập TLS khi cần.
- **2.1.5. Flow:** vòng đời trạng thái của một URL (PENDING → DONE / FAILED → cào lại).

### 2.2. Tiền xử lý dữ liệu (Pre-processing, bước 01–04)
- **2.2.1. Lọc tin IT bằng luật ba tầng**
  - Tầng 0: loại theo chức danh.
  - Tầng 1: từ khóa.
  - Tầng 2: điểm kỹ năng.
  - Danh sách tin đã duyệt tay.
- **2.2.2. Khử trùng lặp**
  - Trong một nguồn: URL, hash nội dung.
  - Giữa các nguồn: blocking, shingle + MinHash/LSH, Jaccard.
  - Gom cụm và chọn bản ghi đại diện (survivorship).
- **2.2.3. Tích hợp lược đồ:** làm phẳng JSON 8 nguồn về một bảng chung (schema mapping).
- **2.2.4. Biến đổi và ép kiểu**
  - Tách lương: khoảng, một đầu, USD → VND.
  - Tách kinh nghiệm, ngày, `posted_month`.
  - Làm sạch HTML, nối bullet.
- **2.2.5. Chuẩn hóa chuỗi:** chức danh (so khớp mờ có chặn đảo viết tắt), 34 tỉnh, cấp bậc, hình thức làm việc.
- **2.2.6. Gán nhóm nghề bằng luật:** thứ tự ưu tiên chức danh cụ thể → từ khóa → JD.
- **2.2.7. Xử lý dữ liệu thiếu và ngoại lai:**
  - Giữ dữ liệu thiếu có cờ (MNAR với lương thỏa thuận).
  - Gắn cờ ngoại lai theo IQR, không xóa.
- **2.2.8. Flow:** phễu 13.361 → 3.899 → 3.800 → 3.799 → 3.718 tin, kèm kiểm tra bảo toàn ở mỗi bước.

### 2.3. Xử lý và xây dựng đặc trưng (Processing, bước 07–12)
- **2.3.1. Tách mục JD:** mô tả / yêu cầu / phúc lợi.
- **2.3.2. Trích kỹ năng bằng từ điển:**
  - Alias và biên từ.
  - Ba góc nhìn: K-tool, K-concept, K-soft.
- **2.3.3. Feature engineering:**
  - Chọn: `min_df`.
  - Trích.
  - Biến đổi: log lương, one-hot.
  - Xây dựng: `n_tools`, `salary_target_m`.
- **2.3.4. Vector ngữ nghĩa:** multilingual-e5-base; dịch JD tiếng Anh bằng envit5 (chạy trên máy).
- **2.3.5. Flow:** từ bảng Silver ra ma trận 3.718 × 973 và vector 768 chiều.

### 2.4. Khai phá dữ liệu (Mining, M1–M6)
- **2.4.1. BI cho SD1:** bảng chéo, trung vị theo cấp và nghề, quy tắc "ít dữ liệu" khi n < 30.
- **2.4.2. FP-Growth cho SD2:**
  - Giỏ công cụ; phân tầng theo nghề × nhóm cấp.
  - Định nghĩa kỹ năng hiếm.
  - Kiểm độ ổn định khi đổi ngưỡng support.
- **2.4.3. Phân cụm cho SD3:**
  - Ghép ba khối có trọng số (tool / concept / e5).
  - SVD → K-Means (k = 10, `n_init` 150); quét k từ 2 đến 20.
  - Đo độ ổn định bằng ARI qua 5 seed.
- **2.4.4. Phát hiện tin "khác hoặc mới":**
  - Isolation Forest kèm mã lý do; GLOSH của HDBSCAN.
  - Ngưỡng đặt theo phân vị dữ liệu.
- **2.4.5. Mô hình lương cho SD4:**
  - Random Forest trên log lương; chia theo công ty (GroupShuffleSplit / GroupKFold).
  - Baseline trung vị cấp × nghề.
  - SHAP và quy đổi ra triệu/tháng.
- **2.4.6. Lộ trình học cho SD5:**
  - Điểm = nhu cầu × (1 + giá trị chuẩn hóa).
  - Thứ tự theo luật SD2; kỹ năng "để sau".
  - coverage@N, kiểm tra 80/20.
- **2.4.7. Flow:** chuỗi `bi → fp → cluster → anomaly → salary → recommend` và các artifact đầu ra.

---

## CHƯƠNG 3: XÂY DỰNG VÀ LẬP TRÌNH (IMPLEMENTATION)

### 3.1. Môi trường và công cụ
- **Ngôn ngữ:** Python 3.12, TypeScript.
- **Lưu trữ:** Cloudflare R2, Parquet.
- **Thu thập:** curl_cffi, Playwright, BeautifulSoup.
- **Xử lý:** pandas, NumPy, DuckDB.
- **Khai phá:** scikit-learn, mlxtend (FP-Growth), hdbscan, SHAP, sentence-transformers.
- **Hệ thống:** Apache Airflow (lập lịch cào), FastAPI + React (giám sát), pytest.

### 3.2. Thiết kế hệ thống
- Kiến trúc tổng thể (`docs/spec/10_architecture.md`): 8 sàn → R2 (`url_ledger/`, `raw/`) → Silver → đặc trưng → `mining/artifacts/` → dashboard.
- Cấu trúc thư mục: `collection/`, `preprocessing/`, `processing/`, `mining/`, `monitoring/`.
- Lược đồ dữ liệu:
  - RawJobEnvelope.
  - Bảng Silver 26 trường (`docs/spec/preprocessing/silver.md`).
  - Ma trận đặc trưng.
  - Artifact Mining.
- Hợp đồng giữa các bước: báo cáo `reports/`, kiểm tra bảo toàn, sha256 đầu vào.

### 3.3. Các chức năng chính (mã giả)

> Mỗi mục: mã giả ngắn + đường dẫn code thật để trích đoạn.

- **3.3.1. Thu thập dữ liệu**
  - *Mã giả Discovery:* duyệt trang → `clean_canonical_url` → ghi PENDING. Code: `collection/common/url_ledger.py`.
  - *Mã giả Detail và CDC:* lấy trang → dựng envelope → `calculate_json_canonical_hash` → so hash cũ → ghi `_v<N>` hoặc bỏ qua. Code: `collection/<nguồn>/crawler.py`, `collection/common/url_ledger.py`.
  - *Mã giả Safe Skip và nghỉ ngẫu nhiên.*
- **3.3.2. Tiền xử lý**
  - *Lọc IT ba tầng:* `preprocessing/common/it_filter.py`, `preprocessing/clean/run.py`.
  - *Khử trùng:*
    - Shingle, MinHash, Jaccard: `preprocessing/deduplication/minhash.py`.
    - Blocking, gom cụm, chọn bản ghi đại diện: `preprocessing/deduplication/inter_source.py`.
  - *Làm phẳng 8 nguồn:* `preprocessing/integration/json_flattener.py`.
  - *Tách lương và kinh nghiệm:* `preprocessing/transformation/salary_parser.py`, `experience_parser.py`.
  - *Chuẩn hóa chức danh và gán nhóm nghề:* `preprocessing/normalization/job_title.py` (`canonical_title`, `family_from_title`).
- **3.3.3. Xử lý đặc trưng**
  - *Tách mục JD:* `processing/extraction/sections.py`.
  - *Trích kỹ năng theo từ điển:* `processing/extraction/skills.py`.
  - *Dựng ma trận đặc trưng:* `processing/construction/features.py`.
  - *Nhúng e5:* `processing/extraction/embed.py`.
- **3.3.4. Khai phá**
  - *FP-Growth phân tầng, kỹ năng hiếm:* `mining/association.py` (`mine_stratified_rules`, `rare_skills`).
  - *Không gian vector, K-Means, độ ổn định, đặt tên cụm:* `mining/clustering.py`.
  - *Bất thường và mã lý do:* `mining/anomaly.py` (`_reason_codes`, `classify_kind`).
  - *Mô hình lương:*
    - Chia theo công ty: `company_split`.
    - Baseline: `baseline_level_family`.
    - Quy đổi SHAP: `skill_values_from_shap`.
    - Code: `mining/salary_model.py`.
  - *Lộ trình học:* `mining/recommend.py`.

### 3.4. Code minh họa
- Chọn 4–6 đoạn tiêu biểu, mỗi giai đoạn ít nhất một đoạn:
  - Hash CDC.
  - MinHash.
  - Luật nhóm nghề.
  - FP-Growth.
  - K-Means + ARI.
  - GroupShuffleSplit + SHAP.
- Lệnh chạy:
  - `run.py`
  - `scripts/run_preprocessing.py --step all --source all`
  - `python -m mining.run_mining_pipeline`

### 3.5. Kiểm thử
- Kiểm thử phân tầng:
  - unit;
  - integration;
  - contract (chuẩn crawler C1–C14 trên mẫu offline);
  - test cần dữ liệu thật.
- Chặn mạng trong test; dữ liệu giả chỉ dùng cho test.
- Sanity check S-01..S-06 trên kết quả thật (`mining/sanity.py`).
- Kết quả: 889 test qua, 5 bỏ qua, 0 hỏng (23/11/2026).

---

## CHƯƠNG 4: ĐÁNH GIÁ VÀ DEMO

### 4.1. Demo hệ thống
- Dashboard giám sát (FastAPI + React): Collection, EDA, Pre-processing, Processing, Market Insights.
- Slide kết quả có biểu đồ tương tác: bản đồ 10 cụm 2D/3D (`docs/presentation/final_slides.html`).

### 4.2. Đánh giá chất lượng dữ liệu (theo 5 tiêu chí)
- **Uniqueness:** khử trùng 1.987 + 616 tin trong một nguồn và 99 tin giữa các nguồn.
- **Accuracy:**
  - Bộ lọc IT.
  - Nhóm nghề: chấm tay 26/39 → 34/39.
  - Danh sách 182 tin không phải IT đã duyệt.
- **Completeness:** độ phủ lương 43,6%; tỉnh; kinh nghiệm.
- **Consistency:** 8 nguồn chung một lược đồ và một bộ nhãn.
- **Timeliness:** `posted_month`, ledger và CDC.

### 4.3. Kết quả khai phá theo SD1–SD5
- **SD1:**
  - Cơ cấu nghề, cấp bậc, tỉnh.
  - Lương tăng theo cấp: 10,0 / 15,5 / 22,5 / 37,5 triệu.
  - MNAR ở cấp Lead.
- **SD2:**
  - 12.642 luật; luật tiêu biểu.
  - 124 kỹ năng hiếm.
  - Độ ổn định: trùng 98% / 89% khi đổi support.
- **SD3:**
  - 10 cụm; ARI 5 seed 0,83.
  - Silhouette 0,075 ở mọi k.
  - Bảng chéo cụm × nghề; phát hiện IT Manager rơi vào cụm hạ tầng.
  - 233 tin bất thường.
- **SD4:**
  - MAE 6,1 so với 7,3 triệu (hơn baseline 16,7%); R² 0,56.
  - Tỷ trọng SHAP; giá trị từng kỹ năng.
- **SD5:**
  - Lộ trình 8 nghề; coverage@10 so với baseline.
  - 4/8 nghề ổn định khi chia 80/20.

### 4.4. So sánh các phương pháp
- Có e5 và không có e5 khi phân cụm: NMI với nhóm nghề 0,32 so với 0,47.
- `n_init` 10 / 50 / 150 với độ ổn định cụm: ARI 0,73 / 0,79 / 0,83.
- Random Forest so với baseline trung vị; chỉ dùng công cụ so với công cụ + khái niệm (MAE 6,23 so với 6,11).
- Luật nhóm nghề trước và sau khi sửa (tỷ lệ Other 15,7% → 10,1%).
- Loại "khác" so với "mới" khi kiểm tay tin bất thường: 8/8 so với 2/9.

### 4.5. Nhận xét
- **Điểm đạt:** các cổng nghiệm thu đều đạt, chạy lại ra cùng số, mọi số đều là số thật.
- **Hạn chế:**
  - Ranh giới nghề IT chồng lấn.
  - Chỉ 44% tin công bố lương.
  - Tỉnh lấy theo trụ sở công ty ở một số sàn.
  - Chỉ một kỳ 3 tháng.
  - Độ đúng nhóm nghề chưa đo trên mẫu độc lập.

---

## KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN
- Câu trả lời cho SD1–SD5 (một câu mỗi SD) và gợi ý cho sinh viên IT.
- Hướng phát triển:
  - Thu thập nhiều kỳ để so theo thời gian.
  - Đo lại nhóm nghề trên mẫu độc lập.
  - Lấy tỉnh theo nơi làm việc.
  - Mở rộng sang phía ứng viên.

## TÀI LIỆU THAM KHẢO
- Sách và bài báo về KDD/CRISP-DM, FP-Growth, K-Means, HDBSCAN/GLOSH, Isolation Forest, Random Forest, SHAP, mô hình e5.

## PHỤ LỤC
- **A.** Bảng 26 trường Silver.
- **B.** Danh sách luật lọc IT và luật nhóm nghề.
- **C.** Bảng nghiệm thu đầy đủ (spec 08 mục 3).
- **D.** Hướng dẫn chạy lại pipeline.
