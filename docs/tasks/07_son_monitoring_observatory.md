# 🖥️ CẨM NANG NHIỆM VỤ: MONITORING OBSERVATORY REFACTORING
## THÀNH VIÊN PHỤ TRÁCH: SƠN

> **Hạn chót hoàn thành (Deadline):** **19:00 PM Chủ Nhật**  
> **Thư mục thực hiện chính (Folder Ownership):**  
> - `monitoring/` (Toàn bộ `monitoring/backend/` và `monitoring/frontend/`)  
> **Nhánh Git cá nhân:** `feature/monitoring-observatory`  
> **Nhánh hợp nhất (Merge Destination):** `sprint/pipeline-delivery`  
> **Tài liệu đặc tả đối chiếu:** [`docs/spec/09_monitoring_spec.md`](../spec/09_monitoring_spec.md), [`docs/spec/10_architecture.md`](../spec/10_architecture.md)

---

## 1. Mục Tiêu & Các Vấn Đề Cốt Lõi Cần Giải Quyết

Sơn chịu trách nhiệm về "Bộ mặt hiển thị trực quan" (Central Observatory) của toàn bộ hệ thống, bao gồm cả việc tái cấu trúc giao diện Frontend và nâng cấp dịch vụ truy vấn Backend FastAPI:

1. **Tái Cấu Trúc File Monolithic `CrawlingPage.tsx` (Vấn đề `VIZ-5`):**
   - *Hiện trạng:* File `monitoring/frontend/src/pages/CrawlingPage.tsx` hiện dài gần 900 dòng, chứa lẫn lộn logic gọi API, quản lý state và render UI.
   - *Nhiệm vụ:* Tách nhỏ thành các Atomic / Presenter Components chuyên biệt đặt trong `monitoring/frontend/src/components/crawling/`:
     * `CrawlTriggerCard.tsx` (Form kích hoạt cào theo nguồn, mẻ và engine)
     * `LedgerStatusTable.tsx` (Bảng thống kê trạng thái URL Ledger: PENDING, DONE, FAILED, CLOSED)
     * `LakehouseHealthCard.tsx` (Thẻ giám sát độ trễ Cloudflare R2 và phân bổ 4 tầng)
     * `RealtimeLogStream.tsx` (Cửa sổ terminal hiển thị Server-Sent Events log)
2. **Khắc Phục Số Liệu Cũ & Kết Nối PostgreSQL Analytics Mart (Vấn đề `VIZ-3`):**
   - *Hiện trạng:* Các trang phân tích hiện đang đọc các file báo cáo tĩnh từ lần chạy pipeline ngày 25/10 trong `reports/`.
   - *Nhiệm vụ:* Viết service kết nối FastAPI backend với **PostgreSQL Analytics Mart** (`vn_it_jobs` chạy trên Docker Compose cùng Airflow), truy vấn trực tiếp dữ liệu từ các bảng `curated_jobs`, `skill_rules`, `job_clusters` để hiển thị số liệu mới nhất.
3. **Hoàn Thiện Phân Hệ 2: Market Insights Dashboard Dành Cho Sinh Viên IT:**
   - Hoàn thiện giao diện hiển thị 4 bài toán phân tích chiến lược:
     * **Bản đồ nhiệt Lương (Salary Heatmap):** Ma trận 12 Job Family $\times$ 6 dải kinh nghiệm, hiển thị trung vị (Median) và khoảng tứ phân vị (IQR). Đơn vị hiển thị: Triệu VNĐ/tháng.
     * **Top Combo Kỹ Năng (FP-Growth Rules):** Bảng hiển thị các tổ hợp công nghệ đi liền nhau, lọc động theo ngưỡng Support, Confidence và Lift. Hỗ trợ chuyển đổi giữa luật toàn thị trường (Macro) và theo từng Job Family.
     * **Phân Cụm Việc Làm (K-Means 2D & 3D Scatter Plot):** Biểu đồ phân tán các bài đăng theo tọa độ PCA $(x, y)$ và chế độ **3D Scatter** $(x, y, z)$ tương tác (xoay, zoom góc nhìn), tô màu theo cụm nghề nghiệp.
     * **Bộ Lọc Đa Chiều:** Lọc theo Level, 34 tỉnh thành và Job Family.
4. **Triệt Để Tuân Thủ Nguyên Tắc "Real Numbers Only" (Zero-Mock Policy):**
   - Tuyệt đối không sinh số ngẫu nhiên `Math.random()`, không hardcode chỉ số giả. Nếu bước nào chưa có dữ liệu, backend trả về `null` kèm lý do cụ thể (`reason: "NO_DATA"`) và frontend hiển thị **Empty State** minh bạch trên UI.

---

## 2. Giải Đáp Chính Thức 5 Nhóm Câu Hỏi Của Sơn (Q&A Clarifications)

Dưới đây là các câu trả lời chính thức từ Trưởng nhóm (Team Lead) để giải tỏa toàn bộ thắc mắc của em:

### Câu hỏi 1: PostgreSQL Analytics Mart
- **Database `vn_it_jobs`:** Database này được khởi tạo trên service PostgreSQL có sẵn trong Docker Compose (`container_name: vn_it_jobs_postgres`, user `airflow`, pass `airflow`, port `5432`).
- **File DDL Schema:** Đã cung cấp sẵn file SQL chuẩn tại [`scripts/sql/init_mart_schema.sql`](../../scripts/sql/init_mart_schema.sql) tạo đủ 4 bảng: `curated_jobs`, `skill_rules`, `job_clusters`, `job_anomalies` với đầy đủ indexes B-Tree và GIN.
- **Môi trường kết nối:** Em kết nối PostgreSQL trên máy cá nhân bằng container Docker này. Biến môi trường đọc từ file `.env` mẫu (`POSTGRES_HOST=localhost`, `POSTGRES_PORT=5432`, `POSTGRES_DB=vn_it_jobs`, `POSTGRES_USER=airflow`, `POSTGRES_PASSWORD=airflow`).

### Câu hỏi 2: Trách Nhiệm Nạp Dữ Liệu
- **Phương án thống nhất:** Thống nhất theo **Phương án 1**: Sơn định nghĩa cấu trúc bảng (file DDL) và cung cấp script nạp mẫu [`scripts/load_mart_from_parquet.py`](../../scripts/load_mart_from_parquet.py). Phúc chịu trách nhiệm xuất các file Parquet đúng schema. Cloudflare R2 đóng vai trò là hub trung tâm để chia sẻ các file Parquet giữa các máy cá nhân.
- **Phần việc của Sơn:** Sơn viết truy vấn SQL trong FastAPI backend đọc dữ liệu từ Mart phục vụ các router `/insights`. Đồng thời viết sẵn logic xử lý khi bảng chưa có dữ liệu (trả về `status: "EMPTY"`, `reason: "NO_DATA"` để frontend hiển thị Empty State trung thực).
- **Khi nào có dữ liệu kiểm thử:** Em có thể dùng script `load_mart_from_parquet.py` để nạp thử file `curated_flat_golden_jobs.parquet` có sẵn ở máy hoặc test trước trạng thái Empty State. Khi Phúc đẩy artifacts lên R2, em chỉ cần kéo về và nạp vào Mart.

### Câu hỏi 3: Phạm Vi Nghiệm Thu Giao Diện
- **Checklist bắt buộc:** Nghiệm thu sprint này tập trung vào checklist trong cẩm nang này: Tái cấu trúc `CrawlingPage.tsx` thành 4 components con; hoàn thiện 4 biểu đồ Market Insights cốt lõi (Heatmap lương, Bảng luật kỹ năng, Scatter phân cụm 2D & 3D, Bộ lọc đa chiều).
- **Tính năng mở rộng (Network Graph, Khuyến nghị sinh viên):** Được coi là Stretch Goals (mục tiêu cộng điểm). Ưu tiên làm xong và ổn định 4 biểu đồ cốt lõi trước; nếu còn thời gian trước deadline Chủ Nhật mới triển khai Network Graph.
- **Phạm vi VIZ-3:** VIZ-3 chỉ yêu cầu chuyển các biểu đồ của **Market Insights** (`/insights`) từ file tĩnh sang đọc trực tiếp từ PostgreSQL Mart. Các trang báo cáo vận hành hoặc phân tích khác vẫn giữ nguyên theo thiết kế hiện tại.

### Câu hỏi 4: Hợp Đồng Dữ Liệu
- **12 Job Family chuẩn:** Thống nhất dùng danh mục tiếng Việt chuẩn theo SPEC-06: *Backend, Frontend, Fullstack, Mobile, Data/AI, DevOps/Cloud, Kiểm thử (QA/QC), Bảo mật (Security), Hệ thống/Mạng, Phân tích nghiệp vụ (BA), Quản lý SP/DA (PM/PO), Thiết kế UI/UX* (và fallback: *Khác*).
- **Đơn vị lương:** Trong database lưu `salary_min_vnd`, `salary_max_vnd`, `salary_avg_vnd` (VNĐ). Khi hiển thị trên Heatmap và biểu đồ, API chia cho $1.000.000$ để hiển thị đơn vị thân thiện là **Triệu VNĐ/tháng**.
- **Dữ liệu phân cụm từ Phúc:** File `job_clusters.parquet` từ Phúc sẽ có đầy đủ các cột: `job_id`, `job_title`, `job_family`, `cluster_id`, `cluster_name`, `pca_x`, `pca_y`, `pca_z`, `is_outlier`, `glosh_outlier_score`.
- **Bộ lọc:** Bộ lọc tỉnh, level, job_family áp dụng chung cho Heatmap lương và Scatter phân cụm. Bảng luật kỹ năng hỗ trợ lọc theo tiền đề (Antecedent) hoặc theo `job_family_scope`.

### Câu hỏi 5: Nhánh Git & Quyền Can Thiệp
- **Nhánh Git:** Bắt đầu từ nhánh `sprint/pipeline-delivery`, checkout sang `feature/monitoring-observatory` để thực hiện, sau đó tạo PR merge lại vào `sprint/pipeline-delivery`.
- **Quyền can thiệp file:** Ngoài thư mục `monitoring/`, em được phép chỉnh sửa các file test liên quan đến monitoring (`tests/integration/test_monitor*.py`), cấu hình Docker Compose nếu cần chỉnh sửa cổng/volume mart, và cập nhật tài liệu báo cáo của cá nhân. Không được can thiệp vào mã nguồn crawler (`collection/`) hay tiền xử lý của người khác.

---

## 3. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Sơn làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Kỹ sư Full-Stack & Giám Sát Hệ Thống (Monitoring & Observatory Engineer) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là tái cấu trúc hệ thống giám sát Central Observatory: (1) Tách nhỏ file monolithic `CrawlingPage.tsx` thành các atomic components; (2) Kết nối FastAPI backend với PostgreSQL Data Mart (database `vn_it_jobs`, xem DDL tại scripts/sql/init_mart_schema.sql) để truy vấn dữ liệu thật thay cho báo cáo cũ (VIZ-3); (3) Hoàn thiện các trang phân tích thị trường Market Insights (Heatmap lương Triệu VNĐ/tháng, Combo kỹ năng FP-Growth, Phân cụm việc làm K-Means hỗ trợ cả 2D và 3D Scatter). Tham khảo đặc tả kỹ thuật tại docs/spec/09_monitoring_spec.md và cẩm nang docs/tasks/07_son_monitoring_observatory.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Chỉ can thiệp vào mã nguồn trong thư mục: `monitoring/` và kiểm tra cấu hình kết nối DB.
- 100% Strict TypeScript: Cấm sử dụng kiểu `any` tùy tiện, cấm file `.js`/`.jsx`. Kiểm tra build bằng `npm run build`.
- Nguyên tắc Real Numbers Only: Tuyệt đối không dùng Math.random() hay dữ liệu giả; khi Mart chưa có dữ liệu bắt buộc trả null kèm reason: "NO_DATA" và hiển thị Empty State trung thực.
- Thiết kế Zero-Auth: Không tạo màn hình đăng nhập / đăng xuất; mở trực tiếp vào dashboard.
- Đảm bảo hiển thị chuẩn trên màn hình desktop (1440px) và responsive tốt trên mobile (390px).

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào: Cơ sở dữ liệu PostgreSQL `vn_it_jobs` (các bảng curated_jobs, skill_rules, job_clusters, job_anomalies) và trạng thái URL Ledger/R2.
- Đầu ra: FastAPI endpoints tại cổng :8000; Vite SPA Dashboard tại cổng :5173 hoạt động mượt mà, build không lỗi.

### 4. YÊU CẦU THỰC HIỆN:
Hãy phân tích file CrawlingPage.tsx và các router backend hiện tại, lập Plan từng bước tách component, sau đó refactor code và chạy `npm run build` để kiểm chứng.
```

---

## 4. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [x] **Bước 1 (Component Refactoring):** Tách `CrawlingPage.tsx` thành 4 component con trong `components/crawling/`; đảm bảo file `CrawlingPage.tsx` mới có dung lượng $< 200$ dòng.
- [x] **Bước 2 (Frontend Type-Check):** Chạy lệnh kiểm tra TypeScript và build frontend:
  ```bash
  cd monitoring/frontend && npm run build
  ```
  Xác nhận: Lệnh build thành công $100\%$ không có lỗi type error.
- [x] **Bước 3 (Backend PostgreSQL Connection):** Kiểm tra các endpoint `/api/v1/insights/...` trong FastAPI, đảm bảo truy vấn thành công dữ liệu từ PostgreSQL container (`vn_it_jobs`) mà không bị lỗi connection timeout; xử lý đúng Empty State khi bảng rỗng.
- [ ] **Bước 4 (Khởi động kiểm thử toàn trình Dashboard):**
  ```bash
  ./start_monitoring.sh --check
  ```
  Mở trình duyệt kiểm tra: Giao diện trực quan, bảng điều khiển Vận hành và các biểu đồ Market Insights hiển thị số liệu thật (hoặc Empty State nếu chưa nạp), hỗ trợ chuyển đổi Scatter 2D/3D mượt mà, không có lỗi console.
- [ ] **Bước 5 (Linting Backend):** Chạy `ruff check monitoring/backend/`.

---

## 5. Mẫu Báo Cáo Nghiệm Thu Bàn Giao (Delivery Report Template)

*Sau khi hoàn thành, Sơn điền thông tin vào mẫu dưới đây và dán vào mô tả Pull Request khi merge vào `sprint/pipeline-delivery`:*

```markdown
### BÁO CÁO NGHIỆM THU: MONITORING OBSERVATORY REFACTORING
- **Người thực hiện:** Sơn
- **Nhánh làm việc:** `feature/monitoring-observatory`
- **Thư mục can thiệp:** `monitoring/backend/`, `monitoring/frontend/`

#### 1. Vấn Đề Gặp Phải (Problems Encountered):
- [Mô tả khó khăn khi tái cấu trúc file dài hoặc mapping kiểu dữ liệu TypeScript với FastAPI]

#### 2. Nguyên Nhân Gốc Rễ (Root Cause):
- [Giải thích vì sao code cũ bị monolithic và phụ thuộc vào report tĩnh]

#### 3. Giải Pháp Kỹ Thuật Đã Triển Khai (Solution Implemented):
- [Liệt kê các component đã tách và cấu trúc service kết nối PostgreSQL]

#### 4. Bằng Chứng Tự Kiểm Chứng (Verification Proof):
- Kết quả lệnh `npm run build`: [Thành công / 0 lỗi]
- Danh sách các component mới tạo:
  * `components/crawling/CrawlTriggerCard.tsx`
  * `components/crawling/LedgerStatusTable.tsx`
  * `components/crawling/LakehouseHealthCard.tsx`
  * `components/crawling/RealtimeLogStream.tsx`
- Ảnh chụp màn hình hoặc xác nhận hiển thị các biểu đồ Market Insights từ dữ liệu thật.

#### 5. Vấn Đề Còn Tồn Đọng (Remaining Issues / Blockers):
- [Ghi rõ nếu còn component nào cần làm đẹp thêm CSS, hoặc ghi "Không còn"]
```


## 6. Báo cáo triển khai thực tế — 06/11/2026

- **Nhánh:** `feature/monitoring-observatory` đã xác nhận trước khi sửa.
- **Frontend:** CrawlingPage chỉ điều phối các presenter; có đủ CrawlTriggerCard, LedgerStatusTable, LakehouseHealthCard, RealtimeLogStream cùng hook và các component hỗ trợ lịch/nguồn/KPI. Trang `/insights` có heatmap, luật FP-Growth Macro/Micro, bộ lọc và scatter PCA 2D/3D kéo xoay/zoom. Z thiếu không được thay bằng tọa độ giả.
- **Backend:** 4 endpoint `/api/v1/insights/{salary-heatmap,skill-combos,clusters,filters/options}`; SQL tham số hóa, kết nối read-only, timeout kết nối 3 giây/truy vấn 5 giây, đóng kết nối sau request. Bảng rỗng trả `EMPTY`, `NO_DATA`, `data: null`; lỗi DB trả 503 `MART_UNAVAILABLE`, không lộ DSN/secret.
- **Cổng Mart local:** 5432 bị PostgreSQL cài sẵn sử dụng, 5433 cũng có dịch vụ. Docker dùng `POSTGRES_PUBLISHED_PORT=15432`, backend `POSTGRES_PORT=15432`; cấu hình local lưu trong `.env`, không commit. Compose vẫn mặc định 5432 trên máy khác và cho phép override. Volume được giữ nguyên; không bật Airflow scheduler.
- **Đã kiểm chứng:** `npm run build` thành công. 6 test tại `tests/integration/test_monitor_insights.py` qua bằng unittest. 4 endpoint đọc Mart thật trả 200/EMPTY/NO_DATA. Playwright Edge headless kiểm tra Empty State tại 390px và 1440px: không tràn ngang, không có pageerror. Sau đó kiểm tra lại toàn trình React → FastAPI → PostgreSQL thật tại cả hai viewport, đủ 4 khối Empty State.
- **Lint:** Hai module backend mới qua Ruff; toàn backend còn 355 findings ở code hiện có, không format diện rộng.
- **Giới hạn:** Mart hiện rỗng, chưa kiểm chứng heatmap/rules/scatter bằng artifacts thật từ Phúc. Máy dùng Python 3.11 thay vì chuẩn 3.12 của repo. FastAPI app.main khởi động thành công tại :8000. Bộ hồi quy ba file test_monitor_endpoints.py, test_monitoring_api.py, test_monitor_insights.py: **32 passed, 1 skipped**, 14.91 giây. Chưa chạy start_monitoring.sh --check trên môi trường Linux/Python 3.12; chưa kiểm chứng scatter có dữ liệu thật.
- **Phạm vi:** Không sửa crawler/preprocessing, không cào thật, không sync R2. Các trang báo cáo cũ giữ nguyên theo Q&A leader.

- **Xem giao diện đang chạy:** http://127.0.0.1:5174/insights (Vite phiên kiểm chứng), Swagger http://127.0.0.1:8000/docs. Build có cảnh báo bundle >500kB, không có lỗi biên dịch.
