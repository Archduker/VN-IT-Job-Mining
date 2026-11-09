# F02. Test không chạy hoặc lỗi collect

Issue: PRE-24, PRE-27. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
- `tests/test_golden_field_preservation.py` lỗi collect.
- Test P3/P4 của Duy không được `make test` chạy.

## Nguyên nhân
- Dòng 25 file test: `from preprocessing.normalization.target_schema_formatter import CANONICAL_ROOT_KEYS, TargetSchemaFormatter, is_unknown`. Thư mục `preprocessing/normalization/` không có module đó (chỉ có `cross_deduplicator`, `location_normalizer`, `log_transformer`, `run`, `skill_normalizer`, `text_cleaner`, ...). File test cũng nằm ở gốc `tests/`, không thuộc `unit/`, `integration/`, `contract/`, `data/` nên không được gắn marker theo thư mục.
- `pyproject.toml` có `testpaths = ["tests"]`, còn test Duy ở `preprocessing/transformation/tests/test_feature_engineering.py` nằm ngoài `tests/`.

## Giải pháp (chọn khi làm, cần hỏi nếu mơ hồ)
- File golden: hỏi Phát xem module `target_schema_formatter` nên được khôi phục hay test nên bỏ. Không tự xóa test của người khác.
- Test Duy: chuyển (git mv) vào `tests/unit/` hoặc thêm đường dẫn vào `testpaths`. Ưu tiên chuyển vào `tests/unit/` cho khớp `tests/README.md`.
- Sửa lỗi `tests/conftest.py:42` khi chạy chung (`relative_to` văn bản hỏng nếu file nằm ngoài `tests/`).

## Xong khi
`make test` thu thập được cả hai nhóm test; không còn lỗi collect.

## Kiểm chứng
`pytest --collect-only -q | tail`, rồi `make test`.

## Rủi ro
Chạy lần đầu test Duy có thể lộ lỗi thật (PRE-23); ghi issue, không sửa trong cùng commit.
