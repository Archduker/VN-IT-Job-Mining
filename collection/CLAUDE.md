# collection/CLAUDE.md

Ngữ cảnh khi làm việc với crawler trong `collection/`. Root `CLAUDE.md` có tổng quan dự án; file này ghi những gì không tự đọc ra được từ code, cùng các lỗi đã từng gặp. Nguyên nhân và cách sửa đầy đủ của từng lỗi nằm ở `docs/issue_log.md` (mã L-xx); việc còn mở ở `KNOWN_ISSUED.md`. Script vận hành và nhóm nào ghi lên R2: `scripts/CLAUDE.md`. Cách viết contract test: `tests/CLAUDE.md`.

## Quy trình 2 pha

| Pha | Hàm | Đầu vào | Đầu ra |
|---|---|---|---|
| 1. Discovery | `discover_urls()` | trang danh sách | URL đã làm sạch, ghi vào ledger với trạng thái `PENDING`, chưa có hash |
| 2. Detail | `crawl_details()` | ledger: `PENDING` trước, sau đó `DONE` từ 21 ngày trở lên | file raw `RawJobEnvelope`, ledger chuyển sang `DONE` kèm `content_hash` |

- **URL Ledger là hợp đồng giữa hai pha.** Hai pha không gọi trực tiếp nhau.
- **Ledger trên R2 là nguồn sự thật.** Mỗi lần chạy có bật sync đều theo thứ tự:
  1. Kéo ledger về (`pull_from_r2`).
  2. Cào.
  3. Cứ khoảng 15 tin thì `save_catalog()` rồi `sync_to_r2()`.
  4. Đồng bộ lần cuối khi xong.
- **Raw và ledger phải lên R2 cùng nhau.** Đẩy raw mà không đẩy ledger thì lần chạy sau sẽ cào lại các tin đó, và trang Crawling đếm thiếu ngày. Đây là SCRAPE-4, xảy ra ngày 01–02/11: crawler chạy không bật sync, sau đó raw được đẩy bằng `scripts/push_raw_to_r2.py`, mà script này chỉ đẩy raw.
- Airflow giới hạn 30 tin mỗi batch, 55 phút nghỉ giữa các ca (`common/adaptive_router.py`). Lịch các ca nằm trong `common/detail_schedule.py`. Discovery và Detail của cùng một nguồn dùng chung `pool_<nguồn>` nên không chạy chồng nhau.

## Vòng đời trạng thái trong ledger

`PENDING → DONE → (sau 21 ngày) RECHECK_DUE → DONE …`, cùng hai trạng thái `FAILED` và `CLOSED`.

- **Repost:** nội dung trùng hash với một URL khác. Bản ghi được đánh `DONE` kèm `repost_of_url_hash` và **không sinh file raw**. Đây là thiết kế, không phải lỗi (audit từng báo nhầm 139 tin).
- **Safe Skip:** một URL lỗi thì `mark_failed()` rồi đi tiếp, không bao giờ dừng cả batch.
- `--retry-failed`: chỉ chạy lại các URL `FAILED`.
- Tin bị gỡ hoặc trả 404 thì `mark_closed()`. Không bao giờ hạ trạng thái `CLOSED` về lại.
- Luật merge của `save_catalog()`: bản có `updated_at` mới hơn thắng (`mark_done`, `mark_failed`, `mark_closed` ghi trường này). Bản ghi cũ chưa có `updated_at` thì theo luật cũ: `DONE` thắng, rồi `last_scraped_at` mới hơn thắng. Trước 03/11/2026 chỉ có luật cũ nên FAILED và CLOSED không bao giờ được lưu (cả 8 ledger có 0 FAILED). Đổi trạng thái thì luôn qua các hàm `mark_*`, không gán `status` trực tiếp. `pull_from_r2()` chỉ thay bản ghi trên máy khi bản đó đang `PENDING` mà bản trên R2 đã `DONE`.

## Layout lưu trữ

| Loại | Trên máy | Trên R2 |
|---|---|---|
| Raw | `data/<nguồn>/raw/<YYYY-MM-DD>/<job_id>_v<N>.json` | `raw/<nguồn>/<YYYY-MM-DD>/<job_id>_v<N>.json` |
| Ledger | `data/<nguồn>/url_ledger/catalog_master.json`, `manifests/` | `url_ledger/<nguồn>/...` |

- `common/r2_storage.canonicalize_lakehouse_key` là luật duy nhất cho key. Hàm này từ chối key không có tên nguồn hợp lệ.
- Layout cũ `raw/crawling/<ngày>/<nguồn>/` và `raw/url_ledger/<ngày>/<nguồn>/` được `normalize_legacy_key` chuyển về layout chuẩn.
- Thư mục `_index/`, `_quality/`, `_listing/` trong `raw/` là file phụ, không phải envelope.
- Các file `batch_001.json` và `raw_batch.json` cũ gom nhiều tin và trùng với file từng tin (PRE-8).
- Chỉ dùng Cloudflare R2, kết nối qua `common/r2_storage.get_r2_client()`. Tên "MinIO" đã đổi hết sang R2 ngày 02/11/2026; cờ `--sync-minio` cũ vẫn nhận như alias của `--sync-r2`.

## Envelope và CDC

- `metadata` có `job_id`, `source`, `source_url`, `scraped_at`, `version`, `content_hash`. `raw_payload` giữ nguyên dữ liệu trang hoặc API, không ép kiểu.
- Hash tính bằng `calculate_json_canonical_hash(raw_payload, exclude_keys=["raw_html"])`. Không hash HTML.
- **Không lưu vào raw giá trị đổi theo ngày cào** như "3 ngày trước" hay `refreshed`, vì hash sẽ đổi ở mọi lần cào lại và sinh version mới vô ích. TopDev đã phải bỏ `published.since`.
- **Raw là bất biến.** Sửa cách đọc trường thì sửa ở `preprocessing/`, không sửa file raw đã lưu.

## Lỗi đã gặp theo nguồn

- **TopDev:** pha detail lưu raw từ API chi tiết, nên chỉ có những trường nằm trong `DETAIL_FIELDS`. Ngày 02/11 đã phải thêm `experiences_str`, `job_levels_str`, `published`. Khi thêm một feature mới, kiểm tra cả `DETAIL_FIELDS` chứ không chỉ `LISTING_FIELDS`.
- **TopCV:** engine mặc định là `curl_cffi`; `cloakbrowser` cần license (máy hiện chưa có), thiếu license thì mọi trang đều lỗi.
- **TopCV, JobsGO:** trước 02/11 luôn ghi `_v1`. Giờ mọi crawler quyết định version qua `UrlLedger.next_version(record, hash)`.
- **`get_pending_or_due_records()` đổi tin đến hạn sang `RECHECK_DUE` ngay trong bộ nhớ.** Đừng so `status == "DONE"` để biết tin đã cào; TopDev và VietnamWorks từng vì thế mà ghi version mới cho nội dung không đổi.
- **`run.py` chỉ đồng bộ R2 khi có `--sync-r2`;** Airflow luôn truyền `sync_r2=True`. Trước 02/11 `run_crawler()` không truyền tham số này nên Airflow không đẩy raw lẫn ledger (SCRAPE-4). Glints chạy qua `GlintsRawPipeline`, luôn ghi thẳng R2.
- **ITviec:** không có chốt chặn ghi đè catalog riêng (các hàm cũ không ai gọi đã xóa, `docs/issue_log.md` L-24). Bảo vệ là cơ chế chung của ledger: `ledger_push_decision()` và luật gộp theo `updated_at`.
- **ITviec:** R2 từng có 4 bản ghi test (`job-mot-100` …). Test không được ghi vào `data/` thật hay bucket thật.

## Trường dữ liệu và Monitoring

- Vị trí F1–F8 trong raw của từng nguồn nằm trong `monitoring/backend/app/core/feature_targets.py` (`RAW_PATHS`). Trang Raw và `scripts/audit_raw_data.py` cùng đọc file này.
- Đổi tên trường trong crawler thì phải sửa `RAW_PATHS`, và `preprocessing/integration/json_flattener.py` nếu flattener đọc trường đó.
- Nguồn không có trường trên trang thì để danh sách rỗng, ví dụ F6 của Glints và ITviec.

## Quy tắc an toàn

- **Ghi hoặc xóa trên R2 phải chạy thử trước, và cần người dùng đồng ý.** Các script dùng cờ `--apply` hoặc `--push` cho bước ghi thật.
- Không bật Airflow scheduler, vì scheduler cào và ghi lên R2.
- Cào thử thật chỉ với lượng rất nhỏ: discovery 1 trang, detail 2 tin.
- Cấu hình chỉ nằm trong `.env`. Không in giá trị; muốn so sánh thì so hash.

## Kiểm tra dữ liệu

```bash
python scripts/audit_raw_data.py --r2            # báo cáo reports/data_audit_<ngày>.md (không đưa vào git), chỉ đọc
python scripts/migrate_lakehouse_layout.py --r2  # chạy thử chuyển layout cũ; --apply để chạy thật
python scripts/sync_cloud_lakehouse.py --download
```

Các cột của audit cần đọc kỹ:
- **Ledger chậm hơn raw:** khác 0 nghĩa là có lần chạy chưa đồng bộ ledger.
- **DONE thiếu raw:** đã trừ repost.
- **Raw ngoài ledger.**

## Tiêu chuẩn crawler

Rút ra từ `docs/guides/two_phase_r2_crawler_playbook.md` và `.agents/skills/crawling-architect/SKILL.md`, rồi chốt cùng người dùng ngày 02/11/2026. Khi tài liệu cũ mâu thuẫn với bảng dưới thì bảng dưới thắng.

Các quyết định đã chốt:
- **Nghỉ giữa 2 request:** mặc định 2.0–4.5 giây, ngẫu nhiên. Nguồn hay chặn bot (TopCV) được đặt chậm hơn trong crawler của nguồn đó. JobsGO, VietnamWorks, TopDev hiện còn nhanh hơn chuẩn (SCRAPE-13).
- **Layout R2:** chỉ dùng `raw/<nguồn>/<ngày>/<job_id>_v<N>.json`. Kiểu `dt=YYYY-MM-DD/batch_001.json` trong skill `collection-submission` đã bỏ.
- **Mẫu cho mỗi nguồn:** 3 cặp HTML/JSON + envelope tại `tests/fixtures/<nguồn>/`: tin thường, tin VIP/hot, lương thỏa thuận. Thư mục này thay cho `samples/` mà skill yêu cầu.
- **Độ phủ F1–F8:** mỗi trường có ở **≥ 90%** tin raw. Trường mà nguồn không hiển thị trên trang (`RAW_PATHS` rỗng) thì không tính.
- **Độ tươi:** nguồn nào không có lần cào mới **quá 7 ngày** thì cảnh báo trên Monitoring và audit báo mức cao.
- **Version:** cào lại mà hash đổi thì ghi `_v<N+1>`; hash không đổi thì giữ version và không ghi file mới. Áp dụng cho mọi nguồn (TopCV, JobsGO trước đây luôn ghi `_v1`).
- **Tên gọi:** dùng R2 trong mọi tên hàm, biến, cờ CLI và file. Không dùng "MinIO" nữa.

| # | Tiêu chuẩn |
|---|---|
| C1 | Có `discover_urls` và `crawl_details` |
| C2 | Discovery chỉ ghi `PENDING`, URL đã bỏ `utm_*`, `ref`, `source` |
| C3 | Detail chọn `PENDING` và `RECHECK_DUE`; `--retry-failed` chỉ chọn `FAILED` |
| C4 | Envelope đủ trường `metadata` và `raw_payload` |
| C5 | Hash không đổi khi cào lại cùng nội dung |
| C6 | Repost không sinh file mới |
| C7 | Safe Skip: lỗi một URL không làm dừng batch |
| C8 | Key raw và ledger theo layout chuẩn |
| C9 | Sync ledger thất bại phải được báo, không im lặng |
| C10 | Nghỉ ngẫu nhiên giữa request (`common/anti_blocking.polite_sleep`), không `time.sleep` cố định |
| C11 | Raw có đủ F1–F8 theo `RAW_PATHS`, mỗi trường ≥ 90% |
| C12 | Cào lại: hash đổi thì `_v<N+1>`, không đổi thì không ghi file mới |
| C13 | Có 3 mẫu trong `tests/fixtures/<nguồn>/` và contract test chạy offline |
| C14 | Discovery không lấy được trang danh sách nào thì raise `DiscoveryError` (Airflow báo đỏ); lấy được ít nhất 1 trang là thành công |
