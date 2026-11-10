# Prompt PH5: dịch JD tiếng Anh sang tiếng Việt bằng `VietAI/envit5-translation` (bước 4b)

> **Nháp, chờ bạn duyệt.** Phụ thuộc: PH0 spike (chưa có báo cáo lúc viết), PH3 (`lang`), PH4 (khử trùng). Các điểm **[CẦN CHỐT]** C1-C12 trong spec phải được chốt trước. "[ĐỀ XUẤT]" là mặc định nếu bạn không đổi. Mọi con số về tốc độ, VRAM, giới hạn token: **lấy từ báo cáo spike**, nếu chưa có thì việc đầu tiên của agent là dừng và báo.

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/PH5_dich_anh_viet_envit5.md` (mục 2 hiện trạng đã đo, mục 3 quyết định, mục 4 luật).
- `reports/preprocessing/_spike/envit5_*.md` (báo cáo spike của PH0, nếu có: điền mục 2.3 của spec từ đây).
- `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` bước 4b, mục 3.2, 4.2, 4.4.
- `docs/spec/preprocessing/spec/P3_transformation.md` (T6b, cột `*_vi`, `translated_by`, mục 80), `PH2_schema_va_lam_sach_ky_tu.md` (`text_clean`, hàm fold), `PH4_*.md`.
- Code: `preprocessing/transformation/{run,text_metrics}.py` (`detect_jd_language`, `EN_VI_RECRUITMENT_DICTIONARY`), `preprocessing/common/{step_report,text_clean}.py`, `preprocessing/deduplication/text_norm.py` (`fold`).

Hiện tại (đo 10/11/2026 trên 5.077 tin của 01_clean, trước PH4):
- Chưa có code dịch. `torch 2.15.0+cu132`, `transformers 5.22.2`, `sentencepiece 0.2.3` có trong `.venv`; model chưa tải.
- 1.347 tin `en` (26,5%): topcv 80, topdev 60, vietnamworks 352, careerviet 65, vieclam24h 10, itviec 604, glints 106, jobsgo 70. Tổng 471.214 từ; trung vị 314 từ/JD, P99 1.063, max 1.489; trung vị 18 dòng/JD, 26.318 dòng; dòng dài: P99 112 từ, max 626, 339 dòng > 100 từ.
- Máy: GPU Quadro T1000 4 GB, RAM 30 GB.
- Mâu thuẫn cần bạn chốt (C2): file thiết kế dùng bản dịch cho bước sau, P3 mục 80 dùng bản gốc.

## 2. Việc cần sửa

**Input:** đầu ra PH4 (`data/preprocessing/01b_deduplication/<nguồn>.jsonl`) đã có `language` (hoặc `lang` từ PH3). **Output:** `data/preprocessing/translation/` (git-ignore): `translations_cache.jsonl`, `<nguồn>.jsonl` hoặc bảng gộp với cột mới, `samples_for_review.json`; `reports/preprocessing/translation/<nguồn>.json` + `_all.json`.

1. `preprocessing/translation/` (mới, C10 [ĐỀ XUẤT]):
   - `masking.py`: `mask(text, no_translate) -> (masked, tokens)` và `unmask(text, tokens) -> text`; token giữ chỗ dạng do spike xác nhận qua được model.
   - `chunking.py`: `split(text, max_tokens, tokenizer)`: theo dòng, vượt giới hạn thì theo câu, còn dài thì theo số token; `join(parts)` giữ thứ tự và xuống dòng; bullet `- ` đứng ngoài đoạn gửi model.
   - `validate.py`: `tokens_ok`, `numbers_equal`, `length_ratio_ok` (ngưỡng từ spike).
   - `translator.py`: bao `transformers` (tokenizer + model), `do_sample=False`, tham số sinh trong `dictionaries/translation_policy.json`; `translate_batch(chunks)`. Tải model, thiết bị (GPU/CPU), `revision` ghim lấy từ policy/manifest.
   - `cache.py`: khóa `sha256(model_id + revision + tham_số + đoạn_đã_che)`, ghi nối tiếp (append) để resume.
   - `run.py`: `run(sources, dry_run, translate=False)`.
2. `preprocessing/dictionaries/no_translate.json` (mới) **chỉ chứa mục bạn duyệt** (C6). Nếu chưa có danh sách, tạo `{}` và chỉ viết hàm + test bằng từ điển nhỏ dựng trong test. Kèm script đếm tần suất tên kỹ năng trong `skills_list` của tin `en` để bạn duyệt (chỉ đọc).
3. Cột mới: `description_vi`, `requirements_vi`, `translated_by`, `translation_status`, `translation_chunks`, `translation_source`, và `*_vi_norm`, `*_vi_fold` (C2/C5; hàm của PH2, không viết bản fold mới). Tin `vi`: `*_vi` = gốc, `translated_by = null`.
4. Báo cáo + manifest: mục 5 của spec (model, revision, thư viện, thiết bị, tham số, seed, cache hit/miss, thời gian, VRAM đỉnh, số đoạn `failed`).
5. `STEPS` / `scripts/run_preprocessing.py`: thêm bước nếu C10 chọn bước riêng; `03_transformation` đọc cột `*_vi` (không sửa `*_clean`). Cập nhật P3 mục 80 theo C2.
6. Dry-run: chọn tin, che và tách đoạn, đếm; **không tải model, không gọi model**. Chạy thật cần cờ `--translate`.
7. `scripts/build_translation_review_sample.py` (mới): 50 JD, `seed=42`, phân tầng theo nguồn (C11), ghi file mẫu cho bạn kiểm tay (gốc cạnh dịch), không đưa vào `reports/`.

## 3. Pseudo code

```text
run(sources, dry_run, translate):
    rows = đọc đầu ra PH4
    todo = [r for r in rows if r.lang == "en"]                       # X0
    cfg  = đọc translation_policy.json; nt = đọc no_translate.json
    if not dry_run and translate: model = load(cfg.model_id, cfg.revision, device)
    for r in todo:
        for field in ("description_clean", "requirements_clean"):    # C1
            masked, toks = mask(r[field], nt)                        # X1
            chunks = split(masked, cfg.max_tokens)                   # X2
            out = []
            for c in chunks:
                key = sha256(model_id + revision + params + c)
                if key in cache: out.append(cache[key]); continue
                if dry_run or not translate: out.append(None); continue
                t = model.translate(c)                               # X3
                if not valid(c, t): t = model.translate(c)           # thử lại 1 lần
                if not valid(c, t): t = c; r.translation_status = "failed"   # X5 giữ gốc
                cache[key] = t; out.append(t)
            vi = unmask(join(out), toks)                             # X4
            r[field_vi], r.translated_by = vi, cfg.model_id
        r.vi_norm, r.vi_fold = make_text_columns(r.vi)               # X6
    tin vi: *_vi = gốc, translated_by = None
    report: input == output (không bỏ tin); extra.translation = manifest
valid(src, dst): tokens_ok(src,dst) and numbers_equal(src,dst) and dst.strip() and length_ratio_ok(src,dst)
```

## 4. Ràng buộc

- Model **duy nhất**: `VietAI/envit5-translation`. Không OpenJev, JEV, Qwen, Gemini, không API ngoài, không model khác.
- Không sửa raw, không sửa `raw_*`, không sửa `*_clean`; chỉ thêm cột. Không dịch `job_title`, `company_name`, `skills_list`, `benefits_list` (C1).
- Không cài gói mới; tải model từ mạng và đặt thư mục cache cần bạn đồng ý (C9). Không đưa trọng số vào git. Không động tới R2, không chạy scheduler, không commit.
- Không bịa số tốc độ/VRAM/giới hạn token: lấy từ báo cáo spike; nếu thiếu thì dừng.
- Không đưa nội dung JD (gốc hoặc dịch) vào `reports/`. `data/preprocessing/translation/` không vào git.
- Bước không bỏ tin: `rows_out = rows_in`. Đoạn hỏng giữ bản gốc và ghi `failed`.
- Sinh xác định (`do_sample=False`); cùng đầu vào + cache = 0 lần gọi model.
- Test không dùng dữ liệu giả: chuỗi thật lấy từ `tests/fixtures/topdev/standard.json`, `tests/fixtures/itviec/*`, hoặc tin `en` thật ghi `job_id` trong chú thích. Test logic bao ngoài (che/trả token, tách đoạn, cache, validate) **không tải model**: hàm dịch được tiêm vào bằng hàm thay thế chỉ để kiểm đường dẫn code; chất lượng dịch chỉ đo bằng model thật.
- Xong thì ghi `docs/issue_log.md` và bẫy mới vào `preprocessing/CLAUDE.md`.

## 5. Ví dụ (thành test)

| Đầu vào | Kết quả mong đợi |
|---|---|
| `"Experience with Python and Docker is a plus"`, `no_translate={"Python","Docker"}` | `mask` ra 2 token giữ chỗ; `unmask(mask(x)) == x` |
| Đoạn có `"15-25 million VND"`, `"3+ years"` | `numbers_equal(src, dst)` True khi dịch giữ số; False nếu dst thiếu `15` |
| Dịch thay thế làm rơi token giữ chỗ | `tokens_ok` False → thử lại 1 lần → vẫn hỏng → giữ gốc, `translation_status = "failed"` |
| Dòng 626 từ (đo thật trong tin `en`) | `split` ra nhiều đoạn, mỗi đoạn ≤ giới hạn token (giá trị từ spike); `join` đúng thứ tự |
| JD 18 dòng bullet `- ...` | sau `join`, 18 dòng, dấu `- ` giữ nguyên, thứ tự không đổi |
| Chạy hai lần liên tiếp | lần hai: 0 lần gọi model, đầu ra giống hệt; `cache_hit` = tổng đoạn |
| Đổi `model_revision` hoặc tham số sinh | khóa cache khác, không dùng cache cũ |
| Tin `vi` | `description_vi == description_clean`, `translated_by is None` |
| `--dry-run` | không import/tải model; báo số tin `en`, số đoạn |
| `rows_in` | `= rows_out`; tin `en` đều có `description_vi` không rỗng |
| `*_vi_fold` của tin dịch | cùng hàm `fold` với PH2 (so với `text_norm.fold`) |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit -q` | xanh, test logic chạy không cần model |
| Spike | đối chiếu mục 2.3 của spec với báo cáo spike | đã điền, số khớp |
| Dry-run | `python scripts/run_preprocessing.py --step translation --source all --dry-run` | báo số tin `en` và số đoạn; không tải model |
| Chạy thử | glints (106 tin `en`), `--translate` | không OOM; báo thời gian, VRAM đỉnh, số `failed` |
| Tái lập | chạy lần hai | 0 lần gọi model; hash đầu ra giống hệt |
| Manifest | đọc `extra.translation` | có model, revision, thư viện, thiết bị, tham số, thời gian |
| **Kiểm tay** | bạn đọc 50 JD (C11), gốc cạnh dịch | kỹ năng và số liệu không đổi (ngưỡng theo C12) |
| Git | `git status` | không file dữ liệu/bản dịch/model trong git |
| Ranh giới | `git diff --stat` | không đụng `collection/`, R2, raw, cột `*_clean` |
