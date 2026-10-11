# Glints Vietnam Crawler

Crawler Glints cho dự án `VN-IT-Job-Mining`, triển khai theo `BaseCrawler` và chuẩn hóa dữ liệu bằng `JobRecord`.

## Cách lấy dữ liệu

- Danh sách việc làm: GraphQL `https://glints.com/api/v2-alc/graphql?op=searchJobsV3` (`CountryCode=VN`, phân trang bằng `page` và `pageSize`).
- Chi tiết việc làm: trang công khai theo dạng `https://glints.com/vn/opportunities/jobs/<slug>/<id>`; crawler đọc đối tượng JSON-LD `JobPosting` được nhúng trong HTML.
- Header `Accept-Encoding: identity` được dùng vì trong một số lần chạy, phản hồi Brotli (`Content-Encoding: br`) không được giải mã đúng ở tầng HTTP client.
- Endpoint REST cũ `/api/job-postings` không được dùng trong bản này; trong quá trình tích hợp, endpoint đó đã trả `Not Found`, còn GraphQL `searchJobsV3` hoạt động.

## Chạy crawler

Từ thư mục gốc repo:

```powershell
python run.py --source glints --max-items 5 -v
```

Output mặc định qua `JsonWriter`:

```text
data/glints/dt=YYYY-MM-DD/batch_001.json
```

Có thể chạy với thư mục thử nghiệm riêng trong Python:

```python
from crawlers.sources.glints.crawler import GlintsCrawler

crawler = GlintsCrawler(
    checkpoint_dir=r"data\glints_test_checkpoint",
    output_dir=r"data\glints_test_output",
    max_items=5,
)
print(crawler.run())
```

## Các trường chính

- `_meta.source_job_id`: ID nguồn từ Glints.
- `raw.title`, `raw.company`: chức danh và công ty.
- `raw.salary`: `salary_min`, `salary_max`, `salary_currency`, `pay_period`, `salary_text`.
- `raw.tags.skills`: kỹ năng từ GraphQL và JSON-LD.
- `raw.description_html`: mô tả HTML gốc từ JSON-LD, được giữ lại để truy vết.
- `raw.description_text`: mô tả thuần, đã bỏ tag HTML, giữ ngắt dòng đoạn và danh sách.
- `raw.description_list`: các dòng mô tả thuần, dùng để tương thích schema `JobRecord` của project.
- `raw.posted_date_text`: `datePosted`, fallback sang `createdAt`; nếu thiếu ngày đăng nhưng tìm thấy mẫu `N days left` và hạn tuyển dụng, suy ra bằng `validThrough - N ngày`.
- `raw.deadline_text`: ngày `validThrough`.
- `_meta.language`: ước lượng `vi` hoặc `en` dựa trên tiêu đề và mô tả.

`description_html` được cố ý giữ nguyên markup của nguồn; trường đã loại bỏ thẻ HTML là `description_text` và từng dòng trong `description_list`.

## Tích hợp `run.py`

Nếu `run.py` hiện tại đã có `glints` trong `SUPPORTED_SOURCES` và nhánh import `GlintsCrawler`, không cần thêm lần nữa. Nếu chưa có, bổ sung `glints` vào danh sách nguồn và dùng nhánh tương tự:

```python
elif source == "glints":
    from crawlers.sources.glints.crawler import GlintsCrawler
    crawler = GlintsCrawler(
        checkpoint_dir=checkpoint_dir,
        output_dir=output_dir,
        max_items=max_items,
    )
    if batch_id:
        crawler.batch_id = batch_id
    return crawler.run()
```

## Unit tests

Từ thư mục gốc repo, chạy:

```powershell
python -m pytest tests/unit/test_glints_crawler.py -q
```

Các test dùng fake HTTP response, không gửi request thật đến Glints.
