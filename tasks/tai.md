# 📋 Bản Giao Việc Chi Tiết — Tài (Chuyên Đề EDA 1)

> **Dự án**: VN-IT-Job-Mining — Hệ thống Thu thập & Khai phá Dữ liệu Tuyển dụng IT Việt Nam  
> **Người thực hiện**: Tài  
> **Vai trò**: Data Analyst / Data Scientist — Phụ trách **Chuyên Đề EDA 1: Phân Phối Mức Lương, Cấu Trúc Thị Trường & Cấp Bậc Kinh Nghiệm**  
> **Ngày giao việc**: 2026-10-08  
> **Tài liệu gốc tham chiếu**: [`docs/crawler_api_analysis.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawler_api_analysis.md) | [`TASKS.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/TASKS.md)

---

## 🎯 1. Mục Tiêu & Công Việc Cần Làm

Bạn chuyển giao phần thu thập dữ liệu để chuyên tâm 100% vào **Khai phá & Phân tích Khám phá Dữ liệu (EDA - Exploratory Data Analysis)**. Trọng tâm của bạn là bóc tách và trực quan hóa toàn bộ bức tranh tài chính (lương bổng), cấp bậc và độ tin cậy của tập dữ liệu tuyển dụng IT tại Việt Nam.

Nhiệm vụ cụ thể của bạn gồm:
1. **Phân tích Chất lượng Dữ liệu & Mức độ Khuyết thiếu (Data Quality & Missing Values)**:
   - Thống kê tỷ lệ dữ liệu khuyết (`null/missing`) trên các trường quan trọng (`salary_min`, `salary_max`, `skills`, `experience`, `benefits`,...) giữa các sàn tuyển dụng.
2. **Phân tích Chuyên sâu về Mức Lương (Salary Landscape)**:
   - Tỷ lệ tin công khai lương vs tin giấu lương (*"Thương lượng"*, *"Thỏa thuận"*, *"Đăng nhập để xem"*).
   - Phân phối mức lương tối thiểu (`Salary Min`) và tối đa (`Salary Max`) theo đơn vị triệu VNĐ/tháng.
   - So sánh dải lương giữa các sàn tuyển dụng (TopDev, VietnamWorks, ITviec, TopCV, Việc Làm 24h, Glints).
   - Tương quan giữa Mức lương và Cấp bậc (Intern/Fresher -> Junior -> Middle -> Senior -> Tech Lead/Manager).
   - Tương quan giữa Mức lương và Số năm kinh nghiệm.
3. **Mô tả Dữ liệu Chuẩn Mực (Data Storytelling & Insights)**:
   - Mỗi biểu đồ **bắt buộc** phải đi kèm 3 nội dung phân tích:
     * **1. Số liệu thực tế**: Min, Max, Median, IQR, Mean, Skewness, tỷ lệ phần trăm %.
     * **2. Nguyên nhân thị trường**: Giải thích vì sao có hiện tượng đó trong ngành CNTT Việt Nam.
     * **3. Hàm ý thực tiễn (Actionable Insight)**: Đưa ra lời khuyên thực tế cho sinh viên IT UTH hoặc ứng viên tìm việc.

---

## 📂 2. File Sẽ Làm Việc

* **Jupyter Notebook chính**: [`notebooks/01_eda_salary_and_market_structure.ipynb`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/notebooks/01_eda_salary_and_market_structure.ipynb)
* **Báo cáo tóm tắt Markdown**: [`docs/eda_salary_report.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/eda_salary_report.md)
* **File dữ liệu đầu vào**: `data/processed/combined_jobs.json` (File JSON mảng tổng hợp từ 7 nguồn do bạn Thuận cung cấp)

---

## 📊 3. Danh Mục Các Biểu Đồ Bắt Buộc Phải Vẽ (Visualizations)

| STT | Loại biểu đồ | Biến phân tích | Mục đích trực quan hóa |
| :---: | :--- | :--- | :--- |
| **1** | **Stacked Bar Chart** | `source` vs tỷ lệ `null` của từng trường | Đánh giá độ hoàn thiện và sàn nào cung cấp dữ liệu sạch nhất. |
| **2** | **Donut Chart** | `is_negotiable` (Công khai vs Thỏa thuận) | Đo lường tính minh bạch về thu nhập của thị trường IT Việt Nam. |
| **3** | **Histogram & KDE Plot** | `salary_min`, `salary_max` (triệu VNĐ) | Khảo sát hình dạng phân phối lương (phân phối chuẩn hay lệch phải Skewed-right). |
| **4** | **Boxplot & Violin Plot** | `source` vs `salary_max` | So sánh dải lương giữa các sàn tuyển dụng và phát hiện ngoại lai (Outliers). |
| **5** | **Grouped Bar / Boxplot** | `seniority_text` vs `salary_min` & `salary_max` | Bậc thang thu nhập theo cấp bậc từ Intern đến Manager. |
| **6** | **Scatter Plot + Regression**| `years_of_experience` vs `salary_max` | Khảo sát tốc độ tăng lương theo số năm kinh nghiệm (Linear vs Exponential). |

---

## 📝 4. Khung Mẫu Mô Tả Dữ Liệu Chuẩn (Template Viết Nhận Xét)

Để đạt điểm tối đa môn Khai phá Dữ liệu / Data Science, bạn phải trình bày theo khung chuẩn sau dưới mỗi biểu đồ:

```markdown
### 📈 Phân tích Biểu đồ 3: Phân phối Mức Lương Tuyển dụng IT (KDE & Histogram)

* **Quan sát thực nghiệm (Empirical Findings)**:
  - Mức lương tối thiểu dao động chủ yếu trong khoảng 10.0 – 25.0 triệu VNĐ (chiếm 65% tổng số tin công khai lương).
  - Mức lương trung vị (Median) đạt **22.5 triệu VNĐ/tháng**, trong khi giá trị trung bình (Mean) là **28.2 triệu VNĐ/tháng**.
  - Đồ thị phân phối bị lệch phải rõ rệt (Positive Skewness = 1.84), kéo dài bởi nhóm vị trí cấp cao (Architect, Director với mức lương > 80 triệu VNĐ).

* **Nguyên nhân thị trường (Market Context)**:
  - Sự chênh lệch giữa Median và Mean phản ánh tính phân hóa mạnh mẽ của ngành IT: nhóm nhân sự phổ thông chiếm số đông ở dải 15–25 triệu, trong khi các chuyên gia AI, Cloud Solution, FinTech nhận mức lương vượt trội kéo lệch giá trị trung bình.

* **Hàm ý thực tiễn (Actionable Takeaway)**:
  - Ứng viên mới ra trường nên lấy mốc Median (khoảng 12–15 triệu cho Fresher) làm mốc thương lượng thực tế, tránh bị nhiễu bởi các tin tuyển dụng cá biệt quảng cáo mức lương "nghìn đô".
```

---

## 📤 5. Output Kỳ Vọng & Tiêu Chuẩn Nghiệm Thu

1. **Jupyter Notebook chạy mượt mà từ đầu đến cuối (`Restart & Run All`)**:
   - Sử dụng thư viện chuẩn: `pandas`, `numpy`, `matplotlib`, `seaborn` (theme nhất quán `sns.set_theme(style="whitegrid")`).
   - Có bảng mô tả thống kê: `.describe()`, kiểm tra phân vị `25%`, `50%`, `75%`.
2. **File báo cáo Markdown**: [`docs/eda_salary_report.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/eda_salary_report.md) đính kèm ảnh biểu đồ đã lưu (`docs/images/salary_*.png`).

---

## 🌿 6. Hướng Dẫn Git Workflow (Kéo Code, Tạo Nhánh & Push)

> [!CAUTION]
> **QUY TẮC BẮT BUỘC TRƯỚC KHI BẮT ĐẦU**:
> 1. Luôn chuyển về `main` và kéo code mới nhất từ remote: `git checkout main && git pull origin main`.
> 2. **BẮT BUỘC TẠO NHÁNH RIÊNG** cho nhiệm vụ của mình: `git checkout -b feature/eda-salary-tai`.  
>    🚫 **TUYỆT ĐỐI KHÔNG** commit hoặc viết code trực tiếp trên nhánh `main`!
> 3. Sau khi hoàn thành và có báo cáo/notebook, push nhánh lên GitHub và tạo Pull Request để Team Leader (@billtran) review và merge.

```bash
# 1. Kéo code mới nhất từ main
git checkout main
git pull origin main

# 2. Bắt buộc tạo nhánh riêng cho mình từ main
git checkout -b feature/eda-salary-tai

# 3. Mở Jupyter Notebook và thực hiện phân tích
# (Chạy lệnh: jupyter notebook hoặc mở trong VS Code)
# Lưu ý: Nhớ xuất biểu đồ ra thư mục docs/images/

# 4. Kiểm tra git status và commit
git status
git add notebooks/01_eda_salary_and_market_structure.ipynb docs/eda_salary_report.md
git commit -m "feat(eda): complete salary distribution, market structure and seniority analysis"

# 5. Đẩy nhánh lên GitHub
git push -u origin feature/eda-salary-tai

# 6. Mở Pull Request vào main để nhóm review
```
