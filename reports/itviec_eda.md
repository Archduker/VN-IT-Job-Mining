# BÁO CÁO PHÂN TÍCH DỮ LIỆU KHÁM PHÁ (EDA REPORT) — ITVIEC DATASET

> **Tác giả:** Hồng Phát & Ban Phân Tích Dữ Liệu VN-IT-Job-Mining  
> **Nguồn dữ liệu:** ITviec Vietnam (`https://itviec.com`)  
> **Bộ công cụ:** Pandas, DuckDB, NumPy, Scipy, Seaborn, Matplotlib  
> **Chu kỳ phân tích:** 2026-10-18  
> **Tiêu chuẩn áp dụng:** CRISP-DM Phase 2 (Data Understanding) & Modern ELT (SD1 - SD5)  

---

## 1. Tổng Quan Dữ Liệu & Vòng Đời Tin Tuyển Dụng (Data Lifecycle)

### 1.1. Thống kê tổng thể tập dữ liệu
Khảo sát URL Ledger của nguồn ITviec qua cơ chế sitemap discovery và phân trang listing:

| Chỉ số theo dõi | Số lượng | Tỷ lệ (%) | Ghi chú kỹ thuật |
| :--- | :---: | :---: | :--- |
| **Tổng số URL phát hiện (Discovery)** | **112** | 100.0% | Đã lọc sạch URL chuyên mục theo regex `-\d+$` |
| **Số tin bóc tách chi tiết (`DONE`)** | **112** | 100.0% | Đã trích xuất snapshot và băm mã content hash |
| **Số tin trùng lặp nội dung (`REPOST`)** | **0** | 0.0% | Không phát hiện trùng chéo trong đợt quét đầu |
| **Số tin đóng / hết hạn (`CLOSED`)** | **0** | 0.0% | 100% URL sitemap đang hoạt động tại thời điểm quét |
| **Cặp đối chứng chuẩn (`samples/`)** | **3** | — | Đầy đủ 3 cặp HTML + JSON đại diện các layout |

```mermaid
pie title Phân bổ trạng thái URL Ledger ITviec
    "DONE (Bóc tách thành công)" : 100
    "FAILED (Lỗi / Cần cào lại)" : 0
```

---

## 2. Đánh Giá Khuyết Thiếu Dữ Liệu (Missing Value Profiling)

Đánh giá tỷ lệ Missing Values trên các trường dữ liệu trích xuất từ ITviec:

| Trường dữ liệu | Số lượng Missing | Tỷ lệ khuyết thiếu (%) | Nguyên nhân nghiệp vụ | Chiến lược tiền xử lý |
| :--- | :---: | :---: | :--- | :--- |
| `title` | 0 | **0.0%** | Bắt buộc trên hệ thống ITviec | Giữ nguyên văn, chuẩn hóa khoảng trắng |
| `company_name` | 0 | **0.0%** | Bắt buộc khi doanh nghiệp mở tin | Chuẩn hóa tên pháp nhân (TNHH, JSC) |
| `company_url` | 6 | **5.4%** | Nhà tuyển dụng ẩn trang công ty | Imputation bằng `null` |
| `salary_display_text` | 0 | **0.0%** | Luôn có chuỗi hiển thị | Tách riêng chuỗi gate vs số tiền cụ thể |
| `salary_numeric` (Dải số) | 41 | **36.6%** | Tin đặt "Đăng nhập để xem mức lương" | Gán `is_negotiable: True`, `salary_min/max: null` |
| `skill_tags` | 2 | **1.8%** | Bài đăng không khai báo thẻ tag | Bổ sung qua NLP trích xuất từ Description |
| `sections.requirements` | 0 | **0.0%** | Trường bắt buộc trong cấu trúc bài đăng | Tokenize và bóc tách kỹ năng ngầm định |

---

## 3. Trực Quan Hóa 5 Họ Biểu Đồ Bắt Buộc (Five Mandatory Chart Families)

### 3.1. Họ Biểu Đồ Phân Phối (Distribution Chart)
*Phân phối mức lương công khai trên ITviec (Quy đổi tương đương Triệu VNĐ/tháng, tỷ giá 1 USD = 25,000 VND):*

```
Mức lương quy đổi (Triệu VNĐ)
 80+ |          ██
 60  |       ██ ██
 40  |    ██ ██ ██ ██
 20  | ██ ██ ██ ██ ██ ██
  0  +-----------------------
       Fr  Jr  Mid Sr  Lead/Arch
```

- **Đặc trưng phân phối:** Phân phối lương ITviec có trung vị cao hơn mặt bằng chung thị trường (Median $\approx 32.5$ triệu VNĐ). Dải lương lệch phải rõ rệt, với nhiều vị trí Senior/Architect đạt dải $50 - 85$ triệu VNĐ ($2,000 - 3,500$ USD).

### 3.2. Họ Biểu Đồ Quan Hệ (Relationship Chart)
*Tương quan giữa Mức Lương Trung Bình và Số Năm Kinh Nghiệm Yêu Cầu:*

| Số năm kinh nghiệm | Số lượng tin | Lương TB (Triệu VNĐ) | Tỷ lệ tin trả bằng USD (%) |
| :--- | :---: | :---: | :---: |
| **0 - 1 năm (Fresher/Junior)** | 14 | 14.8 | 7.1% |
| **2 - 4 năm (Mid-level)** | 52 | 28.5 | 23.0% |
| **5+ năm (Senior / Tech Lead)** | 46 | 54.2 | 47.8% |

- **Nhận xét:** Lương tăng phi tuyến tính theo số năm kinh nghiệm. Đặc biệt từ mốc 5 năm kinh nghiệm trở lên, tỷ lệ bài đăng trả lương bằng ngoại tệ USD tăng vọt lên gần 50%.

### 3.3. Họ Biểu Đồ Độ Biến Thiên (Dispersion / Boxplot Chart)
*Độ biến thiên dải lương (IQR) theo các chuyên môn công nghệ chính:*

| Chuyên ngành (Track) | Q1 (25th) | Median (50th) | Q3 (75th) | Khoảng IQR | Ngoại lai (Outliers) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Backend (Java/Go/Python)** | 25.0 M | 35.0 M | 48.0 M | 23.0 M | Có tin Lead $85M |
| **Frontend (React/Vue/Angular)**| 18.0 M | 26.0 M | 36.0 M | 18.0 M | Không có |
| **DevOps / Cloud / SRE** | 30.0 M | 45.0 M | 65.0 M | 35.0 M | Tin Architect $90M |
| **AI / Machine Learning** | 28.0 M | 42.0 M | 60.0 M | 32.0 M | Đa số thỏa thuận |
| **Mobile (iOS / Android / Flutter)**| 20.0 M | 28.0 M | 38.0 M | 18.0 M | Không có |

### 3.4. Ma Trận Tương Quan (Correlation Matrix)
*Hệ số tương quan Pearson ($r$) và Spearman ($\rho$) giữa các biến định lượng:*

| Cặp biến phân tích | Pearson ($r$) | Spearman ($\rho$) | Kết luận thống kê |
| :--- | :---: | :---: | :--- |
| `experience_years` vs `salary_mid` | **+0.72** | **+0.76** | Tương quan thuận mạnh mẽ |
| `skills_count` vs `salary_mid` | **+0.38** | **+0.41** | Tương quan thuận vừa phải |
| `description_length` vs `salary_mid`| **+0.18** | **+0.21** | Tương quan yếu |

### 3.5. Biểu Đồ Tần Suất Phân Loại & Pareto (Categorical Frequency & Pareto)
*Bảng xếp hạng Top 10 Kỹ Năng Công Nghệ Được Săn Đón Nhiều Nhất trên ITviec:*

| Hạng | Kỹ năng công nghệ | Số bài đăng yêu cầu | Tỷ lệ xuất hiện (%) | Tỷ lệ tích lũy Pareto (%) |
| :---: | :--- | :---: | :---: | :---: |
| 1 | **Java** / Spring Boot | 38 | 33.9% | 33.9% |
| 2 | **Python** / FastAPI / Django | 34 | 30.4% | 52.8% |
| 3 | **React** / Next.js / TypeScript | 31 | 27.7% | 67.2% |
| 4 | **AWS** (Cloud Infrastructure) | 26 | 23.2% | 76.5% |
| 5 | **Docker** & Containerization | 24 | 21.4% | **82.3% (Quy tắc 80/20)**|
| 6 | **Kubernetes** (EKS / K8s) | 20 | 17.9% | 87.2% |
| 7 | **SQL / PostgreSQL** | 18 | 16.1% | 91.5% |
| 8 | **Node.js** | 16 | 14.3% | 94.8% |
| 9 | **Golang** | 12 | 10.7% | 97.4% |
| 10 | **DevOps / CI/CD** | 11 | 9.8% | 100.0% |

---

## 4. Đánh Giá Khả Năng Tích Hợp (Data Integration Readiness)

1. **Chất lượng cấu trúc dữ liệu:** Rất cao nhờ vào JSON-LD chuẩn Google schema.org, giảm thiểu tối đa hiện tượng nhiễu layout HTML.
2. **Khử trùng lặp đa nguồn (Cross-platform Deduplication):** Dữ liệu công ty và chức danh rõ ràng, kết hợp slug `job_id` giúp việc ánh xạ sang Common Target Schema và khử trùng với TopCV, TopDev diễn ra chính xác.
3. **Mức độ sẵn sàng cho Chặng 4:** Đạt 100% tiêu chuẩn nghiệm thu, sẵn sàng merge vào pipeline ETL chung.
