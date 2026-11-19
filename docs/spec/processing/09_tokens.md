# Bước 09: Tokens (**đã bỏ khỏi chuỗi 19/11/2026**)

> **Bỏ 19/11/2026** (kế hoạch yêu cầu dữ liệu P3, người dùng duyệt): bên đọc duy nhất là `n_tokens` của 10c, nay bước 10 tự đếm số từ của mô tả + yêu cầu (`processing/construction/features.py`, `word_count`). `09_tokens` không còn trong `PROCESSING_STEPS`; code `processing/transformation/` còn, chờ gỡ (PRE-39). Phần dưới là mô tả cũ.

> Code: `processing/transformation/tokenize.py` (`tokenize`, `domain_stopwords`, `load_general_stopwords`, `remove_stopwords`); `processing/transformation/run.py` (`run`).
> Lệnh: `python scripts/run_preprocessing.py --step tokens --source all [--dry-run]`.
> Dữ liệu mẫu: điền khi chạy lại trên bảng 04 mới.
> Số liệu trong file này là của lần chạy 10/11/2026 (**chưa chạy lại**).

## 1. Mục đích

Biến văn bản thành token sạch để đo độ dài JD (`n_tokens`, dùng ở 10c).

- Từ 17/11, khi bỏ 12_tfidf, **đây là bên đọc duy nhất** của bước 09. Nếu 10c không cần `n_tokens` thì có thể bỏ luôn bước này (PRE-34).
- Phục vụ SD gián tiếp: `n_tokens` là một đặc trưng mô tả của tin (SD3, SD4).
- Tiêu chí: **consistency** (cùng cách tách cho mọi sàn).
- Ranh giới: không bỏ dòng; không dùng model tải về (underthesea là luật + CRF đóng gói sẵn).

## 2. Luật

### 2.1. Luật đang chạy

| Mã | Điều kiện / cách làm | Hành động |
|---|---|---|
| W9.1 | Trước khi tách từ, thay mỗi kỹ năng đã khớp ở bước 08 bằng token giữ chỗ `sk_<slug>`, để tokenizer không cắt hỏng `C++` hay `Node.js` | modify |
| W9.2 | `underthesea.word_tokenize`, đưa về chữ thường (trừ token `sk_`). Token ghép giữ dấu cách bên trong | modify |
| W9.3 | Bỏ token chỉ gồm dấu câu hoặc ký hiệu (không có ký tự chữ hoặc số); giữ số | drop token |
| W9.4 | Bỏ stopword chung theo `preprocessing/encoding/assets/jd_stopwords_v1.json` | drop token |
| W9.5 | Bỏ stopword theo miền: token có mặt trong hơn 60% số tin (`df_threshold`). Token `sk_` không bao giờ bị coi là stopword | drop token |
| W9.6 | Bullet `phuc_loi` vẫn được tách từ nhưng không thay kỹ năng | modify |

Kết quả 10/11: 10 stopword theo miền (các, có, của, kinh nghiệm, làm việc, năm, theo, trong, và, với). Trung bình số token mỗi tin theo nguồn từ 245 (jobsgo) đến 440 (itviec).

### 2.2. Luật đề xuất

Chưa có. Câu hỏi mở: có cần giữ bước này không (xem mục 7).

## 3. Quy trình xử lý

Thứ tự trong `run` (`processing/transformation/run.py`):

1. Đọc bảng 04, lọc nguồn, sắp theo `job_id_global`.
2. Nạp từ điển đã duyệt như bước 07 và taxonomy như bước 08 (`default_matcher`).
3. Với mỗi tin, gọi lại `analyze` của 07–08 để lấy bullet và vị trí kỹ năng (`hits`). Bước này **không đọc file của 07**.
4. Với mỗi bullet: nếu không phải `phuc_loi` thì `tokenize(text, hits)` (W9.1–W9.3); nếu là `phuc_loi` thì `tokenize(text)` (W9.6). Nối token của mọi bullet thành `tokens` của tin.
5. `domain_stopwords` trên toàn bộ tin (W9.5); nạp stopword chung (W9.4).
6. `tokens_nostop = remove_stopwords(tokens, general, domain)`; `n_tokens = len(tokens)` (số token **trước** khi bỏ stopword).
7. Ghi `all.parquet`; ghi report theo nguồn và `_all`; kiểm `rows_conserved`.

## 4. Input → Output

| | Chi tiết |
|---|---|
| Input | Bảng 04 (qua `analyze`); `preprocessing/encoding/assets/jd_stopwords_v1.json` |
| Output | `data/processing/09_tokens/all.parquet`: `job_id_global`, `source_platform`, `tokens`, `tokens_nostop`, `n_tokens` |
| Report | `reports/processing/09_tokens/`; `extra`: `mean_tokens_per_job`, `df_threshold`, `n_general_stopwords`, `model` (ghi "không dùng model"); `_all` thêm `domain_stopwords` (token và DF) |

## 5. Dữ liệu mẫu

Điền khi chạy lại trên bảng 04 mới: một bullet trước và sau khi tách, có token `sk_` còn nguyên.

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách | Kết quả gần nhất |
|---|---|---|
| Số tin được giữ | `checks.rows_conserved` | Đạt (10/11) |
| Token `sk_` còn nguyên sau khi tách | `tests/unit/test_tokenize.py` | Pass |
| Danh sách stopword theo miền | Người dùng xem | Chưa duyệt chính thức |

## 7. Trạng thái, chỗ thiếu, việc mở

| Trạng thái | Có code, đã chạy thật 10/11 |
|---|---|
| Đánh giá | Chưa có (PRE-34) |

| Chỗ thiếu | Ảnh hưởng | Mã |
|---|---|---|
| Chỉ phục vụ `n_tokens` | Có thể bỏ cả bước nếu 10c không cần; cần người dùng quyết | PRE-34 |
| Stopword chung nằm ở `preprocessing/encoding/assets/` | Không dọn được `preprocessing/encoding/` | PRE-39 |
| `underthesea` chưa ghim phiên bản (máy dev dùng 9.5.0) | Chạy lại trên máy khác có thể ra token khác | PRE-40 |
| Report ghi "không dùng model", `rules` rỗng | Monitoring không thấy luật W9.x | PRE-40 |
