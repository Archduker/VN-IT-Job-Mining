# PH3. Lọc phạm vi và gắn ngôn ngữ (bước 3 của file thiết kế)

> **Nháp đặc tả, chờ bạn duyệt** (10/11/2026). Chưa có code. Prompt: `docs/prompting/PH3_loc_pham_vi_va_ngon_ngu.md` (chưa duyệt).
> **[ĐỀ XUẤT]** = mình đoán. **[CẦN CHỐT]** = cần bạn quyết. Số liệu lấy từ `reports/preprocessing/01_clean/_all.json` (đã có trên máy, chỉ đọc): 13.365 → 5.077 tin.

## 1. Mục tiêu

1. Tin không thuộc phạm vi (không IT, JD quá ngắn, CTV/đa cấp) bị loại có lý do, vào `rejected/`, luật bảo toàn `input = output + dropped` đúng.
2. Mọi tin còn lại có cột `lang` (`vi` / `en` / `other`) và `lang_conf` do fastText `lid.176` gán, thay cho luật đếm chữ có dấu (`detect_jd_language`).
3. Đích theo file thiết kế: kiểm tay 100 tin bị loại, loại nhầm dưới 5%. Tiêu chí chính: Accuracy, Consistency.

## 2. Hiện trạng đã đọc trong code

| Phần | Hiện có | Thiếu / lệch |
|---|---|---|
| Lọc IT | `clean/run.py` C4a gắn nhãn luật 2 tầng (5.424 tin gắn), C4c bỏ theo `clean/it_policy.json` (5.409 tin bỏ) | Đã có. PH3 không viết lại luật; chỉ chốt chỗ đặt (C1 bên dưới) |
| JD ngắn | C5 bỏ JD dưới `MIN_JD_WORDS = 30` từ (188 tin) | File thiết kế ghi **50 từ**; code 30 (chính sách 1.B cũ). Xem C2 |
| CTV / đa cấp | Chưa có luật | Cần luật từ khóa. Xem C3 |
| Ngôn ngữ | `text_metrics.detect_jd_language` (tỉ lệ chữ có dấu, ngưỡng `VI_RATIO_MIN`) chạy ở 03 T6, cột `language` (`vi`/`en`) | Không có `other`, không có độ tin cậy; fastText chưa cài, chưa có `lid.176.bin` |
| `rejected/` | PH2 đã tạo `data/preprocessing/rejected/02_integration/` | Dùng cùng khuôn cho bước này |

## 3. Quyết định đặt ở đâu **[CẦN CHỐT] C1**

Bước 3 (lọc) nằm *trước* khử trùng lặp gần trùng nhưng *sau* làm sạch ký tự (cần văn bản sạch để đếm từ và nhận ngôn ngữ). Pipeline hiện tại lại lọc IT/JD ngắn ở **01_clean** (trước 02 và trước làm sạch ký tự).
- **[ĐỀ XUẤT] A:** giữ C4c/C5 ở 01_clean như cũ; thêm luật CTV/đa cấp (C8) ở 01_clean; đo lại JD ngắn trên `*_clean` ở 03 như bước *cờ* (không bỏ); gắn `lang` ở 03 (thay `detect_jd_language`). Ít đụng nhất, không đổi thứ tự bước.
- B: chuyển toàn bộ bước 3 thành step mới sau 03 (cần đổi `P0_pipeline_contract.md` mục 6 và `run_preprocessing.py`). Đúng thứ tự file thiết kế hơn, tốn công hơn.

## 4. Luật đề xuất

| Mã | Luật | Hành động | Ghi chú |
|---|---|---|---|
| S1 | Tin không IT theo `it_policy.json` | drop | đã có (C4c), PH3 chỉ báo lại số liệu |
| S2 | JD dưới N từ (đếm trên `description_clean + requirements_clean`) | drop | N = 30 hay 50: C2 |
| S3 | Tin CTV / đa cấp / việc không phải tuyển dụng (từ khóa tiêu đề + mô tả, danh sách từ khóa trong file mới `preprocessing/clean/scope_keywords.json`) | drop | danh sách từ khóa do bạn duyệt (C3) |
| S4 | Gắn `lang`, `lang_conf` bằng fastText `lid.176` | modify | không bỏ tin; giữ cả JD tiếng Anh (dịch ở 4b) |

## 5. Ngôn ngữ bằng fastText `lid.176`

- Model: `lid.176.bin` (~126 MB) hoặc bản nén `lid.176.ftz` (~1 MB, kém chính xác hơn). Gói `fasttext` chưa cài, file chưa có: **không tự cài, không tự tải**; lead cài và bạn duyệt nguồn tải (C4).
- Cách gọi **[ĐỀ XUẤT]**: `model.predict(text.replace("\n"," "))` trên `description_clean` đã cắt 1.000 ký tự đầu (fastText không nhận xuống dòng, văn bản dài tốn thời gian mà không tăng độ đúng). Nhãn `__label__vi`/`__label__en`; nhãn khác hoặc độ tin cậy dưới ngưỡng thành `other`. Ngưỡng và độ dài cắt: C5.
- JD song ngữ (tiêu đề tiếng Anh, thân tiếng Việt, hoặc nửa-nửa) là ca khó: **[ĐỀ XUẤT]** ghi `lang_conf`, và đo trên bộ gold (PH1) xem fastText đúng hơn luật đếm dấu bao nhiêu trước khi thay hẳn (C6).
- Ghi tên và hash file model, phiên bản gói `fasttext` vào báo cáo (tái lập). Không dùng API ngoài.
- Cột `language` cũ (`vi`/`en`) giữ để các bước sau không gãy; thêm `lang`, `lang_conf`. **[CẦN CHỐT] C7:** có đổi tên/đồng nhất `language` → `lang` không?

## 6. Đo và báo cáo

- `StepReport`: luật S1–S4 (S1–S3 `drop`, S4 `modify`), ví dụ tối đa 3 mỗi luật, không chứa nội dung JD.
- `extra.scope`: số bị loại theo luật và nguồn; `extra.language`: phân bố `vi/en/other`, phân bố `lang_conf`, số tin luật cũ và fastText bất đồng nhau (kèm 10 ví dụ `job_id`).
- Mẫu kiểm tay: 100 tin bị loại, **[ĐỀ XUẤT]** xuất `data/preprocessing/review/scope_rejected_sample.csv` (seed 42, phân tầng theo luật và nguồn) cho bạn gán nhãn "loại nhầm / đúng"; không ghi đè file đã có nhãn (cùng quy tắc `it_<nguồn>.csv`). Đích: loại nhầm < 5%.

## 7. Ranh giới

Không sửa raw; không động R2; không dùng model nào ngoài fastText ở bước này (dịch là 4b); không tải model tự động; `rejected/` không vào git.

## 8. Tiêu chí xong

`rows_in = rows_out + dropped` ở 8 nguồn; mọi tin ra có `lang` ∈ {vi,en,other} và `lang_conf`; loại nhầm < 5% trên 100 tin kiểm tay; báo cáo ghi hash model; `pytest tests/unit` xanh; test dùng văn bản JD thật (không mock model: nếu chưa có `lid.176.bin` thì test đánh dấu `needs_data`, không bỏ qua im lặng).

## 9. Danh sách [CẦN CHỐT]

| Mã | Câu hỏi | Đề xuất |
|---|---|---|
| C1 | Bước 3 nằm ở 01_clean (giữ) hay step mới? | A: giữ ở 01_clean, thêm S3, gắn `lang` ở 03 |
| C2 | Ngưỡng JD ngắn 30 (code) hay 50 từ (file thiết kế)? Đo số tin 30-49 từ trước khi đổi | đo rồi bạn chọn; mặc định giữ 30 |
| C3 | Danh sách từ khóa CTV/đa cấp (ví dụ "cộng tác viên", "đa cấp", "MLM", "kiếm tiền online"): chưa bịa; sẽ đếm token thật như PH2 C10 rồi bạn duyệt. CTV IT hợp lệ (`CTV lập trình`) có bị loại không? | đếm EDA, bạn duyệt; mặc định chỉ loại khi có từ đa cấp/MLM |
| C4 | Nguồn tải `lid.176.bin` vs `.ftz` (126 MB / 1 MB), lead cài `fasttext` | `.bin`, chính xác hơn |
| C5 | Ngưỡng `lang_conf` để ghi `other`; độ dài cắt văn bản | 0.6; 1.000 ký tự |
| C6 | Thay hẳn `detect_jd_language` hay chạy song song một đợt rồi so trên gold | song song, so trên gold PH1 rồi thay |
| C7 | Tên cột `language` hay `lang` | thêm `lang`, giữ `language` |
| C8 | Luật S3 ở 01_clean (cần chạy lại 01 và R2) hay chỉ cờ ở 03 | cờ ở 03 trước, bỏ tin sau khi bạn duyệt mẫu |

## 10. Quyết định đã chốt và kết quả (10/11/2026)

Người dùng chốt (ghi đè mặc định ở mục 9; C1, C5, C6, C8 khác lấy [ĐỀ XUẤT]):

| Mã | Quyết định | Thực hiện |
|---|---|---|
| C1/C8 | Bỏ S2, S3 ngay ở 01_clean (không chỉ cờ) | `clean/run.py`: C5 (JD ngắn), luật mới **C8** (CTV / đa cấp) |
| C2 | Ngưỡng JD ngắn **50 từ** | `MIN_JD_WORDS = 50` |
| C3 | CTV / đa cấp **bị bỏ**, có mã lý do, giữ mẫu bị bỏ để kiểm tay | `clean/scope_keywords.json`: `multi_level_any` (đa cấp, mlm, kiếm tiền online, thu nhập thụ động; xét tiêu đề + JD) -> `S3_MULTI_LEVEL`; `ctv_title` (cộng tác viên, ctv; chỉ xét tiêu đề) -> `S3_CTV_TITLE`. Chạy thật ghi `data/preprocessing/rejected/01_clean/<nguồn>.jsonl` (C5 và C8, có `rule`, `reason`); `scripts/build_scope_rejected_sample.py` xuất `review/scope_rejected_sample.csv` 100 dòng seed 42 cho bạn gán nhãn |
| C4 | `lid.176.bin` tải từ URL chính thức fastText vào `models/fasttext/` (git-ignored, `.gitignore` thêm `models/`) | `scripts/download_lid_model.py`; sha256 `7e69ec5451bc261cc7844e49e4792a85d7f09c06789ec800fc4a44aec362764e`; báo cáo 03 ghi `language_fasttext.sha256` |
| C5 | ngưỡng 0.6; cắt 1.000 ký tự | `preprocessing/common/lang_id.py` (`detect_lang`), nhãn `vi`/`en`/`other`; thiếu model thì `FileNotFoundError`, không lùi về luật cũ |
| C6 | fastText thay luật đếm dấu | 03 T6: `language`, `language_conf` do fastText; `language_rule` giữ luật cũ chỉ để đo bất đồng (`extra.language_fasttext.disagree_with_old_rule`) |
| C7 | tên cột **`language`** (không `lang`) | như trên |

Đo trong bộ nhớ trên raw 8 nguồn (không ghi dữ liệu/báo cáo): 01_clean còn 5.063 tin (C8 bỏ 13, tất cả `S3_CTV_TITLE`, 0 `S3_MULTI_LEVEL`); C5 ở 50 từ bỏ 187 tin so với 184 ở 30 từ (chỉ 3 tin nằm trong 30-49 từ). Ngôn ngữ (mô tả thô) trên 5.063 tin: vi 3.690, en 1.365, other 8; fastText khác luật cũ ở 37 tin. **Chưa đo:** loại nhầm < 5% trên 100 tin kiểm tay (chờ bạn gán nhãn); đối chiếu `language` với gold PH1.
