# PH0. Nền hạ tầng: R2 `pipeline/`, tên file, gói cài, thử model dịch

> Trạng thái: **đã chốt các điểm cần hỏi (10/11/2026)**; prompt: `docs/prompting/PH0_nen_ha_tang.md`, chờ bạn duyệt. Chưa có code.
> Kế hoạch tổng: các phase PH0–PH9 trong plan "hoàn thiện pre-processing bước 0–9". Quy trình mỗi phase: bạn sửa đặc tả → mình viết prompt → bạn duyệt → mình code → bạn review.
> Các chỗ đánh dấu **[ĐỀ XUẤT]** là mình đoán, không phải quyết định của bạn. Các chỗ **[CẦN CHỐT]** mình không biết.

## 1. Mục tiêu

Chốt những thứ mọi phase sau đều dựa vào, để không phải sửa lại: tên đường dẫn trên R2, các gói phải cài, và liệu model dịch `VietAI/envit5-translation` có chạy được trên máy này.

## 2. Hiện trạng đã đo (10/11/2026)

- R2 có `raw` 12.826, `url_ledger` 64, `staging` 35, `curated` 2 object. `pipeline/` chưa có object.
- `canonicalize_lakehouse_key` (`collection/common/r2_storage.py`) đã chấp nhận mọi key bắt đầu bằng `pipeline/`. Nó **từ chối** key có phần tên bắt đầu bằng dấu chấm (kể cả `.keep`), nên `pipeline/.keep` phải upload tay trong dashboard.
- Tầng `staging/` bắt buộc có tên nguồn ở cấp 2, nên `staging/all.parquet` bị từ chối. `preprocessing/common/r2_export.py` đang tách bảng gộp theo `source_platform` để đẩy 32 file `staging/<nguồn>/preprocessing/<bước>.*`.
- Máy: GPU Quadro T1000 4 GB, RAM 30 GB. Đã có `bs4`, `lxml`, `pandas`, `pyarrow`, `pydantic`. Chưa có torch, transformers, sentencepiece, datasketch, rapidfuzz, pyahocorasick, underthesea, fasttext, ydata-profiling.

## 3. Cần chốt

### 3.1. Tên thư mục con trong `pipeline/` **[ĐÃ CHỐT 10/11/2026: theo đề xuất, vì Monitoring cần đọc theo từng bước]**

**[ĐỀ XUẤT]** `pipeline/<bước>/<tên file>` với `<bước>` trùng tên bước trong `data/preprocessing/` (`01_clean`, `02_integration`, `03_transformation`, `04_normalization`, `05_encoding`) và thêm `pipeline/rejected/`, `pipeline/translation/` cho bản ghi bị loại và bản dịch. Ví dụ: `pipeline/03_transformation/all.parquet`.
Lý do đề xuất: trùng tên local nên dễ so sánh. Bạn có thể đặt tên khác.

### 3.2. Tên file trong `staging/` và `curated/` **[ĐÃ CHỐT 10/11/2026: phương án (a), giữ như hiện tại]**

Hai lựa chọn:
- (a) Giữ `staging/<nguồn>/...` (code hiện tại, không đổi gì); `pipeline/` chứa bảng gộp 8 nguồn.
- (b) Cho `staging/all.parquet`: phải sửa `canonicalize_lakehouse_key` (bỏ `staging` khỏi `SOURCE_LAYERS`), `r2_export.py`, `push_preprocessing_to_r2.py` và các test; đụng ledger `staging/<nguồn>/` của collection.

**[ĐỀ XUẤT]** (a). Lý do: ít rủi ro nhất, vì bảng gộp đã có chỗ ở trong `pipeline/`. Bạn quyết.

### 3.3. Gói cần cài **[ĐÃ ĐỒNG Ý 10/11/2026; cài khi code PH0 được duyệt]**

| Gói | Phase dùng | Việc |
|---|---|---|
| ydata-profiling | PH1 | báo cáo profiling |
| fasttext (hoặc `fasttext-wheel`) + file `lid.176.bin` (~126 MB) | PH3 | nhận diện ngôn ngữ |
| datasketch | PH4 | MinHash + LSH |
| torch, transformers, sentencepiece | PH5 | model dịch |
| rapidfuzz | PH6 | khớp tên công ty |
| pyahocorasick | PH8 | trích kỹ năng |
| underthesea | PH8 | tách từ tiếng Việt |

Mỗi gói ghi version cố định vào `requirements.txt` sau khi cài chạy được. Mình không cài gì khi bạn chưa đồng ý. Mình chưa kiểm các gói này có bản wheel cho Python 3.12 trên máy này; sẽ báo khi cài.

## 4. Thử model dịch (spike, bỏ đi sau khi đo)

Mục đích: biết thật `envit5-translation` có dùng được không, trước khi viết đặc tả PH5. **Không đoán trước kết quả.**

Cần cài torch/transformers/sentencepiece và tải model từ Hugging Face (cần mạng; tests đang chặn mạng nên chạy tay ngoài pytest). Đo:

| Đo | Cách | Ghi vào |
|---|---|---|
| Giới hạn độ dài đầu vào (token) | đọc cấu hình tokenizer/model, thử một đoạn dài | báo cáo spike |
| Có vừa GPU 4 GB không | chạy 10 JD, ghi VRAM đỉnh; nếu lỗi bộ nhớ thì thử CPU | báo cáo spike |
| Tốc độ | thời gian dịch 20 JD thật (lấy từ các JD có `lang` = en), GPU và CPU | báo cáo spike |
| Ước lượng tổng thời gian | số JD tiếng Anh sau khử trùng × thời gian mỗi JD | báo cáo spike |
| Chất lượng sơ bộ | bạn đọc 5 JD đã dịch, kiểm kỹ năng/số liệu không bị đổi | bạn nhận xét |

Kết quả quyết định PH5: dịch trên GPU, CPU theo lô, hay phương án khác. Spike ghi vào `reports/preprocessing/_spike/envit5_2026-11-xx.md` (không đưa model vào git).

## 5. Việc code (nhỏ)

- Nếu chọn (a) ở 3.2: không đổi code. Thêm test khẳng định `canonicalize_lakehouse_key("pipeline/03_transformation/all.parquet")` hợp lệ và `pipeline/.keep` bị từ chối.
- Nếu chọn (b): xem 3.2.
- Cập nhật `preprocessing/common/r2_export.py` để có thêm hàm `pipeline_key(step, name)` theo tên chốt ở 3.1 (chưa ghi gì lên R2).

## 6. Tiêu chí xong

- Bạn đã chốt 3.1, 3.2 và danh sách gói ở 3.3.
- Có báo cáo spike với số đo thật cho 5 dòng ở mục 4.
- Test ở mục 5 xanh; `pytest tests/unit` vẫn xanh.
- Bạn upload `pipeline/.keep` (việc của bạn) và mình liệt kê lại để xác nhận prefix xuất hiện.

## 7. Không làm

Không ghi gì lên R2; không cài gói khi chưa được đồng ý; không sửa dữ liệu raw.
