# BƯỚC 3: XỬ LÝ KHUYẾT THIẾU BẰNG GEN AI & KIỂM ĐỊNH NGOẠI LAI (GEN AI IMPUTATION & OUTLIER HANDLING)

> **Tài liệu quy chuẩn số 03 (Preprocessing Core Document 03 — Step 3: Missing & Outlier)**  
> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Nhiệm vụ:** Bóc trần các Null Marker trá hình, ứng dụng GenAI (Gemini) đọc hiểu sâu văn bản JD để bù khuyết các trường bị thiếu, và áp dụng phương pháp phân vị IQR xử lý ngoại lai số học mà không làm mất thông tin kỹ năng.

---

## 1. Mục Đích & Ranh Giới Bước 3 (Missing & Outlier)

```text
+----------------------------------------------------------------------------------------------------+
|                   RANH GIỚI BẮT BUỘC CỦA BƯỚC 3 (MISSING & OUTLIER HANDLING)                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ĐẦU VÀO - INPUT]:                                                                                |
|  - Bảng phẳng đã được ép kiểu số học và ngày tháng từ Bước 2.                                      |
|                                                                                                    |
|  [ĐƯỢC PHÉP LÀM (DO)]:                                                                             |
|  1. Quét sạch và bóc trần 9+ Null Marker trá hình ('thỏa thuận', 'cạnh tranh', '0', '[]', '{}').  |
|  2. Duy trì cờ `is_salary_negotiable = 1` cho tin thỏa thuận (Missing Not At Random - MNAR).       |
|  3. **Ứng dụng GenAI (Gemini) đọc JD bù khuyết:** kinh nghiệm, cấp bậc, thành phố, kỹ năng.        |
|  4. Đánh dấu cờ kiểm toán `is_imputed_by_genai = True` và ghi nhận độ tin cậy `confidence_score`.  |
|  5. Dùng phương pháp IQR ($Q_1, Q_3$, Bounds) phát hiện 3 lỗi nhập liệu số phổ biến.               |
|  6. Áp dụng kỹ thuật Winsorization (Capping tại phân vị 1% và 99%) để chặn ngoại lai.              |
|                                                                                                    |
|  [TUYỆT ĐỐI CẤM (DO NOT DO)]:                                                                      |
|  - CẤM điền giá trị trung bình (Mean/Median) vào mức lương của các tin thỏa thuận.                |
|  - CẤM xóa bỏ dòng (Drop row) khi gặp outlier lương vì sẽ làm mất thông tin kỹ năng quý giá.      |
|  - CẤM dùng GenAI "bịa đặt" (hallucinate) số liệu khi trong bài đăng hoàn toàn không có cơ sở.    |
|                                                                                                    |
|  [ĐẦU RA - OUTPUT]:                                                                                |
|  - Bảng phẳng sạch sẽ, không còn null giả mạo, các trường khuyết thiếu đã được bù đắp thông minh,  |
|    và dải lương đã được đưa về giới hạn hợp lý.                                                   |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Bóc Trần 9+ Null Marker Trá Hình (Sneaky Null Markers)

Trong dữ liệu cào thực tế từ 8 sàn, hàm `df.isnull()` bỏ sót rất nhiều giá trị rỗng vì chúng bị ngụy trang dưới dạng chuỗi hoặc số đặc biệt:

| Null Marker Trá Hình | Sàn Xuất Hiện Phổ Biến | Bản Chất Kỹ Thuật | Hành Động Xử Lý Chuẩn |
| :--- | :--- | :--- | :--- |
| `""`, `" "` (Chuỗi trắng) | Vieclam24h, TopDev | Form web cho phép submit khoảng trắng | Chuyển về `NaN / None` |
| `"nan"`, `"none"`, `"null"` | Toàn bộ 8 sàn | Lỗi serialize chuỗi từ Python/DB | Chuyển về `NaN / None` |
| `"n/a"`, `"na"`, `"-"`, `"…"` | CareerViet, JobsGO | Ký tự giữ chỗ (placeholder) trên giao diện | Chuyển về `NaN / None` |
| `"[]"`, `"{}"` (Chuỗi json rỗng) | Glints, TopDev | Mảng tags hoặc object rỗng bị ép thành string | Chuyển về `list` rỗng `[]` |
| `"thỏa thuận"`, `"cạnh tranh"` | CareerViet, TopCV, Glints | Chính sách đãi ngộ không công khai số | Bật `is_negotiable = 1`, để lương số = `NaN` |
| `"0"`, `0`, `0.0` | VietnamWorks (`salary=0`) | API ngụy trang giá trị thương lượng bằng số 0 | Bóc trần: đổi về `NaN`, bật `is_negotiable = 1` |
| `"Đăng nhập để xem mức lương"` | ITViec | Cơ chế chặn xem để ép người dùng đăng ký | Đánh dấu ẩn lương, kiểm tra fallback JSON-LD |

---

## 3. Khung Kỹ Thuật Ứng Dụng GenAI Bù Khuyết Dữ Liệu (GenAI Imputer)

### 3.1. Tại Sao Phải Dùng GenAI Để Bù Khuyết?
- Trong hơn $9,000$ bài đăng cào được, có đến **$25\% - 35\%$** bài đăng bị khuyết trường số năm kinh nghiệm (`min_experience_years`), cấp bậc (`seniority`), hoặc danh mục kỹ năng (`skills_list` bị rỗng).
- Tuy nhiên, trong $90\%$ các trường hợp này, thông tin **hoàn toàn có mặt trong văn bản JD tự do**, chỉ là nhà tuyển dụng không tick chọn vào ô form của website.
- **Giải pháp:** Sử dụng **Google Gemini 1.5 Flash** để đọc hiểu ngữ cảnh văn bản và trích xuất thông tin bù vào các ô trống.

### 3.2. Cấu Trúc Prompt Chuyên Biệt Bù Khuyết:

```text
[SYSTEM PROMPT]
Bạn là chuyên gia phân tích dữ liệu thị trường lao động IT tại Việt Nam.
Nhiệm vụ của bạn là đọc kỹ văn bản tuyển dụng (Job Description) và trích xuất các thông tin sau dưới dạng JSON chuẩn.

[YÊU CẦU ĐẶC TẢ ĐẦU RA]:
Trả về DUY NHẤT một JSON object không có markdown bao quanh:
{
  "min_experience_years": float | null,     // Số năm kinh nghiệm tối thiểu yêu cầu (ví dụ: 2.0, 0.5, 0.0 nếu fresher). Null nếu bài không đề cập.
  "job_seniority": string | null,           // 1 trong các bậc: "Intern", "Fresher", "Junior", "Middle", "Senior", "Lead", "Manager"
  "primary_city": string | null,            // Tỉnh/Thành phố làm việc chính (ví dụ: "Hồ Chí Minh", "Hà Nội", "Đà Nẵng", "Remote")
  "hard_skills": list[string],              // Danh sách kỹ năng kỹ thuật, công nghệ, framework, ngôn ngữ (ví dụ: ["Python", "Docker", "SQL"])
  "domain_skills": list[string],            // Nghiệp vụ chuyên ngành (ví dụ: ["Fintech", "Payment Gateway", "E-commerce"])
  "implicit_salary_min_vnd": float | null,  // Lương tối thiểu (VND/tháng) nếu trong bài có đề cập lương ngầm định
  "implicit_salary_max_vnd": float | null,  // Lương tối đa (VND/tháng) nếu có
  "confidence_score": float                 // Độ tự tin từ 0.0 đến 1.0
}

[VĂN BẢN TUYỂN DỤNG CẦN PHÂN TÍCH]
Tiêu đề: {job_title}
Mô tả công việc: {raw_description_text}
Yêu cầu ứng viên: {raw_requirements_text}
```

### 3.3. Quy Tắc Điền Khuyết An Toàn (Safe Imputation Rules):
1. **Quy tắc ưu tiên (Priority Rule):** Nếu trường gốc đã có giá trị hợp lệ từ Bước 1 và 2 $\rightarrow$ **GIỮ NGUYÊN GIÁ TRỊ GỐC**. Chỉ sử dụng giá trị GenAI khi trường gốc là `NaN` hoặc rỗng.
2. **Quy tắc minh bạch (Auditability):** Mọi bản ghi được điền bởi GenAI đều phải bật cờ:
   - `is_imputed_by_genai = True`
   - `imputed_fields = ["min_experience_years", "skills_list"]`
   - `genai_confidence = 0.92`

---

## 4. Kiểm Định & Xử Lý Ngoại Lai Định Lượng (Quantitative Outlier Handling)

### 4.1. Phương Pháp Khoảng Phân Vị IQR (Tukey's Fences):
Áp dụng cho 2 biến định lượng liên tục: **Mức lương tối đa (`salary_max_vnd`)** và **Số năm kinh nghiệm (`min_experience_years`)**:
- $Q_1$: Phân vị thứ 25.
- $Q_3$: Phân vị thứ 75.
- $\text{IQR} = Q_3 - Q_1$.
- $\text{Lower Bound} = \max(0, Q_1 - 1.5 \times \text{IQR})$.
- $\text{Upper Bound} = Q_3 + 1.5 \times \text{IQR}$.

### 4.2. Nhận Diện & Sửa Lỗi 3 Lỗi Nhập Liệu Phổ Biến:
Trước khi áp dụng phương pháp thống kê thuần túy, module kiểm định sẽ tự động nhận diện 3 lỗi do con người nhập sai:

```text
+----------------------------------------------------------------------------------------------------+
|                         3 LỖI NHẬP LIỆU PHỔ BIẾN & CÔNG THỨC SỬA LỖI TỰ ĐỘNG                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [LỖI 1: NHẦM ĐƠN VỊ TIỀN TỆ (GÕ USD VÀO Ô VNĐ)]                                                   |
|  * Hiện tượng: Bài đăng ghi lương 1,500 - 3,000 nhưng đơn vị bị lưu là VNĐ.                        |
|  * Điều kiện nhận diện: `salary_max_vnd < 50,000` VÀ `salary_max_vnd > 100`.                      |
|  * Công thức sửa lỗi: `salary_vnd = salary_vnd * 25,400`.                                          |
|                                                                                                    |
|  [LỖI 2: GÕ THỪA SỐ 0 (TYPO OVER-ZEROING)]                                                         |
|  * Hiện tượng: Nhập 500,000,000 VNĐ thay vì 50,000,000 VNĐ cho vị trí Middle Developer.           |
|  * Điều kiện nhận diện: `salary_max_vnd > 300,000,000` và cấp bậc không phải Giám đốc/C-level.    |
|  * Công thức sửa lỗi: Đưa vào danh sách kiểm duyệt thủ công hoặc chia 10 nếu khớp dải 50tr.       |
|                                                                                                    |
|  [LỖI 3: NHẦM LƯƠNG NĂM VÀO Ô LƯƠNG THÁNG]                                                         |
|  * Hiện tượng: Lương ghi 360,000,000 VNĐ / tháng cho vị trí Senior.                                |
|  * Điều kiện nhận diện: `salary_max_vnd > 200,000,000` và trong JD có chữ "năm" hoặc "annual".   |
|  * Công thức sửa lỗi: `salary_monthly = salary_max_vnd / 12`.                                      |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 4.3. Kỹ Thuật Winsorization (Capping Phân Vị):
- Với các giá trị ngoại lai hợp lệ (ví dụ: Chuyên gia AI cấp cao hoặc Giám đốc Công nghệ thực sự có lương $150 - 200$ triệu VNĐ), **tuyệt đối KHÔNG xóa bỏ bài đăng** vì bản ghi này chứa bộ kỹ năng cực kỳ quý giá phục vụ mục tiêu **SD3**.
- **Giải pháp:** Áp dụng **Winsorization tại phân vị 1% và 99%**:
  - Mọi giá trị $> P_{99}$ được gán bằng $P_{99}$.
  - Mọi giá trị $< P_1$ được gán bằng $P_1$.
  - Lưu giá trị gốc tại `salary_max_raw_value` để bảo toàn vết kiểm toán.
