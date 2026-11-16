# processing/CLAUDE.md

Giai đoạn 3 của quy trình chuẩn: **Processing** (feature engineering + encoding). Đã có logic cho bước 07–09 (PH8) và 10–12 (viết 11/11/2026; chạy thật sau khi chuỗi 03→09 xong). Bước 11 (train/test) bỏ có chủ đích vì Mining unsupervised; không dùng `preprocessing/encoding/execute.py`. Pre-processing nằm ở `preprocessing/`; Mining ở `mining/` (chỉ unsupervised).

## Thư mục

| Thư mục | Việc (theo file thiết kế `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md`) | Bước thiết kế |
|---|---|---|
| `extraction/` | Tách section/bullet, trích kỹ năng (Aho-Corasick), vector hóa | 7, 8, 12 |
| `transformation/` | Tách từ, stopword, log lương, rời rạc hóa | 9, 10 |
| `selection/` | Chọn đặc trưng. Nội dung ngoài ngưỡng bỏ kỹ năng < 5 lần: **chưa chốt** | 10b |
| `construction/` | Xây đặc trưng mới. Danh sách: **chưa chốt** | 10c |
| `encoding/` | Multi-hot kỹ năng, ordinal cấp bậc, cờ nhị phân (đặc tả `docs/spec/preprocessing/spec/P5_encoding.md`) | 10d |

## Ranh giới

- Đầu vào: bảng đã qua Pre-processing (`data/preprocessing/04_normalization/all.parquet`). Đầu ra dự kiến ghi dưới `pipeline/` trên R2 (tên thư mục con chưa chốt) và `curated/`.
- Code đang chạy của Encoding vẫn ở `preprocessing/encoding/`, chưa chuyển sang đây; transformation/normalization cũng giữ nguyên ở `preprocessing/`. Chuyển dần theo từng phase để không vỡ pipeline và test hiện có.
- Không sửa giá trị đã chuẩn hóa ở giai đoạn trước; không đọc lại raw.
- Chỉ fit (TF-IDF, scaler, ngưỡng tần suất) trên dữ liệu thật, tái lập được (`random_state` cố định); không dữ liệu giả.
- Ghi lên R2 phải chạy thử và được người dùng đồng ý.

## Bước 10–12 (đã có code, 11/11/2026)

- `10_features` (`encoding/features.py::build_features`) gộp 10 rời rạc hóa (`transformation/discretize.py`: `salary_bin_range` theo `SALARY_EDGES_M`, `salary_bin_eqfreq5`, `exp_bin`; thiếu = -1), 10b chọn kỹ năng (`selection/sparsity.reduce_sparsity`, `min_df=15` mặc định, kỹ năng hiếm gom thành `other_skill`), 10c xây đặc trưng (`construction/features.py`: `n_skills`, `n_required`, `required_ratio`, `n_tokens`, `n_benefits`, `salary_mid`, `salary_range_ratio`; thiếu = NaN) và 10d mã hóa (multi-hot `skill__*`, `seniority_ord` -1 = chưa rõ, one-hot `fam__*` 16 nhóm + Other, `src__*`, `wm__*`, `emp__*` loại hình làm việc (luật từ khóa, không nhận ra = unknown), `tinh__*` multi-hot top 10 tỉnh theo mọi địa điểm + `other`/`unknown`, `loc_remote`, `loc_ngoai_vn`, số `log_salary_min/max`, `exp_min/max_years`, `headcount` kèm `__missing`, `posted_month`, `days_to_deadline` tính từ ngày cào, cờ). Không có `it_status` (cả 4.671 tin đều `it`, cột hằng) và `*_prob` (04 không có). Ra `data/processing/10_features/features.parquet` + `encoding_dictionary.json`, đúng số dòng bảng 04.
- Lương thỏa thuận và không ghi gộp thành `salary_status__unknown` (người dùng chốt 11/11); số lương không điền. Cờ `seniority_can_kiem` giữ thành cột, không bỏ dòng.
- `12_tfidf` (`extraction/vectorize.py`): TF-IDF 1–2 gram (bigram nối `|`), `min_df=5`, `max_features=20000`, fit trên toàn bộ (unsupervised) → `data/processing/12_tfidf/{tfidf.npz,vocab.json,job_ids.json}`.
- `12_e5` (`extraction/embed.py`): embedding từng bullet của bước 07 bằng `intfloat/multilingual-e5-base` (tiền tố `passage: `, fp16, GPU; cache theo `sha1(text)` chia shard ở `data/processing/12_e5/cache/`, chạy lại không tính lại). Ra `bullet_emb.npy` (float16), `bullet_index.parquet`, `job_emb.npz` (vector JD = trung bình mọi bullet `all` + trung bình theo 3 section `mo_ta/yeu_cau/phuc_loi`, `has` báo JD có section đó; JD không có bullet thì vector 0). Đo thử: ~40 ms/bullet trên Quadro T1000 (88.821 bullet duy nhất, khoảng 1 giờ).
- Các bước 10–12 nối vào `scripts/run_preprocessing.py` (`PROCESSING_STEPS`). Test: `tests/unit/test_processing_10_12.py`, `tests/unit/test_embed.py`.

## PH8 (đã có code)

- `extraction/sections.py`, `skills.py`, `run.py` (bước 07, 08); `transformation/tokenize.py`, `run.py` (bước 09); `selection/sparsity.py` (giảm thưa); `evaluate.py`; từ điển ở `dictionaries/`. Đặc tả: `docs/spec/preprocessing/spec/PH8_*.md` mục 11.
- Bẫy: quét kỹ năng trên văn bản fold với alias ngắn (`bi`, `ba`, `soc`, `c`) sinh nhiễu hàng loạt; chỉ alias >= 4 ký tự hoặc có `# + .` đi đường fold, alias ngắn đi đường hoa thường và phải `approved:true`. `*_candidates.json` không bao giờ được code đọc.
- `underthesea.word_tokenize` trả list, token ghép có dấu cách; token kỹ năng là `sk_<slug>` và không bị coi là stopword.
- Bước 08 quét cả văn bản gốc và bản dịch (`description_vi`, `requirements_vi`) với tin đã dịch; kỹ năng thêm từ bản dịch có `via="text_vi"` (`extraction/run.py::analyze`). Báo cáo `scripts/report_skills_overview.py` ghi `data/processing/skills_overview.html` (DF theo A/B, độ phủ, mức cắt min_df).
- Thư viện `pyahocorasick`, `underthesea` chưa ghim trong `requirements*.txt`; chưa có file nhãn gold nên chưa đo F1.
