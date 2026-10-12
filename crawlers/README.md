# Crawlers

Mỗi nguồn tuyển dụng có một thư mục độc lập trong `sources/`. Mỗi bạn phụ trách một nguồn, chỉ sửa code và tài liệu trong thư mục nguồn mình được phân công.

## Phân công nguồn (8 Nguồn Tuyển Dụng IT)

| Nguồn | Thư mục | Giao thức / Công nghệ | Trạng thái | Sản lượng hiện tại |
|---|---|---|---|---|
| **TopDev** | `sources/topdev/` | REST API v2 (`api.topdev.vn`) | 🚀 Hoàn thành | 125 jobs |
| **CareerViet** | `sources/careerviet/` | Requests + BeautifulSoup (SSR) | 🚀 Hoàn thành | 655 jobs |
| **ITviec** | `sources/itviec/` | Requests + BeautifulSoup (SSR) | 🚀 Hoàn thành | 674 jobs |
| **VietnamWorks** | `sources/vietnamworks/` | Search API POST (`ms.vietnamworks.com`) | 🚀 Hoàn thành | 2,232 jobs |
| **TopCV** | `sources/topcv/` | Playwright Headless Chrome (Anti-WAF) | 🚀 Hoàn thành | 810 jobs |
| **ViecLam24h** | `sources/vieclam24h/` | Next.js SSR State parser | 🚀 Hoàn thành | 445 jobs |
| **Glints** | `sources/glints/` | REST API / SSR | 🚀 Hoàn thành | 244 jobs |
| **JobsGO** | `sources/jobsgo/` | Playwright Headless + BS4 | 🚀 Hoàn thành | 1,476 jobs |

## Module dùng chung (`common/`)

Toàn bộ crawlers kế thừa [`BaseCrawler`](base/base_crawler.py) và tận dụng các module dùng chung:

| Module | Chức năng |
|---|---|
| `http_client.py` | HTTP session + delay ngẫu nhiên 1.5–3.5s + exponential backoff retry + User-Agent rotation |
| `checkpoint.py` | Đọc/ghi checkpoint atomic JSON (`seen_ids`, `last_page`) để resume khi đứt quãng |
| `job_catalog.py` | SQLite State Catalog (`job_catalog.db`) O(1) deduplication & tracking trạng thái thu thập |
| `json_writer.py` | Ghi file JSON chuẩn mảng phân vùng `data/<source>/dt=YYYY-MM-DD/batch_XXX.json` an toàn nguyên tử (atomic write qua file tạm `.tmp`) |
| `data_quality.py` | `DataQualityChecker` kiểm định Schema validity $\ge 95\%$, dedup rate, completeness |
| `schema.py` | Pydantic v2 `JobRecord` (Metadata + Raw + Salary + Tags), smart adapter backward compatibility |
| `utils.py` | Làm sạch thẻ HTML, chuẩn hóa ngắt dòng bullets, bóc tách dải lương chi tiết, nhận diện ngôn ngữ (`vi`/`en`) |
| `s3_uploader.py` | Đồng bộ file batch lên AWS S3 Raw Zone (`boto3`) |

## Quy ước chung

- Tên thư mục và module dùng `snake_case`.
- Mỗi file đầu ra là **JSON Array** `[ { "_meta": {...}, "raw": {...} }, ... ]` lưu theo phân vùng Hive-style `dt=YYYY-MM-DD`.
- Phần `_meta` chuẩn hóa bắt buộc: `source`, `source_job_id`, `url`, `dedup_key`, `crawled_at`, `batch_id`, `language`.
- Phần `raw` bóc tách lương lồng (`JobSalary`), nhóm thẻ (`JobTags`), dọn sạch rác HTML/CSS.
- Delay **1.5–3.5 giây** ngẫu nhiên giữa các request trang chi tiết để cào lịch sự (Polite Crawling).
- Không phá hoại hệ thống đối tác, không bypass trái phép CAPTCHA/DDoS.

## Cách chạy thử nghiệm từng nguồn

```bash
# Chạy trực tiếp file crawler của nguồn
python3 crawlers/sources/topdev/crawler.py --max-items 30
python3 crawlers/sources/topcv/crawler.py --max-items 30
python3 crawlers/sources/vietnamworks/crawler.py --max-items 50

# Hoặc kích hoạt điều phối qua Apache Airflow
make start-airflow
make monitor
```
