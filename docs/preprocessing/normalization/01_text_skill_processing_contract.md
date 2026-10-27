# MODULE CONTRACT — TEXT & SKILL PROCESSING (Giai đoạn 3, Bước 3) · **BẢN DRAFT CHỜ DUYỆT**

> **Trạng thái:** 🟡 DRAFT — chủ soạn thảo: Phát Nguyễn (module Text & Skill Processing). **Chưa phải contract ràng buộc.** Cần Phúc (Integration Lead — xác nhận input) và Thuận (Pipeline Owner — xác nhận output/interface) review. Chưa tạo PR.
> **Căn cứ quy định:** `TASKS.md` §6.1 (Bước 3), §6.3.3 (nhiệm vụ + DoD), §6.2 (ma trận phân công); code hiện hành tại `preprocessing/normalization/`; dữ liệu thực tế `integration/` trên Cloudflare R2 (audit read-only 26/10/2026).
> **Ký hiệu:** ✅ = đã xác minh (đo/code/git) · 🟡 = quy tắc đề xuất (chưa ràng buộc) · 🔴 = chưa thống nhất, chờ quyết định.

---

## 1. Scope

**Mục tiêu (theo TASKS.md §6.3.3):** chuẩn hóa văn bản và kỹ năng của bảng phẳng Integration thành cột dùng chung phục vụ SD2 (12 Job Family) và SD3 (Skill Taxonomy ESCO), trong ranh giới Ironclad Boundaries của `docs/preprocessing/normalization/04_scaling_and_taxonomy.md` §1.

**Trách nhiệm của module:**

| Việc | Module/file chịu trách nhiệm | Trạng thái code ✅ |
|---|---|---|
| Làm sạch JD/requirements (HTML, bullet fragmentation, emoji, control chars) | `preprocessing/normalization/text_cleaner.py::clean_jd_text` (delegate strip-html & stitch sang module Khoa) | Đã có, đã test |
| Làm sạch tiêu đề (tag địa danh, đuôi quảng cáo lương) | `text_cleaner.py::clean_job_title` | Đã có, đã test |
| Chuẩn hóa địa danh (tỉnh/thành) + cờ `is_remote` | `text_cleaner.py::normalize_city`, `detect_remote`, `normalize_work_locations` | Đã có, đã test |
| Taxonomy 12 Job Family (SD2) + 6 Seniority | `taxonomy_mapper.py::classify_job_family`, `standardized_seniority` | Đã có, đã test |
| Chuẩn hóa kỹ năng ESCO 3 nhóm (SD3) + từ điển | `skill_normalizer.py::normalize_skills` + `data/dictionaries/esco_it_skills.json` | Đã có, đã test |
| API cấp bản ghi cho pipeline | `process_record_text()`, `process_record_skills()`, `normalize_dataframe()` | Đã có, đã test |

**Ngoài phạm vi (không thuộc module):**
- Parsing lương/kinh nghiệm/date số học → **Khoa** (Transformation).
- Bóc null marker trá hình & GenAI imputation → **Sơn** (Missing).
- Dedup cross-sàn, record linkage → **Duy**; ghép pipeline & SLA → **Thuận**.
- Thuật toán `html_cleaner`/`bullet_stitcher`/`text_metrics` gốc thuộc **Khoa** (WBS docs 01 §5 Bước 2) — module này **tiêu thụ**, không sở hữu, không copy.

**🔴 PENDING S-1 — Chính sách 2.B (dịch EN→VI):** `docs/preprocessing/integration/01_text_features_...md` §5 đặt "Chính sách 2.B" ở **Bước 4 (normalization = module Phát)**, nhưng implementation hiện nằm ở `transformation/text_metrics.py::standardize_to_vietnamese` (**Khoa**, từ điển 23 thuật ngữ, chưa gọi từ pipeline). Module Phát hiện **không** chứa logic dịch thuật. Cần chốt: (a) giao Khoa giữ nguyên, hay (b) Phát gọi hàm của Khoa trong `process_record_text` và đổi tên cột output tương ứng.

---

## 2. Input Contract

Module đọc **9 trên 29 cột** của tầng Integration flat (physical schema 29 key — ✅ verified toàn bộ 9.824 record/8 nguồn qua `scripts/audit_r2_integration_keys.py`; lưu ý tài liệu nhãn lệch: TASKS.md ghi "20 cột", docstring code ghi "25 trường" — 🔴 xem P-1 §5). Module **chỉ đọc**, không mutate cột input (🟡 theo nguyên tắc "CẤM ghi đè nhãn gốc", docs 04 §1).

| Trường input | Kiểu ✅ | Trống\* | Ý nghĩa & cách module xử lý khi thiếu |
|---|---|---:|---|
| `job_title` | str\|null | 0,13% | Tiêu đề thô → `clean_job_title` + đầu vào taxonomy (family/seniority). null → title_clean=null, family vẫn trả `JF00_OTHER_IT` (hàm không crash ✅ test) |
| `raw_location_text` | str\|null | 3,1% | Địa điểm header → `primary_city`, `detect_remote`. null → `"Không xác định"` |
| `working_locations` | list | 4,3% `[]` | Danh sách chi nhánh (dict/str lai) → `normalize_work_locations` ép `list[str]` tỉnh chuẩn |
| `raw_work_mode` | str\|null | **77,4%** | Chế độ onsite/remote — **chỉ Glints/TopCV có**; module không phụ thuộc đơn nguồn này (cascade 3 nguồn trong `detect_remote`) |
| `raw_seniority_text` | str\|null | **39,3%** | Cấp bậc declared; null **100%** ở glints/itviec/topdev → module tự suy từ title + experience (🟡 quy tắc này được sinh ra do verified gap, cần Phúc xác nhận chấp nhận) |
| `raw_experience_text` | str\|null | 33,2% | Chuỗi kinh nghiệm thô → fallback suy seniority (regex `N năm`). null → bỏ qua fallback |
| `skills_list` | list[str] | 17,8% `[]` | Thẻ kỹ năng gốc (TopDev thiếu 55,5%) → vào `normalize_skills`. `[]` → output skills rỗng (không crash) |
| `raw_description_text` | str\|null | 3,4% | JD thô (một số sàn còn HTML — TopDev 100% theo docs 01) → `clean_jd_text` |
| `raw_requirements_text` | str\|null | 3,6% | Yêu cầu thô → `clean_jd_text` |

\* Quy ước trống: string = null vật lý; array = `[]` (master report của Phúc tính missing = null ∪ empty — 🔴 chờ D-6 của Integration contract). **Null ở tầng này chưa được phân loại bản chất** (form-not-collected / gated / lỗi thu thập / sentinel lẫn trong chuỗi) — thuộc phạm vi Investigation của Sơn, module Phát không kết luận thay.

**Interface gọi (đã có trong code ✅):**
- Level record: `process_record_text(flat: dict) -> dict` rồi `process_record_skills(flat) -> dict` (in-place an toàn: chỉ thêm cột).
- Level DataFrame: `normalize_dataframe(df, skills_column="skills_list")`.

---

## 3. Output Contract

Module sinh **14 cột mới** (tên lấy từ code hiện hành, API `process_record_text`/`process_record_skills`). Số liệu coverage dưới đây đo **direct run** của chính module trên toàn bộ 9.824 record Integration thật (26/10/2026):

| Cột output | Kiểu | Có dữ liệu | Ý nghĩa | Người tiêu thụ chính |
|---|---|---:|---|---|
| `job_title_clean` | str\|null | 99,9% | Tiêu đề đã bóc tag địa danh/đuôi lương | Khoa (JD context), Duy (matching), EDA |
| `jd_clean_text` | str\|null | 96,6% | JD sạch HTML+bullet+emoji, nhiều dòng | Khoa (lương ẩn tầng 2), Sơn (GenAI), Duy (cosine) |
| `requirements_clean_text` | str\|null | 96,4% | Yêu cầu đã làm sạch | Sơn, Duy, EDA |
| `primary_city` | str (không null) | 100% | 1/34 đơn vị HC hiện hành (canonical dict v2), hoặc "Remote"/"Toàn quốc"/"Quốc tế"/"Không xác định"; khong nhan dien→nguyen van | Duy (blocking), Tài, EDA (SD4) |
| `working_locations_clean` | list[str] | 95,7% | Danh sách tỉnh chuẩn, dedup | Duy, EDA |
| `is_remote` | int 0/1 | =1: **2,4%** | Cờ làm việc từ xa | EDA, Tài |
| `standardized_job_family` | str (13 giá trị JF00–JF12) | 100% | Job Family SD2 | Duy (blocking), Tài, EDA (SD2) |
| `standardized_seniority` | str (7 giá trị: 6 bậc + UNKNOWN) | mapped 79,2%, UNKNOWN 20,8% | Seniority chuẩn | Tài (luật Director), Sơn, EDA |
| `skills_standardized` | list[str] | 82,1% | Kỹ năng đã ESCO-hóa + dedup | Duy (cosine), Sơn, EDA (SD3) |
| `hard_skills` | list[str] | 81,1% | Nhóm kỹ năng cứng (SD3) | EDA SD3 |
| `domain_knowledge` | list[str] | 17,0% | Nhóm hiểu biết ngành (SD3) | EDA SD3 |
| `soft_skills` | list[str] | 9,7% | Nhóm kỹ năng mềm (SD3) | EDA SD3 |
| `skills_unmatched` | list[str] | 75,4% **record** có ≥1 tag ngoài từ điển | Nhãn gốc chưa map ESCO (giữ lại, không bỏ). **Lưu ý H: đây là theo-RECORD, không phải tỉ lệ skill chưa map trên toàn dataset** | Phát (bồi từ điển), Sơn |
| `esco_coverage_rate` | float 0–1 | mean **0,197** | Tỉ lệ tag khớp ESCO **của từng record** (trên tag gốc; **KHÔNG tự tính lại** sau `augment_record`) | Quality monitoring |

> **Ba khái niệm cần phân biệt (H, đừng nhầm):** `province_mapping_rate` (location) = tỉ lệ record map được ≠ **accuracy**; `esco_coverage_rate` = trung bình theo-record của **tag gốc**; `skills_unmatched` = **đếm theo record** có ≥1 tag chưa map (không phải tỉ lệ skill chưa map trên toàn dataset). Đây là 3 đại lượng khác nhau, không quy về một số. Output completeness (%) ≠ mapping accuracy (%).

**Quy tắc đầu ra (🟡 đề xuất, chờ duyệt):**
- O-1: Không xóa/sửa bất kỳ cột input nào; output luôn là cột mới (verified: test `test_generates_new_columns_without_touching_originals`).
- O-2: Không ghi đè nội dung khi input null — output là `null`/`[]`/`"Không xác định"`/`JF00_OTHER_IT` theo bảng trên, **không tự bịa giá trị**.
- O-3: Mảng kỹ năng luôn dedup theo canonical (bất biến DoD "không trùng do hoa/thường/dấu chấm" — ✅ test).
- O-4: Kỹ năng ngoài từ điển được **giữ nguyên nhãn** trong `skills_unmatched` (ranh giới "không mất thông tin"), không im thành ESCO sai.

**🔴 PENDING S-2 — Tên cột theo TASKS.md vs code:** TASKS.md §6.2 ghi output là "jd_clean_text, standardized_job_family, standardized_seniority, kỹ năng ESCO" — khớp code, **nhưng không nêu** `job_title_clean`. 🟡 `apply_legacy_column_names()` (text_cleaner.py:354) **TỒN TẠI** nhưng **KHÔNG được export** (không có trong `__init__.py`) và **KHÔNG có call-site** ở bất kỳ đâu → **đang là code bridge chưa tích hợp (dead)**, KHÔNG phải một phần của pipeline đang chạy. Pipeline Phúc hiện tự sinh `job_family`/`job_seniority` trực tiếp, không qua bridge này. → Thuận/Phúc quyết: hoặc export+nối bridge, hoặc bỏ (xem review §9-B).

**Kết quả run toàn quốc cần bàn (🔴 evidence, chưa diễn giải):**
- `JF00_OTHER_IT` = **52,7%** (5.181/9.824) — technically compliant DoD ("hoặc gắn cờ Other IT"), nhưng tỷ lệ quá cao. Mẫu quan sát từ VietnamWorks: phần lớn là tin **non-IT** (kế toán, sales, giáo viên...) lẫn vào dataset. Hướng xử lý (a) lọc non-IT ở tầng nào, (b) bồi keyword cho các ca IT bị bỏ (IT Manager, presales đã sửa 1 phần) — **cả hai đều cần team quyết, module không tự đổi taxonomy**.
- `is_remote` chỉ 2,4% trong khi Glints có `raw_work_mode` 100% — cần đối chiếu phân bố per-source trước khi EDA dùng cột này (🔴 chờ xác minh, chưa kết luận là thấp bất thường hay đúng thực tế).
- `esco_coverage_rate` mean 0,197 (toàn 8 nguồn) — thấp hơn nhiều mẫu VietnamWorks local (0,347) do tag TopDev/CareerViet dạng phrase dài; liên quan trực tiếp đến quyết định S-3 dưới đây.

---

## 4. Processing Rules

### 4.1. Text Cleaning (`text_cleaner.py`)
- **Pipeline 4 bước (✅ code):** strip HTML/CSS inline (delegate `transformation/html_cleaner`) → Bullet Stitching nối câu gãy (delegate `transformation/bullet_stitcher`, nguồn lỗi: Vieclam24h 619 tin theo docs 01 §4) → dọn emoji/control chars (regex Unicode blocks) → nén whitespace. Output giữ cấu trúc dòng.
- **Title (✅ code 26/10):** bóc tag địa danh **mọi vị trí** đầu/giữa/cuối — bao gồm cả biến thể
  tiếng Anh không dấu `[Ho Chi Minh]` (ITviec) và tag giữa title `...- [HCM] - ...` (TopCV),
  bằng callback kiểm tra nội dung ngoặc CHỈ chứa nhãn địa danh (ngoặc tech stack như
  `(ReactJS/ NodeJS)` được giữ nguyên — có test); bóc đuôi quảng cáo lương cả dạng
  `(Lương Khởi Điểm Từ 45M)`. (Known gap ghi ở bản draft trước — đã fix 26/10, chờ Phúc/Thuận review diff.)
- **City (✅ code + data 26–27/10):** `data/dictionaries/vn_provinces.json` **v2.0.0** =
  **34 đơn vị hành chính hiện hành** (từ 1/7/2025, NQ 60-NQ/TW) làm canonical; 63 tên cũ
  giữ trong `successor_map_2025` + alias. `normalize_city` khớp accent-insensitive,
  ranh giới từ, alias dài nhất thắng. Chuỗi không nhận diện → trả nguyên văn (cấm mất nhãn).
  - **LOCATION FIX 27/10 (lỗi logic, không phải hiển thị):** `_norm_loc::_WORD_NUMS`
    trước đây dịch mọi "quận <từ-số>"→số giữa chuỗi ⇒ `"Quận Ba Đình"`→`"quan 3 dinh"`→
    nhầm **Hồ Chí Minh**. Đã siết: **chỉ** dịch khi từ-số ở **cuối chuỗi**; thêm alias
    `bac tu liem`. Kết quả trên 9.824 record: **Ba Đình→HCM sai: 20 → 0**; HN 4.007→4.048,
    HCM 4.135→4.088 (reclassify, **không đổi tổng mapping**). Kèm 2 test (T-B1..B5 + multi-loc).
  - **Metric đúng (đối chiếu baseline, cùng code):** `province_mapping_rate = 9.425/9.824 =
    95,94%` (exact 87,63% + historical-alias 2,63% + district/abbrev 5,68%); special
    (Remote/TQ/QT) 0,35%; unknown 3,06%; unmapped_raw 0,65%. **Lưu ý: mapping_rate KHÔNG
    phải accuracy** — chỉ đo 'resolve về canonical'; accuracy toàn phần chưa kiểm định
    (mới dừng ở lớp lỗi đã biết). Không dùng 99,3x% làm mapping rate (mẫu số còn lẫn
    nhãn đặc biệt).
  - **Pending (không tự đổi luật):** multi-location → thắng bởi 'alias dài nhất toàn chuỗi'
    rồi mới `priority_hubs`, **không phải 'tỉnh đầu tiên' như docstring cũ** (đã sửa docstring);
    luật chọn final cần nhóm chốt.
- **`is_remote` (✅ code):** cascade `raw_location_text` → `raw_work_mode` → `jd_clean_text`.
  🟡 **S-5 đã chốt một chiều (26/10, chờ team xác nhận lại):** "Toàn quốc" **không còn**
  kích hoạt `is_remote` (địa bàn rộng ≠ làm từ xa — hết tình trạng double-count với
  `primary_city`); test cập nhật tương ứng. Câu hỏi còn mở: `is_remote` = 1 chỉ 2,4%
  toàn corpus — cần đối chiếu phân bố per-source trước khi EDA dùng.

### 4.2. Job Family & Seniority Mapping (`taxonomy_mapper.py`)
- **Job Family (✅ code):** cascade 12 family hẹp→rộng, keyword khớp theo **ranh giới từ** (`_kw_hit`, chống `java` cướp `javascript`, `ba` cướp `database`); tiêu đề nhân đôi trọng số so với skills; mọi đầu vào trả về đúng 1 mã JF00–JF12 (DoD ✅ test param 13 ca + bất biến "luôn có mã").
- **Seniority — HAI API KHÁC NHAU (✅ code, đã đối chiếu taxonomy_mapper.py):**
  - `map_seniority_code(seniority_text, title_text, experience_text=None)` → trả **MÃ** (`INTERN`…`UNKNOWN`), cascade `raw_seniority_text`→`job_title`→regex năm trong `raw_experience_text`. `standardized_seniority()` bọc nó (đủ 3 đối số) và **là nguồn sinh cột `standardized_seniority`** (qua `text_cleaner.process_record_text`).
  - `normalize_seniority(seniority_text, title_text)` → trả **NHÃN hiển thị** ("Intern"…"Chưa xác định"), **KHÔNG nhận `experience_text`**. Đây là hàm Phúc gọi trong `run_staging_integration_pipeline.py` (cột `job_seniority`).
  - ⚠️ **Khác biệt logic THẬT (không phải giới hạn hiển thị):** bản ghi chỉ suy được cấp bậc từ kinh nghiệm → `standardized_seniority` có mã, còn `job_seniority` của Phúc = "Chưa xác định". **Không tự hợp nhất**; pending C (xem review report §9), người liên quan Phát+Phúc+Khoa.

### 4.3. Skill Normalization (`skill_normalizer.py` + `data/dictionaries/esco_it_skills.json`)
- **3 tầng (✅ code, offline deterministic):** (1) exact alias — key normalize NFC/lowercase/nén `. - _ /` space → `ReactJS=React.js=React JS→React`, `VueJS→Vue`, `Golang→Go`, `NodeJS→Node.js` (DoD §6.3.3 ✅ test); (2) fuzzy difflib ≥0,86 chỉ cho thuật ngữ ASCII ngắn (typo `Reactj→React`; khóa tiếng Việt để tránh khớp giả); (3) unmatched **giữ nhãn gốc** + flag. 🔴 Fuzzy cũng chạy ở chế độ **exact-tag** (skills_list), tỷ lệ false-positive của nhánh này **chưa đo**.
- **Xử lý tag đa kỹ năng (✅ code):** khớp cả cụm trước (bảo vệ `C/C++`, `UI/UX`, `CI/CD` khỏi xé đôi), fail mới split theo `,`/`;`/` + `/`/ Hoa`. 🟡 **Limitation (chưa xử lý):** một số alias hợp nhất cả cụm — vd `PHP/MySQL` → **PHP** — nên thành phần thứ hai (**MySQL**) **có nguy cơ bị bỏ sót**. Đây là hệ quả cách thiết kế alias hiện tại, **không phải bug đã sửa** (chi tiết + hướng xử lý ở review report).
- **Blacklist (✅ code + data):** `data/dictionaries/skills_blacklist.json` lọc tag rác phi-kỹ năng ("đi làm ngay", "quyền lợi"…).
- **Từ điển:** ~125 canonical ESCO + ~550 alias, mỗi entry có `type` (hard/domain/soft) và liên kết `job_families`; đường dẫn `data/dictionaries/` đã bật git-track (🟡 `.gitignore` negation — chờ review khi commit).
- ✅ **ĐÃ CÀI ĐẶT (26/10) — `preprocessing/normalization/skill_extractor.py`** (boundary-aware,
  mặc định chỉ kích hoạt khi bản ghi ≤ 2 kỹ năng chuẩn hóa, provenance `skills_source`):
  - Kết quả đo trên 9.824 record thật: **31,3% record được bù skills từ JD** (TopDev hưởng
    lợi nhiều nhất — đúng khoảng trống 55,5% tag).
  - **FP đào được trên JD tiếng Việt có dấu và đã chặn bằng `text_scan_blocklist` trong
    `_meta` từ điển** (chỉ ảnh hưởng chế độ scan text, exact-tag không đổi):
    `chăm sóc`⊅`soc`→SIEM, `sắp xếp`⊅`sap`→ERP, `y tế`→Healthcare IT, phrase mềm
    (giao tiếp/lãnh đạo/tỉ mỉ/office) — còn lại trong top trích là soft skill hợp lệ
    (Communication/Problem Solving/Teamwork — chính là nhóm SD3 cần đo).
  - 🟡 **Trạng thái extractor (3 mặt riêng biệt, đừng lẫn):** (i) code ✅ đã implement; (ii) unit test ✅ 6 cases; (iii) `augment_record`/`extract_skills_from_text` **đã export** trong `preprocessing/normalization/__init__.py` nhưng **chưa có call-site** trong pipeline (`run_staging`/`master_pipeline` không gọi) → **chưa bật production, chưa sẵn sàng production**. Precision bù skills mới ở mức **sơ bộ 30 mẫu / 1 người ≈ 93,3%** — chưa phải đánh giá độc lập.
- **🟡 PENDING S-6 — Semantic embedding ESCO mapping (đã xác minh nguồn):** KHÔNG phải DoD — DoD TASKS.md §6.3.3 chỉ gồm (a) 100% title → family/Other IT, (b) không trùng skill do hoa/thường/dấu chấm. Yêu cầu embedding/cosine chỉ là **đề xuất thiết kế** tại `docs/preprocessing/integration/01_text_features_multivariate_analysis_and_exhaustive_mapping.md:182` và `docs/01_modern_data_mining_overview.md:158`; ngưỡng **≥ 0.88** trong `docs/preprocessing/05_post_integration_master_pipeline.md §2.3` thực chất gắn với **cross-platform dedup (Duy)**, không phải pipeline skill của Phát. Implementation hiện tại = dictionary + fuzzy. → cần nhóm quyết có embedding hay không (không tự kết luận là bắt buộc).

---

## 5. Validation Rules

**DoD chính thức (TASKS.md §6.3.3, nghiệm thu):**
1. "100% tiêu đề công việc được ánh xạ vào 1 trong 12 Job Family **hoặc gắn cờ `Other IT`**." — ✅ **đạt theo nghĩa đen**: 9.824/9.824 trả mã JF hợp lệ (run thật). ⚠️ Caveat: cờ Other chiếm 52,7% → xem P-2 dưới.
2. "Không còn hiện tượng trùng lặp kỹ năng do chữ hoa/thường hoặc ký tự dấu chấm." — ✅ **đạt theo nghĩa đen**: 0 canonical duplicate trong `skills_standardized` trên mọi record run; đơn kiểm chứng `["ReactJS","React.js","REACT JS","react"] → ["React"]` + assert `set(...) == {JavaScript, Java, TypeScript}` (chống Java/JS lẫn).

**Test hiện có (✅ pass, offline, reproducible):**
- `tests/test_skill_processing.py` — **60 cases** (26/10: 51 → 27/10: 60): cleaning/title/city/remote/family/seniority/ESCO 3 nhóm/blacklist/multi-tag/fuzzy/unmatched/extractor + API cấp record + smoke data thật VietnamWorks 931 record (tự skip nếu thiếu file).
- **Không phải toàn bộ repo pass.** Phân loại theo chạy thực tế 27/10:
  - Test **đã chạy & pass**: `tests/` loại trừ 2 file dưới đây → **89 passed, 0 failed, 0 skipped** (gồm hồi quy `test_preprocessing_pipeline.py` của Phúc, `test_text_preprocessing_and_metrics.py` của Khoa).
  - Test **không chạy được** (collection error): `tests/test_monitoring_api.py` — thiếu dependency `fastapi` (môi trường, ngoài module).
  - Test **chạy nhưng fail vì thiếu dữ liệu**: `tests/test_integration_step.py` — **2 failed, 1 passed**; 2 fail do thiếu `data/integration/*` local (không phải module Phát).

**Đề xuất tiêu chí bổ sung (🟡, chờ Thuận đưa vào `test_master_pipeline.py`):**
- V-1: output columns ⊆ đăng ký §3 và không ghi đè input (bất biến O-1) — mọi record.
- V-2: `standardized_job_family ∈ JF00..JF12` ∀ record; `standardized_seniority ∈ 6 bậc ∪ UNKNOWN` ∀ record.
- V-3: không canonical duplicate trong `skills_standardized` ∀ record.
- V-4: throughput module ≥100 records/s — ✅ **pure-module ~181–182 rec/s** (dataset local 931 rec, warm-up + 5 run, KHÔNG tính I/O). (Benchmark cũ ~217 rec/s trên 300 rec / singleton warm là **phương pháp khác, không so sánh trực tiếp**.) Cần Thuận đo lại trong pipeline tổng.

**Vấn đề ghi nhận, không tự xử lý (🔴):**
- **P-1:** Tài liệu nhãn lệch so với physical schema (code 29 key, git mọi ref; TASKS.md "20 cột", docstring "25 trường", doc 05 "9.390×20"). Module này **không sửa tài liệu thành viên khác** — ghi nhận để Phúc/Thuận đối chiếu.
- **P-2:** `JF00_OTHER_IT` 52,7% (topdev 91,8%). **JF00 KHÔNG đồng nghĩa Non-IT** — gồm cả tin non-IT lẫn IT chưa được taxonomy nhận diện. Chưa đủ căn cứ để loại bỏ JF00 khỏi dataset; bổ sung `job_scope` (IT/NON_IT/UNCERTAIN) là **đề xuất pending**, không phải quyết định đã chốt. Không tự lọc/xóa (vi phạm "không mất thông tin"). → cần Sơn/Thuận/chủ sàn quyết.
- **P-3:** `skills_list` input là **hỗn hợp** tag công nghệ lẫn phrase nghiệp vụ/soft-skill tự do theo sàn (verified từ run + unmatched 75,4% record) → dictionary cần bồi vòng 2; đề xuất quy trình bồi từ `skills_unmatched` top-N mỗi tuần tới khi coverage TB ≥0,5 (ngưỡng 🟡, chưa chốt).

---

## 6. Dependencies

| Thành viên/module | Chiều phụ thuộc | Nội dung cụ thể |
|---|---|---|
| **Phúc** (Integration) | Phát ← Phúc | Input = 29 cột `integrated_flat` (schema ✅; nhãn tài liệu 🔴 P-1). Cần Phúc xác nhận: tên cột input, quy ước missing null∪`[]`, và việc module được quyền giả định mọi key luôn hiện diện (verified đúng 100%) |
| **Khoa** (Transformation) | hai chiều | Phát **delegate** `strip_html_tags` + `stitch_fragmented_bullets` của Khoa (không sở hữu). Ngược lại Khoa nên dùng `jd_clean_text` của Phát cho JD-regex tầng 2 (đề xuất đã nêu với Khoa, chưa chốt). Chính sách 2.B hiện ở `text_metrics.py` của Khoa → S-1 |
| **Sơn** (Missing/GenAI) | Sơn ← Phát | Sơn đọc `jd_clean_text`, `skills_standardized`, `standardized_seniority`, `primary_city` làm ngữ cảnh GenAI impute; phân loại bản chất null (input contract §2) thuộc Sơn — Phát không kết luận thay |
| **Tài** (Outlier/Quality) | Tài ← Phát | `standardized_seniority` phục vụ luật "non-Director >300M"; lưu ý UNKNOWN 20,8% — luật của Tài cần branch cho giá trị này |
| **Duy** (Dedup) | Duy ← Phát | Blocking key `(normalized_company, primary_city, standardized_job_family)` — tên 2/3 cột thuộc Phát; cosine dùng `skills_standardized` + `jd_clean_text`. Duy cần chốt xử lý record `JF00_OTHER_IT` khi blocking (P-2 liên quan) |
| **Thuận** (Master Pipeline) | Thuận ← Phát | Interface: `process_record_text` → `process_record_skills` (theo thứ tự, record dict) hoặc `normalize_dataframe`; SLA throughput ✅ ~181 rec/s (pure); V-1..V-4 đề xuất vào `test_master_pipeline.py`; **toàn bộ interface chỉ là đề xuất tới khi PR thật** (§6.4 TASKS: PR về `integration/Thuan`) |

**Quyền sở hữu file (theo TASKS.md §6.2):** Phát sở hữu `preprocessing/normalization/` (trừ `cross_deduplicator.py` của Duy đang tạm cư cùng thư mục — lưu ý khi refactor), `data/dictionaries/`, `tests/test_skill_processing.py`. Module **không** sửa `transformation/`, `missing_outlier/`, `integration/`.

---

## Phụ lục — Bằng chứng & tái lập

- Audit physical schema: `scripts/audit_r2_integration_keys.py` (read-only, 9.824/9.824 rec).
- **Lich su trien khai 26–27/10 (gop):** `vn_provinces.json` **v2.0.0** (34 don vi hien hanh +
  `successor_map_2025`/alias 63); `skill_extractor.py` (+ `text_scan_blocklist` trong `_meta` ESCO);
  `apply_legacy_column_names()` trong `text_cleaner.py` (bridge, **chưa tích hợp pipeline**); LOCATION
  FIX 27/10 (`_WORD_NUMS` siết cuối-chuỗi + alias `bac tu liem`).
- **Tests:** `tests/test_skill_processing.py` **60 cases** (26/10: 51 → 27/10: 60). Chạy:
  `.venv/bin/python -m pytest tests/ -q --ignore=tests/test_monitoring_api.py --ignore=tests/test_integration_step.py`
  → **89 passed, 0 failed, 0 skipped** (2 file ignore do thiếu fastapi / thiếu file integration local — ngoài phạm vi module).
- **Metrics chốt (đo trên 9.824 record, code hiện tại):** `province_mapping_rate` 95,94%;
  `esco_coverage_rate` mean 0,197; JD-augment (extractor, khi bật) 31,3% record; JF00 52,7%.
  Chi tiết & phân tách exact/alias: xem `02_text_skill_processing_review.md`.
- **Benchmark pure-module (data local 931 rec, warm-up, 5 run, KHÔNG tính I/O):** chain đầy đủ
  ~**181 rec/s** (nút cổ chai `process_record_skills` ~167). End-to-end qua R2 ~108–172 rec/s
  (chi phối bởi network) — **không dùng** để kết luận throughput module.
- Task spec: `TASKS.md` §6.3.3 (đã tick [x] 3 đầu việc Pha 3 ngày tạo module — lưu ý tick phản ánh *hoàn thành theo TASKS.md*, các PENDING S-1..S-6 trong tài liệu này vẫn mở).
