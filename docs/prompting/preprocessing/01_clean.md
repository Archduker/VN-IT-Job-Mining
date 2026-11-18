# Prompt 01: Clean (chạy lại trên tập raw đang có trên R2, có nhãn C4b và lần cào đầu)

> Đặc tả: [`docs/spec/preprocessing/01_clean.md`](../../spec/preprocessing/01_clean.md). Dữ liệu mẫu: `docs/spec/preprocessing/samples/01_clean.json`.
> Prompt này viết lại ngày 18/11/2026 sao cho chạy lại ra **đúng kết quả lần chạy lại 18/11** (sau L-50): 13.361 → 4.621. Lần chạy đầu 18/11 (trước C9) ra 4.799.

## 1. Ngữ cảnh

**Đọc trước:**

- Đặc tả bước 01 (mục 2 luật, mục 3 quy trình).
- `preprocessing/CLAUDE.md`, `preprocessing/clean/CLAUDE.md`.
- Code: `preprocessing/clean/run.py`, `preprocessing/common/it_filter.py`, `preprocessing/common/raw_reader.py`, `preprocessing/clean/it_policy.json`, `preprocessing/clean/scope_keywords.json`, `preprocessing/clean/label_review.py`.

**Vì sao làm:** dựng lại bước 01 trên **đúng tập raw đang có trên R2**, để mọi bước sau và trang trình bày khớp với dữ liệu nhóm dùng chung. Hai việc đi kèm:

- **Đo bộ lọc IT trên nhãn.** Nhãn tay cũ đã mất. Người dùng chọn để Claude gán nhãn mẫu C4b theo rubric, thay vì gán tay ("tại sao tui phải gán tay trong khi đó bạn có thể xử lý thẳng cho tui").
- **Ghi lần cào đầu** (`first_scraped_at`) trước khi C1 bỏ snapshot cũ, để bước 03 tạo được `posted_month` (PRE-37).

**Số liệu trước khi làm:**

- Máy = R2 + 71 file `data/topcv/raw/2026-11-17/*_v1.json` chỉ có trên máy.
- Report 01 trong git là lần chạy 10/11: 13.361 → 4.799.

## 2. Việc cần sửa

**Input:** `data/<nguồn>/raw/**/*.json` (8 nguồn). **Output:** `data/preprocessing/01_clean/<nguồn>.jsonl`, `data/preprocessing/rejected/01_clean/<nguồn>.jsonl`, `reports/preprocessing/01_clean/<nguồn>.json` + `_all.json`, mẫu `data/preprocessing/review/it_<nguồn>.csv`.

1. **Chỉ dùng raw có trên R2.**
   - So key `raw/` trên R2 (chỉ `list_objects_v2`) với file trên máy, theo từng nguồn.
   - File chỉ có trên máy thì **chuyển** (không xóa) sang `data/_local_only/<nguồn>/raw/<ngày>/`, ghi danh sách vào báo cáo cho người dùng.
2. **Nhãn C4b.**
   - Nếu `data/preprocessing/review/it_<nguồn>.csv` chưa có nhãn: chép bản lưu `data/preprocessing/gold/it_review/it_<nguồn>.csv` về.
   - Nếu cả bản lưu cũng chưa có: Claude gán `nhan_tay` theo rubric của `label_review.py`, chỉ nhìn tiêu đề và kỹ năng, không nhìn `it_rule` hay `it_status`; ghi `nguoi_gan` = `claude`.
   - Dựng trang kiểm mẫu `docs/presentation/preprocessing_steps/c4b_kiem_mau.html`: mọi tin nhãn khác luật + 10% tin cùng ý, cho người dùng duyệt.
   - Nhãn người dùng bổ sung ghi `nguoi_gan` = `nguoi_dung`; nhãn suy theo mẫu của người dùng ghi `claude_theo_mau_nguoi_dung`.
3. **`first_scraped_at`.** Trong `clean_source`, sau C3 và trước C1: `first_seen[job_id]` = `scraped_at` nhỏ nhất trên mọi snapshot và file batch. Ghi vào `metadata.clean.first_scraped_at`.
4. Chạy thật bước 01, rồi sinh trang `docs/presentation/preprocessing_steps/01_clean.html` (`scripts/visualize_preprocessing_steps.py --step 01_clean`).

### Bổ sung 18/11 (L-50, người dùng chốt)

1. **C9**: hằng `STUDY_START = "2026-09-01"`; `out_of_window(flat)` = `parse_date(raw_posted_date)` (hàm của bước 03) có giá trị và nhỏ hơn `STUDY_START`. Bỏ sau C8, trước C6; ghi vào `rejected/` với lý do `BEFORE_STUDY_WINDOW`. Tin không có ngày đăng thì giữ.
2. **C7**: `c7_winner(group)` chọn bản giữ bằng luật chung với D5: `filled` lớn nhất → `authority(nguồn)` (`PLATFORM_AUTHORITY`) → `crawled_at` mới nhất → `job_id` nhỏ nhất.
3. Bộ lọc IT (C4a) nhận `skills_list + category_tags`, vì nhãn chuyên môn TopCV đã chuyển sang `category_tags` ở flattener (prompt 02). Kết quả lọc phải giữ nguyên (C4a 5.424).

## 3. Pseudo code

```text
local_only = files(data/<nguồn>/raw) - keys(R2 raw/<nguồn>)      # chỉ đọc R2
move(local_only → data/_local_only/...)                          # không xóa

for nguồn in 8 nguồn:
    items = read_raw(data/<nguồn>/raw)                           # snapshot + batch
    items -= C3(test, thiếu id/url, sai nguồn)
    first_seen = {job_id: min(scraped_at)}                       # trước C1
    items = C1(snapshot mới nhất) ; C2(batch đã có file riêng)
    flat = flatten(env)                                          # trong bộ nhớ
    metadata.clean = {snapshot_file, it_rule, it_rule_level, it_status,
                      dedup_key, also_on: [], first_scraped_at: first_seen[job_id]}
    items -= C4c(it_status ∈ it_policy[nguồn].drop) ; C5(JD < 50 từ) ; C8(CTV/đa cấp)
    items -= C6(dedup_key trùng trong nguồn)
C7(dedup_key trùng khác nguồn → also_on)
for nguồn: review_sample(...)                                    # không ghi đè file đã có nhãn
check_conserved(mọi nguồn) ; ghi jsonl + report
```

## 4. Ràng buộc

- **Không đẩy gì lên R2** (người dùng: "không có đẩy lên R2"). Chỉ đọc R2 để so key.
- Raw bất biến: không sửa, không xóa file raw; file chỉ có trên máy thì chuyển chỗ và ghi danh sách.
- Không sửa `raw_payload`. Không làm phẳng ra file. Không đổi luật C1–C8 hay `it_policy.json`.
- Không ghi đè file nhãn đã có. Không dựng lại mẫu khi đã có nhãn.
- Chạy thật phải `--source all`. Chạy lẻ thì chỉ dry-run, report vào `_partial/`.
- Không dùng model để phân loại. Nhãn của Claude là để **đo**, không đổi kết quả lọc.
- Không bật Airflow scheduler. Commit chỉ file của việc này. Không push.

## 5. Ví dụ (thành test)

Lấy từ dữ liệu thật ngày 18/11.

| Đầu vào | Kết quả mong đợi | Test |
|---|---|---|
| `topcv 2325743`: `_v1` (20/10 18:44 UTC) và `_v2` (01/11 15:04 UTC) | C1 giữ `2026-11-01/2325743_v2.json`; `first_scraped_at` = `2026-10-20T18:44:44.698712+00:00` | `tests/unit/test_clean_step.py::test_rules_c1_to_c7_and_conservation` (fixture tương tự, `first_scraped_at` = 2026-10-20T06:00:00+00:00) |
| vieclam24h `100160858` có trong `batch_001.json` và có file riêng | C2 bỏ bản batch | như trên |
| glints "HCM925-KỸ THUẬT VIÊN KHUÔN - KCX TÂN THUẬN" | C4a `non_it` → C4c bỏ (chỉ khi `non_it` có trong `it_policy.json[glints].drop`) | `::test_policy_drops_only_approved_status`, `::test_it_rule_whole_words` |
| topcv "Cộng Tác Viên Thiết Kế" | C8 bỏ, `S3_CTV_TITLE`, có dòng trong `rejected/01_clean/topcv.jsonl` | `::test_scope_reason_ctv_va_da_cap`, `::test_c8_va_nguong_50_tu` |
| Cùng `dedup_key` ở glints và jobsgo (`kinh doanh f88\|chuyên viên cao cấp rủi ro gian lận …`) | C7 giữ bản nhiều trường hơn (jobsgo), glints bị bỏ, `also_on` = ["glints:091b32f4…"] | `::test_rules_c1_to_c7_and_conservation` |
| File `it_topcv.csv` đã có nhãn | Không bị ghi đè; nhãn được đọc để đo | `::test_review_file_kept_once_labeled`, `::test_level1_it_labeled_feeds_precision` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Tập raw | Số file trên máy theo nguồn = số key `raw/` trên R2 | Bằng nhau ở 8 nguồn |
| Dry-run | `python scripts/run_preprocessing.py --step clean --source all --dry-run` | Không lỗi, bảo toàn |
| Chạy thật | `python scripts/run_preprocessing.py --step clean --source all` | 13.361 → 4.621; C9 197, C6 189, C7 127, C4a 5.424; từng luật khớp bảng ở đặc tả mục 2 |
| So lần trước | `python scripts/visualize_preprocessing_steps.py --step 01_clean` (so với report trong git HEAD) | Lệch > 5% phải giải thích |
| Lần cào đầu | Đếm tin có `first_scraped_at`; tin nhiều snapshot có `first_scraped_at` < `scraped_at` | 100% có |
| Bộ lọc IT | `extra.review` trong `_all.json` | Ghi số; đích ≥ 95% (hiện 90,8% đúng chung, PRE-12) |
| Nhãn | Người dùng xem `c4b_kiem_mau.html` | Người dùng đồng ý hoặc sửa nhãn |
| Test | `pytest tests/unit/test_clean_step.py -q` | Xanh |
| Ranh giới | `git diff --stat` | Không đụng raw, R2, `collection/` |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 17/11 | Spec 05 v3.0.0 mục 3.1 đã duyệt. Người dùng chốt: "chỉ làm việc với dữ liệu có trên R2 thôi", "không có đẩy lên R2", "chạy từng bước rồi dừng lại tui coi rồi mới thực hiện tiếp" | `7aa63a2` |
| 2 | Duyệt prompt | 17/11 | Đi tắt: không viết prompt riêng; kế hoạch chạy lại 01→04 được duyệt ở plan mode. Prompt này viết lại 18/11 để lưu log | — |
| 3 | Test rồi code | 18/11 | Thêm `first_scraped_at` vào `clean_source`; test `test_rules_c1_to_c7_and_conservation` kiểm `first_scraped_at` | `77cac00` |
| 4 | Dry-run | 17–18/11 | Kiểm R2 (chỉ đọc): máy = R2 + 71 file TopCV ngày 17/11, đã chuyển sang `data/_local_only/`. Dry-run 8 nguồn: 13.361 → 4.799, trùng lần 10/11 | — |
| 5 | Review, chạy thật | 18/11 | Nhãn C4b cũ đã mất. Người dùng chọn phương án (a): "oke làm (a) đi rồi chạy tiếp 01b". Claude gán 643 nhãn, lưu ở `data/preprocessing/gold/it_review/` | `055769e` |
| 5 | (tiếp) | 18/11 | 48 tin để trống. Người dùng chỉ ra các tin IT: "#2,6,14,22,23,25,26,29,32,33,42,43,44,45,46,48 là các tin it rồi bạn tự bổ sung quy luật". Chạy lại 01: precision IT 86,5%, đúng chung 90,8% | `eb06083` |
| 5 | (tiếp) | 18/11 | Chạy lại 01 có `first_scraped_at` (L-49). Trang `01_clean.html` | `77cac00` |
| 1 | Duyệt đặc tả (bổ sung L-50) | 18/11 | Người dùng trả lời các chỗ thiếu PRE-43: "thêm 3 cờ vào silver đi rồi cập nhật lại tài liệu. có thể láy vô tháng. um bỏ nhãn it phần mềm. hmm bạn thấy cáo nào nó có hiệu quả hơn thì lấy cía đó. lấy các loại hợp đồng đó vào sliver đi. bỏ luôn 76 tin glint đó đi"; chọn "Mọi sàn, trước 09/2026" | — |
| 2 | Duyệt prompt | 18/11 | Đi tắt: làm ngay theo câu duyệt ở bước 1; prompt này cập nhật để lưu log | — |
| 3 | Test rồi code | 18/11 | Test trước: `test_c9_out_of_study_window` (6 ca), `test_c7_keeps_most_complete_then_most_authoritative`; đỏ rồi xanh | `591391b` |
| 4 | Dry-run | 18/11 | Không dry-run riêng: dry-run 01b và 02 đọc đầu ra cũ của bước trước nên không đo được tác động. Chạy thật trên máy (không đụng R2), so report với git HEAD | — |
| 5 | Review, chạy thật | 18/11 | Chạy thật 01 → 01b → 02. 01: 13.361 → 4.621; C9 bỏ 197 (glints 100, vietnamworks 82, jobsgo 13, topcv 1, vieclam24h 1); C4a giữ 5.424. L-50; PRE-43 đóng. Chờ người dùng xem | `591391b` + commit tài liệu |
