# ADR 0003: Áp Dụng Kiến Trúc Huy Chương (Medallion Architecture) & Chuẩn Hóa Silver Dataset

- **Trạng thái:** Đã Chấp Thuận (Accepted)  
- **Ngày quyết định:** 2026-10-27  
- **Người đề xuất:** Kỹ Sư Trưởng & Nhóm Khai Phá Dữ Liệu (Lead Data Engineer & Data Mining Team)  
- **Phạm vi ảnh hưởng:** `preprocessing/`, `data/silver/`, `data/curated/`, `scripts/`, Cloudflare R2

---

## 1. Ngữ Cảnh & Vấn Đề (Context)

Trong các giai đoạn phát triển ban đầu, dự án sử dụng các tên gọi phân tầng truyền thống như `raw/`, `url_ledger/`, `staging/`, `transformation/`, `integration/`, và `curated/golden_master.json`.  
Cách gọi này bộc lộ một số hạn chế:
1. **Thiếu tính phân cấp chuẩn công nghiệp:** Khi bước vào giai đoạn Khai phá Dữ liệu (Data Mining với các thuật toán Apriori, Regression, Clustering), việc gọi bộ dữ liệu sau tiền xử lý là "Gold" hoặc "Golden Master" dễ gây nhầm lẫn với các bảng đặc trưng kinh doanh (Business Feature Marts) được tổng hợp ở bước sau.
2. **Khó khăn trong quản trị Lakehouse Cloudflare R2:** Các thành viên trong nhóm khó phân định đâu là tầng dữ liệu cần lưu trữ thô, đâu là bộ dữ liệu chuẩn cần chia sẻ và đâu là các sản phẩm phân tích chuyên sâu.

Nhóm kỹ thuật đã quyết định tái cấu trúc toàn diện hệ thống phân tầng dữ liệu theo **Kiến Trúc Huy Chương (Medallion Architecture: Bronze ➔ Silver ➔ Gold)**.

---

## 2. Quyết Định Kiến Trúc (Decision)

### 2.1. Phân Tầng Medallion 3 Lớp Bắt Buộc:

```text
+-------------------+     +-------------------------+     +----------------------+
|  BRONZE DATASET   | --> |     SILVER DATASET      | --> |     GOLD DATASET     |
| (Raw Ingestion)   |     | (Cleaned & Conformed)   |     | (Mining & Analytics) |
+-------------------+     +-------------------------+     +----------------------+
| - Dữ liệu cào thô |     | - 8,959 tin IT sạch     |     | - SD1: Salary Matrix |
| - Raw envelopes   |     | - 100% RFC 8259 JSON    |     | - SD2: Job Clusters  |
| - URL Ledgers     |     | - Target Schema 11 Keys |     | - SD3: Skill Basket  |
| - Bất biến        |     | - Bảo tồn Null thực tế  |     | - SD4: Market Marts  |
| - data/raw/       |     | - data/silver/          |     | - data/gold/         |
| - r2://raw/       |     | - r2://silver/          |     | - r2://gold/         |
+-------------------+     +-------------------------+     +----------------------+
```

1. **Bronze Dataset (Tầng Dữ Liệu Thô):**
   - Là kết quả thu thập ban đầu từ 8 sàn (Phase 1 & Phase 2).
   - Dữ liệu dạng `RawJobEnvelope`, lưu trữ tại `data/<source>/raw/` và `data/url_ledger/`.
   - Trạng thái: Bất biến (Immutable), bảo toàn nguyên vẹn 100% dữ liệu cào.

2. **Silver Dataset (Bộ Dữ Liệu Chuẩn Sau Tiền Xử Lý):**
   - **Đây chính là "Bộ Dữ Liệu Chuẩn"** đại diện cho toàn bộ thành quả của chuỗi Master Preprocessing Pipeline.
   - Gồm chính xác **8,959 bài đăng IT chuẩn mực** sau khi khử 1,497 bài trùng lặp chéo sàn và lọc 361 tin rác stub JDs.
   - Tuân thủ nghiêm ngặt chuẩn Ground Truth Realism: Bảo tồn `null` cho 5,397 tin lương thỏa thuận (kèm `is_salary_negotiable: true`), 100% ngôn ngữ tiếng Việt (`language: "vi"`), chuẩn hóa 11 Khóa Gốc.
   - Lưu trữ chính thức tại:
     - Dạng đa tầng phân cấp: `data/silver/silver_master_dataset.json`
     - Dạng bảng phẳng: `data/silver/silver_flat_jobs.json`
     - Bệnh án chất lượng: `reports/silver/silver_dataset_health_card.json`
   - *Tính tương thích ngược:* Tiếp tục duy trì song song bản sao tại `data/curated/golden_master.json` và `data/curated/curated_flat_golden_jobs.json` để bảo vệ 100% các script và test suite hiện có.

3. **Gold Dataset (Tầng Tri Thức Nghiệp Vụ & Khai Phá Nâng Cao):**
   - Là các tập dữ liệu dẫn xuất được trích xuất từ Silver Dataset để phục vụ trực tiếp cho 5 mục tiêu Data Mining (SD1 – SD5).
   - Bao gồm: Giỏ giao dịch kỹ năng cho thuật toán Apriori (SD3), Ma trận đặc trưng số hóa cho mô hình hồi quy lương (SD1), Ma trận TF-IDF cho phân cụm chức danh (SD2), Bảng tổng hợp thị trường theo chiều không gian (SD4/SD5).
   - Lưu trữ tại: `data/gold/`.

### 2.2. Quy Chuẩn Đồng Bộ Cloudflare R2:
- Đồng bộ bộ dữ liệu chuẩn Silver lên Cloudflare R2 theo đường dẫn chuẩn mực: `s3://vn-it-jobs/silver/`.
- Phân tách rõ ràng với dữ liệu thô `s3://vn-it-jobs/raw/` (hoặc `bronze/`) và sản phẩm phân tích `s3://vn-it-jobs/gold/`.

---

## 3. Hệ Quả & Lợi Ích (Consequences)

### Tích cực:
- **Tường minh kiến trúc:** Định danh rõ ràng bản chất dữ liệu: Silver là bản ghi chuẩn sau tiền xử lý; Gold là sản phẩm khai phá.
- **Dễ dàng mở rộng cho Data Mining:** Các thuật toán Machine Learning / Khai phá luật kết hợp ở giai đoạn tiếp theo sẽ đọc từ Silver và ghi vào Gold một cách mạch lạc.
- **Bảo mật & Tối ưu lưu trữ R2:** Đảm bảo chỉ tải đúng bộ dữ liệu chuẩn lên Cloudflare R2, tránh tràn ngập các tệp trung gian không cần thiết.
