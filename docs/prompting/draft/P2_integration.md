# Prompt P2: Integration (làm phẳng về 18 trường)

## 1. Ngữ cảnh

Đọc trước:
- `docs/preprocessing/spec/P2_integration.md`: luật I1–I5, danh sách 18 trường.
- `preprocessing/integration/json_flattener.py`: các hàm `_flatten_itviec`, `_flatten_topdev`, `_flatten_careerviet`, `_flatten_jobsgo`.
- `monitoring/backend/app/core/feature_targets.py`: `RAW_PATHS`.

Hiện tại:
- ITviec có 855 tin với ngày đăng dạng tương đối.
- TopDev có ngày đăng 0%, kinh nghiệm 0,1%.
- CareerViet và JobsGO lấy sai trường kỹ năng (PRE-6).
- 6 trường dưới ngưỡng 3 nguồn bị bỏ.

## 2. Việc cần sửa

- **Input:** `data/preprocessing/01_clean/<nguồn>.jsonl`.
- **Output:**
  - **Một file** `data/preprocessing/02_integration/all.parquet` gộp 8 nguồn (cột `source_platform` giữ nguồn): khóa + `it_rule`, `it_prob`, `it_status`, `dedup_key`, `also_on` + 18 trường. Từ bước này trở đi không còn file theo nguồn.
  - `reports/preprocessing/02_integration/<nguồn>.json` (số theo nguồn) và `_all.json` (tổng, có `fields` gộp).
  - Code mới: `preprocessing/integration/run.py` (mới), sửa `json_flattener.py`.

## 3. Pseudo code

```text
KEEP = [18 trường trong đặc tả]

process_source(source, dry_run):
    report = StepReport("02_integration", source, mode)
    rows, bad = [], []
    for line in đọc jsonl:
        env = json.loads(line) hoặc: bad.append(dòng, lỗi); continue      # I0: drop, không được lặng lẽ bỏ
        flat = flatten_raw_job_record(env)                 # I1
        flat = {k: flat.get(k) for k in KEYS + KEEP} | env.metadata.clean
        flat = {k: None if là_trống(v) else v}             # I5
        rows.append(flat)
    report.fields = độ phủ từng trường (có/không có giá trị)
    report.input_rows = số dòng đọc; output_rows = len(rows); rule I0 drop = len(bad)
    return rows, report

run(sources, dry_run):
    rows_all = nối rows của 8 nguồn; total = merge_reports(...); total.check_conserved()
    ghi từng report nguồn, ghi all.parquet (nếu không dry-run), ghi _all

_flatten_itviec:    raw_posted_date = jsonld.datePosted or posted_at_raw       # I2
_flatten_topdev:    raw_posted_date = published.date or date_posted or jsonld.datePosted
                    raw_experience_text = jsonld.experienceRequirements or (giá trị cũ)   # I3
_flatten_careerviet, _flatten_jobsgo: skills_list = trường kỹ năng thật or []          # I4

Để đếm số dòng bị I2–I4 tác động (ghi vào rules), chạy flattener cũ và mới trên cùng envelope
rồi so: chỉ trong lúc chạy, không lưu flattener cũ thành code thứ hai.
```

## 4. Ràng buộc

- Không parse lương, ngày, số năm; không đổi tiền; không bù. Chỉ bỏ dòng JSON hỏng (I0), có đếm và ví dụ.
- Null trá hình ("0", "Đang cập nhật") giữ nguyên chữ; P3 mới đổi.
- Đổi tên trường thì sửa `RAW_PATHS` trong `feature_targets.py` cùng lúc.
- I4: ghi rõ trong báo cáo số tin có `skills_list` rỗng sau sửa. Kỹ năng từ JD do P3 (T7b) rút, không làm ở đây.
- Test cũ của flattener phải qua; test nào đang khẳng định hành vi sai thì sửa và ghi lý do.

## 5. Ví dụ (thành test)

| Đầu vào | Kết quả |
|---|---|
| ITviec `posted_at_raw="Đăng\n6 giờ trước"`, `job_posting_jsonld.datePosted="2026-11-01T03:00:00+07:00"` | `raw_posted_date="2026-11-01T03:00:00+07:00"` |
| TopDev `published.date="2026-10-28"`, `recalled_at=None` | `raw_posted_date="2026-10-28"` |
| TopDev `job_posting_jsonld.experienceRequirements={"monthsOfExperience":24}` | `raw_experience_text` có giá trị (giữ dạng chữ, vd. "24 months") |
| CareerViet chỉ có `job-tags` | `skills_list=[]` |
| `company_address=""` | `None` |
| envelope có `raw_age_text` | cột `raw_age_text` không có trong output |
| file jsonl có 3 dòng tốt + 1 dòng `{"hỏng":` | input 4, output 3, `dropped=[I0: 1]`, bảo toàn vẫn đúng |

## 6. Cách review

- Heatmap độ phủ trên trang `/preprocessing` bước 02: ITviec ngày đăng tuyệt đối ≥ 95%, TopDev ngày đăng > 0%.
- Bạn mở 5 tin ITviec, 5 tin TopDev trên trang web, so ngày đăng với cột mới.
- `rows_out = rows_in` cả 8 nguồn.
- Trang Raw (`/raw`) không lỗi sau khi sửa `RAW_PATHS`.
