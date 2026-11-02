# Báo cáo chất lượng code

Sinh bởi `python scripts/report_code_quality.py` ngày 03/11/2026. Chỉ là danh sách để duyệt: chưa xóa hay gộp gì. Chạy lại bằng `make quality`.

Phạm vi: `collection`, `scripts`, `run.py`, `airflow/plugins`, `airflow/dags`, `monitoring/backend/app`. Không quét `preprocessing/` và `tests/`.

| Bảng | Kiểm tra | Số mục |
|---|---|---|
| A | Import thừa, biến không dùng, khai báo lại (ruff) | 117 |
| B1 | Hàm, method, class không ai gọi (vulture) | 33 |
| B2 | Module không ai import | 3 |
| C | Nhóm hàm trùng logic giữa các file | 2 |
| D | Tên hàm trùng ở nhiều file | 21 |

## A. Import thừa, biến không dùng, khai báo lại

Ruff tự sửa được phần lớn (`ruff check --select F401,F841 --fix`), nhưng import trong `__init__.py` có thể là API công khai, cần xem trước khi xóa.

| File | Số mục | Chi tiết (dòng: nội dung) |
|---|---|---|
| `scripts/run_staging_integration_pipeline.py` | 10 | 21: import thừa os; 24: import thừa collections.Counter; 24: import thừa collections.defaultdict; 27: import thừa typing.Optional; 27: import thừa typing.Set; 29: import thừa numpy; 38: import thừa preprocessing.transformation.salary_parser.UniversalSalaryParser; 40: import thừa preprocessing.missing_outlier.sneaky_null_detector.is_val_null; … và 2 mục nữa |
| `collection/common/r2_raw_pipeline.py` | 6 | 10: import thừa base64; 19: import thừa typing.Iterable; 20: import thừa urllib.parse.urlparse; 27: import thừa collection.common.url_ledger.calculate_container_html_hash; 30: import thừa collection.common.url_ledger.is_due_for_recrawl; 192: biến không dùng head_exc |
| `collection/common/utils.py` | 6 | 17: import thừa hashlib; 23: import thừa urllib.parse.urlparse; 23: import thừa urllib.parse.urlencode; 23: import thừa urllib.parse.parse_qs; 23: import thừa urllib.parse.urlunparse; 211: biến không dùng cleaned |
| `collection/sources/vieclam24h/crawler.py` | 5 | 11: import thừa os; 31: import thừa collection.common.url_ledger.calculate_container_html_hash; 39: import thừa collection.common.utils.parse_salary_detail; 40: import thừa collection.common.utils.strip_html_tags; 890: biến không dùng field_hashes |
| `collection/sources/vietnamworks/crawler.py` | 5 | 48: import thừa collection.common.url_ledger.generate_url_hash; 54: import thừa collection.common.utils.strip_html_tags; 699: biến không dùng consecutive_known_jobs; 700: biến không dùng early_stop_threshold; 950: biến không dùng old_hash |
| `run.py` | 5 | 15: import thừa glob; 16: import thừa datetime.datetime; 16: import thừa datetime.timezone; 16: import thừa datetime.timedelta; 73: biến không dùng crawler_map |
| `collection/common/ip_rotator.py` | 4 | 18: import thừa os; 20: import thừa re; 22: import thừa typing.Tuple; 23: import thừa urllib.parse.urlparse |
| `collection/sources/glints/raw_pipeline.py` | 4 | 9: import thừa random; 10: import thừa re; 11: import thừa time; 13: import thừa urllib.parse.urljoin |
| `collection/sources/topcv/crawler.py` | 4 | 24: import thừa asyncio; 36: import thừa urllib.parse.urlparse; 61: import thừa collection.common.url_ledger.generate_url_hash; 907: biến không dùng nap_sec |
| `scripts/lakehouse_loader.py` | 4 | 29: import thừa glob; 32: import thừa os; 72: import thừa boto3; 73: import thừa botocore.client.Config |
| `collection/sources/careerviet/crawler.py` | 3 | 37: import thừa collection.common.url_ledger.calculate_container_html_hash; 40: import thừa collection.common.url_ledger.diff_json_versions; 46: import thừa collection.common.utils.strip_html_tags |
| `collection/sources/jobsgo/crawler.py` | 3 | 28: import thừa time; 32: import thừa urllib.parse.urlparse; 550: biến không dùng loaded |
| `monitoring/backend/app/api/v1/endpoints/cloud_r2.py` | 3 | 4: import thừa typing.Any; 4: import thừa typing.Dict; 4: import thừa typing.Optional |
| `monitoring/backend/app/api/v1/endpoints/orchestration/airflow.py` | 3 | 4: import thừa typing.Any; 4: import thừa typing.Dict; 4: import thừa typing.List |
| `monitoring/backend/app/services/alert_service.py` | 3 | 8: import thừa json; 11: import thừa pathlib.Path; 15: import thừa app.core.config.settings |
| `airflow/plugins/crawler_operators.py` | 2 | 12: import thừa os; 26: import thừa collection.common.adaptive_router.MAX_ITEMS_PER_BATCH |
| `collection/reports/EDA_glints.ipynb` | 2 | 25: import thừa sklearn.preprocessing.RobustScaler; 25: import thừa sklearn.preprocessing.StandardScaler |
| `collection/reports/EDA_itviec.ipynb` | 2 | 25: import thừa sklearn.preprocessing.RobustScaler; 25: import thừa sklearn.preprocessing.StandardScaler |
| `collection/reports/EDA_jobsgo.ipynb` | 2 | 25: import thừa sklearn.preprocessing.RobustScaler; 25: import thừa sklearn.preprocessing.StandardScaler |
| `collection/reports/EDA_topcv.ipynb` | 2 | 25: import thừa sklearn.preprocessing.RobustScaler; 25: import thừa sklearn.preprocessing.StandardScaler |
| `collection/reports/EDA_topdev.ipynb` | 2 | 25: import thừa sklearn.preprocessing.RobustScaler; 25: import thừa sklearn.preprocessing.StandardScaler |
| `collection/reports/EDA_vieclam24h.ipynb` | 2 | 25: import thừa sklearn.preprocessing.RobustScaler; 25: import thừa sklearn.preprocessing.StandardScaler |
| `collection/reports/EDA_vietnamworks.ipynb` | 2 | 25: import thừa sklearn.preprocessing.RobustScaler; 25: import thừa sklearn.preprocessing.StandardScaler |
| `monitoring/backend/app/api/v1/endpoints/collection/crawling.py` | 2 | 4: import thừa typing.Any; 4: import thừa typing.Dict |
| `monitoring/backend/app/api/v1/endpoints/collection/eda.py` | 2 | 4: import thừa typing.Any; 4: import thừa typing.Dict |
| `monitoring/backend/app/schemas/cloud.py` | 2 | 4: import thừa typing.Any; 4: import thừa typing.List |
| `monitoring/backend/app/services/crawler_service.py` | 2 | 8: import thừa pathlib.Path; 9: import thừa subprocess |
| `monitoring/backend/app/services/ledger_service.py` | 2 | 7: import thừa os; 9: import thừa typing.List |
| `scripts/setup_cloud_storage.py` | 2 | 12: import thừa json; 20: import thừa dotenv.load_dotenv |
| `scripts/sync_cloud_lakehouse.py` | 2 | 17: import thừa boto3; 18: import thừa botocore.client.Config |
| `scripts/view_urls.py` | 2 | 21: import thừa os; 24: import thừa datetime.datetime |
| `collection/base/base_crawler.py` | 1 | 13: import thừa typing.List |
| `collection/common/anti_blocking.py` | 1 | 13: import thừa typing.Optional |
| `collection/common/data_quality.py` | 1 | 19: import thừa collection.common.schema.JobRecord |
| `collection/common/http_client.py` | 1 | 408: biến không dùng ua |
| `collection/common/logger.py` | 1 | 22: import thừa os |
| `collection/reports/EDA_careerviet.ipynb` | 1 | 7: import thừa collections.Counter |
| `collection/sources/glints/crawler.py` | 1 | 1257: biến không dùng remaining |
| `collection/sources/itviec/crawler.py` | 1 | 34: import thừa bs4.BeautifulSoup |
| `collection/sources/topdev/crawler.py` | 1 | 1749: biến không dùng old_hash |
| `monitoring/backend/app/api/v1/endpoints/alerts.py` | 1 | 7: import thừa fastapi.HTTPException |
| `monitoring/backend/app/core/r2_client.py` | 1 | 8: import thừa datetime.datetime |
| `monitoring/backend/app/schemas/crawling.py` | 1 | 4: import thừa typing.Any |
| `monitoring/backend/app/schemas/eda.py` | 1 | 4: import thừa typing.Any |
| `monitoring/backend/app/services/source_report_service.py` | 1 | 4: import thừa collections.Counter |
| `scripts/check_r2.py` | 1 | 38: biến không dùng test_resp |
| `scripts/drain_topcv_loop.py` | 1 | 110: biến không dùng done |
| `scripts/push_integration_to_r2.py` | 1 | 9: import thừa glob |

## B. Code chết

### B1. Hàm, method, class không ai gọi

vulture tìm theo tên trong phạm vi quét, độ tin cậy 60% (hàm luôn ở mức này). Cột "Test dùng" là tên có xuất hiện trong `tests/`: có thì code chỉ còn test gọi. Hàm được gọi qua `getattr`, chuỗi, hay từ notebook thì vulture không thấy, nên phải tìm lại trước khi xóa.

| Vị trí | Loại | Tên | Test dùng |
|---|---|---|---|
| `collection/common/adaptive_router.py:221` | method | `get_state` | không |
| `collection/common/checkpoint.py:151` | method | `update_page` | không |
| `collection/common/checkpoint.py:168` | method | `get_extra` | không |
| `collection/common/checkpoint.py:172` | method | `reset` | có |
| `collection/common/ip_rotator.py:57` | function | `check_proxy_ip` | không |
| `collection/common/ip_rotator.py:73` | class | `ProxyPool` | không |
| `collection/common/ip_rotator.py:103` | method | `has_proxies` | không |
| `collection/common/ip_rotator.py:106` | method | `get_current` | không |
| `collection/common/ip_rotator.py:111` | method | `rotate` | không |
| `collection/common/logger.py:118` | function | `configure_root_logger` | không |
| `collection/common/r2_raw_pipeline.py:231` | method | `put_text` | không |
| `collection/common/r2_raw_pipeline.py:242` | method | `list_keys` | không |
| `collection/common/schema.py:414` | property | `requirements_text` | không |
| `collection/common/schema.py:419` | property | `benefits_text` | không |
| `collection/common/url_ledger.py:225` | function | `diff_json_versions` | không |
| `collection/common/url_ledger.py:466` | method | `is_known` | có |
| `collection/common/url_ledger.py:471` | method | `get_record` | có |
| `collection/sources/careerviet/crawler.py:95` | function | `extract_job_posting_jsonld` | không |
| `collection/sources/careerviet/crawler.py:152` | function | `container_text_for_hash` | không |
| `collection/sources/careerviet/crawler.py:168` | function | `hash_container_text` | không |
| `collection/sources/careerviet/crawler.py:437` | method | `_looks_blocked` | không |
| `collection/sources/glints/crawler.py:1191` | method | `crawl_single_url` | không |
| `collection/sources/itviec/parser.py:75` | function | `sync_mode` | không |
| `collection/sources/itviec/parser.py:81` | function | `local_catalog_count` | không |
| `collection/sources/itviec/parser.py:89` | function | `remote_catalog_count` | không |
| `collection/sources/itviec/parser.py:105` | function | `can_upload_catalog` | không |
| `collection/sources/itviec/parser.py:488` | function | `compute_content_hash` | không |
| `collection/sources/topdev/crawler.py:1060` | method | `crawl` | không |
| `monitoring/backend/app/core/r2_client.py:98` | method | `list_layer_objects` | không |
| `monitoring/backend/app/schemas/cloud.py:18` | class | `R2ObjectItem` | không |
| `monitoring/backend/app/schemas/cloud.py:40` | class | `LocalCloudDiff` | không |
| `monitoring/backend/app/schemas/eda.py:17` | class | `OutlierProfile` | không |
| `monitoring/backend/app/schemas/eda.py:30` | class | `Distribution2D` | không |

### B2. Module không ai import

Không tính entry point (`__init__.py`, `main.py`, file có `if __name__ == "__main__"`, DAG Airflow).

| Module | Chỉ test import |
|---|---|
| `collection/common/ip_rotator.py` | không |
| `collection/common/jsonl_writer.py` | không |
| `scripts/create_golden_master_eda_notebook.py` | không |

## C. Hàm trùng logic giữa các file

Hai hàm cùng nhóm có thân giống hệt nhau sau khi đổi tên biến và tham số (hàm từ 5 dòng). Ứng viên để gộp vào `collection/common/`.

| Nhóm | Số dòng | Các bản |
|---|---|---|
| C1 | 8 | `scripts/audit_raw_data.py:44` `_parse_time`<br>`scripts/reconcile_ledger_from_raw.py:48` `_parse_time` |
| C2 | 5 | `collection/sources/topdev/crawler.py:216` `_clean_text`<br>`collection/sources/vieclam24h/crawler.py:64` `_clean_text` |

## D. Tên hàm trùng ở nhiều file

Hàm cấp module và method private (`_tên`) cùng tên ở từ 2 file. Cùng tên chưa chắc cùng việc: xem bảng C để biết bản nào giống hệt. Method public như `discover_urls` là giao diện chung nên không liệt kê.

| Tên | Số file | Vị trí |
|---|---|---|
| `_get_r2_store` | 7 | `collection/sources/careerviet/crawler.py:327` (CareerVietCrawler)<br>`collection/sources/glints/crawler.py:844` (GlintsCrawler)<br>`collection/sources/itviec/crawler.py:192` (ItviecCrawler)<br>`collection/sources/jobsgo/crawler.py:323` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:399` (TopCVCrawler)<br>`collection/sources/vieclam24h/crawler.py:656` (ViecLam24hCrawler)<br>`collection/sources/vietnamworks/crawler.py:685` (VietnamWorksCrawler) |
| `build_raw_envelope` | 6 | `collection/sources/careerviet/crawler.py:242`<br>`collection/sources/itviec/parser.py:448`<br>`collection/sources/jobsgo/crawler.py:236`<br>`collection/sources/topcv/crawler.py:315`<br>`collection/sources/vieclam24h/crawler.py:334`<br>`collection/sources/vietnamworks/crawler.py:568` |
| `_get_ledger` | 5 | `collection/sources/careerviet/crawler.py:360` (CareerVietCrawler)<br>`collection/sources/itviec/crawler.py:183` (ItviecCrawler)<br>`collection/sources/jobsgo/crawler.py:318` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:394` (TopCVCrawler)<br>`collection/sources/vietnamworks/crawler.py:673` (VietnamWorksCrawler) |
| `build_raw_payload` | 5 | `collection/sources/careerviet/crawler.py:173`<br>`collection/sources/itviec/parser.py:443`<br>`collection/sources/jobsgo/crawler.py:74`<br>`collection/sources/topcv/crawler.py:95`<br>`collection/sources/vieclam24h/crawler.py:84` |
| `extract_job_id` | 4 | `collection/sources/careerviet/crawler.py:274`<br>`collection/sources/itviec/parser.py:35`<br>`collection/sources/jobsgo/crawler.py:66`<br>`collection/sources/topcv/crawler.py:84` |
| `extract_raw_envelope_from_html` | 3 | `collection/sources/glints/crawler.py:705`<br>`collection/sources/topdev/crawler.py:1469`<br>`collection/sources/vietnamworks/crawler.py:598` |
| `_build_session` | 2 | `collection/common/http_client.py:237` (HttpClient)<br>`collection/sources/topdev/crawler.py:155` |
| `_clean_text` | 2 | `collection/sources/topdev/crawler.py:216`<br>`collection/sources/vieclam24h/crawler.py:64` |
| `_fetch_playwright` | 2 | `collection/sources/jobsgo/crawler.py:339` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:602` (TopCVCrawler) |
| `_get_http_client` | 2 | `collection/sources/jobsgo/crawler.py:328` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:404` (TopCVCrawler) |
| `_get_page_content` | 2 | `collection/sources/jobsgo/crawler.py:362` (JobsGoCrawler)<br>`collection/sources/topcv/crawler.py:658` (TopCVCrawler) |
| `_location_text` | 2 | `collection/sources/glints/crawler.py:656`<br>`collection/sources/topdev/crawler.py:652` |
| `_make_record` | 2 | `collection/sources/topdev/crawler.py:676`<br>`collection/sources/vieclam24h/crawler.py:359` |
| `_parse_time` | 2 | `scripts/audit_raw_data.py:44`<br>`scripts/reconcile_ledger_from_raw.py:48` |
| `build_raw_payload_from_api` | 2 | `collection/sources/topdev/crawler.py:1429`<br>`collection/sources/vietnamworks/crawler.py:478` |
| `build_raw_payload_from_html` | 2 | `collection/sources/topdev/crawler.py:1239`<br>`collection/sources/vietnamworks/crawler.py:315` |
| `clean_text` | 2 | `collection/common/utils.py:242`<br>`collection/sources/glints/crawler.py:416` |
| `detect_language` | 2 | `collection/common/utils.py:117`<br>`collection/sources/glints/crawler.py:616` |
| `get_r2_client` | 2 | `collection/common/r2_storage.py:38`<br>`scripts/upload_to_r2.py:59` |
| `is_it_job` | 2 | `collection/sources/glints/crawler.py:190`<br>`collection/sources/vietnamworks/crawler.py:257` |
| `list_sources` | 2 | `monitoring/backend/app/api/v1/endpoints/collection/crawling.py:23`<br>`monitoring/backend/app/api/v1/endpoints/monitor.py:21` |
