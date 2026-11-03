# P4. Normalization: 34 tỉnh, nhãn tiếng Việt, outlier, log lương, gộp nguồn

> Trạng thái: **đã làm, chạy thật 03/11/2026** (8.378 → 8.378, chưa gọi JEV). Sửa sau review 03/11 ở mục 8.
> Cần P3 xong trước. Prompt: `docs/prompting/P4_normalization.md`.

## 1. Ngữ cảnh

| Vấn đề | Số liệu | Mã |
|---|---|---|
| Phân loại theo chuỗi con | "ba" khớp "backend", "intern" khớp "international"; bộ golden cũ có 1.214 tin BA/Product, phần lớn xếp sai | PRE-1, F3 |
| Chuẩn hóa chạy trước imputer | Không còn áp dụng: imputer Gemini đã bỏ ở P3. P4 tự xử lý ô thiếu bằng luật + JEV | PRE-2 |
| Tên tỉnh nhiều kiểu, còn dùng tên cũ | "Hà Nội" 2.111 / "Ha Noi" 509; "Hồ Chí Minh" 1.741 / "Ho Chi Minh" 351; raw còn tên tỉnh trước sáp nhập (Bình Dương, Quảng Nam…) | PRE-3, E4 |
| Cấp bậc mỗi nguồn một bộ từ | VietnamWorks 4 giá trị, TopCV 7; ITviec, Glints, TopDev không có | F2 |
| Cùng công ty khác cách viết | VietnamWorks 15 nhóm, TopCV 12 ("CÔNG TY CỔ PHẦN CÔNG NGHỆ KIOTVIET" / "Công ty Cổ phần Công nghệ KiotViet") | I4 |

Code sửa PRE-1 (khớp từ nguyên vẹn) đã có test, đang ở git stash "preprocessing: so khớp theo từ + chuẩn hóa sau imputer (hoãn)". Lấy phần khớp từ, không viết lại.

## 2. Input

`data/preprocessing/03_transformation/<nguồn>.parquet`.

## 3. Output

- `data/preprocessing/04_normalization/<nguồn>.parquet` và `all.parquet` gộp 8 nguồn.
- Chép `all.parquet` thành `data/curated/curated_flat_golden_jobs.parquet` (tên Monitoring đang đọc).
- **Giá trị chuẩn viết bằng tiếng Việt.** Thuật ngữ ngành giữ tiếng Anh (Junior, Senior, Backend, DevOps…). Tên cột vẫn tiếng Anh như các bước trước.
- Cột mới (giữ mọi cột cũ):

| Cột | Giá trị |
|---|---|
| `locations` (cập nhật) | mỗi phần tử thêm `tinh_thanh` chuẩn (1 trong 34), `tinh_cu` (tên trong raw, nếu khác), `tinh_key` (mã), cờ `ngoai_vn` / `remote` |
| `tinh_chinh` | `tinh_thanh` của địa điểm đầu tiên |
| `seniority` | 1 trong 6 nhãn: "Thực tập", "Mới tốt nghiệp", "Junior", "Middle", "Senior", "Trưởng nhóm/Quản lý"; không xác định được thì "Chưa rõ" |
| `seniority_source`, `seniority_prob` | `raw` / `title` / `kinh_nghiem` / `jev`; xác suất khi dùng JEV |
| `job_family` | 1 trong 12 nhóm nghề chuẩn (bảng dưới) hoặc "Khác" |
| `job_family_source`, `job_family_prob` | như trên |
| `skills_std` | kỹ năng theo tên chuẩn trong `skills.json` ("reactjs", "React.js" → "React") |
| `company_norm` | tên công ty chuẩn hóa (`normalize_company_name`) |
| `salary_min_vnd_capped`, `salary_max_vnd_capped` | sau winsorize 1% – 99% |
| `log_salary_min`, `log_salary_max` | `log(1 + salary_capped)` |
| `is_outlier_salary` | bool |

12 nhóm nghề (đề xuất, bạn duyệt): Backend, Frontend, Fullstack, Mobile, Data/AI, DevOps/Cloud, Kiểm thử (QA/QC), Bảo mật, Hệ thống/Mạng, Phân tích nghiệp vụ (BA), Quản lý sản phẩm/dự án, Thiết kế UI/UX.

## 4. Hướng xử lý (đúng thứ tự)

### N1. Tỉnh/thành: 34 đơn vị sau sáp nhập (hiệu lực 01/07/2025)

Bảng `preprocessing/dictionaries/provinces_34.json` (file mới) lấy theo danh sách bạn cung cấp. Mỗi tỉnh có `key`, tên chuẩn, các tỉnh cũ gộp vào, và bí danh. Bí danh gồm tên không dấu, viết tắt, có hoặc không có "TP." / "Tỉnh" ("HCM", "TP.HCM", "Sài Gòn", "Ha Noi", "HN").

| # | Tỉnh/thành mới | Gộp từ |
|---|---|---|
| 1 | Tuyên Quang | Hà Giang, Tuyên Quang |
| 2 | Cao Bằng | giữ nguyên |
| 3 | Lai Châu | giữ nguyên |
| 4 | Lào Cai | Lào Cai, Yên Bái |
| 5 | Thái Nguyên | Bắc Kạn, Thái Nguyên |
| 6 | Điện Biên | giữ nguyên |
| 7 | Lạng Sơn | giữ nguyên |
| 8 | Sơn La | giữ nguyên |
| 9 | Phú Thọ | Hòa Bình, Vĩnh Phúc, Phú Thọ |
| 10 | Bắc Ninh | Bắc Giang, Bắc Ninh |
| 11 | Quảng Ninh | giữ nguyên |
| 12 | TP. Hà Nội | giữ nguyên |
| 13 | TP. Hải Phòng | Hải Dương, TP. Hải Phòng |
| 14 | Hưng Yên | Thái Bình, Hưng Yên |
| 15 | Ninh Bình | Hà Nam, Ninh Bình, Nam Định |
| 16 | Thanh Hóa | giữ nguyên |
| 17 | Nghệ An | giữ nguyên |
| 18 | Hà Tĩnh | giữ nguyên |
| 19 | Quảng Trị | Quảng Bình, Quảng Trị |
| 20 | TP. Huế | giữ nguyên (Thừa Thiên Huế) |
| 21 | TP. Đà Nẵng | Quảng Nam, TP. Đà Nẵng |
| 22 | Quảng Ngãi | Quảng Ngãi, Kon Tum |
| 23 | Gia Lai | Gia Lai, Bình Định |
| 24 | Đắk Lắk | Phú Yên, Đắk Lắk |
| 25 | Khánh Hòa | Khánh Hòa, Ninh Thuận |
| 26 | Lâm Đồng | Đắk Nông, Lâm Đồng, Bình Thuận |
| 27 | Đồng Nai | Bình Phước, Đồng Nai |
| 28 | TP. Hồ Chí Minh | Bình Dương, TP. Hồ Chí Minh, Bà Rịa - Vũng Tàu |
| 29 | Tây Ninh | Long An, Tây Ninh |
| 30 | Đồng Tháp | Tiền Giang, Đồng Tháp |
| 31 | An Giang | Kiên Giang, An Giang |
| 32 | Vĩnh Long | Bến Tre, Vĩnh Long, Trà Vinh |
| 33 | TP. Cần Thơ | Sóc Trăng, Hậu Giang, TP. Cần Thơ |
| 34 | Cà Mau | Bạc Liêu, Cà Mau |

Danh sách bạn dán ghi "TP. Bắc Ninh", "TP. Quảng Ninh", "TP. Đồng Nai". Theo hiểu biết của mình về Nghị quyết 202/2025/QH15, chỉ có 6 thành phố trực thuộc trung ương: Hà Nội, Hải Phòng, Huế, Đà Nẵng, Hồ Chí Minh, Cần Thơ. Ba nơi kia là tỉnh. Bảng ghi theo cách này, **bạn kiểm lại với văn bản gốc**. Tên chỉ là nhãn hiển thị, đổi tên không làm đổi `key`.

Luật:

- Bỏ dấu, chữ thường, bỏ "tp", "tỉnh", "thành phố", rồi tra bí danh. Tên cũ đổi sang tên mới, giữ tên cũ ở `tinh_cu`.
  - "Bình Dương" → `tinh_thanh="TP. Hồ Chí Minh"`, `tinh_cu="Bình Dương"`.
  - "Vũng Tàu" → "TP. Hồ Chí Minh".
  - "Quảng Nam" → "TP. Đà Nẵng".
- "Remote", "Làm việc từ xa" → `tinh_thanh=null`, `remote=true`.
- Tên nước hoặc thành phố nước ngoài (Singapore, Tokyo, Nhật Bản…) → `tinh_thanh=null`, `ngoai_vn=true`.
- **Phường/xã:** giữ chữ đã tách ở P3, chưa chuẩn hóa. Sau sáp nhập còn khoảng 3.321 phường/xã, và repo chưa có danh mục chính thức. Việc mở: bạn cung cấp nguồn danh mục (hoặc đồng ý dùng một bộ dữ liệu công khai) thì thêm `phuong_xa_key`.

### N2–N9

| Mã | Luật | Ví dụ trước → sau |
|---|---|---|
| N2 | Cấp bậc theo thứ tự: luật **theo từ nguyên vẹn** trên `raw_seniority_text` → trên tiêu đề → theo số năm kinh nghiệm (0 → Mới tốt nghiệp, 1–2 → Junior, 3–4 → Middle, ≥ 5 → Senior) → JEV `choice` 6 nhãn (chỉ khi các bước trước không ra, có `--use-api`). JEV prob < 0,5 → "Chưa rõ" | "Trưởng phòng" → "Trưởng nhóm/Quản lý" (`raw`); "Senior Java" → "Senior" (`title`) |
| N3 | Nhóm nghề: luật theo từ nguyên vẹn trên tiêu đề + `skills_std` (PRE-1) → JEV `choice` 12 nhóm + "Khác" khi luật không ra. prob < 0,5 → "Khác" | "Backend Developer" → "Backend", không còn ra BA |
| N4 | Kỹ năng: ánh xạ về tên chuẩn bằng `skills.json` (P3), bỏ trùng | "ReactJS" → "React" |
| N5 | Công ty: `company_norm` | "Cty CP A" / "CÔNG TY CỔ PHẦN A" → "a" |
| N6 | Outlier lương: sửa lỗi nhập (`fix_common_salary_input_errors`) → IQR để gắn cờ → winsorize 1–99% (`outlier_handler.py`). Không xóa dòng. Ngưỡng tính trên toàn bộ 8 nguồn | 2 tỷ/tháng → cap về mức 99% |
| N7 | Log lương **sau** N6 (`log_transformer.py`) | 20tr → 16,81 |
| N8 | Gộp 8 nguồn thành `all.parquet` | |
| N9 | Khử trùng mờ (`cross_deduplicator.py`, Jaccard + TF-IDF): **mặc định tắt**. Bật thì chỉ báo cáo 30 cặp điểm cao để review, chưa bỏ dòng | |

## 5. Ranh giới

- Không bỏ dòng.
- Không ghi đè cột `raw_*` hay cột của P3; luôn thêm cột mới. Riêng `locations` chỉ được thêm khóa vào từng phần tử, không xóa khóa cũ.
- Không scale trước khi xử lý outlier (N6 trước N7).
- JEV chỉ chọn trong danh sách nhãn đã duyệt. Không thêm nhãn mới.

## 6. Monitoring thấy gì

- Tỉnh: bảng "chữ gốc → tỉnh chuẩn" theo số tin, trong đó tách riêng các dòng **tên cũ → tên mới**. Đếm số tin `remote`, `ngoai_vn`, không nhận được. Bản đồ cột 34 tỉnh.
- Cấp bậc, nhóm nghề: phân bố theo nguồn và theo `*_source` (bao nhiêu do luật, bao nhiêu do JEV); so với bộ golden cũ (vd. BA/Product 1.214 → x).
- Lương: histogram trước/sau cap và sau log; số tin bị cap.
- Khối API: số lần gọi JEV, số lần trúng cache, chi phí.
- Đây là bước đầu tiên có view "toàn bộ dữ liệu gộp" thật.

## 7. Tiêu chí xong và cách review

- `provinces_34.json` có đủ 34 tỉnh; mọi tỉnh cũ trong bảng trên đều tra ra đúng tỉnh mới.
- Không còn cặp tên có dấu / không dấu riêng; không còn tên tỉnh cũ ở `tinh_thanh`.
- Review nhóm nghề: 50 tin ngẫu nhiên (seed 42), bạn gán nhãn tay, đúng ≥ 90%. Tách độ đúng phần luật và phần JEV.
- Review cấp bậc: bảng chéo `raw_seniority_text` × `seniority` cho VietnamWorks và TopCV.
- Test (JEV mock):
  - "Ha Noi" = "Hà Nội";
  - "Bình Dương" → "TP. Hồ Chí Minh" và `tinh_cu="Bình Dương"`;
  - "Remote" → `remote=true`;
  - N2 dùng luật trước JEV;
  - JEV prob 0,4 → "Chưa rõ";
  - N6 không đổi số dòng;
  - N7 chạy sau N6.

## 8. Sửa sau review 03/11/2026

| Mục | Trước | Sau |
|---|---|---|
| Input/Output | file theo nguồn, gộp ở N8 | đọc/ghi `all.parquet` (gộp từ P2) |
| N1 tỉnh | `tinh_chinh` = phần tử đầu dù null; tên "Bắc Ninh", "Quảng Ninh", "Đồng Nai" | `tinh_chinh` = tỉnh đầu tiên khác null; theo danh mục chính thức (03/2026) ba tỉnh này là thành phố: "TP. Bắc Ninh", "TP. Quảng Ninh", "TP. Đồng Nai" |
| N2 cấp bậc | "Nhân viên"/"Chuyên viên" → Middle: 54% tin là Middle | bỏ qua các nhãn này; không xác định → null. Middle còn 10,4%; 1.465 tin để trống |
| N2b JEV | `choice` tự gán nhãn khi luật không ra | chỉ `noul` kiểm nhãn của luật; prob < 0,5 → `seniority_can_kiem` / `job_family_can_kiem` |
| N6 lương | winsorize để lại 2 tỷ/tháng và 0đ | N6a: ngoài 1–500 triệu/tháng → NaN + `salary_suspect` trước IQR. Sau cap: 3–101,6 triệu |
| Ghi file | chép đè `data/curated/curated_flat_golden_jobs.parquet` | không chép; file golden cũ giữ nguyên |
