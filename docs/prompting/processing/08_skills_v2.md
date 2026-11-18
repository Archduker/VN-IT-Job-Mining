# Prompt 08: Làm lại từ điển kỹ năng (skills_v2) và bước 08

> Đặc tả: [`docs/spec/processing/08_skills.md`](../../spec/processing/08_skills.md) mục 2.3 (K8.11–K8.16), K8.8, K8.9.
> **Trạng thái:** viết ngày 18/11/2026, **chờ người dùng duyệt** cùng đặc tả. Chưa viết code.
> Sau việc này: làm lại bộ lọc IT (bước 01 tầng 2 đếm kỹ năng theo từ điển), rồi chạy lại pre-processing và processing.

## 1. Ngữ cảnh

**Đọc trước:**

- Đặc tả 08 mục 2.1 (luật đang chạy), 2.3 (luật mới), 6 (đo trên gold).
- `docs/target/02_sd2_goi_ky_nang.md`, `05_sd5_lo_trinh_hoc.md`: SD2 và SD5 đọc ma trận kỹ năng.
- `preprocessing/CLAUDE.md`: khớp theo từ nguyên vẹn; tên kỹ năng ngắn (C, R, Go) chỉ thêm kèm ngữ cảnh; không dùng model để phân loại hay chuẩn hóa.
- Code: `processing/extraction/skills.py` (`SkillMatcher`, `extract_skills`, `load_taxonomy`), `processing/extraction/run.py`, `scripts/eval_gold_processing.py`; từ điển `processing/dictionaries/skills_taxonomy_230.json`, `preprocessing/dictionaries/skills.json`, các file `*_candidates.json`.
- Cách đã làm với từ điển JD (`scripts/mine_jd_phrases.py`, `scripts/review_jd_dictionary.py`, `preprocessing/dictionaries/jd_extraction.json`): gom ứng viên → Claude đọc → trang duyệt → người dùng duyệt.

**Vì sao làm** (số đo 18/11):

| Vấn đề | Số liệu |
|---|---|
| Hai từ điển lệch nhau | `skills.json` 40 kỹ năng (nguồn của Silver, SD1); taxonomy 230 (nguồn của SD2–SD5); 27 trùng |
| Tag của sàn không đều | careerviet, jobsgo 0%; topcv 54%; các sàn khác 80–100% |
| Tag lộn xộn | 5.389 tag khác nhau, 1.655 có DF ≥ 2; lẫn chức danh, ngành, kỹ năng mềm |
| Độ đúng | F1 0,27 trên 100 JD gold (đích ≥ 0,85) |
| Bộ lọc IT | 31/36 tin IT bị loại nhầm nằm ở tầng 2, vì JD không đủ 2 kỹ năng trong từ điển (thiếu bảo mật, hạ tầng, vận hành) |

**Quyết định của người dùng (18/11):**

- "tui cần phải làm lại cái việc chuẩn hoá các kỹ năng… phải phân tích jd rồi lấy kỹ năng nhưng mà phải đọc hết tất cả kỹ năng".
- Mức chi tiết: kỹ năng con riêng, trỏ về kỹ năng cha.
- Kỹ năng mềm, ngoại ngữ: giữ, gắn cờ.
- Phạm vi đọc: mọi ứng viên từ 2 tin trở lên.
- Một nguồn kỹ năng là bước 08 (K8.9); Silver lấy `skills` từ đây.

## 2. Việc cần sửa

**Input:** `data/preprocessing/02_integration/all.parquet` (4.495 tin; văn bản gốc) để gom ứng viên; bảng 04 + bullet của 07 khi chạy bước 08.

**Output:**

- `scripts/mine_skill_candidates.py` (mới, chỉ đọc) → `data/processing/skill_candidates/candidates.tsv` (ứng viên, DF tổng, DF theo nguồn a–d, DF theo sàn, 3 câu ví dụ).
- `processing/dictionaries/skills_v2.json` (mới) theo K8.11, `_meta.approved` false cho tới khi người dùng duyệt.
- `scripts/review_skills_v2.py` (mới, chỉ đọc) → `docs/presentation/processing_steps/skills_v2.html`.
- `processing/extraction/skills.py`, `run.py`: đọc `skills_v2.json`, thêm cột `kind`, `parent`; tag của sàn chỉ nhận khi khớp alias, bỏ tag trong `not_skill`.
- `scripts/eval_gold_processing.py`: so nhãn gold qua tên chuẩn và alias.

**Các việc, theo thứ tự:**

1. **K8.12:** viết `mine_skill_candidates.py`, chạy, báo số ứng viên theo nguồn. Dừng gửi số cho người dùng nếu tổng vượt 10.000.
2. **K8.13:** Claude đọc hết ứng viên theo lô khoảng 300 mục (DF giảm dần). Mỗi lô ghi thẳng vào `skills_v2.json` (bản nháp). Ghi số mục đã đọc ở `_meta.read_progress` để làm tiếp được nếu ngắt giữa chừng.
3. **K8.14:** sinh trang duyệt; gửi người dùng danh sách `can_hoi`.
4. Người dùng duyệt → `approved: true`.
5. **K8.15:** bước 08 dùng từ điển mới.
6. **K8.16:** đo trước/sau (F1 gold, tin không có kỹ năng, top 15 kỹ năng mỗi nghề).

## 3. Pseudo code

```text
# K8.12 gom ứng viên (bảng 02, mục yêu cầu + mô tả, văn bản gốc NFC)
for tin in 02:
    a = {tag.lower() for tag in skills_list} ∪ {nhãn trong category_tags}   # nhãn TopCV → gợi ý not_skill
    b = token/cụm 1–3 từ "dáng công nghệ" (số, # + . /, hoặc viết hoa giữa câu ≥ 60% số lần)
    c = cụm sau từ báo hiệu, tách theo , / và hoặc
    d = alias của taxonomy_230 và skills.json (chỉ đếm DF)
    cộng DF mỗi ứng viên một lần mỗi tin, theo nguồn và theo sàn; giữ 3 câu ví dụ (seed 42)
giữ ứng viên DF ≥ 2 → candidates.tsv

# K8.13 Claude đọc (không phải code tự động)
for lô in candidates (DF giảm dần, 300 mục):
    mỗi mục → skill mới {slug, name, group, kind, parent, aliases, short_aliases}
            | alias của slug X
            | not_skill {reason: job_title|industry|benefit|degree|generic}
            | can_hoi {lý do}
    ghi skills_v2.json, _meta.read_progress

# K8.15 bước 08
matcher = SkillMatcher(skills_v2)            # alias fold dài ≥ 4 hoặc có # + .; short_aliases hoa thường
for tin: như K8.4–K8.7; tag sàn: alias → slug (via=meta), not_skill → bỏ
ghi job_skills.parquet (+ kind, parent)
```

## 4. Ràng buộc

- Không dùng model để rút hay phân loại kỹ năng: chỉ từ điển + luật. Claude đọc ứng viên là bước lập từ điển, kết quả ghi vào file và người dùng duyệt; pipeline chạy không cần Claude.
- Khớp theo từ nguyên vẹn. Alias ngắn hoặc trùng từ thường (`go`, `r`, `c`, `bi`, `ba`) chỉ vào `short_aliases`, khớp hoa thường.
- Một alias chỉ thuộc một kỹ năng. Trùng thì Claude chọn và ghi vào `can_hoi`.
- `parent` chỉ một cấp cha cho mỗi kỹ năng; không có vòng.
- Chưa duyệt (`approved` khác true) thì bước 08 dừng và báo, giống `jd_extractor.load_rules`.
- Không sửa raw, không sửa bảng 02/04. Không xóa `skills_taxonomy_230.json` cho tới khi người dùng đồng ý.
- Không đẩy R2. Không push git. Commit theo từng việc.

## 5. Ví dụ (thành test)

| Đầu vào | Kết quả mong đợi |
|---|---|
| Bullet yêu cầu "Thành thạo ReactJS, React Native và Node.js" | `react` (required), `react_native` (parent `react`), `nodejs` |
| Bullet "Có kinh nghiệm với MySQL hoặc PostgreSQL" | `mysql`, `postgresql`, cả hai `parent` = `sql` |
| Tag topcv "IT - Phần mềm" (ở `category_tags`) | Không thành kỹ năng (`not_skill`, `industry`) |
| Tag itviec "Team Leadership" | `leadership`, `kind` = `soft` |
| Bullet "Tiếng Anh giao tiếp tốt" | `english`, `kind` = `language` |
| Bullet "Kinh nghiệm Go hoặc Rust" (chữ "Go" viết hoa) | `golang`, `rust`; câu "sẵn sàng go-live" không ra `golang` |
| Từ điển `approved` false | Bước 08 dừng, báo "skills_v2.json chưa được duyệt" |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Ứng viên | `python scripts/mine_skill_candidates.py`; số theo nguồn | Khớp ước lượng 6.000–8.000 (hoặc giải thích) |
| Đọc hết | `_meta.read_progress` = số ứng viên DF ≥ 2 | Bằng nhau |
| Trang duyệt | `skills_v2.html` ở 1100px và 390px | Không tràn ngang; có ví dụ thật mỗi kỹ năng |
| Test | `pytest tests/unit/test_skills_ac.py tests/unit/test_ph8_run.py -q` + test mới theo mục 5 | Xanh |
| Dry-run | `python scripts/run_preprocessing.py --step skills --source all --dry-run` | Bảo toàn số tin |
| Gold | `python scripts/eval_gold_processing.py` trước và sau | F1 tăng; báo riêng phần do sửa cách đo |
| Tin không kỹ năng | `extra.n_jobs_no_skill` | Giảm so với 7,8% |
| Hợp lý | Top 15 kỹ năng mỗi nghề | Người dùng xem và đồng ý |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| — | Quyết định đầu vào | 18/11 | Người dùng: làm lại chuẩn hóa kỹ năng bằng cách đọc JD, đọc hết ứng viên từ 2 tin trở lên; kỹ năng con trỏ về kỹ năng cha; kỹ năng mềm và ngoại ngữ gắn cờ; K8.9 một nguồn kỹ năng. Đo thử số ứng viên: tag DF ≥ 2 1.655, token 4.087, hợp 5.432, cụm sau từ báo hiệu 2.474 | — |
| 1 | Duyệt đặc tả | 18/11 | Người dùng: "TUi duyệt cả 2: đặc tả với prompt" (K8.11–K8.16), chọn đọc hết 10.985 ứng viên | — |
| 2 | Duyệt prompt | 18/11 | Như trên | — |
| — | Đọc ứng viên (K8.12–K8.13) | 18/11 | 36 lô `skills_v2_decisions/b001–b036.txt`, đủ 10.985/10.985 dòng; build `skills_v2.json`: 2.113 kỹ năng, 5.146 not_skill, 11 câu hỏi | 84b1d7f … ae5e4c8 |
| — | Trang duyệt (K8.14) | 18/11 | `scripts/review_skills_v2.py` → `docs/presentation/processing_steps/skills_v2.html`. Đo lại trên bảng 02 lộ 2 lỗi khớp: bỏ dấu làm "công nghệ" khớp "nghe" (1.210 tin), "bản về" khớp "bản vẽ"; "R" khớp "R&D", "Go" khớp "Go-live". Sửa: builder ghi `alias_forms` (dạng có dấu), trang duyệt áp luật đúng dấu + chặn "-chữ"; 23 alias chung chung ("báo cáo", "cải tiến", "quality", "integration", "join", "thị trường"…) chuyển not_skill. Sau sửa: 2.113 kỹ năng, 5.169 not_skill, 99,4% tin có ≥ 1 kỹ năng kỹ thuật, 9 kỹ năng không khớp tin nào. Chờ người dùng chốt 11 câu hỏi và hai luật mới cho K8.15 | (commit này) |
| — | Duyệt từ điển (K8.14) | 18/11 | Người dùng: "duyệt hết, làm tiếp K8.15 đi": 11 can_hoi theo đề xuất (WordPress thành kỹ năng CMS) + luật dấu + chặn "Go-live". Dấu duyệt: `skills_v2_decisions/approval.json` → `approved: true`, 2.114 kỹ năng | (commit này) |
| 3 | Test rồi code | 18/11 | `tests/unit/test_skills_v2.py` (12 test: 7 ví dụ mục 5 + dấu, cụm bằng cấp, R&D, không dấu). Code: `skills.load_skills_v2`, `matcher_from_v2`, luật dấu, chặn "-chữ", cụm chặn, cột `kind`/`parent`; `run.default_matcher` đọc v2. Unit test 578 qua; 2 lỗi có sẵn từ trước (`test_encoding_execution` tfidf, `test_report_code_quality` vulture) | (commit này) |
| 4 | Dry-run | 18/11 | `processing.extraction.run.run(dry_run=True)` trên bảng 03 (bảng 04 chưa chạy lại), 4.495 tin, bảo toàn số tin. Từ điển cũ → v2: dòng kỹ năng 31.291 → 121.325 (kỹ thuật 96.439, mềm 22.108, ngoại ngữ 2.778); tin không có kỹ năng 351 (7,8%) → 3 | — |
| 5 | Review, chạy thật | chưa | | |
