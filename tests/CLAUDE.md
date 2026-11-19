# tests/CLAUDE.md

Quy trình test, chỗ đặt test và luật chung nằm ở `tests/README.md`; đọc file đó trước. Ở đây chỉ ghi phần dễ sai.

- `tests/conftest.py` thêm thư mục gốc, `monitoring/backend` và `scripts/` vào `sys.path`, nên test import được `app.*` và tên script như module (`import push_raw_to_r2`).
- Mạng ngoài localhost bị chặn ở mức socket. Test lỗi kết nối thì kiểm xem mình có quên mock R2 không, đừng gỡ chốt chặn. Test cần mạng thật thì gắn `@pytest.mark.live` và chạy `make test-live` khi người dùng đồng ý.
- `--strict-markers` đang bật: marker mới phải khai báo trong `pyproject.toml`.
- Từng có test ghi vào `data/` thật rồi bị đồng bộ lên R2 (4 tin ITviec giả, `docs/issue_log.md` L-12). Mọi đường dẫn ghi phải nằm trong `tmp_path`.
- `monkeypatch.setattr(module, "X_FILE", ...)` không đổi được tham số mặc định đã gắn lúc định nghĩa hàm (`def write(path=X_FILE)`). Gọi hàm phải truyền đường dẫn rõ; sau khi chạy test xem `git status` có file `reports/` nào bị sửa không (19/11: test bước 04 từng ghi đè `anomalies.json`).

## Contract test cho crawler

- Mỗi nguồn một file `contract/test_<nguồn>_contract.py`. Phần chung (C1, C4, C8, C10, C11, C13) gọi từ `contract/standards.py`; file của nguồn chỉ lo cách dựng envelope từ mẫu và cách chạy `crawl_details` offline. Mẫu đầy đủ: `test_topdev_contract.py` (nguồn API), `test_topcv_contract.py` (nguồn HTML, có C14).
- Chạy offline: monkeypatch `polite_sleep`, `UrlLedger.pull_from_r2`, `UrlLedger.sync_to_r2`; thay `_r2_store` bằng `standards.FakeR2Store()`.
- C11 đọc `RAW_PATHS` từ Monitoring. Trường biết trước là thiếu ở một nguồn thì truyền `allow_missing={"F7": "lý do"}`, không hạ ngưỡng 90%.
- Mẫu trong `fixtures/<nguồn>/` là trang thật đã cắt script/style/svg. Sau khi cắt phải ra đúng `content_hash` như trang gốc; ghi ngày lấy mẫu trong docstring của file test.
- `contract/test_discovery_error_c14.py` gom test C14 (DiscoveryError) của 6 nguồn không có file contract riêng (L-41). Contract đầy đủ C1–C13 cho 6 nguồn đó vẫn còn thiếu (SCRAPE-14). CareerViet nghỉ giữa tin qua `HttpClient` nên `check_random_pause` (tìm lời gọi `polite_sleep` hoặc `uniform`) sẽ không nhận ra.

## Test version (C12)

`integration/test_snapshot_versioning.py` thay `build_raw_envelope` bằng bản giả để chỉ kiểm logic version trong `crawl_details` (TopCV và JobsGO). Nguồn mới muốn thêm vào thì thêm vào `SOURCES` và `make_crawler` trong file đó.
