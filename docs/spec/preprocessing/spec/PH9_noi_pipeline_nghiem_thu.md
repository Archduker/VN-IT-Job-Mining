# PH9. Nối pipeline và nghiệm thu: driver, báo cáo bước, Monitoring, chạy thử/chạy thật, ghi `pipeline/` lên R2

> **Nháp đặc tả, chờ bạn sửa** (10/11/2026). Chưa có code. Prompt: `docs/prompting/PH9_noi_pipeline_nghiem_thu.md` (chưa duyệt).
> **[ĐỀ XUẤT]** = mình đoán. **[CẦN CHỐT]** = mình không biết, cần bạn quyết.
> Phase cuối: chạy sau PH0–PH8. Vì PH3–PH8 chưa làm khi viết nháp này, nhiều chỗ ghi "đọc trạng thái thực tế lúc làm". Số đo ngày 10/11/2026, chỉ đọc.

## 1. Mục tiêu

1. Một driver chạy được toàn chuỗi từ Collection output (`raw`) đến đầu ra của `processing/` bước 7–9, theo thứ tự đúng, mỗi bước ghi báo cáo.
2. Monitoring thấy được mọi bước (kể cả bước `processing/`), khối model dịch, phễu dữ liệu.
3. Chạy `--dry-run` toàn chuỗi, rồi chạy thật (ghi local), báo số vào/ra từng bước.
4. Ghi `issue_log.md` và `KNOWN_ISSUED.md`.
5. Đẩy `pipeline/` lên R2: chạy thử trước, **chỉ ghi khi bạn đồng ý rõ**.

Không có số mẫu mục tiêu (đã chốt 10/11/2026): chỉ báo số tin vào và số còn lại sau mỗi bước.

## 2. Hiện trạng so với thiết kế (đo 10/11/2026)

| Mục | Hiện trạng đo | Lệch / việc phải làm |
|---|---|---|
| Driver | `scripts/run_preprocessing.py`: `MODULES` có 5 bước (`01_clean … 05_encoding`) lấy từ `preprocessing.common.STEPS`; mỗi bước `run(sources, dry_run)`; bước chưa có trong `MODULES` thì in "chưa làm" và dừng; `--step all` chạy đủ 5 | Không có bước dịch, khử trùng MinHash, `processing/` 07–09. `STEPS` thay đổi sau PH3–PH7 thì các nơi dùng `STEPS` đổi theo (xem dưới) |
| Bước `processing/` | `processing/*/` chỉ có `__init__.py` (tới trước PH8) | Cần `run(sources, dry_run)` cùng chữ ký (PH8) và một chỗ gọi từ driver: **[CẦN CHỐT] D1** |
| Báo cáo bước | `reports/preprocessing/<bước>/<nguồn>.json` + `_all.json` (schema P0). Trên máy: `03_transformation` và `04_normalization` `applied` 03/11/2026, 5.177 dòng; `05_encoding` `dry_run` 07/11/2026, 0 dòng | Báo cáo cũ. `01_clean` jsonl 09/11 có 5.077 tin (khác 5.177): **chưa biết** do dữ liệu hay luật đổi |
| Dữ liệu trung gian trên máy | `data/preprocessing/01_clean/*.jsonl` (8 file, 09/11), `02_integration/` **trống**, không có `03/04/05` | Dry-run chuỗi: bước sau đọc đầu ra bước trước, nên dry-run toàn chuỗi **không có đầu vào thật cho bước sau nếu bước trước chỉ dry-run** — xem 4.2, **[CẦN CHỐT] D3** |
| Monitoring (backend) | `monitoring/backend/app/services/preprocessing_step_service.py`: `STEPS` cố định 5 giá trị (chặn giá trị lạ trước khi ghép đường dẫn); đọc `reports/preprocessing/<bước>/` | Không nhận bước `processing/`, không có khối model dịch/phễu nếu PH5 chưa nối |
| Monitoring (frontend) | `PreprocessingPage` có khối riêng theo bước; `05_encoding` được đối xử như "gold", bước khác "silver" | Cần dải bước dài hơn và khối `processing/`; kiểm 390px |
| R2 `pipeline/` | `preprocessing/common/r2_export.py` có `PIPELINE_STEPS = (*STEPS, "rejected", "translation")` và `pipeline_key(step, name)`; **không có chỗ nào gọi `pipeline_key`**; `plan_objects()` và `scripts/push_preprocessing_to_r2.py` chỉ đẩy `staging/<nguồn>/preprocessing/<bước>`, `curated/preprocessing/*` | Push hiện **chưa đẩy `pipeline/`**; phải thêm vào `plan_objects`, mở rộng `PIPELINE_STEPS` cho bước 07–09 |
| `canonicalize_lakehouse_key` | chấp nhận mọi key bắt đầu `pipeline/`; từ chối tên có dấu chấm đầu (`pipeline/.keep` do bạn upload tay) (PH0) | Test đã có từ PH0 (theo prompt PH0); xác nhận lúc làm |
| Cơ chế push | `scripts/push_preprocessing_to_r2.py`: không cờ = chạy thử (đọc R2, liệt kê mới/lệch/khớp); `--push` = ghi; chỉ đẩy object chưa có hoặc lệch | Giữ nguyên nguyên tắc dry-run first |
| Bố cục R2 đã chốt (PH0) | bảng gộp 8 nguồn: `pipeline/<bước>/<tên file>`; `staging/<nguồn>/preprocessing/<bước>.*` giữ nguyên (phương án a) | `<bước>` cho `processing/`: **[CẦN CHỐT] P1 của PH8** |
| Việc mở liên quan | `KNOWN_ISSUED.md` mục 3: PRE-10 (dịch, làm lại bằng envit5), PRE-11, PRE-12 (nhãn nghiệm thu bộ lọc IT), PRE-13 … PRE-17; `docs/issue_log.md` mã cuối đo được: L-33 | Mỗi lỗi được sửa trong PH0–PH8 phải có mục `L-<số kế tiếp>` và xóa khỏi `KNOWN_ISSUED.md`; xem lại danh sách thật lúc làm, mình không đoán mục nào đã hết |
| Phụ thuộc cài | `pyahocorasick`, `underthesea` có trong `.venv` nhưng không trong `requirements*.txt` (PH8); các gói khác của PH0 tùy trạng thái | Ghim version trong `requirements.txt` trước khi nghiệm thu (tái lập) |

## 3. Việc cần làm

### 3.1. Driver

**[CẦN CHỐT] D1** (hình dạng driver):
- (a) **[ĐỀ XUẤT]** một driver `scripts/run_pipeline.py` mới: danh sách bước theo thứ tự (đọc từ một nơi duy nhất, ví dụ `pipeline/steps.py` hoặc mở rộng `preprocessing.common`), gồm các bước preprocessing hiện có sau PH0–PH7 + `07_sections`, `08_skills`, `09_tokens`; `run_preprocessing.py` giữ nguyên làm lối vào cũ cho 5 bước.
- (b) mở rộng `run_preprocessing.py` + `MODULES`.
Lý do (a): `STEPS` đang được import ở nhiều nơi (`r2_export`, `preprocessing_step_service`, driver); thêm bước vào `STEPS` thay đổi hành vi `--step all` và test cũ. Nếu chọn (b), `STEPS` phải đổi và mọi nơi dùng nó phải rà.

**[CẦN CHỐT] D2** (thứ tự với `05_encoding`): code Encoding hiện đọc đầu ra 04 và là bước cuối của `all`. Bước 10b/10c/10d và việc chuyển Encoding sang `processing/` **ngoài đợt này**. **[ĐỀ XUẤT]** driver mới: `01…04` (+ các bước PH3–PH7) → `07, 08, 09`; `05_encoding` chạy riêng như hiện tại và **không** đọc `job_skills` (chưa đổi). Mình chưa kiểm thứ tự thực tế sau PH3–PH7 chèn thêm bước vào `STEPS`; đọc lại lúc làm.

Cờ tối thiểu: `--from <bước>`, `--to <bước>`, `--source`, `--dry-run`, `--stage preprocessing|processing|all`. Mỗi bước in `input → output (mode)` như driver hiện tại. Mọi bước phải `run(sources, dry_run)` và trả `StepReport`.

### 3.2. Báo cáo bước và luật bảo toàn

- Mọi bước dùng `StepReport` hiện có; luật `input = output + dropped` kiểm cho từng bước, từng nguồn và `_all`; vi phạm thì dừng chuỗi, in bước và nguồn.
- Mỗi bước `extra` ghi version luật/từ điển (hash ngắn), `code_version` (git), `mode`, `generated_at`.
- Báo cáo `processing/` ở `reports/processing/<bước>/` hay chung `reports/preprocessing/`: **[CẦN CHỐT] D4.** **[ĐỀ XUẤT]** `reports/processing/<bước>/` (không lẫn `preprocessing`; service Monitoring phải đọc cả hai thư mục theo whitelist bước).
- Funnel (bảng phễu, thiết kế 4.3): một báo cáo tổng `reports/pipeline/funnel.json` ghép `_all.json` của từng bước theo thứ tự: bước, số vào, số ra, số bỏ, lý do chính. Chỉ ghép số đã có trong báo cáo, không tính lại từ parquet.

### 3.3. Monitoring

Theo `monitoring/CLAUDE.md` (số thật, trạng thái rỗng, token UI, 390px):
- Backend: `preprocessing_step_service` nhận danh sách bước từ cùng nguồn sự thật với driver (D1); bước lạ vẫn 404; thiếu file `available=false` kèm lệnh tạo. Bước `processing/` đọc từ thư mục ở D4. API mới (chỉ đọc) trả `funnel` nếu D4/funnel được chốt.
- Frontend: dải bước (`StepStrip`) hiển thị toàn bộ bước; khối "Phễu dữ liệu" (số vào → ra theo bước); khối model: bước dịch (PH5) hiện tên và phiên bản model, số JD đã dịch, số trúng cache; các bước khác "không dùng model (luật if-else)"; khối riêng cho 07 (bullet theo section × nguồn), 08 (JD 0 kỹ năng theo nguồn, top kỹ năng, **F1/độ đúng nếu báo cáo có, nếu không "chưa có nhãn"**), 09 (số token, stopword miền).
- Không gõ tay số; không `Math.random`; báo cáo cũ hơn bước trước thì "Cần chạy lại" (đã có ở P6).
- Test backend (`tmp_path`, bước lạ 404, thiếu file `available=false`) và `npm run build`; Playwright 1440px và 390px, không tràn ngang, không lỗi console.
- Lưu ý: trang `/preprocessing` cũ và `GET /preprocessing/metrics` còn được trang khác đọc (P6); không xóa khi chưa rà.

## 4. Quy trình chạy và nghiệm thu

### 4.1. Chuẩn bị

1. `git status` sạch phần dữ liệu; ghi `git rev-parse HEAD` vào báo cáo nghiệm thu.
2. Dữ liệu đầu vào: `data/<nguồn>/raw/` cần có. `scripts/sync_cloud_lakehouse.py --download` (đọc R2, ghi local): **[CẦN CHỐT] D5** có tải lại không, hay dùng `data/` đang có (raw 09/11)? Mình không biết raw trên máy so với R2 hiện tại chênh bao nhiêu.
3. Ghim version gói vào `requirements.txt`; `pytest tests/unit` và `tests/integration/test_preprocessing_steps_api.py` xanh; `pytest tests/contract` không bị đụng.
4. Bộ gold: nếu bạn đã gán đủ số JD (K6 của PH8), có file nhãn; chưa có thì F1/độ đúng ghi "chưa có nhãn" và nghiệm thu PH8 chưa đóng.

### 4.2. Chạy thử toàn chuỗi (`--dry-run`)

`--dry-run` hiện nghĩa: đọc và ghi báo cáo, không ghi dữ liệu. Vấn đề: bước sau cần đầu ra thật của bước trước; chuỗi dry-run liên tiếp có thể không có đầu vào cho bước kế (đo: `02_integration/` đang trống). **[CẦN CHỐT] D3.** Hai cách:
- (a) **[ĐỀ XUẤT]** dry-run theo thứ tự từng bước **trên đầu vào của bước đó nếu có trên máy**; bước nào thiếu đầu vào thì báo `INPUT_MISSING` kèm bước cần chạy thật trước, không điền 0. Dry-run cả chuỗi chỉ đầy đủ khi đã có dữ liệu local.
- (b) chạy thật các bước ghi **chỉ local** (không R2) ngay, bỏ dry-run toàn chuỗi.
Yêu cầu chung: dry-run không ghi parquet, không ghi `rejected/`, không đụng R2; có ghi `reports/` (theo cách hiện tại).

Trình tự: 1 nguồn (`glints`) → 8 nguồn, gửi bảng số trước khi chạy thật.

### 4.3. Chạy thật (ghi local)

Chạy thật ghi `data/preprocessing/*`, `data/processing/*`, `reports/*` trên máy; không R2. Mỗi bước in bảng `vào / ra / bị bỏ / bị sửa`. Chạy lại lần hai: so hash parquet (idempotent). Nếu số bước này khác bản chạy cũ (03/11: 5.177 dòng), ghi lý do hoặc "chưa rõ".

Bảng nghiệm thu (điền bằng số thật, **không có cột "mục tiêu"** theo quyết định đã chốt):

| Bước | Vào | Ra | Bỏ | Luật bỏ nhiều nhất | Ghi chú |
|---|---|---|---|---|---|
| 01 Clean (+ các bước PH3, PH4) | | | | | |
| 02 Integration | | | | | `rejected` |
| 03 Transformation (+ dịch PH5) | | | | | số JD dịch, model, phiên bản |
| 04 Normalization (+ PH6, PH7) | | | | | |
| 07 sections | | | 0 | | độ đúng gold ≥ 90% (nếu có nhãn) |
| 08 skills | | | 0 | | F1 gold ≥ 0,85 (nếu có nhãn) |
| 09 tokens | | | 0 | | |

Cổng nghiệm thu cứng (từ file thiết kế, không phải "số mẫu mục tiêu"): bảo toàn `in = out + dropped`; PH2 (0% HTML, 0% NFD); PH8 (section ≥ 90%, F1 ≥ 0,85) khi có nhãn; gold của các phase khác theo spec của chúng. Không đạt: báo, không hạ ngưỡng.

### 4.4. Ghi nhận lỗi và việc mở

- Mỗi lỗi sửa được từ PH0 đến PH8: mục `L-<số kế tiếp>` trong `docs/issue_log.md` (Lỗi → Nguyên nhân → Cách xử lý → Còn lại → Kiểm chứng) và xóa khỏi `KNOWN_ISSUED.md`; bẫy dễ lặp lại thêm một dòng vào `CLAUDE.md` thư mục liên quan.
- Mục còn mở thêm vào `KNOWN_ISSUED.md` (ví dụ: ba taxonomy chưa gộp, `STEPS` song song, `pipeline_key` chưa được `plan_objects` gọi nếu chưa nối). **Không** tự xóa mục PRE nào mà phase chưa thực sự giải quyết; rà từng mục lúc làm.
- Cập nhật `preprocessing/CLAUDE.md`, `processing/CLAUDE.md` (hết "chưa có logic", bảng thư mục, driver mới), `scripts/CLAUDE.md` (script mới ghi hay chỉ đọc), `monitoring/CLAUDE.md` nếu đổi API.

### 4.5. Đẩy `pipeline/` lên R2 (chỉ sau khi bạn đồng ý)

Thứ tự bắt buộc, không đảo:
1. Bạn đã upload `pipeline/.keep` (PH0) hay chưa: kiểm bằng liệt kê (chỉ đọc).
2. Code: `plan_objects()` thêm các object `pipeline/<bước>/<tên file>` cho bảng gộp mỗi bước (+ `rejected`, `translation` theo PH0), dùng `pipeline_key`; `PIPELINE_STEPS` thêm 07–09; test cho tên key hợp lệ/không hợp lệ.
3. **Chạy thử:** `python scripts/push_preprocessing_to_r2.py` (không `--push`). Chỉ đọc R2, in từng key: mới / lệch / khớp, kích thước, số dòng, và `generated_at` mỗi báo cáo. Gửi bảng cho bạn. Chạy thử này đọc R2 (`get_r2_client()`), cần `.env`; không in giá trị cấu hình.
4. **Dừng chờ bạn đồng ý** bằng lời rõ ràng cho đúng danh sách key đã liệt kê. Đồng ý chung chung cho "R2" không đủ; AI không tự thêm `--push`.
5. Có đồng ý: `--push`; sau đó chạy lại bản thử, kỳ vọng mọi key = "khớp". Không xóa object nào; không động `raw/`, `url_ledger/`.
- Dữ liệu `staging/<nguồn>/preprocessing/*` và `curated/preprocessing/*` hiện có cũng nằm trong push này: **[CẦN CHỐT] D6** đẩy lại cả hai nhóm hay chỉ `pipeline/` đợt này? **[ĐỀ XUẤT]** chỉ `pipeline/` (đúng phạm vi plan); nhóm cũ báo "lệch" nếu lệch, không tự đẩy.
- Hướng dẫn xóa/dọn prefix cũ (`quality/`, `integration/`, `transformation/`, `silver/`, `gold/`): ngoài phạm vi PH9 (L-33 đã ghi trạng thái; không động).

## 5. Ranh giới

- Raw bất biến; không sửa `collection/`; không chạy `airflow scheduler`; không chạy cào.
- Không in giá trị `.env`; so cấu hình bằng hash nếu cần.
- Ghi R2 chỉ ở bước 4.5.5, sau bản thử và sau đồng ý.
- Không cài gói trong PH9 (chỉ ghim version vào `requirements.txt` các gói đã được bạn cho cài ở PH0).
- Không đổi định nghĩa cột đã có; không xóa file dữ liệu trên máy.
- Monitoring: chỉ đọc báo cáo, không tính lại số.

## 6. Tiêu chí xong

- Driver chạy từng bước và cả chuỗi; bước chưa làm báo rõ; bảo toàn đúng ở mọi bước.
- Dry-run 8 nguồn và chạy thật 8 nguồn ghi đúng báo cáo; chạy lại hai lần cùng hash.
- Bảng nghiệm thu 4.3 điền số thật; mọi chỗ chưa đo ghi "chưa đo" kèm lý do.
- Monitoring hiển thị đủ bước, phễu, khối model; xóa một file báo cáo thì hiện "chưa có", không trắng trang; `npm run build` qua; 390px sạch.
- `issue_log.md` và `KNOWN_ISSUED.md` cập nhật theo 4.4.
- Bản thử `pipeline/` gửi bạn; chỉ khi bạn đồng ý mới `--push`; sau push mọi key "khớp".

## 7. Tổng hợp [CẦN CHỐT]

| Mã | Câu hỏi | [ĐỀ XUẤT] |
|---|---|---|
| D1 | Driver mới `scripts/run_pipeline.py` hay mở rộng `run_preprocessing.py` | driver mới, một danh sách bước duy nhất |
| D2 | Vị trí `05_encoding` so với 07–09 | `05_encoding` chạy riêng, chưa đọc `job_skills` |
| D3 | Dry-run chuỗi khi bước trước chưa có đầu ra | `INPUT_MISSING` kèm hướng dẫn, không điền 0 |
| D4 | Báo cáo `processing/` ở đâu | `reports/processing/<bước>/` |
| D5 | Tải lại raw từ R2 trước khi chạy hay dùng `data/` hiện có | dùng `data/` hiện có, ghi ngày raw vào báo cáo |
| D6 | Push lại `staging/`, `curated/` cùng lúc hay chỉ `pipeline/` | chỉ `pipeline/` |
| (PH8) | P1, P2 (tên bước và bảng đầu vào của `processing/`) | xem PH8 mục 10 |

## Yêu cầu bổ sung của người dùng (10/11/2026): mẫu trước/sau trong báo cáo

Mỗi báo cáo bước (`reports/preprocessing/<bước>/` và `reports/processing/<bước>/`) có khối `samples`: một mẫu cố định (seed 42, vài tin mỗi nguồn, ưu tiên tin bị bước đó thay đổi) gồm `job_id`, nguồn, giá trị TRƯỚC và SAU của các trường bước đó đổi. Không chứa toàn văn JD ngoài các trường bị đổi. Monitoring và slide hiển thị mẫu này cạnh số vào/ra. Dữ liệu thật, không mock.
