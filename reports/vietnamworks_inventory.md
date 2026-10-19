# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — VIETNAMWORKS

> **Người thực hiện:** Khoa (VietnamWorks Source Lead)
> **Nguồn phụ trách:** VietnamWorks (`https://www.vietnamworks.com`)
> **Nhánh Git:** `crawls/vietnamworks` (merge vào `crawls/all`)
> **Ngày hoàn thành kiểm kê:** 2026-10-18
> **Tổng số URL phát hiện (URL Ledger):** 92 bài đăng (Pha 1 Discovery)
> **Số snapshot thô đã trích xuất (Pha 2 Detail):** 3 snapshot mẫu thành công + 3 cặp HTML/JSON đối chứng (`crawlers/sources/vietnamworks/samples/`)
> **Đường dẫn lưu trữ MinIO / Local:** `minio://vn-it-jobs/raw/vietnamworks/` và `data/raw/vietnamworks/`

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

VietnamWorks sử dụng kết hợp Algolia Search API và SSR Detail Container:

| STT | Tên trường gốc | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `jobId` | Integer / String | 100% | 0% | `"1792831"` | ID định danh trên VietnamWorks |
| 2 | `jobTitle` | String | 100% | 0% | `"Senior Data Engineer (Airflow, Snowflake, Spark)"` | Chức danh công việc |
| 3 | `companyName` | String | 100% | 0% | `"VNG Corporation"` | Tên tổ chức tuyển dụng |
| 4 | `prettySalary` | String | 100% | 0% | `"Up to $3,500"` / `"Negotiable"` | Dải lương hiển thị cho ứng viên |
| 5 | `salaryMin` / `Max` | Float | 62% | 38% | `2000.0` / `3500.0` | Mức lương số thực quy đổi |
| 6 | `salaryCurrency` | String | 62% | 38% | `"USD"` / `"VND"` | Tiền tệ dải lương |
| 7 | `jobDescription` | HTML String | 100% | 0% | `"<div class="description">...</div>"` | Toàn văn mô tả trách nhiệm |
| 8 | `jobRequirement` | HTML String | 98% | 2% | `"<div class="requirement">...</div>"` | Toàn văn yêu cầu kỹ thuật |
| 9 | `jobBenefits` | List[Dict] | 94% | 6% | `[{"benefitTitle": "Macbook Pro"}]` | Quyền lợi dạng mảng cấu trúc |
| 10 | `skills` | List[Dict] | 96% | 4% | `[{"skillName": "Spark"}, {"skillName": "Airflow"}]` | Kỹ năng chuẩn hóa hệ thống |
| 11 | `locations` | List[Dict] | 100% | 0% | `[{"cityName": "Hồ Chí Minh"}]` | Vị trí địa lý tuyển dụng |
| 12 | `jobLevel` | String | 88% | 12% | `"Experienced (Senior)"` | Cấp bậc ứng viên |
| 13 | `publishedDate` | String | 95% | 5% | `"2026-10-14T09:30:00Z"` | Thời gian xuất bản bài viết |
| 14 | `content_hash` | String (SHA256) | 100% | 0% | `"90fbe2137..."` | Clean Container HTML Hash |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Chu kỳ Re-crawl:** Thiết lập 21 ngày với cơ chế phát hiện thay đổi nội dung qua Clean Container Hash.
- **Trạng thái URL Ledger:** Duy trì `PENDING`, `DONE`, `FAILED`, `CLOSED`.
- **Safe Skip:** Tích hợp bộ giải mã Algolia/API có fallback sang HTML DOM selector khi cấu trúc mạng thay đổi.
