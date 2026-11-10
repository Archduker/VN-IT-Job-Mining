# processing/CLAUDE.md

Giai đoạn 3 của quy trình chuẩn: **Processing** (feature engineering + encoding). Hiện mới là khung, **chưa có logic**. Pre-processing nằm ở `preprocessing/`; Mining ở `mining/` (chỉ unsupervised).

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

## PH8 (đã có code)

- `extraction/sections.py`, `skills.py`, `run.py` (bước 07, 08); `transformation/tokenize.py`, `run.py` (bước 09); `selection/sparsity.py` (giảm thưa); `evaluate.py`; từ điển ở `dictionaries/`. Đặc tả: `docs/spec/preprocessing/spec/PH8_*.md` mục 11.
- Bẫy: quét kỹ năng trên văn bản fold với alias ngắn (`bi`, `ba`, `soc`, `c`) sinh nhiễu hàng loạt; chỉ alias >= 4 ký tự hoặc có `# + .` đi đường fold, alias ngắn đi đường hoa thường và phải `approved:true`. `*_candidates.json` không bao giờ được code đọc.
- `underthesea.word_tokenize` trả list, token ghép có dấu cách; token kỹ năng là `sk_<slug>` và không bị coi là stopword.
- Thư viện `pyahocorasick`, `underthesea` chưa ghim trong `requirements*.txt`; chưa có file nhãn gold nên chưa đo F1.
