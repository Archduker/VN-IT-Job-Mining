# Hướng Dẫn Cài Đặt & Vận Hành Apache Airflow (VN-IT-Job-Mining)

## 1. Yêu Cầu Môi Trường
- Python 3.12+ (khuyến nghị qua `.venv`)
- SQLite 3 (đi kèm mặc định theo Python)
- Google Chrome (phục vụ headless crawl)

## 2. Cài Đặt Nhanh
Khởi tạo database và cấu hình Airflow:
```bash
# Set thư mục AIRFLOW_HOME và PYTHONPATH
export AIRFLOW_HOME=$(pwd)/airflow
export PYTHONPATH=.:$(pwd)/airflow/plugins

# Khởi tạo database SQLite
airflow db init
```

## 3. Kiểm Tra DAGs
```bash
airflow dags list | grep crawler
```
Output mong đợi gồm 6 DAGs:
- `crawler_topdev` (Thứ Hai 20:00)
- `crawler_careerviet` (Thứ Ba 20:00)
- `crawler_itviec` (Thứ Tư 20:00)
- `crawler_vietnamworks` (Thứ Năm 20:00)
- `crawler_topcv` (Thứ Sáu 20:00)
- `crawler_vieclam24h` (Thứ Bảy 20:00)

## 4. Chạy Thử (Test Run)
Chạy thử nghiệm một task crawler và task kiểm tra chất lượng dữ liệu:
```bash
# Test crawler VietnamWorks
airflow tasks test crawler_vietnamworks crawl_vietnamworks 2026-10-06

# Test DataQualityCheck
airflow tasks test crawler_vietnamworks check_quality_vietnamworks 2026-10-06
```

## 5. Khởi Động Webserver & Scheduler
```bash
# Khởi động Scheduler trong background hoặc tab terminal riêng
airflow scheduler

# Khởi động Webserver ở port 8080
airflow webserver --port 8080
```
Truy cập UI tại: `http://localhost:8080`
