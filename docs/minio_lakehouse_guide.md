# MinIO Lakehouse Guide — VN-IT-Job-Mining

Tài liệu vận hành MinIO cho nhóm crawler. Cấu hình mặc định ưu tiên **MinIO local qua Docker**, bucket `vn-it-jobs`, private by default. Cloudflare R2 là tùy chọn riêng cho chế độ lưu trữ dùng chung.

## 1. Cấu trúc

```text
vn-it-jobs/
├── url_ledger/<source>/
│   ├── catalog_master.json
│   ├── catalog_master.parquet        # nếu pipeline đã cài pyarrow và xuất Parquet
│   ├── discovery_miss_counts.json
│   └── manifests/manifest_YYYY-MM-DD.jsonl
├── raw/<source>/
│   ├── _listing/YYYY-MM-DD/          # payload trang listing/API gốc
│   └── YYYY-MM-DD/                   # detail snapshots/versioned raw records
├── staging/<source>/                 # dữ liệu sau bước chuẩn hóa
└── curated/                          # dữ liệu đã khử trùng lặp / làm giàu
```

Các “thư mục” trong S3/MinIO là object key prefixes, không phải thư mục filesystem. Script khởi tạo đặt `.keep` marker để bốn tầng hiển thị trong Console; những object thực tế do crawler tạo sẽ nằm dưới prefix tương ứng.

## 2. Trước khi chạy

1. Cài và mở Docker Desktop; đợi trạng thái Engine running.
2. Mở Terminal tại thư mục gốc `VN-IT-Job-Mining`.
3. Tạo `.env` từ ví dụ (chỉ tạo nếu chưa có để tránh ghi đè cấu hình hiện tại):

   ```powershell
   if (!(Test-Path .env)) { Copy-Item .env.example .env }
   ```

4. Đảm bảo `.env` đang ở chế độ local MinIO, với endpoint `http://localhost:9000`, bucket `vn-it-jobs`, và thông tin `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` khớp với các biến `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` mà crawler đang dùng.

## 3. Khởi chạy — Windows

Cách ngắn gọn:

```powershell
.\scripts\start_minio.ps1
```

Hoặc chạy trực tiếp:

```powershell
docker compose -f .\docker-compose.minio.yml up -d --build
```

Lần đầu, Docker build container helper Python để khởi tạo bucket. Helper sẽ chờ endpoint MinIO sẵn sàng, tạo bucket nếu chưa tồn tại và tạo marker cho `url_ledger/`, `raw/`, `staging/`, `curated/`. Helper không cần `curl` hoặc `mc` trong image server.

## 4. Mở giao diện và đăng nhập

- Console UI: <http://localhost:9001>
- S3 API: <http://localhost:9000>
- Bucket: `vn-it-jobs`
- Mặc định phát triển cục bộ: `minioadmin` / `minioadmin`

Tài khoản mặc định chỉ phù hợp cho máy dev cá nhân. Đừng expose cổng 9000/9001 ra Internet; nếu dùng máy dùng chung, đổi mật khẩu trong `.env` và Compose sẽ đọc biến đó. Không đưa `.env`, R2 keys hoặc mật khẩu thật lên Git.

## 5. Kiểm tra trạng thái và bucket

```powershell
python scripts/check_minio.py
python scripts/setup_minio.py
```

Xem log:

```powershell
docker compose -f .\docker-compose.minio.yml ps -a
docker compose -f .\docker-compose.minio.yml logs --tail 100 minio
docker compose -f .\docker-compose.minio.yml logs --tail 100 minio-init
```

Nếu container MinIO là `Up` nhưng script kiểm tra S3 lỗi, chạy `check_minio.py` để phân biệt API, credentials và bucket. Đừng kết luận chỉ từ trạng thái Docker `Up`.

## 6. Kiểm tra URL Ledger và dữ liệu crawler

```powershell
python scripts/view_urls.py --source glints --minio --limit 20
python scripts/view_urls.py --source jobsgo --minio --limit 20
```

Nếu bucket đã được tạo nhưng chưa thấy record, nghĩa là dữ liệu chưa được crawl/ghi vào prefix đó. Chỉ bucket và các object thực tế mới được xác nhận là dữ liệu; file fixture tổng hợp trong repo là dữ liệu test, không phải bằng chứng đã crawl live.

## 7. Sử dụng Boto3

```python
import os
import boto3
from botocore.client import Config

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)
response = s3.list_objects_v2(Bucket="vn-it-jobs", Prefix="raw/glints/", MaxKeys=10)
for item in response.get("Contents", []):
    print(item["Key"], item["Size"])
```

Crawler phải đọc endpoint, credentials và bucket từ biến môi trường, không hardcode credentials dùng chung vào source code.

## 8. Dừng / khởi động lại / giữ dữ liệu

Dừng container nhưng giữ volume:

```powershell
docker compose -f .\docker-compose.minio.yml stop
```

Khởi động lại:

```powershell
docker compose -f .\docker-compose.minio.yml up -d --build
```

Dừng và gỡ container/network nhưng giữ volume:

```powershell
docker compose -f .\docker-compose.minio.yml down
```

**Không chạy `docker compose down -v` khi chỉ định restart hoặc khắc phục sự cố.** Tùy chọn `-v` xóa volume `minio_data` và có thể xóa toàn bộ dữ liệu crawler đã lưu trong MinIO local. Chỉ dùng khi chủ động muốn reset dữ liệu và đã backup.

## 9. Chế độ Cloudflare R2 (tùy chọn cho nhóm)

Chỉ bật R2 nếu nhóm đã thống nhất và đã tạo bucket/access keys trên Cloudflare. Cập nhật `.env` bằng credentials thật:

```dotenv
S3_PROVIDER=cloudflare_r2
S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
AWS_ACCESS_KEY_ID=<R2_ACCESS_KEY_ID>
AWS_SECRET_ACCESS_KEY=<R2_SECRET_ACCESS_KEY>
AWS_REGION=auto
S3_BUCKET_NAME=vn-it-jobs
```

Thay placeholder bằng giá trị thực; không để các dấu `<...>` chưa thay thế. Trong chế độ R2, không dùng `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` làm R2 keys. Chỉ các helper được cấu hình chọn R2 mới dùng remote endpoint; lệnh `scripts/check_minio.py` vẫn kiểm tra local MinIO.

Công cụ cloud có sẵn trong repo (cần review `.env` trước khi chạy):

```powershell
python scripts/setup_cloud_storage.py
python scripts/sync_cloud_lakehouse.py --status
python scripts/sync_cloud_lakehouse.py --upload
python scripts/sync_cloud_lakehouse.py --download
```

R2 tính phí theo dung lượng và thao tác; free tier hiện tại được nêu trên bảng giá chính thức, và có thể thay đổi. Không cam kết rằng lưu trữ R2 sẽ luôn miễn phí. Xem [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/) trước khi nhóm quyết định dùng.

## 10. Troubleshooting

| Triệu chứng | Cách xử lý |
|---|---|
| Docker daemon unavailable | Mở Docker Desktop và đợi Engine running; sau đó thử lại lệnh Compose. |
| Port 9000/9001 đã dùng | Chạy `docker ps --filter publish=9000` và `docker ps --filter publish=9001`; dừng container xung đột nếu chắc chắn an toàn hoặc đổi `MINIO_API_PORT` / `MINIO_CONSOLE_PORT`. |
| Container `minio-init` exit code khác 0 | Xem `docker compose -f docker-compose.minio.yml logs minio-init`; kiểm tra log server và thông tin root user/password. |
| HTTP health endpoint trả lỗi | Mở `http://localhost:9000/minio/health/live`; kiểm tra logs và mapping cổng. |
| `InvalidAccessKeyId` / `SignatureDoesNotMatch` | Đồng bộ credentials trong `.env` với credentials mà container MinIO đang chạy; sau khi đổi credentials, recreate container bằng `docker compose ... up -d --force-recreate minio`. Không xóa volume. |
| Bucket không xuất hiện | Xem logs `minio-init`, rồi chạy `python scripts/setup_minio.py` để tạo/kiểm tra bucket. |
| Bucket rỗng | Việc tạo bucket không đồng nghĩa crawler đã chạy; kiểm tra `run.py`, logs và các key trong `raw/` / `url_ledger/`. |
| Có trạng thái unhealthy trên cấu hình cũ | Cấu hình cũ dùng healthcheck `curl` trong image server. Áp dụng Compose cập nhật có `healthcheck: disable: true`, rồi `docker compose -f docker-compose.minio.yml up -d --build`. |

## 11. License

Không cần tải một license key riêng để bật giao diện MinIO local trong cấu hình dev này. Tuy nhiên cần đọc điều khoản giấy phép của đúng bản phân phối/container image đang dùng, đặc biệt trước khi phân phối, sửa đổi hoặc triển khai dịch vụ ngoài phạm vi bài tập. Không coi “không cần license key” là miễn trừ mọi nghĩa vụ giấy phép.
