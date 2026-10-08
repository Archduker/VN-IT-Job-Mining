# Đề cương dự án — Khai phá dữ liệu tuyển dụng CNTT Việt Nam
 
> **Mốc thuyết trình cuối kỳ:** Tuần 9  
> **Mục tiêu dữ liệu:** tối thiểu 10.000 tin tuyển dụng CNTT sạch, không trùng lặp; có pipeline chuẩn.

## 1. Tên dự án

**Tiếng Việt**

> Xây dựng quy trình thu thập và khai phá dữ liệu tuyển dụng CNTT tại Việt Nam

**Tiếng Anh**

> Building a Data Collection Pipeline and Mining IT Recruitment Data in Vietnam

## 2. Mục tiêu

Xây dựng một pipeline có thể tái lập để thu thập định kỳ các tin tuyển dụng CNTT công khai, được phép thu thập tại Việt Nam; lưu trữ chúng trong data lake S3; làm sạch và loại bỏ trùng lặp; sau đó phân tích nhu cầu tuyển dụng CNTT bằng trực quan hóa và một bài toán học máy nhỏ.

Bộ dữ liệu hoàn chỉnh cuối cùng phải có **ít nhất 10.000 tin tuyển dụng duy nhất**. Mỗi dòng biểu diễn một tin tuyển dụng duy nhất, không phải một kỹ năng, một lần cào dữ liệu hay một ảnh chụp trùng lặp.

## 3. Câu hỏi nghiên cứu

1. Những vị trí CNTT nào được đăng tuyển nhiều nhất?
2. Những kỹ năng kỹ thuật nào được yêu cầu nhiều nhất nói chung và trong từng nhóm vị trí?
3. Nhu cầu tuyển dụng khác nhau như thế nào theo địa điểm, cấp bậc và thời gian?
4. Mô hình học máy có thể phân loại một tin tuyển dụng CNTT vào nhóm vị trí dựa trên tiêu đề và mô tả hay không?

## 4. Phạm vi và đạo đức thu thập dữ liệu

- Phạm vi: các tin tuyển dụng CNTT công khai liên quan đến thị trường lao động Việt Nam.
- Không thu thập CV ứng viên, email, số điện thoại hay bất kỳ dữ liệu cá nhân nào.
- Tuân thủ Điều khoản sử dụng và `robots.txt` của từng nguồn; xin phép khi được yêu cầu.
- Không vượt CAPTCHA, đăng nhập vào khu vực bị hạn chế, né giới hạn tốc độ hay phá cơ chế chống bot.
- Lưu URL nguồn và thời điểm thu thập cho từng bản ghi để có thể truy xuất nguồn gốc.

## 5. Lược đồ dữ liệu

| Trường | Mô tả |
|---|---|
| `job_id` | Mã định danh nội bộ, duy nhất |
| `source` | Nền tảng nguồn hoặc trang tuyển dụng của công ty |
| `job_url` | URL công khai chính tắc |
| `job_title` | Tiêu đề công việc gốc |
| `company_name` | Công ty tuyển dụng |
| `location` | Tỉnh/thành hoặc địa điểm đã chuẩn hóa |
| `posted_date` | Ngày đăng hiển thị bởi nguồn, nếu có |
| `collected_date` | Ngày/giờ pipeline thu thập |
| `description` | Nội dung mô tả công việc |
| `requirements` | Nội dung yêu cầu, nếu tách riêng được |
| `seniority` | Intern/Fresher/Junior/Middle/Senior/Lead/Unknown |
| `salary_min` | Mức lương thấp nhất dạng số, có thể rỗng |
| `salary_max` | Mức lương cao nhất dạng số, có thể rỗng |
| `employment_type` | Full-time/Part-time/Contract/Internship/Unknown |
| `skills_normalized` | Danh sách kỹ năng đã chuẩn hóa |
| `role_group` | Nhóm vị trí CNTT đã chuẩn hóa |
| `content_hash` | Hash phục vụ phát hiện trùng lặp |
| `first_seen_date` | Ngày đầu tiên thu thập thành công |
| `last_seen_date` | Ngày thu thập thành công gần nhất |

## 6. Nhóm vị trí

- Backend
- Frontend
- Full-stack
- Data / AI
- DevOps / Cloud
- QA / Testing
- Mobile
- Security / System
- Other IT

## 7. Quy trình khai phá dữ liệu (CRISP-DM)

```text
Hiểu bài toán nghiệp vụ
        ↓
Hiểu dữ liệu
        ↓
Thu thập dữ liệu
        ↓
Làm sạch và chuyển đổi dữ liệu
        ↓
Khai phá dữ liệu / Học máy
        ↓
Đánh giá
        ↓
Trực quan hóa và kết luận
```

## 8. Kiến trúc kỹ thuật

```text
Nguồn tin tuyển dụng công khai được phép / trang careers của công ty
        ↓
Crawler: requests + BeautifulSoup / Playwright
        ↓
Browser Use + Ollama (phương án thử nghiệm dự phòng)
        ↓
S3 Raw Zone: HTML và JSONL gốc
        ↓
Kiểm tra hợp lệ và phân tích dữ liệu
        ↓
S3 Staging Zone: bản ghi đã phân tích và gán kiểu dữ liệu
        ↓
Làm sạch, chuẩn hóa và loại bỏ trùng lặp
        ↓
S3 Curated Zone: dữ liệu job sạch ở định dạng Parquet
        ↓
EDA, trực quan hóa và học máy
```

### Lựa chọn công cụ

| Mục đích | Công cụ |
|---|---|
| Crawler chính cho trang tĩnh | Python `requests` + BeautifulSoup |
| Trang JavaScript/động | Playwright (hoặc Selenium khi cần) |
| Thử nghiệm có hỗ trợ AI | Browser Use mã nguồn mở + Ollama |
| Lưu trữ đối tượng | AWS S3 |
| Xử lý dữ liệu | Python, Pandas, PyArrow |
| Trực quan hóa | Matplotlib, Seaborn, Plotly |
| Học máy | scikit-learn |
| Định dạng lưu trữ | JSONL cho raw; Parquet cho staging và curated |

Browser Use + Ollama sẽ được thử nghiệm trên khoảng 100–300 trang và so sánh với parser truyền thống. Đây không phải crawler chính dùng ở quy mô lớn.

## 9. Cấu trúc data lake trên S3

```text
s3://<bucket-name>/
├── raw/          # HTML/JSONL gốc, phân vùng theo nguồn và ngày
├── staging/      # Bản ghi đã phân tích và gán kiểu dữ liệu
├── curated/      # Bộ dữ liệu job sạch, đã loại trùng
├── analytics/    # Bảng tổng hợp và bảng đặc trưng ML
└── metadata/     # Từ điển dữ liệu, danh mục nguồn, nhật ký thu thập
```

Quy ước phân vùng đề xuất:

```text
raw/source=<source>/year=YYYY/month=MM/day=DD/
staging/source=<source>/year=YYYY/month=MM/day=DD/
curated/year=YYYY/month=MM/
```

## 10. Quy tắc chất lượng dữ liệu

1. Loại bản ghi trùng hoàn toàn bằng `source + canonical job_url`.
2. Phát hiện gần trùng lặp bằng tiêu đề, công ty, địa điểm, mô tả đã chuẩn hóa hoặc content hash.
3. Lưu các lần cào lặp lại bằng cách cập nhật `last_seen_date`; không tạo dòng job mới.
4. Chuẩn hóa địa điểm, ví dụ `HCM`, `TP.HCM` và `Ho Chi Minh` → `Ho Chi Minh City`.
5. Chuẩn hóa kỹ năng, ví dụ `JS` → `JavaScript` và `Node` → `Node.js`.
6. Lương không có dữ liệu phải là `null`, không bao giờ là `0`.
7. Loại các bản ghi thiếu trường thiết yếu: `job_title`, `job_url` hoặc mô tả có thể sử dụng.
8. Lập nhật ký làm sạch gồm: số dòng đầu vào, bị loại, trùng lặp và cuối cùng được giữ lại.

## 11. Tần suất thu thập và mục tiêu dữ liệu

Chạy pipeline thu thập 3 lần mỗi tuần, ví dụ: Thứ Hai, Thứ Tư và Thứ Sáu.

- Mục tiêu cuối cùng: **hơn 10.000 tin tuyển dụng sạch, không trùng lặp**.
- Mục tiêu thu thập thô: **1.500–1.800 bản ghi mỗi tuần**.
- Mục tiêu giữ lại dự kiến sau khi xác thực và loại trùng: **tối thiểu 1.250 tin tuyển dụng duy nhất mỗi tuần**.
- Mỗi lần chạy crawler sẽ ghi lại nhật ký thu thập: run ID, nguồn (source), thời gian bắt đầu/kết thúc, số lượng bản ghi thô (raw count), số lượng hợp lệ (valid count), số lượng trùng lặp (duplicate count), số lượng lỗi (error count), và đường dẫn S3 đầu ra.

## 12. Kế hoạch 8 tuần

| Tuần | Mục tiêu tin tuyển dụng duy nhất (tích lũy) | Kết quả bàn giao chính |
|---:|---:|---|
| 1 | 300–500 | Đề cương, lược đồ dữ liệu, thiết lập S3, bản thử nghiệm crawler |
| 2 | 1.500 | Thu thập ổn định danh sách / trang chi tiết |
| 3 | 3.000 | Chuẩn hóa địa điểm / kỹ năng và loại bỏ trùng lặp |
| 4 | 4.500 | Phân tích khám phá dữ liệu (EDA) và trực quan hóa ban đầu |
| 5 | 6.000 | Thử nghiệm với Browser Use + Ollama |
| 6 | 7.500 | Bộ dữ liệu đặc trưng ML và các mô hình cơ sở (baselines) |
| 7 | 9.000 | Huấn luyện và đánh giá mô hình |
| 8 | 10.000+ | Dashboard / notebook, báo cáo tổng kết và buổi thuyết trình demo |

## 13. Kế hoạch trực quan hóa

- Số lượng việc làm theo nhóm vị trí (role group).
- Top các kỹ năng kỹ thuật được yêu cầu nhiều nhất.
- Phân bố việc làm theo thành phố / địa điểm.
- Biểu đồ nhiệt (heatmap) kỹ năng theo nhóm vị trí.
- Phân bố cấp bậc (seniority) theo nhóm vị trí.
- Số lượng tin tuyển dụng mới được thu thập theo thời gian.
- Dải lương theo nhóm vị trí / địa điểm, nếu độ phủ dữ liệu lương đủ lớn.
- Ma trận nhầm lẫn (confusion matrix) và các chỉ số đánh giá mô hình ML.

## 14. Bài toán học máy

**Nhiệm vụ:** dự đoán `role_group` từ `job_title + description`.

| Giai đoạn | Phương pháp |
|---|---|
| Đặc trưng văn bản | TF-IDF |
| Mô hình cơ sở (Baseline) | Multinomial Naive Bayes |
| Mô hình chính | Logistic Regression hoặc Linear SVM |
| Đánh giá | Phân chia tập train/test phân tầng (stratified) hoặc kiểm định chéo 5-fold (5-fold cross-validation) |
| Thước đo đánh giá | Accuracy, Precision, Recall, F1-score, ma trận nhầm lẫn (confusion matrix) |

## 15. Danh sách kiểm tra xác nhận

Trước khi tiến hành triển khai, hãy xác nhận các điểm sau:

- [ ] Giảng viên yêu cầu 10.000 **tin tuyển dụng duy nhất** trước buổi thuyết trình cuối kỳ vào Tuần 9.
- [ ] Tên đề tài dự án ở trên đã được phê duyệt.
- [ ] Tài khoản AWS và S3 bucket đã sẵn sàng.
- [ ] Đã lựa chọn ít nhất một nguồn tuyển dụng được phép hoặc trang tuyển dụng của công ty.
- [ ] Các nhóm vị trí và lược đồ dữ liệu đã được thống nhất.
- [ ] Quy trình thu thập dữ liệu sẽ được thực hiện 3 lần mỗi tuần.
- [ ] Browser Use + Ollama là nhánh thử nghiệm, không phải crawler chính thức.
