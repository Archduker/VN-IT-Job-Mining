# Bảng Silver (bảng target)

> Danh sách trường, kiểu, ý nghĩa và cột nguồn của bảng 04 là **hợp đồng**, ghi ở [spec 05 mục 4.4](../05_preprocessing_spec.md) (người dùng chốt 17/11/2026). File này chỉ đặc tả **cách dựng** và **cách kiểm** bảng đó.
> Code: chưa có (luật S1 ở [`04_normalization.md`](04_normalization.md), PRE-39). Trang đối chiếu: `docs/presentation/preprocessing_steps/silver_gap.html` (hiện là trang giữ chỗ).
> Prompt: gộp vào [`docs/prompting/preprocessing/04_normalization.md`](../../prompting/preprocessing/04_normalization.md).

## 1. Mục đích

- BI, Monitoring và báo cáo cần một bảng gọn: một dòng một tin, tên cột tiếng Anh, mỗi khái niệm một cột, không có cờ và bản phụ.
- Bảng 04 (`all.parquet`) vẫn là bảng làm việc, vì Processing 07–10 và Mining đang đọc theo tên cột cũ.

## 2. Luật

| Mã | Luật |
|---|---|
| S1 | Chọn đúng các cột trong spec 05 mục 4.4, đổi tên theo cột "Lấy từ cột bảng 04". **Không tính lại giá trị** |
| S2 | `work_mode` thiếu thì ghi `unknown`, không để null (spec 05 mục 4.4) |
| S3 | `employment_type` **chưa vào** Silver. Người dùng chốt 18/11: chỉ thêm khi trích được cho 100% tin. Đo lại sau khi chạy 03 mới |
| S4 | Thứ tự cột đúng như bảng ở mục 4.4. Kiểu dữ liệu đúng như cột "Kiểu" |

## 3. Quy trình xử lý

1. Đọc `data/preprocessing/04_normalization/all.parquet`.
2. Với mỗi trường trong mục 4.4: lấy cột nguồn và đổi tên. Cột nguồn không tồn tại thì **dừng và báo**, không tạo cột rỗng. Đây là cách bảng Silver lộ ra chỗ thiếu.
3. Ép kiểu: `posted_month` là chuỗi `YYYY-MM`; `salary_negotiable` là bool; `skills`, `benefits` là list chuỗi.
4. Ghi `data/preprocessing/04_normalization/silver.parquet`.
5. Ghi trang đối chiếu `silver_gap.html`: với từng trường, cột có hay không, độ phủ theo nguồn, kiểu, 3 giá trị mẫu, đánh dấu `có` / `thiếu cột` / `phủ thấp` / `lệch kiểu`, và bước gây ra chỗ thiếu.

## 4. Input → Output

| | Đường dẫn |
|---|---|
| Input | `data/preprocessing/04_normalization/all.parquet` |
| Output | `data/preprocessing/04_normalization/silver.parquet` (22 cột) |
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
| `exp_min_years` | 1,0 |
| `province` | TP. Hà Nội |
| `work_mode` | onsite |
| `language` | en |
| `posted_month` | 2026-10 |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Số dòng Silver = số dòng bảng 04 | Bằng nhau |
| `job_id` duy nhất | 0 trùng |
| Mọi trường của mục 4.4 có mặt, đúng kiểu | 22/22 |
| Giá trị trùng với cột nguồn của bảng 04 | So từng cột, 0 khác |

## 7. Chỗ thiếu đã biết

Trước khi dựng bảng, ngày 18/11:

| Trường | Chỗ thiếu | Bước | Mã |
|---|---|---|---|
| `posted_month` | Chưa có cột | 03 T3b | PRE-37 |
| `work_mode` | Đang suy từ địa điểm, mặc định onsite | 03 T9a + 04 N14 | — |
| `exp_min_years` | topdev 28,2%; itviec là mức gom | 03 T9c + 04 M4 | — |
| `skills` | Nguồn đang là `skills_std`; TopCV lẫn nhãn ngành | 02, 04 | PRE-40 |
| `benefits` | Từ điển 10 nhóm; phúc lợi tiếng Anh không khớp | 03 T7 | PRE-41 |
