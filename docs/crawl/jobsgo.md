# Phân tích crawler Glints Vietnam và JobsGO

> Phụ trách: Duy — nhánh local `crawls/glints-jobsgo`
> Nguyên tắc: Raw-As-Is, lưu trữ MinIO, tách Discovery/Detail, Safe Skip, CDC và re-crawl 21 ngày.

## 1. Mục tiêu và phạm vi

Crawler thu thập URL tin tuyển dụng, lưu listing payload/HTML thô vào MinIO và dùng catalog để quản lý trạng thái URL. Dữ liệu raw phải được giữ nguyên để có thể tái phân tích; việc bóc tách trường, quy đổi lương, nhận diện kỹ năng và chuẩn hóa schema là bước EDA/Staging sau đó.

Hai nguồn chạy độc lập:

- **Glints Vietnam:** listing qua GraphQL operation `searchJobsV3`; chi tiết lưu HTML response và dữ liệu listing gắn với tin.
- **JobsGO:** listing/category SSR HTML `https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html`; tin chi tiết theo mẫu path `/viec-lam/<slug>-<id>.html`.

## 2. Glints — GraphQL

### 2.1. Discovery

- Endpoint được crawler hiện tại dùng: `https://glints.com/api/v2-alc/graphql?op=searchJobsV3`.
- Query dùng lại `SEARCH_QUERY` từ `crawlers/sources/glints/crawler.py`, gồm ID, tiêu đề, ngày tạo/cập nhật, công ty, quốc gia, địa điểm lồng nhau, lương, kỹ năng, loại việc, kinh nghiệm và category.
- Duyệt page theo `hasMore`; ghi page request/response JSON vào `raw/glints/_listing/<date>/`.
- URL tin được tạo từ ID và slug tiêu đề; `url_hash`/canonical URL do hàm chung trong `crawlers.common.url_ledger` quản lý.

### 2.2. Detail và lưu raw

- Tải HTML của từng URL mới/đến hạn; status 404/410 chuyển `CLOSED`, status bất thường hoặc body rỗng chuyển `FAILED` và không làm dừng các URL còn lại.
- Nội dung nguyên bản được lưu trong `raw.html`. Nếu HTTP client cung cấp `response.content`, bytes được giữ thêm dưới dạng Base64 để hỗ trợ tái lập.
- Hash CDC dùng nội dung đã loại bỏ một số thành phần dễ thay đổi cùng một tập trường listing ổn định. Việc làm sạch chỉ phục vụ hash, không sửa HTML raw.

### 2.3. Giới hạn

GraphQL chỉ trả về các field mà query yêu cầu; không tuyên bố query hiện tại là toàn bộ schema riêng tư của Glints. Khi cần field khác, hãy kiểm tra schema/response được phép dùng và thêm field có căn cứ, không tự bịa field name. HTML detail vẫn được giữ làm bản gốc.

## 3. JobsGO — SSR HTML

### 3.1. Discovery

- Crawl trang danh mục IT và các link pagination có thể nhận diện được trong DOM.
- Chỉ nhận link detail khớp mẫu URL của tin JobsGO để tránh theo các link SEO không liên quan.
- Lưu listing HTML nguyên bản và bản Base64 của response bytes khi có; metadata thẻ tin được lưu riêng để Phase 2 tra cứu.
- Nếu người dùng truyền `--max-pages`, lượt discovery là scan một phần và không được dùng để đánh dấu tin vắng mặt là `CLOSED`.

### 3.2. Detail và selector

- Lưu trọn HTML response của detail page; parser EDA thử tìm các nhãn có ý nghĩa như chức danh, công ty, lương, địa điểm, kinh nghiệm, cấp bậc và mô tả.
- CSS selector cụ thể có thể thay đổi. Vì vậy dữ liệu raw không phụ thuộc việc parser nhận diện thành công; hãy cập nhật selector sau khi kiểm tra các snapshot thực tế.
- Mục kỹ năng lấy bằng keyword scan là đặc trưng dẫn xuất, không được ghi nhầm thành field tags nguyên bản của JobsGO.

### 3.3. Khả năng bị chặn

Trong một lần chạy được quan sát ở môi trường phát triển, listing JobsGO trả HTTP **403**. Đây là hạn chế xác thực/quyền truy cập hoặc kiểm soát của website, không phải bằng chứng rằng website không có tin tuyển dụng. Khi gặp lại 403:

1. Ghi trạng thái crawl/error trong log và dừng xác nhận độ phủ hoàn chỉnh.
2. Không tìm cách vượt qua biện pháp kiểm soát truy cập.
3. Kiểm tra có API/feed/cách truy cập chính thức được website hoặc giảng viên cho phép không; nếu chưa có, báo rõ blocker và không tạo số liệu giả.

## 4. MinIO key layout

```text
vn-it-jobs/
├── url_ledger/<source>/catalog_master.json
├── url_ledger/<source>/manifests/manifest_YYYY-MM-DD.jsonl
├── url_ledger/<source>/discovery_miss_counts.json
└── raw/<source>/
    ├── _listing/YYYY-MM-DD/...
    ├── _listing/current/<job_id>.json
    └── YYYY-MM-DD/<job_id>_v<version>.json
```

S3 prefix là tên khóa logic, không phải thư mục vật lý. Bucket được giữ private theo mặc định. Không dùng `docker compose down -v` khi chỉ cần restart, vì lệnh đó có thể xóa named volume lưu dữ liệu.

## 5. Chu trình vận hành

```powershell
# Khởi động MinIO (giữ nguyên named volume)
docker compose -f .\docker-compose.minio.yml up -d --build
python scripts/check_minio.py

# Discovery trước; lượt chính thức không giới hạn max-pages
python run.py --source glints --phase discover
python run.py --source jobsgo --phase discover

# Detail: --max-items giới hạn số URL xử lý trong lượt
python run.py --source glints --phase detail --max-items 30
python run.py --source jobsgo --phase detail --max-items 30

# Chạy EDA từ snapshot thật đã lưu trong MinIO
python scripts/run_glints_jobsgo_eda.py
```

Tiếp tục Phase 2 nhiều lượt cho đến khi catalog không còn URL `PENDING`/`RECHECK_DUE` có thể xử lý. Chỉ tạo file sample bàn giao từ raw detail thật sau khi cả hai nguồn có ít nhất ba snapshot hợp lệ:

```powershell
python scripts/export_glints_jobsgo_samples.py
```

Thư mục sample có sẵn trong gói là **synthetic test fixtures** để unit-test parser/pipeline; không được báo cáo như sản phẩm crawl thật. Trường hợp JobsGO vẫn 403 thì chưa thể hoàn tất mẫu thật cho nguồn này — ghi nhận blocker thay vì dùng fixture để thay thế.

## 6. CDC và lifecycle

- URL mới: `PENDING`.
- Detail mới thành công: snapshot version 1 và `DONE`.
- `DONE` chưa đủ 21 ngày: bỏ qua.
- `DONE` đến hạn: crawl lại; hash không đổi thì không sinh snapshot mới; hash đổi thì tăng version.
- 404/410: `CLOSED`.
- Lỗi tạm thời: `FAILED`, có thể retry theo quy tắc pipeline.
- Chỉ scan đủ toàn bộ trang mới được tăng bộ đếm vắng mặt; ba lượt full scan liên tiếp vắng mặt mới đóng tin theo thiết lập mặc định.
- URL tương đương nội dung tin đã biết có thể được đánh dấu repost; không xóa raw snapshot đã có.

## 7. Kiểm tra sau cài đặt

```powershell
python -m compileall -q crawlers run.py scripts
python -m pytest tests/unit/test_glints_jobsgo_pipeline.py tests/unit/test_minio_init.py -q
python scripts/check_minio.py
```

Unit tests dùng HTTP response và MinIO store giả lập; chúng không chứng minh website live đã cho phép cào. Chỉ kết quả của lần chạy trên MinIO thực và log/HTTP status mới là bằng chứng thu thập thực tế.
