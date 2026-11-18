# Bước 00: Profiling

> Code: `scripts/profile_sources.py` (`load_before`, `load_after`, `missing_rates`, `text_quality`, `heatmap_html`, `run`). Chỉ đọc.
> Lệnh: `python scripts/profile_sources.py --when before|after|both [--sample 500] [--seed 42] [--dry-run]`.
> Dữ liệu mẫu: chưa có cho lần chạy 18/11. Bước này chạy **sau** khi bước 03 mới chạy xong (mục 7).
> Prompt: gộp vào [`docs/prompting/preprocessing/04_normalization.md`](../../prompting/preprocessing/04_normalization.md), phần nghiệm thu cuối chuỗi.

## 1. Mục đích

- Đo hiện trạng **trước** (raw) và **sau** làm sạch (bảng 03) cho cả 8 nguồn, để báo cáo có bảng "trước và sau".
- Hai thứ được đo: tỷ lệ thiếu của từng trường, và chất lượng văn bản (còn HTML, còn dạng Unicode NFD, còn ký tự ẩn, tỷ lệ tiếng Việt không dấu).
- Tiêu chí: là bằng chứng cho **completeness** và **accuracy** của chữ. Không SD nào đọc trực tiếp kết quả bước này.

## 2. Luật

| Mã | Luật |
|---|---|
| P1 | Lấy mẫu 500 tin mỗi nguồn, seed 42. Nguồn nhỏ hơn thì lấy hết |
| P2 | Quy ước rỗng: None/NaN, chuỗi rỗng, "0", "Đang cập nhật", "None", danh sách rỗng (`EMPTY_TOKENS`) |
| P3 | Chất lượng văn bản: tỷ lệ còn thẻ HTML hoặc entity (`TAG`), còn NFD, còn ký tự ẩn, tiếng Việt không dấu (heuristic `VI_ASCII_MARK`) |
| P4 | Nếu ydata-profiling không chạy được thì chỉ làm heatmap và các tỷ lệ bằng pandas |

## 3. Quy trình xử lý

1. `--when before`: `load_before(nguồn)` lấy raw mới nhất của mỗi `job_id` và làm phẳng trong bộ nhớ, đo trên cột `job_title`, `raw_description_text`, `raw_requirements_text`.
2. `--when after`: `load_after(nguồn)` đọc `data/preprocessing/03_transformation/all.parquet`, lọc theo nguồn, đo trên cột `job_title_clean`, `description_clean`, `requirements_clean`.
3. Lấy mẫu theo P1. `missing_rates` cho mọi cột, `text_quality` cho các cột văn bản.
4. Ghi `missing_matrix.json` (trường × nguồn), `missing_heatmap.html`, `text_quality.json`, và `profile_<nguồn>.html` nếu ydata-profiling chạy được.
5. `--dry-run` chỉ in, không ghi.

## 4. Input → Output

| | Đường dẫn |
|---|---|
| Input before | `data/<nguồn>/raw/` |
| Input after | `data/preprocessing/03_transformation/all.parquet` |
| Output | `reports/preprocessing/00_profiling/{before_clean,after_clean}/`: `missing_matrix.json`, `missing_heatmap.html`, `text_quality.json`, `profile_<nguồn>.html` |
| Dữ liệu | Không ghi dữ liệu |

## 5. Dữ liệu mẫu

Chưa có cho lần chạy 18/11. Sẽ điền khi chạy lại bước này sau 03 mới. Khuôn bảng cần điền:

| Nguồn | Trường | Thiếu trước (%) | Thiếu sau (%) | HTML trước → sau | NFD trước → sau |
|---|---|---|---|---|---|

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Đủ 8 nguồn ở cả before và after | 8/8 |
| Cùng seed thì ra cùng kết quả | So hai lần chạy, giống nhau (trừ thời điểm ghi) |
| Sau làm sạch | HTML 0%, NFD 0%, ký tự ẩn 0% (đích của 03 T6) |

## 7. Trạng thái, chỗ thiếu, việc mở

- **Trạng thái:** có code. Lần chạy gần nhất là 10/11, và bản `after_clean` khi đó đo trên bản 03 **cũ** (chạy lúc 11:54 UTC, trước lần chạy 03 lúc 19:54 UTC).
- **Việc phải làm:** chạy lại `--when both` sau khi bước 03 mới chạy xong (có dịch và trích JD), rồi điền mục 5.
- **Việc mở:** PRE-35.
