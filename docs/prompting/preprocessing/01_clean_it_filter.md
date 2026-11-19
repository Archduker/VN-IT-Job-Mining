# Prompt 01 (bổ sung): Làm lại bộ lọc IT (C4a) bằng từ điển kỹ năng v2

> Đặc tả: [`docs/spec/preprocessing/01_clean.md`](../../spec/preprocessing/01_clean.md) dòng C4a (mục 2), mục 2.1 (định nghĩa "tin IT"), mục 6 (nghiệm thu).
> Kế hoạch: G0 đặc tả và prompt → G1 soát nhãn → G2 test rồi code → G3 dry-run → G4 chạy thật lần lượt. Mỗi giai đoạn dừng cho người dùng xem.
> **Trạng thái:** viết 19/11/2026, người dùng duyệt 19/11 cùng đặc tả.

## 1. Ngữ cảnh

**Đọc trước:**

- Đặc tả 01 mục 2, 2.1, 6, 7.
- Code:
  - `preprocessing/common/it_filter.py` (`classify`, `classify_unknown`, `STRONG_IT`, `NON_IT`, `TECH_SKILLS`);
  - `preprocessing/clean/run.py` (đoạn C4a trong `clean_source`, `review_sample`, `validation_metrics`);
  - `processing/extraction/skills.py` (`load_skills_v2`, `matcher_from_v2`);
  - `preprocessing/normalization/text_cleaner.py` (`classify_job_family_rule`).
- `preprocessing/clean/CLAUDE.md`: cách báo P/R, Wilson, không ghi đè file nhãn.
- Nhãn C4b: `data/preprocessing/review/it_<nguồn>.csv` (bản lưu trong git: `data/preprocessing/gold/it_review/`).

**Vì sao làm** (số đo 18–19/11):

| Vấn đề | Số liệu |
|---|---|
| Độ đúng chung chưa đạt 95% | 90,8% trên 643 nhãn (precision IT 86,5%, recall IT 80,4%) |
| Lỗi theo tầng | Tầng 1 sai 16 (giữ nhầm 11, bỏ nhầm 5); tầng 2 sai 43 (giữ nhầm 12, bỏ nhầm 31) |
| Tầng 2 dùng từ điển 40 kỹ năng cũ | Thiếu bảo mật, hạ tầng, vận hành; từ điển v2 (2.114 kỹ năng) đã duyệt 18/11 |
| Đo thử 240 tin tầng 2 | Luật cũ 0,821; chỉ đếm kỹ năng kỹ thuật v2: 0,40–0,80; luật cũ + "≥ 4 kỹ năng bảo mật": 0,85 |

**Quyết định của người dùng (19/11):**

- "Vai trò IT" là định nghĩa tin IT (đặc tả mục 2.1).
- Sales/marketing thuần, thiết kế đồ họa, kỹ sư điện/cơ khí "không phải là tin IT nha loại bỏ hoàn toàn".
- Chuyên mục sàn là tín hiệu phụ (phương án C).
- Ưu tiên precision (sạch).
- "phải gọi là không tự suy diễn": ca chưa rõ thì hỏi.

## 2. Việc cần sửa

**Input:**

- raw trên máy `data/<nguồn>/raw/` (qua `read_raw`, `flatten_raw_job_record`);
- nhãn C4b;
- `processing/dictionaries/skills_v2.json` (đã duyệt).

**Output:**

- `preprocessing/common/it_filter.py`: tầng 0 `excluded_role`, tầng 1 sửa từ khóa, tầng 2 mới.
- `preprocessing/dictionaries/it_filter_v2.json`: nhóm lõi IT, ngưỡng, từ khóa chuyên mục sàn, danh sách nhóm loại hoàn toàn và ngoại lệ, `approved`.
- `preprocessing/clean/run.py`: truyền `raw_category_text`; `it_rule_level` = 0 cho tầng 0.
- `scripts/eval_it_filter.py` (mới, chỉ đọc) → `data/preprocessing/review/it_filter_eval.json`.
- `data/preprocessing/gold/it_review/relabel_2026-11-19.csv` (nhãn đổi, chờ duyệt), `split_2026-11-19.csv` (tune / giữ lại).
- Test: `tests/unit/test_it_filter.py` (mới hoặc bổ sung), `tests/unit/test_clean_step.py` giữ xanh.

**Các việc, theo thứ tự:**

1. **G1 soát nhãn:**
   - Claude đọc lại 643 nhãn theo mục 2.1 và ghi nhãn đổi kèm lý do.
   - Ca chưa rõ ghi `can_hoi`, không tự suy diễn.
   - Người dùng duyệt rồi mới áp vào CSV (`nguoi_gan` = `claude_v2`).
   - Sau đó chia tune/giữ lại.
2. **G2:**
   - Viết `eval_it_filter.py` trước. Số luật cũ phải ra đúng 90,8% trên nhãn cũ.
   - Viết test, rồi code ba tầng.
   - Chạy lưới ngưỡng trên tập tune và gửi người dùng 3–5 phương án.
   - Người dùng chọn thì đặt `approved: true`.
3. **G3:** dry-run 01; liệt kê tin lật hai chiều.
4. **G4:** chạy thật 01 → 01b → 02, dừng xem; 03, 04, 07, 08 theo vòng riêng.

## 3. Pseudo code

```text
cfg = it_filter_v2.json (approved)          # chưa duyệt → dừng, báo "it_filter_v2.json chưa được duyệt"
M   = matcher_from_v2(load_skills_v2())     # dựng một lần

def excluded_role(title):                   # tầng 0
    t = norm(title)
    if khớp cfg.exceptions(t): return False  # ngoại lệ đã duyệt (vd presales kỹ thuật nếu người dùng chốt)
    return khớp cfg.excluded(t)              # sales/marketing thuần, thiết kế đồ họa, kỹ sư điện/cơ khí

def classify_it(title, signals, jd, category, source):
    if excluded_role(title):            return non_it, level 0
    r = classify(title, signals)         # tầng 1, từ khóa đã sửa
    if r != unknown:                    return r, level 1
    hits  = {h.slug for h in M.find(jd)}
    core  = |{s ∈ hits : group(s) ∈ cfg.core_groups}|
    sec   = |{s ∈ hits : group(s) == security}|
    fam   = classify_job_family_rule(title, ...)
    cat   = khớp cfg.category_terms(category)
    it = (fam and core ≥ cfg.k_fam) or sec ≥ cfg.k_sec or (cat and core ≥ cfg.k_cat[source])   # dạng luật; ngưỡng chọn ở G2
    return it ? it : non_it, level 2
```

## 4. Ràng buộc

- Không dùng model để phân loại; chỉ luật + từ điển. Nhãn Claude gán là để đo, không đổi kết quả lọc.
- **Không tự suy diễn:** ca định nghĩa chưa nói rõ (đặc tả mục 2.1, Q1–Q8) phải hỏi người dùng trước khi đưa vào luật hay nhãn.
- Không ghi đè cột `nhan_tay` khi chưa được duyệt. Không dựng lại mẫu C4b.
- Ngưỡng chỉ chọn trên tập tune. Số nghiệm thu báo trên tập giữ lại. Không chỉnh luật theo từng tin của tập giữ lại.
- Nhóm loại hoàn toàn: chuyên mục sàn và tên công ty không được cứu.
- Không đổi C1–C3, C5–C9, `it_policy.json`.
- Raw bất biến. Không đẩy R2. Không bật scheduler. Commit theo từng giai đoạn, chỉ file của việc đó. Không push.

## 5. Ví dụ (thành test)

Tin thật trong 643 nhãn C4b. Ca Q1–Q8 theo câu trả lời của người dùng 19/11 (đặc tả mục 2.1).

| Đầu vào (tiêu đề; tín hiệu) | Kết quả mong đợi |
|---|---|
| "Postsale Security Engineer"; JD có firewall, IDS/IPS, DLP, antivirus | `it` (tầng 2, tín hiệu bảo mật) |
| "Chuyên viên An Toàn Thông tin" | `it` ở tầng 1 (từ khóa "an toàn thông tin") |
| "Business Development"; công ty phần mềm, JD nhắc AWS/Azure/GCP | `non_it`, tầng 0 (sales thuần) |
| "Kỹ Sư Thiết Kế Điện" | `non_it`, tầng 0 (kỹ sư điện) |
| "Nhân Viên Thiết Kế Hệ Thống Điện, Điện Nhẹ, Hệ Thống Bms / Scada"; chuyên mục "IT Phần cứng - Mạng" | `non_it`, tầng 0; chuyên mục IT không cứu |
| "Nhân Viên Thiết Kế" (bao bì) | `non_it`, tầng 0 (thiết kế đồ họa) |
| "Backend Developer" | `it`, tầng 1 (không đổi so với luật cũ) |
| "Cloud Technical Sales / PreSales" (Q1) | `non_it`, tầng 0 |
| "Kỹ Sư IoT (IoT Engineer)" (Q4) | `non_it`, tầng 0 |
| "KỸ SƯ TỰ ĐỘNG HÓA"; JD có C++, Python, SQL (Q5) | `it` |
| "Chuyên viên phân tích định lượng - Nhóm Phân tích rủi ro" (Q6) | `it` |
| "Research and Teaching Assistant (RTA) in Business Analytics" (Q7) | `non_it`, tầng 0 |
| `it_filter_v2.json` có `approved` = false | Bước 01 dừng, báo "it_filter_v2.json chưa được duyệt" |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Nhãn đổi | Người dùng xem `relabel_2026-11-19.csv` | Người dùng duyệt từng dòng hoặc cả file |
| Đo lại luật cũ | `python scripts/eval_it_filter.py --rule old` | Ra đúng 90,8% trên nhãn cũ |
| Phương án luật | `python scripts/eval_it_filter.py --grid` (tập tune) | Bảng 3–5 phương án: precision IT, recall IT, độ đúng |
| Nghiệm thu | `python scripts/eval_it_filter.py --rule new --split holdout` | Precision IT + Wilson; đích ≥ 95%, chưa đạt thì báo thật |
| Test | `pytest tests/unit/test_it_filter.py tests/unit/test_clean_step.py -q` | Xanh |
| Dry-run | `python scripts/run_preprocessing.py --step clean --source all --dry-run` | Bảo toàn; danh sách tin lật hai chiều (30 mẫu mỗi chiều) cho người dùng xem |
| Chạy thật | `python scripts/run_preprocessing.py --step clean --source all`, rồi 01b, 02 | Số khớp đặc tả mục 2 (cập nhật sau khi chạy) |
| Ranh giới | `git diff --stat` | Không đụng raw, R2, `collection/` |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| — | Quyết định đầu vào | 19/11 | Người dùng: "oke làm lại lọc IT đi. Nhưng mà khi làm phải nhớ chỉnh lại tài liệu spec". Plan mode: chọn "Vai trò IT", "Tín hiệu phụ (C)", "Sạch (precision)". Góp ý kế hoạch: sales/marketing thuần, thiết kế đồ họa, kỹ sư điện/cơ khí "không phải là tin IT nha loại bỏ hoàn toàn"; "phải gọi là không tự suy diễn". Đo thử chỉ đọc trên 240 tin tầng 2 (số ở mục 1) | — |
| 1 | Duyệt đặc tả | 19/11 | Người dùng: "duyệt cả 2, Q5 IT, Q6 IT, còn lại không IT". Đặc tả 01 C4a, mục 2.1 cập nhật theo câu trả lời: presales, DPO/privacy, AV, nhúng/IoT, giảng dạy, vận hành/product growth vào nhóm loại hoàn toàn; tự động hóa và phân tích dữ liệu ngành khác là IT | c876901 + (commit này) |
| 2 | Duyệt prompt | 19/11 | Như trên | — |
| — | G1 soát nhãn | 19/11 | Claude đọc lại 643 nhãn: 22 đề xuất đổi + 24 tin trong 9 nhóm hỏi (H1–H9). Người dùng: "đồng ý 21 nhãn, trừ cái nhãn mới là it mà đánh giá độ tin cậy là thấp. H1,H6 IT, còn lại không IT". Áp 26 nhãn vào `it_*.csv` (cả bản làm việc và bản lưu); còn 168 IT, 475 không IT. Chia tune 451 / giữ lại 192 (phân tầng nguồn × nhãn, seed 42) | 9f2a51c, fbf7f5c |
| 3 | Test rồi code | 19/11 | Test trước: `tests/unit/test_it_filter.py` (27 test: ví dụ mục 5, Q1–Q8, H1/H6, cấu hình chưa duyệt dừng). Code: `it_filter.load_config`, `excluded_role` (tầng 0), `classify_tier1` (từ khóa sửa theo cấu hình, tag sàn qua alias skills_v2 thay `TECH_SKILLS`), `it_signals`, `tier2_decide`, `classify_it`; luật cũ giữ nguyên để đo. Thêm nhánh `k_core` (JD dày kỹ năng lõi, vd "Technical Leader" 17 kỹ năng) sau khi xem lỗi trên tập tune. `scripts/eval_it_filter.py`: luật cũ trên nhãn mới 92,1% (tune 91,6%, P_IT 0,81). Lưới 4.500 tổ hợp trên tune; phương án B (`k_fam` 2, `k_core` 8, itviec `k_cat` 0): tune đúng 0,951, P_IT 0,944; **giữ lại đúng 0,948 [0,907; 0,972], P_IT 0,976 [0,877; 0,996], R_IT 0,82**. Chờ người dùng chọn phương án và duyệt từ khóa tầng 0, ngoại lệ | c34a21c |
| 4 | Dry-run | 19/11 | Người dùng: "duyệt B với cả từ khóa, làm tiếp G3 đi". `it_filter_v2.json` duyệt (B), `clean/run.py` gọi `classify_it`. Dry-run bước 01 trong bộ nhớ (báo cáo ra thư mục tạm, không ghi `reports/`): đầu ra 4.621 → 4.103, bảo toàn đạt. 624 tin IT cũ thành `non_it` (tầng 0: 251, trong đó sales/marketing 77, nhúng/IoT 66, đồ họa 41, điện/cơ khí 36; tầng 1: 4; tầng 2: 369), 107 tin mới vào (tầng 1: 27, tầng 2: 80). Danh sách đầy đủ `data/preprocessing/review/it_filter_flips_2026-11-19.csv`. Chờ người dùng duyệt tin lật | 42423d5 |
| 5 | Review, chạy thật | 19/11 | Người dùng: "oke được á hãy chạy tiếp cho tui đi nhaa" (chấp nhận tin lật, giữ nguyên từ khóa). Chạy thật 01: 13.361 → 4.103 (C4a/C4c 6.050), bảo toàn đạt, khớp dry-run. Sinh lại `01_clean.html`, `samples/01_clean.json`. Đo lại: giữ lại đúng 94,8%, P_IT 97,6%; cả 643 đúng 95,0%. Tiếp theo 01b → 02 | d3f7008 |
| 5b | Chạy thật 01b, 02 | 19/11 | 01b: 4.103 → 3.998 (D5 bỏ 105, trước 125). 02: 3.998 → 3.997 (I6 bỏ 1). Bảo toàn đạt cả hai. Sinh lại trang và `samples/` của 01b, 02; sửa số trong đặc tả 01b, 02. Dừng trước 03 (chờ người dùng chọn chạy bản 03 hiện tại hay làm 03 mới) | (commit này) |
