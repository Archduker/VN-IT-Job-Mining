# BƯỚC 2: CHUYỂN HÓA DỮ LIỆU, BÓC TÁCH KIỂU & XỬ LÝ LƯƠNG (DATA TRANSFORMATION & PARSING)

> **Tài liệu quy chuẩn số 02 (Preprocessing Core Document 02 — Step 2: Transformation)**  
> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Nhiệm vụ:** Chuyển đổi các cột chuỗi thô từ bảng phẳng Staging thành các kiểu dữ liệu có cấu trúc định lượng (`float`, `int`, `datetime`), hiện thực hóa quy trình Cascade bóc tách dải lương và xử lý lương ẩn trong mô tả công việc.

---

## 1. Mục Đích & Ranh Giới Bước 2 (Transformation)

```text
+----------------------------------------------------------------------------------------------------+
|                      RANH GIỚI BẮT BUỘC CỦA BƯỚC 2 (DATA TRANSFORMATION)                           |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ĐẦU VÀO - INPUT]:                                                                                |
|  - Bảng phẳng Staging chứa các cột chuỗi thô từ Bước 1.                                            |
|                                                                                                    |
|  [ĐƯỢC PHÉP LÀM (DO)]:                                                                             |
|  1. Regex bóc tách dải số lương: `salary_min_vnd`, `salary_max_vnd`.                               |
|  2. Quét văn bản JD tìm lương ẩn khi header là "Thỏa thuận" (Cascade Extraction).                  |
|  3. Quy đổi tiền tệ ngoại tệ (USD sang VND) với tỷ giá tham chiếu 25,400.                          |
|  4. Quy đổi chu kỳ trả lương (Lương Năm -> Lương Tháng, Lương Giờ -> Lương Tháng).                 |
|  5. Bóc tách số năm kinh nghiệm tối thiểu: `min_experience_years` (float).                         |
|  6. Ép kiểu ngày đăng tin và hạn nộp hồ sơ về định dạng ISO 8601 (YYYY-MM-DD).                     |
|                                                                                                    |
|  [TUYỆT ĐỐI CẤM (DO NOT DO)]:                                                                      |
|  - CẤM xóa bỏ dòng bài đăng khi phát hiện số lương quá cao hoặc quá thấp (Outlier).               |
|  - CẤM điền giá trị trung bình (Mean/Median) vào các ô lương bị thiếu (Missing).                   |
|  - CẤM áp dụng biến đổi phi tuyến Log-transformation tại bước này (để dành cho Bước 4).            |
|                                                                                                    |
|  [ĐẦU RA - OUTPUT]:                                                                                |
|  - Bảng phẳng đã có các cột định lượng số học và kiểu ngày tháng chuẩn xác.                        |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Quy Trình Cascade 3 Tầng: Bóc Tách Lương & Lương Ẩn Trong JD

```text
+----------------------------------------------------------------------------------------------------+
|                           QUY TRÌNH CASCADE 3 TẦNG BÓC TÁCH MỨC LƯƠNG                              |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   raw_salary_text (Từ Header)                                                                      |
|          │                                                                                         |
|          ├──> [Có dải số rõ ràng? (ví dụ: '15 - 25 triệu', '1,000 - 2,000 USD')]                  |
|          │        │                                                                                |
|          │        └──> [TẦNG 1: HEADER REGEX PARSER]                                               |
|          │             Bóc tách min, max, currency, period.                                        |
|          │             Gán `salary_source = 'header'`.                                             |
|          │                                                                                         |
|          └──> [Là 'Thỏa thuận', 'Cạnh tranh' hoặc Null/Rỗng]                                       |
|                   │                                                                                |
|                   ▼                                                                                |
|          [TẦNG 2: JD REGEX SCANNER]                                                                |
|          Quét văn bản mô tả (JD) tìm các mẫu câu chứa từ khóa lương:                              |
|          - "lương cứng từ 15 đến 20 triệu"                                                         |
|          - "thu nhập up to 30.000.000 VNĐ"                                                         |
|          - "package $1500 - $2500"                                                                 |
|                   │                                                                                |
|                   ├──> [Khớp mẫu Regex thành công]                                                 |
|                   │        └──> Bóc tách dải số, gán `salary_source = 'jd_regex'`.                 |
|                   │             Gán cờ `is_salary_negotiable_declared = 1` (Bảo toàn nhãn gốc).    |
|                   │                                                                                |
|                   └──> [Không khớp Regex hoặc mẫu câu phức tạp]                                    |
|                            │                                                                       |
|                            ▼                                                                       |
|                   [TẦNG 3: GEN AI FALLBACK PARSER]                                                 |
|                   Đoạn văn phức tạp (ví dụ: "Cam kết năm đầu thu nhập trên 400 triệu...")          |
|                   được gửi qua GenAI để bóc tách JSON chuẩn.                                       |
|                   Gán `salary_source = 'jd_genai'`.                                                |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Quy Tắc Chuyển Đổi Tiền Tệ & Chu Kỳ Trả Lương

### 3.1. Chuẩn Hóa Tiền Tệ (Currency Standardization):
- **Đơn vị đích chuẩn:** Toàn bộ mức lương trong hệ thống được quy đổi về **VNĐ/tháng**.
- **Tỷ giá chuyển đổi:**
  - USD sang VND: `1 USD = 25,400 VND`.
  - Giữ lại trường nguyên bản `salary_currency_original` (`'USD'`, `'VND'`) và `salary_min_original` để đảm bảo tính minh bạch và khả năng kiểm toán dữ liệu (Audit Trail).

### 3.2. Chuẩn Hóa Chu Kỳ Trả Lương (Pay Period Standardization):
- **Chu kỳ đích chuẩn:** Theo tháng (`month`).
- **Quy tắc quy đổi:**
  - Lương Năm (`year`): $\text{salary\_month} = \frac{\text{salary\_year}}{12}$.
  - Lương Giờ (`hour`): $\text{salary\_month} = \text{salary\_hour} \times 160$ (chuẩn 160 giờ làm việc/tháng).
  - Lương Ngày (`day`): $\text{salary\_month} = \text{salary\_day} \times 22$ (chuẩn 22 ngày công/tháng).

---

## 4. Bóc Tách Số Năm Kinh Nghiệm (Experience Parsing)

Trường `raw_experience_text` chứa các chuỗi tự do được chuẩn hóa về biến liên tục `min_experience_years` (`float`):

| Chuỗi thô gốc (`raw_experience_text`) | Giá trị số (`min_experience_years`) | Ghi chú quy đổi |
| :--- | :--- | :--- |
| `"Không yêu cầu kinh nghiệm"`, `"Chưa có kinh nghiệm"` | `0.0` | Fresher / Không đòi hỏi kinh nghiệm |
| `"Dưới 1 năm kinh nghiệm"`, `"6 tháng"` | `0.5` | Bán niên |
| `"1 năm"`, `"1 - 2 năm"`, `"Tối thiểu 1 năm"` | `1.0` | Lấy cận dưới an toàn |
| `"2 - 3 năm"`, `"Từ 2 năm trở lên"` | `2.0` | Lấy cận dưới an toàn |
| `"5+ năm"`, `"Trên 5 năm"` | `5.0` | Cấp độ Senior |
| `"Thỏa thuận"`, `None`, Không đề cập | `NaN` (Sẽ được xử lý bởi GenAI ở Bước 3) | Giữ khuyết để GenAI đọc JD bù |

---

## 5. Chuẩn Hóa Định Dạng Ngày Tháng (Date Normalization)

Trường `raw_posted_date` và `raw_deadline` được chuyển đổi thành chuẩn ISO 8601 (`YYYY-MM-DD`):
1. **Dạng ngày tuyệt đối:**
   - `"16/10/2026"` $\rightarrow$ `2026-10-16`
   - `"2026-10-20T11:04:02+07:00"` $\rightarrow$ `2026-10-20`
2. **Dạng ngày tương đối (Relative Dates):**
   - `"2 ngày trước"` $\rightarrow$ `crawled_at - timedelta(days=2)`
   - `"1 tuần trước"` $\rightarrow$ `crawled_at - timedelta(weeks=1)`
   - `"Hôm nay"`, `"8 giờ trước"` $\rightarrow$ `crawled_at.date()`
