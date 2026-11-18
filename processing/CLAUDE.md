# processing/CLAUDE.md

Giai đoạn 3 của quy trình chuẩn: **Processing** (bước 07–12: tách section, trích kỹ năng, tách từ, ma trận đặc trưng, vector văn bản). Đặc tả chính thức: `docs/spec/06_processing_spec.md`. Vị trí trong quy trình: `docs/spec/03_data_mining_lifecycle.md` mục 3.2. Đầu vào là bảng sạch `data/preprocessing/04_normalization/all.parquet` (spec 05 mục 4). Bên dùng đầu ra là `mining/`, gồm cả phần không giám sát (SD2, SD3) và model lương (SD4, SD5).

## Thư mục và bước

| Bước | Code | Đầu ra (`data/processing/`) |
|---|---|---|
| 07 sections | `extraction/sections.py`, `extraction/run.py` | `07_sections/all.parquet` (một dòng một bullet) |
| 08 skills | `extraction/skills.py`, `extraction/run.py`, `selection/sparsity.py` | `08_skills/job_skills.parquet` |
| 09 tokens | `transformation/tokenize.py`, `transformation/run.py` | `09_tokens/all.parquet` |
| 10 features (10, 10b, 10c, 10d) | `encoding/features.py`, `transformation/discretize.py`, `selection/sparsity.py`, `construction/features.py` | `10_features/features.parquet`, `encoding_dictionary.json` |
| ~~12_tfidf~~ | `extraction/vectorize.py` | **Đã bỏ 17/11** (spec 06 mục 3.5); code còn, chờ gỡ (MINE-7). Không thêm bên đọc mới |
| 12_e5 | `extraction/embed.py` (cần GPU) | `12_e5/` |

- Chạy qua `scripts/run_preprocessing.py` (`PROCESSING_STEPS`). 07 và 08 chạy trong cùng một lần gọi. 09 đọc bảng 04 và tự gọi lại `analyze`, không đọc file của 07.
- Report ở `reports/processing/<bước>/`; driver chép 07–09 sang `reports/preprocessing/<bước>/` cho Monitoring.
- Đo trên gold: `processing/evaluate.py`, `scripts/eval_gold_processing.py`.
- **Bước 11 (chia train/test theo công ty) không nằm ở đây.** Nó là một phần của M5 trong `mining/` (SD4), spec 06 mục 4.

## Ranh giới

- Không bỏ dòng; mọi bước giữ đúng số tin của bảng 04.
- Không sửa giá trị đã chuẩn hóa ở pre-processing, không đọc lại raw.
- Fit (min_df, bin đều tần suất, stopword theo DF) hiện làm trên toàn bộ dữ liệu, đúng cho phần không giám sát. Đặc trưng nào dùng cho model lương thì M5 phải fit lại chỉ trên tập train. `salary_bin_*`, `salary_mid`, `salary_range_ratio` tính từ chính lương, nên không được làm đầu vào của model lương (spec 06 mục 2.2).
- Dữ liệu thật, tái lập được (`random_state` cố định); không dữ liệu giả. Ghi lên R2 phải chạy thử và được người dùng đồng ý.

## Bẫy

- **Từ 18/11 bước 08 đọc `dictionaries/skills_v2.json`** (K8.15, `skills.load_skills_v2` + `matcher_from_v2`; dừng nếu `approved` khác true). Sửa từ điển: sửa lô ở `dictionaries/skills_v2_decisions/`, chạy `scripts/build_skills_v2.py`, đo lại bằng `scripts/review_skills_v2.py`; không sửa tay file JSON. `approval.json` trong thư mục lô là dấu duyệt của người dùng. Khớp fold phải đúng dấu (`alias_forms`): thiếu luật này thì "công nghệ" khớp "nghe" ở 1.210 tin. Từ điển cũ `skills_taxonomy_230.json` chỉ còn cho test cũ và `scripts/ph8_measure.py`; chưa xóa khi người dùng chưa đồng ý.
- **Từ điển chỉ đọc bản đã duyệt.** Code đọc `dictionaries/section_headings.json`, `priority_cues.json`, `short_aliases.json`, chỉ mục `approved: true`. `*_candidates.json` không bao giờ được code đọc. Ba file đã duyệt hiện chưa tồn tại, nên chưa có section `uu_tien` và mọi kỹ năng đều `required` (PRE-40).
- Quét kỹ năng trên văn bản fold với alias ngắn (`bi`, `ba`, `soc`, `c`) sinh nhiễu hàng loạt. Chỉ alias ≥ 4 ký tự hoặc có `# + .` đi đường fold; alias ngắn đi đường phân biệt hoa thường và phải `approved: true`.
- Có hai từ điển kỹ năng: `preprocessing/dictionaries/skills.json` (bước 03 → `skills_std`) và `dictionaries/skills_taxonomy_230.json` (bước 08 → `skill__*`). Đừng trộn hai nguồn trong cùng một phân tích (PRE-40).
- `underthesea.word_tokenize` trả list, token ghép có dấu cách bên trong; token kỹ năng là `sk_<slug>` và không bao giờ bị coi là stopword.- 08 quét thêm bản dịch (`description_vi`, `requirements_vi`) với tin đã dịch; kỹ năng chỉ thấy trong bản dịch có `via = "text_vi"`. F1 trên gold chỉ tính `via = "text"`.
- `encoding/features.py` còn import `SENIORITY_MAP`, `TOP_PROVINCES_K`, `to_col_slug` từ `preprocessing/encoding/run.py`; dọn `preprocessing/encoding/` thì phải chuyển các hằng số này trước (PRE-39).
- Nhóm nghề là 10 nhóm + Other (`fam__*`, L-47). Đổi nhóm thì sửa `FAMILY_MAP` ở `preprocessing/normalization/job_title.py`, rồi chạy lại 04, 10 và Mining.
- `posted_month` của 10 đang lấy tháng từ `posted_date` (thiếu 36%); sẽ đổi sang cột `posted_month` của bảng 04 (PRE-37).
- 12_e5: cache theo `sha1(text)` ở `data/processing/12_e5/cache/`, chạy lại không tính lại; khoảng 40 ms/bullet trên Quadro T1000. Model chưa ghim commit (PRE-40).

## Việc còn mở

`docs/KNOWN_ISSUED.md`: PRE-33 (duyệt từ điển, chốt `min_df`, xem lại cách đo F1), PRE-34 (đánh giá 10–12, bullet careerviet thô), PRE-37 (`posted_month`), PRE-39 (dọn `preprocessing/encoding/`), PRE-40 (hai từ điển kỹ năng, report thiếu luật, ghim phiên bản).
