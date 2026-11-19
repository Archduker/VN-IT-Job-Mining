# Nhật ký lỗi đã xử lý

Các lỗi đã sửa trên nhánh `fix/known-issues-p1`, đợt 02–03/11/2026. Mỗi lỗi ghi theo thứ tự: **Lỗi → Nguyên nhân → Cách xử lý → Kiểm chứng**. Việc còn mở nằm ở `KNOWN_ISSUED.md`; xong việc nào thì chuyển sang đây.

Mã cũ (SCRAPE-, VIZ-, PRE-) là mã trong `KNOWN_ISSUED.md` lúc phát hiện.

Kết quả chung sau đợt sửa:

| Hạng mục | Trước | Sau |
|---|---|---|
| Vấn đề mức cao trong audit (`scripts/audit_raw_data.py --r2`) | 8 | 0 |
| Key R2 theo layout cũ | 67 | 0 |
| Tin "ledger chậm hơn raw" | 1.281 | 0 |
| Test tự động (`make test`) | 12 file, không có test crawler | 143 test, có contract test cho TopDev và TopCV |
| Cào thử thật 03/11 (1 trang discovery, 2 tin detail) | — | 7/8 nguồn thành công, ledger trên R2 có giờ mới |

---

## 1. Thu thập (crawler và URL Ledger)

### L-01. Ledger trên R2 không được cập nhật sau khi cào (SCRAPE-4, SCRAPE-9)

- **Lỗi:** raw các ngày 01–02/11 đã có trên R2, nhưng ledger vẫn ghi các tin đó là `PENDING`. Lần chạy sau sẽ cào lại, và trang Crawling đếm thiếu ngày 01/11.
- **Nguyên nhân:** có nhiều nguyên nhân cộng lại.
  1. `run.py` không có tham số `sync_r2` nên không truyền vào crawler; Airflow gọi `run_crawler()` nên cũng không bao giờ đồng bộ.
  2. Raw sau đó được đẩy riêng bằng `scripts/push_raw_to_r2.py`, mà script này chỉ đẩy raw. R2 ghi `LastModified` 8 giờ sau `scraped_at`.
  3. `UrlLedger.sync_to_minio()` tự tạo client riêng: ưu tiên `AWS_*` trước `R2_*` (ngược với raw), thiếu endpoint thì rơi về `http://localhost:9000`.
  4. Biến `storage_label` gán trong `try` nhưng dùng trong `except`, nên khi lỗi thì văng `UnboundLocalError` thay vì trả `False`.
  5. Hàm upload file catalog trên đĩa mà không gọi `save_catalog()` trước, và không crawler nào kiểm tra giá trị trả về.
- **Cách xử lý:**
  - Ledger dùng chung `collection/common/r2_storage.get_r2_client()` và `resolve_r2_bucket()` với raw (một nguồn cấu hình).
  - Sửa `storage_label`; gọi `save_catalog()` trước khi upload.
  - Thêm `UrlLedger.sync_final()`: cuối mỗi pha, đồng bộ không được thì raise `LedgerSyncError` để Airflow báo đỏ. Giữa chừng vẫn chỉ ghi cảnh báo, không dừng batch.
  - `run_crawler(..., sync_r2=False)` và cờ `--sync-r2` trong `run.py`; Airflow luôn truyền `sync_r2=True`.
  - `push_raw_to_r2.py` đẩy cả ledger sau raw, qua `ledger_push_decision()`: từ chối khi catalog trên máy rỗng, bản trên R2 mới hơn, hoặc R2 có URL mà máy không có.
  - Dựng lại ledger bằng script mới `scripts/reconcile_ledger_from_raw.py` (mặc định chạy thử; `--apply` ghi trên máy; `--push` sao lưu bản R2 vào `data/<nguồn>/url_ledger/backups/` rồi đẩy). TopDev: tạo 27, cập nhật 1.105. TopCV: tạo 30, cập nhật 119. CareerViet: đẩy lại.
- **Kiểm chứng:** `tests/integration/test_ledger_sync.py` (10 test: chạy thử không ghi, idempotent, không ghi đè bản R2 mới hơn, `sync_final` raise, `run_crawler` và Airflow truyền `sync_r2`). Cào thử 03/11: ledger của 7 nguồn trên R2 có `updated_at` mới.

### L-02. `save_catalog()` làm mất trạng thái `FAILED` và `CLOSED`

- **Lỗi:** cả 8 ledger có 0 bản ghi `FAILED`, dù log có ghi nhận URL lỗi.
- **Nguyên nhân:** khi gộp bản trong bộ nhớ với bản trên đĩa, luật cũ là "`DONE` thắng, sau đó `last_scraped_at` mới hơn thắng". Một URL vừa chuyển `FAILED` thua bản `DONE` hoặc `PENDING` cũ trên đĩa nên không bao giờ được lưu. Glints còn gán `status = "CLOSED"` trực tiếp, không qua hàm của ledger.
- **Cách xử lý:** `mark_done`, `mark_failed`, `mark_closed` ghi `updated_at`. Khi gộp, bản có `updated_at` mới hơn thắng; bản ghi cũ chưa có `updated_at` vẫn theo luật cũ. Glints đổi sang `self.ledger.mark_closed(url_hash)`.
- **Kiểm chứng:** `tests/unit/test_url_ledger_dedup.py`: `test_failed_and_closed_survive_save`, `test_latest_status_change_wins_between_workers`, `test_records_without_updated_at_keep_old_merge_rule`.

### L-03. TopDev và VietnamWorks ghi version mới cho nội dung không đổi

- **Lỗi:** cào lại tin đến hạn 21 ngày mà nội dung giống hệt vẫn sinh `_v2`.
- **Nguyên nhân:** `get_pending_or_due_records()` đổi trạng thái tin đến hạn thành `RECHECK_DUE` ngay trong bộ nhớ. Crawler kiểm tra "đã cào chưa" bằng `status == "DONE"`, nên tin `RECHECK_DUE` luôn bị coi là tin mới.
- **Cách xử lý:** thêm `UrlLedger.next_version(record, hash)`, coi `RECHECK_DUE` như `DONE`: hash không đổi thì giữ version và không ghi file, hash đổi thì `N+1`. Mọi crawler dùng hàm này.
- **Kiểm chứng:** `tests/integration/test_snapshot_versioning.py::test_next_version_treats_recheck_due_as_done`.

### L-04. TopCV và JobsGO luôn ghi `_v1`

- **Lỗi:** cào lại tin có nội dung đổi vẫn ghi đè `_v1`, mất lịch sử thay đổi (CDC).
- **Nguyên nhân:** tên file và `latest_version` được viết cứng là 1 ở cả 4 chỗ ghi raw.
- **Cách xử lý:** dùng `UrlLedger.next_version()`; tin không đổi được đếm vào `stats["unchanged"]`. Đã thống nhất thành tiêu chuẩn C12.
- **Kiểm chứng:** `tests/integration/test_snapshot_versioning.py` chạy cả TopCV và JobsGO: tin mới ghi `_v1`, cào lại không đổi không ghi file, đổi nội dung ghi `_v2`, repost không ghi file.

### L-05. Raw TopDev thiếu kinh nghiệm, cấp bậc và ngày đăng

- **Lỗi:** độ phủ trên raw TopDev: F5 (kinh nghiệm) 21%, F6 (cấp bậc) 0%, F8 (ngày đăng) 29%.
- **Nguyên nhân:** pha detail lưu raw từ API chi tiết với danh sách `DETAIL_FIELDS`, mà danh sách này thiếu các trường đó. `LISTING_FIELDS` có đủ nên khi xem listing không thấy lỗi.
- **Cách xử lý:** thêm `job_levels_str`, `job_levels_arr`, `experiences_str`, `job_types_str`, `contract_types_str`, `published` vào `DETAIL_FIELDS`. `build_raw_payload_from_api()` bỏ `published.since` ("3 ngày trước") vì giá trị này đổi theo ngày cào và làm hash đổi vô ích. Monitoring thêm đường dẫn F5 (`job_posting_jsonld.experienceRequirements`) và F8 (`published.date`, `date_posted`, `valid_through`) vào `RAW_PATHS`.
- **Còn lại:** raw đã cào trước 02/11 vẫn thiếu; tự đầy đủ dần khi được cào lại (SCRAPE-5 trong `KNOWN_ISSUED.md`).
- **Kiểm chứng:** `tests/contract/test_topdev_contract.py` (C11 trên 3 mẫu thật, C5 hash không đổi khi đổi `published.since`); cào thử 03/11 có đủ F5, F6, F8.

### L-06. CareerViet không đẩy ledger khi chạy qua `run.py --sync-r2`

- **Lỗi:** cào thử 03/11, raw CareerViet lên R2 nhưng ledger không lên.
- **Nguyên nhân:** hai chỗ đồng bộ cuối pha (dòng 848 và 1148 của `collection/sources/careerviet/crawler.py`) kiểm tra tham số cục bộ `sync_r2` của hàm, luôn là `False` khi gọi từ `run.py`, thay vì `self.sync_r2`.
- **Cách xử lý:** đổi thành `if self.sync_r2:`. Ledger CareerViet được đẩy lại bằng `reconcile_ledger_from_raw.py --push` (có sao lưu).
- **Kiểm chứng:** `tests/integration/test_ledger_sync.py::test_final_sync_follows_crawler_setting`.

### L-07. ITviec: chốt chặn ghi đè catalog không hoạt động (sửa một phần)

- **Lỗi:** chốt chặn "không đẩy catalog nhỏ hơn bản trên R2" trong `collection/sources/itviec/parser.py` không bao giờ chặn.
- **Nguyên nhân:**
  - `remote_catalog_count()` kết nối `localhost` (cấu hình MinIO cũ); lỗi kết nối bị bắt và trả `None`, nên `can_upload_catalog()` luôn cho ghi.
  - Báo cáo chất lượng code ngày 03/11 (`docs/code_quality.md`, bảng B1) cho thấy thêm: `sync_mode`, `local_catalog_count`, `remote_catalog_count`, `can_upload_catalog` **không được gọi ở đâu cả**. Chốt chặn chưa từng được nối vào crawler.
- **Cách xử lý:** `remote_catalog_count()` đã dùng `get_r2_client()`; hằng cấu hình đổi sang `R2_RAW_PREFIX`. ITviec hiện được bảo vệ bằng cơ chế chung: kéo ledger từ R2 trước pha detail, luật merge theo `updated_at` (L-02), và `ledger_push_decision()` trong `push_raw_to_r2.py`.
- **Còn lại:** nối chốt chặn vào crawler hoặc xóa 4 hàm này (SCRAPE-15 trong `KNOWN_ISSUED.md`).
- **Kiểm chứng:** chưa có test cho chốt chặn vì nó chưa được gọi. Bản ghi cũ của mục này từng ghi "cào thử đọc được số bản ghi thật trên R2"; câu đó không có căn cứ và đã được bỏ.

### L-08. TopCV: mọi trang đều lỗi khi dùng `cloakbrowser` (SCRAPE-10)

- **Lỗi:** discovery và detail TopCV lỗi ở mọi trang.
- **Nguyên nhân:** engine mặc định là `cloakbrowser`, thư viện này cần license key mà máy chưa có.
- **Cách xử lý:** engine mặc định đổi sang `curl_cffi` ở cả `TopCVCrawler` và cờ `--engine` của `run.py`. Muốn dùng `cloakbrowser` phải chỉ định rõ và có license.
- **Kiểm chứng:** `tests/contract/test_topcv_contract.py::test_scrape10_default_engine_is_curl_cffi`; cào thử 03/11 lấy được 2/2 tin.

### L-09. TopCV: discovery lỗi toàn bộ mà vẫn báo thành công (SCRAPE-11, phần TopCV)

- **Lỗi:** khi mọi trang danh sách đều lỗi, discovery trả danh sách rỗng và Airflow báo xanh, nên không ai biết.
- **Nguyên nhân:** lỗi từng trang bị bắt và bỏ qua; không phân biệt "không có tin mới" với "không tải được trang nào".
- **Cách xử lý:** discovery đếm `pages_ok` và lỗi đầu tiên; `pages_ok == 0` thì raise `DiscoveryError`, `run.py` trả exit 1. Lấy được ít nhất 1 trang là thành công. Đã thống nhất thành tiêu chuẩn C14.
- **Còn lại:** 7 nguồn khác chưa áp dụng C14 (SCRAPE-11).
- **Kiểm chứng:** `tests/contract/test_topcv_contract.py`: 4 test `test_c14_*`.

### L-10. Tên "MinIO" còn khắp code dù hệ thống chỉ dùng R2

- **Lỗi:** tên hàm, cờ CLI, biến môi trường và file vẫn là MinIO (`sync_to_minio`, `--sync-minio`, `MINIO_*`, `minio_raw_pipeline.py`), dễ hiểu nhầm là còn server MinIO cục bộ. Một số chỗ còn fallback đọc `MINIO_*`.
- **Nguyên nhân:** dự án chuyển từ MinIO sang Cloudflare R2 nhưng chỉ đổi cấu hình, không đổi tên.
- **Cách xử lý:** đổi toàn bộ sang R2 ngày 02/11/2026: `R2RawStore` trong `collection/common/r2_raw_pipeline.py`, `sync_to_r2`/`pull_from_r2`, `--sync-r2` (giữ `--sync-minio` làm alias), Glints `--no-r2`, TopCV `--r2`, `view_urls.py --r2`. Xóa fallback `MINIO_*`; `setup_cloud_storage.py` ghi khóa `R2_*` và bỏ khóa `MINIO_*`. Skill, docs, `.gitignore` đã dọn theo.
- **Kiểm chứng:** `make test` qua; `grep -ri minio` chỉ còn alias CLI (`--sync-minio`, `--minio`), chú thích lịch sử, đoạn xóa khóa `MINIO_*` cũ trong `setup_cloud_storage.py`, và `docs/archive/`.

## 2. Dữ liệu trên R2 và trên máy

### L-11. R2 còn key theo layout cũ (SCRAPE-3)

- **Lỗi:** 67 key nằm ở `raw/crawling/<ngày>/<nguồn>/` và `raw/url_ledger/<ngày>/<nguồn>/`, cùng 7.194 bản trùng giữa layout cũ và mới.
- **Nguyên nhân:** các lần chạy trước khi có `canonicalize_lakehouse_key` ghi theo layout cũ.
- **Cách xử lý:** chạy `scripts/migrate_lakehouse_layout.py --r2` (chạy thử, người dùng duyệt số liệu) rồi `--apply`: chuyển 67 key, xóa 7.194 bản trùng, 0 xung đột.
- **Kiểm chứng:** `audit_raw_data.py --r2` báo 0 key layout cũ; `tests/integration/test_audit_raw_data.py::test_r2_layout_check`.

### L-12. ITviec có bản ghi test giả trên R2 và trên máy (SCRAPE-6)

- **Lỗi:** `raw/itviec/2026-10-19/job-{mot-100,hai-200,ba-300,bon-400}_v1.json` là dữ liệu giả, bị tính vào thống kê.
- **Nguyên nhân:** một test cũ ghi vào `data/` thật, sau đó được đồng bộ lên bucket thật.
- **Cách xử lý:** xóa 8 key trên R2 (layout mới và cũ) và 4 file trên máy, sau khi liệt kê đúng từng key cho người dùng duyệt. `tests/conftest.py` chặn mọi kết nối mạng ngoài localhost trong test, và test chỉ ghi vào `tmp_path`.
- **Kiểm chứng:** audit không còn tin ITviec giả.

### L-13. Máy chỉ có raw của VietnamWorks (SCRAPE-2)

- **Lỗi:** trang Collection, Raw, EDA trống ở 7 nguồn.
- **Nguyên nhân:** `.env` chưa có khóa R2 nên chưa tải dữ liệu về.
- **Cách xử lý:** điền khóa R2 vào `.env`, chạy `python scripts/sync_cloud_lakehouse.py --download` (chỉ tải về). Key layout cũ được tải vào đúng thư mục nhờ `normalize_legacy_key`.
- **Kiểm chứng:** 12.778 / 12.779 file raw trên máy đã có trên R2 (file còn lại là `raw_batch.json`, PRE-8).

### L-14. Audit báo nhầm nhiều mục mức cao

- **Lỗi:** audit báo 8 vấn đề mức cao, phần lớn không phải lỗi thật.
- **Nguyên nhân:**
  - Đếm tin trùng có tính cả file batch cũ (`batch_001.json`, `raw_batch.json`), vốn gom lại các tin đã có file riêng.
  - "DONE thiếu raw" tính cả repost (139 tin), mà repost theo thiết kế không sinh file raw.
  - Kiểm tra "trang bị chặn" khớp chữ "captcha" ở bất kỳ đâu trong trang.
  - Tính độ phủ cả với trường mà nguồn không hiển thị (`RAW_PATHS` rỗng), ra 0%.
  - Không có cột phát hiện ledger chậm hơn raw, nên không thấy L-01.
- **Cách xử lý:** bỏ file batch khi tìm trùng; trừ repost khỏi "DONE thiếu raw"; chỉ coi là bị chặn khi dấu hiệu nằm trong tiêu đề hoặc trang dưới 1.000 ký tự; độ phủ là `None` khi `RAW_PATHS` rỗng; thêm cột "Repost" và "Ledger chậm hơn raw" (bỏ qua `CLOSED`).
- **Kiểm chứng:** `tests/integration/test_audit_raw_data.py`; audit sau khi sửa: 0 mục mức cao.

### L-21. File batch cũ `raw_batch.json` của VietnamWorks chỉ có trên máy (PRE-8)

- **Lỗi:** `data/vietnamworks/raw/2026-10-16/raw_batch.json` (9 MB, 931 tin) là file raw duy nhất trên máy chưa có trên R2. Trong đó 206 tin không có file riêng và không có trong ledger, nên crawler không bao giờ cào lại.
- **Nguyên nhân:** crawler đời cũ (bản 0.5.0, ngày 16/10) gom mọi tin vào một file và không ghi ledger. Crawler mới cào lại 725 tin ngày 20/10 thành file riêng; 206 tin còn lại bị bỏ sót.
- **Cách xử lý:**
  - Không đẩy file batch lên R2: 725/931 tin (78%) đã có bản đầy đủ hơn trên R2. Hash khác nhau chỉ vì crawler mới bóc thêm 9 trường; 97/103 trường chung giống hệt.
  - Thêm `reconcile_ledger_from_raw.py --register-batch-missing <file>`: đăng ký `PENDING` cho tin trong batch chưa có file riêng và chưa có trong ledger, ghi nguồn gốc vào `registered_from_batch`. Đã chạy `--push` ngày 03/11: ledger trên R2 từ 1.258 lên 1.464 bản ghi (+206 `PENDING`), không mất bản ghi nào, không bản ghi cũ nào đổi trạng thái. Bản R2 trước đó được sao lưu ở `data/vietnamworks/url_ledger/backups/`.
  - Audit báo nhầm 206 tin là "ledger chậm hơn raw", vì tính cả lần cào trong file batch. Đã sửa: chỉ tính lần cào từ file từng tin.
- **Còn lại:** 206 tin sẽ được cào dần qua các ca detail; tin đã hết hạn sẽ thành `CLOSED`. File batch vẫn nằm trên máy; bước Clean đã khử trùng (L-25).
- **Kiểm chứng:** `tests/integration/test_ledger_sync.py::test_batch_missing_dry_run_lists_only_new_jobs`, `test_batch_missing_apply_registers_pending_without_hash`; `tests/integration/test_audit_raw_data.py::test_ledger_consistency`; `audit_raw_data.py --r2`: 0 mục mức cao.

### L-23. Crawler để lại thư mục rỗng `data/<nguồn>/dt=*`

- **Lỗi:** sau mỗi lần cào, `data/` có thêm thư mục `dt=YYYY-MM-DD` rỗng theo layout cũ, làm lệnh so máy với R2 và báo cáo audit đếm sai.
- **Nguyên nhân:** `collection/common/json_writer.JsonWriter` tạo thư mục ngay khi khởi tạo, kể cả khi không có bản ghi nào được ghi; `close()` luôn gọi `flush()`.
- **Cách xử lý:** chỉ tạo thư mục trong `flush()`; `close()` chỉ flush khi có bản ghi hoặc file đã tồn tại. Đã xóa các thư mục `dt=*` rỗng trên máy.
- **Kiểm chứng:** `tests/unit/test_json_writer.py` (2 test: đóng khi không có bản ghi thì không tạo thư mục; có bản ghi thì ghi đúng file).

### L-24. Code chết và kết nối R2 tự tạo ngoài `get_r2_client()` (SCRAPE-15, GEN-4, một phần GEN-3)

- **Lỗi:** `docs/code_quality.md` báo các hàm chốt chặn ghi đè catalog của ITviec (`sync_mode`, `local_catalog_count`, `remote_catalog_count`, `can_upload_catalog` trong `collection/sources/itviec/parser.py`) không được gọi ở đâu; `scripts/upload_to_r2.py` vẫn ghi theo layout cũ `dt=*/batch_*.json`; `r2_raw_pipeline.py` và `monitoring/backend/app/core/r2_client.py` tự tạo `boto3.client`.
- **Nguyên nhân:** chốt chặn ITviec viết xong nhưng chưa nối vào luồng đồng bộ; bảo vệ thực tế là `ledger_push_decision()` và luật gộp theo `updated_at` của ledger. Script upload cũ không được xóa khi đổi layout. Hai chỗ `boto3.client` có trước khi gom kết nối về `get_r2_client()` (cùng loại lỗi với L-01).
- **Cách xử lý:** xóa các hàm chốt chặn ITviec, `scripts/upload_to_r2.py` và test của nó, `collection/common/ip_rotator.py`, `jsonl_writer.py`, cùng các hàm không ai gọi khác trong báo cáo. `get_r2_client()` nhận thêm `read_timeout`, `max_attempts`; `R2RawStore` và `CloudflareR2Client` gọi qua hàm này. Còn `setup_cloud_storage.py` tự tạo client vì phải thử khóa người dùng vừa nhập (ngoại lệ ghi trong `scripts/CLAUDE.md`).
- **Còn lại:** các mục còn lại của báo cáo chất lượng code (GEN-3).
- **Kiểm chứng:** `make test` xanh; `make quality` không còn báo các hàm trên.

### L-25. File batch cũ trùng file từng tin khi làm phẳng (PRE-8)

- **Lỗi:** `data/vietnamworks/raw/2026-10-16/raw_batch.json` (931 tin) và `data/vieclam24h/raw/2026-10-20/batch_001.json` (616 tin) gom nhiều tin trong một file; 1.341 tin trong đó đã có file riêng mới hơn, nên pipeline cũ đếm và xử lý trùng.
- **Nguyên nhân:** layout cũ ghi theo lô; pipeline cũ đọc mọi file JSON mà không phân biệt file lô với file từng tin.
- **Cách xử lý:** bước Clean mới (`preprocessing/clean/run.py`, đặc tả `docs/spec/preprocessing/spec/P1_clean.md`) đọc riêng file lô (`preprocessing/common/raw_reader.read_raw`). Luật C2 bỏ tin trong file lô đã có file riêng; tin chỉ có trong file lô (206 tin VietnamWorks) được giữ đến khi cào lại có file riêng. Luật C1 giữ snapshot mới nhất của mỗi `job_id`.
- **Kiểm chứng:** `tests/unit/test_clean_step.py::test_rules_c1_to_c7_and_conservation`; lần chạy 03/11/2026: C1 bỏ 1.987, C2 bỏ 1.341 (VietnamWorks 725, Vieclam24h 616), output 8.373 tin không trùng `job_id`.

### L-26. Output P2–P5 sai lương, kỹ năng, cấp bậc, ngôn ngữ, địa điểm (review 03/11/2026)
- **Lỗi:** trên 8.373 tin sau Normalization:
  - 676 tin lấy lương từ tiêu đề, phần lớn sai ("(2026TD450981)" → 2 tỷ/tháng, "Microsoft 365" → 365 triệu);
  - "Up to 40.000.000 VND" → 40.000đ; "From 9.000.000 VND" → 9 nghìn tỷ;
  - kỹ năng "C" ở 6.912 tin (83%);
  - 54% tin là Middle;
  - 1.583 tin "bilingual" phần lớn là tiếng Việt (ước tính dịch 0,45 USD, vượt trần);
  - file chấm dịch `translate_30.csv` tạo lúc dry-run nên trống;
  - 31 tin Hà Nội bị xếp tỉnh Điện Biên;
  - bước 04 ghi đè `data/curated/curated_flat_golden_jobs.parquet`;
  - dòng JSON hỏng ở Integration bị bỏ mà không đếm.
- **Nguyên nhân:**
  - `salary_parser.py` nhận mọi số trong tiêu đề/JD; nhận "m"/"tr" ở bất kỳ đâu trong chuỗi ("from", "trưởng"); số có dấu hàng nghìn chỉ đọc nhóm đầu.
  - `skills.json` có biến thể "c", "go", "py", "ts".
  - `classify_seniority` coi "Nhân viên"/"Chuyên viên" là Middle và "quản lý" trong tiêu đề là cấp quản lý.
  - `detect_language` đếm từ khóa thay vì xét chữ JD.
  - `location_parser` khớp chuỗi con.
- **Cách xử lý:**
  - Tiêu đề/JD chỉ nhận cụm có đơn vị tiền.
  - Lương tháng ngoài 1–500 triệu thì để NaN và gắn cờ `salary_suspect`.
  - "C" chỉ nhận khi có ngữ cảnh.
  - Cấp bậc không xác định thì để trống.
  - JEV chỉ hỏi có/không (`noul`) để gắn cờ `*_can_kiem`; bỏ `choice`.
  - Ngôn ngữ chỉ xét JD: chữ có dấu < 1% thì là `en`.
  - Dịch chia đoạn, có 2 model thi 30 JD, trần chung 0,95 USD (`_cache/spend.json`).
  - Phường/xã đối chiếu `dictionaries/wards_34.json` (3.321 đơn vị mới), bỏ quận/huyện.
  - Gộp 8 nguồn ở Integration (`all.parquet`); luật I0 cho dòng JSON hỏng.
  - Bỏ bước chép đè file golden.
  - Chi tiết ở mục 8 của `docs/spec/preprocessing/spec/P2–P4`.
- **Kiểm chứng:**
  - `tests/unit/test_preprocessing_review_fixes.py` (các ví dụ sai ở trên), `make test`.
  - Chạy thật `scripts/run_preprocessing.py --step all`:
    - Middle 10,7%;
    - kỹ năng "C" còn 243 tin;
    - không còn lương > 500 triệu/tháng;
    - `en` 1.785 tin;
    - Điện Biên 0.


### L-27. Các lỗi pipeline cũ PRE-1, 2, 3, 4, 6, 7 hết khi chuyển sang pipeline 5 bước; "ai" bị tính là Machine Learning; dịch treo khi Gemini quá tải (03/11/2026)
- **Lỗi:**
  - PRE-1: phân loại khớp chuỗi con ("ba" trong "backend", "intern" trong "international").
  - PRE-2: chuẩn hóa chạy trước bước bù giá trị.
  - PRE-3: tên tỉnh không dấu chưa gộp ("Ha Noi" 509 tin).
  - PRE-4: dữ liệu cũ trên `data/staging`, `data/curated` cần chạy lại.
  - PRE-6: kỹ năng CareerViet, JobsGO lấy tag SEO, ngành nghề.
  - PRE-7: TopDev không đọc ngày đăng, kinh nghiệm trong JSON-LD.
  - Mới: chữ "ai" (đại từ tiếng Việt) được tính là kỹ năng Machine Learning, 179/182 tin CareerViet có kỹ năng này.
  - Mới: lượt dịch 30 JD mẫu chạy hàng giờ không ra file khi Gemini trả 503.
- **Nguyên nhân:**
  - PRE-1 đến PRE-7 nằm ở pipeline cũ (`scripts/run_staging_integration_pipeline.py`).
  - `skills.json` có biến thể "ai" cho Machine Learning.
  - `translator.py` thử lại 5 lần khi gặp 429/503 nhưng không tính là lỗi, nên luật "dừng sau 5 lỗi liên tiếp" không bao giờ chạy.
- **Cách xử lý:**
  - Pipeline 5 bước (`scripts/run_preprocessing.py`) thay pipeline cũ:
    - so khớp theo từ (`has_term`);
    - không có bước bù giá trị;
    - tỉnh quy về 34 tỉnh qua `common/province.py`;
    - Integration bỏ tag SEO/ngành (I4) và đọc ngày đăng, kinh nghiệm của TopDev (I3).
  - Git stash "preprocessing: so khớp theo từ + chuẩn hóa sau imputer (hoãn)" không còn cần; giữ lại, người dùng tự xóa bằng `git stash drop` nếu muốn.
  - Bỏ "ai" khỏi `skills.json`, thêm "trí tuệ nhân tạo", "ai/ml", "ai engineer".
  - Hết 5 lần thử vì 429/503 thì tính một lỗi.
- **Kiểm chứng:**
  - Đo trên `data/preprocessing/04_normalization/all.parquet`:
    - 200 tin có "backend" trong tiêu đề, 174 xếp Backend, không tin nào BA;
    - 0 tin tỉnh không dấu;
    - kỹ năng CareerViet, JobsGO lấy từ JD (SQL, Python…);
    - nhóm Data/AI từ 973 còn 724 tin sau khi bỏ "ai".
  - `test_vietnamese_word_ai_is_not_machine_learning`, `test_gemini_overload_503_stops_after_five_chunks`.
  - Phần TopDev còn thiếu là do raw thiếu (SCRAPE-5).

### L-28. Bỏ hẳn model/LLM khỏi dự án, thay bằng luật if-else (04/11/2026)
- **Lỗi:**
  - JEV (OpenCode `jev-1.13-free`) hết lượt miễn phí sau 188 câu, còn 10.775 câu; 4.052 tin kẹt ở "cần kiểm".
  - Gemini 3.8 Flash trả 429 hết hạn mức, chưa dịch được JD nào.
  - Kết quả phụ thuộc dịch vụ ngoài, khó giải thích.
- **Nguyên nhân:** pipeline 5 bước dựa vào model ở 4 chỗ:
  - C4a hỏi JEV tin có phải IT;
  - T6b dịch JD;
  - N2b hỏi JEV nhãn cấp bậc, nhóm nghề;
  - E8 mã hóa xác suất JEV.
- **Cách xử lý:** người dùng quyết định bỏ model (04/11/2026).
  - C4a: luật 2 tầng `it_filter.classify` + `classify_unknown` (nhóm nghề theo tiêu đề và ≥ 2 kỹ năng JD), lưu `it_rule_level`. `it_status` chỉ còn `it`/`non_it`. Người dùng chọn bỏ luôn tin tầng 2 xếp ngoài IT.
  - T6b, T6c bỏ; giữ `language`.
  - N2b: luật mâu thuẫn cấp bậc–kinh nghiệm và nhóm nghề–kỹ năng.
  - E8: cờ 0/1.
  - Xóa `common/jev_client.py`, `common/api_cache.py`, `transformation/translator.py`, cờ `--use-api`, khung API trên Monitoring.
  - Bộ bù giá trị của pipeline cũ (`genai_text_imputer.py`) bỏ đường gọi Gemini, chỉ còn luật.
- **Kiểm chứng:**
  - Chạy thật `--step all`: 14.292 bản ghi raw → 5.177 tin IT.
  - Tầng 1 đúng 303/304, tầng 2 đúng 194/237 (81,9%) trên nhãn tay.
  - N2b gắn cờ 635 tin.
  - R2 34/34 khớp.
  - Test `test_level2_needs_family_and_jd_skills`, `test_seniority_conflict_with_experience`, `test_e5_e8_*`; `make test`.

### L-29. Audit Task #2 (Clean & Dedup) tìm 8 lỗi B1–B8 về báo cáo, lineage, CDC và nhãn (07–08/11/2026)

Chi tiết từng mục ở `docs/tasks/02_tai_clean_and_deduplication.md` §5.4; đây là bản ghi cho toàn dự án.

- **Lỗi:**
  - B1: dry-run lẻ một sàn ghi đè báo cáo snapshot chung của 8 sàn.
  - B2: 7 cụm có `first_posted_at` sai (so chuỗi "DD/MM/YYYY" lẫn ISO).
  - B3: 3 tin repost mất khỏi Golden Master vì bản thua ở tầng liên sàn không được truyền.
  - B4: CDC báo 15 vi phạm "không tăng version" trong khi chỉ 5 bước thực đổi nội dung.
  - B5: điều kiện precision ≥95% được đánh dấu đạt bằng ghi chú trong `it_policy.json`, không phải nhãn từng tin; mẫu C4b thiếu tin tầng 1 dự đoán IT nên không đại diện đầy đủ cho precision IT.
  - B6: regex xóa boilerplate chạy trước NFC nên văn bản NFD không khớp.
  - B7: báo cáo nhầm `pairs_audited` với `cosine_pairs_computed`, block từng sàn với block toàn cục, non_IT trước/sau C5 (có tuyên bố "tăng 68000 lần" sai mẫu số).
  - B8: test gộp bắc cầu dựng sẵn `drop` thay vì kiểm thuật toán.
- **Nguyên nhân:**
  - B1/B7: biến `partial` và tên counter chưa tách phạm vi, báo cáo tái dụng số của phép đo khác.
  - B2/B3: khóa so sánh là chuỗi ngày và metadata tầng dưới không được gom từ toàn cụm.
  - B4: định nghĩa vi phạm chỉ nhìn `version`, không nhìn nội dung.
  - B5: công cụ kiểm định đọc `it_policy.json` (bản ghi quyết định) thay vì đọc nhãn theo `job_id`.
  - B6: thứ tự NFC/regex đảo nhau.
  - B8: fixture mô tả kết quả mong muốn thay vì đầu vào thuật toán.
- **Cách xử lý:**
  - B1: dry-run lẻ ghi sang `reports/preprocessing/_partial/<step>/`; test so byte toàn bộ báo cáo chính trước/sau cho cả Clean và Dedup.
  - B2: parse ngày, quy timestamp không offset về +07 rồi so UTC; giữ biểu diễn ngày đã chọn; ngày không parse được để riêng trong `unparsed_dates`.
  - B3: Golden Master và metadata bản giữ hợp `repost_records` từ toàn cụm (kèm source/job_id/url/hash); kiểm mỗi input ánh xạ đúng một master cuối.
  - B4: tách hai chỉ số và đổi định nghĩa theo nội dung: **`hop_same_version` = 15** là số bước cùng version; **`hop_version_not_bumped` = 5** là số bước cùng version **nhưng canonical hash đổi** (định nghĩa "đổi nội dung" dùng canonical hash, không dùng hash của crawler). Hai trường không đồng nghĩa; 15 bước đó gồm 9 raw payload giống hệt, 6 đổi raw payload. Monitoring hiển thị cả hai.
  - B5: bỏ đánh dấu nghiệm thu; `label_review` in TP/FP/TN/FN, `precision_it`, `precision_non_it`, `recall_it` chỉ từ nhãn từng tin, mẫu thiếu nhãn trả `null`/`NO_LABELS`; thiết kế lại mẫu C4b thành 3 tầng (non_IT tầng 1, mọi tin tầng 2, **100 tin tầng 1 dự đoán IT** chia theo sàn) qua `python -m preprocessing.clean.run --resample-review`. Báo Wilson nhị thức tham khảo trên mẫu đã trả lời. Đính chính ở L-30: không tự suy ra nghiệm thu từ cận dưới khi chưa hiệu chỉnh phân tầng; lead chưa yêu cầu dùng cận dưới làm tiêu chí. `--level1-it` cho phép đổi tổng mẫu trước khi gán.
  - B6: đưa NFC lên trước regex; test cùng văn bản NFC/NFD.
  - B7: thêm counter riêng (`cosine_pairs_computed`, `cosine_blocks`, `cross_pairs_evaluated`, `blocking_unique_blocks`, `lineage_rows`) và bỏ tuyên bố tốc độ sai mẫu số.
  - B8: test pipeline với A–B=0,85; B–C=0,9; A–C=0,8 kiểm master và `transitive-link`; điểm số trong test là fixture biên, không phải đo sản xuất.
- **Kiểm chứng:** 13.365 raw → 5.077 Clean → 4.897 Golden Master; 5.077 tham chiếu ánh xạ đúng một lần; 54 repost về lineage; 7 `first_posted_at` sửa, 0 sai min ngày; báo cáo chính giữ nguyên byte sau dry-run Glints; `test_deduplication_step.py` 55 đạt, Clean 31 đạt, `verify_delivery` chạy lại ở thư mục mới; toàn unit 176 đạt / 1 lỗi ngoài phạm vi (`KNOWN_ISSUED.md` SCRAPE-17); Ruff phạm vi bàn giao sạch; mẫu C4b dựng lại 643 dòng (543 cũ + 100 tầng 1 IT, phân bổ topcv 29/itviec 18/jobsgo 16/vnws 14/careerviet 9/glints 6/topdev 4/vieclam24h 4), hiện 0/643 nhãn.
- **Còn lại:** điều kiện precision ≥95% **chưa đóng** vì mẫu cục bộ hiện chưa có nhãn; chưa xác minh kho nhãn lịch sử toàn dự án (mục B5; `data/` bị gitignore nên không khôi phục từ git — xem `KNOWN_ISSUED.md` PRE-12); category gate tầng 2 chờ chốt SPEC-05 §2.4 theo số liệu 08/11 (xem `KNOWN_ISSUED.md` PRE-13).

### L-30. Kiểm chứng lại tạo mẫu và diễn giải bằng chứng Task #2 (08/11/2026)

- **Lỗi:** `--resample-review --source glints` bỏ qua source, gọi tạo mẫu cho cả tám sàn; `--level1-it` âm hoặc dùng ngoài chế độ tạo mẫu không được chặn. CLI tự kết luận ĐẠT từ Wilson cộng dồn; tài liệu gán yêu cầu cận dưới cho lead và biến regex category thành nhãn/ngữ nghĩa thật.
- **Nguyên nhân:** nhánh CLI gọi `resample_review` bằng mặc định SOURCES; chưa phân biệt thống kê mẫu phân tầng với dân số; probe tìm key và regex không phải bằng chứng nhãn tay.
- **Cách xử lý:** truyền sources đã chọn, kiểm tra tham số trước khi ghi; Wilson kiểm tra miền đầu vào; giữ CI tham khảo nhưng bỏ kết luận nghiệm thu tự động. Sửa §5.8, PRE-12/PRE-13, SCRAPE-17 và trả lời lead trong `cauhoi.md`; thêm cảnh báo Clean/CLAUDE. Không thay bộ lọc, nhãn, raw hoặc snapshot.
- **Kiểm chứng:** đầu lượt 176 đạt / 1 lỗi; sau sửa 180 đạt / 1 lỗi ledger ngoài phạm vi; Clean 35, Dedup 55, Ruff sạch. Test CLI kiểm tra nguồn và không gọi hàm ghi khi tham số sai. Đếm CSV 643/0 nhãn/100 tầng 1 IT; đếm raw pool 4.469. Category 842/101 rỗng/310 khớp/431 không khớp; regex mở rộng 428 khớp và chênh 118. Log `nov08_recheck`, lệnh trong task §5.7–5.8. Hash CSV review và JSON report được đối chiếu trước/sau.
- **Còn lại:** PRE-12, PRE-13 và SCRAPE-17 vẫn mở; không xóa vì chưa giải quyết nhãn, quyết định Q3 hay lỗi Collection. Chờ commit đặc tả Q4, duyệt hai cặp Q5 và nối Integration sau merge Task #2.

### L-31. Probe audit diễn giải sai điểm bắc cầu và độ dài JD (08/11/2026)

- **Lỗi:** probe Q5 gọi độ dài JSON payload là độ dài JD, tra job_id đơn lẻ xuyên sàn; probe ADR dùng điểm bắc cầu như cosine trực tiếp và suy số cạnh thành kết quả tách/gộp cụm. Tài liệu gọi cùng tập token là giống từng byte và mở lại quyết định Q4 đã chốt.
- **Nguyên nhân:** không đối chiếu ý nghĩa trường audit; chưa phân biệt đồ thị cụm với các cạnh hay payload với raw_description_text; tokenizer của probe bỏ thông tin.
- **Cách xử lý:** sửa hai script drafts, lookup bằng URL + job_id và chặn trùng khóa; đo riêng payload/JD qua flattener; loại 7 lineage rows khỏi phép thử trực tiếp. Cập nhật task §5.8.3/5.8.5, PRE-14 và phụ lục cauhoi. Không sửa thuật toán hoặc dữ liệu.
- **Kiểm chứng:** chạy lại hai script exit 0; 81/131 dropped, 14/55 review-band, 2/3 transitive-link đạt điều kiện kép của probe. JD Tinh Vân 826/382; Nasani 448/444/459 ký tự. 12 review-band bằng tập token, cosine 0,765–0,8426. Bảng Wilson tái hiện đủ tám cỡ mẫu. Hash 54 CSV review/JSON report không đổi. Log trong artifact nov08_recheck. Không chạy lại full unit vì chỉ sửa probe và tài liệu; 180 đạt/1 lỗi là kết quả lượt trước.
- **Còn lại:** Q5 vẫn cần nhãn nghiệp vụ; PRE-14 cần đồng bộ ADR với chuẩn lead đã chọn. Không suy số cụm từ số cạnh, không dùng tokenizer probe làm luật merge.

### L-49. Bước 02 bỏ sót hình thức làm việc, lần cào đầu và tách phúc lợi sai (PRE-37 việc 1, PRE-41, Dữ liệu, 18/11/2026)
- **Lỗi:** trang `docs/presentation/preprocessing_steps/02_integration.html` cho thấy: (1) bảng 02 không có `raw_work_mode`, nên bước 04 chỉ suy `work_mode` từ địa điểm, tin có tỉnh thì mặc định onsite; (2) itviec có `work_model` ở 789/818 tin nhưng flattener không đọc; (3) không có lần cào đầu, nên chưa tạo được `posted_month` (PRE-37); (4) careerviet trung bình 1,0 item phúc lợi mỗi tin (các nhãn dính liền), topdev 0,98 (cả khối HTML thành 1 item).
- **Nguyên nhân:** `raw_work_mode` bị bỏ theo luật "trường phải có ở ít nhất một nửa số nguồn" (spec 05 mục 3.3); `_flatten_itviec` không có dòng cho `work_model`; bước 01 chỉ giữ snapshot mới nhất, không ghi lại lần cào đầu; `_flatten_careerviet` tách theo `\n ; • - *` trong khi chuỗi không có dấu phân cách; `_flatten_topdev` lấy cả khối HTML.
- **Cách xử lý:** `preprocessing/clean/run.py` ghi `metadata.clean.first_scraped_at` (scraped_at nhỏ nhất của mọi snapshot và file batch cùng job_id); `preprocessing/integration/run.py` thêm `first_crawled_at` (thiếu thì lấy `crawled_at`) và giữ `raw_work_mode` (ngoại lệ người dùng duyệt 18/11); `json_flattener.py`: itviec `work_model` → `raw_work_mode`, `split_careerviet_benefits` tách theo 15 nhãn cố định, topdev tách khối HTML theo dòng và lấy `description` của `benefits_v2`. Chạy lại 01 → 01b → 02 trên tập raw đang có trên R2.
- **Còn lại:** bước 04 chưa dùng `raw_work_mode` (sửa khi tới bước 04); bước 03 chưa tạo `posted_month` (PRE-37 việc 2); từ điển phúc lợi (PRE-41).
- **Kiểm chứng:** 02: 4.672 → 4.671, 30 cột; `raw_work_mode` có ở topcv 99,5%, glints 100%, itviec 96,5%; item phúc lợi trung bình careerviet 8,7, topdev 9,5; `first_crawled_at` có ở mọi dòng. Test: `tests/unit/test_integration_step.py::test_careerviet_benefits_split_by_fixed_labels`, `::test_topdev_benefits_html_list_one_item_per_line`, `::test_itviec_work_model_kept_as_raw_work_mode`, `::test_integration_output_contract_and_conservation` (30 cột); `tests/unit/test_clean_step.py::test_rules_c1_to_c7_and_conservation` (`first_scraped_at`).

### L-50. Tin ngoài kỳ nghiên cứu, hai luật chọn bản giữ, TopCV thiếu ngày đăng và lẫn nhãn ngành vào kỹ năng (PRE-43, Dữ liệu, 18/11/2026)
- **Lỗi:** khi viết đặc tả từng bước (`docs/spec/preprocessing/`) thấy 4 chỗ: (1) glints ghi ngày tạo tin lần đầu, 76/246 tin có tháng đăng trước 08/2026 (sớm nhất 07/2023), cùng với tin tháng 8 ở vietnamworks, jobsgo, tổng 181 tin trước 09/2026 dù phạm vi đề tài là "tin đăng từ tháng 9"; (2) C7 (bước 01) giữ bản nhiều trường nhất, D5 (bước 01b) giữ sàn uy tín nhất trước, nên cùng một cặp trùng có thể ra bản giữ khác nhau; (3) raw TopCV có `date_posted` ở 102 tin nhưng flattener không đọc, cả 1.520 tin lấy tháng từ lần cào; (4) `skills_list` TopCV gộp `industry_knowledge` và `overview_tags["Chuyên môn"]`: "IT - Phần mềm" 838 tin, "Tài chính" 110, trong khi "Python" chỉ 67.
- **Nguyên nhân:** chưa có luật kỳ nghiên cứu; hai bước viết ở hai thời điểm với hai thứ tự tiêu chí; `_flatten_topcv` thiếu dòng cho `date_posted` và coi nhãn ngành là kỹ năng.
- **Cách xử lý (người dùng chốt 18/11):** `preprocessing/clean/run.py` thêm C9 (`out_of_window`: ngày đăng parse bằng `parse_date` của bước 03 và trước `STUDY_START` 2026-09-01 thì bỏ; không có ngày thì giữ; đặt trước C6) và `c7_winner`; `preprocessing/deduplication/run.py` `pick_cross_winner` đổi thứ tự thành độ đầy đủ → uy tín → mới nhất → `job_id`, chung với C7; `json_flattener.py` đọc `date_posted`, chuyển hai loại nhãn TopCV sang khóa `category_tags` (chỉ bộ lọc IT của bước 01 đọc, nên kết quả lọc không đổi: C4a 5.424 như cũ); I4 của bước 02 đếm cả TopCV; `feature_targets.py` sửa `RAW_PATHS` TopCV. Chạy lại 01 → 01b → 02.
- **Còn lại:** chạy lại 03 trên bảng 02 mới (cùng lượt dịch), rồi 04 và Silver.
- **Kiểm chứng:** 01: C9 bỏ 197 tin (glints 100, vietnamworks 82, jobsgo 13, topcv 1, vieclam24h 1), ra 4.621; 01b: D5 125, ra 4.496; 02: 4.495 tin, 30 cột; TopCV `raw_posted_date` 102 tin; top kỹ năng TopCV là Python 68, SQL 66 (không còn nhãn ngành). Test: `tests/unit/test_clean_step.py::test_c9_out_of_study_window`, `::test_c7_keeps_most_complete_then_most_authoritative`, `tests/unit/test_deduplication_step.py::test_pick_cross_winner_độ_đầy_đủ_trước_uy_tín`, `tests/unit/test_integration_step.py::test_topcv_date_posted_and_skills_without_industry_labels`.

### L-51. Bộ lọc IT đúng 90,8%, dưới đích 95% (PRE-12, Dữ liệu, 19/11/2026)
- **Lỗi:** bước 01, C4a xếp sai 59/643 nhãn C4b (đúng 90,8%, precision IT 86,5%): tầng 1 sai 16, tầng 2 sai 43; các tin sales, đồ họa, điện/cơ khí lọt vào tập IT.
- **Nguyên nhân:** chưa có định nghĩa "tin IT" thống nhất nên cả nhãn lẫn luật đều lệch ở ca ranh giới; tầng 2 (`classify_unknown`) đếm 40 kỹ năng viết tay (`TECH_SKILLS`) và không phân biệt chuyên mục sàn đáng tin hay không.
- **Cách xử lý:** người dùng chốt định nghĩa "vai trò IT", chuyên mục sàn là tín hiệu phụ (C), ưu tiên precision, cùng Q1–Q8, H1–H9 (`docs/spec/preprocessing/01_clean.md` mục 2.1). Soát lại nhãn (`data/preprocessing/gold/it_review/relabel_2026-11-19.csv`, 168 IT / 475 không IT), chia tune 451 / giữ lại 192. `preprocessing/common/it_filter.py` thêm luật ba tầng (`excluded_role`, `classify_tier1`, `it_signals`, `tier2_decide`, `classify_it`) theo `preprocessing/dictionaries/it_filter_v2.json` (phương án B: nhóm nghề + ≥ 2 kỹ năng lõi skills_v2, hoặc ≥ 8 kỹ năng lõi, hoặc itviec có chuyên mục IT). Chạy thật lại 01 → 01b → 02: 4.621 → 4.103 → 3.998 → 3.997.
- **Còn lại:** recall IT 82% trên tập giữ lại (luật ưu tiên sạch nên bỏ nhầm một phần tin IT, nhất là vietnamworks, jobsgo). Người dùng chấp nhận khoảng tin cậy hiện có ngày 19/11.
- **Kiểm chứng:** `pytest tests/unit/test_it_filter.py` (27 test); `python scripts/eval_it_filter.py`: tập giữ lại đúng 94,8% [90,7; 97,2], precision IT 97,6% [87,7; 99,6]; cả 643 nhãn đúng 95,0%. Tin lật so với 18/11: `data/preprocessing/review/it_filter_flips_2026-11-19.csv` (người dùng chấp nhận).

### L-52. Tên hiển thị "C#" thành "C" trong skills_v2 (Dữ liệu, 19/11/2026)
- **Lỗi:** `skills_v2.json` ghi `csharp` với tên "C", trùng tên với `c_lang`. Chỉ ảnh hưởng tên hiển thị (trang duyệt, cột `skill` của `job_skills.parquet`); khớp đi qua alias nên không đổi kết quả trích.
- **Nguyên nhân:** `read_lines` trong `scripts/build_skills_v2.py` cắt mọi thứ sau `#` như chú thích, nên `n=C#` còn `n=C`.
- **Cách xử lý:** chú thích chỉ bắt đầu ở `#` đầu dòng hoặc sau khoảng trắng. Dựng lại từ điển: chỉ tên `csharp` đổi, các trường khác và `not_skill`, `can_hoi` giữ nguyên. `read_lines` cũng bỏ qua `types_*.txt` (danh sách nhãn K8.17, không phải lệnh từ điển).
- **Còn lại:** `job_skills.parquet` mang tên mới khi chạy lại bước 08 (P2).
- **Kiểm chứng:** `pytest tests/unit/test_skills_v2.py -k hash_inside_names`.

### L-53. Báo cáo bước 07 hoặc 08 mất khối `samples` khi chạy bước kia (Dữ liệu, 19/11/2026)
- **Lỗi:** sau `run_preprocessing.py --step skills`, `reports/processing/07_sections/*.json` mất `samples`; chạy `--step sections` thì 08 mất. Commit 5223195 có 07 có mẫu, 08 không có.
- **Nguyên nhân:** `processing.extraction.run` ghi lại báo cáo cả 07 và 08 trong một lần gọi, còn driver chỉ gắn mẫu (`_finish_reports`) cho bước được gọi.
- **Cách xử lý:** `scripts/run_preprocessing.py`: `SAME_CALL = ("07_sections", "08_skills")`; chạy một trong hai thì gắn mẫu cho cả hai. Chạy lại 08 ngày 19/11: cả hai báo cáo có 3 mẫu mỗi nguồn.
- **Kiểm chứng:** `pytest tests/unit/test_ph9_chain.py -k both_07_and_08`.

### L-54. Chạy thử ghi đè `samples_reason` vào báo cáo thật (Dữ liệu, 19/11/2026)
- **Lỗi:** `run_preprocessing.py --step e5 --dry-run` sửa 18 file `reports/*/12_e5/*.json` đang trong git: `samples_reason` từ `NO_ROWS_CHANGED` thành `DRY_RUN_NO_OUTPUT`, dù không có báo cáo mới.
- **Nguyên nhân:** `_finish_reports` gắn mẫu (và chép sang `reports/preprocessing/`) cả khi chạy thử, trong khi `StepReport.write` chỉ ghi khi chạy thật.
- **Cách xử lý:** `_finish_reports` trả về ngay khi `dry_run`. Khôi phục 18 file bằng `git checkout`.
- **Kiểm chứng:** `pytest tests/unit/test_ph9_chain.py -k dry_run_does_not_touch`; chạy lại `--step e5 --dry-run` thì `git status` không có báo cáo nào đổi.

## 3. Monitoring

### L-15. Trang Raw hiện kinh nghiệm "1 - 10 Năm" thành 10 năm

- **Lỗi:** tin yêu cầu "1 - 10 Năm" bị tính là 10 năm kinh nghiệm.
- **Nguyên nhân:** `_experience_years()` trong `source_report_service.py` lấy số cuối cùng trong chuỗi.
- **Cách xử lý:** với khoảng thì lấy cận dưới.
- **Kiểm chứng:** `tests/integration/test_known_issue_fixes.py::test_experience_years_takes_lower_bound_of_range`.

### L-16. Thẻ "Đẩy dữ liệu lên R2" có thể vượt 100%

- **Lỗi:** thẻ hiện 12.825 / 12.779 và báo xong, dù vẫn có file trên máy chưa lên R2.
- **Nguyên nhân:** so hai con số đếm (số key trên R2 với số file trên máy). R2 có thêm file mà máy không có nên tổng R2 lớn hơn, che mất file thiếu.
- **Cách xử lý:** `r2_client.get_full_cloud_sync_status()` so từng key. Thẻ ghi "X / Y file raw trên máy đã có trên R2 · R2 có thêm Z file"; chỉ báo xong khi mọi file trên máy đã có trên R2.
- **Kiểm chứng:** trang Collection 03/11 hiện 12.778 / 12.779, R2 có thêm 47 file.

### L-17. Trang Crawling không chọn được có đồng bộ R2 hay không

- **Lỗi:** bấm chạy crawler từ trang Crawling thì không đồng bộ R2 (cùng nguyên nhân L-01), và không có cách bật.
- **Nguyên nhân:** API trigger không có tham số sync và không truyền `--sync-r2`.
- **Cách xử lý:** thêm `TriggerCrawlRequest.sync_r2` (mặc định `True`); `crawler_service.trigger_crawler` thêm `--sync-r2`; trang Crawling có ô chọn "Đồng bộ R2", bật sẵn.
- **Kiểm chứng:** `tests/integration/test_ledger_sync.py::test_crawling_page_trigger_passes_sync_r2`, `test_trigger_request_defaults_to_sync`.

### L-18. Trang Crawling và Pre-processing tràn ngang trên điện thoại (VIZ-1, VIZ-2)

- **Lỗi:** ở bề rộng 390px, hai trang có thanh cuộn ngang.
- **Nguyên nhân:** hàng lọc ledger trên trang Crawling không xuống dòng và ô nhập có bề rộng cố định; đường dẫn file dài trong `SectionTitle` không ngắt được.
- **Cách xử lý:** hàng lọc dùng `flex flex-wrap gap-2`, ô nhập `w-full sm:w-56`; gợi ý trong `SectionTitle` dùng `[overflow-wrap:anywhere]`.
- **Kiểm chứng:** kiểm bằng Chrome chạy ẩn (Playwright) cả 7 trang ở 390px và 1440px: không tràn, không lỗi console.

### L-19. Trang ML 3D hiện tọa độ ngẫu nhiên (VIZ-4)

- **Lỗi:** trang đã ẩn nhưng endpoint `/api/v1/mining/spatial-3d` vẫn trả số ngẫu nhiên, trái quy tắc "chỉ hiện số thật".
- **Nguyên nhân:** chưa có bước mining nào sinh dữ liệu cho trang này.
- **Cách xử lý:** xóa trang, endpoint và service.
- **Kiểm chứng:** `npm run build` qua; router không còn route `spatial-3d`.

## 4. Testing

### L-29. EDA P5 lỗi khi mở từ thư mục notebooks (09/11/2026)

- **Lỗi:** `eda_p5_final_cohort.ipynb` tìm `notebooks/data/preprocessing/05_encoding/artifact_manifest.json` và fail khi Restart Kernel → Run All từ `notebooks/`.
- **Nguyên nhân:** dùng `root = Path.cwd()`; builder cũ khởi động kernel tại repo root và inject root vào PYTHONPATH nên che giả định cwd/import.
- **Cách xử lý:** cell đầu tìm repo root từ ancestors, thêm root vào sys.path trước import, lấy run từ manifest. Builder nhận `--output-dir`/`--kernel-cwd`, không inject ROOT, bảo vệ output đã có. Tái tạo notebook và HTML đồng bộ, giữ bản trước cùng checksum.
- **Kiểm chứng:** tái hiện lỗi từ `notebooks/` bằng namespace mới; sau sửa dùng Python 3.14.4, kernel mới tại `notebooks/`, chạy đủ 6 cells không lỗi và xuất HTML. 72 P5 tests và Ruff pass; 10 artifact tái tạo vào `/tmp` giống bytes canonical. Evidence tại `reports/preprocessing/05_encoding/refactor_2026-11-09/`; xem [report P5](preprocessing/encoding/07_p5_execution_report.md#p5-refactor).
- **Còn lại:** không có mục tương ứng cần xóa trong KNOWN_ISSUED. Không thay các giới hạn nghiệm thu P5 về lineage, scope, Python 3.12 và whole-repo tests.

### L-20. Test không có cấu trúc, không có test cho crawler (PRE-5)

- **Lỗi:** 12 file test nằm chung một thư mục, không marker, không `conftest.py`. 3 test đọc thẳng `data/` nên fail trên máy không có dữ liệu; 1 test qua mà không kiểm tra gì. Không có test nào cho 8 crawler.
- **Nguyên nhân:** test được thêm dần theo từng việc, không có quy trình chung.
- **Cách xử lý:**
  - Chia `tests/unit`, `integration`, `contract`, `data`, `fixtures`; `tests/conftest.py` tự gắn marker theo thư mục, chặn mạng ngoài localhost (trừ `@pytest.mark.live` với `--run-live`), và skip test `needs_data` khi thiếu dữ liệu.
  - Lệnh `make test`, `test-fast`, `test-contract`, `test-live`.
  - Chốt bộ tiêu chuẩn crawler C1–C14 (`collection/CLAUDE.md`) và viết contract test chạy offline cho TopDev và TopCV với mẫu thật trong `tests/fixtures/<nguồn>/`.
- **Còn lại:** contract test cho 6 nguồn còn lại (SCRAPE-14); báo cáo chất lượng code đã làm ở L-22.
- **Kiểm chứng:** `make test`: 143 qua, khoảng 7 giây, không cần mạng.

### L-22. `make check` gọi target `quality` chưa có (GEN-3)

- **Lỗi:** `make check` dừng ở bước `quality`, nên không có cách nào chạy đủ test, kiểm tra code và build bằng một lệnh.
- **Nguyên nhân:** target `check` được viết trước khi có công cụ báo cáo chất lượng code.
- **Cách xử lý:** thêm `scripts/report_code_quality.py` (ruff F401/F811/F841, vulture, so cây cú pháp tìm hàm trùng logic và trùng tên, tìm module không ai import), ghi `docs/code_quality.md`; thêm `make quality`; thêm `vulture==2.14` vào `requirements-dev.txt`. Báo cáo chỉ liệt kê, không xóa hay gộp gì.
- **Kiểm chứng:** `tests/unit/test_report_code_quality.py` (5 test với project mẫu: trùng logic khác tên, trùng tên, module không ai import, hàm có người gọi không bị báo); `make check` chạy hết.

### L-29. Tách trang Crawling và bổ sung Market Insights đọc PostgreSQL Mart

- **Lỗi:** VIZ-5 dồn state, API, log và UI vào CrawlingPage; thiếu nhóm API `/insights` đọc Mart theo yêu cầu sprint.
- **Nguyên nhân:** Trang Crawling phát triển theo một file; các trang báo cáo cũ phụ thuộc artifact tĩnh.
- **Cách xử lý:** CrawlingPage còn 25 dòng điều phối, hook state/API và các presenter trong `components/crawling/`. Thêm truy vấn SQL chỉ đọc, heatmap median/P25/P75, luật Macro/Micro và scatter PCA 2D/3D. Không sinh dữ liệu thay thế.
- **Kiểm chứng:** Frontend production build thành công; 6 test API Insights qua; 4 endpoint HTTP 200 `EMPTY/NO_DATA` trên PostgreSQL thật; UI Empty State toàn trình React/FastAPI/PostgreSQL không tràn tại 390px/1440px; hồi quy monitoring 32 passed, 1 skipped.
- **Còn lại:** Chưa có dữ liệu Mart để xác minh biểu đồ có dữ liệu; xem báo cáo Sơn. VIZ-3 ở các trang cũ ngoài Insights vẫn được giữ theo phạm vi leader chốt.

### L-30. EDA phụ thuộc raw và staging local dù dữ liệu đã có trên R2

- **Lỗi:** Không xem được EDA trên máy chưa đồng bộ dữ liệu.
- **Nguyên nhân:** EDA chỉ đọc data/<source>/raw và Parquet staging local.
- **Cách xử lý:** Thêm origin=r2, đọc object vào RAM bằng client R2 chung, cache 60 giây, bộ chọn Local/R2. Tách tính biểu đồ từ DataFrame để dùng chung hai nguồn. Lỗi đọc không bị đổi thành số 0 hoặc fallback local.
- **Kiểm chứng:** 16 test qua; build frontend thành công; đọc thật TopCV trên R2 được 1.561 dòng staging và 200 raw mẫu.
- **Còn lại:** Chưa đối soát 8 nguồn; object >128 MiB cần hướng truy vấn Parquet theo range hoặc artifact nhỏ hơn. Xem báo cáo Sơn mục 7.

### L-31. EDA hiện trống tỉnh/thành dù Parquet R2 có địa điểm (09/11/2026)

- **Lỗi:** Khối tỉnh/thành trên `/eda` báo chưa có số liệu với TopCV.
- **Nguyên nhân:** `pipeline_report_service.eda_charts_from_frame` chỉ đọc `primary_city`, nhưng `04_normalization.parquet` hiện dùng `tinh_chinh` (1.548/1.561 dòng TopCV có giá trị).
- **Cách xử lý:** Ưu tiên `tinh_chinh`, fallback `primary_city` theo dòng còn thiếu; loại null/chuỗi trắng trước khi đếm Top 8. Áp dụng chung cho R2 và Local. Không thay đổi dữ liệu R2. Không có mục tương ứng trong `KNOWN_ISSUED.md` cần xóa.
- **Kiểm chứng:** Đọc Parquet TopCV thật từ R2 vào RAM và gọi hàm biểu đồ đã sửa; danh sách 8 nhóm khớp `value_counts().head(8)` của cột nguồn, gồm Hà Nội 1.033 và TP. Hồ Chí Minh 351 tin.
- **Còn lại:** Chưa đối soát 8 nguồn và chưa kiểm lại trình duyệt; xem báo cáo Sơn mục 7.


### L-32. Duplicate EDA chờ mãi dù kiểm kê raw đã hoàn tất (10/11/2026)

- **Lỗi:** TopCV đã có missing/inventory nhưng khối duplicate vẫn báo chờ quét hoàn tất.
- **Nguyên nhân đã xác nhận:** GET summary trên backend cổng 8000 trả raw_scan COMPLETE với 2.755 bản ghi nhưng không có key duplicates; tiến trình Uvicorn vẫn chạy code trước khi thêm duplicate. UI dùng cùng Empty State cho đang quét và COMPLETE thiếu dữ liệu.
- **Cách xử lý:** Restart đúng Uvicorn Monitoring ở cổng 8000 để nạp code mới; không bật scheduler. `scan()` phát hiện cache COMPLETE thiếu duplicates để tự dựng lại. UI phân biệt đang quét, quét lỗi và COMPLETE thiếu kết quả (hướng dẫn restart backend).
- **Kiểm chứng:** Tái hiện response thiếu duplicates của backend cũ; backend mới khởi động thành công. 3 unit test quét raw qua, có test cache COMPLETE cũ cần tự quét lại. Quét Glints thật hoàn tất 334 bản ghi, 333 payload khác nhau, 1 bản ghi trùng dư (0,30%), 2 object dư theo ID filename. Đang đối chiếu lại TopCV qua API backend mới.
- **KNOWN_ISSUED:** Không có mục tương ứng cần xóa.
- **Đối chiếu TopCV qua API đang chạy:** COMPLETE 2.755/2.755 object/bản ghi; 2.746 payload khác nhau, 9 bản ghi trùng dư trong 9 nhóm (0,33%); 2.680 ID filename và 75 object dư theo ID. Kết quả duplicate hiện đã có trong raw_scan của GET summary.
- **Kiểm tra toàn trình:** Edge headless mở trang EDA đang chạy, dùng API backend thật và cache TopCV vừa quét: đã thấy Bản ghi trùng dư, thông báo chờ cũ không còn, không có pageerror.


### L-33. Layout R2 lệch 5 tiền tố đã chốt (GEN-4, 10/11/2026)

- **Lỗi:** Bucket có thêm `silver/` (3 object), `quality/` (26), `integration/` (18), `transformation/` (18) ngoài 5 tiền tố chốt `url_ledger/`, `raw/`, `staging/`, `curated/`, `pipeline/`.
- **Nguyên nhân:** Các pipeline cũ ghi theo layout riêng; code chỉ biết 4 tầng và `silver/`, `gold/`.
- **Cách xử lý:** Thêm `pipeline` vào `R2_LAYER_PREFIX` và alias `silver`→`staging`, `gold`→`curated` (`collection/common/r2_storage.py`, `scripts/migrate_lakehouse_layout.py`). Chạy thử rồi `--prefix-map --apply`: chép `silver/silver_dataset_health_card.json` sang `staging/`; 2 file lớn báo ETag khác (do multipart) nên đối chiếu SHA-256, trùng thì chép tay xong xóa key cũ. Xóa 62 object ở 3 prefix thừa (output cũ ngày 25-26/10 và 01/11, sinh lại được từ raw).
- **Còn lại:** Tên thư mục con của `pipeline/`; tên file trong `staging/`, `curated/` (GEN-4).
- **Kiểm chứng:** Liệt kê lại bucket: `curated` 2, `raw` 12.826, `staging` 35, `url_ledger` 64.
- **KNOWN_ISSUED:** GEN-4 còn mở phần tên file; đã ghi việc đã làm vào GEN-4.

### L-34. Làm sạch ký tự và schema bước 02 (PH2, 10/11/2026)

- **Lỗi:** (1) `integration/run.py` giữ dòng JSON hỏng thành bản ghi giả; (2) id dự phòng của `json_flattener` dùng `hash()` đổi mỗi tiến trình; (3) `strip_html_tags` nuốt `<->`, để lại `&nbsp;` khi mã hóa hai lần, cắt đôi từ ở thẻ inline; (4) 42 tin còn NFD, ký tự ẩn còn sót, gạch ngang/bullet không thống nhất.
- **Nguyên nhân:** Zero-drop áp cho cả dòng không phải bản ghi; `hash(str)` có hạt giống ngẫu nhiên; regex `<[^>]+>` quá rộng; chưa có bước NFC/ký tự ẩn.
- **Cách xử lý:** `rejected/02_integration` (I0, I6 qua pydantic `JobRecord` gồm `job_title` rỗng, I7 qua `strict=True`); id `sha1(url)[:16]`; regex thẻ sửa, unescape tối đa 2 lần; `preprocessing/common/text_clean.py` (NFC, ký tự ẩn, gạch ngang, bullet `- `, lặp tối đa 3 lần khi còn HTML/NFD rồi chỉ cảnh báo) và cột `*_norm`, `*_fold`.
- **Kiểm chứng:** `pytest tests/unit` 359 xanh; chạy khô trên 5.077 tin thật: HTML, NFD, ký tự ẩn còn lại đều 0 ở 8 nguồn; 1 tin careerviet thiếu `job_title` vào rejected.

### L-35. Chuẩn hóa trường sai: chia 12, Backend hút Embedded, nhãn cấp bậc từ số năm không cờ (PH6/PH7, 10/11/2026)
- **Lỗi:** (1) `fix_common_salary_input_errors` chia 12 khi JD có chữ "năm" (vietnamworks `8000 - 9000 USD` từ 203-229 triệu thành 16,9-19,1 triệu) và coi số 100..10.000 là USD; (2) nhãn USD gắn nhầm cho số VND (`7000000 - 10000000 USD`) làm lương bị bỏ; lương năm ghi trong JD (`Annual Salary: 22,000~36,000 USD`) bị bỏ; (3) `Backend` hút Embedded và mọi `developer`; `Nhân Viên Thiết Kế` ra UI/UX; (4) 44,4% nhãn cấp bậc do số năm tạo ra mà không có cờ; (5) N1 bỏ sót 712 tin có tỉnh trong `raw_location_text`; (6) 787 tin itviec và "Không yêu cầu"/"Dưới một năm"/"Lên đến N năm"/"Hơn N năm" không parse được kinh nghiệm.
- **Nguyên nhân:** sửa lương dựa chữ "năm" rời rạc; bộ từ khóa Backend quá rộng; luật số năm nằm trong N2 không đánh dấu; N1 chỉ nhìn `locations`; `experience_parser` thiếu 5 dạng chuỗi.
- **Cách xử lý:** hằng `USD_VND` một nơi (`preprocessing/common/constants.py`); bỏ hai nhánh sai; parser lương đọc lại nhãn USD khi số >= 100.000 và chỉ tính theo năm khi JD ghi đúng các số đó là lương năm; 5 cấp bậc, số năm chuyển sang PH7 (`level_inferred`); 12 nhóm SPEC-01 + `Other`; `job_title.py`, `company_key.py`, `missing_rules.py`; mọi cờ kèm `job_id` trong `anomalies.json`.
- **Kiểm chứng:** `tests/unit/test_ph6_ph7_normalization.py` với chuỗi thật; đo trong bộ nhớ trên 5.076 tin (số trong báo cáo giao việc).

### L-36. Dedup không nằm trong chuỗi, TF-IDF chỉ so khác sàn; thiếu lọc CTV/đa cấp và nhận diện ngôn ngữ (PH3/PH4, 10/11/2026)
- **Lỗi:** (1) `01b_deduplication` ngoài `STEPS`, 02 đọc thẳng 01_clean nên đầu ra dedup không được dùng; (2) tin gần trùng cùng sàn chỉ bị bắt khi hash khớp tuyệt đối; (3) chưa lọc tin CTV/đa cấp, JD ngắn dùng 30 từ; (4) `language` do luật đếm dấu, không có độ tin cậy, không có nhãn `other`.
- **Nguyên nhân:** pipeline dedup dựng riêng; thuật toán TF-IDF cosine trong block; ngôn ngữ là luật tạm.
- **Cách xử lý:** `01b_deduplication` vào `STEPS`, 02 đọc 01b; tầng 2 sha1(text_fold) + cùng company_slug, tầng 3 MinHash/LSH rồi Jaccard chính xác >= 0.85 + cùng company_slug, cả cùng sàn lẫn khác sàn (`dedup_policy.json`); C8 bỏ CTV/đa cấp, JD ngắn 50 từ ở 01_clean; fastText lid.176 (`models/fasttext`, git-ignored) gắn `language`, `language_conf` ở 03.
- **Kiểm chứng:** `pytest tests/unit` + `tests/integration/test_preprocessing_steps_api.py` xanh; 5.077 -> 4.826 sau dedup (D2 72, D4 11, D5 168), chạy 2 lần cho file giữ/loại giống hệt. Precision dedup và loại nhầm C8 chưa đo, chờ người dùng gán nhãn.
- **KNOWN_ISSUED:** không có mục tương ứng.

### L-37. Khóa C6 có tuần cào; phúc lợi quét cả mô tả công việc (10/11/2026)
- **Lỗi:** (1) `dedup_key` của 01_clean có thành phần tuần nên tin đăng lại ở tuần khác không bị gộp; (2) `extract_benefits` so chuỗi con trên toàn JD, nên "máy tính", "laptop", "training" trong phần việc cũng thành phúc lợi "Thiết bị làm việc", "Đào tạo"; "chứng chỉ" (yêu cầu) bị tính là đào tạo.
- **Cách xử lý:** bỏ tuần khỏi `dedup_key` (xóa `_week`); `extract_benefits` chỉ quét `benefits_list` và phần JD từ tiêu đề phúc lợi trở đi, khớp theo ranh giới từ; bỏ "máy tính", "chứng chỉ", "certifications" khỏi `benefits.json`.
- **Kiểm chứng:** `tests/unit/test_pre_fixes.py` (3 test), `tests/unit` 441 qua. Đo trên 03_transformation (4.798 tin): nhãn phúc lợi 19.283 -> 17.769, "Thiết bị làm việc" 1.068 -> 706; dry-run 01_clean ra 4.836 (trước 5.050). Chưa đo precision/recall phúc lợi và precision dedup vì chưa có nhãn tay.

### L-38. Rà lại `KNOWN_ISSUED.md` sau PH0–PH9: đóng mục đã sửa, gộp mục trùng (10/11/2026)
- **Lỗi:** `KNOWN_ISSUED.md` còn nhiều mục đã sửa hoặc bị phương án mới thay, và nhiều mục trùng nhau.
- **Nguyên nhân:** danh sách viết ngày 09/11 trước khi đợt PH0–PH9 đổi dedup (MinHash), dịch (envit5), cấp bậc (5), kỹ năng (taxonomy 230), layout R2 (5 tiền tố).
- **Cách xử lý:** viết lại file; đóng PRE-16, 17, 18, 19, 22, 28, 29, MINE-2, MINE-3, VIZ-3, GEN-9, GEN-6 (gộp vào SCRAPE-17); gộp SCRAPE-5+7+16 và SCRAPE-15+18; gộp PRE-13 và PRE-15 vào PRE-12; PRE-14 viết lại; thêm PRE-32, PRE-33, GEN-10.
- **Kiểm chứng (đã chạy 10/11):**
  - PRE-16: `preprocessing/integration/run.py:29` `IN_DIR = .../01b_deduplication`.
  - PRE-17: `reports/preprocessing/01_clean/_all.json` và `01b_deduplication/_all.json` ghi lại 10/11 19:25–19:26 bởi chuỗi PH9.
  - PRE-18: `pytest tests/unit/test_integration_step.py -k "json or invalid or reject"` 2 qua; code `integration/run.py:180-186`.
  - PRE-19: `grep "abs(hash(" preprocessing processing mining` không còn kết quả.
  - PRE-22: `text_cleaner.SENIORITY_LABELS` 5 nhãn, `encoding/run.py:50` dùng chung; `job_family` có 12 nhóm + Other, không UI/UX; `pytest tests/unit tests/contract` 493 qua, 1 bỏ qua. Nhãn "Chưa rõ" chỉ còn ở đường cũ của `transformation/pipeline.py` (PRE-21).
  - PRE-28, PRE-29: bị PH8 (taxonomy 230, `min_df`) và PH5 (`translator.py`) thay.
  - MINE-2, MINE-3: `import mlxtend, shap, hdbscan` thành công trong `.venv`; test mining nằm trong 493 qua.
  - VIZ-3: báo cáo `reports/preprocessing/*` ghi lại 10/11.
  - Còn mở sau khi kiểm: PRE-23 (`tối thiểu 10 triệu` ra single_value, `2 tỷ` ra 2,0 triệu), PRE-27 (module `target_schema_formatter` không tồn tại), GEN-4 (`canonicalize_lakehouse_key("staging/all.parquet")` vẫn bị từ chối), PRE-26 (70 file, 4,6 MB).
  - Chưa kiểm: nội dung hai mục PRE-16/17 mà người dùng nêu (trích xuất còn sót, kiểm định sau mining), chưa có tài liệu gốc nên chưa ghi vào file.

### L-39. Cấp bậc và kinh nghiệm quy đổi hai chiều theo khoảng người dùng chốt (PH7, 11/2026)
- **Lỗi:** luật cũ `>= 5 năm -> Senior` ngược với dữ liệu (Senior thật có trung vị 3 năm); thiếu kinh nghiệm chỉ được điền cho Intern/Fresher (349 tin vẫn `unknown`).
- **Nguyên nhân:** ngưỡng X6 lấy từ spec P4 và code cũ, chưa có khoảng người dùng duyệt.
- **Cách xử lý:** `level_by_years` (`preprocessing/normalization/text_cleaner.py`): [0,1) Fresher, [1,2) Junior, [2,4) Middle, [4,5) Senior, từ 5 năm để trống. `infer_experience_from_level` (`preprocessing/missing_outlier/missing_rules.py`): thiếu kinh nghiệm thì điền cận dưới theo cấp (0/1/2/4/5) khi cấp từ raw hoặc title, `exp_source="level_<cấp>"`, vẫn chặn vòng. Cập nhật spec và prompt PH7.
- **Kiểm chứng:** `tests/unit/test_ph6_ph7_normalization.py` 30 qua; `tests/unit` 512 qua, 1 bỏ qua.
- **KNOWN_ISSUED:** không có mục tương ứng. Mâu thuẫn cấp bậc-kinh nghiệm vẫn dùng ngưỡng cũ của `seniority_conflict` (Senior < 2 năm, Fresher >= 3 năm).

### L-40. Khóa trùng tên còn tỉnh nên sót tin cùng công ty và cùng tiêu đề; bỏ ghi chú trùng khác ngôn ngữ (PH3/PH4, 11/2026)
- **Lỗi:** sau dedup còn 40 tin có cùng `company_key` và tiêu đề chuẩn hóa với tin khác (29 cặp cùng tỉnh nhưng một bên thiếu tỉnh nên khóa lệch, 11 cặp khác tỉnh).
- **Nguyên nhân:** `dedup_key` (`preprocessing/clean/run.py`) ghép thêm khóa tỉnh của địa điểm đầu tiên.
- **Cách xử lý:** khóa chỉ gồm công ty và tiêu đề (người dùng chốt 11/11). Bỏ khóa `cross_language_dupes` trong báo cáo 01b và đóng C9 trong spec PH4: trùng khác ngôn ngữ không xử lý. Lớp so JD (sha1 và MinHash >= 0,85 cùng công ty) giữ nguyên.
- **Kiểm chứng:** `tests/unit/test_pre_fixes.py::test_dedup_key_is_company_and_title_only` và `test_clean_step.py` 41 qua; chạy lại chuỗi 11/11: 4.699 → 4.671 tin (giảm 28; ước tính trước đó là 40); `tests/unit tests/contract` 571 qua, 1 bỏ qua.
- **KNOWN_ISSUED:** không có mục tương ứng. Rủi ro: tin cùng tên ở hai tỉnh khác nhau bị coi là một.

### L-41. Discovery lỗi toàn trang vẫn báo thành công ở 5 nguồn; tin CLOSED; nodriver; thế hòa ledger (Collection, 11/2026)
- **Lỗi:** (a) CareerViet, Vieclam24h, ITviec, JobsGO không raise khi không lấy được trang danh sách nào, Glints raise `RuntimeError` thường; Airflow không báo đỏ (SCRAPE-11). (b) JobsGO in `RuntimeError: Event loop is closed` lúc đóng nodriver (SCRAPE-12). (c) Test `test_latest_status_change_wins_between_workers` fail trên Windows (SCRAPE-17). (d) Báo cáo "tin CLOSED vẫn có raw mới" của VietnamWorks (SCRAPE-8).
- **Nguyên nhân:** (a) chỉ TopCV, TopDev, VietnamWorks có đếm `pages_ok`. (b) `asyncio.run` đóng loop trước khi transport tiến trình con của nodriver đóng xong. (c) đồng hồ Windows thô nên hai lần `mark_*` liền nhau có cùng `updated_at`, luật `mem_ts >= disk_ts` để bản lưu sau thắng. (d) không phải lỗi hiện tại: `get_pending_or_due_records` đã loại `CLOSED` và crawler không ghi raw khi tin đóng; ca 20/10 và 01/11 do lỗi ledger cũ trước 03/11 không lưu được `CLOSED` (L-24).
- **Cách xử lý:** (a) thêm `pages_ok`/`first_error` và `raise DiscoveryError` (C14) ở CareerViet, Vieclam24h, ITviec (chỉ khi sitemap cũng không thêm được gì), JobsGO; Glints raise `DiscoveryError` khi không có trang nào (vẫn là `RuntimeError` nên chỗ bắt cũ chạy); VietnamWorks tầng 3 thêm đếm `pages_ok`. (b) `await asyncio.sleep(0.5)` sau `browser.stop()`. (c) `_change_ts()` trong `collection/common/url_ledger.py` bảo đảm `updated_at` tăng nghiêm ngặt trong một tiến trình. (d) thêm test khóa hành vi.
- **Kiểm chứng:** `tests/contract/test_discovery_error_c14.py` 6 qua (offline); `tests/unit/test_url_ledger_dedup.py` 13 qua gồm `test_closed_record_never_selected_for_detail` và `test_change_timestamps_strictly_increase`; `tests/contract` đầy đủ qua. Chưa chạy được trên Windows và chưa cào thật để xem lỗi nodriver hết.
- **KNOWN_ISSUED:** SCRAPE-8, 11, 17 đã xóa; SCRAPE-12 đã xóa. Phần Glints (trang 1 API chỉ trả 4 tin ngoài IT nên discovery đăng ký 0 URL) bị bỏ theo quyết định người dùng 11/11, không gọi API thật để xem.

### L-42. Dọn các mục PRE đã xử lý: runner trùng, ghi trùng 04, parse lương, test ngoài testpaths, test hỏng, ADR-04 (11/2026)
- **Lỗi:** các mục PRE-14, 20, 21, 23, 24, 27 còn ghi trong `KNOWN_ISSUED.md` dù code đã đổi.
- **Cách xử lý và bằng chứng (kiểm 11/11):** PRE-20 `preprocessing/integration/run_integration.py` không còn; PRE-21 `preprocessing/transformation/pipeline.py` ghi `data/preprocessing/legacy_features/all.parquet`, không còn đụng `04_normalization`; PRE-23 `parse_salary("tối thiểu 10 triệu")` ra `lower_bound` min 10 max rỗng, `"2 tỷ"` ra 2000 triệu (test ở `test_normalization_step.py`, `test_ph6_ph7_normalization.py`); PRE-24 thư mục `preprocessing/transformation/tests/` không còn file test; PRE-27 xóa `tests/test_golden_field_preservation.py` (import module không tồn tại); PRE-14 thêm ghi chú 11/11 vào ADR-04 (`docs/spec/11_technical_decisions.md`).
- **KNOWN_ISSUED:** sáu mục đã xóa.

### L-43. Nhóm nghề mở rộng từ 12 lên 16 nhóm + Other; bỏ Data Engineer; duyệt `job_titles.json` (PH6, 11/2026)
- **Lỗi:** nhóm Other chiếm 38% (1.793/4.699) vì `job_titles.json` chưa duyệt và chưa có nhóm cho các tin "Developer", "Lập Trình", "CNTT", thiết kế, game, CSDL, ERP.
- **Nguyên nhân:** taxonomy cũ (SPEC-01) chỉ có 12 nhóm, không có nhóm cho nhóm tin chung chung.
- **Cách xử lý:** người dùng sửa 53 mục trong `preprocessing/dictionaries/job_titles.json` và chốt 11/11: bỏ Data Engineer (gộp Data Science/AI, kể cả Data Analyst/BI), thêm Software Engineering, Game Development, Design, Database, Enterprise Software. Mình đặt `approved: true` cho 53 mục đó (so với bản đã commit), 87 mục còn lại `false` nên không nạp. `JOB_FAMILIES_12` đổi tên thành `JOB_FAMILIES` (16 nhóm) ở 6 file; luật tiêu đề và kỹ năng cổng của Data Engineer gộp vào Data Science/AI. Spec PH6, P4, SPEC-01 ghi chú ngày 11/11.
- **Kiểm chứng:** `test_job_titles_json_families_are_known` (mục duyệt phải có nhóm hợp lệ) và `test_normalization_step.py` 36 qua; sau chạy lại 04: Other 707/4.671 (15,1%), trước 1.793/4.699 (38%); nhóm lớn nhất Software Engineering 938, Fullstack 608, Product/Project 517.
- **KNOWN_ISSUED:** PRE-34 bỏ dòng "Other 38%" khi có số mới.

### L-44. Thêm bước 10–12 (10_features, 12_tfidf) vào chuỗi và đóng encoding bước 05 (Processing, 11/2026)
- **Lỗi:** chưa có ma trận đặc trưng số cho Mining; bước 05 encoding cũ (`preprocessing/encoding/execute.py`) cần 7 tham số xuất bản nên bị `SKIPPED` trong chuỗi (PRE-32).
- **Cách xử lý:** `processing/transformation/discretize.py`, `construction/features.py`, `encoding/features.py` (gộp 10, 10b, 10c, 10d), `extraction/vectorize.py` (12); nối vào `scripts/run_preprocessing.py`. Lương thỏa thuận và không ghi thành `salary_status__unknown` (không điền). `min_df=15`. Bước 11 bỏ, e5 làm sau.
- **Kiểm chứng (chạy thật 11/11):** `10_features` 4.671 → 4.671 dòng, 249 cột sau khi làm đủ E1–E5, E7 của P5 (171 cột kỹ năng, mật độ 4,1%, 292 tin không có kỹ năng; `emp__unknown` 317 tin, `tinh__unknown` 102 tin); lương có số 2.140, unknown 2.531; cấp bậc chưa rõ 388, cờ mâu thuẫn 115. `12_tfidf` ma trận 4.671 × 20.000, 1.205.812 phần tử khác 0. `tests/unit tests/contract` qua (xem dòng kết quả cuối phiên); `tests/unit/test_processing_10_12.py` 5 test.
- **KNOWN_ISSUED:** PRE-32 đã xóa; PRE-34 còn phần đánh giá và e5.

### L-45. Thêm bước 12_e5: embedding bullet bằng multilingual-e5-base (Processing, 11/2026)
- **Lỗi:** Processing chưa có biểu diễn ngữ nghĩa của JD, chỉ có TF-IDF.
- **Cách xử lý:** `processing/extraction/embed.py` (bước `12_e5`, nối vào `scripts/run_preprocessing.py`): vector từng bullet (tiền tố `passage: `, fp16, GPU), cache theo `sha1(text)`; vector JD = trung bình mọi bullet + trung bình theo 3 section. `sentence-transformers==6.2.0` ghim vào `requirements.txt`.
- **Kiểm chứng (chạy thật, xong 04:13 ngày 11/11):** `bullet_emb.npy` 114.008 × 768 (fp16), `job_emb.npz` 4.671 JD (không JD nào có vector 0), thứ tự bullet khớp `07_sections`; `tests/unit tests/contract`: 580 qua, 1 bỏ qua; `test_embed.py` 3 test.
- **Còn lại:** phân loại bullet zero-shot chưa làm (không có nhãn vàng để đo); PRE-34.

### L-46. Mining đọc đúng đầu ra Processing và dùng vector e5 (Mining, 11/2026)
- **Lỗi:** `mining/config.py` trỏ `data/preprocessing/05_encoding/features.parquet` (không còn); cột `skill__other_skill` bị tính là kỹ năng thật.
- **Cách xử lý:** trỏ sang `data/processing/10_features/` và `12_e5/job_emb.npz`; `SKILL_EXCLUDE_COLUMNS` thêm `skill__other_skill`; `load_e5` (thiếu job thì báo lỗi, không bịa vector); `build_vector_space` thêm khối e5 (`e5_weight=0.3`); k quét 5–12; driver in so sánh có/không e5; `scripts/plot_clusters_3d.py` vẽ HTML 3D từ `job_clusters.parquet`.
- **Kiểm chứng (chạy thật 11/11, `--only fp,cluster,anomaly`, 4.671 tin, bước `salary` RF+SHAP không chạy vì là supervised):** K-Means k=11, Silhouette 0,0912 (không e5: 0,0862, k=12), Davies-Bouldin 2,63, ARI với nhóm nghề 0,056; PCA 3D giữ 20,5% phương sai; 29.193 luật (26 vĩ mô); 279 tin bất thường (5,97%). Kiểm tra hợp lý: 4/6 mục fail (xem MINE-1). Test mới trong `test_mining_clustering.py`, `test_mining_data_io.py`, `test_plot_clusters_3d.py`.
- **Còn lại:** cụm yếu so với mục tiêu (Silhouette ≥ 0,28; DB < 1,80); MINE-1.

### L-47. Nhóm nghề gộp từ 16 xuống 10 nhóm + Other; Mining K-Means k=10 (PH6, Mining, 11/2026)
- **Lỗi:** 16 nhóm (L-43) chia sai: "Software" thực chất gồm backend, frontend, fullstack; các nhóm nhỏ (Mobile 30, Database 15, Enterprise 16) quá ít tin.
- **Cách xử lý:** người dùng chốt 10 nhóm: Web, Mobile, Game, Bridge, DevOps/Cloud, Tester, Security, IoT, Design, Data/AI (+ Other, không ép tin vào nhóm). `FAMILY_MAP` trong `preprocessing/normalization/job_title.py` gộp nhóm cũ về 10 nhóm ở đầu ra `family_from_title` (Backend/Frontend/Fullstack/Software Engineering → Web; Product/Project, Enterprise Software → Bridge; QA/QC → Tester; Security, System/Network → Security; Embedded/IoT → IoT; Data Science/AI, Database → Data/AI); `job_titles.json` cập nhật theo bảng (140 mục, `approved` giữ nguyên 53). Tên đổi (Tester, IoT, Data/AI, Bridge) là theo cách người dùng viết. Mining: `ClusteringParams` k cố định 10, K-Means, không gian kỹ năng .5 + e5 .5 (bỏ TF-IDF), quét k=2–20 để báo Elbow/Silhouette; ARI/NMI chỉ tính trên tin khác Other.
- **Kiểm chứng (chạy thật 11/11):** `04_normalization` 4.671 → 4.671: Web 1.853, Other 707, Bridge 533, Data/AI 430, Tester 429, DevOps/Cloud 258, Security 254, Design 78, Game 61, IoT 38, Mobile 30; `10_features` 4.671 × 243 (11 cột `fam__*`). Mining k=10: Silhouette 0,1015, Davies-Bouldin 2,49, ARI 0,071 và NMI 0,144 trên 3.964 tin khác Other; không dùng e5: Silhouette 0,1055, ARI 0,096; 13.514 luật; 282 tin bất thường (6,04%). Test: `test_family_map_covers_old_families_and_targets_ten_groups`, `test_fixed_k_overrides_selection_and_scan_still_reported`, `test_family_agreement_ignores_other`.
- **Còn lại:** Web 40% có thể lẫn tin Software Engineer chung không phải web; Security gồm cả hạ tầng/mạng; cụm 1 chứa 292/293 tin không có kỹ năng và cụm 9 là cụm nhiều kỹ năng (trung vị 15), tức phân cụm một phần tách theo số kỹ năng (MINE-1).

### L-48. Khoảng k của phân cụm chưa thống nhất giữa task, checklist, spec và code (MINE-4, Mining, 17/11/2026)
- **Lỗi:** task ghi k = 6–12, checklist 4–14, spec 07 cũ 3–15, code dùng 4–14; không có giá trị nào được chốt.
- **Nguyên nhân:** mỗi tài liệu được viết ở một thời điểm, không có nguồn chung; `ClusteringParams` trong `mining/config.py` không được đối chiếu lại.
- **Cách xử lý:** người dùng đã chốt ở L-47 (11/11) và xác nhận đóng ngày 17/11: K-Means `k_fixed` = 10; vẫn quét k = 2–20 (`k_min`, `k_max`) để báo Elbow và Silhouette. Spec 07 v3.0.0 mục 3.3 ghi đúng các giá trị này; các tài liệu task và checklist cũ không còn là nguồn.
- **Còn lại:** đo độ ổn định qua 5 seed và kiểm cụm có tách theo số kỹ năng hay không (MINE-1, MINE-7).
- **Kiểm chứng:** `mining/config.py` dòng 110–112; `tests/unit/test_mining_clustering.py::test_fixed_k_overrides_selection_and_scan_still_reported`.
