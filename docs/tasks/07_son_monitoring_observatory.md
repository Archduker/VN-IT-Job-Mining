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


## 7. Bổ sung EDA đọc trực tiếp Cloudflare R2 — 09/11/2026

- **Yêu cầu:** Xem EDA mà không phải đồng bộ/download dữ liệu vào thư mục local trước.
- **Triển khai:** Trang `/eda` mặc định chọn Cloudflare R2 và có tùy chọn Local. Các API `/eda/compare` và `/eda/{source}/{inventory,summary,charts}` nhận `origin=r2|local`; mặc định API vẫn là local để tương thích các client cũ.
- **Đọc dữ liệu:** Dùng client R2 chung của dự án; raw lấy tối đa 200 bản ghi đầu tiên theo thứ tự key (không phải mẫu ngẫu nhiên), Parquet ưu tiên `staging/<source>/preprocessing/04_normalization.parquet`, hỗ trợ đường dẫn cũ `<source>_flat_clean.parquet` trên R2. Không đọc báo cáo local trong chế độ R2.
- **Bộ nhớ:** Object được đọc vào RAM, cache 60 giây theo nguồn; đóng StreamingBody sau mỗi lần đọc. Giới hạn mỗi object 128 MiB; object lớn hơn trả 413. Phương án hiện tại truyền toàn bộ Parquet vào RAM, chưa dùng DuckDB range queries; không tạo file dữ liệu hay cache trên đĩa.
- **Trung thực dữ liệu:** Độ đầy đủ tính trên mẫu raw; số dòng/lương/skills/địa điểm tính từ staging R2. Chỉ số không đo được trả null. Thiếu object trả Empty State; lỗi cấu hình, quyền truy cập, kết nối hoặc dữ liệu không hợp lệ trả HTTP 503 với mã nguyên nhân an toàn, không lộ credentials. Không fallback local khi đã chọn R2.
- **Kiểm chứng R2 thật:** Cấu hình hợp lệ. TopCV: 1.561 dòng staging, 200 raw mẫu, 22 trường, độ đầy đủ mẫu 91,43%, tỷ lệ có lương số 58,1%. Biểu đồ lương trả 10 bins. Một lượt cold-read mất 31,16 giây; không ghi dữ liệu về local.
- **Kiểm thử:** Ba endpoint summary/inventory/charts qua HTTP nội bộ với origin=r2 đều trả 200 trên dữ liệu TopCV thật. 16 test qua gồm hợp đồng R2 và hồi quy EDA local; frontend build thành công. Hai cảnh báo deprecation Python có sẵn, build có cảnh báo kích thước bundle.
- **Còn lại:** Chưa đối soát số liệu EDA đủ 8 nguồn với notebook. Cross-source R2 đọc tối đa 4 nguồn đồng thời, lần đầu có thể chậm; dữ liệu thiếu trên R2 cần thành viên pipeline cung cấp. Chưa chuyển các trang Raw/Preprocessing/Market Insights sang cơ chế đọc EDA này.
- **Cách dùng:** Khởi động lại backend sau khi cập nhật `.env` và code, mở `/eda`, chọn “Cloudflare R2 trực tiếp”, chọn nguồn. Credentials chỉ ở `.env` backend; không commit hoặc gửi lên frontend.

### Sửa biểu đồ tỉnh/thành EDA — 09/11/2026

- **Lỗi:** R2 có địa điểm nhưng biểu đồ hiện “Chưa có số liệu địa điểm”: backend chỉ đọc `primary_city`, trong khi Parquet Normalization dùng `tinh_chinh`.
- **Đã sửa:** Hàm tính biểu đồ dùng chung R2/Local ưu tiên `tinh_chinh`, fallback `primary_city` theo từng dòng còn thiếu; bỏ null/chuỗi trắng khi đếm, giữ Top 8 tỉnh/thành và Empty State nếu thực sự không có dữ liệu.
- **Kiểm chứng dữ liệu thật:** Đọc Parquet TopCV trên R2 vào RAM: 1.561 dòng, 1.548 dòng có `tinh_chinh`; kết quả biểu đồ khớp trực tiếp `value_counts().head(8)` trên Parquet. Hà Nội 1.033, TP. Hồ Chí Minh 351, Đà Nẵng 31. Không sửa hoặc ghi dữ liệu trên R2.
- **Giới hạn:** Kiểm chứng service bằng dữ liệu TopCV, chưa đối soát đủ 8 nguồn hoặc kiểm lại giao diện trình duyệt. Khởi động lại backend nếu không bật auto-reload, rồi tải lại `/eda`.
- **Kiểm thử phiên sửa:** Bộ `test_monitor_eda_r2.py` bị treo khi đến test HTTP dùng TestClient sau hai test đầu, đã dừng; không tính lần chạy này là hoàn tất. Đối chiếu service với Parquet R2 thật ở trên đã thành công.

## 8. Điều chỉnh phạm vi theo leader — 09/11/2026

- **Phạm vi giao diện mới:** Chỉ giữ Collection (`/`), EDA (`/eda`), Pre-processing (`/preprocessing`), Processing (`/processing`). Các route khác chuyển về Collection; sidebar chỉ có 4 mục. Phạm vi này thay thế yêu cầu hiển thị các trang khác trong báo cáo trước. Mã nguồn/API cũ được giữ để tránh ảnh hưởng các client khác.
- **EDA:** Dùng trực tiếp Cloudflare R2, bỏ lựa chọn Local trên trang. Không lọc theo ngày, không thêm biểu đồ thời gian. Collection, Pre-processing và Processing vẫn dùng các API nghiệp vụ hiện có; thay đổi này không chuyển các báo cáo pipeline local của Pre-processing/Processing lên R2.
- **Biểu đồ:** Histogram lương, bar chart kỹ năng/tỉnh thành, scatter kinh nghiệm tối thiểu–lương, line chart phân phối lương tích lũy, box plot theo tỉnh/thành kèm bảng IQR, heatmap tỉnh/thành–cấp bậc và ma trận tương quan Pearson cho lương/kinh nghiệm/số lượng tuyển.
- **Quy tắc thống kê:** Lương = trung bình các cận dương, đổi sang triệu VND; không bù số thiếu. Scatter tối đa 1.000 dòng đủ hai biến đầu tiên, công khai số hiển thị/tổng số đủ dữ liệu. Box plot cần ít nhất 4 tin có lương; râu nằm trong Q1 − 1,5×IQR và Q3 + 1,5×IQR, đếm ngoại lai nhưng không xóa. Pearson theo cặp đủ dữ liệu, cần ít nhất 3 dòng và biến không đổi trả null. Heatmap đếm trên Top 8 tỉnh/thành × Top 6 cấp bậc có giá trị, ô 0 là số đếm thực.
- **Kiểm chứng:** Build frontend thành công (còn cảnh báo bundle >500 kB); 3 unit test thống kê qua. Parquet TopCV R2 thật có 1.561 dòng: 907 điểm scatter đủ dữ liệu, 8 box plot, 48 ô heatmap, 9 hệ số tương quan hợp lệ, 106 điểm đường tích lũy kết thúc ở 100%. Response serialize JSON không có NaN/Infinity. Không ghi lên R2 hoặc tạo file dữ liệu local.
- **Giới hạn:** Chưa đối soát đủ 8 nguồn; nhãn kỹ năng vẫn giữ các biến thể gốc trong `skills_list`. Phân tích trên Parquet staging là mô tả số tin hiện có, chưa tự loại trùng xuyên nguồn hay suy ra quan hệ nhân quả. Dữ liệu/cột thiếu hiển thị Empty State hoặc dấu —.
- **Kiểm tra bổ sung:** Tổng cộng 6 test qua (3 test thống kê và 3 test R2 không dùng HTTP TestClient); 2 test HTTP không chạy lại do vấn đề treo đã ghi ở mục 7. Hai module mới gồm service thống kê và test qua Ruff. Edge headless kiểm bản production build tại 390px/1440px bằng response summary/inventory/charts tính từ dữ liệu TopCV thật trên R2, chặn tuyến API trong trình duyệt để cấp các response đó: đúng 4 mục điều hướng, đủ 5 khối Recharts cùng SVG box plot và hai ma trận, không tràn ngang, không có pageerror. Đây là kiểm tra render với dữ liệu thật, chưa phải kiểm thử toàn trình qua FastAPI đang chạy.


## 9. Collection trực tiếp từ R2 — 10/11/2026

- **Yêu cầu:** Leader không cung cấp tài khoản Airflow; trực quan sản phẩm thu thập từ R2 mà không cần PostgreSQL/Airflow.
- **Backend:** `collection_monitor_service.py` chuyển sang `collection_r2_service.py`; endpoint `/api/v1/monitor/collection` trả contract kiểm kê R2 mới (frontend đã cập nhật). List raw JSON có phân trang và đọc `url_ledger/<source>/catalog_master.json` vào RAM, tối đa 4 nguồn song song, cache 60 giây. Không query Airflow hoặc dữ liệu local. Lỗi quyền/kết nối trả 503 có reason an toàn; thiếu Ledger trả null/NO_LEDGER.
- **Frontend:** KPI số object raw, số object trong khoảng 7/14 ngày theo ngày phân vùng của key, dung lượng MiB, độ phủ Ledger. Biểu đồ raw theo ngày/nguồn, bảng trạng thái URL và lần upload gần nhất theo nguồn. Loại bỏ lịch DAG, tỷ lệ chạy thành công và tiến độ unique khỏi Collection vì không có chứng cứ tương ứng.
- **Ý nghĩa số liệu:** Object raw không đồng nghĩa tin unique vì có nhiều version/batch. Ngày theo key không đồng nghĩa thời gian chạy DAG; LastModified là lần upload/ghi gần nhất. Trạng thái Ledger là snapshot hiện tại; không dựng lại lịch sử trạng thái từ snapshot. Object thiếu ngày vẫn tính tổng nhưng không đưa vào biểu đồ. Chưa triển khai đối soát từng URL Ledger với từng raw key.
- **Kiểm chứng:** Đọc R2 thật đủ 8 nguồn: 12.779 object JSON, 8 Ledger, 3 object thiếu ngày hợp lệ; 2.512 object thuộc cửa sổ 14 ngày tại lần kiểm tra. Tổng raw theo nguồn: TopCV 2.755, TopDev 3.892, ITviec 914, CareerViet 663, Vieclam24h 664, VietnamWorks 1.952, Glints 334, JobsGO 1.605. Số liệu thay đổi khi nhóm upload thêm dữ liệu.
- **Kiểm tra code:** Frontend build thành công (cảnh báo bundle >500 kB vẫn còn), 2 unit test qua về đếm version/ngày không hợp lệ và thiếu Ledger; Ruff các module mới/sửa qua sau sắp xếp import. Không ghi lên R2, không tạo file dữ liệu local, không bật scheduler.
- **Giao diện:** Edge headless kiểm production build ở 390px/1440px, cấp response kiểm kê R2 thật qua tuyến API của trình duyệt: đủ 8 dòng nguồn, không tràn ngang, không có pageerror. Đây là kiểm render dữ liệu thật; chưa kiểm HTTP toàn trình qua FastAPI đang chạy.


### Mở rộng ma trận tương quan EDA — 10/11/2026

- Bổ sung 8 biến định lượng: lương min/max/trung bình (triệu VND), kinh nghiệm min/max (năm), số lượng tuyển, số kỹ năng nhận diện, số từ mô tả JD.
- Biến kỹ năng đếm phần tử từ `skills_std` (fallback `skills_clean`, `skills_list`); ndarray/list được xử lý như danh sách, không đếm ký tự của biểu diễn mảng. Số từ JD tính từ `description_clean` (fallback raw description). Không điền missing. Mỗi ô Pearson hiển thị số cặp đủ dữ liệu.
- Kiểm chứng Parquet TopCV thật: 8 biến, 64 ô, cả 64 cặp có Pearson hợp lệ; số cặp đủ dữ liệu thấp nhất trong các ô là 740. 3 unit test qua. Có điều chỉnh sau khi phát hiện `skills_std` trên R2 là ndarray.


## 10. EDA kiểm kê toàn bộ raw R2 trong nền — 10/11/2026

- Thay giới hạn 200 raw trong chế độ R2 bằng quét toàn bộ object JSON dưới `raw/<source>/`, đọc có phân trang, tính từng bản ghi trong file batch. Phạm vi ALL_RAW_VERSIONS bao gồm các phiên bản; không coi đó là tin unique hoặc tự chọn latest.
- `eda_raw_scan_service.py` giữ tối đa 2 lượt quét nguồn đồng thời, trạng thái QUEUED/RUNNING/COMPLETE/ERROR. Theo dõi object và bản ghi đã đọc, không khẳng định phần trăm khi chưa liệt kê xong. Chỉ công bố inventory/độ đầy đủ khi quét hoàn tất; lỗi không biến thành số liệu đầy đủ giả.
- Không giữ danh sách toàn bộ raw trong RAM: xử lý từng object rồi giải phóng; giữ số đếm, kiểu, giá trị mẫu 60 ký tự và SHA-256 giá trị phân biệt theo trường. RAM vẫn tăng theo số giá trị phân biệt; giới hạn mỗi object 128 MiB giữ nguyên. Không ghi raw hoặc cache xuống đĩa.
- Tách đọc staging khỏi quét raw, biểu đồ vẫn đọc toàn bộ Parquet trong lúc quét. Kết quả raw hoàn tất giữ trong RAM của từng process đến khi POST `/api/v1/eda/<source>/scan` để quét lại hoặc backend restart. Giao diện có tiến độ, nút quét lại và polling 5 giây; so sánh nguồn cập nhật 10 giây. Parquet vẫn cache 60 giây. Local API cũ vẫn dùng mẫu 200 để tương thích, UI EDA đang dùng R2.
- Không phải snapshot transaction của bucket: nếu đang upload trong lúc quét, nên quét lại sau khi upload hoàn tất. Kết quả có thời điểm hoàn thành để người xem biết độ mới.
- Kiểm chứng offline: test quét hơn 200 bản ghi (206), phân trang, trường chỉ xuất hiện cuối lượt, thiếu trường ở các dòng trước, số giá trị khác nhau; test lỗi không công bố inventory dở dang. 2 test qua; frontend build thành công (cảnh báo bundle >500 kB có sẵn).
- **Kiểm chứng R2 thật:** Lượt quét Glints hoàn tất COMPLETE, đọc đủ 334 object/334 bản ghi, tìm thấy 16 trường; đã quan sát tiến độ vượt 200. Chưa chạy full-scan cả 8 nguồn trong phiên này.


## 11. Duplicate, histogram không cắt lương, missing bar chart — 10/11/2026

- **Duplicate raw:** Lượt quét đầy đủ tính SHA-256 của payload JSON canonical (sắp xếp key, giữ thứ tự mảng), bỏ envelope metadata. Công bố tổng bản ghi, số payload khác nhau, số bản ghi dư, số nhóm trùng và tỷ lệ dư/tổng; không khẳng định trùng ngữ nghĩa hay trùng liên nguồn. Thống kê riêng object dư theo ID filename bỏ `_vN` để phân biệt nhiều phiên bản với nội dung giống hệt.
- **Histogram staging:** Đọc toàn bộ dòng trong Parquet đang chọn; mỗi dòng lấy trung bình các cận min/max dạng số hữu hạn. Không chặn lương >150/500 triệu, không loại outlier hoặc lấy mẫu; bao gồm 0/âm để EDA và ghi rõ trên giao diện. Tự chia 10 khoảng phủ min–max, gồm cả giá trị max ở bin cuối. NaN/Infinity không được coi là lương số hữu hạn. Không cộng hai cận thành hai tin. Các biểu đồ phân tích khác vẫn giữ quy tắc cận dương của chúng.
- **Missing bar chart:** Hiển thị tất cả trường raw của nguồn đang chọn, tỷ lệ thiếu trên toàn bộ bản ghi lượt quét COMPLETE, tooltip có số dòng thiếu. Không Top N; vùng biểu đồ cuộn theo chiều dọc khi nhiều trường. Quy tắc thiếu: không có key/null/chuỗi rỗng; chưa coi mảng rỗng hoặc marker N/A là null. Chỉnh chú thích 200 bản ghi cũ còn sót.
- **Kiểm chứng:** 7 unit test qua, gồm đối soát duplicate trên batch >200, trường xuất hiện muộn, quét lỗi, histogram gồm 0/âm và lương hàng tỷ, thiếu cột lương; frontend build thành công (cảnh báo bundle >500 kB còn). Chưa chạy lại full scan 8 nguồn hoặc kiểm trình duyệt ở lần bổ sung này. Cần quét lại để cache raw có kết quả duplicate mới.


## 12. Sửa duplicate TopCV báo chờ sau khi quét xong — 10/11/2026

- Tái hiện trực tiếp API backend đang chạy: raw_scan COMPLETE, 2.755 bản ghi nhưng không có key duplicates. Tiến trình Uvicorn chưa nạp code mới bổ sung duplicate; frontend mới hiển thị kiểm kê từ code cũ và một Empty State chung gây nhầm lẫn.
- Đã dừng đúng tiến trình Uvicorn Monitoring cũ và khởi động bản mới ở 127.0.0.1:8000. Không đụng PostgreSQL hoặc bật scheduler. Bản mới đang quét lại TopCV để giữ cache phục vụ người dùng.
- Bổ sung tự phát hiện cache COMPLETE thiếu duplicates để quét lại. Giao diện phân biệt RUNNING/ERROR/COMPLETE thiếu dữ liệu, hướng dẫn restart backend thay vì báo chờ vô hạn.
- Kiểm chứng: 3 test raw scan qua (có test cache cũ thiếu duplicate), Ruff sạch, frontend build thành công. Glints thật có 334 raw, 333 payload khác nhau, 1 bản ghi dư (0,30%), 2 object dư theo ID filename. Lỗi được ghi ở issue_log L-32.
- **Đối chiếu TopCV qua API đang chạy:** COMPLETE 2.755/2.755 object/bản ghi; 2.746 payload khác nhau, 9 bản ghi trùng dư trong 9 nhóm (0,33%); 2.680 ID filename và 75 object dư theo ID. Kết quả duplicate hiện đã có trong raw_scan của GET summary.
- **Kiểm tra toàn trình:** Edge headless mở trang EDA đang chạy, dùng API backend thật và cache TopCV vừa quét: đã thấy Bản ghi trùng dư, thông báo chờ cũ không còn, không có pageerror.
