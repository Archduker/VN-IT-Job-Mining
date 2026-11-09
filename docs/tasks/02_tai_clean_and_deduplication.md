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

**Trạng thái nghiệm thu (08/11):** *Đã hoàn thành phần triển khai và sửa lỗi; chờ nhãn kiểm định,
quyết định Q3 và duyệt Q5 để nghiệm thu.* Bốn điều kiện còn đóng đều nằm ngoài phạm vi code của Task
#2: (1) Q1 — mẫu **643 dòng / 0 nhãn**, hai chỉ tiêu ≥95% chưa đo được; (2) Q3 — lead chốt dùng
chuyên mục sàn hay nhóm nghề nội suy rồi thống nhất §2.4; (3) Q5 — chưa có kết luận duyệt Tinh
Vân/Nasani; (4) — đồng bộ ADR-04 với SPEC-05 (phạm vi `docs/spec`, của lead) rồi mới chạy snapshot
cuối, kiểm chứng và bàn giao PR. Integration và test ledger thuộc phạm vi khác, không tính ở đây.

- [x] HTML entity được giải mã trước parse; NFC trước regex boilerplate; giữ C#, C++, .NET, F#.
- [ ] Precision IT ≥95%: **chưa đóng** vì chưa có nhãn, không phải vì mã sai. Mẫu đã dựng lại 08/11: **643 dòng/0 nhãn**, trong đó **100 dòng tầng 1 dự đoán IT** chia theo sàn (nhóm trước đây chưa được đại diện trong mẫu). Policy chỉ chứa ghi chú tổng hợp; không dùng 331/339 hay 42/47 làm bằng chứng.
- [x] D2 chỉ loại canonical hash trùng; phân biệt cùng version với nội dung đổi nhưng version không tăng.
- [x] Winner ngang authority/độ đầy đủ giữ lần cào mới nhất; min/max ngày fusion so thời gian đã parse.
- [x] Repost của thành viên thua liên sàn đi theo master cuối trong `repost_records`.
- [x] CLI applied lẻ bị chặn; dry-run lẻ không đổi byte nào trong báo cáo chính.
- [x] Có kiểm thử pipeline cho đường nối bắc cầu và ngưỡng đúng bằng 0,85; không gán sẵn trạng thái bị loại.
- [ ] Xác nhận nghiệp vụ hai cặp biên Tinh Vân/Nasani và chính sách bắc cầu với lead.
- [ ] Lead nối Dedup vào Integration và chốt category IT gate theo SPEC-05.
- [ ] Đồng bộ `docs/spec/11_technical_decisions.md` (ADR-04 §3.2) với `docs/spec/05_preprocessing_spec.md` §3.2 mà lead đã chọn — hai tài liệu **đều đã push và vẫn mâu thuẫn** về blocking key và quy tắc ngưỡng (đo được ở §5.8.5, ghi PRE-14). Thuộc phạm vi `docs/spec` của lead; em không sửa và chưa đổi luật dedup.

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
  (Sau kiểm chứng và sửa tiếp 08/11: Clean 35 đạt, Dedup 55 đạt, xem §5.8.4.)
- Toàn bộ unit: 163 đạt, 2 lỗi ngoài phạm vi (thiếu vulture và Collection ledger merge
  status). Cập nhật sau kiểm chứng 08/11: **180 đạt, 1 lỗi** còn lại là test ledger
  `collection/` (Task #1), đã root-cause ở §5.8.4 và ghi `KNOWN_ISSUED.md` SCRAPE-17.
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

1. **Nhãn tay:** chưa có nhãn lịch sử đã khôi phục trên máy; R2 chưa kiểm tra trong lượt này. Mẫu mới **643 dòng, 0 nhãn** đã sẵn sàng cho lead gán — chi tiết §5.8.2. 331/339 và 42/47 chỉ là ghi chú lịch sử chưa xác minh lại; không suy ra precision IT.
2. **Category gate:** SPEC-05 §2.4 bắt "danh mục nghề nghiệp thuộc nhóm CNTT **và** ≥2 kỹ năng IT";
   `common/it_filter.py:86-95` thỏa cấu trúc đó nhưng vế thứ nhất **nội suy nhóm nghề từ tiêu đề +
   JD** (12 nhóm), không đọc `raw_category_text` của sàn. Số 842/dò từ khóa ở §5.8.1 đo trên trường
   chuyên mục, nên không mô tả quyết định thực tế của bộ lọc. Lead chốt nghĩa "danh mục" là chuyên
   mục sàn hay nhóm nghề nội suy (A/B/C ở §5.8.1, PRE-13); chưa đổi code hoặc SPEC.
3. **Integration:** vẫn đọc 01_clean, chưa nhận đầu ra loại 180 dòng của Dedup. Báo cáo Integration cũ ngày 03/11 có 5177 dòng; cần Hoàng/lead cập nhật đường đi và chạy lại.
4. **Mâu thuẫn đặc tả:** cả hai tài liệu **đã push và đang tracked trong HEAD** — ADR-04
   (`docs/spec/11_technical_decisions.md` §3.2 dòng 231, 233–236) ghi Jaccard title ≥0,8 VÀ
   cosine ≥0,75 với blocking không có `Title_Group`; SPEC-05 §3.2 ghi cosine ≥0,85 với blocking có
   `Title_Group`. Lead đã chọn SPEC-05 §3.2 và chấp nhận bắc cầu trong `traloi.md`, code làm theo
   đó, nhưng **chưa sửa ADR-04 cho khớp**; khác biệt hai luật đo được trên 196 cặp audit (§5.8.5,
   PRE-14). Không còn việc "nhận commit đặc tả" — chỉ còn việc anh thống nhất nội dung.
5. **Duyệt nghiệp vụ:** hai cặp biên Tinh Vân/Nasani và cùng pháp nhân cần xác nhận; nguyên tắc bắc cầu đã được lead chấp nhận; cosine cao không phải nhãn đúng.
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

### 5.8 Kiểm chứng lại 08/11/2026 theo `traloi.md`

#### 5.8.1 Q3 — số đo category và giới hạn của phép dò từ khóa

**Điều kiện category nằm trong đặc tả đã push, không phải đề xuất thăm dò.**
`docs/spec/05_preprocessing_spec.md` §2.4 (dòng 107–109, 113) ghi tầng 2 chỉ nhận tin IT khi
"danh mục nghề nghiệp thuộc nhóm Công nghệ thông tin **ĐỒNG THỜI** trích xuất được tối thiểu
$\ge 2$ kỹ năng IT chuẩn". Dòng 100 nêu lý do: sàn tổng hợp (Vieclam24h, CareerViet, TopCV) xếp
nhầm tin kế toán/nhân sự/telesale vào chuyên mục IT.
**Cách code hiện thực hóa điều kiện đó khác với trường mà script lead đo.**
`preprocessing/common/it_filter.py:86-95` (`classify_unknown`) trả `it` khi
`classify_job_family_rule(title, skills)` cho một nhóm nghề hợp lệ (12 nhóm, **suy từ tiêu đề +
JD**) **VÀ** `len(skills) >= MIN_JD_SKILLS (= 2)` — hàm này **không đọc** `raw_category_text`, tức
không dùng chuyên mục do sàn cấp. Vì thế: (i) không đúng khi nói code "bỏ quên vế category"; code
có vế tương đương nhưng bằng tín hiệu khác; và (ii) các số 101 rỗng / 313–431 không khớp ở dưới là
số của **trường chuyên mục sàn**, không mô tả quyết định thực tế của bộ lọc. Chênh lệch thật giữa
hai cách hiểu chỉ đo được sau khi có nhãn tay. Đặc tả viết "danh mục nghề nghiệp" mà không định
nghĩa trường nguồn, nên đây là điểm cần anh chốt ngữ nghĩa, không tự suy.

Đã chạy lại ba script chỉ đọc: `python count_category_tier2.py`,
`python drafts/audit_category_tier2_semantics.py`, `python drafts/probe_true_job_category.py`
(với `PYTHONPATH` là thư mục repo). Các tên nhãn “non-IT”, “category thật”, “VSIC” trong output
hai probe là tên do script đặt, **không phải nhãn tay hay xác nhận ngữ nghĩa**.

- Script lead: 842 tin tầng 2 dự đoán IT, 101 category rỗng, 310 khớp từ khóa, 431 không khớp.
- Theo sàn, thứ tự số là tổng / rỗng / khớp / không khớp:
  topcv 348/27/108/213; topdev 68/68/0/0; vietnamworks 196/0/71/125;
  careerviet 57/2/55/0; vieclam24h 47/0/42/5; itviec 52/4/0/48;
  glints 31/0/1/30; jobsgo 43/0/33/10.
- Regex mở rộng: 428 khớp, 313 không khớp, 101 rỗng. Chênh 118 gồm itviec 48,
  glints 26, topcv 17, vietnamworks 15, jobsgo 7, vieclam24h 5.
  Glints có 30 dòng không khớp từ điển ban đầu nhưng chỉ 26 dòng được regex mới nhận thêm.
- 414 = 101 + 313 là số bị loại **nếu dùng chính regex mở rộng này làm gate**;
  không phải số IT thật bị loại, cũng không phải kết quả tất yếu của SPEC-05.
  Regex còn bỏ sót Glints: System Analyst (2), Technical Manager (1), System Security (1).
  Do đó không thể gọi toàn bộ nhóm không khớp là non-IT.
- 366 chỉ là số khớp `VSIC_RE` (gồm các từ rộng như “tư vấn”, “thiết bị”), chưa xác minh mã VSIC.
- Probe tìm key đệ quy trả 669 có giá trị / 407 khớp / 262 không khớp / 173 không tìm thấy.
  **Không được gọi 669 là độ phủ ngành nghề đúng.** Đặc biệt CareerViet probe tìm `industry`
  chỉ thấy 2/57, trong khi flattener lấy breadcrumb/`Ngành nghề` có 55/57 category không rỗng.
  “Không tìm thấy key” không chứng minh dữ liệu thiếu ngành nghề.

Đối chiếu `preprocessing/integration/json_flattener.py`: CareerViet dòng 221 và 232–234
lấy “Ngành nghề”; Glints 294 ưu tiên `occupationalCategory`, fallback `industry`; ITviec 358
lấy `industry`; JobsGO 433 lấy `occupations`; TopCV 473 lấy `company_industry`;
Việc Làm 24h 655 lấy `industries`; VietnamWorks 745–754 lấy danh sách industries; TopDev
không gán category. Chỉ tên `company_industry` xác định rõ nguồn trường công ty; các tên
`industry`/`industries` khác cần đối chiếu schema nguồn. Rút lại khẳng định “5/8 sàn là ngành công ty”.

**Đề nghị lead chốt Q3 (ngữ nghĩa "danh mục nghề nghiệp" trước, rồi mới tới luật):**
(A) gate bằng chuyên mục sàn sau khi Integration chuẩn hóa trường này — cần Hoàng, vì
`raw_category_text` hiện chủ yếu là ngành công ty;
(B) giữ cách hiện tại (nhóm nghề suy từ tiêu đề + JD) và ghi rõ vào §2.4 rằng đặc tả cho phép tín
hiệu nội suy — rẻ, không đổi số bản ghi, nhưng cần anh xác nhận vì đặc tả đang nói "danh mục";
(C) chuyên mục chỉ là tín hiệu ưu tiên/điểm số, không dùng để loại.
Em chưa áp gate bằng regex thăm dò và chưa sửa SPEC/bộ lọc. Theo `traloi.md`, Tài giữ
`common/it_filter` nếu chọn gate; Hoàng hỗ trợ nếu cần bổ sung trường Integration.

#### 5.8.2 Q1 — mẫu và khoảng tin cậy

Đếm trực tiếp CSV review: **643 dòng, 0 nhãn, 100 dòng tầng 1 dự đoán IT**.
Tổng dòng / tầng 1 IT: topcv 109/29; topdev 84/4; vietnamworks 94/14;
careerviet 80/9; vieclam24h 84/4; itviec 48/18; glints 48/6; jobsgo 96/16.
Không gán nhãn tự động, không tạo lại mẫu trong lượt kiểm chứng này.

Đếm lại bằng `clean_source` + `level1_it_count` trên raw, chỉ dùng StepReport trong bộ nhớ:
4.469 tin tầng 1 dự đoán IT = topcv 1.369, topdev 162, vietnamworks 608, careerviet 396,
vieclam24h 138, itviec 843, glints 244, jobsgo 709. Đây là pool phân loại, không phải số
bản giữ cuối cùng sau toàn bộ Clean.

Mẫu gồm ba tầng có tỷ lệ lấy khác nhau: non_it tầng 1, mọi dự đoán tầng 2, IT tầng 1.
Mẫu cũ vẫn có dự đoán IT ở tầng 2; thiếu độ phủ tầng 1, **không phải mẫu số luôn bằng 0**.
`validation_metrics` báo tỷ lệ cộng dồn trên phần có nhãn và Wilson nhị thức tham khảo;
chưa hiệu chỉnh trọng số lấy mẫu hoặc thiếu phản hồi. Recall cộng dồn cũng chịu giới hạn này.
Ngoài ra dự đoán `non_it` không đồng nghĩa thực sự bị loại: `drop=[]` bỏ qua C4c.
Do đó `precision_non_it` trên mẫu chưa tự chứng minh yêu cầu “≥95% nhóm bị loại thật sự non-IT”.

Lead yêu cầu hai chỉ tiêu ≥95% **kèm khoảng tin cậy**, chưa quy định cận dưới phải ≥95%.
Đã bỏ kết luận tự động “ĐẠT ngưỡng” trong CLI; kể cả mẫu 100/100 cũng chưa tự đóng nghiệm thu.
Cần chốt dân số đánh giá, tổng hợp theo phân tầng/trọng số và quy tắc chấp nhận với lead;
gán riêng 100 tin tầng 1 không đủ đánh giá cả hai chỉ tiêu.

Đối chiếu số học Wilson (không phải bằng chứng chất lượng dữ liệu): 100/100 có cận dưới
96,30%; 99/100 là 94,55%; 196/200 là 94,97%; 197/200 là 95,68%; 200/200 là 98,12%.
Nếu lựa chọn thêm điều kiện cận dưới ≥95% cho một mẫu nhị thức thì 200 cần ít nhất 197 đúng.
Không suy rộng điều kiện đó cho thiết kế phân tầng hiện tại mà chưa chốt phương pháp.

Lệnh đọc tiến độ: `python -m preprocessing.clean.label_review --status`.
Lệnh tạo lại mẫu khi đã thống nhất: `python -m preprocessing.clean.run --resample-review --level1-it 200`.
`--source glints` nay chỉ tạo mẫu Glints, không âm thầm dựng cả tám sàn.
`--level1-it` âm hoặc dùng thiếu `--resample-review` trả exit 2 trước khi ghi.
Sàn đã có nhãn giữ nguyên; việc đổi quota khi đó không đảm bảo tổng mẫu đúng N.
Không có bằng chứng khôi phục nhãn lịch sử trong lượt này; chưa kiểm tra R2, không tuyên bố mất nhãn toàn dự án.

#### 5.8.3 Q4/Q2/Q5/Q6 — quyết định và việc còn chờ

- Q4: hai file chuẩn có trong HEAD `52abf35`; SPEC-05 §3.2 và ADR-04 còn mâu thuẫn về blocking/ngưỡng. **Lead đã chọn SPEC-05 §3.2 và chấp nhận bắc cầu trong `traloi.md`**, không hỏi lại chọn chuẩn. Cần nhận bản cập nhật ADR-04 và ghi chú bắc cầu mà lead nói đã sửa. Có file SPEC trong HEAD không chứng minh bản cập nhật ấy đã xuất bản. Lượt này không kiểm remote; không khẳng định trạng thái push. `git log --all` rỗng chỉ chứng minh không thấy trong các ref local đã có, không chứng minh chưa từng tracked trên mọi nhánh/server.
- Q2 đã chốt hướng Integration đọc envelope JSONL từng sàn ở `01b_deduplication` sau merge
  Task #2. Chưa sửa Integration; chưa tuyên bố pipeline cuối đã nối xong.
- Q5: lead/người đọc JD duyệt Tinh Vân và Nasani, chưa có nhãn quyết định; không chỉnh
  thuật toán vì chỉ hai cặp.
- Q6: giữ nguyên snapshot chung; chạy lại toàn chuỗi sau khi các điều kiện lead nêu được đáp ứng.
  Không commit, mở PR, ghi R2 hoặc tự điền nhãn trong lượt kiểm chứng này.

#### 5.8.4 Q7 — test và phạm vi kết luận

Đầu lượt tái hiện **176 passed, 1 failed**, Clean 31, Dedup 55; Ruff phạm vi sạch.
Sau sửa CLI và cách báo CI: **180 passed, 1 failed**, Clean 35, Dedup 55.
Test lỗi là `test_latest_status_change_wins_between_workers`, mong DONE nhận FAILED ở dòng 229.
Chạy riêng file ledger cũng có **9 passed, 1 failed**; không sửa Collection.
`test_report_code_quality.py` có 5 test đạt trong full suite; không còn lỗi vulture ở lượt này.
Môi trường chạy ghi trong log: Windows, Python 3.12.9, pytest 9.1.1.
Không suy ra mọi máy Windows đều fail hoặc rủi ro sản xuất thấp từ phép thử cục bộ.
Bằng chứng lead nói test pass trên nhánh khác là báo cáo của lead, chưa tự chạy nhánh đó.

Log kiểm chứng gồm `category.txt`, `semantics.txt`, `probe.txt`, `ledger.txt`, `units.txt`,
`ruff.txt`, `measurements.json` trong thư mục artifact `nov08_recheck` của phiên làm việc;
không ghi vào `reports/`. Các lệnh tái hiện tại §5.7 và §5.8.1. Hash các CSV review và
JSON report được so trước/sau để phát hiện thay đổi ngoài ý muốn.

#### 5.8.5 Kiểm chứng phép thử SPEC-05/ADR-04 và hồ sơ Q5

Chạy `python drafts/spec05_vs_adr04_impact.py`: đây là phép thử điều kiện trên điểm cosine
đã làm tròn trong audit hiện hành, dùng tokenizer riêng của probe (bỏ dấu, regex a-z0-9,
tập token). Không phải triển khai/chạy lại ADR-04; tokenizer này làm mất ký hiệu công nghệ.

- 131 dòng `dropped`: 131 đạt cosine ≥0,85; 81 đạt điều kiện kép của probe.
- 55 dòng `review-band`: 0 đạt cosine ≥0,85; 14 đạt điều kiện kép (27 job_id dạng chuỗi).
- 3 dòng `transitive-link`: 0 đạt cosine ≥0,85; 2 đạt điều kiện kép.
- **7 dòng `transitive-dropped` không được tính như điểm trực tiếp**: `run.py:173,310`
  ghi điểm `max(direct, via_score)` và `linked_via`. Ghép Jaccard hai tiêu đề với điểm qua
  trung gian để báo “7/3 đạt” là sai ngữ nghĩa. Đã loại khỏi phép thử trong script.

50 cạnh `dropped` không đạt điều kiện kép **không chứng minh 50 cặp sẽ tách cụm**: còn đường
bắc cầu, blocking thay đổi và TF-IDF cần tính lại. Tương tự 14 cạnh đạt không phải số bản ghi
sẽ được gộp thêm. Ví dụ AI Engineer cosine 0,998/Jaccard 0,714 chỉ minh họa sự khác biệt giữa
hai phép đo; chưa chứng minh toàn bộ 50 cạnh đều là cùng một tin.

Q5: đo lại bằng `python drafts/answer_dot2_open_items.py`, tra hồ sơ bằng URL + job_id,
không dùng job_id đơn lẻ xuyên sàn. Số cũ 3.929/2.807/2.701/3.211/1.984 là độ dài
`json.dumps(raw_payload, ensure_ascii=False)` **không phải độ dài JD**.
Độ dài `raw_description_text` do flattener trả về (chưa coi là toàn bộ nội dung yêu cầu/quyền lợi):

- Tinh Vân: topcv 2037957 = 826 ký tự; jobsgo 29325602191 = 382.
  Lương 20–27 triệu ở cả hai; kinh nghiệm 4 năm so với 3–4 năm.
- Nasani: topcv 2305027 = 448; topcv 2309755 = 444; jobsgo 29265583011 = 459 ký tự.
  TopCV 15–20 triệu, JobsGO 7–30 triệu; cả ba ghi không yêu cầu kinh nghiệm.
  Khoảng lương giao nhau; khác độ dài/lương chưa chứng minh hai vai trò khác nhau.
- Hai cạnh Nasani nối qua JobsGO có cosine 0,8909 và 0,8793. Dòng lineage từ TopCV 2309755
  về TopCV 2305027 mang `linked_via=29265583011`; **0,8793 không phải cosine trực tiếp
  giữa hai tin TopCV**. Nếu nhãn nghiệp vụ xác nhận khác vai trò thì cụm là ứng viên gộp nhầm;
  chưa đủ kết luận nguyên nhân chỉ do Union-Find hoặc không liên quan ngưỡng.

Cả ba cạnh trực tiếp được nêu không đạt Jaccard 0,80 theo tokenizer của probe
(0,143 / 0 / 0,235). **Chốt Q4 không giải quyết Q5**: tiêu chí thuật toán không phải nhãn
trùng thật; đồ thị ADR chưa được chạy lại. Người đọc JD vẫn phải duyệt.

Trong 55 review-band có **12 cặp cùng tập token** theo tokenizer của probe, cosine
0,765–0,8426; không phải “byte-identical titles”. Việc bỏ thứ tự/tần suất token và ký hiệu
C#/C++/.NET có thể xóa khác biệt quan trọng. Đây là nhóm nên bổ sung duyệt, chưa có bằng chứng
rủi ro dưới 0,85 lớn hơn dải 0,85–0,90. Rút đề xuất tự động merge bằng OR tiêu đề giống nhau.
Ví dụ cosine 0,8453 không nằm trong phạm vi 0,765–0,8426 nên không dùng làm ví dụ cho 12 cặp.

Wilson tham khảo đã tính lại: 100→100; 120→119; 150→148; 175→172; 200→197;
250→245; 300→293; 400→389. Không đổi phương pháp nghiệm thu đã nêu ở §5.8.2.

**Bằng chứng mới cho Q3, lấy từ chính năm tin ở bảng trên**
(`python drafts/measure_jd_field_lengths.py`, output `drafts/measure_jd_field_lengths.txt`):
giá trị `raw_category_text` do `flatten_raw_job_record` trả về cho cùng một cụm tin:

| Sàn:job_id | `raw_category_text` | Bản chất trường |
|---|---|---|
| topcv 2037957 | "Xuất bản phần mềm khác" | ngành công ty, kiểu VSIC |
| topcv 2305027 / 2309755 | "Lập trình máy tính khác" | ngành công ty, kiểu VSIC |
| jobsgo 29325602191 | "Lập Trình - Phát Triển Phần Mềm" | chuyên mục nghề |
| jobsgo 29265583011 | **"Sales Công Nghệ Thông Tin"** | chuyên mục nghề, thiên sales |

Hai sàn khác nhau **cấp độ ngữ nghĩa**, không chỉ khác từ điển: TopCV mô tả công ty, JobsGO mô tả vị trí.
Vì vậy gate cứng trên `raw_category_text` sẽ cắt/keep theo **từng sàn** chứ không theo nghiệp vụ:
tin Nasani bên JobsGO rơi vào nhóm Sales đúng loại mà §2.4 dòng 100 muốn chặn, nhưng hai tin TopCV
của cùng công ty thì "Lập trình máy tính khác" lại khớp từ điển IT. Đây là cứ liệu cho phương án
(B)/(C) ở §5.8.1, không phải bằng chứng rằng gate hiện tại sai — chưa có nhãn để đo chênh lệch thật.
