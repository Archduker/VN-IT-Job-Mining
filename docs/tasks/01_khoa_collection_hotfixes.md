# 🛠️ CẨM NANG NHIỆM VỤ: COLLECTION & CRAWLER HOTFIXES
## THÀNH VIÊN PHỤ TRÁCH: ANH KHOA

> **Hạn chót hoàn thành (Deadline):** **19:00 PM Chủ Nhật**  
> **Thư mục thực hiện chính (Folder Ownership):**  
> - `collection/` (Đặc biệt: `collection/sources/topdev/`, `collection/sources/topcv/`, `collection/common/`)  
> - `tests/contract/` (Hệ thống kiểm thử tiêu chuẩn C1–C14)  
> **Nhánh Git cá nhân:** `feature/collection-hotfixes`  
> **Nhánh hợp nhất (Merge Destination):** `sprint/pipeline-delivery`  
> **Tài liệu đặc tả đối chiếu:** [`docs/spec/04_collection_spec.md`](../spec/04_collection_spec.md), [`docs/spec/12_coding_standards.md`](../spec/12_coding_standards.md)

---

## 1. Mục Tiêu & Các Vấn Đề Cốt Lõi Cần Giải Quyết

Khoa chịu trách nhiệm khắc phục các điểm nghẽn và lỗi thu thập dữ liệu thô (Raw Collection) được ghi nhận trong `KNOWN_ISSUED.md`:

1. **Sửa lỗi TopDev thiếu metadata (Vấn đề `SCRAPE-5`):**
   - *Hiện trạng:* Pha detail của TopDev lưu raw thiếu `experiences_str`, `job_levels_str`, `published` trong `DETAIL_FIELDS`.
   - *Nhiệm vụ:* Đảm bảo crawler TopDev lấy trọn vẹn các trường này, kiểm tra cơ chế CDC tự động tạo version mới khi cào lại.
2. **Khắc phục TopDev cào tin ngoài IT (Vấn đề `SCRAPE-15`):**
   - *Hiện trạng:* API `/td/v2/jobs` bỏ qua tham số `category_ids=1`, dẫn đến 1.123 tin ngoài IT bị cào về, gây tốn tài nguyên.
   - *Nhiệm vụ:* Tìm đúng tham số lọc ngành IT của TopDev API hoặc áp dụng bộ lọc sơ bộ tại pha Discovery trước khi ghi vào Sổ cái URL Ledger.
3. **Xử lý 297 tin TopCV bị rỗng mô tả JD (Vấn đề `SCRAPE-16`):**
   - *Hiện trạng:* 297 tin TopCV cào ngày 22–26/10 bị rỗng trường JD (chỉ có tiêu đề, công ty, lương).
   - *Nhiệm vụ:* Tìm nguyên nhân crawler TopCV không bóc tách được DOM trên `/viec-lam/` và `/brand/`; sửa selector và tạo kịch bản đưa các tin này về trạng thái `PENDING` để cào bù (Auto-Backfill).
4. **Hoàn thiện Contract Tests cho 6 nguồn còn lại (Vấn đề `SCRAPE-14` & `SCRAPE-11`):**
   - *Hiện trạng:* Mới chỉ có TopDev và TopCV có contract test.
   - *Nhiệm vụ:* Bổ sung contract tests C1–C14 cho: VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO dựa trên fixtures offline sẵn có trong `tests/fixtures/<source>/`.

---

## 2. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Khoa làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Kỹ sư Thu thập Dữ liệu (Data Collection Specialist) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là xử lý các lỗi cào tồn đọng (SCRAPE-5, SCRAPE-15, SCRAPE-16) và hoàn thiện hệ thống Contract Tests C1-C14 cho 6 nguồn tuyển dụng còn lại. Tham khảo đặc tả kỹ thuật tại docs/spec/04_collection_spec.md và docs/spec/12_coding_standards.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Chỉ được can thiệp vào mã nguồn trong thư mục: `collection/` và `tests/contract/`. Tuyệt đối không chỉnh sửa các thư mục khác.
- Tuân thủ chuẩn Python 3.12, thời gian nghỉ polite_sleep ngẫu nhiên 2.0s - 4.5s.
- Tuyệt đối giữ tính bất biến của dữ liệu thô (Immutable Raw): Không viết script sửa đổi trực tiếp các file JSON cũ trên R2.
- Thao tác R2 luôn chạy ở chế độ kiểm tra an toàn `--dry-run` trước.

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào: API và HTML crawler từ 8 sàn tuyển dụng; URL Ledger catalog_master.json.
- Đầu ra: RawJobEnvelope JSON chuẩn lưu tại data/<source>/raw/; tests/contract/ pass 100% với pytest (chế độ zero-network).

### 4. YÊU CẦU THỰC HIỆN:
Hãy lập Plan chi tiết từng bước trước khi sửa code, sau đó thực hiện lần lượt từng vấn đề kèm lệnh kiểm chứng.
```

---

## 3. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [ ] **Bước 1 (TopDev):** Kiểm tra `collection/sources/topdev/crawler.py`, test cào thử 1 URL thật xem raw JSON sinh ra có đủ `experiences_str`, `job_levels_str`, `published` không.
- [ ] **Bước 2 (TopDev IT Filter):** Xác thực tham số API của TopDev để chỉ lấy tin IT, chạy Discovery thử 1 trang và đếm tỷ lệ tin IT.
- [ ] **Bước 3 (TopCV Empty JD):** Cập nhật selector bóc tách mô tả công việc của TopCV, kiểm tra thử trên 1 fixture bị rỗng cũ.
- [ ] **Bước 4 (Contract Tests):** Chạy lệnh kiểm thử contract:
  ```bash
  pytest tests/contract/ -v
  ```
  Đảm bảo không vi phạm tiêu chuẩn C1–C14 và không có kết nối mạng ra bên ngoài.
- [ ] **Bước 5 (Linting):** Chạy `ruff check collection/ tests/contract/` để dọn dẹp lỗi cú pháp trên phần code mình sửa.

---

## 4. Mẫu Báo Cáo Nghiệm Thu Bàn Giao (Delivery Report Template)

*Sau khi hoàn thành, Khoa điền thông tin vào mẫu dưới đây và dán vào mô tả Pull Request khi merge vào `sprint/pipeline-delivery`:*

```markdown
### BÁO CÁO NGHIỆM THU: COLLECTION & CRAWLER HOTFIXES
- **Người thực hiện:** Anh Khoa
- **Nhánh làm việc:** `feature/collection-hotfixes`
- **Thư mục can thiệp:** `collection/`, `tests/contract/`

#### 1. Vấn Đề Gặp Phải (Problems Encountered):
- [Mô tả chi tiết các lỗi SCRAPE-5, 15, 16 hoặc khó khăn khi viết test]

#### 2. Nguyên Nhân Gốc Rễ (Root Cause):
- [Giải thích vì sao code cũ bị lỗi]

#### 3. Giải Pháp Kỹ Thuật Đã Triển Khai (Solution Implemented):
- [Trình bày cách sửa đổi trong crawler và contract tests]

#### 4. Bằng Chứng Tự Kiểm Chứng (Verification Proof):
- Lệnh chạy test: `pytest tests/contract/` -> Kết quả: [Ví dụ: 18/18 passed]
- Lệnh kiểm tra cào thử: `python run.py --source topdev --phase detail --max-items 3` -> Kết quả: [Đủ trường]

#### 5. Vấn Đề Còn Tồn Đọng (Remaining Issues / Blockers):
- [Ghi rõ nếu còn nguồn nào chưa hoàn hảo, hoặc ghi "Không còn"]
```
