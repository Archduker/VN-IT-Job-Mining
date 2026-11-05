# Báo cáo chất lượng code

Sinh bởi `python scripts/report_code_quality.py` ngày 03/11/2026. Chỉ là danh sách để duyệt: chưa xóa hay gộp gì. Chạy lại bằng `make quality`.

Phạm vi: `collection`, `scripts`, `run.py`, `airflow/plugins`, `airflow/dags`, `monitoring/backend/app`. Không quét `preprocessing/` và `tests/`.

| Bảng | Kiểm tra | Số mục |
|---|---|---|
| A | Import thừa, biến không dùng, khai báo lại (ruff) | 10 |
| B1 | Hàm, method, class không ai gọi (vulture) | 17 |
| B2 | Module không ai import | 1 |
| C | Nhóm hàm trùng logic giữa các file | 0 |
| D | Tên hàm trùng ở nhiều file | 18 |

## A. Import thừa, biến không dùng, khai báo lại

Ruff tự sửa được phần lớn (`ruff check --select F401,F841 --fix`), nhưng import trong `__init__.py` có thể là API công khai, cần xem trước khi xóa.

| File | Số mục | Chi tiết (dòng: nội dung) |
|---|---|---|
| `scripts/run_staging_integration_pipeline.py` | 10 | 21: import thừa os; 24: import thừa collections.Counter; 24: import thừa collections.defaultdict; 27: import thừa typing.Optional; 27: import thừa typing.Set; 29: import thừa numpy; 38: import thừa preprocessing.transformation.salary_parser.UniversalSalaryParser; 40: import thừa preprocessing.missing_outlier.sneaky_null_detector.is_val_null; … và 2 mục nữa |

## B. Code chết

### B1. Hàm, method, class không ai gọi

vulture tìm theo tên trong phạm vi quét, độ tin cậy 60% (hàm luôn ở mức này). Cột "Test dùng" là tên có xuất hiện trong `tests/`: có thì code chỉ còn test gọi. Hàm được gọi qua `getattr`, chuỗi, hay từ notebook thì vulture không thấy, nên phải tìm lại trước khi xóa.

| Vị trí | Loại | Tên | Test dùng |
|---|---|---|---|
| `collection/common/adaptive_router.py:221` | method | `get_state` | không |
| `collection/common/checkpoint.py:151` | method | `update_page` | không |
| `collection/common/checkpoint.py:168` | method | `get_extra` | không |
| `collection/common/checkpoint.py:172` | method | `reset` | có |
| `collection/common/logger.py:117` | function | `configure_root_logger` | không |
| `collection/common/r2_raw_pipeline.py:216` | method | `put_text` | không |
| `collection/common/r2_raw_pipeline.py:227` | method | `list_keys` | không |
| `collection/common/schema.py:414` | property | `requirements_text` | không |
| `collection/common/schema.py:419` | property | `benefits_text` | không |
| `collection/common/url_ledger.py:225` | function | `diff_json_versions` | không |
| `collection/common/url_ledger.py:466` | method | `is_known` | có |
| `collection/common/url_ledger.py:471` | method | `get_record` | có |
| `collection/sources/careerviet/crawler.py:92` | function | `_select_container` | không |
| `collection/sources/careerviet/crawler.py:97` | function | `_clean_container` | không |
| `collection/sources/careerviet/crawler.py:103` | function | `_strip_volatile_labels` | không |
| `collection/sources/itviec/parser.py:430` | function | `build_canonical_jsonld` | không |
| `collection/sources/topdev/crawler.py:1057` | method | `crawl` | không |

### B2. Module không ai import

Không tính entry point (`__init__.py`, `main.py`, file có `if __name__ == "__main__"`, DAG Airflow).

| Module | Chỉ test import |
|---|---|
| `scripts/create_golden_master_eda_notebook.py` | không |

## C. Hàm trùng logic giữa các file

Hai hàm cùng nhóm có thân giống hệt nhau sau khi đổi tên biến và tham số (hàm từ 5 dòng). Ứng viên để gộp vào `collection/common/`.

Không có.

## D. Tên hàm trùng ở nhiều file

Hàm cấp module và method private (`_tên`) cùng tên ở từ 2 file. Cùng tên chưa chắc cùng việc: xem bảng C để biết bản nào giống hệt. Method public như `discover_urls` là giao diện chung nên không liệt kê.

| Tên | Số file | Vị trí |
|---|---|---|
| `_get_r2_store` | 7 | `collection/sources/careerviet/crawler.py:278` (CareerVietCrawler)<br>`collection/sources/glints/crawler.py:844` (GlintsCrawler)<br>`collection/sources/itviec/crawler.py:191` (ItviecCrawler)<br>`collection/sources/jobsgo/crawler.py:322` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:397` (TopCVCrawler)<br>`collection/sources/vieclam24h/crawler.py:649` (ViecLam24hCrawler)<br>`collection/sources/vietnamworks/crawler.py:683` (VietnamWorksCrawler) |
| `build_raw_envelope` | 6 | `collection/sources/careerviet/crawler.py:193`<br>`collection/sources/itviec/parser.py:402`<br>`collection/sources/jobsgo/crawler.py:235`<br>`collection/sources/topcv/crawler.py:313`<br>`collection/sources/vieclam24h/crawler.py:327`<br>`collection/sources/vietnamworks/crawler.py:566` |
| `_get_ledger` | 5 | `collection/sources/careerviet/crawler.py:311` (CareerVietCrawler)<br>`collection/sources/itviec/crawler.py:182` (ItviecCrawler)<br>`collection/sources/jobsgo/crawler.py:317` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:392` (TopCVCrawler)<br>`collection/sources/vietnamworks/crawler.py:671` (VietnamWorksCrawler) |
| `build_raw_payload` | 5 | `collection/sources/careerviet/crawler.py:124`<br>`collection/sources/itviec/parser.py:397`<br>`collection/sources/jobsgo/crawler.py:73`<br>`collection/sources/topcv/crawler.py:93`<br>`collection/sources/vieclam24h/crawler.py:77` |
| `extract_job_id` | 4 | `collection/sources/careerviet/crawler.py:225`<br>`collection/sources/itviec/parser.py:32`<br>`collection/sources/jobsgo/crawler.py:65`<br>`collection/sources/topcv/crawler.py:82` |
| `extract_raw_envelope_from_html` | 3 | `collection/sources/glints/crawler.py:705`<br>`collection/sources/topdev/crawler.py:1466`<br>`collection/sources/vietnamworks/crawler.py:596` |
| `_build_session` | 2 | `collection/common/http_client.py:237` (HttpClient)<br>`collection/sources/topdev/crawler.py:156` |
| `_fetch_playwright` | 2 | `collection/sources/jobsgo/crawler.py:338` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:600` (TopCVCrawler) |
| `_get_http_client` | 2 | `collection/sources/jobsgo/crawler.py:327` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:402` (TopCVCrawler) |
| `_get_page_content` | 2 | `collection/sources/jobsgo/crawler.py:361` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:656` (TopCVCrawler) |
| `_location_text` | 2 | `collection/sources/glints/crawler.py:656`<br>`collection/sources/topdev/crawler.py:649` |
| `_make_record` | 2 | `collection/sources/topdev/crawler.py:673`<br>`collection/sources/vieclam24h/crawler.py:352` |
| `build_raw_payload_from_api` | 2 | `collection/sources/topdev/crawler.py:1426`<br>`collection/sources/vietnamworks/crawler.py:476` |
| `build_raw_payload_from_html` | 2 | `collection/sources/topdev/crawler.py:1236`<br>`collection/sources/vietnamworks/crawler.py:313` |
| `clean_text` | 2 | `collection/common/utils.py:239`<br>`collection/sources/glints/crawler.py:416` |
| `detect_language` | 2 | `collection/common/utils.py:115`<br>`collection/sources/glints/crawler.py:616` |
| `is_it_job` | 2 | `collection/sources/glints/crawler.py:190`<br>`collection/sources/vietnamworks/crawler.py:255` |
| `list_sources` | 2 | `monitoring/backend/app/api/v1/endpoints/collection/crawling.py:23`<br>`monitoring/backend/app/api/v1/endpoints/monitor.py:21` |
