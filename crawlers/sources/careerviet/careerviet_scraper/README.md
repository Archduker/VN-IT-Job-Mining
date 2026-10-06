# CareerViet Job Scraper

Hệ thống thu thập dữ liệu việc làm tự động từ **careerviet.vn**, hỗ trợ 7 danh mục ngành nghề, với cơ chế checkpoint recovery, deduplication và rate limiting.

---

## 📁 Cấu Trúc Project

```
careerviet.vn/
├── careerviet_scraper/
│   ├── __init__.py       # Package init
│   ├── config.py         # Cấu hình URLs, User-Agents, danh mục, timeouts
│   ├── scraper.py        # Browser engine & crawling logic (Playwright)
│   ├── parser.py         # HTML DOM parsing & JSON schema extraction
│   ├── pipeline.py       # Checkpoint, Deduplication, Output, Stats
│   ├── main.py           # CLI Runner (entry point)
│   └── requirements.txt  # Thư viện cần cài
├── careerviet_raw_jobs.json  # Output (tự động tạo)
├── checkpoint.json           # Trạng thái crawl (tự động tạo)
├── error_log.txt             # Log lỗi (tự động tạo)
└── scraper_run.log           # Log chạy chi tiết (tự động tạo)
```

---

## ⚙️ Cài Đặt

### Yêu Cầu
- Python **3.10+**
- pip

### Bước 1: Cài thư viện Python

```powershell
cd "d:\ĐH\Năm 3\Học kỳ 1\Khai thác dữ liệu\careerviet.vn"

# Tạo môi trường ảo (khuyến nghị)
python -m venv .venv
.venv\Scripts\activate

# Cài thư viện
pip install -r careerviet_scraper/requirements.txt
```

### Bước 2: Cài Playwright Browsers

```powershell
playwright install chromium
```

> Nếu gặp lỗi permission, chạy: `playwright install chromium --with-deps`

---

## 🚀 Khởi Chạy

### Chạy đầy đủ (tất cả 7 danh mục)

```powershell
python -m careerviet_scraper.main
```

### Các tùy chọn CLI

| Tham số | Mô tả | Ví dụ |
|---------|-------|-------|
| `--resume` | Tiếp tục từ checkpoint (mặc định) | `--resume` |
| `--reset` | Xóa checkpoint, chạy lại từ đầu | `--reset` |
| `--category` | Chỉ cào một danh mục | `--category "CNTT - Phần mềm"` |
| `--output` | Đường dẫn file JSON output | `--output my_jobs.json` |
| `--concurrency` | Số tab đồng thời | `--concurrency 3` |
| `--delay-min` | Delay tối thiểu (giây) | `--delay-min 2.0` |
| `--delay-max` | Delay tối đa (giây) | `--delay-max 5.0` |
| `--headful` | Chạy có giao diện browser | `--headful` |
| `--verbose` / `-v` | Log chi tiết (debug) | `-v` |

### Ví dụ thực tế

```powershell
# Test với 1 danh mục, verbose
python -m careerviet_scraper.main --category "CNTT - Phần mềm" -v

# Resume sau khi bị gián đoạn
python -m careerviet_scraper.main --resume

# Chạy toàn bộ với delay cao hơn (tránh bị chặn)
python -m careerviet_scraper.main --delay-min 3.0 --delay-max 6.0

# Reset và chạy lại hoàn toàn
python -m careerviet_scraper.main --reset
```

---

## 📊 Schema Dữ Liệu Đầu Ra

File `careerviet_raw_jobs.json`:

```json
[
  {
    "job_id": "35C541AE",
    "crawled_category": "CNTT - Phần mềm",
    "url": "https://careerviet.vn/vi/tim-viec-lam/data-engineer.35C541AE.html",
    "title": "Data Engineer",
    "company_name": "Tên công ty",
    "company_url": "https://careerviet.vn/nha-tuyen-dung/...",
    "salary_raw": "20 Tr - 35 Tr VND",
    "location_city": "Hồ Chí Minh",
    "location_address": "Địa chỉ cụ thể...",
    "posted_date": "20/09/2025",
    "deadline_date": "30/10/2025",
    "experience_raw": "2 - 5 Năm",
    "job_level": "Nhân viên",
    "employment_type": "Toàn thời gian",
    "industries_raw": "CNTT - Phần mềm",
    "tags": ["Python", "SQL", "ETL"],
    "education_raw": "Đại học",
    "job_description_raw": ["Mô tả 1...", "Mô tả 2..."],
    "job_requirements_raw": ["Yêu cầu 1..."],
    "benefits_raw": ["Quyền lợi 1..."],
    "crawled_at": "2026-10-04T12:00:00Z"
  }
]
```

---

## 🛡️ Tính Năng Anti-Detection

| Tính năng | Chi tiết |
|-----------|----------|
| **User-Agent Rotation** | 5 UA thực từ Chrome/Firefox/Edge/Safari |
| **Random Delay** | 1.5s – 3.5s ngẫu nhiên giữa các request |
| **Semaphore Control** | Tối đa 3 tab đồng thời |
| **Webdriver Masking** | Inject JS ẩn `navigator.webdriver` |
| **Context Reset** | Tự động đổi context khi bị HTTP 403/429 |
| **Exponential Backoff** | Retry với delay tăng dần |

---

## 🔄 Cơ Chế Recovery

```
Lần chạy đầu:  Crawl tất cả → Lưu checkpoint.json
Bị crash/tắt:  checkpoint.json ghi nhớ URL đã cào
Lần chạy tiếp: --resume tự động bỏ qua URL đã xong
```

**Checkpoint được lưu:**
- Sau mỗi trang listing hoàn thành
- Sau mỗi 20 job detail crawled
- Khi Ctrl+C (graceful shutdown)

---

## 🏷️ Danh Mục Hỗ Trợ

| # | Tên Danh Mục | Category ID |
|---|-------------|-------------|
| 1 | CNTT - Phần mềm | 47 |
| 2 | CNTT - Phần cứng / Mạng | 48 |
| 3 | Viễn thông | 49 |
| 4 | Internet / Thương mại điện tử | 137 |
| 5 | Mỹ thuật / Thiết kế | 24 |
| 6 | Tự động hóa / Điện - Điện tử | 20 |
| 7 | Tư vấn / Dịch vụ tài chính - Ngân hàng | 13 |

---

## ⚠️ Xử Lý Lỗi

| Lỗi | Hành động |
|-----|-----------|
| HTTP 404 | Skip URL, tiếp tục |
| HTTP 403/429 | Reset context, đổi UA, đợi |
| Timeout | Retry 3 lần với exponential backoff |
| ElementNotFound | Dùng fallback selector |
| Captcha/Block | Ghi vào error_log.txt, bỏ qua |
| Crash/KeyboardInterrupt | Auto-save checkpoint & output |

---

## 📝 Ghi Chú

- **Thời gian ước tính**: ~2-4 giờ cho 7 danh mục (tùy số lượng job và tốc độ mạng)
- **Dữ liệu thô**: Parser giữ nguyên dữ liệu, không clean/normalize ở bước này
- **Encoding**: UTF-8 với `ensure_ascii=False` để hỗ trợ tiếng Việt

---

*Generated by CareerViet Scraper v1.0.0*
