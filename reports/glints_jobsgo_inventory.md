# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ — GLINTS & JOBSGO

> **Người thực hiện:** Duy<br>
> **Nguồn phụ trách:** Glints Vietnam và JobsGO<br>
> **Nhánh Git:** `crawls/glints-jobsgo`<br>
> **Ngày kiểm kê:** Chưa chạy pipeline trên MinIO của nhóm<br>
> **Số raw snapshots:** Chưa có số liệu — điền sau khi chạy crawl<br>
> **Vùng lưu trữ:** `minio://vn-it-jobs/raw/glints/` và `minio://vn-it-jobs/raw/jobsgo/`

> **Trạng thái báo cáo:** Bản kiểm kê ban đầu dựa trên các trường mà crawler Glints hiện truy vấn và cấu trúc HTML JobsGO quan sát được. Cột tỷ lệ xuất hiện/null và số lượng bản ghi chỉ được điền từ dữ liệu thật sau khi pipeline chạy; không suy diễn thành số liệu nghiệm thu.

## 1. Phương pháp bảo toàn Raw As-Is

- Glints: lưu phản hồi GraphQL nguyên bản theo từng trang; đồng thời lưu từng đối tượng job do query hiện tại trả về. HTML chi tiết được lưu nguyên văn trong snapshot JSON. Bộ parser `JobRecord` cũ không được dùng làm Raw Zone.
- JobsGO: lưu nguyên HTML của từng trang danh mục và từng trang chi tiết; lưu thêm metadata link/card đã nhận diện để Phase 2 lấy URL và tiện tra cứu.
- Mỗi URL được chuẩn hóa tracking parameter và băm MD5 thành `url_hash`. Nội dung chi tiết được băm SHA-256 sau khi làm sạch phần nội dung chính; HTML gốc không bị sửa.
- Danh mục vòng đời và manifest được lưu trên MinIO. Manifest là JSONL theo ngày; catalog là `catalog_master.json`.

## 2. Glints — trường gốc quan sát được

Listing GraphQL endpoint: [`searchJobsV3`](https://glints.com/api/v2-alc/graphql?op=searchJobsV3). Danh sách dưới đây là **các trường query hiện tại yêu cầu API trả về**, không phải cam kết rằng đây là toàn bộ field tồn tại trong schema GraphQL riêng tư của Glints.

| Tên trường gốc | Kiểu nguồn | Ý nghĩa / vị trí | Tỷ lệ xuất hiện | Tỷ lệ Null |
|---|---|---|---:|---:|
| `id` | String/ID | ID việc làm trên listing | Chờ crawl | Chờ crawl |
| `title` | String | Chức danh trong listing | Chờ crawl | Chờ crawl |
| `createdAt`, `updatedAt` | Date/time | Thời điểm tạo/cập nhật | Chờ crawl | Chờ crawl |
| `status`, `jobSource` | String/enum | Trạng thái và nguồn tin | Chờ crawl | Chờ crawl |
| `workArrangementOption`, `type` | String/enum | Hình thức làm việc, loại việc | Chờ crawl | Chờ crawl |
| `educationLevel` | String/enum | Trình độ học vấn | Chờ crawl | Chờ crawl |
| `minYearsOfExperience`, `maxYearsOfExperience` | Number | Khoảng kinh nghiệm | Chờ crawl | Chờ crawl |
| `company.id`, `company.name`, `company.brandName` | Object/String | Danh tính công ty | Chờ crawl | Chờ crawl |
| `country.code`, `country.name` | Object/String | Quốc gia | Chờ crawl | Chờ crawl |
| `location.id`, `location.name`, `location.formattedName`, `location.parents.*` | Object/nested | Địa điểm và cấp cha | Chờ crawl | Chờ crawl |
| `salaries[].salaryType`, `salaryMode`, `minAmount`, `maxAmount`, `CurrencyCode` | List/Object | Thông tin lương nguyên gốc | Chờ crawl | Chờ crawl |
| `skills[].mustHave`, `skills[].skill.id`, `skills[].skill.name` | List/Object | Kỹ năng và cờ bắt buộc | Chờ crawl | Chờ crawl |
| `hierarchicalJobCategory.id`, `.level`, `.name` | Object | Danh mục nghề nghiệp phân cấp | Chờ crawl | Chờ crawl |
| JSON-LD `@context`, `@type`, `title`, `description`, `hiringOrganization`, `baseSalary`, `datePosted`, `validThrough`, `jobLocation`, `jobLocationType`, `employmentType`, `skills`, `jobBenefits`, `industry`, `occupationalCategory`, `experienceRequirements` | JSON trong HTML detail | Dữ liệu có cấu trúc nhúng trong trang chi tiết, nếu website cung cấp | Chờ crawl | Chờ crawl |
| Toàn bộ HTML response | HTML string | DOM nguyên bản, bao gồm các trường không có trong danh sách parse | 100% với response HTTP 200 được lưu | Không áp dụng |

**Giới hạn cần ghi nhớ:** GraphQL chỉ trả về các field được nêu trong query. Payload response được giữ nguyên hoàn toàn như API trả về, còn HTML chi tiết được giữ nguyên để bảo toàn thông tin ngoài các field query.

## 3. JobsGO — trường gốc quan sát được

Trang danh mục IT: [`viec-lam-cong-nghe-thong-tin.html`](https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html). Trang detail mẫu quan sát được theo mẫu URL `/viec-lam/<slug>-<id>.html`, ví dụ [trang detail công khai](https://jobsgo.vn/viec-lam/nhan-vien-tu-van-ban-hang-phan-mem-luong-cung-upto-10-trieu-hoa-hong-28219755589.html).

| Tên trường / DOM semantic label | Kiểu nguồn | Ý nghĩa | Tỷ lệ xuất hiện | Tỷ lệ Null |
|---|---|---|---:|---:|
| URL canonical và ID cuối URL | URL string | Định danh tin; ID lấy từ path, fallback hash URL | Chờ crawl | Chờ crawl |
| Tiêu đề tin / `h1` | DOM text | Chức danh tuyển dụng | Chờ crawl | Chờ crawl |
| Tên công ty / link công ty | DOM text + href | Nhà tuyển dụng | Chờ crawl | Chờ crawl |
| `Mức lương` | DOM text | Chuỗi lương hiển thị, kể cả “Thỏa thuận” | Chờ crawl | Chờ crawl |
| `Địa điểm` | DOM text/link | Địa điểm hoặc danh sách địa điểm | Chờ crawl | Chờ crawl |
| `Kinh nghiệm` | DOM text | Số năm/nhóm kinh nghiệm yêu cầu | Chờ crawl | Chờ crawl |
| `Bằng cấp` | DOM text | Trình độ yêu cầu | Chờ crawl | Chờ crawl |
| `Hạn nộp hồ sơ` | DOM text | Deadline và đôi khi số ngày còn lại | Chờ crawl | Chờ crawl |
| `Thời gian làm việc` | DOM text | Ca/giờ làm việc | Chờ crawl | Chờ crawl |
| `Mô tả công việc` | DOM section | Chi tiết nhiệm vụ | Chờ crawl | Chờ crawl |
| `Yêu cầu công việc` | DOM section | Điều kiện ứng viên | Chờ crawl | Chờ crawl |
| `Quyền lợi được hưởng` | DOM section | Phúc lợi | Chờ crawl | Chờ crawl |
| `Ngành nghề` | DOM text/link | Nhóm chuyên môn/danh mục | Chờ crawl | Chờ crawl |
| `Loại hình`, `Cấp bậc` | DOM text | Loại việc và cấp bậc | Chờ crawl | Chờ crawl |
| `Ngày đăng tuyển`, `Số lượng tuyển`, `Yêu cầu độ tuổi` | DOM text | Metadata bổ sung | Chờ crawl | Chờ crawl |
| Toàn bộ HTML response | HTML string | DOM nguyên bản của listing và detail | 100% với response HTTP 200 được lưu | Không áp dụng |

Selector CSS chính xác của JobsGO cần được xác nhận trên các file HTML mẫu được lưu sau khi chạy thực tế. Pipeline ưu tiên bảo toàn HTML, không phụ thuộc một selector đơn lẻ để lưu Raw Zone.

## 4. CDC / versioning

| Thống kê | Kết quả thực tế |
|---|---:|
| URL mới `NEW` / version 1 | Chưa chạy |
| URL cập nhật `UPDATED` / version > 1 | Chưa chạy |
| URL không đổi `UNCHANGED` | Chưa chạy |
| Tin đăng lại `REPOST` | Chưa chạy |
| Tin đóng `CLOSED` | Chưa chạy |
| URL lỗi `FAILED` | Chưa chạy |

## 5. Việc cần hoàn thành để chốt kiểm kê

1. Chạy Discovery cho cả hai nguồn đến hết phân trang, không đặt giới hạn `--max-pages` trong lượt kiểm kê chính thức.
2. Chạy Detail Crawl nhiều đợt đến khi hết URL `PENDING`/`RECHECK_DUE`.
3. Mở notebook `notebooks/eda_preliminary_glints_jobsgo.ipynb`, chạy phần Field Inventory và điền tỷ lệ thực tế từ catalog/snapshots.
4. Kiểm tra trực tiếp ba file HTML mẫu cho mỗi nguồn và đối chiếu key/selector; nếu có layout khác nhau, bổ sung mẫu tương ứng.
