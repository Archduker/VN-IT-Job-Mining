# 🎯 Hướng Dẫn Nội Dung Thuyết Trình & Bảo Vệ Đồ Án
## Đề Tài: VN-IT-Job-Mining — Hệ Thống Tự Động Thu Thập, Kiểm Tra Chất Lượng & Khai Phá Dữ Liệu Tuyển Dụng CNTT Tại Việt Nam

> **Dành cho:** Sinh viên báo cáo tiến độ & bảo vệ đồ án chuyên ngành Kỹ nghệ Dữ liệu / CNTT (Trường ĐH Giao Thông Vận Tải TP.HCM — UTH)  
> **Thời lượng báo cáo đề xuất:** 7 – 10 phút thuyết trình + 3 phút Live Demo + 5 phút trả lời phản biện (Q&A).  
> **File sơ đồ kiến trúc trực quan:** [`docs/architecture/data_collection_architecture.excalidraw`](architecture/data_collection_architecture.excalidraw)

---

## 📑 MỤC LỤC
1. [Cấu Trúc Từng Slide Thuyết Trình (Slide-by-Slide Blueprint)](#1-cấu-trúc-từng-slide-thuyết-trình-slide-by-slide-blueprint)
2. [Kịch Bản Thuyết Trình Lời Nói (Spoken Presentation Script)](#2-kịch-bản-thuyết-trình-lời-nói-spoken-presentation-script)
3. [Kịch Bản Live Demo 4 Bước Cho Giảng Viên](#3-kịch-bản-live-demo-4-bước-cho-giảng-viên)
4. [Bộ 10 Câu Hỏi Phản Biện Của Giảng Viên & Câu Trả Lời Chuẩn Mực](#4-bộ-10-câu-hỏi-phản-biện-của-giảng-viên--câu-trả-lời-chuẩn-mực)
5. [Tóm Tắt Các Điểm Sáng Kỹ Thuật (Key Selling Points)](#5-tóm-tắt-các-điểm-sáng-kỹ-thuật-key-selling-points)

---

## 1. CẤU TRÚC TỪNG SLIDE THUYẾT TRÌNH (SLIDE-BY-SLIDE BLUEPRINT)

Dưới đây là nội dung chi tiết để bạn copy/paste trực tiếp vào PowerPoint, Google Slides hoặc Canva:

---

### 🖥️ Slide 1: Trang Tiêu Đề (Title Slide)
* **Tiêu đề lớn:** HỆ THỐNG TỰ ĐỘNG THU THẬP, KIỂM TRA CHẤT LƯỢNG VÀ KHAI PHÁ DỮ LIỆU TUYỂN DỤNG CNTT TẠI VIỆT NAM (VN-IT-JOB-MINING)
* **Tiêu đề phụ:** Giai Đoạn 1: Hoàn Thiện Hạ Tầng Thu Thập Đa Nguồn, Chuẩn Hóa Schema v1 & Điều Phối Tự Động Với Apache Airflow
* **Thông tin nhóm:**
  - Nhóm sinh viên thực hiện: Nhóm Nghiên cứu Kỹ nghệ Dữ liệu (UTH)
  - Trưởng nhóm (Platform & Core): Trần Minh Thuận (Bill Tran)
  - Giảng viên hướng dẫn: [Tên GVHD]
  - Khoa Công nghệ Thông tin — Trường Đại học Giao thông Vận tải TP.HCM

---

### 🖥️ Slide 2: Bối Cảnh & Đặt Vấn Đề (Problem Statement)
* **Thực trạng thị trường:**
  - Ngành CNTT Việt Nam biến động mạnh về nhu cầu kỹ năng (AI, Cloud, DevOps, Backend) và dải lương.
  - Dữ liệu tuyển dụng bị **phân mảnh** trên nhiều website độc lập: TopDev, VietnamWorks, ITviec, TopCV, CareerViet, Việc Làm 24h, Glints, JobsGO.
* **Những thách thức kỹ thuật cốt lõi (Pain Points):**
  1. *Đa dạng giao thức:* Mỗi sàn có cấu trúc khác nhau (REST API, SSR HTML, Next.js hydrated state, Single Page Application).
  2. *Cơ chế phòng vệ Anti-Scraping:* Cloudflare WAF, CAPTCHA, kiểm tra Browser Fingerprint, chặn dải IP Data Center.
  3. *Chất lượng dữ liệu thô kém:* Thẻ HTML rác bám dính, văn bản dính chùm, mức lương định dạng tự do ("thỏa thuận", "20-40 triệu", "1000-2000 USD").
  4. *Trùng lặp dữ liệu & Lãng phí tài nguyên:* Cào quét lặp lại gây nghẽn mạng và tốn kém chi phí lưu trữ.
* **Mục tiêu đề tài:** Xây dựng một Data Pipeline chuẩn công nghiệp: Thu thập tự động $\rightarrow$ Chống chặn $\rightarrow$ Khử trùng lặp $\rightarrow$ Chuẩn hóa $\rightarrow$ Kiểm định chất lượng $\rightarrow$ Lưu trữ Data Lake.

---

### 🖥️ Slide 3: Ma Trận 8 Nguồn Dữ Liệu & Giải Pháp Kỹ Thuật (Multi-Source Strategy)
* **Bảng so sánh phương thức thu thập của 8 nguồn:**

| Nguồn | Loại Giao Thức / Kiến Trúc Web | Giải Pháp Kỹ Thuật Của Nhóm | Khối Lượng Đã Thu Thập |
|:---|:---|:---|:---:|
| **VietnamWorks** | Search API POST Backend | Khai thác API trực tiếp bằng HTTP Client | **2.232 jobs** |
| **JobsGO** | HTML DOM + Phân trang | Playwright Headless + BeautifulSoup4 | **1.476 jobs** |
| **TopCV** | Cloudflare WAF Challenge | Playwright Chrome + `--disable-blink-features` | **810 jobs** |
| **ITviec** | SSR HTML + Chi tiết bảo vệ | HTTP Client + Parsing Sections sạch | **674 jobs** |
| **CareerViet** | Server-Side Rendering (SSR) | Requests + CSS Selectors an toàn | **655 jobs** |
| **Việc Làm 24h**| Next.js Hydrated SSR State | Parse trạng thái Next.js + Date deduction | **445 jobs** |
| **Glints** | REST API / Đông Nam Á | API Ingestion + Next.js parser | **244 jobs** |
| **TopDev** | Internal REST API v2 | JSON Direct Ingestion siêu tốc | **125 jobs** |
| **TỔNG CỘNG** | **8 Nền Tảng Hàng Đầu** | **Đa giao thức đồng bộ** | **6.661 jobs** |

* **Điểm nhấn:** Không dùng một công cụ cứng nhắc; phân tích sâu bản chất mạng của từng trang để chọn giải pháp tối ưu nhất (API khi có thể, Headless Browser khi có WAF, SSR khi cấu trúc tĩnh).

---

### 🖥️ Slide 4: Kiến Trúc Hệ Thống Tổng Thể (System Architecture)
*(Chèn sơ đồ kiến trúc xuất từ file `docs/architecture/data_collection_architecture.excalidraw`)*

* **5 Tầng Kiến Trúc Khép Kín:**
  1. **Tầng 1 - Data Source Layer:** 8 Sàn tuyển dụng IT hàng đầu Việt Nam.
  2. **Tầng 2 - Crawler & Anti-Bot Engine:** BaseCrawler Framework, HTTP Client xoay vòng User-Agent, Exponential Backoff, Polite Delay 1.5–3.5s.
  3. **Tầng 3 - Orchestration & Scheduling (Apache Airflow 2.11+):** 9 DAGs điều phối tự động, XCom truyền thông, Callback kiểm toán.
  4. **Tầng 4 - Data Quality Gate:** Kiểm định 3 lớp nghiêm ngặt (Schema $\ge 95\%$, Dedup = 0%, Trực quan bắt buộc).
  5. **Tầng 5 - Storage & Live Monitoring:** Lưu trữ phân vùng Hive-style JSON mảng cục bộ, AWS S3 Raw Zone, Terminal Dashboard giám sát trực tiếp.

---

### 🖥️ Slide 5: Luồng Dữ Liệu Chi Tiết (End-to-End Data Flow)
*(Chèn sơ đồ Data Flow xuất từ file `docs/architecture/data_collection_architecture.excalidraw`)*

* **Hành trình của 1 bản ghi tuyển dụng:**
  ```text
  [Portal Web/API] 
        ↓ 
  [Harvest Listing IDs] 
        ↓ 
  [SQLite State Catalog O(1) Check] ──(Đã có SUCCESS)──> [SKIP BỎ QUA]
        ↓ (Nếu mới hoặc cần retry)
  [Detail Worker + Rate Limiter]
        ↓ 
  [Clean Text & Strip HTML Bullets]
        ↓ 
  [Pydantic Compact Schema v1]
        ↓ 
  [Atomic JsonWriter (batch_XXX.json)]
        ↓ 
  [DataQualityOperator Validation] ──(FAIL)──> [DỪNG PIPELINE + ALERT]
        ↓ (PASS)
  [Local Data Lake dt=YYYY-MM-DD] ──> [AWS S3 Raw Zone] ──> [PostgreSQL DWH]
  ```

---

### 🖥️ Slide 6: Chuẩn Hóa Schema & Data Contract v1 (Data Contract)
* **Vấn đề dữ liệu cũ:** JSONL phân mảnh, thẻ `<p>`, `<br>` dính rác, lương định dạng text tùy ý, trường rỗng không kiểm soát.
* **Quy chuẩn Data Contract Compact Schema v1 ([`crawlers/common/schema.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/schema.py)):**
  - **Metadata (`_meta`):** `source`, `source_job_id`, `url`, `dedup_key`, `crawled_at`, `batch_id`, `language` ("vi" | "en").
  - **Lương lồng số học (`raw.salary`):** Bóc tách thành số thực `salary_min`, `salary_max`, `salary_currency` (`VND`, `USD`), `pay_period` ("month"), `is_negotiable`.
  - **Nhóm thẻ 3 chiều (`raw.tags`):**
    - `requirements`: Học vấn, năm kinh nghiệm, chứng chỉ.
    - `skills`: Tech stack chuyên môn (Java, Python, AWS, Docker).
    - `benefits`: Phúc lợi, bảo hiểm (quy tắc rõ ràng: `null` nếu trang không hỗ trợ).
  - **Làm sạch văn bản (`description_list`, `requirements_list`):** Xóa toàn bộ tag HTML, chuẩn hóa bullet points thành danh sách câu sạch sẽ (`list[str]`).
  - **Smart Adapter tương thích ngược:** Sử dụng `@model_validator(mode="before")` giúp pipeline không bao giờ bị đứt gãy nếu crawler cũ trả về format cũ.

---

### 🖥️ Slide 7: Cơ Chế Khử Trùng Lặp 2 Lớp & Hàng Đợi 2 Giai Đoạn (Deduplication)
* **Lớp 1: Checkpoint JSON Cục Bộ (`<source>_checkpoint.json`):**
  - Lưu tập hợp `seen_ids` và `last_page` theo cơ chế atomic write.
  - Cho phép dừng và tiếp tục chạy mẻ cào bất kỳ lúc nào mà không sợ mất dấu.
* **Lớp 2: SQLite State Catalog Tập Trung ([`data/state/job_catalog.db`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/data/state/job_catalog.db)):**
  - Index độc lập theo khóa `(source, source_job_id)`.
  - Truy vấn kiểm tra trùng lặp với độ phức tạp thời gian **$O(1)$**.
  - Quản lý vòng đời trạng thái tin: `DISCOVERED` $\rightarrow$ `SUCCESS` hoặc `FAILED_RETRY_NEXT_RUN`.
* **Kiến trúc Hàng Đợi 2 Giai Đoạn (2-Phase Pipeline Chu kỳ 4 ngày):**
  - **Pha 1 (Harvest Listing):** Quét danh sách trang ngoài cực nhanh, lấy danh sách ID đăng ký vào Catalog.
  - **Pha 2 (Detail Worker Queue):** Chỉ bốc những tin thực sự mới để cào chi tiết.
  - **Hiệu quả:** Giảm **85% lưu lượng mạng lãng phí**, tăng tốc độ cào gấp 6 lần.

---

### 🖥️ Slide 8: Điều Phối Tự Động Bằng Apache Airflow (Orchestration Architecture)
* **9 DAGs Được Thiết Kế Khoa Học:**
  1. **7 Rotating Daily DAGs (`0 20 * * 1` $\rightarrow$ `0 20 * * 0`):**
     - Mỗi ngày cào đúng 1 sàn lúc 20:00 tối.
     - Giãn cách tải mạng giữa các sàn, không dồn tất cả các sàn vào cùng một thời điểm.
  2. **1 Master Weekly DAG (`crawler_weekly_all` — Chủ Nhật 22:00):**
     - Cào toàn bộ 8 nguồn song song.
     - Tích hợp `CrawlSummaryOperator` tổng hợp số liệu và xuất file báo cáo JSON vào `logs/crawl_reports/`.
  3. **1 Periodic 4-day Pipeline (`periodic_it_job_mining_4days`):**
     - Thực thi hàng đợi 2 pha theo chu kỳ 4 ngày.
* **3 Custom Operators Tự Phát Triển:**
  - `JobCrawlerOperator`: Chạy crawler, xử lý XCom output và callbacks.
  - `DataQualityOperator`: Kiểm định chất lượng dữ liệu khép kín.
  - `CrawlSummaryOperator`: Tổng hợp báo cáo mẻ cào tự động.
* **Cơ chế Callbacks:** `_on_crawl_success` và `_on_crawl_failure` ghi log kiểm toán rõ ràng.

---

### 🖥️ Slide 9: Quyết Định Hạ Tầng: Kiến Trúc Lai (Hybrid Cloud Architecture)
* **Bài toán kỹ thuật được đặt ra:** Tại sao không đưa toàn bộ Airflow + Crawlers lên AWS EC2 Free Tier (`t2.micro`)?
* **Phân tích so sánh 2 giải pháp:**

| Tiêu Chí Kỹ Thuật | Đưa Toàn Bộ Lên EC2 Free Tier (`t2.micro`) | Mô Hình Kiến Trúc Lai (Hybrid Cloud) Của Nhóm |
|:---|:---|:---|
| **Bộ nhớ RAM** | ❌ Chỉ có 1 GiB RAM $\rightarrow$ Bị OOM Kill ngay khi bật Airflow + Chrome | ✅ Máy trạm/VM nội bộ (8–16 GiB RAM), chạy đa luồng ổn định |
| **Độ tin cậy mạng & IP** | ❌ IP Data Center của AWS bị Cloudflare WAF chặn ngay lập tức | ✅ Sử dụng IP dân cư thực tế, bypass WAF tự nhiên và bền bỉ |
| **Chi phí hạ tầng** | ⚠️ Vượt quá Free Tier sẽ phát sinh chi phí đắt đỏ | ✅ **0 Đồng chi phí tính toán**, tối ưu hóa tài nguyên sẵn có |
| **Lưu trữ lâu dài** | ❌ Ổ cứng EBS nhỏ (30 GB), khó mở rộng | ✅ **AWS S3 Data Lake** độ bền 11 số 9, dung lượng không giới hạn |

* **Kết luận giải pháp:** **Compute & Crawling chạy trên Local/VM** $\rightarrow$ Dữ liệu sạch đồng bộ lên **AWS S3 Cloud Data Lake** $\rightarrow$ Đây là kiến trúc tối ưu nhất về kỹ thuật lẫn chi phí.

---

### 🖥️ Slide 10: Giám Sát Thời Gian Thực & Kiểm Thử Tự Động (Monitoring & QA)
* **Bảng điều khiển trực quan Terminal Live Dashboard (`make monitor`):**
  - Viết bằng Python Standard Library (không cần cài thêm thư viện nặng).
  - Tự động quét 4 nguồn trạng thái: SQLite State Catalog, Checkpoint JSON, File Batch Partition, và Airflow DB.
  - Hỗ trợ chế độ `--watch` tự làm mới màn hình sau mỗi 5 giây.
* **Bộ kiểm thử tự động (Unit Test Suite):**
  - **195 / 195 test cases đạt 100% Passed** trong thời gian **0.75 giây**.
  - Bao phủ toàn diện: Schema Pydantic, HTTP Client backoff, SQLite Catalog, JsonWriter atomic write, Data Quality Checker, và Parser của toàn bộ 8 nguồn.

---

### 🖥️ Slide 11: Kết Quả Đạt Được & Sản Phẩm Giai Đoạn 1 (Deliverables)
* **Các chỉ số định lượng ấn tượng:**
  - **8 / 8 sàn tuyển dụng** đã hoàn thành crawler độc lập.
  - **6.661 bản ghi việc làm IT thực tế** đã được thu thập và lưu trữ an toàn.
  - **100% bản ghi đạt chuẩn Schema v1**, tỷ lệ trùng lặp nội bộ = 0%.
  - **9 DAGs Airflow** vận hành tự động, có báo cáo audit JSON.
  - **195 unit tests** đảm bảo tính toàn vẹn hệ thống trước mọi thay đổi.
  - Đóng gói vận hành 1-click qua Makefile (`make start-airflow`, `make stop-airflow`, `make monitor`).

---

### 🖥️ Slide 12: Định Hướng Giai Đoạn 2 & Lời Cảm Ơn (Future Roadmap)
* **Kế hoạch giai đoạn 2 (ETL & Khai phá dữ liệu):**
  1. *Data Warehouse Ingestion:* Nạp dữ liệu JSON sạch vào PostgreSQL theo mô hình hình sao (Star Schema).
  2. *NLP & Entity Recognition:* Xây dựng mô hình trích xuất từ khóa kỹ năng công nghệ (Skill Extraction) từ mô tả công việc.
  3. *EDA & Visual Dashboard:* Phát triển Dashboard Streamlit / Power BI phân tích:
     - Top 10 kỹ năng công nghệ được trả lương cao nhất tại Việt Nam.
     - Ma trận tương quan giữa số năm kinh nghiệm và mức lương theo từng ngôn ngữ lập trình.
     - Xu hướng tuyển dụng Remote / Hybrid theo khu vực địa lý.
* **Lời cảm ơn:** Trân trọng cảm ơn Thầy/Cô và Hội đồng đã lắng nghe! Nhóm kính mời Thầy/Cô cùng theo dõi phần Live Demo trực tiếp.

---

## 2. KỊCH BẢN THUYẾT TRÌNH LỜI NÓI (SPOKEN PRESENTATION SCRIPT)

Dưới đây là lời thoại gợi ý từng slide (khoảng 8 phút), giúp bạn nói tự tin, lưu loát và đúng chất Data Engineer:

### Lời mở đầu (Slide 1):
> *"Kính thưa Thầy/Cô trong Hội đồng và các bạn. Em đại diện cho nhóm nghiên cứu xin được trình bày báo cáo tiến độ đồ án với đề tài: **'Hệ thống tự động thu thập, kiểm tra chất lượng và khai phá dữ liệu tuyển dụng CNTT tại Việt Nam (VN-IT-Job-Mining)'**. Trong giai đoạn 1 này, nhóm em tập trung giải quyết triệt để bài toán xây dựng nền tảng Data Collection: thu thập đa nguồn, chuẩn hóa dữ liệu và điều phối tự động bằng Apache Airflow."*

### Vấn đề thực tế (Slide 2 - Slide 3):
> *"Thưa Thầy/Cô, thị trường việc làm IT ở Việt Nam có một đặc thù là dữ liệu bị phân mảnh trên nhiều sàn khác nhau. Một bạn sinh viên hay nhà nghiên cứu muốn biết thị trường đang cần kỹ năng gì thì phải lướt qua cả TopDev, ITviec, TopCV, VietnamWorks,... Tuy nhiên, các sàn này áp dụng rất nhiều lớp bảo mật chống cào dữ liệu, từ Cloudflare WAF cho đến kiểm tra User-Agent.  
> Để giải quyết triệt để, nhóm em không dùng một phương pháp cào cứng nhắc, mà phân tích sâu bản chất kỹ thuật của từng nguồn: Nguồn nào có API nội bộ như TopDev hay VietnamWorks thì nhóm kéo API trực tiếp để đạt tốc độ tối đa; nguồn nào dùng SSR như CareerViet, ITviec thì nhóm bóc tách HTML DOM; và với nguồn có Cloudflare WAF gắt gao như TopCV, JobsGO thì nhóm sử dụng trình duyệt Headless Playwright với cấu hình giả lập danh tính người dùng thật."*

### Kiến trúc & Luồng dữ liệu (Slide 4 - Slide 5):
> *"Đây là sơ đồ kiến trúc tổng thể của hệ thống. Nhóm em thiết kế theo mô hình 5 tầng khép kín:  
> Khi một chu kỳ thu thập bắt đầu, Airflow kích hoạt tác vụ. Thay vì tải toàn bộ bài viết gây tốn băng thông, hệ thống áp dụng cơ chế **Hàng đợi 2 giai đoạn**: Đầu tiên chỉ quét danh sách ID ở trang ngoài, sau đó đối chiếu ngay lập tức với **SQLite State Catalog** với độ phức tạp $O(1)$. Những tin nào đã có trạng thái SUCCESS thì bỏ qua ngay. Chỉ những tin thực sự mới mới được đưa vào hàng đợi để tải chi tiết. Nhờ vậy, nhóm đã giảm được hơn 85% lưu lượng mạng lãng phí."*

### Data Contract & Chất lượng (Slide 6 - Slide 8):
> *"Một điểm sáng kỹ thuật quan trọng của đồ án là **Data Contract Compact Schema v1**. Nhóm định nghĩa cấu trúc dữ liệu chặt chẽ bằng thư viện Pydantic v2: Mức lương được bóc tách số học ra `salary_min`, `salary_max`, `currency`; các thẻ kỹ năng, học vấn được phân loại rõ ràng; và toàn bộ văn bản rác HTML được làm sạch thành các câu bullet chuẩn mực.  
> Ngay sau mỗi lượt cào, một cổng kiểm tra chất lượng tự động **DataQualityOperator** sẽ kích hoạt. File dữ liệu chỉ được chấp nhận nếu tỷ lệ đúng schema $\ge 95\%$ và tỷ lệ trùng lặp bằng đúng 0%. Nếu có bất kỳ sự cố nào, pipeline sẽ lập tức báo dừng và gửi cảnh báo."*

### Quyết định Hạ tầng & Giám sát (Slide 9 - Slide 11):
> *"Về mặt hạ tầng, nhóm đã phân tích rất kỹ và quyết định áp dụng **Kiến trúc Lai (Hybrid Cloud)**: Tầng tính toán cào dữ liệu và Airflow được chạy trên máy nội bộ có 8–16 GB RAM và dùng IP dân cư để vượt qua Cloudflare WAF, tránh hoàn toàn nguy cơ bị OOM Kill trên gói AWS EC2 Free Tier chỉ có 1 GB RAM. Dữ liệu sau khi kiểm định sạch sẽ được đồng bộ lên **AWS S3 Data Lake** để lưu trữ lâu dài.  
> Hiện tại, hệ thống đã thu thập được **6.661 tin tuyển dụng IT thực tế** từ 8 sàn, toàn bộ 195 bài unit test đều đạt 100% Passed. Nhóm cũng xây dựng một bảng điều khiển thời gian thực giúp theo dõi sức khỏe hệ thống chỉ bằng một dòng lệnh."*

---

## 3. KỊCH BẢN LIVE DEMO 4 BƯỚC CHO GIẢNG VIÊN

Khi Thầy/Cô yêu cầu: *"Em bật hệ thống lên cho thầy xem thực tế!"*, bạn thực hiện bình tĩnh theo 4 bước sau:

### 🔹 Bước 1: Khởi động hệ thống Airflow Production (1 dòng lệnh)
Mở terminal và gõ:
```bash
make start-airflow
```
* **Hiện tượng trên màn hình:** Script tự động kích hoạt virtualenv, chạy Scheduler và Webserver dưới dạng daemon ngầm, in ra mã PID và báo `Airflow Webserver is READY at http://localhost:8080`.
* **Thuyết minh:** *"Dạ thưa Thầy, toàn bộ hệ thống lập lịch tự động của em được cấu hình chạy ngầm dạng production daemon có theo dõi PID và kiểm tra health check HTTP, không cần phải mở nhiều cửa sổ terminal thủ công."*

---

### 🔹 Bước 2: Trình diễn giao diện điều khiển Airflow Web UI
Mở trình duyệt truy cập: `http://localhost:8080` (Tài khoản: `admin` / `admin`).
* **Thao tác:**
  1. Chỉ cho thầy thấy danh sách **9 DAGs** đang hoạt động (7 Daily Rotating DAGs, 1 Master Weekly `crawler_weekly_all`, và 1 Periodic 4-day DAG).
  2. Bấm vào nút **▶ (Trigger)** ở dòng `crawler_weekly_all` để kích hoạt cào thử nghiệm.
  3. Bấm vào tab **Graph**: Cho thầy thấy các task crawler chạy song song và hội tụ về `weekly_summary`.
* **Thuyết minh:** *"Dạ thưa Thầy, ở đây có 9 DAGs được lập lịch chuẩn cron. Khi em kích hoạt DAG Master Weekly, cả 8 nguồn tuyển dụng cùng được điều phối thực thi và cuối cùng task `weekly_summary` sẽ tổng hợp kết quả của cả mẻ cào."*

---

### 🔹 Bước 3: Bật màn hình Giám Sát Thời Gian Thực (Live Terminal Monitor)
Mở một tab terminal mới và gõ:
```bash
make monitor
```
* **Hiện tượng trên màn hình:** Màn hình bảng điều khiển ASCII hiển thị chi tiết số liệu của từng nguồn (VietnamWorks: 2.232, JobsGO: 1.476, TopCV: 810,... Tổng cộng: 6.661 jobs, Queue: 0, Trùng lặp: 0).
* **Thuyết minh:** *"Dạ thưa Thầy, nhóm em đã tự phát triển một công cụ giám sát thời gian thực bằng Python Standard Library. Bảng này truy vấn trực tiếp Airflow metadata DB, SQLite State Catalog và các file partition trên đĩa để thầy có thể nắm bắt ngay sức khỏe của toàn bộ kho dữ liệu."*

---

### 🔹 Bước 4: Kiểm chứng tính toàn vẹn với Bộ Kiểm Thử Tự Động
Gõ trên terminal:
```bash
pytest
```
* **Hiện tượng trên màn hình:** Chạy 195 test cases và kết thúc bằng dòng xanh lá cây rực rỡ: `195 passed in 0.75s`.
* **Thuyết minh:** *"Dạ thưa Thầy, mọi thành phần từ bóc tách lương, dọn rác HTML, kiểm tra schema cho đến bộ chống chặn IP đều được bảo vệ bởi 195 unit tests đạt 100% Passed, đảm bảo hệ thống tuyệt đối tin cậy."*

---

## 4. BỘ 10 CÂU HỎI PHẢN BIỆN CỦA GIẢNG VIÊN & CÂU TRẢ LỜI CHUẨN MỰC

Dưới đây là 10 câu hỏi mà các giảng viên chấm đồ án Data Engineering hay hỏi nhất, kèm câu trả lời đắt giá:

### ❓ Câu hỏi 1: "Tại sao nhóm em phải dùng Apache Airflow mà không viết vài dòng lệnh crontab trên Linux cho gọn nhẹ?"
> **Trả lời:**  
> *"Dạ thưa Thầy, crontab của Linux chỉ đơn thuần là bộ kích hoạt theo giờ (Time-based Trigger), nó hoàn toàn không có khả năng quản lý **Đồ thị phụ thuộc (Task Dependency Graph)**.  
> Trong hệ thống của nhóm em, bước kiểm định chất lượng (`DataQualityOperator`) bắt buộc phải chờ bước cào hoàn thành và nhận đường dẫn file thông qua **XCom**. Nếu file cào bị lỗi, Airflow sẽ ngăn chặn ngay lập tức không cho nạp vào kho dữ liệu. Ngoài ra, Airflow cung cấp cơ chế tự động thử lại có thời gian chờ (Retry with Exponential Backoff), giao diện Web trực quan để giám sát, ghi log chi tiết cho từng task và hỗ trợ mở rộng phân tán khi lượng dữ liệu lớn lên."*

---

### ❓ Câu hỏi 2: "Hệ thống của em cào như thế nào? Mỗi lần chạy có phải cào lại toàn bộ dữ liệu từ đầu không?"
> **Trả lời:**  
> *"Dạ thưa Thầy, hệ thống của nhóm em được thiết kế theo nguyên lý **Incremental Crawling (Thu thập gia tăng)**, tuyệt đối không bao giờ cào lại từ đầu.  
> Nhóm xây dựng một kho trạng thái tập trung **SQLite State Catalog** lưu trữ danh tính của từng tin việc làm qua cặp `(source, source_job_id)`. Trước khi gửi request tải nội dung chi tiết, crawler thực hiện một câu truy vấn kiểm tra với độ phức tạp thời gian **$O(1)$**. Nếu tin đó đã có trạng thái `SUCCESS`, hệ thống lập tức bỏ qua (Skip). Nhờ đó, mỗi phiên chạy mới chỉ tập trung xử lý các bài đăng mới xuất hiện, tiết kiệm hơn 85% băng thông và tránh làm phiền đến máy chủ đối tác."*

---

### ❓ Câu hỏi 3: "Các trang web như TopCV dùng Cloudflare WAF rất mạnh, làm sao nhóm em cào được mà không bị chặn IP?"
> **Trả lời:**  
> *"Dạ thưa Thầy, đối với các nền tảng có WAF bảo vệ nghiêm ngặt như TopCV, nhóm em đã áp dụng giải pháp 4 lớp phòng vệ (Polite & Stealth Crawling):  
> 1. **Sử dụng Playwright Headless Chrome:** Tắt cờ tự động hóa (`--disable-blink-features=AutomationControlled`) để Cloudflare không nhận diện được là bot tự động.  
> 2. **Xoay vòng User-Agent:** Sử dụng danh sách User-Agent của các trình duyệt máy tính phổ biến thực tế.  
> 3. **Khoảng nghỉ lịch sự (Polite Delay):** Tạo delay ngẫu nhiên từ 1.5 đến 3.5 giây giữa các lượt xem trang chi tiết để mô phỏng hành vi của người dùng thật.  
> 4. **Exponential Backoff:** Nếu gặp mã phản hồi 429 hoặc 503, hệ thống tự động giãn thời gian chờ lũy tiến $2^n \times \text{delay}$ trước khi thử lại."*

---

### ❓ Câu hỏi 4: "Tại sao nhóm không chạy toàn bộ Airflow và Crawler trên AWS EC2 Free Tier mà lại chọn mô hình Kiến Trúc Lai (Hybrid Cloud)?"
> **Trả lời:**  
> *"Dạ thưa Thầy, đây là một quyết định kỹ thuật được nhóm cân nhắc rất kỹ lưỡng dựa trên 2 yếu tố thực tế:  
> 1. **Vấn đề tài nguyên RAM:** Gói AWS EC2 Free Tier (`t2.micro` / `t3.micro`) chỉ cung cấp 1 GiB RAM. Khi chạy đồng thời Apache Airflow (Scheduler + Webserver) và khởi động trình duyệt Playwright để cào TopCV, lượng RAM tiêu thụ sẽ vượt quá 1 GiB và ngay lập tức bị cơ chế OOM Killer của Linux dừng tiến trình đột ngột.  
> 2. **Chặn IP Data Center:** Các hệ thống WAF hiện đại (như Cloudflare) luôn nhận diện và đánh giá rủi ro rất cao đối với các dải IP thuộc Data Center của AWS. Nếu cào từ EC2, nguy cơ bị dính CAPTCHA hoặc chặn IP là gần như chắc chắn.  
> Do đó, nhóm áp dụng mô hình chuẩn công nghiệp: **Tầng tính toán & thu thập (Compute) chạy trên máy trạm/máy ảo cục bộ** tận dụng 8–16 GiB RAM và dải IP dân cư thực tế; sau đó dữ liệu sạch được tự động đẩy lên **AWS S3 Cloud Storage** để lưu trữ lâu dài với độ bền 11 số 9."*

---

### ❓ Câu hỏi 5: "Dữ liệu cào về có đảm bảo chất lượng không? Nếu trang web bất ngờ đổi cấu trúc HTML thì hệ thống xử lý thế nào?"
> **Trả lời:**  
> *"Dạ thưa Thầy, hệ thống được trang bị 2 cơ chế bảo vệ chất lượng dữ liệu:  
> 1. **Cổng Data Quality Gate tự động:** Sau mỗi mẻ cào, `DataQualityOperator` sẽ quét toàn bộ file JSON và tính toán các chỉ số: Tỷ lệ đúng Schema Pydantic (phải đạt $\ge 95\%$, thực tế là 100%), tỷ lệ trùng lặp khóa duy nhất (phải bằng 0%), và các trường bắt buộc như Tiêu đề, Công ty, Mô tả không được để trống. Nếu không đạt, task sẽ lập tức FAIL và dừng pipeline.  
> 2. **Smart Ingestion Adapter:** Trong schema Pydantic, nhóm sử dụng decorator `@model_validator(mode="before")` để tự động làm sạch và chuyển đổi linh hoạt. Nếu một trang web đổi giao diện khiến parser không bóc tách được, hệ thống sẽ ghi nhận log lỗi cho tin đó và tiếp tục chạy các tin khác mà không làm sập toàn bộ hệ thống."*

---

### ❓ Câu hỏi 6: "Mỗi ngày cào một nguồn (Rotating Schedule) có bị mất tin không khi mà một số tin tuyển dụng chỉ tồn tại vài ngày?"
> **Trả lời:**  
> *"Dạ thưa Thầy, nhóm em đã khảo sát vòng đời của các tin tuyển dụng IT tại Việt Nam: Một tin đăng thường có thời hạn từ 15 đến 30 ngày (do chi phí đăng bài trên các sàn khá đắt).  
> Với chu kỳ xoay vòng 7 ngày một lần cho từng sàn, kết hợp với DAG Master chạy tổng lực vào tối Chủ Nhật và DAG 4 ngày chạy hàng đợi, hệ thống đảm bảo quét phủ 100% các tin mới mà không bao giờ bị bỏ sót. Chiến lược này giúp nhóm phân bổ tải mạng đều đặn mỗi tối, tránh tình trạng dồn toàn bộ 8 nguồn vào cùng một lúc làm nghẽn băng thông."*

---

### ❓ Câu hỏi 7: "Tại sao nhóm lưu file kết quả dạng JSON mảng thay vì JSON Lines (.jsonl) như thiết kế ban đầu?"
> **Trả lời:**  
> *"Dạ thưa Thầy, định dạng JSON mảng chuẩn `[ {...}, {...} ]` mang lại 3 ưu thế vượt trội:  
> 1. **Khả năng tương thích tuyệt đối:** Có thể mở và phân tích trực tiếp bằng một câu lệnh `json.load()` trong Python hoặc `pd.read_json()` trong Pandas mà không cần viết vòng lặp đọc từng dòng.  
> 2. **Kiểm tra tính toàn vẹn (Integrity):** File JSON mảng có dấu đóng ngoặc `]` ở cuối. Nếu file bị đứt gãy do mất điện hay mất mạng giữa chừng, cú pháp JSON sẽ không hợp lệ ngay lập tức và parser sẽ phát hiện được lỗi; trong khi file JSONL rất khó nhận biết dòng cuối cùng đã được ghi trọn vẹn hay chưa.  
> 3. **Cơ chế Atomic Write:** Nhóm sử dụng class `JsonWriter` ghi ra file tạm `.tmp` trước, sau khi hoàn tất toàn bộ mới đổi tên nguyên tử (atomic rename), đảm bảo file lưu trong Data Lake luôn hoàn hảo 100%."*

---

### ❓ Câu hỏi 8: "Trường mức lương được nhóm xử lý như thế nào khi trên web viết rất lộn xộn: có chỗ ghi 'Thỏa thuận', có chỗ ghi '20 - 40 triệu', có chỗ ghi '1000 - 2000 USD'?"
> **Trả lời:**  
> *"Dạ thưa Thầy, nhóm đã xây dựng một module xử lý chuyên biệt tại `crawlers/common/utils.py` và chuẩn hóa về đối tượng `JobSalary`:  
> - Sử dụng biểu thức chính quy (Regex) bóc tách các con số và đơn vị tiền tệ.  
> - Bóc tách thành số thực: `salary_min`, `salary_max`, và `salary_currency` (`VND` hoặc `USD`).  
> - Nếu bài đăng ghi 'Thỏa thuận', trường `is_negotiable` được gán bằng `True`, còn `min/max` sẽ là `None`.  
> Nhờ chuẩn hóa số học này, ở Giai đoạn 2 nhóm em có thể vẽ ngay biểu đồ phân phối mức lương (Boxplot, Histogram) và tính toán mức lương trung vị mà không cần tốn công xử lý chuỗi phức tạp."*

---

### ❓ Câu hỏi 9: "6.661 tin việc làm này hiện đang được tổ chức lưu trữ như thế nào?"
> **Trả lời:**  
> *"Dạ thưa Thầy, dữ liệu được tổ chức theo chuẩn **Hive-style Partitioning** của các hệ thống Big Data:  
> Thư mục: `data/<tên_sàn>/dt=YYYY-MM-DD/batch_XXX.json`.  
> Cách tổ chức này giúp:  
> 1. Dễ dàng truy vấn theo chuỗi thời gian (Time-series Analysis).  
> 2. Sẵn sàng tích hợp thẳng vào các công cụ phân tích dữ liệu lớn như AWS Athena, Apache Spark hoặc DuckDB.  
> 3. Dễ dàng đồng bộ từng thư mục phân vùng lên AWS S3 Raw Zone."*

---

### ❓ Câu hỏi 10: "Giai đoạn 2 nhóm dự định làm gì với lượng dữ liệu này?"
> **Trả lời:**  
> *"Dạ thưa Thầy, sau khi hoàn thành xuất sắc Giai đoạn 1 về Data Ingestion, trong Giai đoạn 2 nhóm sẽ triển khai 3 nhiệm vụ lớn:  
> 1. **Data Warehouse & Transformation:** Chuyển đổi dữ liệu từ Data Lake và nạp vào cơ sở dữ liệu quan hệ PostgreSQL theo mô hình hình sao (Star Schema).  
> 2. **NLP & Khai phá Kỹ năng (Skill Mining):** Dùng Named Entity Recognition (NER) và Regular Expressions để bóc tách các kỹ năng công nghệ (Java, Python, Docker, React, AWS, Kubernetes, LLM,...) từ phần mô tả công việc.  
> 3. **Trực quan hóa & Báo cáo thị trường:** Xây dựng Dashboard trực quan bằng Streamlit / Power BI trả lời các câu hỏi thực tế: Kỹ năng nào đang được trả lương cao nhất? Xu hướng tuyển dụng giữa TP.HCM và Hà Nội ra sao? và Những kỹ năng nào thường đi kèm với nhau trong cùng một Job Description."*

---

## 5. TÓM TẮT CÁC ĐIỂM SÁNG KỸ THUẬT (KEY SELLING POINTS)

Khi bước vào phòng bảo vệ, hãy luôn nhớ **6 "vũ khí" kỹ thuật mạnh nhất** của nhóm để tự tin làm chủ buổi báo cáo:

1. 💎 **Đa dạng 8 nguồn tuyển dụng thực tế:** Không chỉ cào 1–2 trang làm mẫu, mà bao phủ trọn vẹn cả 8 sàn việc làm IT lớn nhất Việt Nam.
2. 💎 **Cơ chế Khử trùng lặp 2 cấp $O(1)$:** Kết hợp Checkpoint JSON và SQLite State Catalog, tiết kiệm 85% băng thông mạng.
3. 💎 **Data Contract Pydantic Schema v1:** Chuẩn hóa nghiêm ngặt mức lương số học, nhóm thẻ 3 chiều, dọn sạch hoàn toàn rác HTML.
4. 💎 **Điều phối 9 DAGs trên Apache Airflow:** Kiến trúc 2 tầng (Rotating Daily + Master Weekly + Periodic 4-day Queue) kết hợp Custom Operators độc lập.
5. 💎 **Kiến trúc Lai (Hybrid Cloud):** Giải quyết triệt để bài toán RAM và Cloudflare WAF của EC2 Free Tier, kết hợp lưu trữ đám mây bền bỉ trên AWS S3.
6. 💎 **Độ tin cậy tuyệt đối:** 6.661 tin tuyển dụng thực tế, 195/195 test cases Passed 100%, có Live Terminal Dashboard giám sát trực tiếp.
