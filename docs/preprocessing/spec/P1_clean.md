# P1. Clean sơ bộ: khử trùng, bỏ rác, phân loại IT (chưa bỏ)

> **Cập nhật 04/11/2026: dự án bỏ hẳn model/LLM (JEV qua OpenCode, Gemini).** Mọi đoạn trong file này nói về JEV, LLM, GenAI, dịch JD, `--use-api`, cache hay sổ tiền API đã hết hiệu lực. Thay bằng luật if-else: xem `docs/preprocessing/spec/P0_pipeline_contract.md` mục 6 và `docs/issue_log.md` L-28.

> Trạng thái: **đã làm, đã chạy thật 03/11/2026 bằng luật; còn chạy JEV (PRE-9)**. Kết quả và các điểm khác đặc tả: mục 9.
> Cần P0 xong trước. Prompt: `docs/prompting/P1_clean.md`.
> Số liệu: `docs/preprocessing/data_issues_2026-11-03.md`, đo lại ngày 03/11 bằng `scripts/report_data_issues.py`.

## 1. Ngữ cảnh

Clean chạy trước mọi bước để các bước sau xử lý ít dòng hơn và không xử lý tin vô ích.

| Vấn đề | Số liệu | Mã |
|---|---|---|
| Nhiều version của cùng tin | 1.975 snapshot v>1 (TopDev 1.105, VietnamWorks 725) | B1 |
| File batch cũ trùng file từng tin | VietnamWorks 931 tin, Vieclam24h 616 tin | B2, PRE-8 |
| Tin ngoài IT ở **mọi nguồn** | Ước lượng thô theo tiêu đề: TopDev 81,8%, Vieclam24h 55,0%, JobsGO 32,7%, CareerViet 23,8%, VietnamWorks 23,0%, TopCV 21,6%, Glints 18,1%, ITviec 5,6%. Riêng TopDev đã chứng minh crawler kéo sai phạm vi: API bỏ qua `category_ids=1` (14.572 tin cả hai cách gọi). Các nguồn khác **chưa rõ nguyên nhân**: có thể do crawler, do nguồn đăng lẫn, hoặc do bộ đếm thô sai | A1 |
| JD rỗng | TopCV 11,1%; JD dưới 200 ký tự: JobsGO 90, TopDev 60, TopCV 49 | I1 |
| Trùng theo luật đã chốt | công ty + tiêu đề: 640 tin thừa; + tỉnh: 409; + tuần đăng: 188 (đo lại 03/11; HTML ghi 636/407 vì dữ liệu đã tải bù) | B3 |

**Vì sao chưa bỏ tin ngoài IT:** cờ do luật từ khóa gắn chưa nói lên tất cả. Nếu tỉ lệ cao là do crawler kéo sai, thì phải sửa ở collection, và bỏ ở pre-processing chỉ che lỗi đi. Nếu là do bộ phân loại sai, thì bỏ đi sẽ mất tin IT thật. Vì vậy phải kiểm từng nguồn (C4b) rồi mới quyết (C4c).

## 2. Input

- `data/<nguồn>/raw/**/*.json`: mọi snapshot `<id>_v<N>.json` và file batch cũ. Bỏ các thư mục `_index`, `_quality`, `_listing`, `_listing_failures`.
- `input.rows` = số snapshot + số tin trong file batch, để Monitoring thấy cả số C1, C2 bỏ.

## 3. Output

- `data/preprocessing/01_clean/<nguồn>.jsonl`: mỗi dòng một envelope, **giữ nguyên `raw_payload`**, thêm khối `metadata.clean`:

```json
{"metadata": {"job_id": "…", "source": "topcv", "…": "…",
              "clean": {"it_rule": "non_it", "it_prob": 0.12, "it_status": "non_it",
                        "dedup_key": "cong ty a|python developer|ha_noi|2026-W44",
                        "also_on": ["jobsgo:123"], "snapshot_file": "raw/2026-11-01/123_v2.json"}},
 "raw_payload": {"…": "nguyên bản"}}
```

- `data/preprocessing/review/it_<nguồn>.csv`: mẫu để bạn gán nhãn tay (C4b).
- Báo cáo `reports/preprocessing/01_clean/<nguồn>.json` và `_all.json` theo schema P0.

## 4. Hướng xử lý (đúng thứ tự)

Để đọc tiêu đề, công ty, tỉnh, ngày, kỹ năng, JD, Clean **mượn** `flatten_raw_job_record` (`preprocessing/integration/json_flattener.py`). Kết quả làm phẳng chỉ dùng để tính khóa, không ghi ra.

| Mã | Luật | Hành động | Ví dụ trước → sau |
|---|---|---|---|
| C1 | Mỗi `job_id` giữ snapshot mới nhất theo (`scraped_at`, `version`) | drop bản cũ | `123_v1`, `123_v2` → giữ `123_v2` |
| C2 | Tin trong file batch đã có file riêng thì bỏ; chưa có thì giữ bản batch | drop | VNW `raw_batch.json` 931 tin → giữ 206 tin (đã đăng ký PENDING, L-21) |
| C3 | Bản ghi test (`job_id` dạng `job-mot-100`, nguồn lạ, thiếu `source_url`) | drop | — |
| C4a | **Phân loại IT ở cả 8 nguồn** | flag, **không bỏ** | xem dưới |
| C4b | **Kiểm từng nguồn**: lấy mẫu để gán nhãn tay, đo độ đúng, tìm nguyên nhân | xuất file review | xem dưới |
| C4c | Bỏ tin ngoài IT **chỉ khi** `preprocessing/clean/it_policy.json` (file mới, bạn duyệt) có chính sách cho nguồn đó | drop theo chính sách | chưa có file → không bỏ tin nào |
| C5 | JD dưới 30 từ (giữ chính sách 1.B cũ) | drop | JD "Liên hệ để biết thêm" → bỏ |
| C6 | Trùng trong cùng nguồn theo `dedup_key` | drop; giữ bản cào mới nhất, bằng nhau thì giữ bản nhiều trường có giá trị hơn | 2 tin JobsGO cùng khóa → giữ 1 |
| C7 | Trùng khác nguồn theo `dedup_key` | giữ một bản (nhiều trường có giá trị nhất), các bản khác ghi vào `also_on` | TopCV + JobsGO cùng khóa → giữ TopCV, `also_on=["jobsgo:…"]` |

### C4a. Phân loại IT

Mỗi tin có ba giá trị:

- `it_rule` ∈ {`it`, `non_it`, `unknown`}: luật từ khóa `preprocessing/common/it_filter.py` (file mới).
  - Khớp **theo từ nguyên vẹn**, không theo chuỗi con (bài học PRE-1: "ba" khớp "backend", "intern" khớp "international").
  - Là `it` khi tiêu đề có từ IT (developer, engineer, lập trình, tester, devops, data…), hoặc có ít nhất 1 kỹ năng công nghệ trong từ điển kỹ năng.
  - Là `non_it` khi tiêu đề có từ ngoài IT rõ ràng (kế toán, tài xế, giáo viên, kinh doanh, bán hàng…) và không có kỹ năng công nghệ.
  - Các trường hợp còn lại là `unknown`.
  - Bộ từ khởi đầu lấy từ `IT_WORDS`, `CLEAR_NON_IT` trong `scripts/report_data_issues.py`.
- `it_prob`: JEV `noul` (P0 mục 6), chỉ khi chạy với `--use-api`. Câu hỏi: "Tin này tuyển một vị trí công việc thuộc ngành Công nghệ thông tin (phát triển phần mềm, dữ liệu, hạ tầng, kiểm thử, bảo mật, quản lý sản phẩm công nghệ)?". Đầu vào: tiêu đề + kỹ năng + 500 ký tự đầu JD. Không có API thì `null`.
- `it_status` ∈ {`it`, `non_it`, `can_kiem`}:
  - `it` hoặc `non_it` khi luật và JEV cùng kết luận (prob ≥ 0,7 là IT, ≤ 0,3 là ngoài IT).
  - `can_kiem` khi hai bên lệch nhau, hoặc 0,3 < prob < 0,7, hoặc luật ra `unknown` mà chưa có JEV.

### C4b. Kiểm từng nguồn (bạn và mình cùng làm)

- Với mỗi nguồn, xuất `data/preprocessing/review/it_<nguồn>.csv` gồm 50 tin `non_it` và 30 tin `can_kiem` (seed 42; nguồn có ít hơn thì lấy hết). Mỗi dòng có link tin, tiêu đề, kỹ năng, `it_rule`, `it_prob`, và cột `nhan_tay` để trống cho bạn điền.
- Sau khi bạn gán nhãn, báo cáo ghi theo từng nguồn:
  - độ đúng của luật và của JEV;
  - **nguyên nhân** chiếm phần lớn:
    - (a) **crawler kéo sai phạm vi**: danh mục hoặc tham số lọc sai, như TopDev `category_ids`. Kiểm bằng cách đọc lại URL listing và tham số trong `collection/sources/<nguồn>/`;
    - (b) nguồn tự đăng lẫn tin ngoài IT;
    - (c) bộ phân loại sai.
- Nguyên nhân (a) thì mở việc ở `KNOWN_ISSUED.md` mục Web scraping để sửa phạm vi cào.

### C4c. Chính sách bỏ tin (chỉ sau C4b)

`preprocessing/clean/it_policy.json` (file mới, chỉ bạn quyết):

```json
{"topdev": {"drop": ["non_it"], "approved_on": "…", "evidence": "C4b: JEV đúng 49/50"},
 "topcv":  {"drop": [], "note": "giữ, chờ sửa crawler"}}
```

- Nguồn không có trong file thì không bỏ tin nào. `can_kiem` không bao giờ bị bỏ tự động.
- Báo cáo ghi rõ chính sách đang áp dụng và ngày duyệt.

### Khóa trùng (C6, C7)

`dedup_key = company_norm | title_norm | tinh_key | week`:

- `company_norm`: dùng lại `normalize_company_name` trong `preprocessing/normalization/cross_deduplicator.py` ("CÔNG TY CỔ PHẦN A" = "Cty A").
- `title_norm`: chữ thường, gộp khoảng trắng, bỏ dấu câu ở đầu và cuối.
- `tinh_key`: mã tỉnh trong **34 tỉnh/thành sau sáp nhập**, qua `preprocessing/common/province.py` (file mới), đọc bảng `preprocessing/dictionaries/provinces_34.json` (file mới, định nghĩa ở P4 mục N1).
  - Tên cũ được gộp về tên mới: "Bình Dương" → `ho_chi_minh`, "Quảng Nam" → `da_nang`.
  - Lấy tỉnh đầu tiên của `working_locations`, không có thì lấy từ `raw_location_text`.
  - Bước 04 dùng lại module này.
  - Nếu không chuẩn hóa tỉnh, nhóm trùng khác nguồn tụt từ 171 xuống 9 chỉ vì cách viết tên khác nhau.
- `week`: tuần ISO của ngày đăng. Thiếu ngày đăng (TopCV, TopDev) thì dùng tuần cào.
- Không dùng trụ sở công ty, vì TopDev 0% có địa chỉ.

## 5. Ranh giới

- Không sửa `raw_payload`; chỉ thêm `metadata.clean`.
- Không làm phẳng output, không parse lương, không ghi giá trị đã chuẩn hóa (khóa chuẩn hóa chỉ dùng để so).
- Không bỏ tin ngoài IT khi chưa có chính sách đã duyệt.

## 6. Monitoring thấy gì

- Phễu toàn bộ: snapshot + batch → sau C1 → … → sau C7, theo từng nguồn.
- **Khối "Kiểm tin ngoài IT"**:
  - theo nguồn: số `it`, `non_it`, `can_kiem`;
  - độ đúng của luật và của JEV trên mẫu đã gán;
  - nguyên nhân (a), (b), (c);
  - chính sách: "chưa duyệt" hoặc ngưỡng đã duyệt;
  - 3 ví dụ mỗi nhóm, kèm link.
- Nhóm trùng khác nguồn: cặp nguồn nào trùng nhiều nhất.
- Khối API: số lần gọi JEV, số lần trúng cache, chi phí.

## 7. Tiêu chí xong và cách review

- Luật bảo toàn đúng ở cả 8 nguồn và `_all`.
- Chạy thử `glints` (nhỏ nhất, 331 tin) trước, rồi `topdev`, rồi cả 8.
- Số khớp với lần đo trước: sau C1 + C2 còn 10.758 tin; C6 + C7 bỏ khoảng 188. Lệch hơn 5% thì giải thích.
- Chưa có `it_policy.json` thì số tin ra = số tin vào trừ C1, C2, C3, C5, C6, C7. C4 bỏ 0 tin.
- C4b: đủ 8 file review. Bạn gán nhãn xong thì báo cáo có độ đúng theo nguồn.
- Test (mỗi luật một test, dữ liệu trong `tmp_path`, JEV mock):
  - C1 lấy bản mới nhất;
  - C2 bỏ tin batch đã có file riêng;
  - C4a: "Kế toán trưởng" → `non_it`; "Backend Developer" → `it`; "International Sales" không thành `it` chỉ vì chữ "intern";
  - C4c: không có policy thì không bỏ; có policy `topdev: drop non_it` thì chỉ bỏ `non_it` của TopDev, giữ `can_kiem`;
  - C6: "Cty A" và "CÔNG TY A" cùng khóa;
  - `tinh_key("TP.HCM") == tinh_key("Bình Dương") == "ho_chi_minh"`.

## 8. Việc ngoài phạm vi

- Sửa phạm vi cào của nguồn có nguyên nhân (a), làm ở collection. Đã biết chắc: TopDev.

## 9. Kết quả lần chạy thật 03/11/2026

Lệnh: `python scripts/run_preprocessing.py --step clean --source all` (chưa có `--use-api`). Code: `preprocessing/clean/run.py`, `preprocessing/common/`. Test: `tests/unit/test_clean_step.py`.

| Luật | Số dòng |
|---|---|
| Input (snapshot + tin trong file batch) | 14.292 |
| C1 snapshot cũ | 1.987 |
| C2 tin batch đã có file riêng | 1.341 |
| C3 bản ghi test | 0 |
| C4a gắn cờ (ngoài IT + cần kiểm) | 6.414 |
| C4c bỏ theo `it_policy.json` (7 nguồn bỏ `non_it`, ITviec giữ hết) | 2.112 |
| C5 JD dưới 30 từ (TopCV chiếm phần lớn, SCRAPE-16) | 320 |
| C6 trùng trong nguồn | 144 |
| C7 trùng khác nguồn | 15 |
| **Output** | **8.373** |

- Sau C1–C3 còn 10.964 tin = 10.758 (số đo trong data_issues, không tính file batch) + 206 tin chỉ có trong file batch VietnamWorks.
- C6 + C7 = 159 tin. Con số này nhỏ hơn 188 trong data_issues vì C5 và C4c chạy trước, đã bỏ một phần tin trùng.
- Độ đúng của luật trên nhãn tay (mỗi nguồn khoảng 80 tin): trong nhóm `non_it` (nhóm chính sách bỏ), 293/294 tin đúng là ngoài IT.

Điểm khác đặc tả, đã chốt khi làm:

- **Luật IT chặt hơn mục 4:** từ yếu ("kỹ thuật", "engineer", "security") một mình không còn tính là IT, mà ra `unknown` để thành `can_kiem`. Phải có ít nhất 2 kỹ năng công nghệ mới tính là IT. "Ngân hàng", "xây dựng", "content" bỏ khỏi danh sách từ ngoài IT, vì chúng làm mất tin IT ngân hàng ("Hệ thống ngân hàng lõi - K.CNTT") và tin "Xây dựng mô hình phát hiện gian lận".
- C3 chạy trước C1 (bản ghi thiếu `job_id` không gom được), báo cáo vẫn ghi theo thứ tự C1 → C7.
- Một nguồn sai luật bảo toàn thì cả bước dừng, chưa nguồn nào được ghi.
- Báo cáo `_all` có thêm `extra.cross_source_pairs` (cặp nguồn trùng: giữ → bỏ) và `extra.review` theo nguồn (`status_non_it_correct/status_non_it` là độ đúng của nhóm sẽ bị bỏ).

