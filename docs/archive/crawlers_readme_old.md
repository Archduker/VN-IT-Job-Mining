# Crawlers

Mỗi nguồn tuyển dụng có một thư mục độc lập trong `sources/`. Mỗi bạn phụ trách một nguồn, chỉ sửa code và tài liệu trong thư mục nguồn mình được phân công.

## Phân công nguồn

| Nguồn | Thư mục | Người phụ trách | Công cụ | Trạng thái |
|---|---|---|---|---|
| TopDev | `sources/topdev/` | Sơn | requests + BS4 | ⬜ Chưa bắt đầu |
| CareerViet | `sources/careerviet/` | Tài | requests + BS4 | ⬜ Chưa bắt đầu |
| ITviec | `sources/itviec/` | Phát | requests + BS4 | ⬜ Chưa bắt đầu |
| VietnamWorks | `sources/vietnamworks/` | Khoa | requests + BS4 | ⬜ Chưa bắt đầu |
| TopCV | `sources/topcv/` | Thuận | Playwright / Browser Use | ⬜ Chưa bắt đầu |
| _Chưa chốt_ | `sources/<tên>/` | Phúc | _Tùy nguồn_ | ⚠️ Cần chọn nguồn |

## Module dùng chung (`common/`)

Thuận viết và bảo trì. Cả nhóm import dùng, **không tự sửa** (nếu cần thay đổi thì báo Thuận):

| Module | Chức năng |
|---|---|
| `http_client.py` | HTTP session + delay ngẫu nhiên 2–5s + retry với backoff + User-Agent |
| `checkpoint.py` | Đọc/ghi checkpoint (seen_ids, last_page) để chạy tiếp khi bị gián đoạn |
| `jsonl_writer.py` | Ghi file JSONL an toàn (append, flush từng dòng) |
| `s3_uploader.py` | Upload batch lên S3 Raw Zone (boto3) |
| `telegram_notifier.py` | Gửi báo cáo sau mỗi batch (số tin mới, trùng, lỗi) |
| `schema.py` | Validate schema `_meta` + `raw` trước khi ghi |
| `utils.py` | URL normalize, hash, logging |

## Quy ước chung

- Tên thư mục và module dùng `snake_case`.
- Mỗi bản ghi JSONL phải có cấu trúc `{ "_meta": {...}, "raw": {...} }`.
- Phần `_meta` bắt buộc giống nhau cả 6 nguồn (xem schema trong [TASKS.md](../TASKS.md#4-hợp-đồng-dữ-liệu-data-contract)).
- Phần `raw` mỗi nguồn tự quyết, **giữ nguyên văn gốc**, bắt buộc có `description_html`.
- Lưu HTML/JSON gốc ra S3 Raw Zone, **không đưa dữ liệu crawl lên Git**.
- Delay **2–5 giây** ngẫu nhiên giữa các request (dùng `common/http_client.py`).
- Ghi checkpoint sau mỗi 10 tin (dùng `common/checkpoint.py`).
- Trước khi cào, kiểm tra `robots.txt` và điều khoản sử dụng. **Không vượt CAPTCHA**, đăng nhập, hoặc phá giới hạn tốc độ.

## Cấu trúc thư mục mỗi nguồn

```text
sources/<tên-nguồn>/
├── crawler.py          # Logic cào: listing → filter mới → detail → ghi JSONL
├── parser.py           # Parse HTML → dict (listing parser + detail parser)
├── config.py           # URL gốc, headers, delay, max_items mặc định
├── README.md           # Owner, URL được phép, robots.txt, cách chạy, ghi chú
└── tests/              # (Tùy chọn) test parser với HTML mẫu
```

## Cách chạy

```bash
# Chạy một nguồn cụ thể (từ thư mục gốc dự án)
python run.py --source topdev --max-items 30

# Chạy với batch_id tùy chỉnh
python run.py --source careerviet --max-items 200 --batch-id 2026-10-07_careerviet_001
```
