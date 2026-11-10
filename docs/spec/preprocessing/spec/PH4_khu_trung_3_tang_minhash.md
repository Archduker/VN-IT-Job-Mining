# PH4. Khử trùng lặp 3 tầng với MinHash (bước 4 của file thiết kế)

> **Nháp đặc tả, chờ bạn sửa** (10/11/2026). Chưa có code. Prompt: `docs/prompting/PH4_khu_trung_3_tang_minhash.md` (chưa duyệt).
> **[ĐỀ XUẤT]** = mình đoán. **[CẦN CHỐT]** = mình không biết, cần bạn quyết.
> Số liệu đo ngày 10/11/2026, chỉ đọc, trên `data/preprocessing/01_clean/*.jsonl` (5.077 tin: topcv 1.561, topdev 227, vietnamworks 800, careerviet 448, vieclam24h 182, itviec 905, glints 271, jobsgo 683), văn bản `job_title + raw_requirements_text + raw_description_text` qua `deduplication.text_norm.clean_text` + `fold`. MinHash đo bằng `datasketch 2.0.0` (đã cài trong `.venv`), `seed=42`, chỉ để đo, không phải code của phase. Chưa đo trên `data/preprocessing/02_integration/` (đang trống) và chưa có cột `text_fold` của PH2 trên đầu ra thật.

## 1. Mục tiêu

Đầu ra không còn tin trùng (tiêu chí **Uniqueness**) theo 3 tầng của file thiết kế: (1) `nguồn + id`, (2) `sha1(text_fold)`, (3) MinHash (shingle 5 từ, 128 permutation, ngưỡng 0.85) kết hợp khóa `company_key + title_key`. Giữ bản đầy đủ nhất; lưu `duplicate_of` và `sources[]`. Mọi bản bị loại có dòng truy vết chỉ về bản giữ. Đích nghiệm thu theo file thiết kế: **precision ≥ 95% trên 50 cặp gần ngưỡng** do bạn chấm.

Vị trí: sau lọc phạm vi (PH3), trước dịch (PH5), theo mục 3.2 file thiết kế.

## 2. Hiện trạng và so với thiết kế (đã đo)

### 2.1. Code hiện có (`preprocessing/deduplication/`)

| Thiết kế | Đang có | Lệch |
|---|---|---|
| Tầng 1: `nguồn + id` | Clean C1 (chuỗi version `_v<N>`), C2 (batch cũ trùng file từng tin), C3 | Đã làm ở bước 01. Đo: **0** cặp `(source, job_id)` trùng trên 5.077 tin của 01_clean |
| Tầng 2: `sha1(text_fold)` | D2 (cùng sàn) và D4 (liên sàn) dùng **SHA-256 trên canonical JSON** của nhiều trường (tiêu đề, công ty, mô tả, yêu cầu, ...) sau `clean_text` + `fold` | Khác định nghĩa: không phải hash văn bản JD đã fold. Chưa dùng cột `text_fold` (PH2) |
| Tầng 3: MinHash, shingle 5 từ, 128 perm, 0.85 | D5 là **TF-IDF char_wb 3..5 + cosine ≥ 0.85**, chỉ so **khác sàn**, chỉ trong cùng block `Slug(Company)_LocationCode_TitleGroup`, cổng `same_company` khi slug ngắn (< 4 ký tự) | Khác thuật toán. Tin gần trùng **cùng sàn** chỉ bị bắt khi hash khớp tuyệt đối (D2) |
| Khóa `company_key + title_key` | `blocking.blocking_key` = slug công ty + mã tỉnh + nhóm chức danh | Có sẵn dạng block, không có `title_key` riêng; không dùng `company_key` của PH6 (chưa có) |
| Giữ bản đầy đủ nhất | `pick_winner` = nhiều trường có giá trị nhất, rồi bản cào mới nhất, rồi `job_id`; liên sàn: `pick_cross_winner` + `PLATFORM_AUTHORITY`; `fuse()` tạo Golden Record | Đạt ý. Giữ logic, đổi nguồn cặp trùng |
| `duplicate_of`, `sources[]` | `metadata.dedup.{master_id, merged_from, kept_job_id}` trong envelope; `duplicates_audit.csv` | Tên khác thiết kế; chưa là cột phẳng |
| Dòng truy vết mỗi bản bị loại | Có (audit, kể cả nối gián tiếp `linked_via`) | Giữ |
| Vị trí trong chuỗi | `01b_deduplication` **không nằm trong `STEPS`** (`preprocessing/common/__init__.py`: `01_clean, 02_integration, ...`) và không có trong `scripts/run_preprocessing.py`; `02_integration/run.py` đọc thẳng `01_clean/` | **Đầu ra của dedup hiện không được bước sau dùng.** Xem **[CẦN CHỐT] C1** |
| Gói | `datasketch` đã cài (2.0.0) | Còn `requirements.txt` chưa kiểm ở phase này |
| Test | `tests/unit/test_deduplication_step.py`, `test_cross_deduplicator.py` | Khẳng định hành vi TF-IDF, sẽ phải đổi |

Báo cáo hiện có (`reports/preprocessing/01b_deduplication/_all.json`, tạo 07/11/2026, `code_version c1555c0`, 5.077 → 4.897): D2 54, D4 9, D5 117 (tổng 180 tin bị loại); 189 cặp được audit, 131 cặp ≥ 0.85, 113 cụm; 58 dòng audit trong dải duyệt.

### 2.2. Đo ba tầng trên 5.077 tin của 01_clean (10/11/2026)

| Phép đo | Kết quả |
|---|---|
| Tầng 1: `(source, job_id)` trùng | 0 |
| Tầng 2: `sha1(fold(text))` trùng | 84 nhóm, 103 tin loại được; 14 nhóm khác sàn, 70 nhóm chỉ trong một sàn |
| Tầng 3: cặp Jaccard shingle-5 ≥ 0.85 (tính chính xác trên ứng viên LSH ngưỡng 0.7) | **396 cặp**: 294 cùng sàn, 102 khác sàn; 261 cụm, 319 tin loại được (đã gồm cả 103 tin của tầng 2) |
| Cặp 0.70 ≤ J < 0.85 | 138 cặp (55 cùng sàn, 83 khác sàn) |
| Cặp 0.80 ≤ J < 0.90 (dải "gần ngưỡng" dùng chấm tay) | 115 cặp (57 cùng sàn, 58 khác sàn) |
| Cặp J ≥ 0.85 mà **cùng slug công ty** (`fold(company_name)` bỏ ký tự không phải chữ/số) | 288 / 396. Còn **108 cặp J ≥ 0.85 khác slug công ty** |
| Cặp J ≥ 0.85 theo tổ hợp sàn (nhiều nhất) | jobsgo-jobsgo 133, itviec-itviec 68, jobsgo-topcv 35, topcv-topcv 26, careerviet-careerviet 22, glints-glints 17, itviec-topdev 12, careerviet-topcv 11 |
| Độ dài văn bản (từ, sau fold) | min 39, P5 114, trung vị 322, P95 789, max 2.300; 1 tin < 50 từ, 0 tin < 5 từ (không có shingle rỗng) |

Đọc số: MinHash 0.85 loại được **nhiều hơn rõ rệt** so với 01b hiện tại (319 so với 180), chủ yếu vì bắt được 294 cặp **cùng sàn** gần trùng mà hash tuyệt đối không bắt. Mình **chưa biết** bao nhiêu cặp trong đó là tin khác thật (cùng công ty đăng cùng JD mẫu cho nhiều vị trí hoặc nhiều địa điểm, ví dụ 133 cặp jobsgo-jobsgo) nên **không** kết luận số 319 là đúng; chính 50 cặp bạn chấm mới trả lời. Đây là lý do khóa `company_key + title_key` có mặt trong thiết kế. Giới hạn của phép đo: LSH chỉ cho ứng viên, nên recall của LSH ở 0.85 chưa được đo riêng; số cặp chính xác chỉ tính trên ứng viên.

## 3. Cần chốt (ảnh hưởng thiết kế)

- **[CẦN CHỐT] C1. Dedup nằm đâu trong chuỗi.** Hiện `01b` đứng ngoài `STEPS` và 02 không đọc đầu ra của nó. **[ĐỀ XUẤT]** giữ module `preprocessing/deduplication/`, đưa `01b_deduplication` vào `STEPS` giữa 01 và 02, `02_integration` đọc `01b_deduplication/<nguồn>.jsonl` thay `01_clean/`. Cách này đổi số tin vào của 02 và mọi báo cáo sau, nên cần bạn đồng ý. Cách khác: đặt dedup sau 03 để dùng `text_fold` thật của PH2 (phải sửa lại hợp đồng P0 mục 7). Lý do chọn cách đầu: bước 01b đã chạy trên envelope và test sẵn, `text_fold` có thể tính nội bộ bằng `text_norm.fold`.
- **[CẦN CHỐT] C2. `text_fold` lấy từ đâu.** PH2 tạo `description_fold`, `requirements_fold` ở 03. Nếu dedup ở trước 03 (C1 đề xuất), dedup tự tính `fold(clean(title + requirements + description))` bằng `preprocessing.common.text_clean` + `text_norm.fold` (cùng hàm với PH2, không viết bản thứ bảy). **[ĐỀ XUẤT]** như vậy; mã hash dùng `sha1` đúng như file thiết kế (không dùng SHA-256 canonical JSON cũ cho tầng 2).
- **[CẦN CHỐT] C3. Cổng `company_key + title_key` là AND hay chỉ cảnh báo.** Đo: 108/396 cặp J ≥ 0.85 khác slug công ty. **[ĐỀ XUẤT]** loại chỉ khi J ≥ 0.85 **và** cùng `company_slug` (hàm `blocking.company_slug`, chưa có `company_key` của PH6); `title_key` = `fold(job_title)` đã bỏ ký tự không phải chữ/số, dùng **chỉ để ghi cờ** `title_differs` (không chặn), vì cùng JD mẫu đăng cho nhiều chức danh là trường hợp cần bạn duyệt. Cặp J ≥ 0.85 khác công ty: không loại, ghi vào audit.
- **[CẦN CHỐT] C4. Cùng sàn có được loại bằng MinHash không.** Đo: 294/396 cặp là cùng sàn. Thiết kế không phân biệt cùng/khác sàn. Code hiện tại chỉ loại cùng sàn khi hash khớp tuyệt đối. **[ĐỀ XUẤT]** loại cả cùng sàn theo luật C3, vì cùng một tin repost là nguồn đếm trùng kỹ năng; nhưng cặp cùng sàn **khác `title_key` hoặc khác tỉnh** chỉ vào audit (không loại) cho tới khi bạn chấm xong 50 cặp.
- **[CẦN CHỐT] C5. Số cặp chấm tay và dải chọn.** Thiết kế: 50 cặp "gần ngưỡng". **[ĐỀ XUẤT]** lấy ngẫu nhiên `seed=42`: 25 cặp từ dải 0.85 ≤ J < 0.90 (bị loại) và 25 cặp từ 0.80 ≤ J < 0.85 (không bị loại, để đo recall bị mất); dải 0.80-0.90 hiện có 115 cặp, đủ mẫu. Precision ≥ 95% chỉ tính trên nhóm "bị loại" nên thực chất 25 cặp nếu chia đôi; **[CẦN CHỐT]** bạn muốn đủ 50 cặp bị loại (đúng chữ file thiết kế) hay chia đôi.
- **[CẦN CHỐT] C6. Tham số.** Shingle 5 từ trên `text_fold` tách theo khoảng trắng; 128 perm; ngưỡng 0.85; `seed` của MinHash cố định để chạy lại ra cùng kết quả. **[ĐỀ XUẤT]** giữ đúng giá trị file thiết kế, hằng số nằm trong `preprocessing/dictionaries/dedup_policy.json` (version vào báo cáo) thay vì hardcode; không đổi ngưỡng cho tới khi có kết quả chấm.
- **[CẦN CHỐT] C7. Đoạn mở đầu JD giống nhau.** File thiết kế (B5) nêu 300 ký tự đầu giống hệt ở TopDev 739, JobsGO 479, Vieclam24h 213 tin (số của đợt đo trước, mình chưa đo lại trên 5.077 tin). Boilerplate này làm tăng Jaccard giữa các tin khác nhau của cùng công ty. **[ĐỀ XUẤT]** chưa cắt boilerplate ở PH4 (cắt là xóa nội dung, thuộc PH tách section); xem kết quả chấm trước, nếu precision < 95% thì cân nhắc.
- **[CẦN CHỐT] C8. Tên cột.** **[ĐỀ XUẤT]** bản giữ có `sources` (list `"<nguồn>:<id>"` của mọi thành viên, kể cả bản giữ) và `duplicate_count`; bản bị loại vào `data/preprocessing/rejected/01b_deduplication/<nguồn>.jsonl` với `duplicate_of` (`"<nguồn>:<id>"` bản giữ), `drop_rule`, `jaccard`; không nhét thêm cột vào envelope ngoài `metadata.dedup` (đã có).
- **[CẦN CHỐT] C9. Trùng khác ngôn ngữ.** Cùng một tin đăng bản tiếng Anh ở sàn này và tiếng Việt ở sàn kia sẽ **không** bị MinHash bắt (không chung shingle). PH4 chạy trước dịch (PH5). **[ĐỀ XUẤT]** chấp nhận và ghi vào báo cáo (không đo được); không dịch trước chỉ để khử trùng.

## 4. Luật (mã luật dùng tiền tố D để khỏi đổi Monitoring)

| Mã | Hành động | Mô tả | Ghi chú |
|---|---|---|---|
| D0 | drop | Tầng 1: trùng `(source, job_id)` | Dự kiến 0 (đo 10/11); giữ làm lưới an toàn nếu 01 đổi |
| D1 | flag | Kiểm toán chuỗi version CDC (giữ như hiện tại) | số 1.987 hiện tại |
| D2 | drop | Tầng 2 cùng sàn: `sha1(text_fold)` trùng | thay hash SHA-256 canonical JSON |
| D4 | drop | Tầng 2 liên sàn: `sha1(text_fold)` trùng | giữ mã |
| D5 | drop | Tầng 3: Jaccard shingle-5 ≥ 0.85 **và** cùng `company_slug` (C3, C4) | **đổi thuật toán**, giữ mã; thay chữ `cosine` bằng `jaccard` trong báo cáo |
| D7 | flag | Cặp J ≥ 0.85 không loại (khác công ty, hoặc cùng sàn khác `title_key`/tỉnh theo C4) và cặp 0.70 ≤ J < 0.85 | vào audit để bạn duyệt; không đổi dữ liệu |
| D6 | flag | Hợp nhất Golden Record (`fuse`) | giữ |

Quy tắc chung: gộp cụm bằng union-find như `inter_source.clusters` (A~B, B~C thì cùng cụm), mọi bản bị loại có `linked_via` nếu nối gián tiếp. Bản giữ: `pick_winner` (cùng sàn) hoặc `pick_cross_winner` (liên sàn), giữ nguyên. LSH chỉ sinh ứng viên; **mọi cặp ứng viên đều phải tính Jaccard chính xác trên tập shingle** trước khi quyết định (không tin ước lượng MinHash).

## 5. Đo và báo cáo

- `StepReport` bước `01b_deduplication`: luật D0, D2, D4, D5 (drop, kèm số theo nguồn và ví dụ ≤ 3 không chứa nội dung JD), D6, D7; `checks`: `input = output + dropped` (luật bảo toàn đã có).
- `extra`: `{"dedup": {"num_perm":128, "shingle_words":5, "threshold":0.85, "seed":..., "lib_version":"datasketch x.y.z"}, "tier_counts": {...}, "pairs_by_band": {"[0.85,1]":..., "[0.80,0.90)":..., "[0.70,0.85)":...}, "same_source_pairs":..., "cross_source_pairs":..., "company_gate_blocked_pairs":...}`.
- Báo cáo so sánh trước/sau trên cùng 5.077 tin: số tin loại theo luật cũ (D2 54 + D4 9 + D5 117 = 180, báo cáo 07/11) với số mới, kèm số tin "cũ loại, mới giữ" và "cũ giữ, mới loại" (cần để bạn biết đổi thuật toán làm gì). Số này **phải đo lúc code**, mình chưa có.
- `data/preprocessing/01b_deduplication/duplicates_audit.csv` giữ; thêm cột `jaccard`, `same_company`, `title_differs`, `same_source`. File chấm tay `data/preprocessing/gold/dedup_pairs_sample.json` (git-ignore, cùng chỗ với gold của PH1) để công cụ `.html` chấm đọc.
- Dry-run vẫn tính và ghi báo cáo (vào `_partial/` nếu chạy lẻ, như hiện tại), không ghi jsonl/parquet.

## 6. Ranh giới

- Không sửa raw, không sửa `01_clean/`. Không đụng R2, không chạy scheduler.
- Không dùng model (MinHash là thuật toán xác định). Không chọn ngưỡng theo cảm tính: ngưỡng đổi chỉ sau khi có kết quả chấm của bạn.
- Không gộp 6 bản `fold` rời nhau (việc dọn, không thuộc PH4).
- Không cắt boilerplate, không dịch (xem C7, C9).
- Không tạo cột `company_key` (thuộc PH6); dùng `company_slug` hiện có.

## 7. Tiêu chí xong

- `rows_in = rows_out + dropped` ở 8 nguồn; mỗi bản bị loại có dòng truy vết chỉ về bản giữ.
- Chạy lại hai lần cùng đầu vào, cùng `seed`: danh sách bản giữ giống hệt (so hash danh sách `job_id_global`).
- Tầng 2 = hash `sha1(text_fold)`; tầng 3 = Jaccard chính xác ≥ 0.85 trên shingle 5 từ; ví dụ 2 JD khác nhau 1 câu ở 400 từ bị gộp, khác 30% thì không.
- **Precision ≥ 95% trên 50 cặp gần ngưỡng** do bạn chấm (C5). Chưa có số đo; không tự chấm thay bạn.
- `pytest tests/unit` xanh; test cũ khẳng định hành vi TF-IDF/cosine được sửa và ghi lý do.
- Số tin vào/ra và so sánh cũ-mới ghi trong báo cáo (không đặt số mục tiêu).

## 8. Monitoring thấy gì

- Phễu: vào → D0 → D2 → D4 → D5 → ra; theo nguồn.
- Bảng cặp theo dải Jaccard; số cặp bị cổng công ty chặn; 3 ví dụ mỗi luật (không có nội dung JD).
- Nếu đổi tên `cosine` thành `jaccard`, kiểm trang `/preprocessing` có đọc khóa `cosine_threshold` không (chưa kiểm).

## 9. Không làm

Không đổi thuật toán PH6 (chuẩn hóa công ty bằng rapidfuzz); không ghi `pipeline/` lên R2; không gộp trùng khác ngôn ngữ; không xóa file `rejected/` của bước khác.

## 10. Quyết định đã chốt và kết quả (10/11/2026)

| Mã | Quyết định | Thực hiện |
|---|---|---|
| C1 | `01b_deduplication` vào `STEPS` giữa 01 và 02; 02 đọc đầu ra 01b | `preprocessing/common/__init__.py`; `integration/run.py` `IN_DIR` = `01b_deduplication` (bỏ tự tải 01_clean từ R2 vào thư mục này); `scripts/run_preprocessing.py` (`--step deduplication`); Monitoring `preprocessing_step_service.py`; `r2_export.SILVER_STEPS` vẫn 4 bước cũ (01b chưa đẩy R2) |
| C2 | `text_fold` tự tính trong dedup | `deduplication/minhash.fold_text`, `sha1_fold` |
| C3 | Cổng AND: J >= 0.85 **và** cùng `company_slug` (không rỗng); `title_key` chỉ ghi cờ `title_differs`. Tầng 2 (sha1) cũng đòi cùng `company_slug` | `run.py`, khóa `fkey` |
| C4 | Loại cả **cùng sàn lẫn khác sàn** (không còn ngoại lệ khác tỉnh/title_key) | luật D5 |
| C5 | 50 cặp = 25 bị loại (0.85 <= J < 0.90) + 25 không bị loại (0.80 <= J < 0.85); script + CSV, **tôi không chấm** | `scripts/build_dedup_pairs_sample.py` -> `data/preprocessing/review/dedup_pairs_sample.csv` (cột `nhan_tay`: `trung`/`khac`; không ghi đè khi đã có nhãn). Precision chỉ tính trên nhóm `bi_loai` |
| C6 | Tham số trong `preprocessing/dictionaries/dedup_policy.json` | version, num_perm 128, shingle 5, ngưỡng 0.85, seed 42, dải duyệt |
| C7, C8, C9 | Mặc định: không cắt boilerplate; bản giữ có `metadata.dedup.sources`, `duplicate_count`; bản bị loại vào `data/preprocessing/rejected/01b_deduplication/<nguồn>.jsonl` (`duplicate_of`, `drop_rule`, `jaccard`, `linked_via`, không chứa JD); trùng khác ngôn ngữ không đo (ghi trong `extra.cross_language_dupes`) | |

Luật: D0 (nguồn+id), D2/D4 (sha1 text_fold cùng/khác sàn), D5 (Jaccard chính xác sau LSH), D7 (flag cặp không loại), D6 giữ; `extra.dedup`, `tier_counts`, `pairs_by_band`, `same_source_pairs`, `cross_source_pairs`, `company_gate_blocked_pairs`. TF-IDF cosine đã bỏ khỏi `inter_source.py`.

Đo thật (đọc `01_clean`, ghi vào thư mục tạm), 5.077 -> **4.826** tin, bảo toàn dòng đúng: D0 0, D2 72, D4 11, D5 168 (tổng 251 bị loại; báo cáo TF-IDF cũ 180). D5: 119 cùng sàn, 49 khác sàn (D4 11 khác sàn, D2 72 cùng sàn). Cặp J >= 0.85: 277, trong đó 206 qua cổng (`same_source_pairs` 143, `cross_source_pairs` 63: chỉ cạnh MinHash còn sống sau D2/D4), 71 cặp bị cổng công ty chặn, 153 cặp bị loại có `title_differs`, D7 193 cặp. Chạy 2 lần: file giữ và file rejected giống hệt byte. **Chưa đo:** precision >= 95% (chờ bạn chấm 50 cặp); so danh sách tin "cũ loại / mới giữ" (không còn output 01b cũ trên máy, chỉ có số tổng).
