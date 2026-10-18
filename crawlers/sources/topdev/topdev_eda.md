# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) - TOPDEV

> **Người thực hiện:** Sơn  
> **Nguồn phụ trách:** Topdev - https://topdev.vn/
> **Nhánh Git:** `feature/topdev-son`  
> **Ngày hoàn thành cào:** 2026-10-17
> **Tổng số bài đăng cào được (Raw Records):** 2819  
> **Đường dẫn thư mục Local:** `VN-IT-Job-Mining\crawlers\sources\topdev`

## 1. Tổng quan

- Nguồn dữ liệu: TopDev.
- Số lượng tin tuyển dụng: 2.819.
- Số lượng trường: 69.
- `listing_response`: thông tin tin tuyển dụng trong danh sách.
- `detail_response`: thông tin chi tiết của tin tuyển dụng.

## 2. Ý nghĩa các trường dữ liệu

| Index | Tên cột                                           | Ý nghĩa                                                                                         |
| ----: | ------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
|     0 | `category_ids`                                    | Danh sách mã danh mục được gán cho tin tuyển dụng.                                              |
|     1 | `listing_response.id`                             | Mã định danh tin tuyển dụng.                                                                    |
|     2 | `listing_response.title`                          | Tiêu đề hoặc chức danh tuyển dụng.                                                              |
|     3 | `listing_response.is_content_image`               | Cho biết nội dung tin có sử dụng hình ảnh hay không.                                            |
|     4 | `listing_response.is_content_image_enabled`       | Trạng thái bật tính năng nội dung dạng hình ảnh.                                                |
|     5 | `listing_response.owned_id`                       | Mã định danh đối tượng sở hữu tin tuyển dụng.                                                   |
|     6 | `listing_response.company.id`                     | Mã định danh nhà tuyển dụng.                                                                    |
|     7 | `listing_response.company.display_name`           | Tên hiển thị của công ty tuyển dụng.                                                            |
|     8 | `listing_response.company.image_logo`             | URL hình ảnh logo công ty.                                                                      |
|     9 | `listing_response.company.slug`                   | Chuỗi định danh công ty dùng trong URL.                                                         |
|    10 | `listing_response.company.detail_url`             | URL trang thông tin nhà tuyển dụng.                                                             |
|    11 | `listing_response.company.is_followed`            | Cho biết tài khoản thu thập dữ liệu có theo dõi công ty hay không.                              |
|    12 | `listing_response.skills_str`                     | Danh sách kỹ năng dưới dạng chuỗi văn bản.                                                      |
|    13 | `listing_response.skills_arr`                     | Danh sách kỹ năng dưới dạng mảng.                                                               |
|    14 | `listing_response.experiences_str`                | Thông tin kinh nghiệm làm việc theo định dạng chuỗi.                                            |
|    15 | `listing_response.contract_types_str`             | Loại hợp đồng lao động, ví dụ Fulltime.                                                         |
|    16 | `listing_response.job_types_str`                  | Hình thức làm việc, ví dụ Trực tiếp.                                                            |
|    17 | `listing_response.job_levels_str`                 | Cấp bậc tuyển dụng dưới dạng chuỗi.                                                             |
|    18 | `listing_response.job_levels_arr`                 | Danh sách cấp bậc tuyển dụng dưới dạng mảng.                                                    |
|    19 | `listing_response.addresses.address_region_ids`   | Danh sách mã định danh khu vực tuyển dụng.                                                      |
|    20 | `listing_response.addresses.address_region_array` | Danh sách tên khu vực tuyển dụng.                                                               |
|    21 | `listing_response.addresses.collection_addresses` | Danh sách đối tượng địa chỉ chi tiết, có thể chứa tỉnh, quận, phường, đường và tọa độ.          |
|    22 | `listing_response.addresses.full_addresses`       | Danh sách địa chỉ làm việc đầy đủ.                                                              |
|    23 | `listing_response.addresses.sort_addresses`       | Địa chỉ rút gọn dùng cho hiển thị hoặc sắp xếp.                                                 |
|    24 | `listing_response.addresses.address_region_list`  | Tên khu vực tuyển dụng, ví dụ Thành phố Hà Nội.                                                 |
|    25 | `listing_response.detail_url`                     | URL trang chi tiết tin tuyển dụng.                                                              |
|    26 | `listing_response.slug`                           | Chuỗi định danh tin tuyển dụng dùng trong URL.                                                  |
|    27 | `listing_response.salary.min_estimate`            | Trường lương tối thiểu ước tính; cần xác minh quy tắc tạo giá trị.                              |
|    28 | `listing_response.salary.currency_estimate`       | Đơn vị tiền tệ gắn với thông tin lương ước tính.                                                |
|    29 | `listing_response.salary.unit`                    | Đơn vị tính lương, ví dụ MONTH.                                                                 |
|    30 | `listing_response.salary.min`                     | Mức lương tối thiểu được ghi nhận.                                                              |
|    31 | `listing_response.salary.max`                     | Mức lương tối đa được ghi nhận.                                                                 |
|    32 | `listing_response.salary.min_filter`              | Giá trị lương tối thiểu phục vụ lọc hoặc tìm kiếm.                                              |
|    33 | `listing_response.salary.is_negotiable`           | Cờ thể hiện trạng thái thương lượng lương; dữ liệu mẫu sử dụng chuỗi "0" hoặc "1".              |
|    34 | `listing_response.salary.currency`                | Đơn vị tiền tệ của mức lương.                                                                   |
|    35 | `listing_response.salary.max_filter`              | Giá trị lương tối đa phục vụ lọc hoặc tìm kiếm.                                                 |
|    36 | `listing_response.salary.value`                   | Giá trị lương dạng hiển thị, ví dụ khoảng lương hoặc "Thương lượng".                            |
|    37 | `listing_response.salary.max_estimate`            | Trường lương tối đa ước tính; cần xác minh quy tắc tạo giá trị.                                 |
|    38 | `listing_response.is_salary_visible`              | Trạng thái cho biết thông tin lương được đánh dấu là hiển thị hay không.                        |
|    39 | `listing_response.published.date`                 | Ngày đăng tin tuyển dụng.                                                                       |
|    40 | `listing_response.published.datetime`             | Ngày và thời gian đăng tin theo định dạng nguồn dữ liệu.                                        |
|    41 | `listing_response.published.since`                | Thời gian tương đối kể từ khi đăng, ví dụ 1 ngày trước.                                         |
|    42 | `listing_response.is_applied`                     | Trạng thái tài khoản đã ứng tuyển vào tin tuyển dụng hay chưa.                                  |
|    43 | `listing_response.is_followed`                    | Trạng thái tài khoản có theo dõi tin tuyển dụng hay không.                                      |
|    44 | `listing_response.is_blacklisted`                 | Trạng thái tin tuyển dụng có nằm trong danh sách chặn hay không.                                |
|    45 | `listing_response.recalled_at`                    | Thời điểm thu hồi tin tuyển dụng, nếu có.                                                       |
|    46 | `listing_response.is_remove_cv`                   | Trường trạng thái liên quan đến CV; ý nghĩa nghiệp vụ chính xác cần xác minh.                   |
|    47 | `listing_response.is_viewed`                      | Trạng thái tin tuyển dụng đã được tài khoản xem hay chưa.                                       |
|    48 | `listing_response.promotions`                     | Thông tin quảng bá hoặc khuyến mãi gắn với tin, nếu có.                                         |
|    49 | `detail_response.id`                              | Mã định danh tin tuyển dụng trong dữ liệu chi tiết.                                             |
|    50 | `detail_response.is_content_image`                | Cho biết nội dung chi tiết có sử dụng hình ảnh hay không.                                       |
|    51 | `detail_response.is_content_image_enabled`        | Trạng thái bật tính năng nội dung dạng hình ảnh trong dữ liệu chi tiết.                         |
|    52 | `detail_response.content`                         | Nội dung mô tả tổng quan của tin tuyển dụng.                                                    |
|    53 | `detail_response.benefits_v2`                     | Danh sách quyền lợi theo cấu trúc dữ liệu phiên bản mới.                                        |
|    54 | `detail_response.responsibilities`                | Mô tả trách nhiệm và nhiệm vụ công việc.                                                        |
|    55 | `detail_response.owned_id`                        | Mã định danh đối tượng sở hữu tin trong dữ liệu chi tiết.                                       |
|    56 | `detail_response.is_salary_visible`               | Trạng thái hiển thị lương trong dữ liệu chi tiết.                                               |
|    57 | `detail_response.is_applied`                      | Trạng thái tài khoản đã ứng tuyển hay chưa trong dữ liệu chi tiết.                              |
|    58 | `detail_response.is_followed`                     | Trạng thái theo dõi tin trong dữ liệu chi tiết.                                                 |
|    59 | `detail_response.is_blacklisted`                  | Trạng thái chặn tin trong dữ liệu chi tiết.                                                     |
|    60 | `detail_response.recalled_at`                     | Thời điểm thu hồi tin trong dữ liệu chi tiết, nếu có.                                           |
|    61 | `detail_response.is_remove_cv`                    | Trường trạng thái liên quan đến CV trong dữ liệu chi tiết; cần xác minh.                        |
|    62 | `detail_response.is_viewed`                       | Trạng thái đã xem tin trong dữ liệu chi tiết.                                                   |
|    63 | `detail_response.requirements_arr`                | Mảng yêu cầu tuyển dụng có cấu trúc; có thể null dù nội dung yêu cầu vẫn tồn tại ở trường khác. |
|    64 | `detail_response.responsibilities_original`       | Nội dung trách nhiệm công việc ở dạng gốc.                                                      |
|    65 | `detail_response.requirements_original`           | Nội dung yêu cầu ứng viên ở dạng gốc, có thể gồm kỹ năng, kinh nghiệm, học vấn và chứng chỉ.    |
|    66 | `detail_response.benefits_original`               | Danh sách quyền lợi ở cấu trúc gốc, có thể chứa các trường icon và value.                       |
|    67 | `detail_response.recruitment_process_original`    | Thông tin quy trình tuyển dụng ở dạng gốc, nếu có.                                              |
|    68 | `detail_response.promotions`                      | Thông tin quảng bá hoặc khuyến mãi trong dữ liệu chi tiết, nếu có.                              |

## 3. Lưu ý khi phân tích

- Giá trị null hoặc thiếu dữ liệu không đồng nghĩa với giá trị bằng 0.
- Các trường lương có thể chứa số, chuỗi hoặc giá trị biểu thị thương lượng; cần chuẩn hóa trước khi tính toán.
- `skills_str` và `skills_arr` biểu diễn cùng nhóm thông tin kỹ năng theo hai định dạng khác nhau.
- `responsibilities` và `responsibilities_original` có thể chứa nội dung tương tự nhau.
- `benefits_v2` và `benefits_original` có cấu trúc khác nhau; cần kiểm tra trước khi gộp.
- Các trường trạng thái như `is_applied`, `is_followed`, `is_viewed` có thể phản ánh tài khoản thu thập dữ liệu thay vì đặc điểm chung của tin tuyển dụng.
- Các trường có toàn bộ giá trị null trong tập dữ liệu hiện tại cần được xem xét khi làm sạch dữ liệu.
- Ý nghĩa nghiệp vụ chưa thể xác nhận chỉ từ giá trị mẫu phải được kiểm tra thêm bằng tài liệu API hoặc mã nguồn crawler.

## 4. Đánh Giá Khuyết Thiếu Dữ Liệu (Missing Values Analysis)

Phân tích trên 2.819 tin và 69 trường cho thấy dữ liệu thiếu tập trung ở một số trường chi tiết; không nên mặc định giá trị thiếu là 0 hoặc tự điền trước khi xác định ý nghĩa nghiệp vụ.

| Trường                                                         |            Thiếu |   Tỷ lệ |
| -------------------------------------------------------------- | ---------------: | ------: |
| `listing_response.recalled_at`                                 |            2.819 | 100,00% |
| `listing_response.promotions`                                  |            2.819 | 100,00% |
| `detail_response.recruitment_process_original`                 |            2.819 | 100,00% |
| `detail_response.recalled_at`                                  |            2.819 | 100,00% |
| `detail_response.promotions`                                   |            2.819 | 100,00% |
| `detail_response.requirements_arr`                             |            2.818 |  99,96% |
| `detail_response.content`                                      |            1.959 |  69,49% |
| `listing_response.skills_str` và `listing_response.skills_arr` | 1.578 mỗi trường |  55,98% |
| `detail_response.requirements_original`                        |                6 |   0,21% |
| `detail_response.benefits_v2`                                  |                4 |   0,14% |
| Một số trường địa chỉ, loại công việc và trách nhiệm           |     2 mỗi trường |   0,07% |

**Nhận xét:** Hai trường kỹ năng có cùng tỷ lệ thiếu vì biểu diễn cùng nhóm dữ liệu. `requirements_arr` gần như luôn thiếu, trong khi `requirements_original` có dữ liệu ở 2.813 tin; nên ưu tiên kiểm tra trường gốc thay vì loại tin. Các trường thiếu 100% chưa cung cấp giá trị phân tích trong snapshot này.

## 5. Thống Kê Ngoại Lai Mức Lương Theo Tiền Tệ

Áp dụng quy tắc IQR (ngoài khoảng `Q1 - 1,5 × IQR` đến `Q3 + 1,5 × IQR`) riêng cho từng loại tiền tệ và từng trường lương; chỉ tính các giá trị số lớn hơn 0. Không quy đổi hoặc gộp VND với USD.

| Tiền tệ | Trường          | Số tin có lương hợp lệ | Số giá trị ngoại lai |
| ------- | --------------- | ---------------------: | -------------------: |
| VND     | Lương tối thiểu |                    995 |                   66 |
| VND     | Lương tối đa    |                    980 |                   61 |
| USD     | Lương tối thiểu |                     36 |                    8 |
| USD     | Lương tối đa    |                     48 |                    4 |

Có **99 tin duy nhất** chứa ít nhất một giá trị ngoại lai; tổng số ngoại lai theo từng trường lớn hơn số tin vì một tin có thể ngoại lai ở cả lương tối thiểu và tối đa. Notebook ghi nhận một số giá trị rất lớn ở nhóm USD (ví dụ 70.000.000 và 120.000.000); cần đối chiếu đơn vị/tiền tệ với dữ liệu nguồn trước khi diễn giải hoặc xử lý. Không nên tự động xóa các tin này.

## 6. Top 15 Kỹ Năng Xuất Hiện Nhiều Nhất

Notebook ghi nhận 329 giá trị kỹ năng khác nhau. Bảng dưới đây đếm số lần xuất hiện sau khi trải phẳng `skills_arr`; nhãn bị rút gọn ở bảng đầu ra notebook đã được đối chiếu với snapshot dữ liệu.

| Hạng | Kỹ năng                                                            | Số lần |
| ---: | ------------------------------------------------------------------ | -----: |
|    1 | Sales                                                              |    261 |
|    2 | Marketing                                                          |    160 |
|    3 | Business Development                                               |    156 |
|    4 | Business/Sales                                                     |    150 |
|    5 | Kế toán                                                            |    110 |
|    6 | HR                                                                 |     68 |
|    7 | Customer Service/Customer Support                                  |     65 |
|    8 | Giảng dạy                                                          |     47 |
|    9 | Nhà hàng/Khách sạn/Du lịch                                         |     39 |
|   10 | English                                                            |     37 |
|   11 | Content                                                            |     34 |
|   12 | AutoCAD                                                            |     32 |
|   13 | Electricity / Electronics / Refrigeration / Industrial Electricity |     25 |
|   14 | Chinese                                                            |     25 |
|   15 | Consultant                                                         |     23 |

Các kỹ năng đứng đầu gồm nhiều nhóm bán hàng, kinh doanh, kế toán và dịch vụ, không chỉ kỹ năng công nghệ. Vì vậy, không nên diễn giải bảng này như phân phối kỹ năng IT thuần túy nếu chưa lọc/xác nhận phạm vi ngành của tin.

## 7. Cơ Cấu Địa Điểm Làm Việc

Số liệu đếm các lần xuất hiện địa điểm sau khi trải phẳng danh sách khu vực; một tin có thể đóng góp nhiều địa điểm. Tỷ lệ là tỷ trọng trong các địa điểm đã ghi nhận, không phải tỷ lệ tin duy nhất.

| Hạng | Địa điểm              | Lượt ghi nhận |  Tỷ lệ |
| ---: | --------------------- | ------------: | -----: |
|    1 | Thành phố Hồ Chí Minh |         1.316 | 42,42% |
|    2 | Thành phố Hà Nội      |         1.138 | 36,69% |
|    3 | Tỉnh Hưng Yên         |            66 |  2,13% |
|    4 | Thành phố Hải Phòng   |            62 |  2,00% |
|    5 | Thành phố Đà Nẵng     |            56 |  1,81% |
|    6 | Tỉnh Đồng Nai         |            54 |  1,74% |
|    7 | Tỉnh Tây Ninh         |            35 |  1,13% |
|    8 | Tỉnh Bắc Ninh         |            32 |  1,03% |
|    9 | Tỉnh Long An          |            24 |  0,77% |
|   10 | Tỉnh Quảng Ninh       |            24 |  0,77% |
|   11 | Tỉnh Hà Nam           |            24 |  0,77% |
|   12 | Thành phố Cần Thơ     |            21 |  0,68% |
|   13 | Tỉnh Thanh Hóa        |            20 |  0,64% |
|   14 | Tỉnh An Giang         |            18 |  0,58% |
|   15 | Tỉnh Gia Lai          |            16 |  0,52% |

Hai địa điểm dẫn đầu chiếm 79,11% số lượt địa điểm trong kết quả phân tích.

## 8. Top 15 Yêu Cầu Kinh Nghiệm Xuất Hiện Nhiều Nhất

Thống kê theo giá trị nguyên gốc của `experiences_str` trên 2.819 tin; các chuỗi ghép nhiều mức kinh nghiệm được giữ thành nhóm riêng.

| Hạng | Yêu cầu kinh nghiệm | Số tin |  Tỷ lệ |
| ---: | ------------------- | -----: | -----: |
|    1 | 1 năm               |    599 | 21,26% |
|    2 | Không yêu cầu       |    511 | 18,13% |
|    3 | 2 năm               |    401 | 14,23% |
|    4 | 3 năm               |    354 | 12,56% |
|    5 | 5 năm               |    256 |  9,08% |
|    6 | Tất cả kinh nghiệm  |     82 |  2,91% |
|    7 | 1 năm, 2 năm        |     69 |  2,45% |
|    8 | 2 năm, 3 năm        |     64 |  2,27% |
|    9 | 3 năm, 5 năm        |     57 |  2,02% |
|   10 | 06 tháng            |     54 |  1,92% |
|   11 | 4 năm               |     52 |  1,85% |
|   12 | 1 năm, 3 năm        |     44 |  1,56% |
|   13 | 7 năm               |     39 |  1,38% |
|   14 | 2 năm, 5 năm        |     30 |  1,06% |
|   15 | 10 năm              |     26 |  0,92% |

Nhóm 1 năm, không yêu cầu kinh nghiệm và 2–3 năm là các giá trị phổ biến nhất trong snapshot.

## 9. Thống Kê Cấp Bậc Công Việc

Đếm các nhãn trong `job_levels_arr` sau khi trải phẳng; do một tin có thể có nhiều cấp bậc, đây là tỷ lệ trên tổng lượt nhãn cấp bậc, không phải tỷ lệ tin duy nhất.

| Cấp bậc             | Lượt ghi nhận |  Tỷ lệ |
| ------------------- | ------------: | -----: |
| Nhân viên           |           824 | 27,28% |
| Chuyên viên         |           682 | 22,58% |
| Chuyên viên cấp cao |           648 | 21,45% |
| Trưởng nhóm         |           200 |  6,62% |
| Tất cả cấp bậc      |           197 |  6,52% |
| Trưởng phòng        |           192 |  6,36% |
| Giám đốc            |           141 |  4,67% |
| Thực tập            |            99 |  3,28% |
| Phó phòng           |            21 |  0,70% |
| Mới tốt nghiệp      |            11 |  0,36% |
| Phó giám đốc        |             5 |  0,17% |
| Phó nhóm            |             1 |  0,03% |

Ba nhóm Nhân viên, Chuyên viên và Chuyên viên cấp cao chiếm 71,31% lượt nhãn cấp bậc.

## 10. Thống Kê Hình Thức Làm Việc

Giá trị được tách theo dấu phẩy trước khi đếm. Vì vậy, số đếm và tỷ lệ tính trên các mục hình thức làm việc sau khi tách, không nhất thiết bằng số tin duy nhất.

| Hình thức                                        | Lượt ghi nhận |  Tỷ lệ |
| ------------------------------------------------ | ------------: | -----: |
| Trực tiếp                                        |         2.796 | 98,87% |
| Từ xa                                            |            13 |  0,46% |
| Linh hoạt                                        |            12 |  0,42% |
| Nước ngoài                                       |             5 |  0,18% |
| `None` (giá trị thiếu sau khi chuyển kiểu chuỗi) |             2 |  0,07% |

`None` không phải một hình thức làm việc hợp lệ; cần giữ/đánh dấu là thiếu khi chuẩn hóa dữ liệu.

## 11. Thống Kê Cơ Chế CDC & Versioning

Snapshot hiện có được tạo lúc **2026-10-16 17:43:51 (+07:00)** và chứa **2.819 tin**. Trong phạm vi thư mục TopDev chỉ có snapshot hiện tại; không có snapshot trước, lịch sử version hoặc ledger trạng thái để so sánh. Vì vậy, không thể phân loại đáng tin cậy:

- Tin mới hoàn toàn (Version 1 - NEW): **Chưa xác định**.
- Tin có chỉnh sửa nội dung (Version > 1 - UPDATED): **Chưa xác định**.
- Tin giữ nguyên (ACTIVE - Unchanged): **Chưa xác định**.
- Tin đã đóng/hết hạn (CLOSED): **Chưa xác định**.

Không xem toàn bộ 2.819 bản ghi là NEW hoặc ACTIVE chỉ dựa vào một lần chụp dữ liệu. Trường `recalled_at` bị thiếu ở 100% bản ghi trong snapshot nên cũng không đủ căn cứ để đếm tin đóng/hết hạn.

## 12. Các Vấn Đề Kỹ Thuật Đã Gặp & Giải Pháp

- **Anti-bot / rate limit:** Metadata của lần chạy ghi nhận 96 trang đã xử lý, 0 trang lỗi, 0 lỗi lấy chi tiết, 0 tin bị bỏ qua và danh sách lỗi rỗng; không có log mã HTTP riêng để kết luận có hay không từng phản hồi 429/403. Crawler cấu hình header `Accept`, `Accept-Language`, `Origin`, `Referer`, `User-Agent` (cookie tùy chọn); retry tối đa 3 lần cho GET với backoff, tôn trọng `Retry-After` và áp dụng cho 429/500/502/503/504. Mặc định có delay 0,5 giây giữa các lần phân trang tiếp theo và các yêu cầu lấy chi tiết; timeout mỗi request là 25 giây.
- **Cấu trúc DOM bất thường:** Crawler lấy dữ liệu từ API JSON của TopDev, không phân tích DOM trang tuyển dụng; do đó không có thống kê các layout DOM khác nhau. Nội dung HTML nằm trong payload được làm sạch khi trích xuất.
- **Tốc độ cào trung bình:** **Chưa được đo/lưu**. Metadata lưu thời điểm tạo snapshot nhưng không có thời điểm bắt đầu hoặc tổng thời gian chạy. Delay 0,5 giây là khoảng chờ cấu hình, không phải tốc độ thực tế; không đủ dữ liệu để suy ra requests/giây hoặc phút/1.000 tin.
