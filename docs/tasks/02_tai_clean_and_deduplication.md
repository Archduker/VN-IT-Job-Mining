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
   - *Tầng 2 (Context Filter):* Nếu tiêu đề chưa rõ ràng (ví dụ: "Nhân viên kỹ thuật"), kiểm tra category IT **VÀ** quét nội dung JD; yêu cầu bài đăng chứa ít nhất $\ge 2$ kỹ năng công nghệ IT chuẩn từ bộ từ điển.
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

## 3. Checklist sau phản biện độc lập

- [x] HTML entity được giải mã trước parse; NFC trước regex boilerplate; giữ C#, C++, .NET, F#.
- [ ] Precision IT ≥95%: **chưa kiểm chứng**. CSV hiện có 0/543 nhãn. Policy chỉ chứa ghi chú tổng hợp; không dùng 331/339 làm bằng chứng precision IT.
- [x] D2 chỉ loại canonical hash trùng; phân biệt cùng version với nội dung đổi nhưng version không tăng.
- [x] Winner ngang authority/độ đầy đủ giữ lần cào mới nhất; min/max ngày fusion so thời gian đã parse.
- [x] Repost của thành viên thua liên sàn đi theo master cuối trong `repost_records`.
- [x] CLI applied lẻ bị chặn; dry-run lẻ không đổi byte nào trong báo cáo chính.
- [x] Có kiểm thử pipeline cho đường nối bắc cầu và ngưỡng đúng bằng 0,85; không gán sẵn trạng thái bị loại.
- [ ] Xác nhận nghiệp vụ hai cặp biên Tinh Vân/Nasani và chính sách bắc cầu với lead.
- [ ] Lead nối Dedup vào Integration và chốt category IT gate theo SPEC-05.

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

## 5. Bàn giao sau phản biện ngày 07/11/2026

### 5.1 Phạm vi và trạng thái

Sửa trong `preprocessing/clean/`, `preprocessing/deduplication/`,
`tests/unit/test_deduplication_step.py` và tài liệu này. Không sửa raw, Integration,
common/it_filter, orchestrator, báo cáo chính của thành viên khác hoặc AGENTS.md.
Không upload R2 và không bật scheduler.

Các JSON đã commit trong `reports/preprocessing/01_clean/` và `01b_deduplication/`
là **snapshot lịch sử f693b30**, không phải kết quả chạy mã đã sửa. Đặc biệt số
`hop_version_not_bumped=15` ở snapshot cũ có định nghĩa sai. Chạy lệnh kiểm chứng
ở §5.7 để tạo báo cáo mới vào thư mục riêng. Bằng chứng có SHA-256 mã nguồn;
chỉ `code_version` Git không đủ nhận diện mã đang có thay đổi chưa commit.

### 5.2 Số liệu baseline được kiểm độc lập

Tái chạy raw local của snapshot f693b30 cho kết quả:

| Sàn | Raw | IT trước drop | non_IT trước drop | Clean | Dedup |
|---|---:|---:|---:|---:|---:|
| topcv | 2749 | 1739 | 935 | 1561 | 1550 |
| topdev | 3890 | 230 | 2552 | 227 | 225 |
| vietnamworks | 1947 | 804 | 415 | 800 | 794 |
| careerviet | 660 | 453 | 189 | 448 | 424 |
| vieclam24h | 1276 | 185 | 475 | 182 | 170 |
| itviec | 915 | 895 | 15 | 905 | 885 |
| glints | 331 | 275 | 56 | 271 | 270 |
| jobsgo | 1597 | 753 | 787 | 683 | 579 |
| Tổng | 13365 | 5334 | 5424 | 5077 | 4897 |

- Clean: C1=1987, C2=616, C3=4, C4c=5409, C5=188, C6=71, C7=13; tổng 8288.
- Dedup: D2=54, D4=9, D5=117; tổng 180, tỷ lệ 180/5077=3,5454%.
- Bảo toàn ở cả 8 sàn của mỗi bước; Golden Master có 4897 ID duy nhất.
- `duplicate_count`: 4784×1 + 104×2 + 7×3 + 1×4 + 1×6; tổng 5023, **chưa bao gồm 54 repost D2**.
- 113 cụm liên sàn; 126 bản loại liên sàn có đường truy vết về bản giữ.
- CSV 196 dòng/12 cột: 131 dropped, 55 review-band, 3 transitive-link, 7 transitive-dropped.
- Cosine theo nhóm: dropped 0,8544–1; review-band 0,7519–0,8453; transitive-link 0,8059–0,8360.
- D4/D5 trong CSV là 8/123 cặp; D4/D5 trong report là 9/117 bản ghi. Không cộng trực tiếp.
- 47 nhóm D2 có độ đầy đủ bằng nhau; 3 cụm liên sàn chạm tie-break; không giữ sai thời gian khi ngang tiêu chí trước.
- 0/5077 dòng còn regex `&(nbsp|amp|#\d+);` sau chuẩn hóa các TEXT_FIELDS. Cùng regex trên raw_payload cho 1391 dòng; raw được giữ nguyên.
- ITviec có 15 non_IT trước C5, 0 bị C4c loại, 4 bị C5 loại vì 0 từ; còn 11 ở output Clean. `drop=[]` không vô hiệu hóa các luật chất lượng khác.
- Golden Master thiếu first_posted_at=1658, skills=1073, location=117, salary_text=20; title/company/description mỗi trường 1; salary_source_platform có giá trị ở 2223 dòng.
- Có tin `careerviet:35C8A80A` thiếu tiêu đề. Tỷ lệ làm tròn 100% không chứng minh mọi dòng có title.

### 5.3 Định nghĩa chỉ số đã sửa

- `pairs_audited` = số cặp lưu audit (baseline 189), không phải số phép tính cosine.
- `cosine_pairs_computed` = tổng n(n−1)/2 trong các ma trận đã tính; không gồm đường chéo, mỗi cặp tính một lần (baseline đo độc lập 2811).
- `cosine_blocks` = số ma trận thực sự được tính (baseline 219).
- `cross_pairs_evaluated` = số cặp khác sàn qua gate tên công ty, trước ngưỡng audit.
- `blocking_blocks` giữ nghĩa cũ: tổng số block riêng từng sàn (3861). `blocking_unique_blocks` là số key duy nhất sau D2 (baseline 3627).
- C(5077,2)=12885426; bỏ tuyên bố tốc độ tăng 68000 lần vì lấy số cặp audit làm mẫu số là sai.
- `hop_same_version` đếm mọi bước cùng version. `hop_version_not_bumped` đếm cùng version **và canonical hash thay đổi**. Hai trường không đồng nghĩa.
- Raw baseline: 10762 job_id, 1974 chuỗi nhiều snapshot, 1987 bước; crawler hash không đổi=13, canonical hash không đổi=23. Trong 15 bước cùng version, 9 raw payload giống hệt; chỉ 6 đổi raw payload và 5 đổi canonical hash.
- `lineage_rows` = tổng duplicate_count + tổng repost_records. Phải bằng input Clean và mỗi `(source, job_id)` phải có đúng một master cuối.
- `unparsed_dates` giữ giá trị ngày không parse được; không đưa chuỗi tương đối hoặc sai định dạng vào min/max.

### 5.4 Nhật ký sửa lỗi B1–B8

Các mục dưới đây theo khuôn Lỗi → Nguyên nhân → Xử lý → Kiểm chứng. Lead cần
chuyển sang mã L-tiếp-theo trong `docs/issue_log.md`; file đó và KNOWN_ISSUED.md
ngoài phạm vi sửa của Tài nên không tự cấp mã/xóa mục của người khác.

1. **B1 — Báo cáo chạy lẻ ghi đè snapshot:** `.partial` mới áp dụng audit/master, chưa áp dụng report → dry-run lẻ ghi sang `reports/preprocessing/_partial/<step>/` → test so byte của tất cả báo cáo chính trước/sau, cho cả Clean và Dedup.
2. **B2 — first_posted sai:** sort chuỗi DD/MM/YYYY lẫn ISO → parse ngày, quy timestamp không offset về +07 và so UTC; giữ nguyên biểu diễn ngày được chọn, giữ ngày không parse được riêng → test khác tháng, ISO/DD/MM, timezone và ngày không hợp lệ. Review baseline tìm 7 cụm sai.
3. **B3 — Mất 3 repost qua hai tầng:** D2 winner thua liên sàn không truyền reposts → Golden Master và metadata bản giữ hợp `repost_records` từ toàn cụm, có source/job_id/url/hash → test loser có repost; kiểm mỗi input có đúng một tham chiếu cuối.
4. **B4 — CDC báo sai 15 vi phạm:** chỉ kiểm version bằng nhau → tách hop_same_version và yêu cầu canonical hash khác cho vi phạm → test hai lần cào không đổi cùng version không bị đếm sai.
5. **B5 — Precision chưa có nhãn:** dùng ghi chú policy thay dữ liệu nhãn và trộn lớp IT/non_IT → bỏ đánh dấu nghiệm thu; công cụ hiển thị TP/FP/TN/FN, precision IT, precision non_IT, recall IT. Không mẫu hợp lệ trả null/NO_LABELS. **Chưa đóng điều kiện precision ≥95%.**
6. **B6 — Boilerplate phụ thuộc Unicode:** regex chạy trước NFC → đưa NFC lên trước → test cùng văn bản NFC/NFD.
7. **B7 — Sai cách diễn giải số:** nhầm cặp audit với cặp tính cosine, block toàn cục với tổng block từng sàn, non_IT trước/sau C5 → thêm counters riêng và đính chính §5.2–5.3.
8. **B8 — Test bắc cầu dựng sẵn drop:** writer test không kiểm thuật toán → test pipeline với A–B=0,85; B–C=0,9; A–C=0,8, kiểm master và transitive-dropped. Điểm trong test là fixture kiểm biên, không phải số đo dữ liệu sản xuất.

Các bẫy được lưu thêm trong CLAUDE.md của hai thư mục Clean/Dedup.

### 5.5 Kiểm thử và bằng chứng

- 54 test tại `tests/unit/test_deduplication_step.py` đạt; cùng 20 test Clean = 74 đạt.
- Toàn bộ unit: 163 đạt, 2 lỗi ngoài phạm vi (thiếu vulture và Collection ledger merge status).
- Ruff phạm vi Clean/Dedup/test riêng sạch.
- Bộ kiểm chứng `python -m preprocessing.deduplication.verify_delivery` tái chạy vào thư mục mới, giữ báo cáo gốc; kiểm bảo toàn, lineage đúng một lần, ngày đầu tiên và báo cáo dry-run lẻ.
- Không coi ghi chú policy là tập nhãn, không tự gán nhãn để đạt precision.

Kết quả chạy dữ liệu thật sau sửa (07/11/2026): 13365 → 5077 → 4897;
54 repost xuất hiện trong lineage cuối; 5077 tham chiếu đầu vào ánh xạ đúng một lần.
7 first_posted_at thay đổi so snapshot cũ, 0 sai min ngày và 0 giá trị ngày không parse được.
Cả hai bước giữ nguyên byte của báo cáo chính sau dry-run Glints.
CDC: hop_same_version=15, hop_version_not_bumped=5 theo canonical hash.
Counters runtime: 219 ma trận, 2811 cặp không thứ tự, 1362 cặp khác sàn qua gate,
189 cặp lưu audit; blocking_unique_blocks=3627. Báo cáo gốc trong repo giữ nguyên.


### 5.6 Việc còn mở / kiến nghị cross-member

1. **Nhãn tay:** CSV hiện tại 0/543 nhãn; cần dữ liệu theo job_id, predicted label, human label, người duyệt/ngày duyệt. 331/339 và 42/47 chỉ là ghi chú lịch sử chưa xác minh lại; không suy ra precision IT.
2. **Category gate:** common/it_filter suy family từ title/skills, chưa kiểm category IT từ nguồn AND ≥2 skills như SPEC-05. Lead phối hợp owner common; không sửa lén trong Task #2.
3. **Integration:** vẫn đọc 01_clean, chưa nhận đầu ra loại 180 dòng của Dedup. Báo cáo Integration cũ ngày 03/11 có 5177 dòng; cần Hoàng/lead cập nhật đường đi và chạy lại.
4. **Mâu thuẫn đặc tả:** ADR-04 mô tả Jaccard title≥0,8 và cosine≥0,75; SPEC-05 dùng cosine≥0,85. Lead chốt tài liệu ưu tiên.
5. **Duyệt nghiệp vụ:** hai cặp biên Tinh Vân/Nasani, quan hệ bắc cầu và cùng pháp nhân cần xác nhận; cosine cao không phải nhãn đúng.
6. **R2:** thiếu ~931 envelope VNW và khớp staging 7/8 là thông tin lịch sử chưa đo lại trong lần sửa này.
7. **API Clean:** giữ hợp đồng run(sources,dry_run) cho orchestrator tập nguồn tùy chọn. CLI chặn applied lẻ; người gọi API applied vẫn phải tự cung cấp tập nguồn đầy đủ. Không dùng API applied lẻ để debug.
8. **Snapshot chính:** báo cáo/data cũ chưa được thay thế trong phạm vi này; lead chọn xuất bản lần chạy mới sau khi nghiệm thu. Raw bất biến.

### 5.7 Lệnh tái hiện

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
python -m pytest tests/unit/test_deduplication_step.py tests/unit/test_clean_step.py -q
python -m pytest tests/unit -q
python -m ruff check preprocessing/clean preprocessing/deduplication tests/unit/test_deduplication_step.py
python -m preprocessing.clean.label_review --status
# Dùng đường dẫn CHƯA tồn tại, được phép ghi; không trỏ tới reports/ hay data/raw.
python -m preprocessing.deduplication.verify_delivery --output-dir <thu-muc-moi>
```

Kết quả kiểm chứng: `<thu-muc-moi>/verification.json`, `reports/`,
`01_clean/`, `01b_deduplication/`; báo cáo chạy lẻ nằm dưới `reports/_partial/`.
Không cần sync R2 nếu raw local đã đủ. Không chạy lệnh upload/apply/push lên R2.
