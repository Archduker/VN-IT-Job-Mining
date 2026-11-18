# Đặc tả chi tiết từng bước Processing

> **Quan hệ với spec 06:** [`06_processing_spec.md`](../06_processing_spec.md) giữ hợp đồng chung (chuỗi bước, fit trên toàn bộ hay chỉ trên tập train, dùng model và từ điển, chỗ lệch). Các file ở đây là **đặc tả chi tiết** của từng bước: luật, quy trình theo thứ tự trong code, input → output, dữ liệu mẫu, kiểm tra. Mỗi luật chỉ ghi chi tiết ở một chỗ, là file của bước đó.
>
> **Khuôn và cách đọc** giống [`docs/spec/preprocessing/`](../preprocessing/README.md). Ngày viết: 18/11/2026.
>
> **Trạng thái số liệu:** pre-processing đang được chạy lại, nên bảng 04 sẽ đổi. Mọi số trong các file này là của **lần chạy 10–11/11/2026** (spec 06, `code_version` 37bb865, 4.671 tin), kèm nhãn "chưa chạy lại". Mục "Dữ liệu mẫu" để trống đến khi chạy lại trên bảng 04 mới; không có số nào ở đây được tính mới.

## Mục lục

| Bước | File | Code | Lần chạy thật gần nhất |
|---|---|---|---|
| 07 Sections | [`07_sections.md`](07_sections.md) | `processing/extraction/sections.py`, `run.py` | 10/11 (chưa chạy lại) |
| 08 Skills | [`08_skills.md`](08_skills.md) | `processing/extraction/skills.py`, `run.py`, `processing/selection/sparsity.py` | 10/11 (chưa chạy lại) |
| 09 Tokens | [`09_tokens.md`](09_tokens.md) | `processing/transformation/tokenize.py`, `run.py` | 10/11 (chưa chạy lại) |
| 10 Features (10, 10b, 10c, 10d) | [`10_features.md`](10_features.md) | `processing/encoding/features.py`, `transformation/discretize.py`, `selection/sparsity.py`, `construction/features.py` | 10–11/11 (chưa chạy lại) |
| 12_e5 | [`12_e5.md`](12_e5.md) | `processing/extraction/embed.py` | 10/11 (chưa chạy lại) |

Bước 11 (chia train/test theo công ty) **không nằm ở Processing**, mà ở M5 trong `mining/` (spec 06 mục 4). 12_tfidf đã bỏ ngày 17/11 (spec 06 mục 3.5).

## Khuôn của mỗi file

Mọi file bước dùng đúng 7 mục, theo thứ tự này:

1. **Mục đích**: SD được phục vụ và tiêu chí chất lượng.
2. **Luật**: bảng gồm mã, điều kiện, hành động; số tin của lần chạy thật. Mục 2.1 là luật đang chạy; mục 2.2 (nếu có) là **luật đề xuất, chờ người dùng duyệt**.
3. **Quy trình xử lý**: các bước đánh số đúng thứ tự thực thi trong code.
4. **Input → Output**: đường dẫn, định dạng, schema, report và file phụ.
5. **Dữ liệu mẫu**: điền khi chạy lại trên bảng 04 mới.
6. **Kiểm tra và nghiệm thu**: lệnh, ngưỡng, kết quả lần chạy gần nhất.
7. **Trạng thái, chỗ thiếu, việc mở**: mã PRE trong `docs/KNOWN_ISSUED.md`.

## Chuỗi bước và ranh giới

```text
data/preprocessing/04_normalization/all.parquet   (bảng sạch, spec 05)
  ▼ 07 sections   tách JD thành bullet, gán section
  ▼ 08 skills     trích kỹ năng trên từng bullet     (07 và 08 chạy trong cùng một lần gọi)
  ▼ 09 tokens     tách từ, bỏ stopword               (đọc bảng 04, tự gọi lại analyze của 07–08)
  ▼ 10 features   10 rời rạc hóa → 10b chọn kỹ năng → 10c xây đặc trưng → 10d mã hóa
  ▼ 12_e5         embedding bullet của 07 (cần GPU)
data/processing/<bước>/
```

- Lệnh chung: `python scripts/run_preprocessing.py --step all` (chạy chung chuỗi với pre-processing), hoặc `--step <bước>` cho một bước.
- **Không bỏ dòng:** mọi bước giữ đúng số tin của bảng 04 (12_e5 đếm theo bullet).
- **Không sửa giá trị đã chuẩn hóa** ở pre-processing, không đọc lại raw.
- Report ghi ở `reports/processing/<bước>/`; driver chép 07–09 sang `reports/preprocessing/<bước>/` cho Monitoring.
- Processing chỉ ghi trên máy; đẩy lên R2 thì theo spec 05 mục 2.1 (chạy thử trước, được người dùng đồng ý).
- `random_state` cố định, dữ liệu thật, không mock.

## Chọn đặc trưng và giảm chiều nằm ở đâu

Quy trình chuẩn của giai đoạn 3 có bốn việc: chọn, trích, biến đổi, xây đặc trưng, kèm mã hóa. Bảng dưới cho biết từng việc ở bước nào.

| Việc | Bước | Hiện trạng |
|---|---|---|
| Trích (extraction) | 07, 08, 12_e5 | Có. Section, kỹ năng, vector e5 |
| Biến đổi (transformation) | 09, 10 | Có. Tách từ; bin lương và kinh nghiệm |
| Xây (construction) | 10c | Có. 7 đặc trưng mới từ cột đã có |
| Mã hóa (encoding) | 10d | Có. Multi-hot, one-hot, ordinal, cờ |
| **Chọn đặc trưng (selection)** | **10b** | **Mới một phần:** chỉ gom kỹ năng DF < `min_df` (15). Chưa loại cột hằng, cột trùng thông tin. Xem [`10_features.md`](10_features.md) mục 2.2 |
| **Giảm chiều** | **Không nằm ở Processing** | Thuộc M3 trong `mining/` (`reduce_svd`, SVD/PCA), chạy ngay trước K-Means và HDBSCAN (SD3). SD2 chạy FP-Growth trực tiếp trên ma trận 0/1; SD4 dùng Random Forest nên không cần |

## Đầu ra Processing phục vụ SD nào

| Đầu ra | Bước | Bên đọc | SD |
|---|---|---|---|
| `07_sections/all.parquet` | 07 | 08, 09, 12_e5 | gián tiếp SD2, SD3 |
| `08_skills/job_skills.parquet` | 08 | 10; dự kiến M1 (nhu cầu kỹ năng tin người mới), M6 | SD1 (câu kỹ năng), SD2, SD4, SD5 |
| `09_tokens/all.parquet` | 09 | 10c (`n_tokens`) | gián tiếp |
| `10_features/features.parquet`, `encoding_dictionary.json` | 10 | M2 (`skill__*`), M3, M4, M5 | SD2, SD3, SD4, SD5 |
| `12_e5/job_emb.npz` | 12_e5 | M3, M4 | SD3 |

Nguồn kỹ năng của Mining là cột `skill__*` của bước 10, tức taxonomy 230 của bước 08. Không trộn với `skills_std` của bảng 04 (spec 07 mục 2, PRE-40).

## Việc chung còn mở

| Việc | Ảnh hưởng | Mã |
|---|---|---|
| Duyệt ba từ điển `section_headings`, `priority_cues`, `short_aliases` (hiện chỉ có bản `*_candidates.json`: 64, 40 và 49 mục, `skill_merge_candidates` rỗng) | 07 không có section `uu_tien`; 08 coi mọi kỹ năng là `required`; alias ngắn (C, R, Go, BI) không bắt được | PRE-33, PRE-40 |
| Hai từ điển kỹ năng | `skills_std` (bước 03) và `skill__*` (bước 10) khác nhau cho cùng một tin | PRE-40 |
| `posted_month` của bước 10 lấy từ tháng của `posted_date` | Thiếu ở 36,2% số tin | PRE-37 |
| Báo cáo thiếu `rules`; model e5, `pyahocorasick`, `underthesea` chưa ghim phiên bản | Monitoring không thấy luật; chạy lại trên máy khác có thể ra khác | PRE-40 |
| Import hằng số từ `preprocessing/encoding/run.py` (10) và danh sách stopword ở `preprocessing/encoding/assets/` (09) | Không dọn được `preprocessing/encoding/` | PRE-39 |
| Gỡ 12_tfidf (`processing/extraction/vectorize.py`, test, thư mục dữ liệu và report) | Code chết | MINE-7 |
