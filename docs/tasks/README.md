# 📋 BẢNG ĐIỀU PHỐI SPRINT NHIỆM VỤ (SPRINT DELIVERY BOARD)
## DỰ ÁN: VN-IT-JOB-MINING — HỆ THỐNG KHAI PHÁ DỮ LIỆU LAO ĐỘNG IT VIỆT NAM

> **Hạn chót hoàn thành (Deadline):** **19:00 PM Chủ Nhật**  
> **Nhánh gốc tích hợp (Sprint Base Branch):** `sprint/pipeline-delivery`  
> **Mục tiêu Sprint:** Hoàn thiện toàn bộ các bước còn thiếu và các vấn đề tồn đọng từ Collection $\rightarrow$ Preprocessing $\rightarrow$ Processing $\rightarrow$ Data Mining $\rightarrow$ Monitoring $\rightarrow$ Evaluation để ra được bộ dữ liệu Golden Master và hệ thống phân tích hoàn chỉnh.

---

## 1. Bảng Phân Bổ Nhiệm Vụ 8 Thành Viên (Folder Ownership Matrix)

| STT | Thành Viên | Phân Vùng Chuyên Trách | Thư Mục Thực Hiện Chính (Folder Ownership) | Nhánh Làm Việc | Merge Vào | Tệp Cẩm Nang Nhiệm Vụ & Báo Cáo | Trạng Thái |
|:---:|---|---|---|---|---|---|:---:|
| **1** | **Khoa** | Collection & Crawler Hotfixes | `collection/`<br>`tests/contract/` | `feature/collection-hotfixes` | `sprint/pipeline-delivery` | [`01_khoa_collection_hotfixes.md`](01_khoa_collection_hotfixes.md) | 🟡 In Progress |
| **2** | **Tài** | Bước 1: Clean & Deduplication 2 lớp | `preprocessing/clean/`<br>`preprocessing/deduplication/` | `feature/p1-clean-dedup` | `sprint/pipeline-delivery` | [`02_tai_clean_and_deduplication.md`](02_tai_clean_and_deduplication.md) | 🟡 In Progress |
| **3** | **Hoàng** *(Mới)* | Bước 2: Integration & Schema Flatten | `preprocessing/integration/` | `feature/p2-integration-flatten` | `sprint/pipeline-delivery` | [`03_hoang_integration_and_flattening.md`](03_hoang_integration_and_flattening.md) | 🟡 In Progress |
| **4** | **Duy** | Bước 3 & 4: Transformation & Normalization | `preprocessing/transformation/`<br>`preprocessing/normalization/`<br>`preprocessing/dictionaries/` | `feature/p3-p4-transform-normalize` | `sprint/pipeline-delivery` | [`04_duy_transformation_and_normalization.md`](04_duy_transformation_and_normalization.md) | 🟡 In Progress |
| **5** | **Phát** | Bước 5: Feature Encoding & Matrices | `preprocessing/encoding/` | `feature/p5-encoding-matrices` | `sprint/pipeline-delivery` | [`05_phat_encoding_and_matrices.md`](05_phat_encoding_and_matrices.md) | 🟡 In Progress |
| **6** | **Phúc** | Data Mining Core Algorithms | `mining/` | `feature/mining-algorithms` | `sprint/pipeline-delivery` | [`06_phuc_data_mining_algorithms.md`](06_phuc_data_mining_algorithms.md) | 🟡 In Progress |
| **7** | **Sơn** | Monitoring Observatory Refactoring | `monitoring/backend/`<br>`monitoring/frontend/` | `feature/monitoring-observatory` | `sprint/pipeline-delivery` | [`07_son_monitoring_observatory.md`](07_son_monitoring_observatory.md) | 🟡 In Progress |
| **8** | **Thuận** *(Lead)* | Pipeline Integration & Evaluation | `docs/reports/`<br>`scripts/`<br>`tests/integration/` | `sprint/pipeline-delivery` | `main` | [`08_thuan_integration_and_evaluation.md`](08_thuan_integration_and_evaluation.md) | 🔵 Coordinating |

---

## 2. Nguyên Tắc Phân Chia Theo Thư Mục (Folder Ownership Rules)

1. **Ranh giới thư mục độc quyền (Strict Isolation):** Mỗi thành viên chỉ thực hiện commit các thay đổi trong **Thư mục thực hiện chính** được giao và tệp cẩm nang cá nhân của mình trong `docs/tasks/`. Tuyệt đối không can thiệp vào thư mục của thành viên khác để tránh xung đột mã nguồn (merge conflicts).
2. **Quy trình 5 bước bắt buộc:**
   - **Bước 1 — Đọc đặc tả:** Đọc kỹ tài liệu đối chiếu trong `docs/spec/` trước khi bắt đầu.
   - **Bước 2 — Soạn Prompt chuẩn:** Dùng khung Prompt có sẵn trong cẩm nang cá nhân để làm việc với AI Agent (Claude Code / Antigravity / Cursor).
   - **Bước 3 — Lên Plan & Review:** Lập danh sách công việc chi tiết trước khi code.
   - **Bước 4 — Viết Code & Tự kiểm chứng (Self-Verification):** Chạy `make test-fast` hoặc test của module mình, xuất log kiểm toán số liệu thật.
   - **Bước 5 — Viết báo cáo bàn giao:** Cập nhật mục Báo cáo nghiệm thu ở cuối file cẩm nang cá nhân trước khi tạo Pull Request.

---

## 3. Hướng Dẫn Git Phối Hợp Làm Việc

```bash
# 1. Cập nhật nhánh sprint/pipeline-delivery từ remote
git fetch origin
git checkout sprint/pipeline-delivery
git pull origin sprint/pipeline-delivery

# 2. Tạo nhánh tính năng cá nhân
git checkout -b feature/<ten-nhanh-cua-ban>

# 3. Làm việc trong thư mục của mình, kiểm tra chuẩn mã nguồn
make lint
make test-fast

# 4. Commit và push nhánh lên GitHub
git add <thu-muc-cua-ban> docs/tasks/0X_<ten-ban>.md
git commit -m "feat(<module>): hoàn thành nhiệm vụ sprint"
git push origin feature/<ten-nhanh-cua-ban>

# 5. Tạo Pull Request trên GitHub vào nhánh base: sprint/pipeline-delivery
# Gửi link PR cho Lead Thuận review trước 19:00 Chủ Nhật.
```
