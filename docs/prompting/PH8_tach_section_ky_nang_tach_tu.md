# Prompt PH8: tách section/bullet, trích kỹ năng Aho–Corasick, tách từ + stopword (`processing/`)

> **Nháp, chờ bạn duyệt.** Các điểm **[CẦN CHỐT]** trong spec (P1, P2, S1–S4, K1–K6, W1–W5) phải được chốt trước khi giao prompt này cho agent code. Chỗ ghi "[ĐỀ XUẤT]" là mặc định nếu bạn không đổi.

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/PH8_tach_section_ky_nang_tach_tu.md` (mục 2 là hiện trạng đã đo; mục 4 là luật; mục 5 là cách đo).
- `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` bước 7, 8, 9, mục 3.2, 4.1–4.4.
- `processing/CLAUDE.md`, `preprocessing/CLAUDE.md`, `docs/spec/preprocessing/spec/PH2_schema_va_lam_sach_ky_tu.md` (cột `*_clean/_norm/_fold`).
- Code: `preprocessing/common/gold.py` (`SECTIONS`, `load_gold`, `validate_label`), `preprocessing/common/text_clean.py`, `preprocessing/common/step_report.py`, `preprocessing/deduplication/text_norm.py` (`fold`), `preprocessing/transformation/skill_extractor.py` (chỉ làm đối chứng, **không sửa**), `preprocessing/encoding/skills_taxonomy_230.py`, `preprocessing/encoding/assets/jd_stopwords_v1.json`, `scripts/build_gold_sample.py` (`_text`), `scripts/run_preprocessing.py` (mẫu driver).

Hiện tại (đo 10/11/2026 trên 5.077 tin của `01_clean`, xấp xỉ, mục 2 spec):
- `processing/extraction`, `processing/transformation` chỉ có `__init__.py`.
- `pyahocorasick` 2.3.1 và `underthesea` 9.5.0 đã cài trong `.venv` nhưng chưa có trong `requirements*.txt`.
- Có 3 taxonomy (40 / 92 / 230 kỹ năng); không có tệp ~300 như thiết kế.
- Quét trên `text_fold` với alias ngắn gây nhiễu: `bi` khớp 1.314 tin, `ba` 675, `soc` 285, `c` 267, `r` 175.
- `gold_sample.json` có 100 JD, **chưa có file nhãn**: chưa đo được F1 và độ đúng section.
- `underthesea` cắt vụn `C++`, `Node.js`, `C#/.NET`; token `skill_python` đi qua nguyên vẹn; 100 JD gold mất 1,3 giây.

## 2. Việc cần sửa (tất cả là code mới trong `processing/`, trừ ghi chú)

**Input** (**[CẦN CHỐT] P2**): bảng gộp sau pre-processing, cột `job_id_global, source_platform, description_clean, requirements_clean` (+ `benefits_list` nếu có). **Output**: `data/processing/<bước>/all.parquet`, báo cáo `reports/processing/<bước>/<nguồn>.json` + `_all.json` (tên bước: spec P1, [ĐỀ XUẤT] `07_sections`, `08_skills`, `09_tokens`).

1. `preprocessing/dictionaries/section_headings.json` (mới): chứa **chỉ các mục bạn duyệt**; chưa duyệt thì `{}`. Kèm script `scripts/list_section_heading_candidates.py` (chỉ đọc) in dòng ngắn đứng riêng theo tần suất để bạn duyệt. Không bịa mục.
2. `processing/extraction/sections.py`: `split_sections(description, requirements, benefits=None) -> list[Bullet]` theo luật S7.1–S7.5. Dùng `SECTIONS` từ `gold.py`.
3. `processing/extraction/skills.py`: `build_automaton(taxonomy) -> Automaton` (khóa `fold(alias)` cho alias an toàn, K8.1), `extract_skills(bullets, automaton, ...) -> list[SkillHit]` theo K8.2–K8.6. Alias ngắn/dễ trùng (K8.3) đi đường riêng: quét `text_clean` phân biệt hoa thường + ngữ cảnh. Taxonomy đọc từ JSON trong `dictionaries/` ([ĐỀ XUẤT] xuất từ `TAXONOMY_230`; `processing/` không import `preprocessing/encoding/`).
4. `processing/transformation/tokenize.py`: `tokenize(bullet_text, hits) -> list[str]` (W9.1–W9.3, đầu ra `list`, token giữ chỗ nguyên); `domain_stopwords(docs_tokens, df_threshold=0.6)` (W9.5); `remove_stopwords(tokens, general, domain, protected)`.
5. `processing/extraction/run.py` và `processing/transformation/run.py`: `run(sources, dry_run) -> dict[nguồn, StepReport]` cùng chữ ký các bước `preprocessing/<bước>/run.py`; không bỏ JD (`dropped = 0`); `extra` theo mục 5 spec.
6. `processing/evaluate.py` + `scripts/eval_gold_processing.py` (chỉ đọc): nạp nhãn bằng `load_gold`, chạy bước 7 và 8 trên 100 JD gold, in độ đúng section (5.1) và P/R/F1 skills (5.2), theo nguồn và tổng, kèm số JD đã gán nhãn mỗi trường (`coverage`). Thiếu file nhãn thì in "chưa có nhãn" và thoát mã 0, không điền số.
7. `requirements.txt`: ghim `pyahocorasick==2.3.1`, `underthesea==9.5.0` (version đã đo trên máy) **chỉ khi bạn đồng ý**; không chạy `pip install`.
8. Không sửa: `skill_extractor.py`, `skills_clean`, `description_clean`, `requirements_clean`, `preprocessing/encoding/`.

## 3. Pseudo code

```text
# bước 7
split_sections(desc, req, benefits):
    out = []
    for field, default in ((desc,"mo_ta"), (req,"yeu_cau"), (benefits,"phuc_loi")):   # benefits tùy S1
        sec = default
        for line in lines(field) (bỏ dòng rỗng):
            text = bỏ tiền tố "- "
            if is_heading(text, HEADINGS):            # ngắn, khớp từ điển đã duyệt
                sec = map_heading(text) or sec; continue       # S7.3, tiêu đề không thành bullet
            s, rule = sec, ("S7.2" nếu sec==default else "S7.3")
            if has_priority_cue(text, CUES): s, rule = "uu_tien", "S7.4"
            out.append(Bullet(idx, s, text, rule))
    return out

# bước 8
for job in jobs:
    hits = {}
    for b in job.bullets:
        for (alias, canon, span) in scan(b):         # AC trên fold(b.text) cho alias an toàn
            if boundary_ok(...): hits.add(canon, b.section)
        for (alias, canon) in scan_short_case_sensitive(b.text_clean): hits.add(...)   # K8.3
    level/weight theo K8.5; gộp theo canon (level cao nhất, n_mentions)
    thêm via=meta nếu K4

# bước 9
for bullet: text = thay mỗi span kỹ năng bằng "sk_<slug>"; toks = word_tokenize(text)
tokens = lọc dấu câu; lower trừ sk_*
DF = số JD chứa token / tổng JD; domain = {t : DF > 0.6 và không bắt đầu "sk_"}
tokens_nostop = tokens - general - domain
```

## 4. Ràng buộc

- Không sửa raw, không đọc raw, không đổi tên/giá trị cột đã có, không dùng model, không ghi R2, không cài gói, không commit.
- Không bịa danh sách: tiêu đề section, cụm "ưu tiên", alias ngắn (K8.3), stopword mới đều từ EDA và bạn duyệt. Chưa duyệt thì file `{}` và code dùng từ điển nhỏ dựng trong test.
- Nhãn gold chưa có thì **không** tự sinh nhãn; test đánh giá dùng nhãn dựng thủ công trên chuỗi thật từ `gold_sample.json` (ghi `job_id` trong chú thích) hoặc `tests/fixtures/<nguồn>/`.
- Bước 07/08/09 không bỏ JD; `rows_in = rows_out + dropped(=0)`.
- `reports/` đưa vào git: không chứa toàn văn JD (ví dụ trước → sau cắt 120 ký tự, như P6).
- Dùng `fold` từ `deduplication/text_norm.py`, không viết bản fold thứ bảy.
- Chạy lại hai lần ra cùng hash (sắp xếp đầu ra ổn định theo `job_id_global, bullet_idx, skill`).
- Không đổi hành vi test cũ; test nào khẳng định hành vi sai thì sửa và ghi lý do.
- Sau khi xong ghi `docs/issue_log.md` (mã `L-` kế tiếp) nếu có lỗi được sửa; nêu bẫy `fold` + alias ngắn vào `processing/CLAUDE.md`.

## 5. Ví dụ (thành test; chuỗi thật lấy từ gold/fixtures, ghi `job_id`)

| Đầu vào | Kết quả mong đợi |
|---|---|
| `description="- Phát triển API\n- Review code"`, `requirements="- Có 2 năm kinh nghiệm\n- Biết Docker"` (dựng từ tin thật, ghi job_id) | 4 bullet: 2 `mo_ta` (S7.2), 2 `yeu_cau` (S7.2) |
| Dòng `"Quyền lợi:"` (từ điển test `{"phuc_loi": ["quyền lợi"]}`) giữa trường description | dòng tiêu đề không thành bullet; các dòng sau là `phuc_loi` (S7.3) |
| Bullet `"Ưu tiên có kinh nghiệm Kubernetes"` (cụm test `["ưu tiên"]`) | section `uu_tien` (S7.4) |
| `fold("Bị phạt nặng")` có chứa `bi` | không sinh kỹ năng BI (K8.3) |
| `"Kinh nghiệm BI và Power BI"` | BI được nhận do viết hoa đúng, theo từ điển test |
| `"Thành thạo C++, Node.js và C#/.NET"` | kỹ năng `C++`, `Node.js`, `C#`, `.NET` được nhận (ranh giới `# + .` đúng) |
| `"Thành thạo Node.js"` qua bước 9 | `tokens` chứa `sk_nodejs` (hoặc slug theo taxonomy), không chứa `node`, `.`, `js` rời |
| Kỹ năng ở bullet `yeu_cau` / `uu_tien` | `level=required, weight=1` / `preferred, 0.5` |
| Cùng kỹ năng ở `uu_tien` và `yeu_cau` | một dòng, `required`, `n_mentions=2` |
| Token `sk_*` có DF > 0,6 trong corpus test | **không** bị bỏ ở `tokens_nostop` |
| `word_tokenize("Có kinh nghiệm lập trình viên backend tại công ty phần mềm")` (đã đo) | token ghép `kinh nghiệm`, `lập trình viên`, `công ty`, `phần mềm` giữ nguyên |
| JD không có bullet/kỹ năng | vẫn có mặt trong báo cáo, đếm `n_jobs_no_bullet`/`n_jobs_no_skill`, không bị bỏ |
| `eval_gold_processing.py` khi chưa có file nhãn | in "chưa có nhãn", mã thoát 0, không in số |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit -q` (test mới `test_sections.py`, `test_skills_ac.py`, `test_tokenize.py`) | xanh |
| Bảo toàn | `python scripts/run_processing.py --step sections --source glints --dry-run`, rồi 8 nguồn (script này thuộc PH9; trước đó gọi `run()` trực tiếp) | `dropped=0` mọi nguồn |
| Đối chứng taxonomy | so tỉ lệ tin 0 kỹ năng với số đo 2.3 spec; liệt kê top 30 alias theo DF | alias ngắn không còn nằm đầu bảng (`bi`, `ba`, `soc`); số khớp bị K8.3 chặn được báo |
| Độ đúng section | `python scripts/eval_gold_processing.py --gold <file nhãn>` | ≥ 90% theo bullet (5.1), báo theo nguồn; nếu thấp, nêu lỗi còn lại |
| F1 kỹ năng | cùng lệnh | F1 micro `via=text` ≥ 0,85 (5.2); báo kỹ năng ngoài taxonomy riêng |
| Tách từ | in `tokens` của 20 JD (seed 42) cạnh bullet gốc | không còn `C++/C#/Node.js/.NET` vụn; token `sk_*` đúng JD |
| Stopword | xem danh sách DF > 0,6 trong báo cáo 09 | bạn duyệt từng token; không có token kỹ năng |
| Tái lập | chạy hai lần, so hash parquet | trùng |
| Git | `git status`, `git diff --stat` | không đụng `collection/`, R2, `skill_extractor.py`, `preprocessing/encoding/`; không file dữ liệu trong git |
