# 📋 Bản Giao Việc Chi Tiết — Khoa (Chuyên Đề EDA 2)

> **Dự án**: VN-IT-Job-Mining — Hệ thống Thu thập & Khai phá Dữ liệu Tuyển dụng IT Việt Nam  
> **Người thực hiện**: Khoa  
> **Vai trò**: Data Analyst / NLP Specialist — Phụ trách **Chuyên Đề EDA 2: Kỹ Năng Công Nghệ, Địa Lý & Khai Phá Văn Bản (NLP / Text Mining)**  
> **Ngày giao việc**: 2026-10-08  
> **Tài liệu gốc tham chiếu**: [`docs/crawler_api_analysis.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawler_api_analysis.md) | [`TASKS.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/TASKS.md)

---

## 🎯 1. Mục Tiêu & Công Việc Cần Làm

Bạn chuyển giao phần cào crawler để chuyên trách 100% vào **Khai phá Dữ liệu Chuyên sâu (Data Mining & NLP)**. Trọng tâm của bạn là bóc tách hệ sinh thái công nghệ (Tech Stacks), thị trường địa lý vùng miền và khai phá nội dung văn bản (Job Description & Phúc lợi) trong tập dữ liệu tổng hợp.

Nhiệm vụ cụ thể của bạn gồm:
1. **Phân tích Hệ Sinh Thái Kỹ Năng & Công Nghệ (Tech Stack Ecosystem)**:
   - Tách và chuẩn hóa danh sách kỹ năng từ trường `skills_text` (Python, Java, JavaScript, React, Docker, AWS, SQL, Kubernetes,...).
   - Top 20 công nghệ được săn đón nhiều nhất tại thị trường Việt Nam.
   - Ma trận đồng xuất hiện kỹ năng (**Co-occurrence Matrix & Heatmap**): Kỹ năng nào thường đi đôi với nhau? (ví dụ: React đi với TypeScript; Spring Boot đi với MySQL/PostgreSQL; DevOps đi với Docker/K8s/CI-CD).
2. **Phân tích Bản Đồ Địa Lý & Mô Hình Làm Việc (Geographic & Work Model)**:
   - Tỷ trọng phân bổ việc làm IT giữa các trung tâm lớn: TP. Hồ Chí Minh vs Hà Nội vs Đà Nẵng vs Tỉnh thành khác.
   - Xu hướng làm việc: On-site vs Hybrid vs Remote (Work From Home).
   - So sánh đặc thù tech stack giữa Hà Nội và TP.HCM.
3. **Khai Phá Văn Bản (Text Mining / NLP trên JD & Phúc lợi)**:
   - **Word Cloud**: Trực quan hóa đám mây từ khóa tuyển dụng phổ biến nhất.
   - **N-gram Analysis (Bigrams, Trigrams)**: Phân tích các cụm từ xuất hiện nhiều nhất trong phần yêu cầu tuyển dụng (`requirements_text`), ví dụ: *"khả năng làm việc nhóm"*, *"giao tiếp tiếng anh"*, *"tư duy logic"*.
   - **Phúc lợi đãi ngộ (`benefits_text`)**: Bóc tách top các chế độ phúc lợi phổ biến (Lương tháng 13, Bảo hiểm sức khỏe, Khám sức khỏe định kỳ, Du lịch hằng năm, Cấp laptop MacBook).
   - **Ngôn ngữ bài đăng**: Tỷ lệ bài viết bằng tiếng Anh (`language == 'en'`) vs tiếng Việt (`language == 'vi'`) trên thị trường tuyển dụng.
4. **Mô tả Dữ liệu Chuẩn Mực**:
   - Mỗi biểu đồ phải có diễn giải đầy đủ 3 phần: **1. Số liệu thực tế** -> **2. Nguyên nhân thị trường** -> **3. Hàm ý thực tiễn**.

---

## 📂 2. File Sẽ Làm Việc

* **Jupyter Notebook chính**: [`notebooks/02_eda_skills_geo_textmining.ipynb`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/notebooks/02_eda_skills_geo_textmining.ipynb)
* **Báo cáo tóm tắt Markdown**: [`docs/eda_skills_nlp_report.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/eda_skills_nlp_report.md)
* **File dữ liệu đầu vào**: `data/processed/combined_jobs.json` (File JSON mảng tổng hợp do bạn Thuận cung cấp)

---

## 📊 3. Danh Mục Các Biểu Đồ Bắt Buộc Phải Vẽ (Visualizations)

| STT | Loại biểu đồ | Biến phân tích | Mục đích trực quan hóa |
| :---: | :--- | :--- | :--- |
| **1** | **Horizontal Bar Chart** | Top 25 Kỹ năng công nghệ (`skills`) | Nhận diện công nghệ "vua" đang thống trị thị trường IT Việt Nam. |
| **2** | **Heatmap Ma Trận Đồng Xuất Hiện** | Ma trận cặp kỹ năng (Co-occurrence) | Phân tích các cụm tech stack đi liền nhau (Backend, Frontend, DevOps, Data). |
| **3** | **Bar / Donut Chart** | Địa điểm (`location_text`: HCM, HN, ĐN) | Xác định thủ phủ việc làm công nghệ tại Việt Nam. |
| **4** | **Stacked Bar Chart** | Địa điểm vs Tỷ lệ yêu cầu Tiếng Anh (`language`) | So sánh tỷ lệ công ty quốc tế (dùng tiếng Anh) giữa Hà Nội và TP.HCM. |
| **5** | **Word Cloud** | `description_text` & `requirements_text` | Trực quan hóa các khái niệm và kỳ vọng trọng tâm của nhà tuyển dụng. |
| **6** | **Top Bigrams Bar Chart** | Cụm 2 từ (Bigrams) trong yêu cầu công việc | Khám phá các yêu cầu kỹ năng mềm và kỹ năng phụ trợ thường gặp. |
| **7** | **Horizontal Bar Chart** | Phúc lợi (`benefits_text`) | Thống kê tỷ lệ các gói đãi ngộ phổ biến thu hút nhân tài IT. |

---

## 📝 4. Khung Mẫu Mô Tả Dữ Liệu Chuẩn (Template Viết Nhận Xét)

```markdown
### 📈 Phân tích Biểu đồ 2: Ma trận Đồng xuất hiện Kỹ năng Công nghệ (Co-occurrence Heatmap)

* **Quan sát thực nghiệm (Empirical Findings)**:
  - Cặp công nghệ có tần suất xuất hiện cùng nhau cao nhất là **Docker & CI/CD (chiếm 38% các tin tuyển dụng Backend/DevOps)**, tiếp theo là **React & TypeScript (34%)**, và **Python & SQL (31%)**.
  - Đối với mảng Backend, Java có độ liên kết cao nhất với Spring Boot và PostgreSQL, trong khi PHP hầu như chỉ đồng xuất hiện với Laravel và MySQL.

* **Nguyên nhân thị trường (Market Context)**:
  - Sự bùng nổ của kiến trúc Microservices và Cloud-Native khiến việc biết lập trình đơn thuần không còn đủ; nhà tuyển dụng hiện nay mặc định yêu cầu lập trình viên phải có kỹ năng containerization (Docker) và tự động hóa triển khai (CI/CD).
  - TypeScript đã trở thành tiêu chuẩn công nghiệp (de-facto standard) trong các dự án React chuyên nghiệp tại Việt Nam.

* **Hàm ý thực tiễn (Actionable Takeaway)**:
  - Sinh viên theo đuổi Frontend không nên dừng lại ở JavaScript thuần mà bắt buộc phải trang bị thêm TypeScript. Lập trình viên Backend cần học thêm Docker ngay từ trên ghế nhà trường để gia tăng tính cạnh tranh.
```

---

## 📤 5. Output Kỳ Vọng & Tiêu Chuẩn Nghiệm Thu

1. **Jupyter Notebook chạy hoàn chỉnh (`Restart & Run All`)**:
   - Sử dụng các thư viện: `pandas`, `matplotlib`, `seaborn`, `wordcloud`, `nltk` (hoặc `underthesea` xử lý tiếng Việt).
2. **File báo cáo Markdown**: [`docs/eda_skills_nlp_report.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/eda_skills_nlp_report.md) có đầy đủ ảnh biểu đồ minh họa trích xuất từ notebook.

---

## 🌿 6. Hướng Dẫn Git Workflow (Kéo Code, Tạo Nhánh & Push)

```bash
# 1. Kéo code mới nhất từ main
git checkout main
git pull origin main

# 2. Tạo nhánh làm việc cho EDA Skills & NLP
git checkout -b feature/eda-skills-nlp-khoa

# 3. Mở Jupyter Notebook và thực hiện phân tích
# Lưu biểu đồ vào thư mục docs/images/

# 4. Kiểm tra git status và commit
git status
git add notebooks/02_eda_skills_geo_textmining.ipynb docs/eda_skills_nlp_report.md
git commit -m "feat(eda): complete skills co-occurrence, geographic distribution and nlp text mining"

# 5. Đẩy nhánh lên GitHub
git push -u origin feature/eda-skills-nlp-khoa

# 6. Mở Pull Request vào main để nhóm cùng review
```
