# Quy Chuẩn Hoạt Động & Phát Triển Hệ Thống Monitoring (Monitoring System Rules)

Tài liệu này là quy chuẩn bắt buộc (Non-negotiable Rules) cho bất kỳ AI Agent hoặc kỹ sư nào tham gia phát triển, mở rộng hoặc bảo trì hệ thống **VN-IT-Job-Mining Central Observatory** (`monitoring/`).

---

## 1. Nguyên Tắc Sứ Mệnh: Bộ Máy Miêu Tả Hình Ảnh Thực Tế (Visual Truth Engine)
- Hệ thống Monitoring **không được tạo ra chỉ để hiển thị các con số tĩnh**.
- Mọi trang màn hình phải phản ánh trung thực, liên tục dòng chảy biến đổi của dữ liệu qua 3 giai đoạn chuẩn:
  $$\text{Collection (Thô As-Is)} \longrightarrow \text{Pre-processing (Tiền Xử Lý)} \longrightarrow \text{Processing (Tích Hợp \& Khử Trùng)} \Longrightarrow \text{Golden Master Dataset}$$
- Mục tiêu tối thượng: Giúp kỹ sư theo dõi độ biến thiên và kiểm soát chất lượng qua từng bước để tinh chế ra **Bộ Dữ Liệu Hoàn Chỉnh Nhất**.

---

## 2. Nguyên Tắc Zero-Auth (Tuyệt Đối Không Có Nút Đăng Nhập)
- Phạm vi của hệ thống là **Engineering Observatory & Data Pipeline Cockpit** nội bộ.
- **Nghiêm cấm** tạo các trang đăng nhập (Login/Sign-in), đăng xuất (Logout), modal xác thực tài khoản, hoặc nút User Profile rườm rà.
- Toàn bộ giao diện người dùng phải mở trực tiếp vào bảng điều khiển trung tâm mà không có bất kỳ rào cản xác thực nào.

---

## 3. Nguyên Tắc Phân Tách Tuyệt Đối Giữa Crawling và EDA (Decoupled Crawl vs EDA)
- **Crawling Operations (`/crawling`)** thuộc về tầng **Vận Hành (Operations)**:
  - Chỉ chứa các tính năng: Bắt đầu/dừng batch cào, chọn Phase 1 (Discovery) / Phase 2 (Detail), chọn engine `curl_cffi` (Cloudflare bypass) hoặc `playwright`, stream log console thời gian thực (SSE), duyệt danh mục URL Ledger (`catalog_master.json`), kiểm tra mã băm SHA-256 CDC.
  - Tuyệt đối **không nhồi nhét** các biểu đồ phân tích thống kê phân phối vào trang này.
- **EDA Intelligence Hub (`/eda`)** thuộc về tầng **Khoa Học Dữ Liệu (Data Science)**:
  - Chỉ chứa các tính năng: Bảng kiểm kê trường dữ liệu (Field Inventory), tỷ lệ khuyết thiếu (Null Rate %), phát hiện ngoại lai (Outliers IQR/Z-score), và 5 họ biểu đồ 2D chuẩn mực.
  - Hỗ trợ chuyển đổi giữa xem **Đơn nguồn** (từng sàn) và **So sánh xuyên sàn Cross-Platform** (8 sàn trên cùng biểu đồ).
  - Tuyệt đối **không đặt nút bấm kích hoạt cào** trong trang này.

---

## 4. Nguyên Tắc Giám Sát Apache Airflow Minh Bạch
- Mọi biến động của pipeline tự động phải được phản ánh trực quan qua module **Airflow Pipeline (`/airflow`)**.
- Bắt buộc theo dõi:
  1. Trạng thái của **Scheduler daemon** (PID, Heartbeat).
  2. Trạng thái của **Webserver daemon** (Cổng `:8080`, số lượng workers).
  3. Lịch sử chạy và kết quả thực thi (`success`, `failed`, `running`) của 7 DAGs cào xoay vòng hàng ngày: `crawler_topdev`, `crawler_careerviet`, `crawler_itviec`, `crawler_vietnamworks`, `crawler_topcv`, `crawler_vieclam24h`.
  4. Thông tin được truy vấn trực tiếp từ cơ sở dữ liệu `airflow/airflow.db` và tiến trình hệ điều hành.

---

## 5. Nguyên Tắc Đồng Bộ Cloudflare R2 Vững Chắc (Robust R2 Sync Engine)
- Hệ thống độc quyền sử dụng **Cloudflare R2** (`vn-it-jobs`). Toàn bộ mã nguồn MinIO S3 cục bộ và generic Boto3 S3 đã bị loại bỏ.
- **Đồng bộ hóa liên tục giữa Cloud và Monitoring (Cloud & Monitoring Sync)**:
  - Hệ thống giám sát không được vận hành cô lập với ổ cứng cục bộ mà phải liên tục kiểm toán (Audit) đối chiếu với Cloudflare R2 bucket.
  - Phân hệ Crawling & Collection phải tích hợp dải giám sát đồng bộ (Cloud Synchronization Strip), hiển thị độ trễ ping và hỗ trợ **1-Click Cloud Sync** cho cả URL Ledger (`catalog_master.json`) lẫn các tệp JSON thô (Raw As-Is).
- Cơ chế đồng bộ (Sync) phải đảm bảo:
  1. **Tính toán chênh lệch (Diff Calculation)**: Dựa trên mã băm nội dung SHA-256 (`content_hash`), không so sánh cảm tính bằng ngày giờ file.
  2. **Non-blocking & Progress Tracking**: Tác vụ đồng bộ phải chạy ngầm, cung cấp endpoint báo cáo tiến độ (X/Y files, % hoàn thành, lỗi nếu có).
  3. **Kiểm tra tính toàn vẹn 4 phân tầng**: `url_ledger/`, `raw/`, `staging/`, `curated/`.

---

## 6. Tiêu Chuẩn Thẩm Mỹ Giao Diện (Aesthetic & Design Standards)
- **Theme**: Dark Slate cao cấp làm chủ đạo (`bg-slate-950`, `bg-slate-900`, viền `border-slate-800`).
- **Hiệu ứng**: Áp dụng Glassmorphism (`backdrop-blur-md`), góc bo hiện đại (`rounded-2xl`), và các hiệu ứng phát sáng nhẹ (Subtle glow).
- **Màu sắc ngữ nghĩa thống nhất**:
  - `Emerald (#10b981)`: Trạng thái thành công, Golden Master Dataset, kết nối online.
  - `Cyan (#06b6d4)`: Tác vụ tiền xử lý, dữ liệu làm sạch.
  - `Indigo/Violet (#6366f1 / #8b5cf6)`: Master Dashboard, thương hiệu hệ thống, phân hệ ML 3D.
  - `Amber (#f59e0b)`: Cảnh báo, chênh lệch đồng bộ (Out of sync), tiến trình đang chạy.
  - `Rose (#f43f5e)`: Lỗi cào, bài đăng bất thường / tin rác (Isolation Forest Anomaly).
- **Tận dụng MCP**: Tận dụng triệt để `shadcn-space` MCP để lấy cấu trúc blocks chuẩn, kết hợp `magic-ui` để tạo animation mượt mà.


---

## 7. Quy Định Ngôn Ngữ Bắt Buộc: 100% TypeScript (Strictly No JavaScript)
- Toàn bộ mã nguồn phía giao diện người dùng, cấu hình xây dựng (Vite `vite.config.ts`, Tailwind `tailwind.config.ts`), công cụ hỗ trợ và script kiểm thử UI bắt buộc phải viết bằng **TypeScript** (`.ts`, `.tsx`).
- **Tuyệt đối cấm**:
  - Không tạo hoặc lưu trữ các tệp có đuôi `.js` hoặc `.jsx` trong thư mục frontend.
  - Không tắt cờ `"allowJs": false` trong `tsconfig.json`.
- Mọi component, hook, hàm tiện ích và dữ liệu trao đổi API phải được định kiểu tường minh thông qua TypeScript Interfaces/Types tại `types.ts`, nghiêm cấm lạm dụng kiểu `any`.
- Khi tích hợp khối UI từ MCP (`shadcn-space`), chỉ chấp nhận mã nguồn TypeScript chuẩn.
