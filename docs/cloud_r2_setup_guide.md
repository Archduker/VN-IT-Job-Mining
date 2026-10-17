# ☁️ Cẩm Nang Thiết Lập & Đồng Bộ Cloudflare R2 Data Lakehouse Cho Cả Team

---

## 1. 🌟 Tại Sao Nhóm Sử Dụng Cloudflare R2?

Khi các thành viên trong nhóm cào dữ liệu độc lập trên máy tính cá nhân (TopCV, ITViec, VietnamWorks, TopDev,...), việc chia sẻ dữ liệu gặp phải các vấn đề:
- MinIO cục bộ (`localhost:9000`) chỉ lưu trên máy cá nhân, máy người khác không xem được.
- Đẩy hàng chục ngàn file HTML thô vào GitHub sẽ làm phình to repo và gây lỗi xung đột Git (merge conflict).

**Cloudflare R2** giải quyết triệt để vấn đề này:
- **Chuẩn Amazon S3 API**: Tương thích 100% với mã nguồn crawler hiện tại.
- **Hoàn toàn miễn phí**: Miễn phí **10 GB lưu trữ** và **0đ phí tải về (Free Egress)** trọn đời.
- **Tập trung hóa thời gian thực (24/7)**: Bất kỳ ai cào xong, dữ liệu lập tức xuất hiện trên Cloud chung để cả nhóm cùng dùng làm EDA và mô hình hóa.

---

## 2. 🔑 Cách Lấy Thông Số Kết Nối Trên Cloudflare (Mất 2 Phút)

*(Nếu bạn là nhóm trưởng tạo bucket hoặc đã có sẵn tài khoản Cloudflare)*

1. Đăng nhập vào [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Chọn **R2 Object Storage** ở menu bên trái.
3. **Lấy Account ID**:
   - Nhìn sang góc phải màn hình, mục **Account Details** $\to$ Sao chép **Account ID** (chuỗi 32 ký tự, ví dụ: `9a8b7c6d...`).
4. **Tạo Bucket**:
   - Bấm nút **Create bucket** $\to$ Đặt tên: **`vn-it-jobs`** $\to$ Bấm **Create Bucket**.
5. **Tạo API Token (Khóa truy cập)**:
   - Ở trang chủ R2, bấm vào liên kết **Manage R2 API Tokens** (góc phải).
   - Bấm **Create API Token**.
   - Quyền hạn (Permissions): Chọn **Object Read & Write**.
   - Áp dụng cho: Chọn bucket **`vn-it-jobs`** (hoặc All buckets).
   - Bấm **Create API Token**.
   - Màn hình sẽ hiện ra:
     - **Access Key ID** (chuỗi 32 ký tự)
     - **Secret Access Key** (chuỗi 64 ký tự)
     - **Endpoint URL**: `https://<account_id>.r2.cloudflarestorage.com`
   *(Hãy lưu lại khóa này cẩn thận vì Secret Key chỉ hiển thị 1 lần duy nhất).*

---

## 3. 🚀 Cấu Hình Tự Động 1-Lệnh Cho Từng Thành Viên

### Cách 1: Chạy Wizard tương tác (Khuyến nghị)
Bạn chỉ cần mở terminal và gõ:
```bash
.venv/bin/python scripts/setup_cloud_storage.py
```
Script sẽ lần lượt hỏi Account ID, Access Key ID, Secret Access Key:
- Tự động kiểm tra bắt tay S3 API.
- Tự động tạo bucket `vn-it-jobs` nếu chưa có.
- Tự động đẩy dữ liệu TopCV hiện tại (2.776 bài đăng) lên Cloud R2.
- Tự động lưu cấu hình an toàn vào `.env` (file này đã nằm trong `.gitignore` nên an toàn tuyệt đối).

### Cách 2: Điền trực tiếp qua dòng lệnh:
```bash
.venv/bin/python scripts/setup_cloud_storage.py \
  --account-id <YOUR_ACCOUNT_ID> \
  --access-key <YOUR_ACCESS_KEY_ID> \
  --secret-key <YOUR_SECRET_ACCESS_KEY> \
  --bucket vn-it-jobs
```

---

## 4. 🔄 Cách Cả Nhóm Đồng Bộ & Lấy Dữ Liệu Của Nhau

Sau khi đã cấu hình xong, mọi thành viên đều có thể tương tác với Cloud Lakehouse dễ dàng:

### 4.1. Xem danh sách URL cào được trên Cloud:
```bash
# Xem 20 bài đăng mới nhất từ Cloud Lakehouse chung
.venv/bin/python scripts/view_urls.py --source topcv --minio --limit 20
```
*(Giao diện sẽ hiển thị nhãn `☁️ [CLOUDFLARE R2 LAKEHOUSE]` xác nhận đang đọc từ Cloud).*

### 4.2. Tải toàn bộ dữ liệu của cả nhóm về máy mình:
Khi bạn khác cào xong ITViec, VietnamWorks hoặc TopDev, bạn chỉ cần gõ:
```bash
.venv/bin/python scripts/sync_cloud_lakehouse.py --download
```
Toàn bộ file HTML thô, file sổ cái URL Ledger của các bạn khác sẽ tự động được tải về thư mục `data/` trên máy bạn.

### 4.3. Đẩy dữ liệu mới cào từ máy mình lên Cloud:
Khi bạn cào thêm bài đăng mới hoặc cào sàn mới:
```bash
.venv/bin/python scripts/sync_cloud_lakehouse.py --upload
```
*(Hoặc các crawler tự động đẩy lên Cloud R2 sau mỗi 5 trang nếu file `.env` đã bật).*

### 4.4. Xem tình trạng lưu trữ trên Cloud:
```bash
.venv/bin/python scripts/sync_cloud_lakehouse.py --status
```

---

## 5. 🔒 Quy Tắc Bảo Mật Cho Nhóm

1. **Tuyệt đối không commit file `.env` lên GitHub**:
   - File `.env` chứa mật khẩu API Token của nhóm. Dự án đã cấu hình sẵn trong `.gitignore`.
2. **Chia sẻ cấu hình an toàn**:
   - Nhóm trưởng có thể gửi file `.env` cho các thành viên trong nhóm qua kênh chat riêng (Zalo/Telegram/Discord) để mọi người copy vào thư mục dự án trên máy họ.
