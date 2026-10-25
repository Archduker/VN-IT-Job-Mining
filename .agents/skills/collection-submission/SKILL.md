---
name: collection-submission
description: >-
  Chuyên gia kiểm tra, thẩm định và hướng dẫn nộp hồ sơ thu thập dữ liệu tuyển dụng (Data Collection Deliverables).
  Quy định chuẩn bộ 3 file HTML thô + 3 file JSON tương ứng (kèm file .md mô tả),
  cơ chế đồng bộ dữ liệu cào đa tầng lên MinIO Lakehouse và Cloudflare R2,
  và tự động chấm điểm tiêu chuẩn nghiệm thu (Definition of Done - DoD).
---

# Collection Submission Skill (Hồ Sơ Nghiệm Thu Thu Thập Dữ Liệu)

Kỹ năng này trang bị cho AI Agent và các thành viên dự án quy chuẩn nghiệm thu hoàn chỉnh cho công việc thu thập dữ liệu (Phase 1 & Phase 2), kiểm tra tự động bộ mẫu dữ liệu (Samples), đồng bộ đa đám mây (MinIO & Cloudflare R2) và hồ sơ báo cáo.

---

## 1. Tiêu Chuẩn Bộ Mẫu Thử Nghiệm (Samples Delivery Standard)

Mỗi sàn tuyển dụng bắt buộc phải tạo thư mục lưu trữ mẫu tại:
`collection/sources/<tenweb>/samples/`

### 1.1. Cấu trúc bắt buộc: 3 File HTML Thô + 3 File JSON Tương Ứng
Bộ mẫu phải phản ánh được sự biến thiên layout của sàn web thực tế:

| Tên File Mẫu | Định dạng HTML | Định dạng JSON tương ứng | Tiêu chí phân loại mẫu |
| :--- | :--- | :--- | :--- |
| **Mẫu 1: Tiêu chuẩn** | `sample_standard_job.html` | `sample_standard_job.json` | Tin tuyển dụng cơ bản, mức lương số rõ ràng (VD: 15 - 25 triệu VND), đầy đủ mô tả công việc. |
| **Mẫu 2: Đặc thù / VIP** | `sample_hot_vip_job.html` | `sample_hot_vip_job.json` | Tin tuyển dụng loại VIP / Hot / Urgent / Spotlight / có badge công ty đặc biệt hoặc cấu trúc DOM khác biệt. |
| **Mẫu 3: Lương đặc biệt** | `sample_negotiable_salary.html` | `sample_negotiable_salary.json` | Tin có mức lương "Thỏa thuận", lương ngoại tệ (USD), hoặc bài đăng có số lượng thẻ tech tags / benefits phong phú. |

> [!NOTE]
> Đối với các nguồn cào thuần REST / Algolia / GraphQL API (như `topdev`, `vietnamworks`):
> - Có thể lưu `sample_*.html` là HTML snapshot tải từ link web đại diện, hoặc file text response tương đương.
> - `sample_*.json` là kết quả parse chuẩn hóa theo đúng Data Contract dự án (Schema v1: metadata, raw payload, clean lines).

### 1.2. File Markdown Mô Tả Sample (`.md`)
Khuyến khích và cho phép thành viên nộp thêm file Markdown ghi chú tại:
`collection/sources/<tenweb>/samples/README.md` (hoặc `sample_notes.md`)
- Trình bày URL gốc của từng sample.
- Bảng đối soát các selector CSS/XPath tương ứng trên giao diện web.
- Ghi chú các trường dị biệt hoặc trường dễ bị null trên sàn đó.

---

## 2. Quy Chuẩn Đồng Bộ Đa Đám Mây (MinIO & Cloudflare R2)

Toàn bộ dữ liệu thu thập được ở cả 2 pha bắt buộc phải đồng bộ lên **cả MinIO Lakehouse cục bộ VÀ Cloudflare (Cloudflare R2 Object Storage)**:

### 2.1. Cấu hình biến môi trường (`.env`)
Đảm bảo file `.env` đã điền đủ thông tin cho cả 2 đích:

```bash
# --- MinIO Lakehouse (Local) ---
MINIO_ENDPOINT=http://localhost:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET=vn-it-jobs

# --- Cloudflare R2 Object Storage (Remote) ---
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET_NAME=vn-it-jobs
R2_ENDPOINT_URL=https://<your_account_id>.r2.cloudflarestorage.com
```

### 2.2. Quy hoạch đường dẫn lưu trữ trên Lakehouse
```text
vn-it-jobs/
├── url_ledger/
│   └── <source>/
│       ├── catalog_master.json
│       └── manifests/
│           └── manifest_YYYY-MM-DD.jsonl
└── raw/
    └── <source>/
        └── dt=YYYY-MM-DD/
            ├── batch_001.json
            └── clean_containers/
                └── <job_id>.html
```

### 2.3. Lệnh đồng bộ một chạm (One-Command Sync)
Sau khi cào xong, chạy script đồng bộ tự động:
```bash
# Đồng bộ toàn bộ dữ liệu cào cục bộ lên MinIO và Cloudflare R2
python3 scripts/sync_cloud_lakehouse.py
```

---

## 3. Bộ Hồ Sơ Báo Cáo Nghiệm Thu Bắt Buộc

Mỗi nhánh `crawls/<tenweb>` khi tạo Pull Request vào `main` phải có đủ 3 tài liệu:
1. **Tài liệu phân tích kiến trúc web:**
   `docs/crawl/<tenweb>.md` (phân tích SSR/SPA, cơ chế chống bot, Cloudflare WAF, container selector).
2. **Báo cáo kiểm kê trường dữ liệu (Field Inventory):**
   `collection/reports/<tenweb>_inventory.md` (theo mẫu `templates/raw_crawl_inventory_template.md`).
3. **Báo cáo phân tích dữ liệu sơ bộ (Preliminary EDA):**
   `collection/reports/<tenweb>_eda.md` (theo mẫu `templates/preliminary_eda_template.md`).

---

## 4. Công Cụ Kiểm Tra Nghiệm Thu Tự Động (Automated DoD Verifier)

Kỹ năng này cung cấp sẵn script CLI để kiểm tra nhanh mức độ hoàn thành nhiệm vụ của bất kỳ nguồn nào:

```bash
# Kiểm tra nghiệm thu cho nguồn TopCV
python3 .agents/skills/collection-submission/scripts/verify_submission.py --source topcv

# Kiểm tra cho nguồn VietnamWorks
python3 .agents/skills/collection-submission/scripts/verify_submission.py --source vietnamworks
```

### Tiêu chí chấm điểm tự động của Script:
- [x] **Criterion 1 (HTML Samples):** Tối thiểu 3 file `.html` trong `collection/sources/<source>/samples/`.
- [x] **Criterion 2 (JSON Samples):** Tối thiểu 3 file `.json` tương ứng, parse hợp lệ không lỗi cú pháp.
- [x] **Criterion 3 (Sample Docs):** Kiểm tra file `.md` mô tả sample nếu có.
- [x] **Criterion 4 (Architecture Doc):** File `docs/crawl/<source>.md` tồn tại và có nội dung phân tích.
- [x] **Criterion 5 (Inventory Report):** File `collection/reports/<source>_inventory.md` tồn tại.
- [x] **Criterion 6 (EDA Report):** File `collection/reports/<source>_eda.md` tồn tại.
- [x] **Criterion 7 (Storage Readiness):** Kiểm tra cấu hình kết nối MinIO và Cloudflare R2 trong môi trường.
