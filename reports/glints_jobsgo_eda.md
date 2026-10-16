# BÁO CÁO EDA SƠ BỘ — GLINTS & JOBSGO

> **Người thực hiện:** Duy<br>
> **Nguồn:** Glints Vietnam và JobsGO<br>
> **Notebook:** `notebooks/eda_preliminary_glints_jobsgo.ipynb`<br>
> **MinIO:** `minio://vn-it-jobs/raw/glints/`, `minio://vn-it-jobs/raw/jobsgo/`<br>
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

## 3. Chất lượng và tình trạng dữ liệu

| Chỉ tiêu | Glints | JobsGO | Nguồn số liệu |
|---|---:|---:|---|
| Số URL trong catalog | Chưa chạy | Chưa chạy | `url_ledger/<source>/catalog_master.json` |
| Số snapshot version mới nhất | Chưa chạy | Chưa chạy | `raw/<source>/..._v*.json` |
| Tỷ lệ lương công khai dạng số (%) | Chưa chạy | Chưa chạy | Notebook EDA |
| Tỷ lệ lương thương lượng / không công khai (%) | Chưa chạy | Chưa chạy | HTML/GraphQL raw |
| Tỷ lệ thiếu địa điểm (%) | Chưa chạy | Chưa chạy | Snapshot raw |
| Tỷ lệ thiếu kinh nghiệm (%) | Chưa chạy | Chưa chạy | Snapshot raw |
| Tỷ lệ thiếu mô tả (%) | Chưa chạy | Chưa chạy | Snapshot raw |

Không nên ghi các số ước lượng từ số trang kết quả tìm kiếm vào bảng này; chỉ ghi số đo trên raw snapshot đã thu thập và kiểm chứng.

## 4. Ngoại lai IQR

Sử dụng Q1, Q3, IQR = Q3 − Q1; cận dưới `max(0, Q1 − 1.5*IQR)` và cận trên `Q3 + 1.5*IQR`. Chỉ áp dụng cho mẫu có `salary_min`/`salary_max` hợp lệ sau quy đổi về **triệu VND/tháng**. Không ép lương “thỏa thuận” vào phân phối số.

| Chỉ số | Glints | JobsGO |
|---|---:|---:|
| Số bản ghi có lương số chuẩn hóa | Chưa chạy | Chưa chạy |
| Q1 / Median / Q3 lương tối thiểu | Chưa chạy | Chưa chạy |
| IQR và cận ngoài | Chưa chạy | Chưa chạy |
| Số và tỷ lệ outlier | Chưa chạy | Chưa chạy |

## 5. Biểu đồ bắt buộc trong notebook

1. Histogram phân phối lương min/max (triệu VND/tháng).
2. Boxplot lương để xem ngoại lai IQR.
3. Bar chart Top 15 kỹ năng/thẻ kỹ năng quan sát được.
4. Biểu đồ tỷ lệ công khai lương theo nguồn.
5. Bar chart Missing Rate của các trường chính theo nguồn.

## 6. So sánh sơ bộ giữa hai nền tảng

- **Glints:** listing cung cấp dữ liệu có cấu trúc qua GraphQL cho chức danh, công ty, địa điểm, lương, kỹ năng, kinh nghiệm và category. Chi tiết tin có thể chứa JSON-LD `JobPosting`, nhưng mức độ đầy đủ cần đo theo từng bản ghi.
- **JobsGO:** trang SSR hiển thị các nhãn như mức lương, địa điểm, kinh nghiệm, bằng cấp, hạn hồ sơ, mô tả, yêu cầu, phúc lợi, ngành nghề, loại hình, cấp bậc và ngày đăng. Các trường cần đọc từ DOM có thể có layout khác nhau; nguyên HTML được lưu làm căn cứ tái trích xuất.
- Chưa kết luận sàn nào công khai lương nhiều hơn trước khi chạy thống kê trên cùng cách định nghĩa `salary_public_numeric`.

## 7. Cách chạy và cập nhật số liệu

1. Khởi động MinIO theo `docker-compose.minio.yml` và xác nhận bucket `vn-it-jobs` đã có dữ liệu.
2. Chạy tất cả cell trong notebook theo thứ tự.
3. Dùng `summary_by_source`, `missing_rate_table`, `iqr_summary` và các biểu đồ để thay các ô “Chưa chạy” bằng kết quả thật.
4. Ghi lại ngày chạy, phạm vi URL, số record loại trùng và số snapshot lỗi trong báo cáo cuối.
