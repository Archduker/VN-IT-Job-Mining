# Bảng Checklist Quy Chuẩn Đầu Ra Cho Crawler (Definition of Done)

> **Mục đích tài liệu:** Bảng kiểm tra toàn diện các tiêu chí kỹ thuật và quy chuẩn đầu ra bắt buộc phải đạt được trước khi nghiệm thu crawler của bất kỳ nguồn nào trong dự án VN-IT-Job-Mining.

> **Cập nhật 03/11/2026.** Checklist này được kiểm tự động bằng contract test (`tests/contract/test_<nguồn>_contract.py`, chạy `make test-contract`) theo bảng tiêu chuẩn C1–C14 trong `collection/CLAUDE.md`. Mã C trong ngoặc ở bảng dưới chỉ tiêu chuẩn tương ứng.

---

## 1. Bảng Kiểm Tra Nhanh (Executive Checklist)

| STT | Tiêu Chí Kiểm Tra | Trọng Số | Trạng Thái Đạt |
| :---: | :--- | :---: | :---: |
| **1** | Kiến trúc Hai Pha Độc Lập (`discover_urls` & `crawl_details`) (C1, C14) | 20đ | [ ] ĐẠT |
| **2** | Pha 1: URL ban đầu **hoàn toàn chưa có hash**, đẩy lên Cloudflare R2 | 10đ | [ ] ĐẠT |
| **3** | Pha 2: Kéo URL từ Cloudflare R2 về máy để thực hiện cào chi tiết | 10đ | [ ] ĐẠT |
| **4** | **Băm toàn vẹn Document JSON của 1 bài đăng** (Không băm HTML thô) | 15đ | [ ] ĐẠT |
| **5** | **Lưu ngược lại hash vào cả URL trong Ledger lẫn file Raw Snapshot**; version tăng khi hash đổi (C12) | 10đ | [ ] ĐẠT |
| **6** | Cơ chế Safe Skip & **Failed Queue** (Gặp lỗi đưa vào queue bữa khác cào lại) | 10đ | [ ] ĐẠT |
| **7** | Cơ chế **Checkpoint Sync định kỳ** (mỗi 15-20 tin tự động đẩy lên Cloudflare R2); sync cuối pha lỗi thì báo lỗi (C9) | 5đ | [ ] ĐẠT |
| **8** | Chống chặn Bot: Polite Sleep ngẫu nhiên 2.0s - 4.5s giữa các lượt cào | 5đ | [ ] ĐẠT |
| **9** | Đủ 3 mẫu thật trong `tests/fixtures/<nguồn>/` và contract test chạy offline (C13); F1–F8 ≥ 90% (C11) | 15đ | [ ] ĐẠT |
| **10** | Mã nguồn Single-File gọn gàng (`crawler.py`), đầy đủ cờ CLI | 5đ | [ ] ĐẠT |
| **11** | Chấm điểm tự động DoD Scorer đạt tối thiểu **100 / 100 điểm** | Bắt buộc | [ ] ĐẠT |

---

## 2. Chi Tiết Từng Quy Chuẩn Đầu Ra

### Quy Chuẩn 1: Kiến Trúc 2 Pha Độc Lập (Two-Phase Decoupled)
- [ ] Hàm `discover_urls()` phụ trách Pha 1: Quét danh mục, tìm kiếm hoặc phân trang API để lấy toàn bộ danh sách URL.
- [ ] Hàm `crawl_details()` phụ trách Pha 2: Cào nội dung chi tiết theo danh sách URL từ URL Ledger.
- [ ] Hai pha tách rời hoàn toàn: Pha 1 có thể chạy hôm nay, Pha 2 có thể chạy ngày mai mà không ảnh hưởng lẫn nhau.

---

### Quy Chuẩn 2: Quản Lý URL & Cloudflare R2 Lakehouse
- [ ] **Tại Pha 1 (Discovery):**
  - [ ] Khi đăng ký bài viết mới vào Ledger: `status = "PENDING"`.
  - [ ] **Ban đầu chưa có hash:** `content_hash = None`. Tuyệt đối không sinh hash giả khi chưa tải trang chi tiết.
  - [ ] Đồng bộ catalog master (`catalog_master.json`) và daily manifest (`manifest_YYYY-MM-DD.jsonl`) lên `r2://vn-it-jobs/url_ledger/<source>/`.
- [ ] **Tại Pha 2 (Details):**
  - [ ] Crawler có khả năng gọi `ledger.pull_from_r2()` để kéo catalog mới nhất từ Cloudflare R2 về máy trước khi lọc URL cào.
- [ ] **Cuối mỗi pha:** gọi `ledger.sync_final()`, không gọi `sync_to_r2()` rồi bỏ qua kết quả. Đẩy raw thì phải đẩy cả ledger (`docs/issue_log.md` L-01).
- [ ] **Discovery không tải được trang nào:** raise `DiscoveryError` (C14).

---

### Quy Chuẩn 3: Thuật Toán Băm Toàn Vẹn Document JSON (Post-Crawl Hashing)
- [ ] **Băm cấu trúc JSON của bài đăng (KHÔNG băm HTML thô):**
  - [ ] Sau khi cào xong HTML, trích xuất toàn bộ dữ liệu vào `raw_payload`.
  - [ ] Áp dụng `calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])` trên chính đối tượng JSON này.
- [ ] **Lưu ngược lại mã hash vào 2 vị trí:**
  - [ ] **Vị trí 1 (URL trong Ledger):** Cập nhật `content_hash = canonical_hash`, chuyển `status = "DONE"`, cập nhật `last_scraped_at = now()`. Đổi trạng thái luôn qua `mark_done`/`mark_failed`/`mark_closed` (các hàm này ghi `updated_at` để luật merge giữ đúng trạng thái).
  - [ ] **Version (C12):** dùng `UrlLedger.next_version(record, hash)`. Hash không đổi thì không ghi file mới; đổi thì `_v<N+1>`.
  - [ ] **Không lưu giá trị đổi theo ngày cào** ("3 ngày trước", `refreshed`) vào `raw_payload`, vì hash sẽ đổi ở mọi lần cào lại.
  - [ ] **Vị trí 2 (Raw Envelope Snapshot):** Lưu vào trường `metadata.content_hash`, `metadata.canonical_hash` và `metadata.field_hashes` trong file raw JSON đẩy lên Cloudflare R2:
    `r2://vn-it-jobs/raw/<source>/<YYYY-MM-DD>/{job_id}_v{version}.json`.

---

### Quy Chuẩn 4: Cơ Chế Bắt Lỗi Safe Skip & Failed Queue
- [ ] **Safe Skip:** Từng bài viết phải được bọc trong khối `try...except`. Nếu 1 URL bị lỗi (timeout mạng, lỗi server 500, lỗi 404, WAF chặn), crawler **tuyệt đối không được crash**, ghi log cảnh báo và tiếp tục cào tin tiếp theo.
- [ ] **Failed Queue:**
  - [ ] URL bị lỗi được ghi nhận qua `ledger.mark_failed(url_hash, error_msg)`.
  - [ ] Trạng thái bài viết chuyển sang `status = "FAILED"`, lưu lại chi tiết lỗi và số lần thử (`retry_count`).
  - [ ] Crawler hỗ trợ cờ CLI `--retry-failed` để lần sau có thể chọn cào lại các URL trong hàng đợi lỗi này.
- [ ] **Checkpoint Sync Định Kỳ:**
  - [ ] Khi cào hàng trăm tin, cứ sau mỗi **15 - 20 bài đăng** thành công, crawler tự động gọi `ledger.save_catalog()` và `ledger.sync_to_r2()` để đồng bộ ngay tiến độ lên Cloudflare R2 Lakehouse.

---

### Quy Chuẩn 5: Chống Chặn & Hành Vi Cào Lịch Sự (Anti-Blocking)
- [ ] **Polite Delay (C10):** Phải có khoảng nghỉ ngẫu nhiên 2.0s - 4.5s giữa 2 bài đăng chi tiết, qua `collection.common.anti_blocking.polite_sleep`. Không dùng `time.sleep(hằng_số)` cố định. Nguồn hay chặn bot được đặt chậm hơn.
- [ ] **Nhận diện chặn an toàn:** Khi gặp Cloudflare Challenge ("Attention Required!") hoặc HTTP 429: crawler dừng an toàn ngay lập tức, lưu dump HTML vào `_blocked/` để phân tích, giữ nguyên trạng thái `PENDING` cho các bài chưa cào.

---

### Quy Chuẩn 6: Bộ Ba Mẫu Chuẩn (C13)
Tại thư mục `tests/fixtures/<source_name>/` (thay cho `samples/` cũ):
- [ ] Có **3 mẫu thật** (HTML hoặc JSON API): tin thường, tin VIP/hot, tin lương thỏa thuận. Tên file theo loại, ví dụ `standard.html`, `negotiable_salary.html`, `vip_brand_page.html`.
- [ ] Mẫu được cắt bỏ script/style để nhẹ, nhưng phải cho ra đúng `content_hash` như trang gốc.
- [ ] Docstring đầu file contract test ghi ngày lấy mẫu và lý do chọn từng mẫu.

---

### Quy Chuẩn 7: Đóng Gói Mã Nguồn & CLI
- [ ] Toàn bộ logic crawler, parser, envelope builder nằm trong 1 file duy nhất `collection/sources/<source_name>/crawler.py`.
- [ ] Hỗ trợ đầy đủ các tham số CLI:
  - `--phase discovery`
  - `--phase details`
  - `--phase sync`
  - `--phase view`
  - `--online`
  - `--sync-r2` (tên cũ `--sync-minio` vẫn nhận)
  - `--retry-failed`
  - `--limit N`
  - `--local-html-dir PATH`

---

### Quy Chuẩn 8: Kiểm Thử & Nghiệm Thu Tự Động (Verification)
- [ ] Contract test của nguồn phải **PASS 100%**, chạy offline:
  ```bash
  pytest tests/contract/test_<source_name>_contract.py
  ```
- [ ] Chạy công cụ chấm điểm tự động từ skill `collection-submission`:
  ```bash
  python3 .agents/skills/collection-submission/scripts/verify_submission.py --source <source_name>
  ```
  - **Điểm nghiệm thu tối thiểu:** $\ge 100 / 100$ điểm.
- [ ] Cào thử thật lượng nhỏ (`python run.py --source <nguồn> --phase all --max-pages 1 --max-items 2 --sync-r2`), rồi kiểm trên Cloudflare R2 (dashboard Cloudflare hoặc `python scripts/sync_cloud_lakehouse.py --status --source <nguồn>`):
  - [ ] `url_ledger/<source>/catalog_master.json` đã tồn tại và hiển thị đúng số lượng URL.
  - [ ] `raw/<source>/<YYYY-MM-DD>/` chứa đầy đủ các file raw envelope JSON đã cào.
  - [ ] `python scripts/audit_raw_data.py --r2`: cột "Ledger chậm hơn raw" bằng 0.
