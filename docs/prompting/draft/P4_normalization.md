# Prompt P4: Normalization (34 tỉnh, nhãn tiếng Việt, JEV, outlier, log, gộp nguồn)

> **Cập nhật 04/11/2026: dự án bỏ hẳn model/LLM (JEV qua OpenCode, Gemini).** Mọi đoạn trong file này nói về JEV, LLM, GenAI, dịch JD, `--use-api`, cache hay sổ tiền API đã hết hiệu lực. Thay bằng luật if-else: xem `docs/preprocessing/spec/P0_pipeline_contract.md` mục 6 và `docs/issue_log.md` L-28.

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
SENIORITY = ["Thực tập","Mới tốt nghiệp","Junior","Middle","Senior","Trưởng nhóm/Quản lý"]   # không xác định → null (để trống)
FAMILIES  = [12 nhóm trong đặc tả]                                                         # + "Khác"

process_source_records(source, rows, jev, dry_run):     # rows = một nhóm source_platform của 03_transformation/all.parquet
    N1: for loc in locations:
            p = province.lookup(loc.tinh_thanh or loc.raw)     # tên mới, tên cũ, bí danh, không dấu
            loc.tinh_key, loc.tinh_thanh = p.key, p.name if p else (None, None)
            loc.tinh_cu = tên gốc nếu khác p.name
            loc.remote = khớp "remote|từ xa"; loc.ngoai_vn = khớp danh sách nước ngoài
        tinh_chinh = tinh_thanh đầu tiên khác null trong locations
    N2: seniority, source = by_word(raw_seniority_text) or by_word(job_title_clean) or by_years(exp_min_years) or (None, None)
        # "Nhân viên", "Nhân viên/Chuyên viên", "Chuyên viên" không phải cấp bậc → bỏ qua, xét tiêu đề và số năm
    N3: job_family = luật từ nguyên vẹn trên title + skills_std, không ra → "Khác"
    N2b (JEV chỉ hỏi có/không, không dùng choice):
        nếu có nhãn: prob = jev.noul("<trường>_dung", "Tin này có <trường> là '<nhãn>' không?", state=title + 500 ký tự JD)
        <trường>_prob = prob; <trường>_can_kiem = prob < 0,5   # gắn cờ → mẫu gán nhãn tay → nhãn tay ghi đè
        nhãn luật giữ nguyên, JEV không tự đổi nhãn
    N4: skills_std = [SKILLS.canonical(s) for s in skills_clean], bỏ trùng
    N5: company_norm = normalize_company_name(company_name)

run(sources, dry_run, use_api):
    all = đọc 03_transformation/all.parquet; groupby source_platform → process_source_records
    N6a: lương tháng ngoài 1–500 triệu → NaN, salary_suspect = true (trước IQR)
    N6: fix_common_salary_input_errors → is_outlier_salary (IQR) → *_capped (winsorize 1–99%, ngưỡng tính trên all)
    N7: log_salary_* = log1p(*_capped)
    N9: tắt mặc định; --fuzzy-dedup chỉ ghi 30 cặp điểm cao vào báo cáo
    ghi 04_normalization/all.parquet. KHÔNG chép đè data/curated/curated_flat_golden_jobs.parquet (file của pipeline cũ)
```

## 4. Ràng buộc

- Không bỏ dòng. Không ghi đè cột cũ; `locations` chỉ được thêm khóa.
- N6 trước N7. Ngưỡng cap tính trên toàn bộ nguồn.
- Luật đưa nhãn, JEV chỉ kiểm có/không (`noul`) rồi gắn cờ `*_can_kiem`; không dùng `choice`, không để JEV tự gán nhãn. Không có nhãn thì để trống, không đoán.
- Nhãn giá trị viết tiếng Việt (thuật ngữ ngành giữ tiếng Anh), tên cột giữ tiếng Anh.
- Phường/xã đã được P3 đối chiếu `preprocessing/dictionaries/wards_34.json` (3.321 đơn vị mới). Không tự tải danh mục từ mạng lúc chạy.
- Không ghi vào `data/curated/`. Đẩy lên R2 là việc riêng, phải được bạn đồng ý.

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
| title "International Business Analyst", không có cấp bậc, không có số năm | `seniority=None` (để trống), không gọi JEV |
| `raw_seniority_text="Nhân viên"`, title "Kế toán", không có số năm | `seniority=None` |
| title "Senior Backend Developer", JEV noul trả 0,1 | `seniority="Senior"`, `seniority_prob=0.1`, `seniority_can_kiem=true` |
| title "Backend Developer" | "Backend", không ra BA |
| `skills_clean=["ReactJS","React.js"]` | `["React"]` |
| lương 400 triệu/tháng giữa các tin 10–50 triệu | `is_outlier_salary=true`, `*_capped` = mức 99% |
| lương 2,026 tỷ/tháng | `salary_suspect=true`, lương = NaN |

## 6. Cách review

- Tỉnh: bảng "chữ gốc → tỉnh chuẩn", lọc riêng các dòng tên cũ → tên mới; số `remote`, `ngoai_vn`, không nhận được. Bạn xem 20 dòng không nhận được.
- Nhóm nghề: 50 tin ngẫu nhiên (seed 42), bạn gán nhãn, đúng ≥ 90%; tách độ đúng phần luật và phần JEV. So số BA/Product với bộ golden cũ (1.214).
- Cấp bậc: bảng chéo `raw_seniority_text` × `seniority` cho VietnamWorks và TopCV.
- Lương: histogram trước/sau cap trên trang monitoring; số dòng không đổi.
- `--dry-run --use-api` trước để xem số lần gọi JEV và tiền.
