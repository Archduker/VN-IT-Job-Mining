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
