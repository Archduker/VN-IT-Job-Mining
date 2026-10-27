# BÁO CÁO REVIEW KỸ THUẬT — Module Text & Skill Processing

> **Ngày:** 27/10/2026 · **Tác giả:** module Text & Skill Processing (Phát Nguyễn) · **Trạng thái:** bản review nội bộ, **chưa commit/push**
> **Phạm vi:** chỉ module Text & Skill Processing. Không đổi schema chung, không đổi pipeline tích hợp, không đổi salary/Khoa, không thiếu/tự mở rộng taxonomy, không tự phân loại IT/Non-IT.
> **Quy ước:** ✅ đã xác minh (đo/code/test) · 🟡 đề xuất/chưa ràng buộc · 🔴 chưa xác minh được / cần nhóm quyết.

---

## 1. Overview
- **Mục tiêu module:** chuẩn hóa văn bản + kỹ năng của bảng phẳng Integration phục vụ SD2 (12 Job Family) và SD3 (Skill Taxonomy ESCO), trong ranh giới Ironclad (docs 04).
- **Phạm vi phụ trách:** `preprocessing/normalization/` (trừ `cross_deduplicator.py` của Duy), `data/dictionaries/`, `tests/test_skill_processing.py`.
- **File chính:** `text_cleaner.py`, `taxonomy_mapper.py`, `skill_normalizer.py`, `skill_extractor.py`, 3 dictionary JSON.

## 2. Scope
Reviewed: Text Cleaning (A), Skill Normalization (B), Skill Extraction (C), Taxonomy Mapping (D), Location Normalization (rủi ro logic — đã sửa). Out-of-scope chỉ ghi nhận: salary parsing (Khoa), null-semantics/GenAI (Sơn), dedup (Duy), master pipeline (Thuận).

## 3. Implementation Summary
| Chức năng | Trạng thái |
|---|---|
| Text cleaning (HTML/bullet/emoji/control, title, city, is_remote) | ✅ hoàn thành + đã test |
| Taxonomy 12 JF + 6 seniority | ✅ hoàn thành; JF00 có vấn đề dữ liệu (§6) |
| Skill normalization ESCO 3 nhóm (exact/fuzzy/keep) | ✅ hoàn thành |
| Skill extraction boundary-aware | 🟡 code + test xong, **chưa bật** trong pipeline (chờ S-3) |
| Location normalization | ✅ **đã sửa lỗi logic 27/10** (`_WORD_NUMS`) |
| `apply_legacy_column_names()` (bridge) | 🟡 tồn tại, **chưa tích hợp**, chưa export (`__init__`/pipeline không gọi) |
| Non-IT filtering / đổi schema / đổi tên cột | ⛔ không thuộc phạm vi — để Pending |

## 4. Technical Review

### A. Text Cleaning ✅
- `clean_jd_text` = strip HTML → bullet-stitch → dọn emoji/control → nén whitespace; **delegate** html_cleaner/bullet_stitcher của Khoa (không copy) — `preprocessing/normalization/text_cleaner.py` (clean_jd_text, ~L120-145).
- `clean_job_title`: callback chỉ xóa ngoặc **chứa đúng nhãn địa danh** → giữ `(ReactJS/ NodeJS)`; bóc đuôi lương/`(Lương Khởi Điểm Từ 45M)`. Có test.
- ⚠️ Trùng lặp nhận diện: `normalize_seniority`/`classify_job_family` được import lại trong `text_cleaner` để giữ API cũ → chỉ là re-export, không logic đúp. ✅ Ghi nhận, không phải lỗi.

### B. Skill Normalization ✅
- 3 tầng deterministic: (1) exact alias với `normalize_skill_key` (nén `. - _`, giữ `/` → `C/C++`,`UI/UX` an toàn); (2) fuzzy ASCII ≥0.86, chặn từ <6 ký tự & >4 từ & không-ASCII (chống "giao tiếp tốt"~"giao tiếp"); (3) unmatched giữ nhãn. `match_one` short-circuit khi khớp cả tag nên `C/C++` không bị split. ✅ test.
- Dedup theo canonical; `esco_coverage_rate = matched/total_tag`.
- 🟡 **Phát hiện (không sửa):** alias `"PHP/MySQL"` (dict) map **cả tag → PHP**, **mất MySQL** (false negative). Là **modeling từ điển**, không crash; đề xuất tách alias hoặc split. Người quyết: Phát (khi bồi từ điển).
- 🔴 **Fuzzy chạy cả ở chế độ exact-tag** (skills_list), không chỉ JD — chấp nhận nhưng chưa đo FP riêng cho nhánh này.

### C. Skill Extraction 🟡 (chưa bật)
- `extract()`: inverted-index token-first → xác nhận regex **ranh giới từ**, **longest-alias-thắng + occupied-span** (`preprocessing/normalization/skill_extractor.py`, extract ~L147-177) — chặn `git` khớp trong `gitlab ci`, `java` trong `javascript`. ✅ test.
- `augment_record`: **chỉ** chạy khi `skills_standardized ≤ 2`; thêm `skills_extracted_from_jd`, `skills_source ∈ {tags,tags+jd,jd_scan,none}`; không sửa tag sàn. ✅ test.
- 🔴 **FP còn sót** (audit tay 30 mẫu phiên trước, single-annotator **~93,3%**): `CRM←"quản lý khách hàng"`, `Figma←"photoshop"`, `GDPR←"bảo mật dữ liệu"`, `Cyber Security←"bảo mật thông tin"` ở ngữ cảnh sai. Đã chặn 2 họ lớn (`soc`→SIEM, `sap`→ERP) qua `text_scan_blocklist`. FP còn lại là **giới hạn matching-cụm-từ, cần contextual rule** → **không tự sửa**, để Pending + khuyến nghị audit 2 người.
- ⚠️ **`esco_coverage_rate` không được tính lại** sau augment → cột này chỉ phản ánh tag gốc, **không** gồm skill trích từ JD. Ghi chú cho downstream; **chưa đổi** (quyết định ngữ nghĩa chờ Thuận/Sơn).
- ⚠️ **`skills_source`/`skills_extracted_from_jd` chưa xuất hiện trong output pipeline hiện hành** (vì augment chưa nối) → Sơn/Duy **chưa được đọc** 2 cột này.

### D. Taxonomy Mapping ✅ (dữ liệu cần bàn)
- `_kw_hit` khớp **ranh giới từ** (chống `java`⊂`javascript`, `ba`⊂`database`). Cascade hẹp→rộng. JF07 đặt trước JF06 nhưng bộ keyword rời nhau (data engineer→JF06, data analyst→JF07) ✅.
- `standardized_job_family` luôn trả 1 mã (0 crash); `standardized_seniority` 6 bậc + UNKNOWN.
- ⚠️ **Phân kỳ seniority:** `map_seniority_code` **có dùng** `raw_experience_text`, còn `normalize_seniority` (Phúc gọi trong run_staging) **không dùng** → cùng record có thể ra 2 kết quả. → Pending C.

## 5. Location Fix & Metrics (Before/After)
**Lỗi logic** tại `_norm_loc` `_WORD_NUMS`: dịch *mọi* "quận <từ-số>"→số giữa chuỗi ⇒ `"Quận Ba Đình"`→`"quan 3 dinh"`→**nhầm Hồ Chí Minh** (thực ra Hà Nội). Ảnh hưởng **dữ liệu phân tích** (SD4 + blocking Duy), không phải hiển thị.
**Sửa:** chỉ dịch khi từ-số ở **cuối chuỗi**; thêm alias `bac tu liem`; docstring `normalize_city` cập nhật.

| Số đo (cùng code hiện tại, **toàn bộ 9.824 record**, đơn vị = record, 1 primary_city/record) | Before | After |
|---|---:|---:|
| province_mapped (→34 canonical) | 9.425 | 9.425 |
| — exact full-name | 8.609 | 8.609 |
| — historical alias (tỉnh cũ) | 258 | 258 |
| — district/abbrev alias | 558 | 558 |
| special (Remote/Toàn quốc/Quốc tế) | 34 | 34 |
| unknown ("Không xác định", raw rỗng) | 301 | 301 |
| unmapped_raw (passthrough) | 64 | 64 |
| **Σ = 9.824** ✅ | ✅ | ✅ |
| **"Quận Ba Đình"→HCM (SAI)** | **20** | **0** ✅ |
| Hà Nội / Hồ Chí Minh | 4.007 / 4.135 | 4.048 / 4.088 |
| **province_mapping_rate** = mapped/9.824 | 95,94% | 95,94% |

**Giải thích khác biệt:** mapping_rate **không đổi** vì bản chất lỗi là **gán nhầm thành phố chứ không phải không map** — 41 record Ba Đình/Nam Từ Liêm/… chuyển HCM→HN, HCM−47/HN+41, tổng mapping giữ nguyên. Đây là minh chứng **mapping_rate ≠ accuracy**.
- **Multi-location:** 465 record có >1 địa danh → `primary_city` **collapse về 1** theo luật hiện hành = *alias dài nhất toàn chuỗi*, rồi `priority_hubs` (**không phải "tỉnh đầu tiên"** như docstring cũ — đã sửa docstring; đa địa danh vẫn giữ ở `working_locations_clean`).
- 🔴 **Accuracy toàn phần CHƯA xác minh** — mới chứng minh *lớp lỗi đã biết* (Ba Đình/Nam Từ Liêm) về 0; chưa kiểm định thủ công 558 record district-bucket + toàn bộ exact. Không được gọi mapping_rate là accuracy.

## 6. Testing Results
| Test suite | Total | Passed | Failed | Skipped | Ghi chú |
|---|---:|---:|---:|---:|---|
| `tests/test_skill_processing.py` | 60 | 60 | 0 | 0 | +2 method location 27/10 |
| Repo trong phạm vi môi trường (`--ignore` monitoring & integration_step) | 89 | 89 | 0 | 0 | 2 file ignore: thiếu `fastapi`, thiếu file integration local — **ngoài module** |
| `test_monitoring_api.py` | – | – | – | – | không chạy: ModuleNotFound fastapi (môi trường) |
| `test_integration_step.py` | 3 | 1 | 2 | 0 | fail vì **thiếu `data/integration/*` local** (môi trường); pre-existing, không thuộc module Phát |

## 7. Performance Benchmark (TASK 6)
**Phương pháp:** dữ liệu local `data/vietnamworks/raw/2026-10-16/raw_batch.json`, **931 records**, flatten trước (ngoài vùng đo), deep-copy mỗi run, **warm-up + 5 run**, `time.perf_counter`.
| Chuỗi (pure module, KHÔNG tính I/O) | Throughput |
|---|---|
| `process_record_text` (text) | ~1.359 rec/s |
| `process_record_skills` (ESCO) | ~167 rec/s ← **nút cổ chai** |
| `augment_record` (JD scan, chủ yếu skip vì std>2) | ~3.697 rec/s |
| **Chain đầy đủ (không extractor)** | **~182 rec/s** |
| **Chain đầy đủ (có extractor)** | **~181 rec/s** |
- End-to-end qua **R2 stream** ~108–172 rec/s — **báo riêng, không dùng** để kết luận throughput module (chi phối bởi network/Range-GET).
- **Giới hạn:** 1 máy dev, Python 3.14, **1 dataset 931 rec**, chưa đo trên TopDev (2.755, nhiều tag dài), chưa profile vì sao ESCO chậm (giả thuyết: vòng fuzzy `SequenceMatcher` O(index) cho mỗi tag unmatched — 🔴 chưa xác minh bằng profiler). SLA Thuận >100 rec/s: pure ~181 ✅ nhưng cần Thuận đo lại trong pipeline thật.
- **Không so sánh trực tiếp với benchmark cũ ~217 rec/s** (đo trên **300 rec, singleton warm** — mẫu số + phương pháp khác). Tài liệu này lấy **181–182 rec/s (931 rec, warm-up + 5 run)** làm số chuẩn.

## 8. Known Issues & Limitations
1. ✅ **Đã sửa:** location `_WORD_NUMS` cross-city (Ba Đình/Nam Từ Liêm).
2. 🟡 Skill extractor **chưa bật** trong pipeline; `skills_source`/`skills_extracted_from_jd` chưa vào output.
3. 🟡 residual FP cụm-từ (CRM/Figma/GDPR/Cyber) — cần contextual rule + audit 2 người; precision hiện single-annotator 93,3% 🔴.
4. 🟡 `esco_coverage_rate` không cập nhật sau augment.
5. 🟡 alias `"PHP/MySQL"` ăn mất MySQL (FN nhẹ).
6. 🔴 accuracy location toàn phần & accuracy ESCO chưa kiểm định độc lập.
7. ⚠️ `apply_legacy_column_names()` **dead code** (không caller/export).
8. ⚠️ 52,7% `JF00_OTHER_IT` (topdev 91,8%) — **không mặc định là Non-IT**.
9. ⚠️ **Thuật ngữ metric (H):** `province_mapping_rate` ≠ accuracy; `esco_coverage_rate` là trung bình theo-record trên tag gốc; `skills_unmatched` đếm **theo record** (không phải tỉ lệ skill). Không suy ra độ chính xác từ các tỉ lệ phủ/đủ này.

## 9. Pending Decisions — Cần nhóm thống nhất
Mỗi mục: Hiện trạng · Bằng chứng · Rủi ro · Đề xuất · Người quyết.

**A. IT vs NON-IT và JF00**
- Hiện trạng: JF00=5.181/9.824 (52,7%); topdev 2.529/2.755 (91,8%) — cao bất thường.
- Bằng chứng: title topdev JF00 gồm `Kế Toán`, `Chăm Sóc Khách Hàng`, `Marketing`… **và** cả IT chưa bắt từ (`Game Designer`, `Quản Trị Mạng` biến thể).
- Rủi ro: nếu coi JF00=Non-IT sẽ **xóa nhầm** IT; nếu giữ nguyên thì SD2 loãng.
- Đề xuất: mẫu JF00 theo từng nguồn (ưu tiên **TopDev**) để **EDA + chủ sàn** quyết; cân nhắc cột `job_scope` (IT/non-IT) đặt **trước** taxonomy. **Không tự lọc/xóa, không loại bỏ toàn bộ JF00.** → **Người quyết: chủ sàn TopDev = Sơn (theo TASKS.md §1) + Thuận; KHÔNG phải module Phát.**

**B. Canonical columns (`job_family` vs `standardized_job_family`; `job_seniority` vs `standardized_seniority`)**
- Hiện trạng: module Phát xuất `standardized_*`; pipeline Phúc dùng `job_family`/`job_seniority`.
- Bằng chứng: `run_staging` dòng 147/166 tự tính `job_family`/`job_seniority`; `apply_legacy_column_names` **không được gọi**, không export.
- Rủi ro: 2 tên cột song song, hoặc bridge vô hiệu.
- Đề xuất: Thuận chốt bộ tên **duy nhất** trong output contract; nếu dùng `standardized_*` thì bỏ `apply_legacy_column_names` hoặc export + nối vào `master_pipeline`. → **Thuận (+ Phúc).**

**C. Seniority logic & `raw_experience_text`**
- Hiện trạng: `map_seniority_code` dùng experience; `normalize_seniority`(Phúc gọi) không dùng.
- Rủi ro: **2 module phân loại cùng record ra kết quả khác nhau**.
- Đề xuất: thống nhất **1** hàm seniority duy nhất + 1 bộ đầu vào (`raw_seniority_text`,`job_title`,`raw_experience_text`). → **Phát + Phúc + Khoa** (Khoa sở hữu `min_experience_years` parse).

**D. Pipeline integration & output contract**
- Hiện trạng: interface `process_record_text`→`process_record_skills`(→`augment_record`) sẵn sàng nhưng chưa nối; extractor off.
- Đề xuất: Thuận quyết thứ tự + có bật `augment_record` + cách tiêu thụ `is_remote`/`skills_source`. → **Thuận.**

**E. Multi-location precedence**
- Hiện trạng: "alias dài nhất toàn chuỗi" rồi `priority_hubs`; đã **sửa docstring** cho khớp, **chưa đổi luật**.
- Rủi ro: "Hà Nội, Hồ Chí Minh" thắng do độ dài, không theo ngữ nghĩa primary.
- Đề xuất: nếu cần `primary+secondary_city` hoặc luật "tỉnh đầu tiên" → đổi có test. → **Thuận/EDA(SD4).**

**F. Bật `skill_extractor` mặc định**
- Cần precision ≥ ngưỡng do **2 người** audit + quyết `esco_coverage_rate` có tính skill-trích-hay-không. → **Phúc/Thuận/Sơn.**

## 10. Recommended Next Actions
- **Module tôi đã xong:** location fix + tests + re-measure; contract cập nhật; báo cáo này. Text/skill/taxonomy review xong: **không phát hiện thêm bug logic nào cần sửa trong phiên này** (các mục §8 còn lại là **limitation thiết kế / pending / future improvement**, KHÔNG phải bug đang chờ sửa — phân loại lại cho đúng ở §9).
- **Module tôi theo dõi:** (F) audit precision 2 người; bồi từ điển từ `skills_unmatched` (gồm `PHP/MySQL` split, `game designer`…); cân nhắc profiler ESCO bottleneck; cập nhật `esco_coverage_rate` sau augment nếu team muốn.
- **Thành viên khác quyết:** A (JF00/`job_scope`) — Sơn/Thuận/chủ sàn; B/C/D/E (tên cột, seniority, tích hợp, multi-loc) — Phúc/Thuận/Khoa.
- **Trước khi tích hợp:** Thuận chốt output contract đơn nhất → bật/đặt `augment_record` → chạy `test_master_pipeline`.

## 11. Files Changed
**Phiên 27/10 này (chỉ module):**
- `preprocessing/normalization/text_cleaner.py` — siết `_WORD_NUMS` (end-anchor), docstring `normalize_city`. (Lỗi location logic.)
- `data/dictionaries/vn_provinces.json` — +alias `bac tu liem` (v2.0.0 34 đơn vị đã dựng 26/10).
- `tests/test_skill_processing.py` — +2 method (T-B1..B5, multi-location precedence).
- `docs/preprocessing/normalization/01_text_skill_processing_contract.md` — §4.1 City + §3 `primary_city` + Phụ lục.
- `docs/preprocessing/normalization/02_text_skill_processing_review.md` — **file mới (báo cáo này)**.
**Không đổi:** code skill/taxonomy/extractor (chỉ review — không phát sinh bug phải sửa), pipeline Phúc, salary Khoa, missing/dedup, `.env*`. **Không commit/push.**
