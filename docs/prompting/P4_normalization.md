# Prompt P4: Normalization (34 tỉnh, nhãn tiếng Việt, JEV, outlier, log, gộp nguồn)

## 1. Ngữ cảnh

Đọc trước:
- `docs/preprocessing/spec/P4_normalization.md`: N1–N9, bảng 34 tỉnh, 6 cấp bậc, 12 nhóm nghề.
- `docs/preprocessing/spec/P0_pipeline_contract.md` mục 6: JEV, cache, `--use-api`.
- `preprocessing/common/province.py`, `preprocessing/dictionaries/provinces_34.json` (từ P1).
- `preprocessing/normalization/text_cleaner.py`: `normalize_seniority`, `classify_job_family`.
- `preprocessing/missing_outlier/outlier_handler.py`, `preprocessing/normalization/log_transformer.py`, `cross_deduplicator.py`.

Code sửa PRE-1 (khớp từ nguyên vẹn) đang ở git stash "preprocessing: so khớp theo từ + chuẩn hóa sau imputer (hoãn)". Xem bằng `git stash show -p stash@{0}`, lấy phần khớp từ. Phần "chuẩn hóa sau imputer" không cần nữa vì đã bỏ imputer.

## 2. Việc cần sửa

- **Input:** `data/preprocessing/03_transformation/<nguồn>.parquet`.
- **Output:**
  - `data/preprocessing/04_normalization/<nguồn>.parquet` và `all.parquet`.
  - Chép `all.parquet` sang `data/curated/curated_flat_golden_jobs.parquet`.
  - Báo cáo bước kèm `_all.json`.
  - Code: `preprocessing/normalization/run.py` (mới).

## 3. Pseudo code

```text
SENIORITY = ["Thực tập","Mới tốt nghiệp","Junior","Middle","Senior","Trưởng nhóm/Quản lý"]   # + "Chưa rõ"
FAMILIES  = [12 nhóm trong đặc tả]                                                         # + "Khác"

run(source, dry_run, use_api):
    df = đọc parquet
    N1: for loc in locations:
            p = province.lookup(loc.tinh_thanh or loc.raw)     # tên mới, tên cũ, bí danh, không dấu
            loc.tinh_key, loc.tinh_thanh = p.key, p.name if p else (None, None)
            loc.tinh_cu = tên gốc nếu khác p.name
            loc.remote = khớp "remote|từ xa"; loc.ngoai_vn = khớp danh sách nước ngoài
        tinh_chinh = locations[0].tinh_thanh
    N2: seniority, source, prob = by_word(raw_seniority_text) or by_word(job_title_clean) or by_years(exp_min_years)
        if None and use_api: label, prob = jev.choice(SENIORITY, title + 500 ký tự JD); label = label if prob >= 0.5 else "Chưa rõ"
    N3: job_family tương tự: luật từ nguyên vẹn trên title + skills_std → jev.choice(FAMILIES + ["Khác"])
    N4: skills_std = [SKILLS.canonical(s) for s in skills_clean], bỏ trùng
    N5: company_norm = normalize_company_name(company_name)

run_all(dry_run, use_api):
    all = concat 8 nguồn                                           # N8
    N6: fix_common_salary_input_errors → is_outlier_salary (IQR) → *_capped (winsorize 1–99%, ngưỡng tính trên all)
    N7: log_salary_* = log1p(*_capped)
    N9: tắt mặc định; --fuzzy-dedup chỉ ghi 30 cặp điểm cao vào báo cáo
    ghi all.parquet; chép sang data/curated/curated_flat_golden_jobs.parquet
```

## 4. Ràng buộc

- Không bỏ dòng. Không ghi đè cột cũ; `locations` chỉ được thêm khóa.
- N6 trước N7. Ngưỡng cap tính trên toàn bộ nguồn.
- Luật chạy trước, JEV chỉ cho phần luật không ra. JEV chỉ chọn trong danh sách nhãn; prob < 0,5 thì "Chưa rõ" / "Khác".
- Nhãn giá trị viết tiếng Việt (thuật ngữ ngành giữ tiếng Anh), tên cột giữ tiếng Anh.
- Phường/xã không chuẩn hóa (chưa có danh mục). Không tự tải danh mục từ mạng.
- Chép sang `data/curated/` chỉ trên máy. Đẩy lên R2 là việc riêng, phải được bạn đồng ý.

## 5. Ví dụ (thành test, JEV mock)

| Đầu vào | Kết quả |
|---|---|
| `tinh_thanh="Ha Noi"` | `"TP. Hà Nội"`, `tinh_key="ha_noi"` |
| `"Bình Dương"` | `"TP. Hồ Chí Minh"`, `tinh_cu="Bình Dương"` |
| `"Quảng Nam"` | `"TP. Đà Nẵng"` |
| `"Hà Giang"` | `"Tuyên Quang"` |
| `raw="Remote"` | `tinh_thanh=None`, `remote=true` |
| `raw="Tokyo, Japan"` | `tinh_thanh=None`, `ngoai_vn=true` |
| `raw_seniority_text="Trưởng phòng"` | "Trưởng nhóm/Quản lý", `seniority_source="raw"` |
| title "Senior Java Developer" | "Senior", `title` |
| title "International Business Analyst", không có cấp bậc, không có số năm | không ra "Thực tập"; gọi JEV |
| JEV trả "Junior" prob 0,4 | "Chưa rõ" |
| title "Backend Developer" | "Backend", không ra BA |
| `skills_clean=["ReactJS","React.js"]` | `["React"]` |
| lương 2 tỷ/tháng giữa các tin 10–50 triệu | `is_outlier_salary=true`, `*_capped` = mức 99% |

## 6. Cách review

- Tỉnh: bảng "chữ gốc → tỉnh chuẩn", lọc riêng các dòng tên cũ → tên mới; số `remote`, `ngoai_vn`, không nhận được. Bạn xem 20 dòng không nhận được.
- Nhóm nghề: 50 tin ngẫu nhiên (seed 42), bạn gán nhãn, đúng ≥ 90%; tách độ đúng phần luật và phần JEV. So số BA/Product với bộ golden cũ (1.214).
- Cấp bậc: bảng chéo `raw_seniority_text` × `seniority` cho VietnamWorks và TopCV.
- Lương: histogram trước/sau cap trên trang monitoring; số dòng không đổi.
- `--dry-run --use-api` trước để xem số lần gọi JEV và tiền.
