# Bảng Checklist Quy Chuẩn Đầu Ra Cho Crawler (Definition of Done)

> **Mục đích tài liệu:** Bảng kiểm tra toàn diện các tiêu chí kỹ thuật và quy chuẩn đầu ra bắt buộc phải đạt được trước khi nghiệm thu crawler của bất kỳ nguồn nào trong dự án VN-IT-Job-Mining.

---

## 1. Bảng Kiểm Tra Nhanh (Executive Checklist)

| STT | Tiêu Chí Kiểm Tra | Trọng Số | Trạng Thái Đạt |
| :---: | :--- | :---: | :---: |
| **1** | Kiến trúc Hai Pha Độc Lập (`discover_urls` & `crawl_details`) | 20đ | [ ] ĐẠT |
| **2** | Pha 1: URL ban đầu **hoàn toàn chưa có hash**, đẩy lên MinIO | 10đ | [ ] ĐẠT |
| **3** | Pha 2: Kéo URL từ MinIO về máy để thực hiện cào chi tiết | 10đ | [ ] ĐẠT |
| **4** | **Băm toàn vẹn Document JSON của 1 bài đăng** (Không băm HTML thô) | 15đ | [ ] ĐẠT |
| **5** | **Lưu ngược lại hash vào cả URL trong Ledger lẫn file Raw Snapshot** | 10đ | [ ] ĐẠT |
| **6** | Cơ chế Safe Skip & **Failed Queue** (Gặp lỗi đưa vào queue bữa khác cào lại) | 10đ | [ ] ĐẠT |
| **7** | Cơ chế **Checkpoint Sync định kỳ** (mỗi 15-20 tin tự động đẩy lên MinIO) | 5đ | [ ] ĐẠT |
| **8** | Chống chặn Bot: Polite Sleep ngẫu nhiên 2.0s - 4.5s giữa các lượt cào | 5đ | [ ] ĐẠT |
| **9** | Đủ bộ 3 cặp file mẫu: 3 HTML thô + 3 JSON Raw Envelope + README mapping | 15đ | [ ] ĐẠT |
| **10** | Mã nguồn Single-File gọn gàng (`crawler.py`), đầy đủ cờ CLI | 5đ | [ ] ĐẠT |
| **11** | Chấm điểm tự động DoD Scorer đạt tối thiểu **100 / 100 điểm** | Bắt buộc | [ ] ĐẠT |

---

## 2. Chi Tiết Từng Quy Chuẩn Đầu Ra

### Quy Chuẩn 1: Kiến Trúc 2 Pha Độc Lập (Two-Phase Decoupled)
- [ ] Hàm `discover_urls()` phụ trách Pha 1: Quét danh mục, tìm kiếm hoặc phân trang API để lấy toàn bộ danh sách URL.
- [ ] Hàm `crawl_details()` phụ trách Pha 2: Cào nội dung chi tiết theo danh sách URL từ URL Ledger.
- [ ] Hai pha tách rời hoàn toàn: Pha 1 có thể chạy hôm nay, Pha 2 có thể chạy ngày mai mà không ảnh hưởng lẫn nhau.

---

### Quy Chuẩn 2: Quản Lý URL & MinIO Lakehouse
- [ ] **Tại Pha 1 (Discovery):**
  - [ ] Khi đăng ký bài viết mới vào Ledger: `status = "PENDING"`.
  - [ ] **Ban đầu chưa có hash:** `content_hash = None`. Tuyệt đối không sinh hash giả khi chưa tải trang chi tiết.
  - [ ] Đồng bộ catalog master (`catalog_master.json`) và daily manifest (`manifest_YYYY-MM-DD.jsonl`) lên `minio://vn-it-jobs/url_ledger/<source>/`.
- [ ] **Tại Pha 2 (Details):**
  - [ ] Crawler có khả năng gọi `ledger.pull_from_minio()` để kéo catalog mới nhất từ MinIO về máy trước khi lọc URL cào.

---

### Quy Chuẩn 3: Thuật Toán Băm Toàn Vẹn Document JSON (Post-Crawl Hashing)
- [ ] **Băm cấu trúc JSON của bài đăng (KHÔNG băm HTML thô):**
  - [ ] Sau khi cào xong HTML, trích xuất toàn bộ dữ liệu vào `raw_payload`.
  - [ ] Áp dụng `calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])` trên chính đối tượng JSON này.
- [ ] **Lưu ngược lại mã hash vào 2 vị trí:**
  - [ ] **Vị trí 1 (URL trong Ledger):** Cập nhật `content_hash = canonical_hash`, chuyển `status = "DONE"`, cập nhật `last_scraped_at = now()`.
  - [ ] **Vị trí 2 (Raw Envelope Snapshot):** Lưu vào trường `metadata.content_hash`, `metadata.canonical_hash` và `metadata.field_hashes` trong file raw JSON đẩy lên MinIO:
    `minio://vn-it-jobs/raw/<source>/<YYYY-MM-DD>/{job_id}_v{version}.json`.

---

### Quy Chuẩn 4: Cơ Chế Bắt Lỗi Safe Skip & Failed Queue
- [ ] **Safe Skip:** Từng bài viết phải được bọc trong khối `try...except`. Nếu 1 URL bị lỗi (timeout mạng, lỗi server 500, lỗi 404, WAF chặn), crawler **tuyệt đối không được crash**, ghi log cảnh báo và tiếp tục cào tin tiếp theo.
- [ ] **Failed Queue:**
  - [ ] URL bị lỗi được ghi nhận qua `ledger.mark_failed(url_hash, error_msg)`.
  - [ ] Trạng thái bài viết chuyển sang `status = "FAILED"`, lưu lại chi tiết lỗi và số lần thử (`retry_count`).
  - [ ] Crawler hỗ trợ cờ CLI `--retry-failed` để lần sau có thể chọn cào lại các URL trong hàng đợi lỗi này.
- [ ] **Checkpoint Sync Định Kỳ:**
  - [ ] Khi cào hàng trăm tin, cứ sau mỗi **15 - 20 bài đăng** thành công, crawler tự động gọi `ledger.save_catalog()` và `ledger.sync_to_minio()` để đồng bộ ngay tiến độ lên MinIO Lakehouse.

---

### Quy Chuẩn 5: Chống Chặn & Hành Vi Cào Lịch Sự (Anti-Blocking)
- [ ] **Polite Delay:** Phải có khoảng nghỉ ngẫu nhiên 2.0s - 4.5s giữa 2 bài đăng chi tiết. Không dùng `time.sleep(hằng_số)` cố định.
- [ ] **Nhận diện chặn an toàn:** Khi gặp Cloudflare Challenge ("Attention Required!") hoặc HTTP 429: crawler dừng an toàn ngay lập tức, lưu dump HTML vào `_blocked/` để phân tích, giữ nguyên trạng thái `PENDING` cho các bài chưa cào.

---

### Quy Chuẩn 6: Bộ Ba Cặp Mẫu Chuẩn (Delivery Samples)
Tại thư mục `crawlers/sources/<source_name>/samples/`:
- [ ] Có ít nhất **3 file HTML thô đại diện**: `{job_id_1}.html`, `{job_id_2}.html`, `{job_id_3}.html`.
- [ ] Có đúng **3 file JSON Raw Envelope tương ứng**: `{job_id_1}_v1.json`, `{job_id_2}_v1.json`, `{job_id_3}_v1.json`.
- [ ] Các file JSON mẫu phải có `metadata.content_hash` khớp 100% với mã băm toàn vẹn document JSON tái sinh từ chính file HTML tương ứng.
- [ ] Có file `samples/README.md` giải thích ngữ cảnh từng file mẫu và bảng mapping các trường dữ liệu.

---

### Quy Chuẩn 7: Đóng Gói Mã Nguồn & CLI
- [ ] Toàn bộ logic crawler, parser, envelope builder nằm trong 1 file duy nhất `crawlers/sources/<source_name>/crawler.py`.
- [ ] Hỗ trợ đầy đủ các tham số CLI:
  - `--phase discovery`
  - `--phase details`
  - `--phase sync`
  - `--phase view`
  - `--online`
  - `--sync-minio`
  - `--retry-failed`
  - `--limit N`
  - `--local-html-dir PATH`

---

### Quy Chuẩn 8: Kiểm Thử & Nghiệm Thu Tự Động (Verification)
- [ ] Toàn bộ unit tests của nguồn cào phải **PASS 100%**:
  ```bash
  pytest tests/unit/test_<source_name>_*.py
  ```
- [ ] Chạy công cụ chấm điểm tự động từ skill `collection-submission`:
  ```bash
  python3 .agents/skills/collection-submission/scripts/verify_submission.py --source <source_name>
  ```
  - **Điểm nghiệm thu tối thiểu:** $\ge 100 / 100$ điểm.
- [ ] Kiểm tra thực tế trên MinIO Lakehouse qua Web Console UI (`http://localhost:9001`):
  - [ ] `url_ledger/<source>/catalog_master.json` đã tồn tại và hiển thị đúng số lượng URL.
  - [ ] `raw/<source>/<YYYY-MM-DD>/` chứa đầy đủ các file raw envelope JSON đã cào.
