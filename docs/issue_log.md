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
- **Cách xử lý:** bước Clean mới (`preprocessing/clean/run.py`, đặc tả `docs/preprocessing/spec/P1_clean.md`) đọc riêng file lô (`preprocessing/common/raw_reader.read_raw`). Luật C2 bỏ tin trong file lô đã có file riêng; tin chỉ có trong file lô (206 tin VietnamWorks) được giữ đến khi cào lại có file riêng. Luật C1 giữ snapshot mới nhất của mỗi `job_id`.
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
  - Chi tiết ở mục 8 của `docs/preprocessing/spec/P2–P4`.
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
- **Kiểm chứng:** tái hiện lỗi từ `notebooks/` bằng namespace mới; sau sửa dùng Python 3.14.4, kernel mới tại `notebooks/`, chạy đủ 6 cells không lỗi và xuất HTML. 72 P5 tests và Ruff pass; 10 artifact tái tạo vào `/tmp` giống bytes canonical. Evidence tại `reports/preprocessing/05_encoding/refactor_2026-11-09/`; xem [report P5](preprocessing/encoding/05_p5_handoff_2026-11-08.md#p5-refactor).
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
