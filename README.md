# **VN IT Job Mining Data Collection System**

Hệ thống thu thập dữ liệu tuyển dụng IT tự động tại Việt Nam, orchestrate bằng **Apache Airflow**, lưu trữ dữ liệu dạng **JSONL phân vùng (partitioned)** và kiểm soát chất lượng dữ liệu trước khi nạp vào kho dữ liệu.

---

## 🏛️ Kiến Trúc Hệ Thống

```mermaid
flowchart TD
    subgraph Sources["6 Nguồn Thu Thập Tuyển Dụng"]
        S1["TopDev (REST API)"]
        S2["VietnamWorks (Search API)"]
        S3["CareerViet (SSR + Detail)"]
        S4["ITviec (SSR + Detail)"]
        S5["TopCV (Playwright Headless)"]
        S6["ViecLam24h (SSR State)"]
    end

    subgraph Architecture["BaseCrawler Framework"]
        BC["BaseCrawler (crawlers/base/base_crawler.py)"]
        HTTP["HttpClient (UA Rotation, Delay 2-5s, Retry)"]
        CK["CheckpointManager (Atomic JSON, Resume, Dedup)"]
        JW["JsonlWriter (Schema Validation, Partitioning)"]
        DQ["DataQualityChecker (Schema Valid, Dedup Key, Uniqueness)"]
    end

    subgraph Orchestration["Apache Airflow (LocalExecutor)"]
        D1["crawler_topdev (Thứ Hai 20:00)"]
        D2["crawler_careerviet (Thứ Ba 20:00)"]
        D3["crawler_itviec (Thứ Tư 20:00)"]
        D4["crawler_vietnamworks (Thứ Năm 20:00)"]
        D5["crawler_topcv (Thứ Sáu 20:00)"]
        D6["crawler_vieclam24h (Thứ Bảy 20:00)"]
    end

    subgraph Storage["Lưu Trữ Dữ Liệu"]
        LOC["data/<source>/dt=YYYY-MM-DD/batch_XXX.jsonl"]
    end

    Sources --> BC
    HTTP --> BC
    CK --> BC
    JW --> BC
    BC --> LOC
    Orchestration --> BC
    LOC --> DQ
```

---

## 📦 Cài Đặt & Chạy Thử Nghiệm

### 1. Kích hoạt môi trường
```bash
source .venv/bin/activate
export PYTHONPATH=.
```

### 2. Chạy thử nghiệm từng crawler riêng lẻ (Single File .py)
Mỗi nguồn được đóng gói gọn trong đúng **1 file duy nhất** tại `crawlers/sources/<source>/crawler.py`:

```bash
# TopDev
python crawlers/sources/topdev/crawler.py --max-items 30

# VietnamWorks
python crawlers/sources/vietnamworks/crawler.py --max-items 50

# CareerViet
python crawlers/sources/careerviet/crawler.py --max-items 30

# ViecLam24h
python crawlers/sources/vieclam24h/crawler.py --max-items 30

# ITviec
python crawlers/sources/itviec/crawler.py --max-items 30
```

### 3. Xem báo cáo tiến độ thu thập
```bash
python scripts/report.py
```

### 4. Chạy Unit Tests & Test Coverage
```bash
pytest --cov=crawlers/common --cov=crawlers/base tests/unit
```
Toàn bộ 78 test cases đạt trạng thái **100% Passed**, Coverage **≥ 75%**.

---

## 🕒 Rotating Daily Schedule trên Airflow
| Ngày | Nguồn | DAG ID | Lịch Chạy |
|:---|:---|:---|:---|
| Thứ Hai | **TopDev** | `crawler_topdev` | `0 20 * * 1` |
| Thứ Ba | **CareerViet** | `crawler_careerviet` | `0 20 * * 2` |
| Thứ Tư | **ITviec** | `crawler_itviec` | `0 20 * * 3` |
| Thứ Năm | **VietnamWorks** | `crawler_vietnamworks` | `0 20 * * 4` |
| Thứ Sáu | **TopCV** | `crawler_topcv` | `0 20 * * 5` |
| Thứ Bảy | **ViecLam24h** | `crawler_vieclam24h` | `0 20 * * 6` |

Xem hướng dẫn chi tiết tại:
- [Hướng dẫn thiết lập Airflow](docs/airflow_setup_guide.md)
- [Checklist báo cáo demo với thầy](docs/demo_checklist.md)
