# Prompt P1: Clean sơ bộ (khử trùng, bỏ rác, phân loại IT ở cả 8 nguồn, chưa bỏ)

> **Cập nhật 04/11/2026: dự án bỏ hẳn model/LLM (JEV qua OpenCode, Gemini).** Mọi đoạn trong file này nói về JEV, LLM, GenAI, dịch JD, `--use-api`, cache hay sổ tiền API đã hết hiệu lực. Thay bằng luật if-else: xem `docs/spec/preprocessing/spec/P0_pipeline_contract.md` mục 6 và `docs/issue_log.md` L-28.

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/P1_clean.md`: luật C1–C7, C4a/C4b/C4c, khóa trùng.
- `docs/spec/preprocessing/spec/P0_pipeline_contract.md` mục 6: luật gọi JEV, cache, `--use-api`.
- `docs/spec/preprocessing/spec/P4_normalization.md` mục N1: bảng 34 tỉnh, dùng cho `tinh_key`.
- `scripts/report_data_issues.py`: `IT_WORDS`, `CLEAR_NON_IT`, `dedup_funnel`.
- `preprocessing/normalization/cross_deduplicator.py`: `normalize_company_name`.
- Tài liệu JEV: https://opencode.ai/v2/docs/console/models/ mục Jev (endpoint `POST https://opencode.ai/inference/systemone/v1/systemone`, model `jev-1.13-free`, câu hỏi kiểu `noul`).

Số hiện tại:
- 10.758 tin sau khi giữ bản mới nhất.
- Ước lượng thô tỉ lệ ngoài IT: 5,6% (ITviec) đến 81,8% (TopDev).
- Trùng theo luật đã chốt: 640 → 409 → 188 tin thừa.

**Quyết định đã chốt:** chưa bỏ tin ngoài IT ở nguồn nào. Phải kiểm từng nguồn trước, vì tỉ lệ cao có thể do crawler kéo sai.

## 2. Việc cần sửa

- **Input:** `data/<nguồn>/raw/**/*.json` (snapshot và file batch).
- **Output:**
  - `data/preprocessing/01_clean/<nguồn>.jsonl`: envelope giữ nguyên, thêm `metadata.clean`.
  - `data/preprocessing/review/it_<nguồn>.csv`: mẫu để gán nhãn tay.
  - `reports/preprocessing/01_clean/<nguồn>.json` và `_all.json`.
- **File mới:**
  - `preprocessing/common/it_filter.py`;
  - `preprocessing/common/province.py` + `preprocessing/dictionaries/provinces_34.json`;
  - `preprocessing/common/jev_client.py` (gọi JEV qua `requests`, có cache);
  - `preprocessing/clean/it_policy.json`: **không tạo**. Bạn tạo sau C4b.
- Viết đủ luật vào `preprocessing/clean/run.py`.

## 3. Pseudo code

```text
run_all(dry_run, use_api):
    per_source = {src: clean_source(src, use_api) for src in SOURCES}   # C1–C6
    cross_source_dedup(per_source)                                       # C7, ghi _all.json
    for src: report.write(); export_review_sample(src); if not dry_run: ghi jsonl

clean_source(src, use_api):
    items = mọi snapshot + mọi tin trong file batch        # input_rows = len(items)
    C1: nhóm theo job_id, giữ max(scraped_at, version); còn lại → dropped "C1"
    C2: tin từ batch mà job_id đã có file riêng → dropped "C2"
    C3: job_id khớp mẫu test hoặc thiếu source_url → dropped "C3"
    for env in items:
        flat = flatten_raw_job_record(env)                 # chỉ để đọc khóa
        c = env.metadata.clean
        c.it_rule = it_filter.classify(flat.title, flat.skills)            # it | non_it | unknown
        c.it_prob = jev.noul(IT_QUESTION, text_for(flat)) if use_api else None
        c.it_status = combine(c.it_rule, c.it_prob)                         # it | non_it | can_kiem
        c.dedup_key = key(flat)
    C4c: policy = đọc preprocessing/clean/it_policy.json nếu có, không có thì {}
         drop nếu policy[src].drop chứa c.it_status (không bao giờ drop "can_kiem")
         rule "C4a" action "flag" ghi số it/non_it/can_kiem; rule "C4c" ghi số bị bỏ (0 khi chưa có policy)
    C5: JD < 30 từ → dropped "C5"
    C6: nhóm theo dedup_key, giữ crawled_at mới nhất, bằng nhau thì giữ bản nhiều trường có giá trị hơn
    return items, report

combine(rule, prob):
    if prob is None: return rule if rule != "unknown" else "can_kiem"
    jev = "it" if prob >= 0.7 else "non_it" if prob <= 0.3 else None
    if jev is None or (rule != "unknown" and rule != jev): return "can_kiem"
    return jev

key(flat) = normalize_company_name(company) | title_norm(title) | province.key(first_location) | iso_week(posted or crawled)

jev.noul(question, text):
    h = sha256(model + question + text)
    if cache/jev/h.json tồn tại: return cached
    if dry_run: đếm call + token, return None
    POST /api/alpha/decisions  {model: "typesafe/jev-1.13", state: {text}, questions: {is_it: {type: "noul", ...}}}
    ghi cache; cộng usage.cost vào report.api

export_review_sample(src):
    50 tin non_it + 30 tin can_kiem (random seed 42), cột: link, tiêu đề, kỹ năng, it_rule, it_prob, nhan_tay (trống)
```

## 4. Ràng buộc

- Không sửa `raw_payload`; chỉ thêm `metadata.clean`. Không ghi ra dữ liệu đã làm phẳng.
- **Không bỏ tin ngoài IT khi chưa có `it_policy.json`.** Không tạo file này thay bạn.
- Khớp từ nguyên vẹn, không khớp chuỗi con (PRE-1).
- Khóa `OPENCODE_API_KEY` đọc từ `.env`, không in ra. Chỉ gọi mạng khi có `--use-api`. Lần đầu chạy toàn bộ thì `--dry-run --use-api` trước, gửi ước tính tiền cho bạn.
- Chỉ gửi cho JEV tiêu đề, kỹ năng, 500 ký tự đầu JD.
- `province.key` viết một lần, P4 dùng lại.
- Thứ tự luật cố định: C1 → C7.

## 5. Ví dụ (thành test, JEV mock)

| Đầu vào | Kết quả |
|---|---|
| `123_v1.json`, `123_v2.json` | giữ `123_v2`, C1 = 1 |
| batch có tin 9 và tin 5; file riêng có tin 5 | giữ tin 9 (batch) và tin 5 (file riêng), C2 = 1 |
| TopDev "Kế toán trưởng", skills `["Kế toán"]`, JEV 0,05 | `it_status=non_it`, **không bị bỏ** (chưa có policy) |
| Như trên, policy `{"topdev": {"drop": ["non_it"]}}` | C4c drop |
| TopDev "Backend Developer", JEV 0,95 | `it` |
| "International Sales Manager" | `it_rule` không phải `it` (chữ "intern" không tính) |
| luật `it`, JEV 0,2 | `can_kiem`, không bao giờ bị bỏ |
| `province.key("TP.HCM")`, `("Bình Dương")`, `("Ho Chi Minh")` | cùng `ho_chi_minh` |
| JobsGO "Cty A" / "CÔNG TY A", cùng tiêu đề, cùng tỉnh, cùng tuần | C6 = 1 |
| TopCV + JobsGO cùng khóa | C7 = 1, bản giữ lại có `also_on` |
| gọi `jev.noul` hai lần cùng đầu vào | lần hai không gọi mạng |

## 6. Cách review

1. `--dry-run --source glints`: luật bảo toàn đúng.
2. `--dry-run --use-api --source all`: xem số lần gọi JEV và ước tính tiền. Bạn duyệt rồi mới chạy thật.
3. **Gán nhãn IT theo nguồn:** mở `data/preprocessing/review/it_<nguồn>.csv`, điền `nhan_tay` (`it` / `non_it`), mỗi nguồn 80 dòng. Mình tính độ đúng của luật và JEV, rồi cùng xác định nguyên nhân (a) crawler, (b) nguồn đăng lẫn, (c) phân loại sai, bằng cách đọc lại URL listing và tham số crawler của nguồn đó.
4. Bạn quyết `it_policy.json` theo từng nguồn. Nguồn có nguyên nhân (a) thì mở việc sửa crawler.
5. `--source all`: sau C1 + C2 còn 10.758; C6 + C7 khoảng 188; lệch hơn 5% thì giải thích.
6. Chạy hai lần: báo cáo giống nhau (nhờ cache).
