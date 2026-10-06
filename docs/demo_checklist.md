# Checklist Báo Cáo & Demo Với Thầy Giáo

## 1. Mục Tiêu Báo Cáo
Trình diễn hệ thống thu thập dữ liệu việc làm IT tự động tại Việt Nam với Apache Airflow, kiến trúc thu gom chuẩn hoá dạng JSONL phân vùng theo ngày và cơ chế kiểm soát chất lượng dữ liệu (Data Quality).

---

## 2. Các Bước Thực Hiện Demo Trực Tiếp

### Bước 1: Giới thiệu Kiến trúc & Cấu trúc Mã Nguồn
- Trình bày kiến trúc `BaseCrawler` kế thừa thống nhất:
  - `crawlers/base/base_crawler.py`
  - Các nguồn: `topdev`, `vietnamworks`, `careerviet`, `itviec`, `vieclam24h`, `topcv`
- Trình bày cấu trúc dữ liệu tuân thủ schema Pydantic:
  - `_meta`: `source`, `source_job_id`, `url`, `dedup_key`, `batch_id`, `crawled_at`
  - `raw`: các trường thô không làm sai lệch dữ liệu gốc (`title`, `company`, `description_html`, `salary_text`, ...)

### Bước 2: Chạy Thử Nghiệm 1 Crawler Độc Lập
Chạy crawler trực tiếp qua CLI với tùy chọn giới hạn số lượng tin:
```bash
python crawlers/sources/topdev/crawler.py --max-items 5
```
- Cho thầy xem log: HTTP GET thành công, tự động delay lịch sự, áp dụng retry.
- Kiểm tra file checkpoint: `data/topdev/topdev_checkpoint.json`.
- Chạy lại lệnh trên lần thứ 2: chứng minh **cơ chế Deduplication không cào lại tin cũ** (skipped 5 tin).

### Bước 3: Airflow Orchestration & Schedule
- Mở danh sách DAGs:
```bash
airflow dags list | grep crawler
```
- Trình diễn cấu trúc rotating daily schedule: Mỗi ngày trong tuần kích hoạt 1 nguồn (20:00).
- Trigger thủ công một DAG run trên terminal:
```bash
airflow tasks test crawler_vietnamworks crawl_vietnamworks 2026-10-06
```

### Bước 4: Kiểm Soát Chất Lượng Dữ Liệu (Data Quality)
- Chạy kiểm tra chất lượng file vừa thu thập:
```bash
python -c "from crawlers.common.data_quality import DataQualityChecker; print(DataQualityChecker('data/vietnamworks/dt=2026-10-06/batch_001.jsonl').check())"
```
- Xem kết quả: 100% bản ghi hợp lệ schema, không rỗng trường bắt buộc, tỷ lệ trùng lặp 0%.

### Bước 5: Báo Cáo Tổng Hợp Tiến Độ
Chạy dashboard dòng lệnh tổng kết toàn hệ thống:
```bash
python scripts/report.py
```
Hiển thị tổng số tin và tình trạng dữ liệu của từng nguồn.

### Bước 6: Test Suite & Coverage
Chạy toàn bộ unit test chứng minh tính ổn định của hệ thống:
```bash
pytest --cov=crawlers/common --cov=crawlers/base tests/unit
```
Toàn bộ 78 test cases đạt trạng thái **PASSED** với độ bao phủ **≥ 75%**.
