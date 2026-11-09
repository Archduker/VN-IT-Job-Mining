# Frozen P5 cohort run

Bắt đầu từ `README.md` và handoff05 để phân biệt runtime với các helper review lịch sử.
Tests P5 ở `tests/unit/test_encoding_*.py`; 4 approval tests đã chuyển vào đó.
Notebook cuối phải tự tìm repo root và thêm sys.path trước import package, chạy từ
`notebooks/` bằng kernel mới; không giả định cwd=repo root. Builder nhận --output-dir
để kiểm vào thư mục tạm, không ghi đè cặp notebook/HTML đã có.

Đọc `docs/spec/preprocessing/encoding/06_p5_execution_contract.md` và execution report07.
Runner đầy đủ là `python -m preprocessing.encoding.execute` với input manifest,
frozen vocabulary, stopwords, cohort ledger, decision record, history root và explicit
output/evidence roots. Runtime assets ở `preprocessing/encoding/assets/`, không đọc Downloads.

`run.py:run` chỉ delegate khi đủ explicit config; thiếu config fail trước IO.
`run_encoding.py` delegate CLI mới; --apply/--source legacy bị chặn trước writes.
Chỉ execute.py là implementation full-bundle. Không sửa P3/P4 hoặc exporter chung.

Arrow Table.cast có thể lỗi khi nested-list/struct chứa null-only child và số location
lớn hơn số job. Loader chỉ dựng lại cột cần null-type union theo values và so lossless;
không ép null→[] hoặc stringify nested fields để vượt lỗi.

N_P4=5177=5104include+62exclude+11quarantine; output chỉ5104include, không claim
bảo toàn5177output sau lọc. Bản5177 và source cũ có checksum ở history bundle.
85reviewed không biến5092retained_unreviewed thành verified IT; không sửa job_family.
PASS_TECHNICAL_REVIEW không tự là nghiệm thu: Python3.12UNVERIFIED và whole-repo
test limitations phải được báo đúng, không tự nâng PASS/P5 complete.
