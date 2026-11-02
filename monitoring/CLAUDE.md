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

`KNOWN_ISSUED.md`: VIZ-3 (các trang báo cáo hiện số pipeline ngày 25/10), VIZ-5 (`CrawlingPage.tsx` khoảng 890 dòng, cần tách component).
