# BƯỚC 4: CHUẨN HÓA THANG ĐO, BIẾN ĐỔI PHÂN PHỐI & TAXONOMY (NORMALIZATION & SCALING)

> **Tài liệu quy chuẩn số 04 (Preprocessing Core Document 04 — Step 4: Normalization)**  
> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Nhiệm vụ:** Biến đổi phân phối số học đưa về dạng chuẩn (Gaussian-like), co giãn thang đo dữ liệu (Scaling), và chuẩn hóa các trường phân loại (Chức danh về 12 Job Family, Kỹ năng về Taxonomy ESCO, Địa danh về 63 Tỉnh thành).

---

## 1. Mục Đích & Ranh Giới Bước 4 (Normalization)

```text
+----------------------------------------------------------------------------------------------------+
|                      RANH GIỚI BẮT BUỘC CỦA BƯỚC 4 (NORMALIZATION & SCALING)                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ĐẦU VÀO - INPUT]:                                                                                |
|  - Bảng phẳng đã sạch lỗi kỹ thuật, không còn null giả mạo, đã được bù khuyết từ Bước 3.           |
|                                                                                                    |
|  [ĐƯỢC PHÉP LÀM (DO)]:                                                                             |
|  1. Thực hiện Log-transformation cho mức lương: `log_salary = log(1 + salary_max_vnd)`.            |
|  2. Thực hiện RobustScaler hoặc Min-Max Scaling cho các biến định lượng phục vụ mô hình hóa.       |
|  3. Chuẩn hóa chức danh tuyển dụng về 12 Job Family chuẩn ngành IT Việt Nam (SD2).                 |
|  4. Chuẩn hóa cấp bậc nghề nghiệp về 6 bậc chuẩn (Intern -> Lead/Manager).                         |
|  5. Chuẩn hóa địa bàn làm việc về 63 tỉnh/thành phố chuẩn quốc gia.                                |
|  6. Chuẩn hóa tên kỹ năng về Từ điển Kỹ năng Chuẩn (ESCO IT Skills Taxonomy) (SD3).                |
|                                                                                                    |
|  [TUYỆT ĐỐI CẤM (DO NOT DO)]:                                                                      |
|  - CẤM ghi đè làm mất nhãn văn bản gốc của tiêu đề hoặc kỹ năng (luôn giữ cả cột gốc và chuẩn).   |
|  - CẤM scale dữ liệu khi chưa qua bước kiểm định và làm sạch ngoại lai (Outliers).                |
|                                                                                                    |
|  [ĐẦU RA - OUTPUT]:                                                                                |
|  - BỘ DỮ LIỆU VÀNG (GOLDEN MASTER DATASET) phẳng hoàn toàn, sẵn sàng phục vụ phân tích SD1 - SD5. |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Biến Đổi Phân Phối Số Học: Log-Transformation

### 2.1. Tại Sao Bắt Buộc Phải Dùng Log-Transformation?
- Trong dữ liệu tuyển dụng IT tại Việt Nam, mức lương có phân phối **lệch phải cực đoan (Heavy Right-Skewed)**:
  - Đa số nhân sự tập trung ở dải $10 - 30$ triệu VNĐ/tháng.
  - Một số ít vị trí Senior/Architect/Director có mức lương từ $80 - 150+$ triệu VNĐ/tháng kéo đuôi phân phối dài về bên phải.
  - Chỉ số Skewness thực tế đạt $+5.36$ và Kurtosis đạt $+32.39$ (phân phối nhọn đuôi dày Leptokurtic).
- Hiện tượng này khiến các thuật toán phân tích (K-Means, Linear Regression, PCA) bị sai lệch nghiêm trọng do nhạy cảm với đuôi dài.

### 2.2. Công Thức Biến Đổi Chuẩn:
$$y = \log(1 + x)$$
- Trong đó $x$ là `salary_max_vnd` (hoặc tính theo đơn vị Triệu VNĐ).
- **Kết quả:** Phân phối sau khi biến đổi được nén về dạng gần chuẩn (Bell-shaped Gaussian-like), ổn định phương sai và giảm thiểu tác động của các giá trị cực đại.

---

## 3. Chuẩn Hóa 12 Nhóm Nghề Nghiệp Chuẩn (12 Job Families Taxonomy)

Toàn bộ các tiêu đề công việc tự do từ 8 sàn tuyển dụng được phân loại vào **12 Job Family chuẩn** của ngành Công nghệ Thông tin tại Việt Nam (Phục vụ mục tiêu **SD2**):

| Mã Nhóm (Code) | Tên Job Family Chuẩn | Từ Khóa Nhận Diện Đặc Trưng (Keywords) |
| :--- | :--- | :--- |
| `JF01_BACKEND` | Backend Development | Java, Spring, Node.js, Python, Golang, PHP, .NET, Django, C# |
| `JF02_FRONTEND` | Frontend Development | React, Vue, Angular, Next.js, HTML/CSS, Tailwind, TypeScript |
| `JF03_FULLSTACK` | Fullstack Development | Fullstack, MERN, MEVN, Web Developer |
| `JF04_MOBILE` | Mobile App Development | Flutter, React Native, iOS, Android, Swift, Kotlin |
| `JF05_DEVOPS` | DevOps / Cloud / SRE / SysAdmin | Docker, Kubernetes, CI/CD, AWS, Azure, GCP, Linux, Terraform |
| `JF06_DATA_ENG` | Data Engineering & Big Data | Spark, Hadoop, Kafka, Airflow, ETL, DWH, BigQuery, Databricks |
| `JF07_DATA_AI` | Data Science / AI / Machine Learning | Machine Learning, Deep Learning, PyTorch, TensorFlow, NLP, LLM |
| `JF08_QA_QC` | Software QA / QC / Automation Test | Tester, QA, QC, Automation, Selenium, Playwright, Postman |
| `JF09_SECURITY` | Cyber Security / InfoSec | SOC, Pentest, SIEM, Security, ISO 27001, CEH, CISSP |
| `JF10_PROD_BA` | Product Management / Business Analyst | Product Owner, PO, PM, Business Analyst, BA, Scrum Master |
| `JF11_UI_UX` | UI/UX Design | Figma, UI/UX, Design, Wireframe, Prototype, Adobe XD |
| `JF12_EMBEDDED`| Embedded Systems / IoT / Hardware | C/C++, Embedded, IoT, Firmware, PLC, RTOS, PCB |

---

## 4. Chuẩn Hóa 6 Bậc Nghề Nghiệp (Seniority Standardization)

Trường `raw_seniority_text` và kết quả suy luận từ JD được ánh xạ về **6 cấp bậc chuẩn**:

```text
+----------------------------------------------------------------------------------------------------+
|                                  6 CẤP BẬC SENIORITY QUY CHUẨN                                     |
+----------------------------------------------------------------------------------------------------+
| 1. INTERN    : Thực tập sinh, Sinh viên năm cuối, Intern Developer.                                |
| 2. FRESHER   : Mới tốt nghiệp, dưới 1 năm kinh nghiệm, đang đào tạo lại.                           |
| 3. JUNIOR    : Từ 1 - 2 năm kinh nghiệm, làm việc có người hướng dẫn.                              |
| 4. MIDDLE    : Từ 2 - 4 năm kinh nghiệm, làm việc độc lập, tự chủ tính năng.                       |
| 5. SENIOR    : Từ 4 - 7 năm kinh nghiệm, giải quyết bài toán kiến trúc, hướng dẫn junior.          |
| 6. LEAD_MGR  : Trên 7 năm kinh nghiệm, Tech Lead, Team Lead, Engineering Manager, Director, CTO.   |
+----------------------------------------------------------------------------------------------------+
```

---

## 5. Chuẩn Hóa Địa Danh (63 Tỉnh Thành Việt Nam)

Trường địa điểm làm việc `raw_location_text` được chuẩn hóa về tên tỉnh/thành phố chính thức:
- `"HCM"`, `"Hồ Chí Minh"`, `"TP.HCM"`, `"Sài Gòn"`, `"Quận 1"`, `"Bình Thạnh"` $\rightarrow$ **`Hồ Chí Minh`**.
- `"HN"`, `"Hà Nội"`, `"Cầu Giấy"`, `"Ba Đình"`, `"Hà nội"` $\rightarrow$ **`Hà Nội`**.
- `"ĐN"`, `"Đà Nẵng"` $\rightarrow$ **`Đà Nẵng`**.
- `"Toàn quốc"`, `"Làm việc từ xa"`, `"Remote"` $\rightarrow$ **`Remote`**.
- Tạo cờ nhị phân `is_remote = 1` nếu tin cho phép làm việc từ xa.
