# Known Issues

Danh sách việc còn tồn đọng, cập nhật ngày 02/11/2026 trên nhánh `fix/known-issues-p1`. Xử lý xong mục nào thì xóa mục đó, chi tiết để trong commit.

Thứ tự làm của dự án: **web scraping → trực quan hóa dữ liệu → pre-processing**. Phần pre-processing để sau, chưa sửa.

## 1. Web scraping

**SCRAPE-1. Chưa kiểm tra với R2 và Airflow thật**

- Phạm vi: trạng thái Phase 1 đọc từ `task_instance`, trạng thái Phase 2 đọc từ `dag_run` (`monitoring/backend/app/services/airflow_service.py`), đọc mẫu raw từ R2, hai thẻ R2 và Airflow trên header.
- Hiện trạng: mới test bằng dữ liệu giả lập. `.env` đang trống nên chưa kết nối được.
- Cách xử lý: điền khóa R2 và kết nối PostgreSQL của Airflow vào `.env`, rồi mở lại trang Crawling.

**SCRAPE-2. Máy này chỉ có raw của VietnamWorks**

- Ảnh hưởng: trang Collection, Raw và EDA hiện trống ở 7 nguồn còn lại.
- Cách xử lý: sau SCRAPE-1, chạy `python scripts/sync_cloud_lakehouse.py --download`. Lệnh này chỉ tải về, không ghi lên R2.

## 2. Trực quan hóa dữ liệu

**VIZ-1. Chưa xem trên trình duyệt các trang vừa dựng lại**

- Phạm vi: EDA, Pre-processing, Processing, Master Dashboard và bảng lịch trên trang Crawling. Đã qua build và test API, chưa mở bằng Chrome vì extension chưa kết nối.

**VIZ-2. Chưa kiểm tra giao diện ở 390px**

- Phạm vi: mọi trang. Mới kiểm tra trên Chrome desktop.

**VIZ-3. Các trang báo cáo đang hiện số của lần chạy pipeline ngày 25/10**

- Vị trí: `reports/` trong git, đọc qua `monitoring/backend/app/services/pipeline_report_service.py`
- Ảnh hưởng: số là thật, nhưng mang các lỗi của pre-processing cũ (xem mục 3). Mỗi trang có ghi giờ chạy pipeline.
- Cách xử lý: tự hết khi làm xong mục 3 và chạy lại pipeline.

**VIZ-4. Trang ML 3D đã ẩn nhưng code còn**

- Vị trí: `monitoring/frontend/src/pages/MLMining3DPage.tsx`, `monitoring/backend/app/services/ml_spatial_3d_service.py`
- Ảnh hưởng: endpoint `/api/v1/mining/spatial-3d` vẫn trả tọa độ ngẫu nhiên.
- Cách xử lý: xóa hẳn, hoặc nối với bước mining thật khi có.

**VIZ-5. `CrawlingPage.tsx` quá dài**

- Vị trí: `monitoring/frontend/src/pages/CrawlingPage.tsx` (khoảng 890 dòng)
- Cách xử lý: tách thành các component trong `components/`.

## 3. Pre-processing (để sau)

Code sửa cho PRE-1 và PRE-2 đã viết xong và có test, đang cất trong git stash "preprocessing: so khớp theo từ + chuẩn hóa sau imputer (hoãn)". Lấy lại bằng `git stash list` rồi `git stash apply stash@{N}`.

**PRE-1. Phân loại theo chuỗi con làm sai nhóm nghề, cấp bậc, thành phố**

- Vị trí: `classify_job_family`, `normalize_seniority`, `normalize_city` trong `preprocessing/normalization/text_cleaner.py`; heuristic trong `preprocessing/missing_outlier/genai_text_imputer.py`
- Ảnh hưởng: "ba" khớp trong "backend", "soc" khớp trong "associate", "intern" khớp trong "international". Bộ golden có 1.214 tin BA/Product, phần lớn là xếp sai.
- Cách xử lý: so khớp theo từ nguyên vẹn (có trong stash).

**PRE-2. Chuẩn hóa chạy trước imputer**

- Vị trí: `scripts/run_staging_integration_pipeline.py`
- Ảnh hưởng: nhóm nghề, thành phố, cấp bậc được tính trước khi imputer bù giá trị, nên giá trị bù không được dùng. Từ commit `a87b2c1`, CareerViet và JobsGO để `skills_list` rỗng cho imputer bù, nên nhóm nghề của hai nguồn này chỉ còn dựa vào title.
- Cách xử lý: chuẩn hóa sau imputer (có trong stash).

**PRE-3. Tên thành phố không dấu chưa được gộp**

- Vị trí: `normalize_city`
- Ảnh hưởng: có cả "Hà Nội" (2.111) và "Ha Noi" (509), "Hồ Chí Minh" (1.741) và "Ho Chi Minh" (351).
- Cách xử lý: bỏ dấu trước khi so khớp.

**PRE-4. Dữ liệu đã xử lý cần chạy lại**

- Vị trí: `data/staging/`, `data/curated/` trên R2, `reports/` trong git
- Ảnh hưởng: chưa phản ánh phần làm phẳng đã sửa ở commit `a87b2c1` (CareerViet, JobsGO, TopDev), cũng như PRE-1 đến PRE-3.
- Cách xử lý: làm PRE-1 đến PRE-3, chạy `python scripts/run_staging_integration_pipeline.py`, so số trước và sau, rồi mới đẩy lên R2.

**PRE-5. Test phụ thuộc vào `data/` trên máy**

- Vị trí: `tests/test_integration_step.py` (2 test), `tests/test_monitoring_api.py` (`test_crawling_enum_summary`), `tests/test_preprocessing_pipeline.py` (`test_flatten_sources_samples`)
- Ảnh hưởng: 3 test fail khi thiếu `data/`; `test_flatten_sources_samples` qua mà không kiểm tra gì.
- Cách xử lý: dùng fixture nhỏ trong `tests/`, hoặc đánh dấu skip có ghi lý do.

## 4. Chung

**GEN-1. Khoảng 1.300 lỗi ruff tồn đọng** ở `collection/` và `tests/`. Dọn thành một lượt riêng.

**GEN-2. `README.md` và `TASKS.md` lệch code.** Chi tiết ở mục "Known mismatches" trong `CLAUDE.md`.
