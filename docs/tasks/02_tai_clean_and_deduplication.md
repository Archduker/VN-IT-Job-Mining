# 🧹 CẨM NANG NHIỆM VỤ: CLEAN & DEDUPLICATION 2 LỚP
## THÀNH VIÊN PHỤ TRÁCH: PHAN NHẬT TÀI

> **Hạn chót hoàn thành (Deadline):** **19:00 PM Chủ Nhật**  
> **Thư mục thực hiện chính (Folder Ownership):**  
> - `preprocessing/clean/` (Bộ lọc IT 2 tầng, bộ lọc văn bản rác, HTML stripping)  
> - `preprocessing/deduplication/` (Động cơ khử trùng lặp nội sàn CDC & liên sàn TF-IDF Cosine)  
> **Nhánh Git cá nhân:** `feature/p1-clean-dedup`  
> **Nhánh hợp nhất (Merge Destination):** `sprint/pipeline-delivery`  
> **Tài liệu đặc tả đối chiếu:** [`docs/spec/05_preprocessing_spec.md`](../spec/05_preprocessing_spec.md), [`docs/spec/11_technical_decisions.md`](../spec/11_technical_decisions.md) (Mục ADR-04)

---

## 1. Mục Tiêu & Các Vấn Đề Cốt Lõi Cần Giải Quyết

Tài chịu trách nhiệm xây dựng "Cánh cổng kiểm soát chất lượng" đầu tiên của chuỗi tiền xử lý (Bước 1: Clean & Dedup) để loại bỏ toàn bộ dữ liệu rác, tin ngoài IT và các bài đăng tuyển trùng lặp:

1. **Bộ Lọc Ngành IT 2 Tầng Tất Định (Deterministic Two-Tier IT Filter):**
   - *Triết lý:* Tuyệt đối không dùng LLM/GenAI tốn kém và bất định (theo quyết định L-28).
   - *Tầng 1 (Title Filter):* Quét từ khóa chuyên môn IT trong chức danh tuyển dụng (developer, engineer, lập trình viên, data, devops, tester...).
   - *Tầng 2 (Context Filter):* Nếu tiêu đề chưa rõ ràng (ví dụ: "Nhân viên kỹ thuật"), quét nội dung JD; yêu cầu bài đăng phải chứa ít nhất $\ge 2$ kỹ năng công nghệ IT chuẩn từ bộ từ điển.
2. **Làm Sạch Văn Bản HTML & Lọc Rác:**
   - Dùng BeautifulSoup (`lxml`) bóc tách HTML, thay thẻ ngắt đoạn bằng `\n`, loại bỏ `<script>`, `<iframe>`.
   - Chuẩn hóa Unicode dựng sẵn NFC tiếng Việt, xóa ký tự điều khiển (`\x00`, `\u200b`).
   - Loại bỏ các bài đăng rỗng hoặc JD dưới 30 từ (Luật C5).
3. **Khử Trùng Lặp 2 Lớp (Two-Layer Deduplication Engine):**
   - **Lớp 1 (Nội sàn - Intra-source CDC):** Khử trùng các tin đăng lại (repost) trong cùng 1 sàn dựa trên mã băm canonical JSON và `job_id`.
   - **Lớp 2 (Liên sàn - Inter-source Cross-platform):** Áp dụng kỹ thuật **Blocking Key** (`Slug(Company) + "_" + City + "_" + Title_Group`) để giảm không gian so sánh $O(N^2) \rightarrow O(\sum N_k^2)$, sau đó đo độ tương đồng văn bản **TF-IDF Cosine Similarity** (ngưỡng $\ge 0.85$). Gom cụm các bài đăng trùng thành một Golden Record duy nhất (hợp nhất danh sách nguồn và tập kỹ năng $S_1 \cup S_2$).

---

## 2. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Tài làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Kỹ sư Tiền Xử Lý Dữ Liệu (Data Preprocessing Engineer) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là hoàn thiện Bước 1 trong chuỗi tiền xử lý: Làm sạch văn bản, Bộ lọc IT 2 tầng không dùng LLM, và Động cơ khử trùng lặp 2 lớp (Nội sàn CDC + Liên sàn Blocking Key & TF-IDF Cosine >= 0.85). Tham khảo đặc tả kỹ thuật tại docs/spec/05_preprocessing_spec.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Chỉ được can thiệp vào mã nguồn trong thư mục: `preprocessing/clean/` và `preprocessing/deduplication/`.
- Không sử dụng bất kỳ API gọi LLM nào (Zero-LLM Policy); toàn bộ logic phải mang tính tất định (Regex, Rules, Vector Cosine).
- Đảm bảo tính bảo toàn dữ liệu: Ghi nhận rõ số lượng tin bị loại bỏ kèm lý do (Non-IT, Empty JD, Duplicate).
- Tuân thủ Python 3.12, xử lý vector hóa với Scikit-learn / Numpy để tối ưu tốc độ.

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào: Các bản ghi raw JSON từ thư mục `data/<source>/raw/`.
- Đầu ra: Bảng dữ liệu sạch đã khử trùng lặp sẵn sàng cho bước Integration; báo cáo thống kê tỷ lệ loại bỏ (Dedup drop rate, Non-IT drop rate).

### 4. YÊU CẦU THỰC HIỆN:
Hãy lập Plan chi tiết từng bước trước khi viết code, sau đó thực hiện lần lượt các chức năng và chạy kiểm chứng với dữ liệu thực tế.
```

---

## 3. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [ ] **Bước 1 (Clean Logic):** Kiểm tra hàm bóc tách HTML và chuẩn hóa Unicode tiếng Việt, đảm bảo không làm mất các ký tự công nghệ quan trọng (ví dụ: `C#`, `C++`, `.NET`).
- [ ] **Bước 2 (IT Filter Test):** Chạy thử bộ lọc IT trên tập 100 tin mẫu; đo độ chính xác (Precision) đạt $\ge 95\%$ trên nhãn thực tế.
- [ ] **Bước 3 (Intra-source Dedup):** Kiểm tra việc lọc trùng cùng sàn qua `job_id` và CDC hash, đảm bảo không bị mất các tin có nội dung cập nhật mới.
- [ ] **Bước 4 (Inter-source Dedup):** Chạy thuật toán Blocking + TF-IDF Cosine trên tập dữ liệu đa sàn. Kiểm tra danh sách các cặp bài đăng có Cosine $\ge 0.85$ xem có đúng là tuyển cùng 1 vị trí của cùng công ty không.
- [ ] **Bước 5 (Tự kiểm chứng số liệu):** Xác thực phương trình bảo toàn:
  $$\text{Tổng tin đầu vào} = \text{Tin IT hợp lệ} + \text{Tin ngoài IT} + \text{Tin rỗng} + \text{Tin trùng lặp}$$
- [ ] **Bước 6 (Linting):** Chạy `ruff check preprocessing/clean/ preprocessing/deduplication/`.

---

## 4. Mẫu Báo Cáo Nghiệm Thu Bàn Giao (Delivery Report Template)

*Sau khi hoàn thành, Tài điền thông tin vào mẫu dưới đây và dán vào mô tả Pull Request khi merge vào `sprint/pipeline-delivery`:*

```markdown
### BÁO CÁO NGHIỆM THU: CLEAN & DEDUPLICATION 2 LỚP
- **Người thực hiện:** Phan Nhật Tài
- **Nhánh làm việc:** `feature/p1-clean-dedup`
- **Thư mục can thiệp:** `preprocessing/clean/`, `preprocessing/deduplication/`

#### 1. Vấn Đề Gặp Phải (Problems Encountered):
- [Mô tả những thách thức khi lọc tin ngoài IT hoặc khi tính độ tương đồng đa sàn]

#### 2. Nguyên Nhân Gốc Rễ (Root Cause):
- [Giải thích các trường hợp gây nhiễu, ví dụ: tiêu đề tuyển dụng đặt quá chung chung]

#### 3. Giải Pháp Kỹ Thuật Đã Triển Khai (Solution Implemented):
- [Mô tả chi tiết luật 2 tầng và thuật toán Blocking Key + TF-IDF Cosine]

#### 4. Bằng Chứng Tự Kiểm Chứng (Verification Proof):
- Số lượng tin đưa vào kiểm tra: [...]
- Số tin giữ lại (Clean IT): [...] (Tỷ lệ: ...%)
- Số tin bị loại do ngoài IT: [...] | Do rỗng JD: [...]
- Số tin trùng lặp phát hiện (Deduped): [...] (Nội sàn: ..., Liên sàn: ...)

#### 5. Vấn Đề Còn Tồn Đọng (Remaining Issues / Blockers):
- [Ghi rõ nếu còn ca kiểm tra nào nghi vấn, hoặc ghi "Không còn"]
```
