# Prompt PH6: chuẩn hóa trường (bước 04) và gom chức danh về nhóm nghề

> **Nháp, chờ bạn duyệt.** Các điểm **[CẦN CHỐT]** `K1`-`K15` trong spec phải được chốt trước khi giao prompt này cho agent code, **nhất là K9 (taxonomy 12 nhóm)**, K4 (itviec), K5, K6. Chỗ nào prompt ghi "[ĐỀ XUẤT]" là mặc định nếu bạn không đổi.

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/PH6_chuan_hoa_truong.md` (mục 2 là hiện trạng đã đo; mục 3 là luật `N10`-`N19`; mục 6 là điểm chờ chốt).
- `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` bước 5 và bảng 3.3.
- `docs/spec/01_product_spec.md` mục 4.4 (12 nhóm nghề), `docs/spec/preprocessing/spec/P3_transformation.md` (T2, T4, T8), `P4_normalization.md` (N1-N9).
- Code: `preprocessing/normalization/run.py` (N1-N7), `normalization/text_cleaner.py` (`classify_seniority`, `classify_job_family_rule`, `FAMILY_RULES`, `has_term`), `normalization/cross_deduplicator.py` (`normalize_company_name`), `transformation/experience_parser.py`, `transformation/job_family_classifier.py` (`_FAMILY_RULES`, `_SKILL_GATES`), `transformation/salary_parser.py`, `missing_outlier/outlier_handler.py`, `common/province.py`, `common/step_report.py`, `preprocessing/dictionaries/abbreviations.json` (khuôn `approved`).

Hiện tại (đã đo 10/11/2026 bằng chạy bước 02 và 03 trong bộ nhớ trên `data/preprocessing/01_clean/*.jsonl`, 5.076 tin):
- Kinh nghiệm: 1.237 tin có chữ mà `exp_min_years` null (itviec 787: `3.1 năm (37 tháng)`, `0.8 năm (10 tháng)`, `5.1 năm (61 tháng)`; `Không yêu cầu` 393; `Dưới một năm kinh nghiệm` 45; `Lên đến N Năm` 9; `Hơn 5 năm` 2).
- Cấp bậc: bước 04 ra 6 nhãn (Thực tập, Mới tốt nghiệp, Junior, Middle, Senior, Trưởng nhóm/Quản lý), 44,4% nhãn do số năm tạo ra; chuẩn đích là 5 cấp.
- Địa điểm: `tinh_chinh` null 843 tin, trong đó 712 tin có `prov_key(raw_location_text)` ra tỉnh; chưa có cột hình thức làm việc.
- Nhóm nghề: có 3 danh sách 12 nhóm khác nhau (SPEC-01, `text_cleaner.JOB_FAMILIES`, `job_family_classifier.JOB_FAMILIES`); P4 xếp 398/585 tin Backend-theo-tiêu đề chỉ nhờ từ chung (`developer`, `software engineer`, `java`...); "Khác" 560 tin.
- Chức danh: `job_title_clean` có 4.223 giá trị khác nhau (4.106 sau casefold), 88% chỉ xuất hiện một lần; sau bỏ nhiễu còn 2.470; `rapidfuzz` gộp thêm chỉ xuống 2.215.
- Lương: `fix_common_salary_input_errors` chia 12 khi JD có chữ "năm" (sai cả 6 giá trị đo được); hằng 25.400 ở 2 nơi.
- Công ty: `company_norm` chưa có `rapidfuzz`; ngưỡng 90 gộp nhầm khoảng 6/23 nhóm.
- `rapidfuzz 3.14.6` đã có trong `.venv`; chưa có file nào import nó.

## 2. Việc cần sửa

Input: `data/preprocessing/03_transformation/all.parquet`. Output: `data/preprocessing/04_normalization/all.parquet` (thêm cột, không đổi cột cũ).

**A. Lương, kinh nghiệm (spec 3.1, 3.2)**
1. Một hằng `USD_VND = 25_400` (mục 3.1 N10a); `outlier_handler.py` import hằng này.
2. `fix_common_salary_input_errors`: bỏ hai nhánh (x 25.400 khi 100..10.000; chia 12 khi JD có "năm"). Hàm vẫn tồn tại (chữ ký giữ) trả đúng số vào; hoặc bỏ lời gọi ở `apply_global_salary_normalizations` (chọn một, ghi lý do). **Không** thêm nhánh sửa mới (PH7 M5 quyết).
3. `experience_parser.parse_experience_range`: thêm N11a-N11d và status mới. N11e (itviec) theo K4; nếu K4 chưa chốt thì chỉ ghi `status="compound_years_months"` kèm `exp_min = số năm` và cờ trong `flags`.

**B. Cấp bậc, địa điểm (spec 3.3, 3.4)**
4. `classify_seniority`: trả 5 nhãn `Intern/Fresher`, `Junior`, `Middle`, `Senior`, `Lead/Manager`; chỉ hai tầng `raw` và `title`; **bỏ tầng số năm** (PH7 M3c làm lại). Thêm `seniority_level` 0-4. Bỏ bộ hằng thừa của `experience_parser.SENIORITY_LEVELS` khỏi luồng (không xóa file, không đổi test cũ ngoài phần nhãn).
5. `_normalize_locations`: thêm fallback N13 (thử `raw_location_text` toàn chuỗi, rồi `company_address`) khi mọi phần tử không ra tỉnh. Ghi `tinh_source`.
6. Cột `work_mode` (N14) theo K8.

**C. Chức danh, nhóm nghề (spec 3.5, 3.6): phần mới**
7. `preprocessing/normalization/job_title.py` (mới) với:
   - `core_title(title_clean) -> (core: str, level: str | None, tech_hint: list[str])` thực hiện N15a-N15f. Bất biến: không bao giờ đổi `job_title_clean`.
   - `load_title_dict() -> dict` đọc `preprocessing/dictionaries/job_titles.json`, **chỉ dùng các mục `approved: true`**.
   - `canonical_title(core_fold, title_dict) -> (canonical | None, source, score | None)`: exact -> alias (`has_term`) -> fuzzy (`rapidfuzz.process.extractOne`, `scorer=fuzz.token_set_ratio`, `score_cutoff=T`, độ dài >= 8).
   - `family_from_title(core_fold, canonical, skills_std) -> (family, source)` theo N17 (thứ tự canonical -> từ khóa tiêu đề thu hẹp -> kỹ năng cổng -> `Other`).
8. `preprocessing/dictionaries/job_titles.json` (mới) **chỉ chứa mục đã được bạn duyệt** (K9). Nếu chưa có danh sách duyệt: tạo file có `entries: []`, chỉ viết hàm và test bằng từ điển dựng trong test. Viết thêm `scripts/count_title_candidates.py` (chỉ đọc, không ghi file dữ liệu) in ra chức danh lõi tần suất >= N (tham số `--min-count`, mặc định 5) để bạn duyệt; **script này không tự thêm mục nào vào từ điển**.
9. `text_cleaner.classify_job_family_rule` và `FAMILY_RULES`: đổi sang danh sách 12 nhóm theo K9, từ khóa Backend thu hẹp (bỏ `developer`, `software engineer`, `lập trình viên`, `java`, `python`, `node`... khỏi **luật tiêu đề**; giữ chúng chỉ như tín hiệu kỹ năng ở bước 3). Giữ thứ tự "đặc thù trước, chung sau" (Embedded, Security, QA, BA/Product, DevOps, System, Data, Mobile, Frontend, Backend). Nhóm không xếp được là `Other`, **không phải "Khác"**. Không xóa `job_family_classifier.py` (module riêng, có test); ghi vào spec (không sửa code) rằng hai module chưa gộp.

**D. Công ty, ngày (spec 3.7, 3.8)**
10. `company_key` (N18): chuẩn hóa dấu thanh, so khớp `rapidfuzz` trên các `company_norm` khác nhau của cả bảng; tự động gộp khi `token_sort_ratio >= 90` **và** (một tên là tập con từ của tên kia **hoặc** bằng nhau sau khi bỏ khoảng trắng). Cặp còn lại đạt >= 90: ghi `data/preprocessing/review/company_pairs.csv` (cột: `a`, `b`, `score`, `decision` để trống; file đã có `decision` do tay thì **không ghi đè** nhãn cũ, khuôn như `it_<nguồn>.csv`). `company_norm` rỗng -> `company_key = null`.
11. Ngày (N19): kiểm `date_parser.py`; thêm ngày tương đối chỉ khi hàm hiện tại chưa có (đọc trước); không đổi `deadline_before_crawl`.

**E. Báo cáo**
12. Luật `N10`-`N19`; `extra.field_parse`, `extra.title_taxonomy`, `extra.other_samples` (mục 4 spec). Phân bố `job_family`, `seniority` theo nguồn. `dry-run` vẫn tính và ghi báo cáo, không ghi parquet.

## 3. Pseudo code

```text
# 04 normalization, thêm vào process_source_records (mỗi tin, theo thứ tự)
title_core, lvl_in_title, tech_hint = core_title(rec.job_title_clean)
rec.job_title_core, rec.title_tech_hint = title_core, tech_hint

# N12 cấp bậc (chỉ raw, title)
sen, src = classify_seniority(rec.raw_seniority_text, title_core_with_level or job_title_clean)
rec.seniority, rec.seniority_source, rec.seniority_level = sen, src, level_of(sen)

# N13 tỉnh
locs, tinh = _normalize_locations(rec.locations)
if tinh is None:
    tinh = prov_name(prov_key(rec.raw_location_text)) or prov_name(prov_key(rec.company_address))
    rec.tinh_source = "raw_location_full" if ...
rec.tinh_chinh = tinh
rec.work_mode = work_mode(locs, rec.job_title_clean, rec.raw_location_text)   # K8

# N16-N17 chức danh -> nhóm
canon, csrc, score = canonical_title(fold(title_core), TITLE_DICT)
fam, fsrc = family_from_title(fold(title_core), canon, skills_std)
rec.title_canonical, rec.title_canonical_source, rec.title_match_score = canon, csrc, score
rec.job_family, rec.job_family_source = fam or "Other", fsrc or "none"

canonical_title(core_fold, d):
    if core_fold in d.exact: return d.exact[core_fold], "exact", None
    for entry in d.entries: if has_term(core_fold, entry.aliases): return entry.canonical, "alias", None
    if len(core_fold) >= 8:
        m = rapidfuzz.process.extractOne(core_fold, d.alias_fold_list, scorer=fuzz.token_set_ratio, score_cutoff=T)
        if m: return d.canonical_of[m[0]], "fuzzy", m[1]
    return None, "none", None

family_from_title(core_fold, canon, skills):
    if canon: return d.family_of[canon], "canonical"
    for family, kws in FAMILY_RULES_NARROW: if has_term(core_fold, kws): return family, "title"
    gated = [f for f, gate in SKILL_GATES if len(skills & gate) >= 2]
    if len(gated) == 1: return gated[0], "skills"
    return None, "none"          # nhiều nhóm hòa: Other (K11)

# sau vòng lặp (cả bảng gộp 8 nguồn)
company_key = cluster(company_norm_list)        # N18, ổn định: đại diện = tên ngắn nhất, hòa theo thứ tự chữ
write company_pairs.csv (cặp >= 90 chưa tự gộp)
```

## 4. Ràng buộc

- Không sửa raw, không sửa `raw_*`, `job_title`, `job_title_clean`, `salary_min_vnd`, `salary_max_vnd`; chỉ thêm cột. Không bỏ dòng (`rows_out = rows_in`).
- **Không model**: chỉ `rapidfuzz` + từ điển + regex. Không cài gói. Không động tới R2. Không commit.
- Không điền, không suy (PH7): không suy cấp từ số năm, không suy kinh nghiệm từ cấp bậc, không gắn cờ ngoại lai.
- Không tự thêm chức danh chuẩn vào `job_titles.json`; mục chưa `approved: true` không được nạp. Không đưa nội dung JD vào `reports/`.
- Test không dùng dữ liệu giả: chuỗi thật lấy từ `data/preprocessing/01_clean/*.jsonl` hoặc `tests/fixtures/<nguồn>/` (ghi `job_id` nguồn trong chú thích test). Với từ điển chức danh, test dựng từ điển nhỏ gồm các chức danh thật nêu ở mục 5.
- Sửa test cũ nào khẳng định hành vi sai (`classify_seniority` 6 nhãn, "Khác", chia 12) thì ghi lý do; sửa `tests/unit/test_normalization_step.py` cho nhãn mới.
- Sau khi xong: ghi lỗi vào `docs/issue_log.md` (mã `L-` kế tiếp): chia 12 sai, Backend hút Embedded, thiết kế đồ họa vào UI/UX, N1 bỏ sót 712 tin có tỉnh.

## 5. Ví dụ (thành test)

| Đầu vào (thật) | Kết quả mong đợi |
|---|---|
| `raw_experience_text="Không yêu cầu"` (jobsgo, topcv) | `exp_min=0`, `status=explicit_zero` |
| `"Dưới một năm kinh nghiệm"` (glints) | `(0, 1)` |
| `"Lên đến 2 Năm"` (careerviet) | `(0, 2)` |
| `"Hơn 5 năm"` (careerviet) | `(5, None)` |
| `"3.1 năm (37 tháng)"` (itviec) | theo K4; mặc định `(3.1, None)` + status `compound_years_months` |
| vietnamworks `raw_salary_text="8000 - 9000 USD"` | `salary_min/max` = 203.200.000 / 228.600.000 sau cả bước 04 (không còn 16,9 triệu) |
| `raw_seniority_text="Thực Tập Sinh"` | `seniority="Intern/Fresher"`, `source="raw"` |
| `raw_seniority_text="Nhân viên"`, `job_title="Senior DevOps Engineer"` | `Senior`, `source="title"` |
| `raw_seniority_text="Nhân viên"`, `job_title="Backend Developer"`, `exp_min=3` | `seniority=None` (không suy từ số năm ở PH6) |
| `job_title="Project Manager"` (K6) | không tự thành `Lead/Manager`; `job_family` Product/Project |
| `raw_location_text="Tòa nhà MB, số 18 Lê Văn Lương, Phường Yên Hòa, Hà Nội"` (locations không ra tỉnh) | `tinh_chinh="TP. Hà Nội"`, `tinh_source="raw_location_full"` |
| `raw_location_text="Remote"` | `work_mode="remote"` |
| `job_title_clean="[All level] BackEnd Engineer (Java, Spring Boot) - Khối Công nghệ thông tin (2025TD1785)"` | `core="BackEnd Engineer"`, `tech_hint=["Java","Spring Boot"]`, `job_family=Backend`, `job_title_clean` không đổi |
| `"Nhân Viên IT- Thu Nhập 15-35 Triệu- Tại Hải Phòng"` | `core="IT"` (sau bỏ tiền tố), `title_canonical=None`, `job_family=Other` |
| `"Middle/Senior Embedded Software Engineer (C++,C)"` | `job_family=Embedded/IoT` (nếu K9=A) **không** `Backend` |
| `"Nhân Viên Thiết Kế"` (đồ họa) | `job_family=Other`, **không** UI/UX |
| `"Tuyển Gấp- Junior QA Automation Engineer (M/f/d)"` | `core="QA Automation Engineer"`, `seniority=Junior`(title), `job_family=QA/QC` |
| từ điển test `{"Business Analyst": ["business analyst","ba","phân tích nghiệp vụ"]}` và `"Chuyên viên phân tích nghiệp vụ"` | `title_canonical="Business Analyst"`, source `alias` |
| cùng từ điển, `"Busines Analyst"` (lỗi gõ, dựng từ chuỗi thật `"Business Analyst"` bỏ 1 chữ) | `fuzzy`, `title_match_score >= T` |
| `"ba"` đứng một mình, độ dài 2 | không đi qua `fuzzy` (độ dài < 8); chỉ `exact` |
| `company_norm`: `"công nghệ quảng ích"` / `"công nghệ quảng ích qig"` (thật) | cùng `company_key` |
| `"sotatek"` / `"statek"`; `"công nghệ dtg"` / `"công nghệ itg"` (thật) | **không** tự gộp; vào `company_pairs.csv` |
| `company_name` rỗng | `company_key=null` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit -q` | xanh |
| Bảo toàn | `python scripts/run_preprocessing.py --step normalization --source all --dry-run` | `rows_in = rows_out`, `dropped = 0` |
| Kinh nghiệm | báo cáo `extra.field_parse` | tin có chữ mà `exp_min` null: 1.237 -> giảm theo spec mục 7; liệt kê chuỗi còn lại |
| Cấp bậc | phân bố 5 nhãn x nguồn x `seniority_source` | chỉ `raw`/`title`; không `Thực tập`, `Mới tốt nghiệp`, `Trưởng nhóm/Quản lý` |
| Tỉnh | `tinh_chinh` null trước/sau | 843 -> khoảng 117 |
| Nhóm nghề | bảng phân bố 12 + `Other` so P4 (Backend 856...) | `Embedded` có tin; đọc 30 tin Backend-theo-tiêu đề cũ nay đổi nhóm |
| Chức danh | `extra.title_taxonomy` | in đủ số; 4.106 -> `job_title_core` ~2.470 (ghi số thật) |
| Công ty | `company_pairs.csv` | các cặp nhầm trong spec 2.6 có mặt trong file, không bị gộp |
| Đọc tay | bạn chấm 50 chuỗi thật mỗi parser (lương, kinh nghiệm, cấp bậc, tỉnh) và 50 tin nhóm nghề (`data/preprocessing/review/family_50.csv`, seed 42) | parser >= 95%; nhóm nghề >= 90% |
| `title_canonical` | 50 tin có `canonical != null`, seed 42 | precision >= 95% (K13) |
| Git | `git status`, `git diff --stat` | không đụng `collection/`, R2, raw; không file dữ liệu/`review/` trong git; không đổi tên cột đã có |
