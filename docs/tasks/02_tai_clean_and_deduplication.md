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

- [x] **Bước 1 (Clean Logic):** Kiểm tra hàm bóc tách HTML và chuẩn hóa Unicode tiếng Việt, đảm bảo không làm mất các ký tự công nghệ quan trọng (ví dụ: `C#`, `C++`, `.NET`).
  *Bằng chứng:* unit test khẳng định `fold("Kỹ Sư .NET / C++ / C# - F#") == "ky su .net / c++ / c# - f#"` và `clean_text` xử lý `\u200b`, `\ufeff`, `\x07` mà không xóa `#`/`+`. 46/46 test xanh (mục 5.5). Đã kiểm thêm SPEC-05 mục 2.1.4: `strip_html` giải mã entity nên `&nbsp;`/`&#39;`/`&amp;` không còn lọt vào văn bản so sánh.
- [x] **Bước 2 (IT Filter Test):** Chạy thử bộ lọc IT trên tập 100 tin mẫu; đo độ chính xác (Precision) đạt $\ge 95\%$ trên nhãn thực tế.
  *Bằng chứng:* nhãn gán tay lưu vĩnh viễn trong `preprocessing/clean/it_policy.json` (duyệt 03/11, `approved_on`), tổng hợp từ 7 sàn có `drop=["non_it"]`: **331/339 = 97,6%** $\ge$ 95%. **Ngoại lệ:** riêng careerviet 42/47 = 89,4% (chưa đạt, xem mục 5.6.1). itviec `drop=[]` nên không có cặp precision nào, chỉ có ghi chú 21/22 tin mẫu là IT thực thụ. Bộ mẫu trên máy này (543 dòng) chưa được gán lại nên chưa tự tính được – xem mục 5.6.2.
- [x] **Bước 3 (Intra-source Dedup):** Kiểm tra việc lọc trùng cùng sàn qua `job_id` và CDC hash, đảm bảo không bị mất các tin có nội dung cập nhật mới.
  *Bằng chứng:* D2 chỉ bỏ khi hash của văn bản đã chuẩn hóa trùng 100% (54 dòng); 1.987 bước nhảy CDC được kiểm toán riêng (`extra.cdc`), 15 bước đổi nội dung nhưng không bump `version` được đẩy về Collection chứ **không** bị dedup xóa.
- [x] **Bước 4 (Inter-source Dedup):** Chạy thuật toán Blocking + TF-IDF Cosine trên tập dữ liệu đa sàn. Kiểm tra danh sách các cặp bài đăng có Cosine $\ge 0.85$ xem có đúng là tuyển cùng 1 vị trí của cùng công ty không.
  *Bằng chứng đã duyệt tay:* toàn bộ 9 bản ghi D4 + 12 cặp cosine cao nhất + 12 cặp thấp nhất trong nhóm bị loại + 3 cặp bắc cầu + cụm `ila_HCM_other` mới được đưa vào so sánh (xem 5.6.3). Kết luận: đúng công ty + đúng vị trí; **2 cặp biên** còn nghi vấn được ghi ở mục 5.6.3. 55 cặp review-band (0,752–0,845) cố ý không merge.
- [x] **Bước 5 (Tự kiểm chứng số liệu):** Xác thực phương trình bảo toàn:
  $$\text{Tổng tin đầu vào} = \text{Tin IT hợp lệ} + \text{Tin ngoài IT} + \text{Tin rỗng} + \text{Tin trùng lặp}$$
  *Bằng chứng:* `13.365 = 5.077 (Clean) + 8.288 (drop)` và `5.077 = 4.897 + 180`; `rows_conserved = true` trên cả 8/8 sàn ở cả hai bước (StepReport raise exception nếu phương trình sai, không ghi file).
- [x] **Bước 6 (Linting):** Chạy `ruff check preprocessing/clean/ preprocessing/deduplication/`. → `All checks passed!` (đã lint thêm cả `tests/unit/test_deduplication_step.py`).

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

---

## 5. BÁO CÁO NGHIỆM THU ĐÃ ĐIỀN (bản thật – dùng làm mô tả Pull Request)

- **Người thực hiện:** Phan Nhật Tài
- **Nhánh làm việc:** `feature/p1-clean-dedup` → merge destination `sprint/pipeline-delivery`
- **Thư mục can thiệp:** `preprocessing/clean/`, `preprocessing/deduplication/` (+ 1 file test `tests/unit/test_deduplication_step.py`)
- **Thời điểm nghiệm thu:** 07/11/2026 06:54 UTC (`generated_at` của `01b_deduplication/_all.json`), chế độ `applied`, đủ 8/8 sàn (`extra.partial_run = false`, `checks.notes` trống). Đây là bản chạy **sau** lượt audit ràng buộc lần 2; mọi số liệu dưới đây lấy từ chính hai file báo cáo này.
- **Nguồn số liệu duy nhất mà Monitoring đọc:** `reports/preprocessing/01_clean/_all.json`, `reports/preprocessing/01b_deduplication/_all.json`

### 5.1 Danh mục file bàn giao

| File | Trạng thái | Vai trò |
|:--|:--|:--|
| `preprocessing/deduplication/text_norm.py` | mới | Bóc HTML (BeautifulSoup + lxml), NFC, xóa ký tự điều khiển, lọc boilerplate, `fold()` bỏ dấu nhưng giữ `C# C++ .NET F#` |
| `preprocessing/deduplication/blocking.py` | mới | `company_slug`, `location_code` (HN/HCM/DN/BD/TN/na), `title_group`, `blocking_key` |
| `preprocessing/deduplication/intra_source.py` | mới | Lớp 1: `job_id` + canonical-JSON hash (D1/D2/D3) + kiểm toán chuỗi CDC |
| `preprocessing/deduplication/inter_source.py` | mới | Lớp 2: Blocking → TF-IDF `char_wb 3..5` → Cosine $\ge$ 0.85 → Union-Find bắc cầu → Golden Master UUIDv5 (D4/D5/D6) |
| `preprocessing/deduplication/run.py` | mới | Điều phối 8 sàn, ghi `golden_master_jobs.parquet/.jsonl`, `duplicates_audit.csv`, bảo toàn số liệu |
| `preprocessing/clean/run.py` | sửa | Thêm CLI `python -m preprocessing.clean.run --source ...` (trước đây chạy mà không làm gì) + cờ `partial_run` chống ghi đè `_all.json` khi chạy lẻ 1 sàn |
| `preprocessing/clean/label_review.py` | mới | Trợ lý gán nhãn tay bộ lọc IT (`--status` in Precision, `--source`, `--redo`); **không tự gán nhãn** |
| `tests/unit/test_deduplication_step.py` | mới | 46 test: text_norm (kèm HTML entity), blocking, CDC, cosine, fusion, quy tắc chọn bản ghi thắng của hai tầng, truy vết bản bị loại gián tiếp, bảo toàn số liệu, CLI, sandbox 2 sàn |

### 5.2 Vấn Đề Gặp Phải (Problems Encountered)

1. **Xung đột giữa Zero Information Loss và làm sạch văn bản:** hợp đồng bước 01 cấm sửa `raw_payload`, nên mọi chuẩn hóa HTML/Unicode chỉ được diễn ra *trong tầng so sánh* của dedup, không được ghi ngược vào dữ liệu.
2. **Bùng nổ không gian so sánh liên sàn:** 5.077 tin bước vào Dedup; so toàn bộ mọi cặp là $\binom{5077}{2} = 12.885.466$ cặp ($O(N^2)$), đặc tả SPEC-05 mục 3.2 nêu rõ đây là lý do phải có Blocking.
3. **Nhiễu văn bản đặc thù sàn VN:** boilerplate quảng cáo ("Tải ứng dụng...", "Cam kết bảo mật..."), bullet `"• \n"` của ITviec/JobsGO, `U+200B`, `U+FEFF`, `\x07`, và hai biến thể hoa/thường của cùng một tiêu đề ("Trưởng Nhóm Phát Triển Phần Mềm" vs "Trưởng nhóm Phát triển phần mềm").
4. **Công ty đăng template JD gần giống nhau cho nhiều vị trí** (nasani có cả loạt tin "Tư vấn triển khai phần mềm website") → cosine cao giả tạo giữa các tin **khác** vị trí; ngược lại cùng một vị trí nhưng hai sàn cắt HTML khác nhau khiến cosine tụt xuống sát dưới ngưỡng.
5. **Ba lỗi thật trong chính module của tôi** chỉ phát hiện được bằng cách *đo giá trị trả về*, không phát hiện được bằng cách đọc code:
   - `TITLE_GROUPS` chứa từ khóa **có dấu** ("trưởng nhóm", "kỹ sư cầu nối") trong khi `title_group()` đã `fold()` đầu vào về không dấu ⇒ 2 nhóm `manage`, `brse` là code chết, mọi trưởng nhóm bị gán `other`.
   - Regex boilerplate `[^\n]{0,60}` tham lam **nuốt tới 60 ký tự JD thật** nằm sau một câu quảng cáo ⇒ nội dung đưa vào TF-IDF bị mất chữ.
   - Nhánh `kind = "merged"` trong audit không bao giờ chạy (một cặp $\ge$ 0.85 luôn có đúng 1 dòng thua) ⇒ số học audit lệch.
6. **Sự cố vận hành:** một test thiếu fixture `sandbox` đã chạy thật và ghi đè `reports/preprocessing/01b_deduplication/_all.json` bằng kết quả dry-run 1 sàn (448→443) – tức trang Monitoring sẽ hiện số thiếu. Đã khôi phục bằng chạy lại `--source all` và chèn cơ chế phòng vệ.
7. **Bốn lỗi tìm được ở lượt audit ràng buộc lần 2 (07/11)**, đều là lỗi thật trên dữ liệu thật, đều đã sửa và đã chạy lại pipeline:
   - **Thiếu `html.unescape`** – SPEC-05 mục 2.1.4 yêu cầu giải mã entity trước khi parse nhưng `strip_html()` bỏ qua. Đo: **6/5.077 dòng** vẫn còn `&nbsp;`/`&#39;` trong văn bản đưa vào hash và TF-IDF (tức hai bản giống nhau vẫn ra hai hash khác nhau). Sau sửa: **0/5.077** (kiểm bằng cách quét mẫu `&(nbsp|amp|#\d+);` sau `clean_text`).
   - **`MIN_COMPANY_SLUG = 4` âm thầm bỏ sót bản trùng thật** – slug 3 ký tự bị loại khỏi so sánh liên sàn nên các công ty FPT/ILA/HCI/WIR không bao giờ được đối chiếu: đo được **5 block / 14 bản ghi** nằm ngoài vòng so sánh. Sau sửa (ngưỡng 3 + thêm điều kiện `same_company()`): **4 block / 12 bản ghi** đã được so, phát hiện thêm **1 cụm trùng thật** (`ila_HCM_other`: ILA Vietnam đăng cùng vị trí "Software Development Manager" trên cả VietnamWorks 2107147 lẫn TopDev 2133354/2141962, cosine 0,9146) ⇒ số loại tăng đúng 178 → 180 và số cụm 112 → 113.
   - **Chạy lẻ một sàn ghi đè tài nguyên toàn dự án** – `golden_master_jobs.*` và `duplicates_audit.csv` vẫn mang tên toàn dự án dù chỉ chứa dữ liệu một sàn. Đã thêm hậu tố `.partial` + CLI **từ chối** `applied` khi không đủ 8 sàn.
   - **Tie-break thời gian đi ngược chiều** – `pick_cross_winner()` cũ dùng `min(..., str(seen_at), ...)`, nghĩa là khi hai bản **cùng sàn và cùng độ đầy đủ** thì bản **cào cũ hơn** thắng, trái D2 và trái ý "giữ version mới nhất" của SPEC-05 mục 3.1. Đo: **3/113 cụm** thật sự chạm tie-break này và cả 3 đều đang giữ sai bản. Sau sửa: 0 cụm giữ bản không mới nhất; không cụm nào đổi sàn nên số dòng mỗi sàn không đổi.

### 5.3 Nguyên Nhân Gốc Rễ (Root Cause)

- **Tiêu đề chung chung** ("Nhân Viên IT", "Kỹ Sư IT", "Chuyên viên kỹ thuật") nên Tầng 1 không kết luận được, buộc phải xuống Tầng 2 đếm $\ge 2$ kỹ năng công nghệ trong JD; các sàn đa ngành (TopDev 2.552, JobsGO 787, Vieclam24h 475, TopCV 935 non_it) trả về hàng nghìn tin ngoài IT vì URL Discovery quét theo slug danh mục rộng.
- **Mọi lỗi ở 5.2 đều cùng một gốc:** giả định định dạng đầu vào thay vì đo hàm thật. Bài học: với pipeline text, mọi hằng số regex/từ khóa/ngưỡng phải được kiểm chứng bằng probe in giá trị trả về trên chính 5.077 dòng, không bằng ví dụ tự viết trong test.
- **Blocking key dung hòa 2 nguồn sai số** (tên công ty và chuỗi tỉnh tự do) nên `company_slug` phải bỏ hậu tố pháp nhân + bỏ dấu + bỏ ký tự đặc biệt, `location_code` quy về 6 mã; chỉ cần một nguồn thiếu tỉnh là key rơi vào `na` (ví dụ `lgcns_na_other`) ⇒ mất 1 chiều chặn, phải trông chờ cosine.
- **Không thể tăng cosine bằng cách bỏ Stop Word tiếng Việt**, vì bỏ stop word sẽ xóa luôn các từ phân biệt vị trí ("Junior" vs "Senior", "Hà Nội" vs "HCM").

### 5.4 Giải Pháp Kỹ Thuật Đã Triển Khai (Solution Implemented)

**a) Bộ lọc IT 2 tầng tất định, không LLM**
- Tầng 1 khớp từ khóa tiêu đề; Tầng 2 khớp $\ge 2$ kỹ năng trong JD cho các tiêu đề mơ hồ; kết quả ghi `it_rule` (it/non_it/unknown), `it_rule_level`, `it_status` vào `metadata.clean`.
- Quyết định xóa tin nằm ở **hợp đồng duyệt tay** `preprocessing/clean/it_policy.json`: sàn nào chưa được duyệt `drop` thì **không bỏ tin nào** (luật C4c). itviec `drop=[]` vì là nguồn chuyên IT ⇒ 15 tin non_it của itviec vẫn được giữ (C4a `flag`), không bị âm thầm xóa.

**b) Clean 7 luật bảo toàn `raw_payload`** C1 (giữ snapshot mới nhất mỗi `job_id`) → C2 (batch cũ đã có file riêng) → C3 (record test/thiếu `job_id`/`source_url`) → C4a/C4b/C4c (phân loại + mẫu gán nhãn + áp policy) → C5 (JD < 30 từ) → C6 (trùng trong sàn: company+title+tỉnh+tuần) → C7 (trùng khác sàn, ghi `also_on`).

**c) Lớp 1 – Nội sàn CDC (D1/D2/D3):** tách chuỗi phiên bản theo `job_id`, băm canonical JSON của phần nội dung; **chỉ bỏ khi hash của văn bản đã chuẩn hóa trùng 100%**. Bản giữ chọn theo thứ tự (số trường có giá trị, rồi `scraped_at` mới nhất, rồi `job_id`): đo trên 47 nhóm repost thì `filled()` **bằng nhau ở 100% nhóm** (vì nội dung đã trùng hash nên tập trường như nhau), nên trên thực tế bản cào mới nhất thắng ở cả 47/47 nhóm – đúng ý "giữ version mới nhất" của SPEC-05 mục 3.1. Chuỗi CDC bất thường không bị xóa mà được xuất sang `extra.cdc` cho Collection.

**d) Lớp 2 – Liên sàn (D4/D5/D6):**
- `blocking_key = Slug(Company)_LocationCode_TitleGroup` ⇒ 3.861 block; chỉ sinh cặp trong block có ≥ 2 sàn và slug công ty ≥ 3 ký tự, rồi TfidfVectorizer(`char_wb`, 3..5) tính cosine ⇒ **189 cặp** phải đo thực sự (131 cặp $\ge$ 0.85 + 58 cặp dưới ngưỡng để duyệt).
- D4: hash nội dung trùng 100% (không cần cosine). D5: cosine $\ge$ 0.85. Cặp dưới ngưỡng vẫn được ghi audit trong **review-band $0.75 \le \text{cosine} < 0.85$** → **giữ cả hai** bản, chờ người duyệt. (Review-band không phải một luật D riêng: luật **D6** là bước hợp nhất Golden Record, `flag`, đúng **113** bản giữ có `metadata.dedup.merged_from`, trùng khớp `extra.clusters = 113`).
- Gom cụm bắc cầu bằng Union-Find; bản giữ của cụm chọn theo (uy tín sàn, độ đầy đủ trường, **bản cào mới nhất**, `job_id`). Fusion Golden Master neo UUIDv5 theo `blocking_key|src:job_id`: tiêu đề theo thẩm quyền sàn (ITviec > TopDev > VietnamWorks > còn lại), công ty/JD dài nhất, kỹ năng lấy hợp $S_1 \cup S_2$, ưu tiên lương dạng số, `first_posted` min / `last_seen` max.

**e) Kiểm toán & an toàn số liệu:** `StepReport.check_conserved()` dựng exception nếu `input.rows ≠ output.rows + Σ dropped[].rows` ⇒ không ghi bất kỳ file nào; `extra.partial_run` + note trong `checks.notes` cảnh báo khi chạy lẻ một sàn, **cả hai CLI đều từ chối** `applied` khi không đủ 8 sàn (`parser.error`, exit 2) và tài nguyên chung mang hậu tố `.partial` để không đè bản đủ.

### 5.5 Bằng Chứng Tự Kiểm Chứng (Verification Proof)

**Phương trình bảo toàn (chế độ applied, đủ 8 sàn):**

$$13.365\,(raw) - 8.288\,(Clean\ drop) = 5.077 \qquad 5.077 - 180\,(Dedup\ drop) = 4.897$$

| Sàn | raw vào Clean | IT | non_it | Sau Clean | Sau Dedup |
|:--|--:|--:|--:|--:|--:|
| topcv | 2.749 | 1.739 | 935 | 1.561 | 1.550 |
| topdev | 3.890 | 230 | 2.552 | 227 | 225 |
| vietnamworks | 1.947 | 804 | 415 | 800 | 794 |
| careerviet | 660 | 453 | 189 | 448 | 424 |
| vieclam24h | 1.276 | 185 | 475 | 182 | 170 |
| itviec | 915 | 895 | 15 | 905 | 885 |
| glints | 331 | 275 | 56 | 271 | 270 |
| jobsgo | 1.597 | 753 | 787 | 683 | 579 |
| **Tổng** | **13.365** | **5.334** | **5.424** | **5.077** (37,99%) | **4.897** (96,45% của Clean) |

**Chi tiết số bị loại:**
- Clean: C1 1.987 | C2 616 | C3 4 | C4c 5.409 (ngoài IT theo policy) | C5 188 (JD < 30 từ) | C6 71 | C7 13 = **8.288**. Trong 5.424 tin non_it chỉ 5.409 bị bỏ vì 15 tin non_it của itviec được policy giữ lại.
- Dedup: **D2 54** (repost cùng sàn, hash trùng) | **D4 9** (trùng liên sàn hash 100%) | **D5 117** (cosine $\ge$ 0.85) = **180** (tỷ lệ khử trùng 3,55%). Nội sàn 54, liên sàn 126.
- Audit `duplicates_audit.csv`: **196 dòng** = 131 `dropped` (cosine 0,8544–1,0000) + 55 `review-band` (0,7519–0,8453) + 3 `transitive-link` (0,8059–0,8360) + 7 `transitive-dropped`. `pairs_audited` 189, `pairs_over_threshold` 131, `clusters` 113, `cross_platform_clusters` **113/113**, `blocking_blocks` 3.861, `golden_rows` 4.897.
- **Truy vết 100% bản bị loại:** 126 bản bị loại liên sàn, đo lại thấy **0 bản** không có dòng audit nào chiếu về đúng bản giữ của nó. 7 trường hợp phải ghi dòng riêng (4 bản chỉ nối gián tiếp A~B, B~C; 3 bản có cặp trực tiếp nhưng dưới 0.85), cột `linked_via` chỉ ra bản trung gian là cầu nối. Lưu ý CSV đếm theo **cặp** còn báo cáo đếm theo **bản ghi**, nên cột `rule` trong CSV là D4 8 / D5 123 (131 dòng) khác `rule_totals` D4 9 / D5 117 (126 bản) – không cộng trực tiếp hai số này được.
- Đối chiếu chéo trong Golden Master: phân bố `duplicate_count` = 4.784×1 + 104×2 + 7×3 + 1×4 + 1×6 ⇒ 4.897 bản giữ, tổng số bản được hợp = 5.023 = 4.897 + 126 ✓ khớp đúng số D4+D5. `master_id` duy nhất: 4.897/4.897.
- Hiệu quả Blocking: 189 cặp phải đo cosine thay vì $\binom{5077}{2} = 12.885.466$ cặp ($O(N^2) \rightarrow O(\sum N_k^2)$, giảm ~68.000 lần).
- CDC nội sàn (10.762 `job_id`, 1.974 chuỗi >1 phiên bản, 1.987 bước nhảy): 13 bước crawler hash không đổi, 23 bước canonical hash không đổi, **15 bước nội dung đổi nhưng không bump `version`**.
- **Đối chiếu baseline R2 staging:** output Clean khớp **từng dòng** với `staging/*/preprocessing/01_clean.jsonl` ở 7/8 sàn (`missing=0, extra=0`); riêng vietnamworks 800 vs 900 do R2 thiếu ~931 envelope VNW (blocker ở mục 5.6.8).
- Test & lint: `pytest tests/unit/test_deduplication_step.py` → **46 passed**; `pytest tests/unit` → **155 passed / 2 failed** (2 fail có sẵn, không thuộc phạm vi – xem mục 5.6.8); `ruff check preprocessing/clean preprocessing/deduplication tests/unit/test_deduplication_step.py` → **All checks passed!**
- **Bốn kiểm tra ràng buộc làm ở lượt audit lần 2** (mỗi cái đều đo trên 5.077 dòng thật, không suy luận từ code):
  - Entity HTML sau chuẩn hóa: **0/5.077** (trước sửa: 6). Số dòng `01_clean` *thô* còn mang entity là 1.410 – **đúng chủ đích**, vì hợp đồng bước 01 cấm sửa `raw_payload` (Zero Information Loss); entity chỉ bị loại ở tầng so sánh.
  - Block slug ngắn được so trở lại: **4 block / 12 bản ghi / 13 cặp** (`fpt_HN_other`, `hci_HN_other`, `ila_HCM_other`, `wir_HN_other`); 3/4 block không tìm ra trùng, block `ila` tìm ra 1 cụm thật. Block slug **rỗng** (`_HN_other`, 2 bản topcv+vieclam24h không có tên công ty) vẫn cố ý loại vì không có căn cứ nào để nói cùng công ty.
  - Hướng tie-break thời gian: 3/113 cụm chạm tie-break, sau sửa **0** cụm giữ bản không mới nhất, **0** cụm đổi sàn.
  - Rò rỉ C5 (JD < 30 từ lọt xuống dưới): đo lại = **0**, không có lỗi.

### 5.6 Vấn Đề Còn Tồn Đọng (Remaining Issues / Blockers)

1. **Precision của careerviet 89,4% (42/47) < ngưỡng 95%** – 5 tin IT thật bị xếp non_it (logistics/giáo viên/cơ khí đứng chung danh mục). Cộng dồn 7 sàn có policy `drop` vẫn **331/339 = 97,6%** nên bước 2 đạt ở cấp dự án, nhưng riêng sàn này chưa đạt. Cách xử lý: gán nhãn lại 71 tin mẫu rồi siết keyword cho careerviet: `python -m preprocessing.clean.label_review --source careerviet` rồi `--status`.
2. **Cột `nhan_tay` trên máy này đang trống cả 543 dòng** (80 topcv + 80 topdev + 80 vietnamworks + 80 vieclam24h + 80 jobsgo + 71 careerviet + 42 glints + 30 itviec; `extra.review.*.labeled = 0` ở cả 8 sàn). CSV mẫu bị tạo mới 07/11 vì `data/` nằm ngoài git. Con số 97,6% ở checklist lấy từ bằng chứng đã duyệt vĩnh viễn trong `it_policy.json` (03/11), **không** phải từ CSV hiện tại. Muốn `extra.review` tự tính thì phải gán nhãn lại bằng `label_review.py`.
3. **2 cặp biên nghi vẫn chưa đủ căn cứ tách:** `congnghephanmemtinhvan_HCM_backend` 0,8674 ("Nhân Viên Backend" vs "Backend Software Developer (C#/.NET)") và `congnghephanmemnasani_HCM_other` 0,8793 ("Nhân Viên Tư Vấn Công Nghệ Thông Tin Thu Nhập 15-20T" vs "Nhân Viên Tư Vấn Giải Pháp CNTT") đã bị gộp. Nếu lead thấy là 2 vị trí khác nhau thì cần nâng ngưỡng D5 hoặc thêm điều kiện khác biệt lương/kinh nghiệm.
4. **58 cặp dưới ngưỡng 0.85 vẫn được ghi audit** (`extra.audit_review_band = 58`), tách làm hai loại đã đo lại từ CSV: **55 dòng `review-band`** (cosine 0,7519–0,8453) cố ý **giữ cả hai bản**, và **3 dòng `transitive-link`** (0,8059–0,8360) – hai bản này dưới ngưỡng với nhau nhưng đã bị gộp *gián tiếp* qua bản trung gian. Trong 55 cặp giữ-cả-hai có cặp gần như chắc chắn trùng: `w2solution_HCM_dotnet` 0,8426 (hai tiêu đề chỉ khác khoảng trắng sau `(` và trước `,`), `canifa_HN_manage` 0,8148 (chỉ khác hoa/thường); ngược lại block `congnghephanmemnasani_HCM_other` có tới **20 cặp** vì công ty này phát hành JD template gần giống nhau cho nhiều vị trí, nên đa số là **không** trùng thật. Đây là đánh đổi có chủ đích: thà còn trùng còn hơn xóa nhầm tin thật.
5. **Phản hồi sang Collection (không phải lỗi Clean/Dedup):** 15 bước nhảy CDC đổi nội dung mà không bump `version`, 13 bước crawler hash không đổi, 23 bước canonical hash không đổi; topdev có chuỗi CDC dài bất thường (1.106 job_id nhiều phiên bản). Nếu `version` không đúng thì C1/D2 đang giữ snapshot sai lệch.
6. **Chất lượng tiêu đề ở đầu vào:** `fill_pct_in(job_title) = 99,9%`; ví dụ itviec `iso-27001` có title và description rỗng → bị C5 chặn, nên `fill_pct_out = 100%`. Không còn tin không tiêu đề lọt xuống Integration.
7. **Golden Master còn thiếu trường – nguyên nhân từ đầu vào, không phải từ dedup** (đo trực tiếp trên 4.897 dòng `golden_master_jobs.jsonl`, chế độ hợp nhất chỉ lấy được giá trị nào có ít nhất một sàn cung cấp):
   - `first_posted_at` rỗng **1.658** (33,9%) – crawler không lấy ngày đăng ở một số sàn;
   - `skills_extracted` rỗng **1.073** (21,9%) – thuộc phạm vi SD3 (LLM/NLP trích kỹ năng), không phải bước tôi;
   - `location` rỗng **117**, `salary_text` rỗng **20**; chỉ **2.223/4.897** dòng có `salary_source_platform` (tức lương dạng số);
   - `job_title`, `company_name`, `job_description` mỗi thứ chỉ **1** dòng rỗng → chứng minh không tin rỗng nào lọt qua C5/C3.
   Đề xuất: @Duy xử lý missing/outlier trên `first_posted_at` + lương; @Phát/@Khoa lo `skills_extracted`.
8. **Blocker liên quan đến người khác (cần lead xử lý):**
   - **Dedup chưa nằm trên đường đi của dữ liệu:** `preprocessing/integration/run.py` vẫn đọc `data/preprocessing/01_clean/` (nguyên văn `input.path` trong `_all.json`), nên **180 bản trùng** mà tôi vừa loại vẫn đang chảy xuống Integration → Mining. Cần @Hoàng Đ.N. đổi đường dẫn sang `01b_deduplication/golden_master_jobs.*` hoặc lead quyết định thứ tự bước trong pipeline.
   - **Bậc thang số liệu trên Monitoring đang lệch:** `reports/preprocessing/02_integration/_all.json` vẫn là bản chạy ngày **03/11/2026 17:12 UTC** với `input.rows = output.rows = 5.177`, trong khi Clean hiện tại xuất **5.077**. Trang Monitoring đọc `_all.json` của mỗi bước nên sẽ hiển thị Integration *nhiều hơn* Clean – không phải lỗi của 2 bước tôi giao.
   - **VietnamWorks thiếu ~100 `job_id` so với baseline staging** vì raw trên R2 không đủ (~931 envelope chưa đẩy lên) → Integration và Mining đang thiếu dữ liệu VNW. Đề xuất @Khoa cào bù và @Thuận đẩy raw lên R2.
   - `data/` bị `.gitignore`: toàn bộ `jsonl`, `golden_master_jobs.parquet`, `duplicates_audit.csv` **không lên git**; review số liệu phải mở `reports/preprocessing/**/*.json` hoặc kéo từ R2 staging.
   - 2 test fail có sẵn ngoài phạm vi tôi (đã tái hiện 07/11): `test_report_code_quality.py::test_vulture_does_not_flag_called_function` (thiếu package `vulture`) và `test_url_ledger_dedup.py::test_latest_status_change_wins_between_workers` (khu vực Collection).
9. **Không còn lỗi kỹ thuật tồn đọng trong 2 thư mục được giao**: pipeline chạy lại từ raw → golden master tái lập đúng số liệu trên, `rows_conserved = true` trên 8/8 sàn ở cả hai bước, lint sạch, 46/46 test của bước này xanh. Lượt audit ràng buộc lần 2 đã đóng 4 lỗi thật (mục 5.2.7) **và** 1 lỗ hổng truy vết (mục 5.5: 126/126 bản bị loại liên sàn đều truy vết được về bản giữ).

### 5.7 Lệnh tái hiện (PowerShell)

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m preprocessing.clean.run --source all              # 13.365 -> 5.077
python -m preprocessing.deduplication.run --source all      # 5.077 -> 4.897
python -m preprocessing.deduplication.run --source glints --dry-run   # thử 1 sàn, không ghi dữ liệu
python -m preprocessing.clean.label_review --status          # xem Precision từng sàn + cộng dồn
python -m pytest tests/unit/test_deduplication_step.py -q    # 46 passed
python -m pytest tests/unit -q                               # 155 passed / 2 failed (xem 5.6.8)
python -m ruff check preprocessing/clean preprocessing/deduplication tests/unit/test_deduplication_step.py
```

Lưu ý vận hành (thêm từ lượt audit lần 2): chạy lẻ một sàn **mà không kèm** `--dry-run` thì cả hai CLI **từ chối** với `exit 2` (`parser.error`) để không ghi đè `_all.json`/golden master toàn dự án; muốn chạy lẻ phục vụ debug thì bắt buộc kèm `--dry-run` (tài nguyên chung lúc đó mang hậu tố `.partial`).

