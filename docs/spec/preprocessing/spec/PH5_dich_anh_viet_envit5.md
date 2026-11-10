# PH5. Dịch JD tiếng Anh sang tiếng Việt bằng `VietAI/envit5-translation` (bước 4b của file thiết kế)

> **Nháp đặc tả, chờ bạn sửa** (10/11/2026). Chưa có code. Prompt: `docs/prompting/PH5_dich_anh_viet_envit5.md` (chưa duyệt).
> **[ĐỀ XUẤT]** = mình đoán. **[CẦN CHỐT]** = mình không biết, cần bạn quyết.
> Số liệu đo ngày 10/11/2026, chỉ đọc, trên `data/preprocessing/01_clean/*.jsonl` (5.077 tin). **Chưa có báo cáo spike** `reports/preprocessing/_spike/` (thư mục không tồn tại lúc viết), nên **mọi con số về tốc độ, VRAM, giới hạn token, kích thước model đều chưa biết**; đặc tả để trống, không đoán. Khi spike xong, điền mục 2.3 và chốt C3, C4.
> Quyết định đã chốt (10/11/2026): model duy nhất là `VietAI/envit5-translation`, chạy local; giữ cột gốc và cột dịch; cache theo hash; ghi tên và phiên bản model vào manifest. Máy: GPU Quadro T1000 4 GB, RAM 30 GB.

## 1. Mục tiêu

Dịch **toàn bộ** JD tiếng Anh sang tiếng Việt để các bước sau (từ điển viết tắt, trích kỹ năng, tách từ, TF-IDF) làm việc trên một ngôn ngữ (tiêu chí **Consistency**, **Completeness**), không làm hỏng nội dung: tên kỹ năng/công nghệ, số liệu (lương, năm kinh nghiệm) giữ nguyên. Raw và cột gốc bất biến. Đích nghiệm thu theo file thiết kế: **kiểm tay 50 JD đã dịch, kỹ năng và số liệu không bị đổi**.

Vị trí: sau lọc phạm vi (PH3) và khử trùng (PH4), trước tách section và trích kỹ năng (mục 3.2 file thiết kế).

## 2. Hiện trạng và so với thiết kế (đã đo)

### 2.1. Code và dữ liệu

| Thiết kế | Đang có | Lệch |
|---|---|---|
| Cột `lang` bằng fastText `lid.176` (PH3) | Cột `language` (`vi`/`en`) do `text_metrics.detect_jd_language` (tỉ lệ chữ có dấu < ngưỡng `VI_RATIO_MIN` thì `en`) trong `transformation/run.py` | PH5 phụ thuộc PH3 sẽ đổi cách gắn `lang`; trước khi PH3 xong, PH5 dùng `language` hiện có |
| Dịch toàn bộ JD `lang=en` | **Chưa có.** P3 mục T6b chỉ là đặc tả (cột `description_vi`, `requirements_vi`, `translated_by`), không có code, 0 mục `envit5` trong `preprocessing/` | Cần xây |
| Cột gốc giữ nguyên, cột Việt thêm | P3: `description_vi`, `requirements_vi`, `translated_by` | Tên cột chưa chốt với PH2 (`*_clean`, `*_norm`, `*_fold`). Xem C5 |
| Tính lại `text_norm`, `text_fold` trên bản dịch | P3 mục 80: "mọi bước sau rút thông tin từ bản gốc, bản dịch chỉ để đọc" | **Mâu thuẫn giữa file thiết kế (dùng bản dịch cho bước sau) và P3 (dùng bản gốc).** Xem C2 |
| `<trường>_source = model`, tên + phiên bản model vào `meta.json` | Chưa có | Cần xây; "manifest" của bạn = `meta.json`/báo cáo bước |
| Che thuật ngữ bằng token giữ chỗ | P3 T6b mô tả "bảng không dịch" theo `docs/spec/06_processing_spec.md` mục 4.3; từ điển `skills.json` **chưa có** (taxonomy ~300 kỹ năng thuộc PH8); `EN_VI_RECRUITMENT_DICTIONARY` có trong `text_metrics.py` (dịch thuật ngữ tuyển dụng bằng từ điển) | Cần nguồn danh sách thuật ngữ cho PH5. Xem C6 |
| Cache theo hash | Chưa có | Cần xây |
| Gói | `torch 2.15.0+cu132`, `transformers 5.22.2`, `sentencepiece 0.2.3` có trong `.venv` (đo 10/11/2026) | Chưa kiểm `requirements.txt`; **model chưa tải** (không có `~/.cache/huggingface/hub`) |

### 2.2. Lượng JD cần dịch (đo trên 5.077 tin của 01_clean, trước khử trùng PH4)

Gắn `en` bằng `detect_jd_language` trên `description_clean + requirements_clean` (đã bỏ tiêu đề/công ty):

| Nguồn | Tin | `en` |
|---|---|---|
| topcv | 1.561 | 80 |
| topdev | 227 | 60 |
| vietnamworks | 800 | 352 |
| careerviet | 448 | 65 |
| vieclam24h | 182 | 10 |
| itviec | 905 | 604 |
| glints | 271 | 106 |
| jobsgo | 683 | 70 |
| **Tổng** | **5.077** | **1.347 (26,5%)** |

Báo cáo 03 cũ (03/11/2026, 5.177 tin) ghi 1.395 `en` (26,9%); số mới lệch do 01_clean đã đổi từ 5.177 sang 5.077 và do làm sạch khác. Số `en` **sau khử trùng PH4 chưa biết** (phụ thuộc kết quả C3 của PH4), nên tổng thời gian chạy chỉ ước được sau cả PH4 lẫn spike. `KNOWN_ISSUED.md` nêu "khoảng 24,2%" bằng cách đo khác; mình dùng số đo hôm nay.

Kích thước đầu vào cần dịch (chỉ các tin `en`, `description_clean + requirements_clean`, tách theo từ bằng khoảng trắng; **token của envit5 chưa biết**):

| Đại lượng | Giá trị |
|---|---|
| Từ mỗi JD: trung vị / P90 / P99 / max | 314 / 598 / 1.063 / 1.489 |
| Tổng từ cần dịch (1.347 tin) | 471.214 |
| Số dòng (bullet/đoạn) mỗi JD: trung vị / P90 / max | 18 / 38 / 98 |
| Số dòng không rỗng toàn bộ | 26.318 |
| Từ mỗi dòng: trung vị / P90 / P99 / P99,9 / max | 13 / 31 / 112 / 304 / 626 |
| Dòng dài hơn 100 từ | 339 |

Hệ quả (chưa phải kết luận về model): tách theo dòng đủ ngắn cho phần lớn dòng (P90 31 từ), nhưng 339 dòng > 100 từ và vài dòng tới 626 từ cần tách tiếp theo câu. Cả `description` lẫn `requirements` đều không rỗng ở mọi tin `en` (0 rỗng).

### 2.3. Kết quả spike (CHƯA CÓ, điền khi có `reports/preprocessing/_spike/envit5_*.md`)

| Mục | Giá trị |
|---|---|
| Số tham số / dung lượng model | chưa biết |
| Giới hạn token đầu vào (tokenizer/model) | chưa biết (file thiết kế cũng ghi "chưa kiểm") |
| VRAM đỉnh, GPU 4 GB, batch bao nhiêu | chưa biết |
| Tốc độ: GPU, CPU (giây mỗi JD hoặc mỗi dòng) | chưa biết |
| Có cần tiền tố ngôn ngữ trong đầu vào (ví dụ `en: ...`) | chưa kiểm; theo trí nhớ model card có, cần xác minh trong spike |
| Hành vi với số, ký hiệu, tên công nghệ, bullet | chưa biết |

## 3. Cần chốt

- **[CẦN CHỐT] C1. Dịch trường nào.** **[ĐỀ XUẤT]** `description` và `requirements` (hai trường dài mà các bước sau dùng). `job_title`, `benefits_list`, `skills_list`, `company_name` **không dịch** (tên riêng, chức danh kỹ thuật; nếu dịch tiêu đề sẽ phá phân loại nhóm nghề PH6 vốn dùng cả tiêu đề tiếng Anh). `benefits_list` chưa đo có bao nhiêu tin tiếng Anh; nếu bạn muốn dịch, thêm vào.
- **[CẦN CHỐT] C2. Bước sau dùng bản gốc hay bản dịch.** File thiết kế: tính lại `text_norm`, `text_fold` trên bản dịch, cột Việt dùng cho các bước sau. P3 T6b/mục 80: mọi bước sau rút thông tin từ bản gốc. **[ĐỀ XUẤT]** theo file thiết kế (mới hơn, ghi quyết định 10/11): thêm `description_vi_norm`, `description_vi_fold` (và `requirements_*`); trích kỹ năng (PH8) quét **cả** `text_fold` gốc lẫn `*_vi_fold` (tên kỹ năng giữ tiếng Anh nên bản gốc vẫn dùng được); khi `lang=vi`, cột `*_vi` = cột gốc và `translated_by = null`. Phải sửa câu P3 mục 80.
- **[CẦN CHỐT] C3. Chiến lược chạy (phụ thuộc spike).** Ba khả năng: GPU 4 GB nếu vừa; CPU theo lô chạy qua đêm; hoặc phương án khác. Mình **không** chọn trước. Điều kiện để chạy hết: tạm định **dịch theo lô, có tiếp tục từ chỗ dừng** (cache theo hash), nên mất điện hay lỗi OOM không dịch lại từ đầu.
- **[CẦN CHỐT] C4. Cách tách đầu vào.** **[ĐỀ XUẤT]** tách theo dòng (bullet), dòng nào vượt giới hạn token (giá trị từ spike) thì tách theo câu (dấu `.`, `;`, `:` theo sau bởi khoảng trắng), dòng nào còn dài thì tách theo số token tối đa; ghép lại giữ đúng thứ tự và dấu xuống dòng; bullet `- ` giữ nguyên ngoài đoạn gửi model (không để model dịch dấu `-`).
- **[CẦN CHỐT] C5. Tên cột.** **[ĐỀ XUẤT]** giữ tên P3: `description_vi`, `requirements_vi`, `translated_by`; thêm `translation_status` (`translated`/`not_needed`/`failed`), `translation_chunks` (số đoạn), `translation_source` (`model` hoặc `rule`, theo quy ước `<trường>_source` của file thiết kế). Ghép `*_vi_norm`, `*_vi_fold` theo C2.
- **[CẦN CHỐT] C6. Che thuật ngữ (token giữ chỗ).** Cần danh sách không dịch, nhưng `skills.json` chưa có (PH8). **[ĐỀ XUẤT]** PH5 dùng bảng nhỏ `preprocessing/dictionaries/no_translate.json` **chỉ chứa các mục bạn duyệt**, dựng từ tên kỹ năng/công nghệ thấy trong cột `skills_list` của chính 1.347 tin `en` (đếm tần suất, bạn duyệt), cộng mẫu regex cho số/đơn vị/tiền (`\d`, `USD`, `$`, `%`, `15-25`); khi PH8 có `skills.json` thì gộp. Token giữ chỗ phải qua được model nguyên vẹn (kiểm trong spike; dạng token do spike quyết). Sau dịch, mọi token giữ chỗ phải được trả lại; thiếu một token thì đoạn đó coi là lỗi (C7).
- **[CẦN CHỐT] C7. Khi dịch hỏng.** **[ĐỀ XUẤT]** kiểm 3 điều trên mỗi đoạn dịch: (a) mọi token giữ chỗ còn đủ và đúng số lần; (b) mọi dãy số trong đoạn gốc có mặt trong đoạn dịch (tập số bằng nhau); (c) đầu ra không rỗng và không dài/ngắn bất thường so với đầu vào (ngưỡng tỉ lệ chưa biết, lấy từ spike). Một điều không đạt: thử lại một lần (cùng tham số, xác định), vẫn hỏng thì **giữ bản gốc cho đoạn đó**, `translation_status = failed` ở tin, không bỏ tin. Số đoạn hỏng ghi báo cáo.
- **[CẦN CHỐT] C8. Tái lập.** Sinh văn bản xác định (không lấy mẫu ngẫu nhiên: `do_sample=False`; số beam do spike chọn), ghi `seed` và toàn bộ tham số sinh vào manifest. Cùng đầu vào, cùng model, cùng phần cứng thì cùng đầu ra; khác GPU/CPU có thể khác nhẹ (chưa kiểm). **[ĐỀ XUẤT]** cache khóa theo `sha256(model_id + model_revision + tham_số + văn bản đoạn đã che)`; bỏ cache khi đổi bất kỳ thành phần nào.
- **[CẦN CHỐT] C9. Model tải từ đâu và ghim phiên bản.** Cần mạng để tải lần đầu; **[ĐỀ XUẤT]** ghim `revision` (commit hash của Hugging Face) vào manifest, thư mục cache nằm ngoài git (`data/preprocessing/models/` hoặc `~/.cache/huggingface`, bạn chọn). Việc tải cần bạn đồng ý (mạng).
- **[CẦN CHỐT] C10. Nơi đặt code và bước.** **[ĐỀ XUẤT]** module riêng `preprocessing/translation/` (đọc đầu ra PH4, ghi `data/preprocessing/translation/`: `translations_cache.jsonl`, `all.parquet` hoặc jsonl theo nguồn, cùng báo cáo `reports/preprocessing/translation/`), vì bước chạy lâu, cần resume, không nên nằm trong vòng lặp `process_source` của 03; 03 đọc cột `*_vi` từ đây. Cách khác: nằm trong 03 T6b như P3 đã viết. Mình chọn cách đầu, cần bạn đồng ý, và cần cập nhật `STEPS` nếu thêm bước.
- **[CẦN CHỐT] C11. Số tin chấm tay.** 50 JD như file thiết kế. **[ĐỀ XUẤT]** lấy ngẫu nhiên `seed=42` có phân tầng theo nguồn (mỗi nguồn ≥ 1; tỉ lệ theo số tin `en`), bao gồm cả tin có đoạn `failed` nếu có.

## 4. Luật

| Mã | Hành động | Mô tả |
|---|---|---|
| X0 | flag | Chọn tin cần dịch: `lang = en`, sau PH4; tin `vi` đi thẳng (`*_vi` = gốc, `translated_by = null`) |
| X1 | modify | Che thuật ngữ bằng token giữ chỗ (C6) |
| X2 | modify | Tách đoạn theo C4 |
| X3 | modify | Dịch bằng model, ghi `translated_by`, cache theo C8 |
| X4 | modify | Trả lại token giữ chỗ, ghép đoạn, kiểm số và token (C7) |
| X5 | flag | Đoạn hỏng giữ nguyên bản gốc, `translation_status = failed` |
| X6 | modify | Tính `*_vi_norm`, `*_vi_fold` theo C2 (cùng hàm của PH2, không viết bản mới) |

Bước **không bỏ tin** (`rows_out = rows_in`); mã chỉ là gợi ý, thống nhất với mã `T6b` của P3 khi chốt C10.

## 5. Đo và báo cáo

- Manifest/`meta.json` và `extra.translation`: `model_id` = `VietAI/envit5-translation`, `model_revision`, phiên bản `torch`, `transformers`, `sentencepiece`, thiết bị (GPU/CPU, tên GPU), tham số sinh, `seed`, giới hạn token đã dùng, số bản dịch lấy từ cache và số dịch mới, thời gian chạy tổng (giây), thời gian trung bình mỗi đoạn và mỗi JD, VRAM đỉnh nếu GPU.
- Theo nguồn và `_all`: số tin `en`, số tin dịch xong, số đoạn, số đoạn `failed`, số lần thử lại, số token giữ chỗ bị mất.
- 3 ví dụ gốc → dịch mỗi nguồn trong báo cáo? **Không** (JD là dữ liệu, không đưa vào `reports/` được tracked bằng git). Ví dụ chỉ ghi vào `data/preprocessing/translation/samples_for_review.json` (git-ignore).
- Dry-run: chọn tin và đếm đoạn, **không gọi model**, báo ước lượng số đoạn (không ước thời gian khi chưa có số spike).
- Chạy thật cần cờ rõ ràng (ví dụ `--translate`) vì chạy lâu và tải model.

## 6. Ranh giới

- Model duy nhất: `VietAI/envit5-translation`. Không OpenJev, JEV, Qwen, Gemini, không API ngoài, không bất kỳ model nào khác (kể cả fastText của PH3 là việc của PH3).
- Không sửa raw, không sửa `raw_*`, không sửa cột `*_clean`; chỉ thêm cột.
- Không dịch `job_title`, `company_name`, `skills_list` (C1).
- Không đưa model/trọng số vào git. Không động tới R2. Không cài gói mà không hỏi (gói đã cài, chỉ hỏi khi cần gói mới). Không đưa nội dung JD vào `reports/`.
- Không nhúng thêm model embedding (`multilingual-e5-base` thuộc bước 4.2/12, ngoài PH5).

## 7. Tiêu chí xong

- `rows_out = rows_in`; mọi tin `lang = en` có `description_vi` không rỗng (dịch hoặc `failed` giữ gốc); tin `vi` có `*_vi` = gốc.
- Chạy lại với cache: 0 lần gọi model, đầu ra giống hệt.
- Mọi đoạn đã dịch qua kiểm C7 (token đủ, tập số bằng nhau) hoặc được đánh `failed`; tỉ lệ `failed` ghi trong báo cáo (không đặt số mục tiêu khi chưa có số đo).
- Manifest có tên + `revision` model, tham số, thiết bị, thời gian.
- **Kiểm tay 50 JD (C11): kỹ năng và số liệu (lương, năm kinh nghiệm) không bị đổi.** Ngưỡng cụ thể file thiết kế không ghi; **[CẦN CHỐT] C12** bạn muốn "không JD nào lỗi" hay chấp nhận một tỉ lệ nhỏ? Mình chưa đặt số.
- `pytest tests/unit` xanh; test cho che/trả token, tách đoạn, cache, kiểm số chạy **không cần model** (dịch giả chỉ dùng trong test của logic bao ngoài, bằng hàm thay thế tiêm vào; kết quả chất lượng dịch chỉ đo bằng model thật, không dựng số).

## 8. Monitoring thấy gì

- Khối "Dịch": model, phiên bản, thiết bị, số tin/đoạn dịch, `failed`, thời gian chạy, theo nguồn.
- Nếu bước chưa chạy: trạng thái rỗng `NO_DATA` trung thực (nguyên tắc Real Numbers). Không hiển thị mẫu dịch trên giao diện.

## 9. Không làm

Không dịch trường ngoài C1; không chạy model trên tin sẽ bị PH4 loại; không bịa số tốc độ/VRAM; không dùng bản dịch để sửa raw; không đưa bản dịch lên R2 (`pipeline/translation/` do PH9 quyết, dry-run trước).
