# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — GLINTS

> **Người thực hiện:** Duy (Glints & JobsGO Source Lead)
> **Nguồn phụ trách:** Glints Vietnam (`https://glints.com/vn`)
> **Nhánh Git:** `crawls/glints-jobsgo` (merge vào `crawls/all`)
> **Ngày hoàn thành kiểm kê:** 2026-10-18
> **Tổng số URL phát hiện (URL Ledger):** 37 bài đăng (Pha 1 Discovery)
> **Số snapshot thô đã trích xuất (Pha 2 Detail):** 37 snapshot thực tế + 3 cặp HTML/JSON đối chứng (`crawlers/sources/glints/samples/`)
> **Đường dẫn lưu trữ MinIO / Local:** `minio://vn-it-jobs/raw/glints/` và `data/raw/glints/`

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

Thu thập qua GraphQL API `searchJobsV3` và SSR Detail Page:

| STT | Tên trường gốc | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `id` | String | 100% | 0% | `"job-glints-101"` | ID định danh công việc Glints |
| 2 | `title` | String | 100% | 0% | `"Senior Frontend Engineer (React, TypeScript)"` | Tiêu đề công việc |
| 3 | `company.name` | String | 100% | 0% | `"Tech Vanguard Singapore"` | Tên tổ chức tuyển dụng |
| 4 | `salary.minAmount` / `maxAmount` | Float | 56.8% | 43.2% | `25000000` / `45000000` | Mức lương min/max định lượng |
| 5 | `salary.currency` | String | 56.8% | 43.2% | `"VND"` / `"USD"` | Tiền tệ dải lương |
| 6 | `description` | HTML String | 100% | 0% | `"<p>Develop responsive web app...</p>"` | Toàn văn mô tả công việc |
| 7 | `skills` | List[Dict] | 78.4% | 21.6% | `[{"name": "React"}, {"name": "TypeScript"}]` | Kỹ năng được gắn thẻ |
| 8 | `minYearsOfExperience` | Integer | 100% | 0% | `3` | Số năm kinh nghiệm tối thiểu |
| 9 | `country` / `city` | String | 100% | 0% | `"Vietnam"` / `"Ho Chi Minh City"` | Địa điểm làm việc |
| 10 | `isRemote` | Boolean | 100% | 0% | `true` | Cờ báo hiệu làm việc từ xa |
| 11 | `content_hash` | String (SHA256) | 100% | 0% | `"31fe89a2..."` | Clean Container HTML/GraphQL Hash |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Chu kỳ Re-crawl:** Kiểm tra chu kỳ 21 ngày với `is_due_for_recrawl(last_scraped_at, days=21)`.
- **Trạng thái URL Ledger:** Duy trì `PENDING`, `DONE`, `FAILED`, `CLOSED`.
- **Safe Skip:** Tích hợp bộ bắt lỗi GraphQL rate limiting (HTTP 403/429) tiếp tục cào an toàn.
