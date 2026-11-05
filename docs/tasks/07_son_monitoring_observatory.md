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
     * **Bản đồ nhiệt Lương (Salary Heatmap):** Ma trận 12 Job Family $\times$ 5 dải kinh nghiệm, hiển thị trung vị (Median) và khoảng tứ phân vị (IQR).
     * **Top Combo Kỹ Năng (FP-Growth Rules):** Bảng hiển thị các tổ hợp công nghệ đi liền nhau, lọc động theo ngưỡng Support, Confidence và Lift.
     * **Phân Cụm Việc Làm (K-Means 2D Scatter Plot):** Biểu đồ phân tán các bài đăng theo tọa độ PCA $(x, y)$, tô màu theo cụm nghề nghiệp.
     * **Bộ Lọc Đa Chiều:** Lọc theo Level, 34 tỉnh thành và Job Family.
4. **Triệt Để Tuân Thủ Nguyên Tắc "Real Numbers Only" (Zero-Mock Policy):**
   - Tuyệt đối không sinh số ngẫu nhiên `Math.random()`, không hardcode chỉ số giả. Nếu bước nào chưa có dữ liệu, trả về `null` kèm lý do và hiển thị **Empty State** minh bạch trên UI.

---

## 2. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Sơn làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Kỹ sư Full-Stack & Giám Sát Hệ Thống (Monitoring & Observatory Engineer) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là tái cấu trúc hệ thống giám sát Central Observatory: (1) Tách nhỏ file monolithic `CrawlingPage.tsx` thành các atomic components; (2) Kết nối FastAPI backend với PostgreSQL Data Mart để truy vấn dữ liệu thật thay cho báo cáo cũ (VIZ-3); (3) Hoàn thiện các trang phân tích thị trường Market Insights (Heatmap lương, Combo kỹ năng, Phân cụm việc làm). Tham khảo đặc tả kỹ thuật tại docs/spec/09_monitoring_spec.md và docs/spec/10_architecture.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Chỉ được can thiệp vào mã nguồn trong thư mục: `monitoring/` (cả `monitoring/backend/` và `monitoring/frontend/`).
- 100% Strict TypeScript: Cấm sử dụng kiểu `any` tùy tiện, cấm file `.js`/`.jsx`. Kiểm tra build bằng `npm run build`.
- Nguyên tắc Real Numbers Only: Tuyệt đối không dùng Math.random() hay dữ liệu giả; khi không có dữ liệu bắt buộc hiển thị Empty State trung thực.
- Thiết kế Zero-Auth: Không tạo màn hình đăng nhập / đăng xuất; mở trực tiếp vào dashboard.
- Đảm bảo hiển thị chuẩn trên màn hình desktop và responsive tốt trên tablet/mobile.

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào: Cơ sở dữ liệu PostgreSQL `vn_it_jobs` (các bảng curated_jobs, skill_rules, job_clusters) và trạng thái URL Ledger/R2.
- Đầu ra: FastAPI endpoints tại cổng :8000; Vite SPA Dashboard tại cổng :5173 hoạt động mượt mà, build không lỗi.

### 4. YÊU CẦU THỰC HIỆN:
Hãy phân tích file CrawlingPage.tsx và các router backend hiện tại, lập Plan từng bước tách component, sau đó refactor code và chạy `npm run build` để kiểm chứng.
```

---

## 3. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [ ] **Bước 1 (Component Refactoring):** Tách `CrawlingPage.tsx` thành 4 component con trong `components/crawling/`; đảm bảo file `CrawlingPage.tsx` mới có dung lượng $< 200$ dòng.
- [ ] **Bước 2 (Frontend Type-Check):** Chạy lệnh kiểm tra TypeScript và build frontend:
  ```bash
  cd monitoring/frontend && npm run build
  ```
  Xác nhận: Lệnh build thành công $100\%$ không có lỗi type error.
- [ ] **Bước 3 (Backend PostgreSQL Connection):** Kiểm tra các endpoint `/api/v1/insights/...` trong FastAPI, đảm bảo truy vấn thành công dữ liệu từ PostgreSQL container mà không bị lỗi connection timeout.
- [ ] **Bước 4 (Khởi động kiểm thử toàn trình Dashboard):**
  ```bash
  ./start_monitoring.sh --check
  ```
  Mở trình duyệt kiểm tra: Giao diện trực quan, bảng điều khiển Vận hành và các biểu đồ Market Insights hiển thị số liệu thật, không có lỗi console.
- [ ] **Bước 5 (Linting Backend):** Chạy `ruff check monitoring/backend/`.

---

## 4. Mẫu Báo Cáo Nghiệm Thu Bàn Giao (Delivery Report Template)

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
