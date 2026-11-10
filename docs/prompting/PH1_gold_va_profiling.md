# Prompt PH1: profiling 8 nguồn và công cụ gán nhãn gold 100 JD

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/PH1_gold_va_profiling.md` (đã chốt 10/11/2026).
- `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` bước 0 và mục 4.1.
- `preprocessing/common/raw_reader.py` (đọc envelope mới nhất mỗi `job_id`), `preprocessing/integration/json_flattener.py` (`flatten_raw_job_record`).
- `scripts/label_tool.py`: chỉ tham khảo cách đọc dữ liệu và `REVIEW_DIR`; không tái dùng.
- `preprocessing/dictionaries/provinces_34.json`, `skills.json`.

Hiện tại: chưa có profiling; chưa có bộ gold. Dữ liệu sau Clean ở `data/preprocessing/02_integration/all.parquet`. Làm sau PH0 (gói đã cài).

## 2. Việc cần làm

**A. Profiling** (`scripts/profile_sources.py`, `--when before_clean|after_clean|both`, `--sample 500`, `--seed 42`, `--dry-run`)
- `before_clean`: đọc raw mới nhất mỗi `job_id` của từng nguồn, làm phẳng bằng `flatten_raw_job_record`, lấy ngẫu nhiên 500 tin (hoặc tất cả nếu ít hơn).
- `after_clean`: đọc `02_integration/all.parquet`, 500 tin mỗi `source_platform`.
- Đầu ra `reports/preprocessing/00_profiling/<when>/`: `missing_matrix.json` (tỉ lệ thiếu trường × nguồn), `missing_heatmap.html` (heatmap màu tự dựng, không cần thư viện ngoài; hiển thị được ở 390 px), `text_quality.json` (% còn HTML, % NFD, % không dấu theo nguồn), `profile_<nguồn>.html` từ `ydata-profiling` **nếu** chạy được (không thì bỏ, ghi lý do vào JSON).
- Số "trước xử lý" làm bảng so với "sau Clean".

**B. Mẫu gold** (`scripts/build_gold_sample.py --seed 42`)
- Lấy từ raw mới nhất mỗi `job_id`, **trước lọc IT**, chia 100 JD cho 8 nguồn (12–13 mỗi nguồn: nguồn đầu danh sách `SOURCES` nhận 13 cho đến khi đủ 100), ngẫu nhiên theo `seed`.
- Ghi `data/preprocessing/gold/gold_sample.json`: mỗi JD gồm `job_id`, `source`, `url`, tiêu đề, công ty, văn bản JD đã làm sạch HTML nhẹ (giữ xuống dòng, bullet), các trường thô (lương, kinh nghiệm, địa điểm) để bạn đối chiếu; và `seed`.
- Thư mục `data/preprocessing/gold/` git-ignore.

**C. Công cụ nhãn** (`scripts/gold_labeler.html`, một file, không máy chủ, không thư viện ngoài mạng)
- Nạp `gold_sample.json` bằng nút chọn file. Mỗi JD một màn: JD bên trái, biểu mẫu bên phải (xếp dọc ở 390 px).
- 7 trường nhãn theo bảng mục 3.2 của spec; **mọi trường bỏ qua được**, mỗi trường có trạng thái "chưa gán / không ghi / giá trị". Section: bôi đen đoạn trong JD rồi bấm nút section (5 nút). Kỹ năng: ô gõ có gợi ý từ `skills.json` nhúng sẵn vào file lúc build, mỗi kỹ năng chọn bắt buộc hay ưu tiên.
- Phím tắt (←/→ đổi JD, 1/2 IT/không IT), tiến độ x/100 và số trường đã gán, tự lưu `localStorage` mỗi thay đổi (bọc try/catch, vẫn chạy khi bị chặn), nút "Xuất JSON" tải `gold_labels.json`, nút "Nạp nhãn cũ".
- Nhúng danh sách 34 tỉnh và skills từ file từ điển bằng script build `scripts/build_gold_labeler.py` (sinh `gold_labeler.html` từ khuôn); hoặc viết tay file html và nhúng JSON bằng bước build. Chọn cách ít file nhất và nói rõ.

**D. Đọc và kiểm nhãn** (`preprocessing/common/gold.py`): `load_gold(path)` kiểm schema (trường bắt buộc, giá trị hợp lệ: 5 cấp bậc, 34 tỉnh, 5 section), trả `dict[job_id] -> nhãn`; báo cáo số JD đã gán từng trường. Chưa viết hàm đo bước nào.

## 3. Pseudo code

```text
profile(when, sample, seed):
    for nguồn in SOURCES:
        df = (flatten(raw_reader.latest(nguồn)) if before_clean else đọc 02_integration lọc nguồn)
        df = df.sample(min(sample, len(df)), random_state=seed)
        missing[nguồn] = {trường: tỉ lệ rỗng (None, "", "0", "Đang cập nhật" tính là rỗng, liệt kê quy ước vào JSON)}
        text[nguồn] = {html: % chứa thẻ <...> hoặc &entity;, nfd: % có ký tự tổ hợp (unicodedata.normalize("NFC", s) != s),
                       no_diacritic: % văn bản tiếng Việt không có ký tự có dấu}
    ghi json + heatmap html; thử ydata_profiling.ProfileReport(df, minimal=True) trong try, lỗi thì ghi lý do

build_sample(seed):
    pool = flatten(raw_reader.latest(nguồn)) mỗi nguồn
    quota = chia 100 cho 8 nguồn
    chọn theo random.Random(seed), ghi file; chạy lại cùng seed -> cùng job_id

load_gold(path): kiểm từng trường; sai giá trị -> ValueError nêu job_id và trường
```

## 4. Ràng buộc

- Chỉ đọc raw và `data/preprocessing/`; không sửa raw; không ghi R2; không tự gán nhãn thay người dùng; không dùng model.
- Không mock: dữ liệu thật. `--dry-run` của profiling chỉ in kế hoạch, không ghi.
- Không in nội dung JD ra log ngoài vài ví dụ ngắn.
- `reports/preprocessing/00_profiling/` đưa vào git; `data/preprocessing/gold/` thì không.
- Nếu `ydata-profiling` lỗi với pandas 3.1.1: **không** hạ pandas; bỏ ydata và ghi lý do.

## 5. Ví dụ (test kiểm)

```text
tỉ lệ thiếu: cột ["a","b"] giá trị [None,"x"],[ "Đang cập nhật","y"] -> a: 100%, b: 0%
NFD: "Việt" ghép dạng tổ hợp -> tính là NFD; "Việt" dạng dựng sẵn -> không
build_gold_sample(seed=42) hai lần -> cùng danh sách job_id; tổng 100; mỗi nguồn 12 hoặc 13
load_gold: cấp bậc "Guru" -> ValueError; tỉnh không trong 34 -> ValueError; trường để trống -> hợp lệ ("chưa gán")
gold_labeler.html: nạp mẫu 3 JD, gán IT cho JD 1, tải lại trang -> nhãn còn; "Xuất JSON" khớp schema load_gold
```

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit -q` | xanh |
| Profiling | `python scripts/profile_sources.py --when both --dry-run` rồi chạy thật | đủ 8 nguồn, 2 báo cáo, cùng seed cùng số |
| Mẫu | `python scripts/build_gold_sample.py --seed 42` | 100 JD, mỗi nguồn 12–13, cả JD ngoài IT và JD tiếng Anh |
| HTML | mở `gold_labeler.html`, gán thử, kiểm 390 px | không lỗi console, nhãn còn sau tải lại |
| Git | `git diff --stat` | không có file dữ liệu/ nhãn trong git ngoài `reports/preprocessing/00_profiling/` |
