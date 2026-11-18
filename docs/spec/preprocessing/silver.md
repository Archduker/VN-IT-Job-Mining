# Bảng Silver (bảng target)

> Danh sách trường, kiểu, ý nghĩa và cột nguồn của bảng 04 là **hợp đồng**, ghi ở [spec 05 mục 4.4](../05_preprocessing_spec.md) (người dùng chốt 17/11/2026, bổ sung 18/11/2026: 26 trường). File này chỉ đặc tả **cách dựng** và **cách kiểm** bảng đó.
> Code: chưa có (luật S1 ở [`04_normalization.md`](04_normalization.md), PRE-39). Trang đối chiếu: `docs/presentation/preprocessing_steps/silver_gap.html` (hiện là trang giữ chỗ).
> Prompt: gộp vào [`docs/prompting/preprocessing/04_normalization.md`](../../prompting/preprocessing/04_normalization.md).

## 1. Mục đích

- BI, Monitoring và báo cáo cần một bảng gọn: một dòng một tin, tên cột tiếng Anh, mỗi khái niệm một cột, không có bản phụ.
- Từ 18/11 có thêm 3 cờ mà SD1 cần (`seniority_inferred`, `exp_inferred`, `salary_outlier`) và `employment_type`. Với 26 trường này, BI trả lời được đủ 7 câu SD1 mà không phải đọc bảng 04 (mục 6b).
- Bảng 04 (`all.parquet`) vẫn là bảng làm việc, vì Processing 07–10 và Mining đang đọc theo tên cột cũ.

## 2. Luật

| Mã | Luật |
|---|---|
| S1 | Chọn đúng các cột trong spec 05 mục 4.4, đổi tên theo cột "Lấy từ cột bảng 04". **Không tính lại giá trị** |
| S2 | `work_mode` thiếu thì ghi `unknown`, không để null (spec 05 mục 4.4) |
| S3 | `employment_type` vào Silver (người dùng đổi quyết định 18/11, bỏ điều kiện 100%). Tin không rõ để null; độ phủ ghi ở `silver_gap.html` |
| S4 | Thứ tự cột đúng như bảng ở mục 4.4. Kiểu dữ liệu đúng như cột "Kiểu" |

## 3. Quy trình xử lý

1. Đọc `data/preprocessing/04_normalization/all.parquet`.
2. Với mỗi trường trong mục 4.4: lấy cột nguồn và đổi tên. Cột nguồn không tồn tại thì **dừng và báo**, không tạo cột rỗng. Đây là cách bảng Silver lộ ra chỗ thiếu.
3. Ép kiểu: `posted_month` là chuỗi `YYYY-MM`; `salary_negotiable`, `salary_outlier`, `seniority_inferred`, `exp_inferred` là bool (không có null); `skills`, `benefits` là list chuỗi.
4. Ghi `data/preprocessing/04_normalization/silver.parquet`.
5. Ghi trang đối chiếu `silver_gap.html`: với từng trường, cột có hay không, độ phủ theo nguồn, kiểu, 3 giá trị mẫu, đánh dấu `có` / `thiếu cột` / `phủ thấp` / `lệch kiểu`, và bước gây ra chỗ thiếu.

## 4. Input → Output

| | Đường dẫn |
|---|---|
| Input | `data/preprocessing/04_normalization/all.parquet` |
| Output | `data/preprocessing/04_normalization/silver.parquet` (26 cột) |
| Trang | `docs/presentation/preprocessing_steps/silver_gap.html` |

## 5. Dữ liệu mẫu

Điền khi có bảng. Kỳ vọng cho tin mẫu `topcv_2325743`:

| Trường | Giá trị kỳ vọng |
|---|---|
| `job_id` | topcv_2325743 |
| `source` | topcv |
| `title` | Backend Developer |
| `salary_min`, `salary_max` | 10.160.000, 22.860.000 (nếu không bị cap) |
| `salary_negotiable` | false |
| `salary_outlier` | false |
| `seniority_inferred` | false (cấp "Nhân viên" lấy từ ô của sàn) |
| `exp_inferred` | false (1 năm lấy từ ô của sàn) |
| `employment_type` | full_time |
| `exp_min_years` | 1,0 |
| `province` | TP. Hà Nội |
| `work_mode` | onsite |
| `language` | en |
| `posted_month` | 2026-10 (từ `date_posted` 2026-10-08, đọc từ 18/11) |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Số dòng Silver = số dòng bảng 04 | Bằng nhau |
| `job_id` duy nhất | 0 trùng |
| Mọi trường của mục 4.4 có mặt, đúng kiểu | 26/26 |
| Giá trị trùng với cột nguồn của bảng 04 | So từng cột, 0 khác |

### 6b. Silver đủ cho SD1 chưa

| Câu SD1 | Trường Silver | Ghi chú |
|---|---|---|
| 1.1 Nhóm nghề × sàn | `job_family`, `source` | |
| 1.2 Cấp bậc | `seniority`, `seniority_inferred` | Báo riêng phần suy ra |
| 1.3 Tỉnh, hình thức | `province`, `work_mode`, `employment_type` | |
| 1.4 Lương | `salary_min`, `salary_max`, `salary_negotiable`, `salary_outlier` | Trạng thái lương: có số / thỏa thuận / không rõ, suy từ 3 cột đầu |
| 1.5 Người mới | `seniority`, `exp_min_years`, `exp_inferred`, `skills`, `language`, lương | So kinh nghiệm chỉ trên tin `exp_inferred` = false |
| 1.6 Phúc lợi | `benefits` | |
| 1.7 Theo tháng | `posted_month`, `source`, `job_family`, `seniority` | Tin trước 09/2026 đã bị C9 bỏ ở bước 01 |

## 7. Chỗ thiếu đã biết

Trước khi dựng bảng, ngày 18/11:

| Trường | Chỗ thiếu | Bước | Mã |
|---|---|---|---|
| `posted_month` | Chưa có cột | 03 T3b | PRE-37 |
| `work_mode` | Đang suy từ địa điểm, mặc định onsite | 03 T9a + 04 N14 | — |
| `exp_min_years` | topdev 27,9%; itviec là mức gom | 03 T9c + 04 M4 | — |
| `skills` | Nguồn đang là `skills_std` (PRE-40). Nhãn ngành TopCV đã bỏ ở 02 (18/11) | 04 | PRE-40 |
| `employment_type` | Chưa có cột; 6,6% tin không rõ (topdev 198/202) | 04 N19 | — |
| `seniority_inferred`, `exp_inferred`, `salary_outlier` | Có ở bảng 04 (tên cũ), chỉ cần S1 đổi tên | S1 | PRE-39 |
| `benefits` | Từ điển 10 nhóm; phúc lợi tiếng Anh không khớp | 03 T7 | PRE-41 |
