# Known Issues

Danh sách việc còn tồn đọng, đối chiếu với code ở commit `b7d6af3` (02/11/2026). Xử lý xong mục nào thì xóa mục đó, chi tiết để trong commit.

Mức ưu tiên:

- **P1:** sai dữ liệu, hoặc giao diện hiện sai.
- **P3:** chưa kiểm chứng, dọn dẹp.

## P1: Sai dữ liệu hoặc hiện sai

**DATA-4. Dữ liệu đã xử lý vẫn theo logic làm phẳng cũ**

- Vị trí: `data/staging/`, `data/curated/`, `reports/integration/`
- Ảnh hưởng: `json_flattener.py` đã sửa cho CareerViet, JobsGO và TopDev, nhưng file đã tạo trước đó vẫn chứa kỹ năng sai và thiếu kinh nghiệm, cấp bậc của TopDev.
- Cách xử lý: tải raw về, chạy lại `python scripts/run_staging_integration_pipeline.py`, rồi đẩy kết quả lên R2. Không có API key thì kỹ năng được quét bằng heuristic.

**DATA-5. Nhóm nghề của CareerViet và JobsGO giờ chỉ dựa vào title**

- Vị trí: `scripts/run_staging_integration_pipeline.py:147`
- Ảnh hưởng: `classify_job_family` chạy trước imputer, lúc `skills_list` của hai nguồn này đang rỗng. Tin có title chung chung dễ bị xếp sai nhóm hơn.
- Cách xử lý: phân loại lại sau khi imputer đã bù kỹ năng. Cần xem lại ranh giới bước trong `docs/preprocessing/00_architecture_overview.md` trước khi đổi.

**CRAWL-5. Bảng lịch tuần chưa khớp vận hành thật**

- Vị trí: `monitoring/backend/app/services/crawler_service.py`, `get_weekly_crawl_schedule`
- Ảnh hưởng: bảng gán mỗi nguồn vào một thứ trong tuần kèm quota gõ cứng, trong khi DAG của cả 8 nguồn chạy hằng ngày. Trạng thái Phase 2 hiện `SUCCESS` khi hết `PENDING`, không phải theo lần chạy Airflow.
- Cách xử lý: đối chiếu với `collection/common/adaptive_router.py`, rồi lấy trạng thái Phase 2 từ `dag_run`.

**UI-1. Năm trang còn số mẫu**

- Vị trí: EDA, Pre-processing, Processing, Master Dashboard, ML 3D, banner gắn ở `monitoring/frontend/src/App.tsx`
- Ảnh hưởng: các trang đã có nhãn "Số liệu mẫu", nhưng chưa dùng để xem dữ liệu thật được.
- Cách xử lý: nối từng trang với dữ liệu thật, hoặc ẩn trang chưa cần.

## P3: Chưa kiểm chứng và dọn dẹp

**VERIFY-1. Chưa kiểm tra giao diện ở 390px**

- Phạm vi: trang Collection và Raw. Mới kiểm tra trên Chrome desktop.

**VERIFY-2. Chưa kiểm tra phần kết nối thật**

- Phạm vi: đọc mẫu raw từ R2 (`monitoring/backend/app/services/source_report_service.py`), hai thẻ R2 và Airflow trên header khi đang kết nối, trạng thái Phase 1 đọc từ `task_instance` của Airflow.

**VERIFY-3. Chưa xem hai trang mới với dữ liệu thật đủ 8 nguồn**

- Phạm vi: đã thử bằng dữ liệu giả lập. Máy này chỉ có `data/vietnamworks`.
- Cách xử lý: chạy `python scripts/sync_cloud_lakehouse.py --download` rồi xem lại.

**TEST-1. Test phụ thuộc vào `data/` trên máy**

- Vị trí: `tests/test_integration_step.py` (2 test), `tests/test_monitoring_api.py:149`, `tests/test_preprocessing_pipeline.py:26`
- Ảnh hưởng: 3 test ở hai file đầu fail khi thiếu `data/`. Còn `test_flatten_sources_samples` vẫn qua mà không kiểm tra gì trong trường hợp đó.
- Cách xử lý: dùng fixture nhỏ trong `tests/`, hoặc đánh dấu skip có ghi lý do.

**CLEAN-1. `CrawlingPage.tsx` quá dài**

- Vị trí: `monitoring/frontend/src/pages/CrawlingPage.tsx` (880 dòng)
- Cách xử lý: tách thành các component trong `components/`, nên làm cùng CRAWL-5.

**CLEAN-2. Khoảng 1.300 lỗi ruff tồn đọng**

- Phạm vi: `collection/`, `tests/`
- Cách xử lý: dọn thành một lượt riêng, không trộn với thay đổi tính năng.

**DOCS-1. `README.md` và `TASKS.md` lệch code**

- Chi tiết: mục "Known mismatches" trong `CLAUDE.md`.
- Cách xử lý: cập nhật hai file này theo code hiện tại.
