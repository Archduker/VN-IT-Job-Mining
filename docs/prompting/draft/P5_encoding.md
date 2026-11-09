# Prompt P5: Encoding (bảng số cho mô hình)

## 1. Ngữ cảnh

Đọc trước: `docs/spec/preprocessing/spec/P5_encoding.md` (luật E1–E7).

Bộ golden (P4) là bảng chữ đã chuẩn hóa. P5 đổi bộ golden sang bảng toàn số, kèm từ điển để giải mã ngược. Bộ golden giữ nguyên.

## 2. Việc cần sửa

- **Input:** `data/preprocessing/04_normalization/all.parquet`.
- **Output:**
  - `data/preprocessing/05_encoding/features.parquet`.
  - `data/preprocessing/05_encoding/encoding_dictionary.json`.
  - `reports/preprocessing/05_encoding/_all.json`.
  - Code: `preprocessing/encoding/run.py` (mới).

## 3. Pseudo code

```text
SENIORITY_ORDER = ["Thực tập","Mới tốt nghiệp","Junior","Middle","Senior","Trưởng nhóm/Quản lý"]   # "Chưa rõ" = -1

run(dry_run):
    df = đọc all.parquet
    out = df[["job_id_global"]]
    E1: out.seniority_ord = SENIORITY_ORDER.index(v) or -1
    E2: one-hot job_family, source_platform, employment_type   (pandas.get_dummies, prefix "<cột>__", tên cột theo mã không dấu)
    E3: top_tinh = 10 tinh_key nhiều tin nhất (34 tỉnh); multi-hot "tinh__<key>"; còn lại tinh__other = 1; thêm remote, ngoai_vn
    E4: top_skills = kỹ năng có ≥ 20 tin, tối đa 200; multi-hot "skill__<tên>"; skills__other_count
    E5: giữ cột số; thêm "<cột>__missing" = isna
    E6: is_negotiable, is_outlier_salary → 0/1; it_status → one-hot
    E7: posted_month, days_to_deadline
    E8: it_prob, seniority_prob, job_family_prob giữ số + __missing
    dictionary = {cột_mã: {nguồn, cách, map, ngưỡng}}
    kiểm: mọi cột (trừ khóa) là số; len(out) == len(df)
```

## 4. Ràng buộc

- Không bỏ dòng, không đổi giá trị đã chuẩn hóa, không bù NaN.
- Ngưỡng (10 tỉnh, ≥ 20 tin, tối đa 200 kỹ năng) ghi trong từ điển, không viết cứng ở chỗ khác.
- Không mã hóa JD ở bước này.
- Không thêm thư viện mới (pandas đủ).

## 5. Ví dụ (thành test)

| Đầu vào | Kết quả |
|---|---|
| `seniority="Junior"` | `seniority_ord=2` |
| `seniority="Chưa rõ"` | `-1` |
| `tinh_key` của locations = `["ha_noi","can_tho"]`, `can_tho` không trong top 10 | `tinh__ha_noi=1`, `tinh__other=1` |
| `exp_min_years=NaN` | giữ NaN, `exp_min_years__missing=1` |
| `is_negotiable=True` | `1` |

## 6. Cách review

- Giải mã ngược 5 dòng ngẫu nhiên bằng từ điển, so với bộ golden.
- Xem số cột theo nhóm và độ thưa phần kỹ năng trên trang monitoring.
- Bạn quyết lại ngưỡng K kỹ năng sau khi xem phân bố.
