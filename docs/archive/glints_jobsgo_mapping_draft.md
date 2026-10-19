# BẢNG ÁNH XẠ TÍCH HỢP DỮ LIỆU — GLINTS & JOBSGO

> **Người thực hiện:** Duy
> **Nguồn:** Glints Vietnam và JobsGO
> **Nhánh Git:** `crawls/glints-jobsgo`
> **Mục đích:** Đề xuất map sang Common Target Schema trong Integration Summit. Raw Zone giữ nguyên bản gốc; phép ánh xạ chỉ chạy ở Staging/Curated.

## 1. Bảng đối chiếu trường về Common Target Schema

| Trường đích | Bắt buộc | Glints — trường nguồn | JobsGO — trường nguồn | Quy tắc staging đề xuất |
|---|---|---|---|---|
| `job_id_global` | Có | `id` GraphQL | ID số cuối URL detail; nếu không có thì hash URL | Tạo khóa nguồn `glints:<id>` / `jobsgo:<id>`; không dùng ID đơn lẻ xuyên sàn |
| `source_platform` | Có | Hằng `glints` | Hằng `jobsgo` | String lowercase |
| `job_title` | Có | GraphQL `title`, fallback JSON-LD `title` | DOM `h1`/tiêu đề card | Strip whitespace, giữ title raw riêng nếu cần |
| `company_name` | Có | `company.brandName`, `company.name`, JSON-LD `hiringOrganization.name` | Link/tên công ty trong card hoặc detail | Giữ raw company; chuẩn hóa alias ở integration layer |
| `job_description_raw` | Có | JSON-LD `description` nếu có; toàn bộ raw HTML luôn giữ | DOM section “Mô tả công việc”; toàn bộ raw HTML luôn giữ | Không drop HTML ở Raw; trường clean là trường dẫn xuất riêng |
| `salary_min_vnd` | Không/nullable | `salaries[].minAmount` hoặc JSON-LD `baseSalary.value.minValue` | Chuỗi “Mức lương” trong DOM, có thể “Từ …”, range hoặc thỏa thuận | Parse ở staging; xác định currency/period; lưu raw salary text và đơn vị gốc |
| `salary_max_vnd` | Không/nullable | `salaries[].maxAmount` hoặc JSON-LD `maxValue` | Chuỗi lương trên card/detail | Không suy diễn cận min/max nếu nguồn chỉ nêu một cận; lưu giá trị số ở đơn vị triệu VND sau chuẩn hóa |
| `salary_currency` | Không/nullable | `CurrencyCode` / JSON-LD `baseSalary.currency` | Đơn vị ghi cạnh mức lương, thường VNĐ khi có hiển thị | Không mặc định nếu không xác định được |
| `is_salary_negotiable` | Có (derived) | So sánh label/chuỗi lương gốc; field API có thể null | Chuỗi “Thỏa thuận/Thoả thuận” | Boolean dẫn xuất; unknown không được biến thành lương 0 |
| `min_experience_years` | Không/nullable | `minYearsOfExperience` hoặc `experienceRequirements.monthsOfExperience` | Label `Kinh nghiệm` | Parse có đơn vị; “Không yêu cầu” thành 0 chỉ ở staging theo quyết định nhóm |
| `work_location_city` | Không/nullable | `location.formattedName`, `location.parents`, JSON-LD `jobLocation.address` | Label/link `Địa điểm` | Chuẩn hóa tỉnh/thành; giữ danh sách location gốc khi có nhiều nơi |
| `employment_type` | Không/nullable | `type` / JSON-LD `employmentType` | Label `Loại hình` | Map về Full-time/Part-time/Internship… và giữ raw label |
| `seniority_level` | Không/nullable | `hierarchicalJobCategory` và kinh nghiệm | Label `Cấp bậc` | Map riêng khỏi năm kinh nghiệm; không suy Senior chỉ từ title mà không ghi confidence |
| `raw_skill_tags` | Không/nullable | `skills[].skill.name` | Kỹ năng có cấu trúc nếu có; ngành nghề/danh mục và nội dung JD vẫn ở raw HTML | Giữ danh sách nguyên văn; không trộn taxonomy AI vào raw tags |
| `posted_date` | Không/nullable | `createdAt` / JSON-LD `datePosted` | Label `Ngày đăng tuyển` | Parse sang ISO date ở staging; raw timestamp giữ nguyên |
| `deadline_date` | Không/nullable | JSON-LD `validThrough` | Label `Hạn nộp hồ sơ` | Parse ngày nếu rõ ràng; không suy ngày hết hạn từ thời gian còn lại nếu chưa kiểm chứng |
| `cdc_version` | Có | Version snapshot của Raw pipeline | Version snapshot của Raw pipeline | Lấy `_meta.version`; giữ toàn bộ lịch sử thay đổi |
| `extended_attributes` | Có | `status`, `jobSource`, `educationLevel`, `workArrangementOption`, category và toàn bộ GraphQL payload | `Thời gian làm việc`, `Bằng cấp`, `Số lượng tuyển`, `Yêu cầu độ tuổi`, ngành nghề và DOM fields đặc thù | Lưu JSON linh hoạt; không ép trường đặc thù thành cột chung khi chưa thống nhất |

## 2. Trường đặc thù nên giữ trong `extended_attributes`

### Glints
- `status`, `jobSource`, `educationLevel`, `workArrangementOption`.
- `company.id`, `country.*`, `location.parents`, `hierarchicalJobCategory.*`.
- `salaryType`, `salaryMode`, `mustHave`, kỹ năng nguyên bản và JSON-LD properties không có cột chung.
- Tham chiếu object key của listing payload và metadata truy vết HTTP.

### JobsGO
- Thời gian/ca làm việc, địa chỉ chi tiết, bằng cấp, số lượng cần tuyển và yêu cầu độ tuổi.
- Danh mục ngành nghề và cấp bậc theo nhãn gốc.
- Các khối mô tả/yêu cầu/phúc lợi theo HTML; không chỉ lưu một đoạn văn đã nối.

## 3. Các trường có thể thiếu hoặc cần kiểm tra

| Trường đích | Rủi ro thiếu | Xử lý đề xuất |
|---|---|---|
| `salary_min_vnd`, `salary_max_vnd` | Tin không công khai số lương; chu kỳ/tiền tệ có thể không rõ | Để NULL, tạo `is_salary_negotiable`/`salary_disclosure_type`, không impute tại Raw |
| `min_experience_years` | Nhãn dạng nhóm hoặc không nêu | Parse có kiểm định; nếu không chắc giữ NULL và raw label |
| `work_location_city` | Remote, nhiều địa điểm, địa chỉ mới/thay đổi hành chính | Giữ raw text + normalized city, cho phép nhiều địa điểm |
| `raw_skill_tags` | JobsGO có thể không có tag kỹ năng riêng trong card | Để NULL nếu không có tag thực; trích skills từ JD ở cột `extracted_skills` tầng Curated |
| `posted_date` / `deadline_date` | DOM hiển thị nhiều định dạng hoặc phần “còn N ngày” | Giữ chuỗi gốc; chỉ chuyển sang datetime nếu parse đáng tin cậy |

## 4. Quy tắc tích hợp và chất lượng

1. Không xóa trường raw khi normalize; mọi biến đổi phải sinh trường dẫn xuất bên cạnh raw.
2. Tiền tệ lương chỉ quy đổi khi currency rõ. Quy tắc tỷ giá dùng chung (nếu áp dụng) phải được Integration Summit chốt và ghi kèm ngày/tỷ giá.
3. Không coi hai URL là hai cơ hội độc lập chỉ vì ID khác nhau. Dùng CDC hash/repost trong cùng nguồn và bước semantic dedup xuyên nguồn ở Curated.
4. Không merge bản ghi chỉ dựa trên title; cần công ty, similarity mô tả và thời gian đăng để giảm false positive.
5. Lưu key tham chiếu giữa `url_ledger`, raw listing payload và raw detail snapshot để audit/re-process.
