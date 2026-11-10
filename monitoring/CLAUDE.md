# monitoring/CLAUDE.md

Ngữ cảnh khi làm việc với Monitoring. **`.agents/rules/monitoring_system_rules.md` là bắt buộc**; file này chỉ ghi phần không tự đọc ra được từ code và các lỗi đã gặp. Cách chạy: `monitoring/README.md`.

## Cấu trúc

- Backend FastAPI `backend/app`: `api/v1/endpoints` → `services` → đọc `data/`, `reports/`, R2, Airflow. Cấu hình và đường dẫn ở `core/config.py`, `core/data_paths.py`.
- Frontend React/TypeScript `frontend/src`: trang ở `pages/`, component theo trang ở `components/<trang>/`, mọi type ở `types.ts`, gọi API ở `api/`.
- Trang chính là Collection (`/`) và Raw (`/raw`), cùng dùng `/api/v1/monitor` (`collection_monitor_service.py`, `source_report_service.py`).
- Thao tác vận hành nằm ở `/crawling`; biểu đồ phân tích nằm ở `/eda`. Không trộn hai loại này.
- EDA, Pre-processing, Processing, Master Dashboard đọc kết quả pipeline trong `reports/` và `data/staging/` qua `pipeline_report_service.py`. `reports/` nằm trong git, nên các trang này hiện số của lần chạy pipeline được commit gần nhất.

## Điều cần biết

- **Chỉ hiện số thật.** Thiếu dữ liệu thì service trả `null` kèm lý do, frontend hiện trạng thái trống. Trang ML 3D từng trả số ngẫu nhiên nên đã bị xóa (`docs/issue_log.md` L-19).
- **`core/feature_targets.py` (`RAW_PATHS`) là nguồn chung** cho trang Raw, `scripts/audit_raw_data.py` và contract test (`tests/contract/standards.py`). Sửa đường dẫn ở đây là đổi cả ba. Phải khớp với `preprocessing/integration/json_flattener.py`. Nguồn không hiển thị trường nào thì để danh sách rỗng, không tính vào độ phủ.
- **So sánh máy với R2 theo từng key**, không so hai con số đếm (L-16); trên R2 có thể có file mà máy không có. Diff nội dung dùng `content_hash`, không dùng thời gian.
- **Bấm chạy crawler trên trang Crawling là cào thật.** `crawler_service.trigger_crawler` chạy `run.py` và thêm `--sync-r2` khi ô "Đồng bộ R2" được chọn (mặc định có, L-17). Kiểm thử trang này thì không bấm chạy, trừ khi người dùng đồng ý.
- Đọc chuỗi kinh nghiệm dạng khoảng ("1 - 10 Năm") thì lấy cận dưới (L-15).
- Monitoring không bao giờ bật Airflow scheduler.

## Giao diện

- Code mới dùng token `ink`, `line`, `panel`, `brand`, `state`. **Không dùng `slate`:** `tailwind.config.ts` đảo ngược bảng `slate` cho các trang cũ thời nền tối ("Công cụ khác").
- Chỉ TypeScript, không có file `.js`/`.jsx`.
- **Kiểm ở cả 390px và 1440px.** Trang Crawling và Pre-processing từng tràn ngang trên điện thoại (L-18). Hàng nút hoặc bộ lọc dùng `flex-wrap`, ô nhập dùng `w-full sm:w-<n>`, đường dẫn hoặc chuỗi dài dùng `[overflow-wrap:anywhere]`.
- Không có test hay lint cho frontend; `npm run build` (trong `frontend/`) là bước kiểm kiểu.

## Kiểm tra

```bash
./start_monitoring.sh --no-db --no-browser   # FastAPI 127.0.0.1:8000, Vite :5173; log ở logs/monitoring/
pytest tests/integration/test_monitor_endpoints.py tests/integration/test_monitoring_api.py
cd monitoring/frontend && npm run build
```

Kiểm giao diện không cần mở cửa sổ: Playwright chạy ẩn với Chrome của máy (`executable_path="/usr/bin/google-chrome"`, vì Playwright chưa tải trình duyệt riêng). Mở từng trang ở 390px và 1440px, so `document.documentElement.scrollWidth` với bề rộng cửa sổ, và đọc lỗi console.

## Còn mở

`KNOWN_ISSUED.md`: VIZ-3 (các trang báo cáo hiện số pipeline ngày 25/10), VIZ-5 đã được tách thành hook và presenter trong `components/crawling/`, xem nhật ký lỗi.

## Market Insights Mart
- `/insights` đọc PostgreSQL qua `insights_service.py`; bảng rỗng trả `EMPTY/NO_DATA`, lỗi kết nối/schema trả HTTP 503 `MART_UNAVAILABLE` (không lộ thông tin đăng nhập).
- Máy có PostgreSQL riêng có thể trùng cổng 5432. Docker hỗ trợ `POSTGRES_PUBLISHED_PORT`; cấu hình `POSTGRES_PORT` của backend cùng cổng publish (máy Sơn hiện dùng 15432). Không xóa volume để giải quyết xung đột cổng.
- `pca_z` nullable: không thay bằng 0 để tạo điểm 3D. Chỉ điểm có đủ XYZ mới xuất hiện trong chế độ 3D; 2D vẫn giữ điểm XY.
- Lương Mart tính bằng VNĐ/tháng; API trả trung vị/P25/P75 theo triệu VNĐ. Tin thỏa thuận và ngoài 1–500 triệu không tham gia tính lương.

## EDA R2
- Collection (`/`) từ 10/11/2026 dùng `collection_r2_service.py`: list raw JSON và đọc Ledger trên R2, cache 60 giây, không query Airflow/local. Đếm object gồm version, ngày biểu đồ theo phân vùng trong key; LastModified chỉ là lần upload/ghi gần nhất. Không suy ra số tin unique, lịch sử DAG hoặc tỷ lệ chạy thành công từ inventory.
- Phạm vi UI leader chốt ngày 09/11/2026: chỉ Collection, EDA, Pre-processing, Processing. EDA dùng R2 trực tiếp, không phân tích theo ngày; line chart là phân phối lương tích lũy. `eda_exploration_service.py` tính scatter, box/IQR, heatmap và Pearson từ staging; không bù giá trị thiếu hoặc tự xóa ngoại lai. Các báo cáo Pre-processing/Processing vẫn theo API pipeline hiện có.
- Parquet sau Normalization hiện dùng `tinh_chinh` cho tỉnh/thành; EDA ưu tiên cột này và fallback `primary_city` của staging cũ cho dòng còn thiếu. Không dùng địa chỉ raw để giả lập tỉnh/thành đã chuẩn hóa (L-31).
- `/eda` gọi origin=r2 trực tiếp. API vẫn hỗ trợ local để tương thích client cũ; origin=r2 chỉ đọc R2 và không fallback local. Raw lấy tối đa 200 mẫu đầu tiên (không ngẫu nhiên); staging đọc 04_normalization.parquet trên R2 vào RAM, cache 60 giây, mỗi object tối đa 128 MiB. Không lưu cache dữ liệu xuống đĩa.
- Thiếu object và lỗi quyền/kết nối là hai trạng thái khác nhau; không nuốt ClientError thành Empty State. Không ghi exception SDK hoặc credentials vào response.

- EDA raw R2 từ 10/11/2026 quét toàn bộ trong nền (`eda_raw_scan_service.py`), tối đa 2 nguồn đồng thời, gồm mọi version. Không còn cap 200 ở R2; staging đọc riêng, không chờ raw. Chỉ COMPLETE mới có inventory/độ đầy đủ. Cache raw giữ đến quét lại/restart; POST `/api/v1/eda/<source>/scan` quét lại. Local API cũ còn mẫu 200. Điều này thay thế mô tả giới hạn raw trước đó.

- EDA duplicate so payload canonical SHA-256 trong từng nguồn, riêng với object dư theo ID filename; chỉ COMPLETE công bố. Histogram dùng toàn bộ lương số hữu hạn trong staging, kể cả 0/âm, không chặn outlier và 10 bins phủ min–max. Mỗi dòng lấy trung bình cận có số; các phân tích lương khác vẫn chỉ dùng cận dương.

- Khi frontend mới cần field duplicate nhưng summary COMPLETE không có key `duplicates`, kiểm tra backend đã restart để nạp code mới chưa. UI không được biểu diễn trường hợp này thành đang quét; cache COMPLETE thiếu duplicate tự quét lại (L-32).
