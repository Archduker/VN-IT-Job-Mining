# Prompt PH3: lọc phạm vi và gắn ngôn ngữ (fastText lid.176)

> **Nháp, chờ bạn duyệt.** Các điểm **[CẦN CHỐT]** (C1 đến C8) trong `docs/spec/preprocessing/spec/PH3_loc_pham_vi_va_ngon_ngu.md` phải chốt trước khi giao prompt này cho agent code. Chưa có code.

## 1. Ngữ cảnh

Đọc trước: spec PH3 (mục 2 hiện trạng, mục 4-5 luật); `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` bước 3, mục 3.2, 4.2-4.3; `preprocessing/CLAUDE.md`; `docs/spec/preprocessing/spec/P1_clean.md`, `P0_pipeline_contract.md`; spec PH2 (khuôn `rejected/`).
Code: `preprocessing/clean/run.py` (C4a, C4c, C5), `clean/it_policy.json`, `preprocessing/transformation/text_metrics.py` (`detect_jd_language`), `transformation/run.py`, `preprocessing/common/step_report.py`.

Hiện tại: bỏ IT và JD ngắn (30 từ) đã có ở 01_clean; chưa có luật CTV/đa cấp; ngôn ngữ do luật đếm chữ có dấu; chưa cài `fasttext`, chưa có `lid.176.bin`.

## 2. Việc cần làm (sau khi chốt C1 đến C8)

1. `preprocessing/common/lang_id.py` (mới): `detect_lang(text) -> (lang, conf)` bọc fastText; tải model từ đường dẫn trong `.env` hoặc `preprocessing/dictionaries/` (không tự tải, thiếu file thì ném lỗi rõ ràng, không lùi về luật cũ); ghi hash SHA-256 file model.
2. `scope_keywords.json` (mới): chỉ các mục bạn đã duyệt (C3); luật S3 theo C8.
3. Thêm luật S2/S3 theo C1/C2; S4 gắn `lang`, `lang_conf` (C5, C7); báo cáo theo spec mục 6; `rejected/<bước>/<nguồn>.jsonl` theo khuôn PH2.
4. Script xuất mẫu kiểm tay 100 tin bị loại (seed 42), không ghi đè file đã có nhãn.

## 3. Pseudo code

```text
for rec in records:
    if not it_in_scope(rec): reject("S1")
    elif words(rec.description_clean + rec.requirements_clean) < N: reject("S2")
    elif matches(scope_keywords, rec): reject("S3")
    else:
        lang, conf = detect_lang(rec.description_clean[:1000].replace("\n", " "))
        rec.lang = lang if conf >= T else "other"; rec.lang_conf = conf
check: input == output + dropped
```

## 4. Ràng buộc

Không sửa raw; không động R2; không tự cài gói hoặc tải model; không mock fastText (test dùng JD thật, thiếu model thì `needs_data`); không đưa nội dung JD vào `reports/`; không commit; sửa test cũ nào khẳng định hành vi sai thì ghi lý do; xong thì ghi `docs/issue_log.md`.

## 5. Ví dụ (thành test, dùng chuỗi thật)

| Đầu vào | Mong đợi |
|---|---|
| JD ITviec tiếng Anh thật (fixture) | `lang=en`, `lang_conf` ≥ ngưỡng |
| JD TopCV tiếng Việt thật | `lang=vi` |
| JD song ngữ thật (chọn từ Glints) | ghi `lang_conf` thấp hoặc `other`, ghi vào mẫu bất đồng |
| JD dưới N từ | S2, vào rejected, không vào output |
| Tin có từ đa cấp đã duyệt | S3 |
| Thiếu `lid.176.bin` | lỗi rõ ràng |

## 6. Cách review

`pytest tests/unit -q`; chạy bước với 8 nguồn, so `rows_in = rows_out + dropped`; đọc 100 tin bị loại (loại nhầm < 5%); đối chiếu `lang` fastText với nhãn gold PH1; xem hash model trong báo cáo; `git diff --stat` không đụng raw, R2, `collection/`.
