# BÁO CÁO EDA SƠ BỘ — GLINTS & JOBSGO

> **Người thực hiện:** Duy
> **Nguồn:** Glints Vietnam và JobsGO
> **Notebook:** `notebooks/eda_preliminary_glints_jobsgo.ipynb`
> **MinIO:** `minio://vn-it-jobs/raw/glints/`, `minio://vn-it-jobs/raw/jobsgo/`
> **Trạng thái:** Khung báo cáo chuẩn bị trước; số liệu phải được sinh từ snapshot thực tế, chưa điền số liệu giả.

## 1. Câu hỏi phân tích

1. Tỷ lệ công khai lương dạng con số khác nhau thế nào giữa Glints và JobsGO?
2. Tỷ lệ thiếu lương, kinh nghiệm, địa điểm và mô tả của mỗi sàn là bao nhiêu?
3. Phân phối lương (khi chuyển đổi được đơn vị và chu kỳ trả lương) có lệch phải hay chứa ngoại lai IQR không?
4. Những kỹ năng/danh mục nào xuất hiện thường xuyên trong dữ liệu thô, và mức độ đầy đủ của trường kỹ năng giữa hai sàn ra sao?

## 2. Phạm vi và quy tắc

- Đơn vị quan sát là một URL/tin tuyển dụng trong catalog. Snapshot lịch sử được giữ lại cho CDC; EDA cơ cấu thị trường nên chỉ dùng version mới nhất theo `url_hash`, tránh đếm một tin đã cập nhật nhiều lần thành nhiều cơ hội việc làm.
- Lương không được ép thành 0. “Thỏa thuận/Thoả thuận” là lương không công khai bằng con số; đây không phải giá trị 0 và không được impute bằng trung bình trong bước Raw.
- Các giá trị số chỉ được đưa vào phân tích so sánh khi quy đổi được tiền tệ và chu kỳ trả lương có căn cứ. Bản gốc vẫn được bảo toàn trong MinIO.
- Outlier IQR là “ngoại lai nghi vấn”, không đồng nghĩa lỗi dữ liệu. Trước khi loại/capping phải kiểm tra đơn vị tiền tệ, lương theo tháng/năm và đặc điểm nghề nghiệp.

## 3. Kết quả chạy trên dữ liệu thật

Chạy `python scripts/run_glints_jobsgo_eda.py` hoặc chạy toàn bộ notebook `notebooks/eda_preliminary_glints_jobsgo.ipynb`. Script cập nhật tự động khối bên dưới, sinh CSV và biểu đồ trong `reports/generated/`. Không copy số liệu từ synthetic fixtures.

<!-- BEGIN AUTO-GENERATED EDA RESULTS -->

# Kết quả EDA thực nghiệm — Glints & JobsGO

- **Thời điểm chạy (UTC):** `2026-10-18 07:52:54 UTC`
- **Endpoint:** `http://localhost:9000` | **Bucket:** `vn-it-jobs`
- **Đơn vị phân tích:** snapshot version mới nhất theo `source_job_id`; snapshot listing, test fixture và HTML sample không tham gia thống kê.
- **Nguyên tắc lương:** không gán 0 cho lương thiếu/thỏa thuận; chỉ so sánh theo tháng khi period + currency nhận diện được; USD chỉ quy đổi nếu `FX_VND_PER_USD` được đặt rõ trong `.env`.

## 1. Tổng quan theo nguồn

| Nguồn | URL catalog | Latest snapshots | Lương số | Lương thương lượng | Thiếu lương | Lương tháng so sánh được | FAILED ledger | Listing errors | Lỗi listing gần nhất |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| glints | 37 | 37 | 21 (56.76%) | 0 | 16 | 21 | 0 | 2 | HTTP 403 |
| jobsgo | 0 | 0 | 0 (N/A (no snapshots)) | 0 | 0 | 0 | 0 | 1 | HTTP 403 |

## 2. Missing rate các trường chính

| Nguồn | Trường | Record | Thiếu | Missing rate |
|---|---|---:|---:|---:|
| glints | `title` | 37 | 0 | 0.00% |
| glints | `company` | 37 | 0 | 0.00% |
| glints | `salary_text` | 37 | 16 | 43.24% |
| glints | `location` | 37 | 0 | 0.00% |
| glints | `min_experience_years` | 37 | 0 | 0.00% |
| glints | `description_chars` | 37 | 0 | 0.00% |
| glints | `skill_tags_raw` | 37 | 8 | 21.62% |
| jobsgo | `title` | 0 | 0 | N/A |
| jobsgo | `company` | 0 | 0 | N/A |
| jobsgo | `salary_text` | 0 | 0 | N/A |
| jobsgo | `location` | 0 | 0 | N/A |
| jobsgo | `min_experience_years` | 0 | 0 | N/A |
| jobsgo | `description_chars` | 0 | 0 | N/A |
| jobsgo | `skill_tags_raw` | 0 | 0 | N/A |

## 3. Lương ngoại lai — IQR

Đơn vị: triệu VND/tháng; bảng chỉ có giá trị khi tiền tệ và kỳ trả lương đủ rõ.

| Nguồn | Trường | n | Q1 | Median | Q3 | IQR | Cận dưới | Cận trên | Outlier | Tỷ lệ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| glints | `salary_min_million_vnd_month` | 21 | 10.000 | 12.000 | 20.000 | 10.000 | 0.000 | 35.000 | 3 | 14.29% |
| glints | `salary_max_million_vnd_month` | 20 | 11.875 | 17.000 | 31.250 | 19.375 | 0.000 | 60.312 | 0 | 0.00% |
| jobsgo | `salary_min_million_vnd_month` | 0 | N/A | N/A | N/A | N/A | N/A | N/A | 0 | N/A |
| jobsgo | `salary_max_million_vnd_month` | 0 | N/A | N/A | N/A | N/A | N/A | N/A | 0 | N/A |

## 4. Từ khóa kỹ năng (heuristic, không phải taxonomy chuẩn)

| Kỹ năng | Số tin có từ khóa | Tỷ lệ lũy tích trên lượt nhắc |
|---|---:|---:|
| Agile | 9 | 3.18% |
| Java | 7 | 5.65% |
| AWS | 7 | 8.13% |
| Docker | 7 | 10.60% |
| CI/CD | 7 | 13.07% |
| Python | 7 | 15.55% |
| MySQL | 6 | 17.67% |
| Scrum | 6 | 19.79% |
| Azure | 6 | 21.91% |
| Git | 6 | 24.03% |
| JavaScript | 5 | 25.80% |
| PHP | 5 | 27.56% |
| Linux | 5 | 29.33% |
| PostgreSQL | 5 | 31.10% |
| Customer Service | 5 | 32.86% |
| English Language | 4 | 34.28% |
| C# | 4 | 35.69% |
| SQL | 4 | 37.10% |
| Machine Learning | 3 | 38.16% |
| Quality Assurance | 3 | 39.22% |

## 5. Biểu đồ được tạo

- `reports/generated/figures/01_salary_distribution.png`
- `reports/generated/figures/02_experience_salary_relationship.png`
- `reports/generated/figures/03_salary_dispersion_by_source.png`
- `reports/generated/figures/04_pearson_correlation.png`
- `reports/generated/figures/05_spearman_correlation.png`
- `reports/generated/figures/06_skills_pareto.png`
- `reports/generated/figures/07_salary_disclosure_by_source.png`
- `reports/generated/figures/08_missing_rate_by_source.png`

## 6. Raw field/HTML selector inventory

- Tổng mục trường/selector quan sát được: **477** (field JSON và selector HTML được báo cáo riêng).
- `presence_rate_pct` đo số snapshot có field/selector; `non_null_rate_pct` chỉ áp dụng trường JSON. `absent_rate_pct` phân biệt với field có nhưng null/empty.

## 7. Lỗi đọc snapshot

Số đối tượng không đọc/parse được: **0**.

## 8. Diễn giải và giới hạn

- Đây là EDA trên dữ liệu thực sự hiện diện trong MinIO ở thời điểm chạy, không phải ước lượng độ phủ của toàn website.
- Không so sánh mức lương nếu currency/period chưa xác định; tỷ lệ lương dạng số có thể cao hơn tỷ lệ lương tháng so sánh được.
- IQR đánh dấu điểm nghi vấn chứ không khẳng định dữ liệu sai; cần đối chiếu HTML gốc trước mọi xử lý outlier.
- Skill frequency dùng keyword-boundary scan từ title/description/HTML; rà soát thủ công trước khi dùng cho phân tích thị trường chính thức.
- Nếu một nguồn có 0 snapshot, phần trăm của nguồn đó là N/A; cần xử lý blocker crawl (ví dụ HTTP 403/selector thay đổi) trước khi so sánh hai nguồn.

<!-- END AUTO-GENERATED EDA RESULTS -->

## 4. Phương pháp Missing Rate và ngoại lai IQR

Missing rate được tính trên snapshot detail mới nhất của mỗi URL/source job ID; field thiếu, explicit null, chuỗi rỗng và list rỗng được coi là missing cho các trường nghiệp vụ tương ứng. Raw selector inventory phân biệt trường JSON **có mặt** với trường có mặt nhưng null/empty.

Sử dụng Q1, Q3, IQR = Q3 − Q1; cận dưới `max(0, Q1 − 1.5*IQR)` và cận trên `Q3 + 1.5*IQR`. Chỉ áp dụng cho `salary_min`/`salary_max` đủ căn cứ quy đổi về **triệu VND/tháng**. Outlier là tín hiệu rà soát HTML/raw gốc, không phải lệnh tự động xóa hay winsorize dữ liệu.

## 5. Nhóm biểu đồ EDA bắt buộc

1. **Distribution:** histogram lương tháng có thể so sánh.
2. **Relationship:** scatter kinh nghiệm yêu cầu với cận lương tối đa tháng; xu hướng tuyến tính chỉ mang tính mô tả.
3. **Dispersion/Outlier:** boxplot lương tháng theo nguồn và bảng IQR.
4. **Correlation:** ma trận tương quan Pearson và Spearman cho trường số đủ dữ liệu.
5. **Categorical frequency/Pareto:** tần suất keyword kỹ năng và tỷ lệ tích lũy.

Bổ sung: bar chart missing rate và tỷ lệ tin có lương số. Mỗi biểu đồ ghi rõ khi thiếu dữ liệu; không được tạo quan sát giả để làm đầy chart.

## 6. So sánh sơ bộ giữa hai nền tảng

- **Glints:** listing cung cấp dữ liệu có cấu trúc qua GraphQL cho chức danh, công ty, địa điểm, lương, kỹ năng, kinh nghiệm và category. Chi tiết tin có thể chứa JSON-LD `JobPosting`, nhưng mức độ đầy đủ cần đo theo từng bản ghi.
- **JobsGO:** trang SSR hiển thị các nhãn như mức lương, địa điểm, kinh nghiệm, bằng cấp, hạn hồ sơ, mô tả, yêu cầu, phúc lợi, ngành nghề, loại hình, cấp bậc và ngày đăng. Các trường cần đọc từ DOM có thể có layout khác nhau; nguyên HTML được lưu làm căn cứ tái trích xuất.
- Chưa kết luận sàn nào công khai lương nhiều hơn trước khi chạy thống kê trên cùng cách định nghĩa `salary_public_numeric`.

## 7. Cách chạy và cập nhật số liệu

1. Khởi động MinIO theo `docker-compose.minio.yml` và xác nhận bucket `vn-it-jobs` đã có dữ liệu.
2. Chạy `python scripts/run_glints_jobsgo_eda.py` hoặc **Run All** notebook.
3. Đối chiếu `reports/generated/glints_jobsgo_eda_summary_YYYY-MM-DD.md`, các CSV và PNG; script tự cập nhật khối kết quả ở trên.
4. Ghi lại ngày chạy, phạm vi URL, số record loại trùng và số snapshot lỗi trong báo cáo cuối.
