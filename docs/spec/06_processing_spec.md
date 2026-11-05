# ĐẶC TẢ BIẾN ĐỔI DỮ LIỆU & TRÍCH XUẤT ĐẶC TRƯNG
## MODULE 06: DATA TRANSFORMATION & FEATURE ENGINEERING SPECIFICATION

> **Tài liệu đặc tả kỹ thuật hệ thống (System Specification Document)**  
> **Dự án:** Phân tích thị trường việc làm IT Việt Nam (VN-IT-Job-Mining)  
> **Phiên bản:** 2.0 — Cập nhật: Tháng 11/2026  
> **Trạng thái:** Official Technical Specification  
> **Phạm vi xử lý:** Chuyển đổi dữ liệu từ tầng Silver (Cleaned Tabular) sang tầng Gold (Curated Features & Mining Matrices).

---

## 1. Tổng Quan Chuyển Đổi Silver $\rightarrow$ Gold

Tầng Silver cung cấp dữ liệu dạng bảng sạch (`all.parquet`), đã giải quyết các vấn đề bóc tách HTML, khử trùng lặp nội sàn/đa sàn và sửa lỗi bảng mã Unicode. Tuy nhiên, các thuộc tính cốt lõi như kỹ năng, cấp bậc, nhóm nghề và mức lương vẫn đang tồn tại dưới dạng chuỗi văn bản tự do (Free-form text) hoặc mảng danh sách thô.

**Tầng Gold (Transformation & Feature Engineering)** chịu trách nhiệm:
1. Chuẩn hóa phân loại vị trí công việc vào **12 Job Families chuẩn**.
2. Phân cấp và đồng nhất kỹ năng IT qua **Taxonomy 6 nhóm cốt lõi** và từ điển Alias Normalization.
3. Bóc tách và quy đổi chuẩn hóa mức lương về thang đo duy nhất (**Triệu VNĐ / Tháng**).
4. Sinh các cấu trúc dữ liệu nâng cao phục vụ trực tiếp cho các thuật toán Khai phá dữ liệu (Data Mining):
   - **One-Hot / Multi-Hot Binary Matrix:** Cho khai phá luật kết hợp (Association Rules: Apriori / FP-Growth).
   - **Co-occurrence Matrix:** Cho phân tích đồ thị và tương quan cặp kỹ năng (Skill Graph Network).
   - **TF-IDF Vector Space:** Cho phân cụm văn bản (Clustering: K-Means / HDBSCAN) và tìm kiếm ngữ nghĩa.

```mermaid
flowchart TD
    Silver["Silver Layer: all.parquet\n(Cleaned & Curated Master Jobs)"] --> TransformEngine["ENGINE BIẾN ĐỔI & TRÍCH XUẤT ĐẶC TRƯNG"]
    
    subgraph FeatureEngineering["Transformation & Feature Pipeline"]
        direction TB
        F1["1. Domain & Job Role Tagging\n(12 Job Families + Seniority Levels)"]
        F2["2. IT Skill Taxonomy & Alias Mapping\n(6 Categories + Boundary Disambiguation)"]
        F3["3. Universal Salary Normalization\n(Regex Cascade + USD/VND 25,400 + Period Calc)"]
        F4["4. Mining Matrices Generation\n(Multi-Hot + Co-occurrence + TF-IDF)"]
        F1 --> F2 --> F3 --> F4
    end
    
    TransformEngine --> FeatureEngineering
    FeatureEngineering --> GoldTables["GOLD LAKEHOUSE LAYER"]
    
    subgraph GoldArtifacts["Gold Data Products"]
        G1["gold_master_jobs.parquet\n(Bảng việc làm chuẩn hóa hoàn chỉnh)"]
        G2["features.parquet\n(Bảng đặc trưng số học cho Machine Learning)"]
        G3["matrix_skill_onehot.parquet\n(Ma trận nhị phân M jobs x N skills)"]
        G4["matrix_skill_cooccurrence.parquet\n(Ma trận đồng xuất hiện N x N skills)"]
    end
    
    GoldTables --> GoldArtifacts
```

---

## 2. Chuẩn Hóa & Gán Nhãn Nhóm Nghề IT (Domain & Job Role Classification)

Để phân tích cơ cấu cung - cầu lao động, mọi tin tuyển dụng phải được gán nhãn vào một trong **12 Job Family chuẩn** của ngành CNTT tại Việt Nam, kết hợp cùng cấp bậc kinh nghiệm (**Seniority Level**).

### 2.1. Phân Loại 12 Job Family Chuẩn
Hệ thống sử dụng cơ chế luật kết hợp (Title Keyword Matching + JD Context/Skill Constraints) với thứ tự ưu tiên xác định:

| STT | Job Family | Từ Khóa Nhận Diện Trong Tiêu Đề (`job_title`) | Kỹ Năng Ràng Buộc Trong JD |
|---|---|---|---|
| 1 | **Kiểm thử (QA/QC)** | `tester`, `qa`, `qc`, `quality assurance`, `automation test`, `manual test`, `kiểm thử`, `sqa` | `Selenium`, `Cypress`, `Postman`, `JMeter`, `Appium` |
| 2 | **Bảo mật (Security)** | `security`, `soc`, `pentest`, `cyber`, `an ninh mạng`, `bảo mật`, `infosec`, `siem`, `devsecops` | `Penetration Testing`, `Firewall`, `SIEM`, `OWASP`, `CISSP` |
| 3 | **Phân tích nghiệp vụ (BA)**| `business analyst`, `ba`, `phân tích nghiệp vụ`, `product analyst`, `system analyst` | `UML`, `BPMN`, `User Story`, `BRD`, `Jira`, `SQL` |
| 4 | **Thiết kế UI/UX** | `ui/ux`, `ux/ui`, `ui designer`, `ux designer`, `product designer`, `thiết kế giao diện` | `Figma`, `Adobe XD`, `Sketch`, `Wireframing`, `Prototyping` |
| 5 | **Quản lý SP/DA** | `product manager`, `project manager`, `scrum master`, `pm`, `po`, `product owner` | `Agile`, `Scrum`, `Sprint Planning`, `Kanban`, `Roadmapping` |
| 6 | **DevOps/Cloud** | `devops`, `cloud`, `sre`, `infrastructure`, `ci/cd`, `sysadmin`, `site reliability` | `Docker`, `Kubernetes`, `AWS`, `Terraform`, `CI/CD`, `Linux` |
| 7 | **Hệ thống/Mạng** | `system engineer`, `network engineer`, `kỹ sư hệ thống`, `quản trị mạng`, `helpdesk` | `Cisco`, `CCNA`, `Routing`, `Switching`, `TCP/IP`, `Windows Server` |
| 8 | **Data/AI** | `data engineer`, `data analyst`, `data scientist`, `ai`, `machine learning`, `bi`, `nlp` | `Python`, `SQL`, `Spark`, `TensorFlow`, `PyTorch`, `Power BI` |
| 9 | **Mobile** | `mobile`, `android`, `ios`, `flutter`, `react native`, `swift`, `kotlin developer` | `Flutter`, `React Native`, `iOS`, `Android`, `Swift`, `Kotlin` |
| 10 | **Fullstack** | `fullstack`, `full stack`, `full-stack`, `toàn diện` | $\ge 1$ Backend Skill VÀ $\ge 1$ Frontend Skill |
| 11 | **Frontend** | `frontend`, `front-end`, `front end`, `web client`, `reactjs developer`, `vue developer` | `React`, `Vue`, `Angular`, `JavaScript`, `HTML/CSS`, `TypeScript` |
| 12 | **Backend** | `backend`, `back-end`, `back end`, `server-side`, `java dev`, `golang dev`, `.net dev` | `Java`, `Spring Boot`, `Node.js`, `Go`, `Python`, `C#`, `PHP` |

- **Giải quyết nhập nhằng (Disambiguation Logic):**
  - Ưu tiên các nhóm nghề chuyên biệt hẹp trước (QA/QC, Security, BA, UI/UX, Quản lý) để tránh bị rơi nhầm vào nhóm lập trình chung.
  - Vị trí `Fullstack` yêu cầu trong phần mô tả công việc (JD) bắt buộc phải xuất hiện đồng thời kỹ năng thuộc nhóm Backend (ví dụ: `Node.js`, `Java`, `Go`) và Frontend (ví dụ: `React`, `Vue`, `TypeScript`). Nếu chỉ có kỹ năng phía máy chủ, tin sẽ tự động hạ cấp về `Backend`.

### 2.2. Chuẩn Hóa Cấp Bậc Kinh Nghiệm (Seniority Level Mapping)
Cấp bậc được chuẩn hóa thành 6 nhãn theo thứ bậc thứ tự (Ordinal Encoding từ 0 đến 5, gán -1 cho "Chưa rõ"):

$$\text{Seniority} \in \{\text{Thực tập (0)}, \text{Mới tốt nghiệp/Fresher (1)}, \text{Junior (2)}, \text{Middle (3)}, \text{Senior (4)}, \text{Trưởng nhóm/Quản lý (5)}\}$$

```python
SENIORITY_RULES = [
    ("Thực tập", [r"\bintern\b", r"\binternship\b", r"thực tập", r"thực tập sinh"]),
    ("Mới tốt nghiệp", [r"\bfresher\b", r"mới tốt nghiệp", r"chưa có kinh nghiệm"]),
    ("Junior", [r"\bjunior\b", r"\bjr\b", r"1\s*[-–]\s*2\s*năm"]),
    ("Middle", [r"\bmiddle\b", r"\bmid\b", r"2\s*[-–]\s*4\s*năm"]),
    ("Senior", [r"\bsenior\b", r"\bsr\b", r"chuyên viên cao cấp", r"5\+?\s*năm"]),
    ("Trưởng nhóm/Quản lý", [r"\blead\b", r"\bleader\b", r"trưởng nhóm", r"\bmanager\b", r"quản lý", r"\bdirector\b", r"\bhead of\b"]),
]
```

---

## 3. Bộ Từ Điển Phân Cấp Kỹ Năng IT (IT Skill Taxonomy & Alias Normalization)

Kỹ năng công nghệ là đơn vị phân tích trọng tâm (Atomic Analytical Unit) của đồ án tốt nghiệp. Do các nhà tuyển dụng sử dụng hàng nghìn cách viết hoa-thường, tên gọi thương mại, hoặc từ lóng khác nhau, hệ thống xây dựng cây phân cấp kỹ năng 3 tầng:

$$\text{Category (Nhóm)} \longrightarrow \text{Canonical Skill (Kỹ Năng Chuẩn)} \longrightarrow \text{Aliases (Biến Thể / Từ Đồng Nghĩa)}$$

```mermaid
graph TD
    Taxonomy["IT Skill Taxonomy (6 Trục Cốt Lõi)"]
    
    Taxonomy --> C1["1. Programming Languages"]
    Taxonomy --> C2["2. Frameworks & Libraries"]
    Taxonomy --> C3["3. Databases & Caching"]
    Taxonomy --> C4["4. Cloud & DevOps"]
    Taxonomy --> C5["5. Tools, Protocols & Architecture"]
    Taxonomy --> C6["6. Methodologies & Soft Skills"]
    
    C1 --> S1["Go / Golang"]
    S1 --- A1["Aliases: 'go', 'golang', 'golang developer'"]
    
    C2 --> S2["React"]
    S2 --- A2["Aliases: 'react', 'reactjs', 'react.js', 'react js'"]
    
    C4 --> S3["Kubernetes"]
    S3 --- A3["Aliases: 'kubernetes', 'k8s', 'k8s cluster'"]
```

### 3.1. Bảng Tra Phân Cấp Kỹ Năng IT Chi Tiết (6 Nhóm Cốt Lõi)

#### Nhóm 1: Ngôn Ngữ Lập Trình (Programming Languages)
- **Java:** `java`, `core java`, `java 8`, `java 11`, `java 17`, `java 21`
- **Python:** `python`, `python3`, `py`
- **JavaScript:** `javascript`, `js`, `ecmascript`, `es6`
- **TypeScript:** `typescript`, `ts`
- **Go:** `golang`, `go` (Yêu cầu Regex khớp biên từ `\bgo\b` kèm ngữ cảnh lập trình để tránh nhầm chữ "go" trong tiếng Anh)
- **C#:** `c#`, `csharp`, `c sharp`, `.net c#`
- **C++:** `c++`, `cpp`, `c/c++`
- **PHP:** `php`, `php7`, `php8`
- **Rust:** `rust`, `rustlang`
- **Kotlin:** `kotlin`
- **Swift:** `swift`
- **SQL:** `sql`, `t-sql`, `pl/sql`

#### Nhóm 2: Framework & Thư Viện (Frameworks & Libraries)
- **React:** `react`, `reactjs`, `react.js`
- **Next.js:** `next.js`, `nextjs`, `next`
- **Vue.js:** `vue`, `vuejs`, `vue.js`, `vue 3`, `nuxt`, `nuxtjs`
- **Angular:** `angular`, `angularjs`, `angular 2+`
- **Spring Boot:** `spring`, `springboot`, `spring boot`, `spring framework`, `spring mvc`
- **Node.js:** `node`, `nodejs`, `node.js`, `express`, `expressjs`, `nestjs`
- **.NET Core:** `.net`, `.net core`, `asp.net`, `asp.net core`, `dotnet`
- **Django / FastAPI:** `django`, `fastapi`, `flask`
- **Laravel:** `laravel`, `symfony`
- **Flutter:** `flutter`, `dart/flutter`
- **React Native:** `react native`, `react-native`, `rn`

#### Nhóm 3: Cơ Sở Dữ Liệu & Bộ Nhớ Đệm (Databases & Caching)
- **PostgreSQL:** `postgresql`, `postgres`, `psql`
- **MySQL:** `mysql`, `mariadb`
- **MongoDB:** `mongodb`, `mongo`, `nosql mongodb`
- **Redis:** `redis`, `redis cache`
- **Elasticsearch:** `elasticsearch`, `elastic search`, `elk`, `opensearch`
- **SQL Server:** `sql server`, `mssql`, `ms sql`
- **Oracle:** `oracle`, `oracle db`
- **Kafka:** `kafka`, `apache kafka` (Message broker / Streaming)
- **RabbitMQ:** `rabbitmq`, `message queue`

#### Nhóm 4: Điện Toán Đám Mây & Vận Hành (Cloud & DevOps)
- **Docker:** `docker`, `container`, `docker-compose`
- **Kubernetes:** `kubernetes`, `k8s`, `k8s cluster`, `helm`
- **AWS:** `aws`, `amazon web services`, `ec2`, `s3`, `lambda`, `ecs`, `rds`
- **Google Cloud:** `gcp`, `google cloud`, `google cloud platform`, `bigquery`
- **Microsoft Azure:** `azure`, `microsoft azure`
- **CI/CD:** `ci/cd`, `cicd`, `jenkins`, `gitlab-ci`, `github actions`, `argocd`
- **Terraform:** `terraform`, `iac`, `infrastructure as code`
- **Linux:** `linux`, `ubuntu`, `centos`, `bash shell`

#### Nhóm 5: Công Cụ, Kiến Trúc & Giao Thức (Tools, Architecture & Protocols)
- **Git:** `git`, `github`, `gitlab`, `bitbucket`
- **Microservices:** `microservices`, `micro-services`, `service-oriented`
- **REST API:** `restful api`, `rest api`, `restful`, `rest`
- **GraphQL:** `graphql`, `apollo`
- **gRPC:** `grpc`, `protobuf`
- **Design Patterns:** `design patterns`, `oop`, `solid`, `clean architecture`, `ddd`

#### Nhóm 6: Phương Pháp Luận & Kỹ Năng Mềm (Methodologies & Soft Skills)
- **Agile / Scrum:** `agile`, `scrum`, `kanban`, `sprint`
- **Giao tiếp tiếng Anh:** `tiếng anh`, `english`, `toeic`, `ielts`, `fluent english`
- **Giải quyết vấn đề:** `problem solving`, `tư duy logic`, `critical thinking`
- **Làm việc nhóm:** `teamwork`, `làm việc nhóm`, `collaboration`

### 3.2. Cơ Chế Khớp Kỹ Năng Tên Ngắn (Short-name Disambiguation)
Các kỹ năng có tên rất ngắn như **C**, **R**, **Go**, **AI** rất dễ bị kích hoạt sai (False Positive) khi người tuyển dụng viết câu văn thông thường (ví dụ: "chữ **C** trong CEO", "take ca**r**e", "đi lại (**go**)", "b**ai** toán").
- **Quy tắc phân giải ngữ cảnh (Context-Aware Regex):**
  - Kỹ năng `Go`: Khớp `\b(golang|go\s+developer|lập trình\s+go|go\s+language)\b` hoặc `\bgo\b` khi xung quanh có các từ khóa: `backend`, `microservices`, `docker`, `kubernetes`.
  - Kỹ năng `C`: Chỉ chấp nhận khi viết dưới dạng `\bc/c\+\+\b`, `lập trình c\b`, hoặc `c/embedded`.
  - Kỹ năng `R`: Chỉ khớp khi nằm trong ngữ cảnh phân tích dữ liệu: `\br\s+programming\b`, `python/r`, `r\s+studio`.

---

## 4. Chuẩn Hóa Mức Lương (Universal Salary Normalization)

Bài toán chuẩn hóa lương đối mặt với sự phân mảnh lớn: có tin ghi USD, có tin ghi triệu VND; có tin tính theo giờ, tháng, năm; có tin ghi dạng "Từ 15 triệu", "Up to $2,000", "15 - 25 triệu".

### 4.1. Quy Chuẩn Đơn Vị Đích & Tỷ Giá Chuẩn
- **Đơn vị đích duy nhất:** **Triệu VNĐ / Tháng** (`salary_min_mil_vnd`, `salary_max_mil_vnd`, `salary_avg_mil_vnd`).
- **Tỷ giá ngoại tệ chuẩn (Standard FX Rate):**
  $$1 \text{ USD} = 25.400 \text{ VNĐ}$$
  (Tỷ giá liên ngân hàng tháng 10-11/2026, cố định phục vụ tính toán khoa học cho đồ án).

### 4.2. Giải Thuật Bóc Tách Đa Tầng (Cascade Regex Extractor)

```mermaid
flowchart TD
    RawInput["Chuỗi Văn Bản Lương Thô"] --> CheckNegotiable{"Khớp từ khóa Thỏa thuận?\n(cạnh tranh, thỏa thuận, deal, negotiable)"}
    CheckNegotiable -- "Đúng" --> SetFlag["is_salary_negotiable = True\nsalary_min = NaN, salary_max = NaN"]
    CheckNegotiable -- "Sai" --> ParseCascade["Universal Salary Parser"]
    
    ParseCascade --> T2a["T2a: Phân biệt hàng nghìn vs thập phân\n(2,000 -> 2000 vs 8.5 -> 8.5)"]
    T2a --> T2bc["T2b & T2c: Xử lý cận mở\n('Từ X' -> min=X, max=None)\n('Up to Y' -> min=None, max=Y)"]
    T2bc --> T2d["T2d: Quy đổi chu kỳ & tiền tệ\n(Năm -> /12, Giờ -> *160, USD -> *25,400)"]
    T2d --> T2f["T2f: Đưa về Triệu VNĐ\nsalary_avg = (min + max) / 2"]
```

1. **Phân biệt dấu phân cách số (T2a):**
   - Số hàng nghìn: `2,000` hoặc `2.000` hoặc `25,000,000` $\rightarrow$ loại bỏ ký tự ngăn cách, đưa về số nguyên.
   - Số thập phân: `8.5` triệu hoặc `8,5` triệu $\rightarrow$ chuẩn hóa thành `8.5`.
2. **Xử lý khoảng chặn một đầu (T2b, T2c):**
   - Mẫu `"Từ X"` (ví dụ: "Từ 20 triệu"): Gán `salary_min = X`, `salary_max = NaN`.
   - Mẫu `"Lên tới Y"`, `"Up to Y"` (ví dụ: "Up to $2,500"): Gán `salary_min = NaN`, `salary_max = Y`.
   - Mẫu `"X - Y"` (ví dụ: "15 - 25 triệu"): Gán `salary_min = X`, `salary_max = Y`.
3. **Quy đổi chu kỳ thời gian (Period Normalization):**
   - Theo năm: $\text{Lương tháng} = \text{Lương năm} / 12$.
   - Theo giờ: $\text{Lương tháng} = \text{Lương giờ} \times 160$ (chuẩn 160 giờ làm việc/tháng).
   - Theo ngày: $\text{Lương tháng} = \text{Lương ngày} \times 22$ (chuẩn 22 ngày công/tháng).
4. **Tính toán lương đại diện (Representative Salary):**
   $$\text{salary\_avg} = \begin{cases} 
   \frac{\text{salary\_min} + \text{salary\_max}}{2} & \text{khi cả hai đều có giá trị} \\
   \text{salary\_min} & \text{khi chỉ có min} \\
   \text{salary\_max} & \text{khi chỉ có max} \\
   \text{NaN} & \text{khi lương thỏa thuận}
   \end{cases}$$

---

## 5. Sinh Ma Trận Kỹ Năng Cho Khai Phá Dữ Liệu (Feature Matrices Generation)

Để các thuật toán Data Mining (Khai phá luật kết hợp Apriori/FP-Growth, Phân cụm K-Means, Phân tích đồ thị mạng xã hội kỹ năng) có thể hoạt động trực tiếp, hệ thống sinh ra 3 ma trận đặc trưng từ tập dữ liệu Gold.

### 5.1. Ma Trận Nhị Phân Kỹ Năng (One-Hot / Multi-Hot Skill Matrix)
- **Kích thước:** Ma trận $M \times K$, trong đó:
  - $M$: Số lượng tin tuyển dụng IT hợp lệ ($M \approx 5.000 - 15.000$ bài đăng).
  - $K$: Số lượng kỹ năng chuẩn hàng đầu (chọn top $K$ kỹ năng có tần suất xuất hiện $\ge 20$ lần, thường $K \in [100, 200]$ kỹ năng).
- **Định nghĩa phần tử:**
  $$X_{ij} = \begin{cases} 1 & \text{nếu công việc } i \text{ yêu cầu kỹ năng } j \\ 0 & \text{ngược lại} \end{cases}$$
- **Ứng dụng khai phá:**
  - Thuật toán **Apriori** và **FP-Growth** chạy trực tiếp trên ma trận nhị phân này để tìm các **Tập kỹ năng phổ biến (Frequent Itemsets)** và các **Luật kết hợp (Association Rules)**.
  - Ví dụ phát hiện luật: $\{\text{React}\} \Rightarrow \{\text{TypeScript}\}$ (Độ tin cậy $\text{Confidence} = 78\%$, Độ nâng $\text{Lift} = 3.2$).

### 5.2. Ma Trận Kỹ Năng Đồng Xuất Hiện (Skill Co-occurrence Matrix)
- **Kích thước:** Ma trận vuông đối xứng $K \times K$.
- **Định nghĩa toán học:**
  $$\mathbf{C} = \mathbf{X}^T \mathbf{X}$$
  Trong đó phần tử $C_{jk}$ tại dòng $j$, cột $k$ đại diện cho số lượng bài đăng tuyển dụng yêu cầu **đồng thời cả hai kỹ năng $j$ và $k$**:
  $$C_{jk} = \sum_{i=1}^M X_{ij} X_{ik}$$
  - Đường chéo chính $C_{jj}$ chính là tần suất xuất hiện độc lập của kỹ năng $j$.
- **Ứng dụng khai phá:**
  - Xây dựng **Skill Graph Network**: Mỗi node là một kỹ năng, trọng số của cạnh (Edge weight) là $C_{jk}$.
  - Thuật toán phát hiện cộng đồng (Community Detection - Louvain Algorithm) trên ma trận này để tự động gom cụm các hệ sinh thái công nghệ (ví dụ: Cụm Java Enterprise, Cụm Modern Web React/Node, Cụm Cloud Data Engineering).

```
          Java   Spring  Docker  React  TypeScript
Java      1250    980     620     110      85
Spring     980   1020     580      90      70
Docker     620    580    1450     450     520
React      110     90     450    1800    1420
TypeScript  85     70     520    1420    1650
```

### 5.3. Không Gian Vector TF-IDF Của Mô Tả Tuyển Dụng (TF-IDF Vector Space)
- **Mục đích:** Chuyển hóa toàn bộ nội dung văn bản mô tả công việc (JD) thành không gian vector số học nhằm phân cụm bài viết (Job Clustering) và phát hiện các bài tuyển dụng có nội dung tương tự.
- **Tham số cấu hình:**
  - Thư viện: `scikit-learn TfidfVectorizer`.
  - Dải N-gram: $(1, 2)$ (từ đơn và từ ghép 2 từ).
  - Tần suất tài liệu tối thiểu (`min_df = 5`): Loại bỏ các từ quá hiếm gặp.
  - Tần suất tài liệu tối đa (`max_df = 0.8`): Loại bỏ các từ xuất hiện trong hơn 80% tài liệu (từ phổ thông, stop words).
  - Kích thước không gian vector: Giới hạn `max_features = 3000` thuộc tính quan trọng nhất.
- **Ứng dụng khai phá:**
  - Sử dụng cho thuật toán phân cụm **K-Means / HDBSCAN** để tìm kiếm các phân khúc công việc ẩn (Latent Job Profiles) mà tiêu đề bài viết chưa phản ánh hết.
  - Giảm chiều dữ liệu với **PCA / t-SNE / UMAP** để trực quan hóa toàn bộ thị trường lao động IT lên biểu đồ phân tán 2D trên Dashboard.
