# airflow/CLAUDE.md

Ngữ cảnh khi làm việc với Airflow. Vận hành chi tiết: `docs/guides/03_airflow_guide.md`. Crawler: `collection/CLAUDE.md`.

## Cấu trúc

| File | Nội dung |
|---|---|
| `dags/crawler_dags.py` | `dag_discovery_daily` (05:00) và 8 DAG `crawler_detail_<nguồn>` theo `DETAIL_CRON` |
| `plugins/crawler_operators.py` | `AdaptiveRouteCheckOperator`, `JobCrawlerOperator`, `DataQualityOperator`, `DataPreprocessOperator` |
| `airflow.cfg` | cấu hình; `AIRFLOW_HOME` là thư mục này |

Lịch giờ các ca nằm trong `collection/common/detail_schedule.py`, luật chạy hay bỏ ca nằm trong `collection/common/adaptive_router.py` (tối đa 30 tin mỗi ca, nghỉ 55 phút giữa các ca, ngày thường chỉ chạy ca tối). Hai file này thuộc `collection/` vì Monitoring cũng đọc chúng để vẽ lịch.

## Điều cần biết

- **`run_crawler()` trong `run.py` là API của Airflow.** `JobCrawlerOperator` gọi trực tiếp hàm này với `sync_r2=True`. Đổi chữ ký hàm thì sửa cả operator; `tests/integration/test_ledger_sync.py::test_airflow_operator_always_syncs_r2` sẽ báo nếu operator không còn bật sync.
- Trước 02/11/2026 operator không truyền `sync_r2`, nên Airflow không đẩy raw lẫn ledger lên R2 (`docs/issue_log.md` L-01).
- Task fail khi đồng bộ ledger cuối pha thất bại (`LedgerSyncError`) hoặc discovery không tải được trang nào (`DiscoveryError`, mới áp dụng cho TopCV). Đây là chủ ý, để lỗi hiện đỏ thay vì bị nuốt.
- Discovery và detail của cùng nguồn dùng chung `pool_<nguồn>` (1 slot), nên hai pha không bao giờ chạy chồng nhau trên cùng ledger.
- Quota động: route check đẩy `dynamic_max_items` qua XCom, task crawl đọc lại.
- `DataPreprocessOperator` là bộ làm sạch nhẹ riêng, ghi `data/<nguồn>/staging/<ngày>/`. Nó **không** dùng `preprocessing/`, và bộ dữ liệu golden không bao giờ đến từ Airflow.
- Airflow chạy trên PostgreSQL (`make db-up`, docker). Mục "airflow.db" trong `.agents/rules/monitoring_system_rules.md` đã cũ.
- Airflow cài bằng `scripts/setup_airflow.sh`, không có trong `requirements.txt`.

## Quy tắc an toàn

- **Không bật scheduler** (`make airflow-scheduler`, `scripts/start_airflow.sh`) khi người dùng chưa đồng ý: scheduler cào thật và ghi lên R2.
- Kiểm DAG không cần scheduler: `python -c "from airflow.models import DagBag; print(DagBag('airflow/dags').import_errors)"`.
- Chạy thử một task: `airflow tasks test <dag_id> <task_id> <ngày>`. Task crawl vẫn cào thật, nên chỉ dùng với lượng nhỏ.

## Còn mở

SCRAPE-1 trong `KNOWN_ISSUED.md`: chưa kiểm với Airflow thật vì user chưa có quyền docker (`sudo usermod -aG docker $USER`).
