# Bước 07: Sections

> Code: `processing/extraction/sections.py` (`split_sections`, `load_headings`, `load_cues`, `load_approved`, lớp `Bullet`); `processing/extraction/run.py` (`analyze`, `run`). Chạy chung một lần gọi với bước 08.
> Lệnh: `python scripts/run_preprocessing.py --step sections --source all [--dry-run]` (hoặc `--step all`).
> Dữ liệu mẫu: điền khi chạy lại trên bảng 04 mới.
> Số liệu trong file này là của lần chạy 10/11/2026 trên 4.671 tin (**chưa chạy lại**).

## 1. Mục đích

Tách JD thành các **bullet** có nhãn section, để:
- bước 08 biết một kỹ năng nằm ở phần yêu cầu, phần ưu tiên hay phần phúc lợi;
- bước 12_e5 có đơn vị văn bản ngắn để embedding;
- bước 09 tách từ theo từng bullet.

| Bên dùng | SD |
|---|---|
| 08 (mức bắt buộc/ưu tiên) | SD2, SD4, SD5 |
| 12_e5 (embedding) | SD3 |

- Tiêu chí: **accuracy** (đúng section), **consistency** (cùng cách tách cho 8 sàn).
- Ranh giới: không bỏ dòng (mọi tin vẫn có mặt; tin không có bullet thì ghi ở `n_jobs_no_bullet`); không sửa chữ của bảng 04; chỉ đọc từ điển có `approved: true`.

## 2. Luật

### 2.1. Luật đang chạy

| Mã | Điều kiện / cách làm | Hành động | Số bullet 10/11 |
|---|---|---|---|
| S7.1 | Tách theo dòng. Dòng bắt đầu bằng `- ` là một bullet (bỏ ký hiệu); dòng không có ký hiệu cũng là một bullet, trừ khi là tiêu đề (S7.3). Bỏ dòng rỗng | modify | 114.008 |
| S7.2 | Section mặc định theo trường nguồn: `description_clean` → `mo_ta`, `requirements_clean` → `yeu_cau`, `benefits_list` → `phuc_loi` | modify | `mo_ta` 39.153, `yeu_cau` 35.152, `phuc_loi` 39.703 |
| S7.3 | Dòng là tiêu đề (có trong `section_headings.json` đã duyệt, tối đa 6 từ, so sau khi fold và bỏ dấu `:` cuối) thì đổi section cho các dòng sau, đến tiêu đề kế tiếp. Bản thân dòng tiêu đề không thành bullet | modify | 0 (chưa có từ điển đã duyệt) |
| S7.4 | Bullet mở đầu bằng cụm "ưu tiên" (theo `priority_cues.json` đã duyệt) → `uu_tien`. Nếu dòng ngắn (≤ 6 từ), kết thúc bằng `:` và mở đầu bằng cụm đó thì nó là tiêu đề: đổi section các dòng sau sang `uu_tien`, không thành bullet | modify | 0 (chưa có từ điển đã duyệt) |
| S7.5 | Không khớp luật nào thì giữ section mặc định | — | 114.008 (100% theo S7.2) |

Hệ quả hiện tại: **không có bullet nào ở `uu_tien` hay `khac`**, vì cả hai từ điển chưa được duyệt.

### 2.2. Luật đề xuất

Chưa có luật mới. Việc phải làm là **duyệt từ điển** (không phải đổi luật):

| Việc | Chi tiết |
|---|---|
| Duyệt `section_headings` | Bản ứng viên `processing/dictionaries/section_headings_candidates.json` có 64 mục. Người dùng đánh `approved: true` cho mục đúng, lưu thành `section_headings.json` |
| Duyệt `priority_cues` | Bản ứng viên có 40 mục; lưu thành `priority_cues.json` |
| Sau khi duyệt | Chạy lại 07 và 08; đo lại độ đúng section trên gold |

## 3. Quy trình xử lý

Thứ tự trong `analyze` và `run` (`processing/extraction/run.py`):

1. Đọc bảng 04, sắp theo `job_id_global`, lọc theo `--source`.
2. Nạp từ điển đã duyệt: `load_headings()` (khóa là `fold(phrase)` bỏ `:`), `load_cues()`. File thiếu thì danh sách rỗng, không báo lỗi.
3. Với mỗi tin, gộp `benefits_list` thành một chuỗi (mỗi mục một dòng).
4. `split_sections(description_clean, requirements_clean, benefits, headings, cues)`. Lần lượt ba trường `description_clean` → `requirements_clean` → benefits; mỗi trường bắt đầu với section mặc định của nó:
   1. Với mỗi dòng: bỏ khoảng trắng, bỏ `- ` đầu dòng, bỏ dòng rỗng (S7.1).
   2. Tính `key = fold(text)` bỏ `:` cuối. Nếu `key` có tối đa 6 từ:
      - `key` nằm trong tiêu đề đã duyệt → đổi section, bỏ qua dòng này (S7.3);
      - dòng kết thúc bằng `:` và `key` bắt đầu bằng cụm ưu tiên → đổi section thành `uu_tien`, bỏ qua dòng này (S7.4).
   3. Nếu `key` bắt đầu bằng cụm ưu tiên → bullet `uu_tien`, `rule = S7.4`.
   4. Ngược lại → bullet với section hiện tại; `rule = S7.2` nếu section còn là mặc định, `S7.3` nếu đã bị tiêu đề đổi.
5. **[chỉ khi `translation_status = translated`]** tách thêm bản dịch (`description_vi`, `requirements_vi`) để bước 08 quét kỹ năng; bullet ghi ra bảng 07 vẫn theo bản gốc.
6. Ghi một dòng mỗi bullet; ghi report theo nguồn và `_all`; kiểm `rows_conserved` (số tin vào = ra).

## 4. Input → Output

| | Chi tiết |
|---|---|
| Input | `data/preprocessing/04_normalization/all.parquet`: `job_id_global`, `source_platform`, `description_clean`, `requirements_clean`, `benefits_list`, `skills_list`; tin đã dịch thì thêm `description_vi`, `requirements_vi`, `translation_status` |
| Output | `data/processing/07_sections/all.parquet`, một dòng một bullet: `job_id_global`, `source_platform`, `bullet_idx`, `section` (`mo_ta`, `yeu_cau`, `uu_tien`, `phuc_loi`, `khac`), `text`, `section_rule` (`S7.2`, `S7.3`, `S7.4`) |
| Report | `reports/processing/07_sections/<nguồn>.json` và `_all.json`; `extra`: `n_bullets`, `bullets_by_section`, `bullets_by_rule`, `n_jobs_no_bullet`, `headings_approved`, `cues_approved` |
| Số dòng | Số bullet (114.008 ở lần chạy 10/11); số tin giữ nguyên |

## 5. Dữ liệu mẫu

Điền khi chạy lại trên bảng 04 mới: tin mẫu xuyên suốt và vài bullet trước → sau của từng luật S7.2, S7.3, S7.4. Cho đến khi từ điển được duyệt, chỉ có thể minh họa S7.2.

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách | Đích | Kết quả gần nhất |
|---|---|---|---|
| Số tin được giữ | `checks.rows_conserved` trong report | Bằng bảng 04 | Đạt (10/11) |
| Tin không có bullet | `n_jobs_no_bullet` | 0 | 0 (10/11) |
| Độ đúng section theo bullet | `python scripts/eval_gold_processing.py`; so theo nội dung dòng, chỉ tính bullet nằm trong vùng đã gán nhãn trên bộ gold (`processing/evaluate.py`) | ≥ 90% | **84,5%** (11/11), chưa đạt |
| Test | `tests/unit/test_sections.py`, `test_processing_skeleton.py` | Pass | — |

Bộ gold gộp `data/preprocessing/gold/gold_labels.json` không có trên máy dùng để viết file này; chỉ có `gold_labels_tai_76_100.json`. Muốn đo lại phải lấy file gộp từ máy đã chạy ngày 11/11.

## 7. Trạng thái, chỗ thiếu, việc mở

| Trạng thái | Có code, đã chạy thật 10/11. Độ đúng 84,5%, chưa đạt đích 90% |
|---|---|

| Chỗ thiếu | Ảnh hưởng | Mã |
|---|---|---|
| Chưa có `section_headings.json`, `priority_cues.json` đã duyệt | 100% bullet theo S7.2; không có `uu_tien` nên mọi kỹ năng là `required` ở bước 08 | PRE-33, PRE-40 |
| Bullet careerviet thô: 399/400 tin chỉ có 3 bullet | Embedding và `n_tokens` của careerviet kém chi tiết hơn các sàn khác | PRE-34 |
| Báo cáo `rules` rỗng; ghi "pipeline không dùng model" | Monitoring không thấy luật S7.x | PRE-40 |
