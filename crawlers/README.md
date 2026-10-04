# Crawlers

Mỗi nguồn tuyển dụng có một thư mục độc lập trong `sources/`. Mỗi bạn phụ trách một nguồn, chỉ sửa code và tài liệu trong thư mục nguồn mình được phân công.

| Nguồn | Thư mục | Người phụ trách | Trạng thái |
|---|---|---|---|
| TopDev | `sources/topdev/` | Sơn | Chưa bắt đầu |
| LinkedIn | `sources/linkedin/` | Phúc | Chưa bắt đầu |
| CareerViet | `sources/careerviet/` | Tài | Chưa bắt đầu |
| JobsGO | `sources/jobsgo/` | Khoa | Chưa bắt đầu |
| ITviec | `sources/itviec/` | Phát | Chưa bắt đầu |
| TopCV | `sources/topcv/` | Thuận | Chưa bắt đầu |

Trước khi cào, người phụ trách phải kiểm tra `robots.txt` và điều khoản sử dụng của nguồn. Không vượt CAPTCHA, đăng nhập, hoặc giới hạn tốc độ.

## Quy ước chung

- Tên thư mục và module dùng `snake_case`.
- Lưu HTML/JSON gốc ra S3 Raw Zone, không đưa dữ liệu crawl lớn lên Git.
- Mỗi bản ghi phải có `source`, `job_url` (canonical) và `collected_date`.
- Ghi số lượng thu thập, lỗi và đường dẫn đầu ra vào `run_log.jsonl` khi chạy.

Mỗi thư mục nguồn đã có `README.md` để ghi owner, URL được phép cào, cách chạy và ghi chú parser. Khi triển khai, có thể thêm `crawler.py`, `parser.py`, `config.py` và `tests/` vào đúng thư mục nguồn đó.
