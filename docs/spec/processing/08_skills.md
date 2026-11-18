# Bước 08: Skills

> Code: `processing/extraction/skills.py` (`SkillMatcher`, `extract_skills`, `load_taxonomy`, `load_short_forms`, `short_alias_candidates`); `processing/extraction/run.py` (`analyze`, `run`); `processing/selection/sparsity.py` (`reduce_sparsity`, tùy chọn).
> Lệnh: `python scripts/run_preprocessing.py --step skills --source all [--dry-run]` (chạy chung lần gọi với bước 07).
> Dữ liệu mẫu: điền khi chạy lại trên bảng 04 mới.
> Số liệu trong file này là của lần chạy 10/11/2026 trên 4.671 tin (**chưa chạy lại**).

## 1. Mục đích

Mỗi tin có một danh sách kỹ năng chuẩn, kèm mức **bắt buộc** hay **ưu tiên**. Đây là nguyên liệu chính của:

| SD | Dùng để |
|---|---|
| SD1 | Số kỹ năng và nhu cầu kỹ năng của tin người mới (câu 1.5) |
| SD2 | Gói kỹ năng (luật kết hợp), top kỹ năng theo nghề, kỹ năng hiếm |
| SD4 | Cột `skill__*` của model lương |
| SD5 | `demand(k)`, kỹ năng nên học, kỹ năng để sau |

- Tiêu chí: **accuracy** (đúng kỹ năng), **consistency** (cùng một slug cho cùng một kỹ năng dù mỗi sàn gọi khác nhau), **completeness** (ít tin không có kỹ năng).
- Ranh giới: không bỏ dòng; không sửa `skills_std` của bảng 04; không đọc lại raw.

## 2. Luật

### 2.1. Luật đang chạy

| Mã | Điều kiện / cách làm | Hành động |
|---|---|---|
| K8.1 | Dựng một automaton Aho–Corasick từ taxonomy `processing/dictionaries/skills_taxonomy_230.json` (230 kỹ năng, 6 nhóm). Khóa là `fold(alias)`, chỉ cho alias dài ≥ 4 ký tự **hoặc** có `#`, `+`, `.` (ví dụ `c#`, `c++`, `.net`). Alias thuộc nhiều kỹ năng bị bỏ và ghi vào `alias_conflicts_dropped` | modify |
| K8.2 | Ranh giới từ: ký tự liền trước và liền sau chỗ khớp không thuộc `[a-z0-9_#+]` | modify |
| K8.3 | Alias ngắn hoặc dễ trùng từ thường (`bi`, `ba`, `soc`, `c`, `r`, `go`…) **không** quét trên văn bản fold. Chúng chỉ khớp phân biệt hoa thường trên văn bản gốc, và chỉ khi có trong `short_aliases.json` đã duyệt. Lý do: quét trên fold thì `bi` khớp 1.314 tin, so với 363 tin khi khớp hoa thường | modify |
| K8.4 | Quét riêng từng bullet để biết section của từng lần khớp. Khớp chồng nhau thì giữ khớp dài nhất | modify |
| K8.5 | Mức theo section: `yeu_cau`, `mo_ta`, `khac` → `required`, weight 1; `uu_tien` → `preferred`, weight 0,5; `phuc_loi` **không quét**. Cùng kỹ năng xuất hiện nhiều lần thì giữ mức cao nhất (`required` > `preferred`) và cộng `n_mentions` | modify |
| K8.6 | Kỹ năng từ `skills_list` của bảng 04 (nếu chưa có từ văn bản) ghi thêm với `via = meta`, `level = required`, `section = null`. F1 trên gold chỉ tính `via = text` | modify |
| K8.7 | Tin đã dịch (`translation_status = translated`): quét thêm bản dịch. Kỹ năng chỉ thấy trong bản dịch ghi `via = text_vi`; kỹ năng đã có thì cộng `n_mentions` và có thể nâng mức | modify |

Kết quả 10/11: 32.637 cặp (tin, kỹ năng), 219 kỹ năng được dùng, trung bình 6,99 và trung vị 5 kỹ năng mỗi tin. 363 tin (7,8%) không có kỹ năng nào lấy từ văn bản; tính cả `meta` thì còn 292 tin. Số kỹ năng có DF dưới 3/5/10/20/50 tin lần lượt là 14/24/42/65/101.

Hệ quả hiện tại:
- Vì chưa có cụm "ưu tiên" nào được duyệt, **mọi kỹ năng đều `required`**; mức 1 và 0,5 chưa có tác dụng.
- Vì chưa có `short_aliases.json` đã duyệt, alias ngắn không bao giờ được bắt.
- Kỹ năng mềm và ngoại ngữ đứng đầu (ví dụ topcv: communication 677 tin, english 463, teamwork 356; python 258).

### 2.2. Luật đề xuất (chờ người dùng duyệt)

| Mã | Đề xuất | Lý do |
|---|---|---|
| **K8.8** | Thêm trường `"soft": true` cho 8 slug trong taxonomy: `communication`, `teamwork`, `problem_solving`, `logical_thinking`, `time_management`, `presentation`, `english`, `japanese`. Bước 08 thêm cột `is_soft` vào `job_skills.parquet` | Spec 07 mục 4 (quyết định 2, 17/11): M1, M2, M6 xếp hạng hai danh sách riêng. Không lấy nguyên nhóm `methodologies_softskills_data`, vì nhóm này lẫn Agile, BI, machine learning. Taxonomy hiện chưa có trường `soft` |
| **K8.9** | Chốt nguồn kỹ năng duy nhất cho SD1–SD5 là bước 08; cột `skills` của Silver cũng lấy từ đây | PRE-40 |
| **K8.10** | Duyệt `short_aliases.json` (bản ứng viên có 49 mục) và `priority_cues.json` | PRE-33; SD5 cần phân biệt bắt buộc và ưu tiên |

## 3. Quy trình xử lý

Thứ tự trong `analyze` và `run` (`processing/extraction/run.py`):

1. Nạp taxonomy (`load_taxonomy`) và alias ngắn đã duyệt (`load_short_forms`; thiếu file thì rỗng). `SkillMatcher` dựng automaton từ khóa an toàn (K8.1), ghi `conflicts`, dựng biểu thức chính quy cho alias ngắn (K8.3).
2. Với mỗi tin, lấy các bullet của bước 07 (cùng lần gọi, không đọc lại file).
3. `extract_skills(bullets, matcher, skills_list)`:
   1. Bỏ bullet `phuc_loi` (K8.5).
   2. Với mỗi bullet: `matcher.find(text)` quét đường fold (kiểm ranh giới K8.2) và đường alias ngắn; sắp theo độ dài giảm dần, giữ khớp không chồng nhau (K8.4).
   3. Gộp theo slug: lần đầu tạo dòng với `level`/`weight` theo section; các lần sau cộng `n_mentions` và nâng mức nếu cao hơn.
   4. Với mỗi tên trong `skills_list` mà `meta_slug` nhận ra và slug chưa có: thêm dòng `via = meta` (K8.6).
4. **[chỉ khi tin đã dịch]** làm lại bước 3 trên bản dịch; kỹ năng mới ghi `via = text_vi`, kỹ năng cũ cộng `n_mentions` và có thể nâng mức (K8.7).
5. Nếu chạy có `min_df` hoặc `merge_map`: `reduce_sparsity` gộp alias rồi gom kỹ năng DF < `min_df` vào `other_skill` (hoặc `family_<nhóm>`), ghi thêm `job_skills_reduced.parquet`. Mặc định không làm gì (`min_df = None`); việc gom ở mức 15 tin do bước 10b làm.
6. Ghi `job_skills.parquet`; ghi report theo nguồn và `_all` (`_all` thêm khối `sparsity`); kiểm `rows_conserved`.

## 4. Input → Output

| | Chi tiết |
|---|---|
| Input | Bullet của 07 (tính trong cùng lần gọi); cột `skills_list`, `translation_status`, `description_vi`, `requirements_vi` của bảng 04; taxonomy; `short_aliases.json` đã duyệt |
| Output | `data/processing/08_skills/job_skills.parquet`, một dòng một cặp (tin, kỹ năng): `job_id_global`, `source_platform`, `slug`, `skill` (tên chuẩn), `level` (`required`, `preferred`), `weight` (1 hoặc 0,5), `section`, `via` (`text`, `text_vi`, `meta`), `n_mentions`. Tùy chọn: `job_skills_reduced.parquet` |
| Report | `reports/processing/08_skills/`; `extra`: `n_job_skill_rows`, `n_jobs_no_skill`, `top_skills` (30), `short_forms_approved`, `alias_conflicts_dropped`; `_all` thêm `sparsity` |

## 5. Dữ liệu mẫu

Điền khi chạy lại trên bảng 04 mới: một tin mẫu với các bullet và kỹ năng trích ra, kèm ví dụ cho K8.3 (`bi` khớp hoa thường so với fold) và K8.7 (kỹ năng chỉ thấy trong bản dịch).

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách | Đích | Kết quả gần nhất |
|---|---|---|---|
| Số tin được giữ | `checks.rows_conserved` | Bằng bảng 04 | Đạt (10/11) |
| P/R/F1 micro theo cặp (tin, kỹ năng) | `python scripts/eval_gold_processing.py`; chỉ tính `via = text`; nhãn không ánh xạ được về taxonomy tính là FN và báo riêng | F1 ≥ 0,85 | **0,27** (11/11); có thể một phần do cách so tên kỹ năng với `slug` |
| Kiểm thủ công | 20 tin ngẫu nhiên | Hợp lý | Chưa làm |
| Test | `tests/unit/test_skills_ac.py`, `test_ph8_run.py` | Pass | — |

## 7. Trạng thái, chỗ thiếu, việc mở

| Trạng thái | Có code, đã chạy thật 10/11. F1 trên gold 0,27, chưa đạt |
|---|---|

| Chỗ thiếu | Ảnh hưởng | Mã |
|---|---|---|
| Chưa duyệt `short_aliases.json`, `priority_cues.json` | Không bắt được C, R, Go, BI; mọi kỹ năng đều `required` | PRE-33, PRE-40 |
| F1 0,27 và cách đo | Chưa biết lỗi nằm ở trích xuất hay ở cách so tên với `slug`; nên đo lại trước khi sửa | PRE-33 |
| 7,8% tin không có kỹ năng từ văn bản | SD2 bỏ các tin này; SD3 loại khỏi phân cụm (spec 07 mục 4) | PRE-35 |
| Hai từ điển kỹ năng (`skills_std` ở 03, `skill__*` ở 08) | Cùng một tin có hai danh sách khác nhau | PRE-40 |
| Taxonomy chưa có trường `soft` | M1, M2, M6 chưa tách được hai danh sách | MINE-7 |
| Taxonomy 230 chưa có kỹ năng ngoài từ điển; DF < 15 bị gom ở 10b | SD2 không thấy kỹ năng hiếm dưới 15 tin trong ma trận; cần quyết có chạy 2.4 trên `job_skills.parquet` | — |
| `pyahocorasick` chưa ghim phiên bản; report `rules` rỗng | Tái lập; Monitoring không thấy luật K8.x | PRE-40 |
