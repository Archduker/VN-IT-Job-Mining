# scripts/CLAUDE.md

Script vận hành và tiện ích. Trước khi chạy script nào, xem nó thuộc nhóm nào dưới đây. **Ghi hoặc xóa trên R2 phải chạy thử trước, gửi số liệu cho người dùng, và chỉ chạy thật khi người dùng đồng ý.**

## Chỉ đọc (chạy thoải mái)

| Script | Việc |
|---|---|
| `audit_raw_data.py [--r2]` | Báo cáo chất lượng raw và ledger ra `reports/data_audit_<ngày>.md` (không đưa vào git). Đọc kỹ cột "Ledger chậm hơn raw", "DONE thiếu raw" (đã trừ repost), "Raw ngoài ledger" |
| `report_data_issues.py` | Thống kê vấn đề dữ liệu raw sau làm phẳng (trùng lặp, độ phủ trường, lương, ngày…), ghi `docs/spec/preprocessing/data_issues_2026-11-03.html`. `compute()` trả dict để Monitoring dùng lại |
| `report_raw_problems_r2.py [--from-json]` | Đo vấn đề dữ liệu raw **trực tiếp trên R2** (chỉ `list_objects_v2` và `get_object`), ghi `docs/presentation/raw_problems_r2.json` và bộ slide `slides_raw_problems.html` (mục A vấn đề raw, mục B cách xử lý). `--from-json` dựng lại slide mà không gọi R2 |
| `read_eda_diagnosis.py --source <nguồn>` | Đọc luật EDA từ notebook mà không mở notebook |
| `view_urls.py [--r2] [--status]` | Xem ledger trên máy hoặc trên R2 |
| `sync_cloud_lakehouse.py --status` | So máy với R2 |
| `sync_cloud_lakehouse.py --download [--source]` | Tải R2 về `data/` (chỉ ghi trên máy) |
| `lakehouse_loader.py` | Nạp raw thành DataFrame, có thể tải bù từ R2 |
| `migrate_lakehouse_layout.py [--r2]` | Không có `--apply` thì chỉ liệt kê key layout cũ sẽ được chuyển |
| `reconcile_ledger_from_raw.py --source <nguồn>` | Không có `--apply`/`--push` thì chỉ in kế hoạch |

## Ghi trên máy

| Script | Việc |
|---|---|
| `reconcile_ledger_from_raw.py --apply` | Dựng lại ledger từ raw: tạo bản ghi thiếu, cập nhật bản ghi có raw mới hơn. Không hạ `CLOSED`, không xóa bản ghi; repost cũ có snapshot mới thì bỏ `repost_of_url_hash` |
| `label_tool.py [--source] [--web] [--stats] [--auto-obvious] [--generate-policy]` | Tool gán nhãn tay cho review C4b (`data/preprocessing/review/it_<nguồn>.csv`), hỗ trợ TUI 1 phím bấm và Web UI nhanh |
| `run_preprocessing.py --step <bước>\|all --source <nguồn>\|all [--dry-run]` | Pipeline pre-processing 5 bước (`docs/spec/preprocessing/spec/`). Ghi `data/preprocessing/<bước>/`, `reports/preprocessing/<bước>/` (Monitoring đọc), mẫu gán nhãn `data/preprocessing/review/`. Không gọi model: phân loại là luật if-else. Từ bước 02 dữ liệu gộp 8 nguồn trong một file `all.parquet` |
| `run_staging_integration_pipeline.py` | Chạy cả pipeline pre-processing, ghi `data/staging/`, `data/curated/`, `reports/<nguồn>/` (thuộc phần pre-processing, đang để sau) |
| `create_golden_master_eda_notebook.py` | Sinh notebook EDA cho bộ golden |
| `build_slides.py [--save-before <parquet>]` | Sinh slide thuyết trình `docs/presentation/slides.html` từ báo cáo 5 bước, `docs/presentation/data/*.json` (số trước sửa) và `compute()` của `report_data_issues.py`. Dừng nếu bảng vấn đề ↔ luật (`ISSUE_TO_RULES`) lệch với luật trong báo cáo. Chạy lại sau mỗi lần chạy pipeline |

## Ghi hoặc xóa trên R2 (phải chạy thử và được đồng ý)

| Script | Chạy thử | Việc |
|---|---|---|
| `push_raw_to_r2.py` | `--dry-run` | Đẩy raw trên máy lên R2, rồi đẩy ledger qua `ledger_push_decision()` (từ chối khi catalog trên máy rỗng, bản R2 mới hơn, hoặc R2 có URL mà máy không có) |
| `reconcile_ledger_from_raw.py --push` | chạy không cờ | Ghi trên máy, sao lưu bản R2 vào `data/<nguồn>/url_ledger/backups/`, rồi đẩy |
| `reconcile_ledger_from_raw.py --source <nguồn> --register-batch-missing <file batch> --push` | bỏ `--push` | Kéo ledger từ R2, đăng ký `PENDING` cho tin trong file batch cũ chưa có file riêng và chưa có trong ledger, sao lưu rồi đẩy. Chạy thử xong thì `--push` thẳng: chạy `--apply` trước thì lần `--push` sau không còn gì để đẩy |
| `migrate_lakehouse_layout.py --r2 --apply` | bỏ `--apply` | Chép key layout cũ sang layout chuẩn, **xóa** key cũ |
| `sync_cloud_lakehouse.py --upload` | `--status` | Đẩy cả `data/` (gồm staging, curated) |
| `push_integration_to_r2.py` | — | Đẩy kết quả integration |
| `push_preprocessing_to_r2.py --push` | chạy không cờ | Đẩy output pipeline 5 bước: `staging/<nguồn>/preprocessing/<bước>.*` (bảng gộp tách theo nguồn) và `curated/preprocessing/`. R2 chỉ có 5 tiền tố; `pipeline/` chưa có object (chốt 10/11/2026). Chỉ đẩy key chưa có hoặc lệch (so `generated-at` và số dòng trong metadata). Bố cục: `preprocessing/common/r2_export.py` |
| `check_r2.py` (`make check-r2`) | — | Ghi rồi xóa ngay một key thử để kiểm quyền |
| `setup_cloud_storage.py` | — | Ghi khóa R2 vào `.env`, tạo bucket nếu chưa có |

## Cào thật (cần người dùng đồng ý)

- `drain_topcv_loop.py`: vòng lặp chạy nền, cứ 20 phút cào 30 tin TopCV và đẩy lên R2. Không chạy khi chưa được yêu cầu.
- `start_airflow.sh`, `airflow_ctl.sh`: bật scheduler, tức là cào thật. Xem `airflow/CLAUDE.md`.
- `setup_airflow.sh`, `setup_airflow_connections.py`, `setup_ec2.sh`: cài đặt môi trường.

## Lưu ý khi viết script mới

- Kết nối R2 qua `collection.common.r2_storage.get_r2_client()` và `resolve_r2_bucket()`. Không tự tạo `boto3.client` hay đọc biến môi trường riêng (ngoại lệ duy nhất: `setup_cloud_storage.py` thử khóa người dùng vừa nhập): ledger từng đọc khóa theo thứ tự khác với raw nên đẩy sai chỗ (`docs/issue_log.md` L-01).
- Key R2 đi qua `canonicalize_lakehouse_key`.
- Bước ghi thật đặt sau cờ `--apply` hoặc `--push`; mặc định là chạy thử.
- Không in giá trị trong `.env`; muốn so hai khóa thì so hash.
- Test script ở `tests/integration/`, dữ liệu trong `tmp_path`, R2 thì mock.
