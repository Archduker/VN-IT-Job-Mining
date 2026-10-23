# VN-IT-Job-Mining Central Observatory & Monitoring Platform

Hệ thống Giám sát & Đo lường Toàn diện cho nền tảng khai phá dữ liệu tuyển dụng CNTT Việt Nam (**VN-IT-Job-Mining**).

---

## 🎯 Sứ Mệnh Cốt Lõi (Core Mission)

> **Mục tiêu tối thượng của hệ thống Monitoring**:
> **Miêu tả hình ảnh thực tế của dữ liệu thông qua các thông số và biểu đồ liên tục, liền mạch theo từng bước; giúp nhóm kỹ sư dễ dàng theo dõi biến thiên chất lượng từ thô đến tinh, từ đó đưa ra BỘ DỮ LIỆU HOÀN CHỈNH NHẤT (Golden Master Dataset).**

Hệ thống được thiết kế theo nguyên tắc **Upscale dễ dàng**, cho phép mở rộng các nguồn cào mới, các quy tắc tiền xử lý hoặc các mô hình AI/ML mà không làm gián đoạn tính liên tục của các biểu đồ trực quan.

---

## 🔄 Quy Trình Pipeline 3 Giai Đoạn Chuẩn Hóa

$$\textbf{1. Collection} \longrightarrow \textbf{2. Pre-processing} \longrightarrow \textbf{3. Processing} \Longrightarrow \textbf{Golden Master (api/Dashboard)}$$

1. **Giai Đoạn 1: Collection (Thu thập thô nguyên bản — Zero Information Loss)**
   - *1.1 URL Discovery*: Quét phân vùng danh mục không giới hạn thời gian (`url_ledger/`).
   - *1.2 Detail Extraction*: Bóc tách theo kiến trúc 2 pha, cơ chế Safe Skip bắt lỗi an toàn (404/500 không sập tiến trình).
   - *1.3 As-Is Lakehouse Ingestion*: Lưu trữ phân vùng Envelope JSON (`raw/<source>/YYYY-MM-DD/*.json`).
   - *1.4 Collection EDA*: Bảng kiểm kê trường DOM thô (Field Inventory) và tỷ lệ khuyết thiếu ban đầu.

2. **Giai Đoạn 2: Pre-processing (Tiền xử lý & Chuẩn hóa dữ liệu)**
   - *2.1 Field Unification*: Regex bóc tách dải lương số học (`salary_min_vnd`, `salary_max_vnd`), quy đổi USD sang VND, parse năm kinh nghiệm `min_experience_years`.
   - *2.2 Text Sanitization*: Bóc bỏ thẻ HTML rác, unescape ký tự đặc biệt, chuẩn hóa mảng bullet `description_list`.
   - *2.3 Tag Categorization*: Phân nhóm rõ ràng 3 cụm thẻ: Yêu cầu, Quyền lợi và Kỹ năng chuyên môn.
   - *2.4 Pre-processing EDA*: Đo lường tỷ lệ parse regex thành công và mức độ giảm tỷ lệ khuyết thiếu (Null Reduction Rate).

3. **Giai Đoạn 3: Processing (Tích hợp, Khử trùng lặp & Khai phá AI/ML)**
   - *3.1 Schema Harmonization*: Ánh xạ 8 proprietary schemas về **Common Target Schema v1**.
   - *3.2 Entity Resolution*: Sử dụng Sentence-Transformers tính Cosine Similarity tiêu đề và công ty để loại bỏ bài đăng trùng lặp xuyên sàn.
   - *3.3 Golden Master Dataset Assembly*: Đóng gói tập dữ liệu vàng sạch vào phân tầng `curated/golden_master/` (định dạng Parquet).
   - *3.4 AI/ML 3D Spatial Lab*: Trực quan hóa không gian đa chiều WebGL 60 FPS (UMAP 3D Embeddings và ranh giới phân tách tin rác Isolation Forest).

---

## 🌟 Trung Tâm Điều Hành: Executive Master Dashboard (`api/Dashboard`)

Endpoint: `GET /api/dashboard` (hoặc `GET /api/v1/dashboard`) phục vụ toàn bộ thông số vĩ mô của bộ dữ liệu sau khi integration:
- Tổng số bài đăng duy nhất sau khử trùng lặp.
- Tỷ lệ giảm trùng lặp toàn hệ thống (Deduplication Rate %).
- Bảng độ hội tụ Schema đích (100% mục tiêu).
- Phân bổ tỷ trọng đóng góp từ 8 sàn (TopCV, ITviec, TopDev, CareerViet, Vieclam24h, VietnamWorks, Glints, JobsGO).
- Phân phối mức lương chuẩn thị trường IT Việt Nam (P25, Median, Mean, P75).
- Top kỹ năng công nghệ vàng theo từ điển chuẩn ESCO.
- Dòng chảy dữ liệu (Data Lineage tracking).

---

## ☁️ Hạ Tầng Cloud Lakehouse (Độc Quyền Cloudflare R2)

Dự án chuẩn hóa **100% độc quyền trên Cloudflare R2** (`vn-it-jobs`). Toàn bộ cấu hình MinIO cục bộ và thư viện `boto3` dùng chung cho S3 generic đã được loại bỏ.

- **R2 Diff Engine**: So khớp theo thời gian thực tổng số tệp cục bộ (`data/<source>/raw/`) và đám mây R2 (`raw/<source>/`).
- **Đồng Bộ 1-Click**: Nút bấm kích hoạt tải lên R2 trực tiếp từ giao diện giám sát cho từng sàn.
- **4 Phân Tầng Lakehouse**: `url_ledger/`, `raw/`, `staging/`, `curated/`.

---

## ⚙️ Điều Phối Apache Airflow (Orchestration Monitor)

Giao diện giám sát vận hành Airflow trực tiếp:
- Theo dõi PID Scheduler & Webserver (Port 8080).
- Trực quan hóa 7 DAGs xoay vòng hàng ngày (`crawler_topdev`, `crawler_careerviet`, `crawler_itviec`, `crawler_vietnamworks`, `crawler_topcv`, `crawler_vieclam24h`, `crawler_glints`).
- Đọc trực tiếp trạng thái run từ SQLite metadata DB (`airflow/airflow.db`).

---

## 🔒 Quy Chuẩn Zero-Auth (Không Cần Đăng Nhập)

Hệ thống tuân thủ nghiêm ngặt **Quy chuẩn Zero-Auth** đặt tại [`.agents/rules/monitoring_system_rules.md`](../.agents/rules/monitoring_system_rules.md):
- Hoàn toàn loại bỏ form login, avatar tài khoản, hay cơ chế chặn phân quyền.
- Tối ưu 100% trải nghiệm quan sát trực tiếp, phản hồi tức thời cho đội ngũ kỹ sư dữ liệu.

---

## 💎 Chuẩn Hóa 100% Pure TypeScript (Strictly No JavaScript)

Dự án áp dụng quy định bắt buộc về ngôn ngữ:
- **100% TypeScript**: Tất cả các tệp mã nguồn (`.ts`, `.tsx`), models, services, và tệp cấu hình (`vite.config.ts`, `tailwind.config.ts`) đều là TypeScript chuẩn.
- **Không có bất kỳ file `.js` / `.jsx` nào** trong mã nguồn dự án. Trình biên dịch khóa cứng với `"allowJs": false`.

---

## 🧩 Công Cụ MCP & Agent Skills

Hệ thống được chuẩn hóa kết hợp cùng các công cụ MCP:
- `shadcnspace-mcp`: Trích xuất blocks và layout component hiện đại.
- `puppeteer`: Tự động hóa kiểm thử UI và chụp ảnh dashboard.
- Xem chi tiết tại [`.agents/skills/mcp-ui-architect/SKILL.md`](../.agents/skills/mcp-ui-architect/SKILL.md).

---

## 🚀 Hướng Dẫn Khởi Chạy

### 1. Khởi chạy Backend API (FastAPI)
```bash
cd monitoring/backend
../../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Docs: `http://localhost:8000/docs`
- Master Dashboard API: `http://localhost:8000/api/dashboard`

### 2. Khởi chạy Frontend UI (React + Vite + Tailwind)
```bash
cd monitoring/frontend
npm run dev
```
- Mở trình duyệt tại: `http://localhost:5173`
