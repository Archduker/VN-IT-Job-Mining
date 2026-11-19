# ĐẶC TẢ PROCESSING (bước 07–12)

> **Dự án:** VN-IT-Job-Mining. Đề tài: "Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT".
> **Phiên bản:** 3.0.1, ngày 17/11/2026. **Trạng thái:** đã duyệt 17/11/2026 (chặng 3); 3.0.1 ghi quyết định bỏ 12_tfidf (chặng 4).
> **Thay cho:** bản 2.0 (viết theo thiết kế 13 bước, lẫn cả phần pre-processing), các file P5, PH8, PH9 và nhật ký P5 trong `docs/spec/preprocessing/`.
> **Quan hệ với tài liệu khác:** mã bước, thư mục và đường dẫn lấy theo [spec 03](03_data_mining_lifecycle.md) mục 3.2. Đầu vào là bảng sạch của [spec 05](05_preprocessing_spec.md) mục 4. Bên dùng đầu ra là Mining ([spec 07](07_mining_spec.md)). Mục tiêu: [`docs/target/`](../target/00_de_tai.md).

## 0. Cách đọc

- **Nguồn sự thật:** code (`scripts/run_preprocessing.py` `PROCESSING_STEPS`, `processing/**`), rồi report chạy thật `reports/processing/<bước>/`, rồi đặc tả cũ (chỉ phần còn khớp code).
- **Số liệu** lấy từ report chạy thật ngày 10–11/11/2026 (`code_version` 37bb865), trên 4.671 tin của bảng 04. Dữ liệu còn đang làm sạch (PRE-35), nên các số sẽ đổi.
- **Mỗi bước** viết theo khuôn: Mục đích, Code, Đầu vào, Đầu ra, Report, Luật, Kiểm tra, Trạng thái, Việc mở.
- Mã luật: `S7.x` (07 tách section), `K8.x` (08 kỹ năng), `W9.x` (09 tách từ). Bước 10 dùng tên bước con 10, 10b, 10c, 10d.

## 1. Processing phục vụ SD nào

Processing biến bảng sạch thành các **biểu diễn** mà Mining dùng: kỹ năng theo từng tin, ma trận đặc trưng số và vector văn bản. Processing không trả lời câu hỏi nào của SD.

| Đầu ra | Bước | Bên đọc | SD |
|---|---|---|---|
| `07_sections/all.parquet` (bullet theo section) | 07 | 08, 12_e5 | gián tiếp: SD2, SD3 |
| `08_skills/job_skills.parquet` (tin × kỹ năng, mức bắt buộc hay ưu tiên) | 08 | 10; dự kiến M1 BI (nhu cầu kỹ năng của tin người mới) và M6, cả hai chưa có code | SD1 (câu về kỹ năng), SD2, SD4, SD5 |
| ~~`09_tokens/all.parquet`~~ | 09 | **Bỏ khỏi chuỗi 19/11**: 10c tự đếm `n_tokens` | — |
| `10_features/features.parquet` + `encoding_dictionary.json` | 10 | M2 (cột `skill__*` = K-tool; `concept__*`, `soft__*` bảng riêng), M3, M4, M5 | SD2, SD3, SD4, SD5 |
| ~~`12_tfidf/`~~ | 12_tfidf | **Bỏ** (người dùng chốt 17/11, mục 3.5) | — |
| `12_e5/job_emb.npz` | 12_e5 | M3 (phân cụm), M4 | SD3 |

## 2. Hợp đồng chung

### 2.1. Chuỗi bước

```text
data/preprocessing/04_normalization/all.parquet   (bảng sạch, spec 05)
  ▼  07 sections   tách JD thành bullet, gán section
  ▼  08 skills     trích kỹ năng trên từng bullet       (07 và 08 chạy trong cùng một lần gọi)
  ✗  09 tokens     bỏ khỏi chuỗi 19/11 (10c tự đếm số từ)
  ▼  10 features   10 rời rạc hóa → 10b chọn kỹ năng → 10c xây đặc trưng → 10d mã hóa
  ▼  12_e5         embedding bullet của 07 bằng multilingual-e5-base (cần GPU)
data/processing/<bước>/
```

- Lệnh: `python scripts/run_preprocessing.py --step <bước>|all` (chạy chung chuỗi với pre-processing). Muốn chạy riêng một bước thì dùng tên bước, ví dụ `--step 10_features`.
- **Không bỏ dòng.** Mọi bước giữ đúng 4.671 tin của bảng 04 (riêng 12_e5 đếm theo bullet: 114.008 dòng vào, 114.008 dòng ra).
- **Không sửa giá trị đã chuẩn hóa** ở pre-processing, không đọc lại raw.
- Report ghi ở `reports/processing/<bước>/`; driver chép thêm 07–09 sang `reports/preprocessing/<bước>/` cho trang Monitoring.
- Processing chỉ ghi trên máy. Đẩy lên R2 thì theo spec 05 mục 2.1.

### 2.2. Fit trên toàn bộ hay chỉ trên tập train

- Các bước có fit (ngưỡng `min_df` ở 10b, bin đều tần suất ở 10, stopword theo DF ở 09) hiện **fit trên toàn bộ 4.671 tin**. Cách này đúng cho phần không giám sát (M2, M3, M4).
- **Với SD4 (M5) thì khác:** đặc trưng nào được fit từ dữ liệu, nếu dùng làm đầu vào cho model lương, phải fit lại **chỉ trên tập train**, bên trong `sklearn.Pipeline` của M5. Bước 11 (chia train/test theo công ty) nằm ở M5, không nằm ở Processing (spec 03, mục 3.3). Cụ thể:
  - `salary_bin_eqfreq5` và `salary_mid`, `salary_range_ratio` được tính từ chính biến mục tiêu, nên **không được làm đầu vào** của model lương.
  - Cột `skill__*` được chọn bằng `min_df` trên toàn bộ dữ liệu. Có rò rỉ nhẹ (chỉ là số tin có kỹ năng, không dính tới lương). M5 phải ghi rõ chuyện này, hoặc tính lại `min_df` trên tập train.

### 2.3. Dùng model và từ điển

| Thứ dùng | Bước | Loại | Ghim phiên bản |
|---|---|---|---|
| `pyahocorasick` | 08 | Thuật toán (automaton), không phải model | Chưa ghim trong `requirements*.txt` |
| `underthesea.word_tokenize` | 09 | Luật + CRF đóng gói sẵn, không tải gì khi chạy | Chưa ghim (máy dev dùng 9.5.0) |
| `intfloat/multilingual-e5-base` | 12_e5 | Model embedding, chạy local trên GPU, fp16 | **Chưa ghim commit** (mục 6) |

- **Từ điển phải được duyệt.** Code chỉ đọc `processing/dictionaries/section_headings.json`, `priority_cues.json`, `short_aliases.json`, và chỉ lấy mục `approved: true`. Các file `*_candidates.json` do script sinh ra, **code không bao giờ đọc**. Đến 17/11 cả ba file đã duyệt **chưa tồn tại**, nên 07 chỉ dùng luật S7.2 và 08 không dùng alias ngắn (mục 6).
- Taxonomy kỹ năng của 08 là `processing/dictionaries/skills_taxonomy_230.json` (230 kỹ năng, 6 nhóm), khác với `preprocessing/dictionaries/skills.json` mà bước 03 T7 dùng (mục 6).

## 3. Các bước

### 3.1. Bước 07: Sections

| Mục | Nội dung |
|---|---|
| Mục đích | Tách JD thành bullet có nhãn section, để 08 biết kỹ năng nằm ở phần yêu cầu, phần ưu tiên hay phần phúc lợi, và để 12_e5 có đơn vị văn bản ngắn. Gián tiếp phục vụ SD2, SD5 (kỹ năng bắt buộc hay ưu tiên) và SD3 |
| Code | `processing/extraction/sections.py` (`split_sections`, `load_headings`, `load_cues`), `processing/extraction/run.py` (`analyze`, `run`) |
| Đầu vào | Bảng 04: `job_id_global`, `source_platform`, `description_clean`, `requirements_clean`, `benefits_list`, `skills_list`; với tin đã dịch thì thêm `description_vi`, `requirements_vi` |
| Đầu ra | `data/processing/07_sections/all.parquet`: một dòng một bullet, cột `job_id_global`, `source_platform`, `bullet_idx`, `section` (`mo_ta`, `yeu_cau`, `uu_tien`, `phuc_loi`, `khac`), `text`, `section_rule` |
| Report | `reports/processing/07_sections/`; `extra`: `n_bullets`, `bullets_by_section`, `bullets_by_rule`, `n_jobs_no_bullet`, `headings_approved`, `cues_approved` |

**Luật:**

| Mã | Luật |
|---|---|
| S7.1 | Tách theo dòng. Dòng bắt đầu bằng `- ` là một bullet; dòng không có ký hiệu bullet cũng là một bullet, trừ khi nó là tiêu đề (S7.3). Bỏ dòng rỗng |
| S7.2 | Section mặc định lấy theo trường nguồn: `description_clean` → `mo_ta`, `requirements_clean` → `yeu_cau`, `benefits_list` → `phuc_loi` |
| S7.3 | Dòng là tiêu đề (khớp `section_headings.json` đã duyệt) thì đổi section cho các dòng sau, đến tiêu đề kế tiếp. Bản thân dòng tiêu đề không thành bullet |
| S7.4 | Bullet hoặc tiêu đề mở đầu bằng cụm "ưu tiên" (theo `priority_cues.json` đã duyệt, ví dụ "ưu tiên", "nice to have", "là một lợi thế") → `uu_tien` |
| S7.5 | Không khớp luật nào thì giữ section mặc định |

Kết quả 10/11: 114.008 bullet (`mo_ta` 39.153, `yeu_cau` 35.152, `phuc_loi` 39.703); 0 tin không có bullet. **100% bullet theo S7.2**, vì chưa có tiêu đề và cụm "ưu tiên" nào được duyệt. Do đó không có bullet nào ở `uu_tien` hay `khac`.

| Mục | Nội dung |
|---|---|
| Kiểm tra | Độ đúng theo bullet trên bộ gold (`processing/evaluate.py`, `scripts/eval_gold_processing.py`): so theo nội dung dòng, chỉ tính bullet nằm trong vùng đã gán nhãn. Đích theo thiết kế: ≥ 90% |
| Trạng thái | Có code, đã chạy thật 10/11. Đo trên gold ngày 11/11: **84,5%**, chưa đạt |
| Việc mở | PRE-33 (duyệt `section_headings`, `priority_cues`), PRE-34 (bullet careerviet thô: 399/400 tin chỉ có 3 bullet) |

### 3.2. Bước 08: Skills

| Mục | Nội dung |
|---|---|
| Mục đích | Mỗi tin có một danh sách kỹ năng chuẩn, kèm mức bắt buộc hay ưu tiên. Đây là nguyên liệu chính của SD2 (gói kỹ năng), SD4 (giá trị kỹ năng), SD5 (kỹ năng nên học), và của câu hỏi kỹ năng ở SD1 |
| Code | `processing/extraction/skills.py` (`SkillMatcher`, `extract_skills`, `load_taxonomy`, `load_short_forms`), `processing/extraction/run.py`, `processing/selection/sparsity.py` |
| Đầu vào | Bullet của 07 (tính trong cùng lần gọi) và `skills_list` của bảng 04 |
| Đầu ra | `data/processing/08_skills/job_skills.parquet`: một dòng một cặp (tin, kỹ năng), cột `job_id_global`, `source_platform`, `slug`, `level` (`required`, `preferred`), `weight` (1 hoặc 0,5), `section`, `via` (`text`, `text_vi`, `meta`), `n_mentions`. Nếu chạy có `min_df` hoặc `merge_map` thì ghi thêm `job_skills_reduced.parquet` |
| Report | `reports/processing/08_skills/`; `extra`: `n_job_skill_rows`, `n_jobs_no_skill`, `top_skills` (30), `short_forms_approved`, `alias_conflicts_dropped`, `sparsity` (ở `_all`) |

**Luật:**

| Mã | Luật |
|---|---|
| K8.1 | Dựng automaton Aho–Corasick một lần từ taxonomy 230. Khóa là `fold(alias)`, chỉ cho alias dài ≥ 4 ký tự hoặc có `#`, `+`, `.` (`c#`, `c++`, `.net`) |
| K8.2 | Ranh giới từ: ký tự liền trước và liền sau chỗ khớp không thuộc `[a-z0-9_#+]` |
| K8.3 | Alias ngắn hoặc dễ trùng từ thường (`bi`, `ba`, `soc`, `c`, `r`, `go`…) **không** quét trên văn bản fold. Chúng chỉ khớp phân biệt hoa thường trên văn bản gốc, và chỉ khi có trong `short_aliases.json` đã duyệt. Lý do: quét trên fold thì `bi` khớp 1.314 tin, so với 363 tin khi khớp hoa thường |
| K8.4 | Quét riêng từng bullet để biết section của từng lần khớp |
| K8.5 | Mức theo section: `yeu_cau`, `mo_ta`, `khac` → `required`, weight 1; `uu_tien` → `preferred`, weight 0,5; `phuc_loi` không quét. Cùng kỹ năng xuất hiện nhiều lần thì giữ mức cao nhất và cộng `n_mentions` |
| K8.6 | Kỹ năng từ `skills_list` của nguồn ghi thêm với `via = meta`, `level = required`. F1 trên gold chỉ tính `via = text` |
| K8.7 | Tin đã dịch (`translation_status = translated`): quét thêm bản dịch. Kỹ năng chỉ thấy trong bản dịch ghi `via = text_vi`; kỹ năng đã có thì chỉ cộng số lần nhắc |

Kết quả 10/11: 32.637 cặp (tin, kỹ năng), 219 kỹ năng được dùng, trung bình 6,99 và trung vị 5 kỹ năng mỗi tin. 363 tin (7,8%) không có kỹ năng nào lấy từ văn bản; tính cả `meta` thì còn 292 tin. Số kỹ năng có DF dưới 3/5/10/20/50 tin lần lượt là 14/24/42/65/101.

- Vì chưa có cụm "ưu tiên" nào được duyệt, **mọi kỹ năng đều là `required`**. Mức bắt buộc hay ưu tiên (thiết kế: 1 và 0,5) hiện chưa có tác dụng.
- Kỹ năng mềm và ngoại ngữ đứng đầu danh sách (ví dụ topcv: communication 677 tin, english 463, teamwork 356; python 258). SD2 và SD5 phải quyết có tách nhóm kỹ năng mềm khi xếp hạng hay không (spec 07).

| Mục | Nội dung |
|---|---|
| Kiểm tra | P/R/F1 micro trên gold, theo cặp (tin, kỹ năng), chỉ tính `via = text`. Nhãn không ánh xạ được về taxonomy thì tính là FN và báo riêng. Đích theo thiết kế: F1 ≥ 0,85. Kiểm thủ công 20 tin ngẫu nhiên |
| Trạng thái | Có code, đã chạy thật 10/11. F1 trên gold ngày 11/11: **0,27**, có thể một phần do cách so tên kỹ năng với `slug` |
| Việc mở | PRE-33 (xem lại cách đo F1; duyệt `short_aliases`), PRE-35 (SD2: 7% tin không có kỹ năng, F1 thấp) |

### 3.3. Bước 09: Tokens

| Mục | Nội dung |
|---|---|
| Mục đích | Biến văn bản thành token sạch để đo độ dài JD (`n_tokens`, 10c). Từ 17/11, khi bỏ 12_tfidf, đây là bên đọc duy nhất; nếu 10c không cần `n_tokens` thì có thể bỏ luôn bước 09 (PRE-34) |
| Code | `processing/transformation/tokenize.py` (`tokenize`, `domain_stopwords`, `load_general_stopwords`, `remove_stopwords`), `processing/transformation/run.py` |
| Đầu vào | Bảng 04. Bước này gọi lại `analyze` của 07–08 để lấy bullet và vị trí kỹ năng, không đọc file của 07 |
| Đầu ra | `data/processing/09_tokens/all.parquet`: `job_id_global`, `source_platform`, `tokens`, `tokens_nostop`, `n_tokens` |
| Report | `reports/processing/09_tokens/`; `extra`: `mean_tokens_per_job`, `df_threshold`, `n_general_stopwords`, `domain_stopwords` (token và DF) |

**Luật:**

| Mã | Luật |
|---|---|
| W9.1 | Trước khi tách từ, thay mỗi kỹ năng đã khớp ở 08 bằng token giữ chỗ `sk_<slug>`, để tokenizer không cắt hỏng `C++` hay `Node.js` |
| W9.2 | `underthesea.word_tokenize`, đưa về chữ thường (trừ token `sk_`). Token ghép giữ dấu cách bên trong |
| W9.3 | Bỏ token chỉ gồm dấu câu hoặc ký hiệu; giữ số |
| W9.4 | Bỏ stopword chung theo danh sách |
| W9.5 | Bỏ stopword theo miền: token có mặt trong hơn 60% số tin. Token `sk_` không bao giờ bị coi là stopword |
| W9.6 | Bullet `phuc_loi` vẫn được tách từ nhưng không thay kỹ năng |

Kết quả 10/11: 10 stopword theo miền (các, có, của, kinh nghiệm, làm việc, năm, theo, trong, và, với). Trung bình số token mỗi tin theo nguồn từ 245 (jobsgo) đến 440 (itviec).

| Mục | Nội dung |
|---|---|
| Kiểm tra | Token `sk_` còn nguyên sau khi tách; danh sách stopword theo miền phải được người dùng xem |
| Trạng thái | Có code, đã chạy thật 10/11 |
| Việc mở | PRE-34 (đánh giá hiệu quả của 09–12) |

### 3.4. Bước 10: Features (10, 10b, 10c, 10d)

| Mục | Nội dung |
|---|---|
| Mục đích | Một ma trận số, mỗi tin một dòng, dùng chung cho mọi bước Mining. Phục vụ SD2 (cột kỹ năng), SD3 (đầu vào phân cụm và Isolation Forest), SD4 (đặc trưng của model lương), SD5 |
| Code | `processing/encoding/features.py` (`build_features`, `skill_block`, `run`); `processing/transformation/discretize.py` (10); `processing/selection/sparsity.py` (10b); `processing/construction/features.py` (10c); hằng ở `processing/encoding/constants.py` |
| Đầu vào | Bảng 04, `08_skills/job_skills.parquet` (cần cột `type`) |
| Đầu ra | `data/processing/10_features/features.parquet` (đúng 4.671 dòng, khóa `job_id_global`), `encoding_dictionary.json` (mỗi cột: cách mã hóa, cột nguồn) |
| Report | `reports/processing/10_features/`; `extra`: `n_cols`, `min_df`, `n_skill_cols`, `n_skills_folded` |

**10, rời rạc hóa** (thiếu giá trị thì -1, không điền trung bình):

| Cột | Cách tính |
|---|---|
| `salary_bin_range` | Lương tham chiếu (trung bình hai cận có số, triệu/tháng) chia theo mốc 10, 20, 35, 60 triệu (`SALARY_EDGES_M`, đề xuất) |
| `salary_bin_eqfreq5` | 5 nhóm đều tần suất trên tin có lương |
| `exp_bin` | 0: dưới 1 năm; 1: 1–2; 2: 3–5; 3: trên 5 |

**10b, chọn kỹ năng (19/11):** ba khối theo `skill_view` (`docs/target/06_yeu_cau_du_lieu.md` mục 2): `skill__` = K-tool, `concept__` = K-concept, `soft__` = K-soft; mỗi khối gom DF < `min_df` = 15 (người dùng chốt 19/11) vào `<khối>__other_skill`. Chạy 19/11: 291, 562, 63 cột. Chi tiết ở `docs/spec/processing/10_features.md`. Các tiêu chí chọn khác chưa chốt (PRE-34).

**10c, xây đặc trưng** (thiếu thì NaN): `n_skills`, `n_required`, `required_ratio`, `n_tokens`, `n_benefits`, `salary_mid`, `salary_range_ratio`.

**10d, mã hóa:**

| Nhóm cột | Cách mã hóa |
|---|---|
| `skill__<slug>`, `concept__<slug>`, `soft__<slug>` | Multi-hot từ 08 theo ba khối (sau 10b) |
| `seniority_ord` | Ordinal 0–4 theo 5 cấp; chưa rõ = -1 |
| `fam__*` | One-hot 10 nhóm nghề + Other |
| `src__*` | One-hot nguồn |
| `wm__*` | One-hot `work_mode` (onsite, remote, hybrid, unknown) |
| `emp__*` | Loại hình làm việc (full_time, part_time, intern, contract, unknown), luật từ khóa trên `raw_employment_type` |
| `tinh__*`, `loc_remote`, `loc_ngoai_vn` | Multi-hot 10 tỉnh nhiều tin nhất, xét mọi địa điểm của tin (`TOP_PROVINCES_K`); còn lại là `tinh__other`; không có tỉnh là `tinh__unknown` |
| `log_salary_min`, `log_salary_max`, `exp_min_years`, `exp_max_years`, `headcount` | Giữ số; thiếu thì NaN kèm cột `__missing` |
| `posted_month`, `days_to_deadline`, `days_to_deadline__missing` | Ngày; `days_to_deadline` tính từ `crawled_at` |
| `salary_status__value`, `salary_status__unknown`, `is_negotiable`, `is_outlier_salary`, `seniority_can_kiem` | Cờ 0/1. Lương thỏa thuận và lương không ghi gộp vào `salary_status__unknown` (người dùng chốt 11/11) |

- Không có cột `it_status` (mọi tin đều là `it`, nên là cột hằng) và không có `*_prob` (bảng 04 không có).
- Cờ `seniority_can_kiem` được giữ thành cột, không bỏ dòng; Mining tự lọc.

| Mục | Nội dung |
|---|---|
| Kiểm tra | Số dòng bằng bảng 04; mọi cột có trong `encoding_dictionary.json`; không có NaN ngoài các cột số đã ghi |
| Trạng thái | Có code, đã chạy thật. Report 10/11 ghi 242 cột; L-47 (11/11, sau khi gộp 10 nhóm nghề) ghi 243 cột |
| Việc mở | PRE-37 việc 4 (`posted_month` đang lấy tháng từ `posted_date`), PRE-34 (đánh giá: `min_df`, mốc bin lương, 10c có ích không), PRE-33 (chốt `min_df`) |

### 3.5. Bước 12_tfidf: đã bỏ (17/11/2026)

- **Quyết định:** người dùng chốt ngày 17/11 bỏ TF-IDF khỏi dự án (spec 07 mục 4). Biểu diễn nội dung JD cho SD3 chỉ dùng e5 (12_e5).
- **Lý do:** không bước Mining nào đọc `12_tfidf/`; M3 đã tắt TF-IDF tự dựng từ L-47 (`tfidf_weight` = 0) và chạy với kỹ năng + e5.
- **Lần chạy cuối** (10/11): ma trận 4.671 × 20.000, 1.205.812 ô khác 0. Thông số cũ: `TfidfVectorizer` unigram + bigram, `min_df` 5, `sublinear_tf`, L2. Xem lại bằng `git show`.
- **Việc code** (MINE-7): bỏ `12_tfidf` khỏi `PROCESSING_STEPS` trong `scripts/run_preprocessing.py` (**làm 19/11**); xóa `processing/extraction/vectorize.py` cùng test của nó, xóa `data/processing/12_tfidf/` và `reports/processing/12_tfidf/`: chưa làm (cần người dùng đồng ý xóa).

### 3.6. Bước 12_e5

| Mục | Nội dung |
|---|---|
| Mục đích | Vector ngữ nghĩa của từng tin, đọc được cả tiếng Việt lẫn tiếng Anh, cho SD3 (phân cụm M3, tìm tin "khác hoặc mới" M4) |
| Code | `processing/extraction/embed.py` |
| Đầu vào | `07_sections/all.parquet` |
| Đầu ra | `data/processing/12_e5/bullet_emb.npy` (float16, một dòng một bullet), `bullet_index.parquet`, `job_emb.npz` (vector tin = trung bình mọi bullet; thêm trung bình riêng theo `mo_ta`, `yeu_cau`, `phuc_loi`, và mảng `has` cho biết tin có section đó không; tin không có bullet thì vector 0), `meta.json`; cache theo `sha1(text)` chia shard ở `cache/` |
| Report | `reports/processing/12_e5/`; `extra`: `bullets`, `dim`, `model`, `jobs` |
| Luật | Thêm tiền tố `passage: `; độ dài tối đa 256 token; batch 64; vector chuẩn hóa; fp16 trên GPU. Chạy lại chỉ tính văn bản chưa có trong cache. Dry-run không gọi model |
| Kiểm tra | Số bullet bằng 07; `dim` = 768 |
| Trạng thái | Có code, đã chạy thật 10/11: 114.008 bullet, 4.671 tin, khoảng 40 ms mỗi bullet trên Quadro T1000 |
| Việc mở | Mục 6: ghim phiên bản model; report ghi sai `api.used = false` |

## 4. Bước 11 (chia train/test) không thuộc Processing

- Thiết kế cũ coi bước 11 là tùy chọn, vì khi đó Mining chỉ có phần không giám sát. Từ 16/11 SD4 có model lương, nên **bước 11 là bắt buộc cho SD4** và được đặt trong M5 (spec 03 mục 3.3, spec 07).
- Luật giữ từ thiết kế: chia theo **công ty** (`company_key` của bảng 04) bằng `GroupShuffleSplit`, 80/20, `random_state = 42`. Không công ty nào có mặt ở cả hai tập. Mọi bước fit của model nằm trong `sklearn.Pipeline`.
- SD5 kiểm tách tập 80/20 trên tin người mới (`docs/target/05_sd5_lo_trinh_hoc.md` mục 6). Việc này cũng làm ở Mining.

## 5. Kiểm tra chung

- Mọi bước giữ đúng số tin (`checks.rows_conserved`).
- Bộ gold 100 JD (`data/preprocessing/gold/gold_labels.json`) đo 07 và 08 bằng `scripts/eval_gold_processing.py`. Kết quả 11/11: section 84,5%; phúc lợi P 0,97 / R 0,60; kỹ năng F1 0,27.
- File gold không có trong git và không có trên máy dùng để viết spec này ngày 17/11 (chỉ có `gold_labels_tai_76_100.json`). Muốn đo lại thì phải lấy file gộp từ máy đã chạy ngày 11/11.
- Test: `tests/unit/test_sections.py`, `test_skills_ac.py`, `test_tokenize.py`, `test_ph8_run.py`, `test_processing_10_12.py`, `test_embed.py`, `test_eval_gold_processing.py`.

## 6. Chỗ lệch cần biết

| Chỗ lệch | Ảnh hưởng | Xử lý |
|---|---|---|
| Chưa có `section_headings.json`, `priority_cues.json`, `short_aliases.json` đã duyệt | 07 chỉ tách theo trường nguồn; không có `uu_tien`, nên mọi kỹ năng đều `required` (`required_ratio` gần như luôn 1); alias ngắn (C, R, Go, BI) không bao giờ được bắt | PRE-33: người dùng duyệt từ điển. SD2 và SD5 cần phân biệt bắt buộc và ưu tiên |
| Hai từ điển kỹ năng: `preprocessing/dictionaries/skills.json` (03 T7 → `skills_std`) và `processing/dictionaries/skills_taxonomy_230.json` (08 → `skill__*`) | `skills_std` của bảng 04 và cột `skill__*` của bước 10 có thể khác nhau cho cùng một tin | PRE-40: chọn một nguồn kỹ năng cho SD1–SD5 (đề xuất: 08), hoặc đồng bộ hai từ điển |
| Report 07, 08, 09, 10, 12 có `rules` rỗng; 12_e5 ghi `api.used = false` dù gọi e5; 07–09 ghi "pipeline không dùng model" | Monitoring không thấy luật nào; khối model sai cho 12_e5 | PRE-40: ghi luật S7, K8, W9, 10b vào `rules`; 12_e5 ghi tên model |
| `intfloat/multilingual-e5-base` không ghim commit; `pyahocorasick`, `underthesea` chưa ghim phiên bản | Chạy lại trên máy khác có thể ra vector hoặc token khác | PRE-40 |
| 10 lấy `posted_month` từ tháng của `posted_date` | Thiếu ở 36,2% số tin (topcv 0%) | PRE-37 việc 4 |
| 10 import hằng số từ `preprocessing/encoding/run.py` | Không xóa được `preprocessing/encoding/` dù bước 05 đã bỏ | PRE-39: chuyển 3 hằng số sang `processing/` trước khi dọn `encoding/` |
| 12_tfidf không có bên đọc | Tốn thời gian chạy; spec cũ ghi M3 dùng TF-IDF | Người dùng chốt bỏ 17/11 (mục 3.5); code chưa gỡ (MINE-7) |
| `processing/CLAUDE.md` cũ ghi "16 nhóm + Other", "Mining chỉ unsupervised" | Hướng dẫn sai | Đã sửa cùng chặng 3 |

## 7. Tài liệu đã gộp vào spec này

Nội dung còn đúng của các file dưới đây đã nằm trong spec này hoặc spec 05. Người dùng duyệt và các file đã bị xóa ngày 17/11/2026; muốn xem bản cũ thì dùng `git show <commit>:<đường dẫn>`.

- `docs/spec/preprocessing/spec/P5_encoding.md`, `PH8_tach_section_ky_nang_tach_tu.md`, `PH9_noi_pipeline_nghiem_thu.md` (phần driver và report đã ở spec 05 mục 2).
- `docs/spec/preprocessing/encoding/` (16 file nhật ký P5, quy trình duyệt cũ của `preprocessing/encoding/`, đã được bước 10 thay).
- `docs/prompting/draft/P5_encoding.md`, `docs/prompting/preprocessing/spec/P5_encoding.md`.
- Bản 2.0 của spec này: mục nhóm nghề, cấp bậc, lương, dịch đã chuyển sang spec 05; mục taxonomy kỹ năng 6 nhóm nay nằm trong `skills_taxonomy_230.json`.
