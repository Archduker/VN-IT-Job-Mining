# Prompt PH0: nền hạ tầng (R2 `pipeline/`, gói cài, thử model dịch)

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/PH0_nen_ha_tang.md` (đã chốt 10/11/2026).
- `collection/common/r2_storage.py`: `canonicalize_lakehouse_key`, `R2_LAYER_PREFIX`, `SOURCE_LAYERS`.
- `preprocessing/common/r2_export.py`: `silver_key`, bố cục hiện tại.
- `preprocessing/common/__init__.py`: `STEPS`, `SOURCES`.

Hiện tại: R2 có 5 tiền tố hợp lệ; `pipeline/` chưa có object (người dùng tự upload `pipeline/.keep`). `canonicalize_lakehouse_key` đã chấp nhận `pipeline/...` nhưng chưa có hàm dựng key `pipeline/`. Chưa cài torch, transformers, sentencepiece, datasketch, rapidfuzz, pyahocorasick, underthesea, fasttext, ydata-profiling. GPU 4 GB.

## 2. Việc cần làm

1. `preprocessing/common/r2_export.py`: thêm `pipeline_key(step, name)` trả `to_r2_key(f"pipeline/{step}/{name}")`; `step` thuộc `STEPS` hoặc `rejected`, `translation`, nếu không thì `ValueError`. Không đổi `silver_key` và `staging/<nguồn>/...` (giữ phương án a).
2. Test (`tests/unit/test_pipeline_keys.py`): `pipeline_key("03_transformation","all.parquet")` đúng; `canonicalize_lakehouse_key` chấp nhận key đó, từ chối `pipeline/.keep`; `silver_key` không đổi so với trước.
3. Cài gói trong `.venv` rồi ghi version đã chạy được vào `requirements.txt` (nhóm "preprocessing/processing"): ydata-profiling, fasttext (nếu không có wheel cho Python 3.12 thì `fasttext-wheel`; nếu cả hai lỗi, **dừng và báo**), datasketch, torch (bản CPU hoặc CUDA phù hợp, báo bản đã chọn), transformers, sentencepiece, rapidfuzz, pyahocorasick, underthesea. Sau cài chạy `python -c "import <gói>"` từng gói, in version. Kiểm `ydata-profiling` với pandas 3.1.1 bằng một DataFrame nhỏ; không chạy được thì ghi vào báo cáo (người dùng đã chấp nhận thay bằng pandas ở PH1).
4. Spike `envit5` (script tạm `scripts/spike_envit5.py`, không đưa model vào git, không chạy trong pytest): đo 5 mục ở mục 4 của spec, trên 20 JD tiếng Anh thật lấy từ `data/preprocessing/02_integration/all.parquet`. Ghi `reports/preprocessing/_spike/envit5_<ngày>.md`.

## 3. Pseudo code spike

```text
tải tokenizer + model "VietAI/envit5-translation" (cần mạng; ghi dung lượng đã tải)
in model_max_length / max_position, kiểm tay một đoạn dài hơn giới hạn: có cắt, lỗi hay cảnh báo
chọn 20 JD có lang = en (bước này chưa có cột lang: dùng heuristic tạm tỉ lệ ký tự ASCII/stopword tiếng Anh, ghi rõ là tạm)
for device in [cuda nếu có, cpu]:
    dịch JD theo đoạn (cắt theo bullet/câu sao cho đoạn < giới hạn - lề), batch 1 rồi batch 4
    ghi: thời gian/JD, VRAM đỉnh (torch.cuda.max_memory_allocated) hoặc RAM, có OOM không
tổng thời gian ước tính = số JD tiếng Anh (đọc từ dữ liệu, không bịa) * thời gian/JD trung vị
in 5 JD gốc và bản dịch cạnh nhau cho người dùng đọc
```

## 4. Ràng buộc

- **Không cài gì ngoài danh sách; không ghi lên R2; không sửa raw.** Tải model cần mạng: nếu mạng bị chặn thì dừng và báo.
- Mọi lệnh cài in rõ gói và version; nếu phải hạ/nâng pandas, numpy hay gói đang dùng thì **dừng và hỏi** trước.
- Cấm mock trong spike: dùng JD thật.
- Không đoán kết quả spike; số nào chưa đo được thì ghi "chưa đo" kèm lý do.

## 5. Ví dụ (test kiểm)

```text
pipeline_key("03_transformation", "all.parquet") -> "pipeline/03_transformation/all.parquet"
pipeline_key("rejected", "02.jsonl")             -> "pipeline/rejected/02.jsonl"
pipeline_key("99_x", "a")                        -> ValueError
canonicalize_lakehouse_key("pipeline/.keep")     -> ValueError
silver_key("01_clean","topcv")                   -> "staging/topcv/preprocessing/01_clean.jsonl"
```

## 6. Cách review

| Kiểm | Lệnh | Đạt |
|---|---|---|
| Test mới và cũ | `pytest tests/unit -q` | xanh |
| Gói cài đủ | `python -c "import torch, transformers, datasketch, rapidfuzz, ahocorasick, underthesea, fasttext"` | không lỗi (gói lỗi phải được báo) |
| Báo cáo spike | đọc `reports/preprocessing/_spike/envit5_*.md` | đủ 5 số đo hoặc "chưa đo" có lý do |
| R2 | liệt kê prefix sau khi bạn upload `.keep` | thấy `pipeline/` |
| Git | `git diff --stat` | chỉ `r2_export.py`, `requirements.txt`, test, script spike, báo cáo |
