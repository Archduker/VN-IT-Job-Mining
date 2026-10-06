# **Implementation Plan — VN IT Job Mining Data Collection System**

## **Problem Statement:**
Xây dựng hệ thống thu thập dữ liệu tự động dùng **Apache Airflow chạy trên laptop**, orchestrate việc cào 6 trang tuyển dụng IT tại Việt Nam. Code từ các thành viên đã được pull về, chuẩn hoá theo kiến trúc **BaseCrawler (1 file `.py` cho mỗi nguồn)** với type hints + docstrings, tích hợp schema Pydantic, ghi dữ liệu phân vùng `data/<source>/dt=YYYY-MM-DD/batch_XXX.jsonl`, và quản lý tiến độ bằng CheckpointManager.

---

## **Bảng Tổng Hợp Trạng Thái Các Tasks (100% HOÀN THÀNH):**

| # | Task | Trạng thái | Chi tiết triển khai |
|---|------|:---:|---------------------|
| **1** | Setup môi trường & dependencies | ✅ **HOÀN THÀNH** | Môi trường Python 3.12 (`.venv`), Apache Airflow 2.11.2, pydantic, pytest, requests, bs4, playwright. |
| **2** | Data Schema & Common Modules | ✅ **HOÀN THÀNH** | `crawlers/common/schema.py` (`JobRecord`, `JobMetadata`, `JobRaw`), `http_client.py` (GET/POST, delay, UA rotation), `logger.py`, `utils.py`. |
| **3** | Build Checkpoint & JsonlWriter | ✅ **HOÀN THÀNH** | `crawlers/common/checkpoint.py` (atomic write JSON), `crawlers/common/jsonl_writer.py` (phân vùng partitioned JSONL, schema validator). |
| **4** | Pull & Audit code từ GitHub | ✅ **HOÀN THÀNH** | Pull và merge toàn bộ code của các bạn: `itviec`, `topdev`, `vietnamworks`, `careerviet`. |
| **5** | Refactor TopDev Crawler (Single file) | ✅ **HOÀN THÀNH** | `crawlers/sources/topdev/crawler.py`: Kế thừa `BaseCrawler`, gọi REST API chính thức, parse full fields, crawl JSONL chuẩn. |
| **6** | Refactor VietnamWorks, CareerViet, ITviec & Nguồn 6 | ✅ **HOÀN THÀNH** | - `vietnamworks/crawler.py`: POST API Search, bóc tách đầy đủ chi tiết.<br>- `careerviet/crawler.py`: SSR category + parsing detail.<br>- `itviec/crawler.py`: Độc lập CLI, tích hợp schema & checkpoint.<br>- `vieclam24h/crawler.py` (Nguồn 6 thay thế LinkedIn): Bóc tách SSR `__NEXT_DATA__`. |
| **7** | Implement TopCV Crawler (Playwright) | ✅ **HOÀN THÀNH** | `crawlers/sources/topcv/crawler.py`: Tích hợp Playwright headless với Google Chrome, cấu hình chống bot. |
| **8** | Base Crawler Abstract Class | ✅ **HOÀN THÀNH** | `crawlers/base/base_crawler.py`: `BaseCrawler` quản lý chung lifecycle, `fetch_items()`, `parse_item()`, checkpoint deduplication và JSONL writing. |
| **9** | Setup Airflow & 6 DAGs | ✅ **HOÀN THÀNH** | Khởi tạo Airflow SQLite DB, viết `airflow/plugins/crawler_operators.py` và 6 DAGs trong `airflow/dags/crawler_dags.py` theo rotating daily schedule (20:00 hàng ngày). |
| **10** | Data Quality Check & Monitoring | ✅ **HOÀN THÀNH** | `crawlers/common/data_quality.py` (`DataQualityChecker`), `DataQualityOperator` trong Airflow, dashboard dòng lệnh `scripts/report.py`. |
| **11** | Comprehensive Tests (Coverage ≥ 75%) | ✅ **HOÀN THÀNH** | 78/78 unit tests **PASSED 100%**, coverage của common và base modules đạt **75.0%**. |
| **12** | Documentation & Demo Materials | ✅ **HOÀN THÀNH** | Cập nhật `README.md`, `docs/airflow_setup_guide.md`, `docs/demo_checklist.md`, crawl thử nghiệm dữ liệu thực tế. |

---

## **Kiến Trúc Thu Thập (Single File per Source):**

```
crawlers/
├── base/
│   ├── __init__.py
│   └── base_crawler.py          # Abstract Class chuẩn hoá
├── common/
│   ├── checkpoint.py            # Quản lý checkpoint & deduplication
│   ├── data_quality.py          # Kiểm tra chất lượng dữ liệu
│   ├── http_client.py           # HTTP client rotate UA, delay, retry
│   ├── jsonl_writer.py          # Partitioned JSONL writer
│   ├── logger.py                # Logging format chuẩn
│   ├── schema.py                # Pydantic schemas (JobRecord, etc.)
│   └── utils.py                 # URL normalize, batch_id, strip tags
└── sources/
    ├── topdev/crawler.py        # 1 file duy nhất cho TopDev
    ├── vietnamworks/crawler.py  # 1 file duy nhất cho VietnamWorks
    ├── careerviet/crawler.py    # 1 file duy nhất cho CareerViet
    ├── itviec/crawler.py        # 1 file duy nhất cho ITviec
    ├── vieclam24h/crawler.py    # 1 file duy nhất cho ViecLam24h (nguồn 6)
    └── topcv/crawler.py         # 1 file duy nhất cho TopCV (Playwright)
```

---

## **Airflow Schedule (Rotating Daily Schedule):**

- **Thứ Hai 20:00:** `crawler_topdev`
- **Thứ Ba 20:00:** `crawler_careerviet`
- **Thứ Tư 20:00:** `crawler_itviec`
- **Thứ Năm 20:00:** `crawler_vietnamworks`
- **Thứ Sáu 20:00:** `crawler_topcv`
- **Thứ Bảy 20:00:** `crawler_vieclam24h`