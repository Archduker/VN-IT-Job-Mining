# Quy trình test

## Chạy test

| Lệnh | Chạy gì | Khi nào dùng |
|---|---|---|
| `make test-fast` | Chỉ `unit/` (khoảng 1 giây) | Trong lúc sửa code |
| `make test` | Mọi test trừ `live` | Trước khi báo xong một việc |
| `make test-contract` | Test tiêu chuẩn crawler C1–C14 | Khi sửa crawler |
| `make check` | `make test`, báo cáo chất lượng code, build frontend | Trước khi commit (target `quality` chưa viết nên hiện dừng ở bước này) |
| `make test-live` | Cào thật, gọi R2 thật | Chỉ khi người dùng đồng ý, với lượng rất nhỏ |

Chạy một file hoặc một test: `pytest tests/unit/test_url_ledger_dedup.py::test_name`.

## Đặt test ở đâu

| Thư mục | Nội dung | Luật |
|---|---|---|
| `unit/` | Hàm nhỏ: làm sạch URL, hash, parse | Không đọc `data/`, không mạng, mỗi test < 1 giây |
| `integration/` | API monitoring, script trong `scripts/` | Dữ liệu tạo trong `tmp_path`; R2 thì mock |
| `contract/` | Mỗi crawler 1 file `test_<nguồn>_contract.py` | Dùng mẫu trong `fixtures/<nguồn>/`, không mạng |
| `data/` | Kiểm tra trên `data/` hoặc `reports/` thật | Tự skip khi thiếu dữ liệu |
| `fixtures/<nguồn>/` | HTML/JSON mẫu đã cắt gọn | 3 mẫu: tin thường, tin VIP, lương thỏa thuận |

Marker theo thư mục được gắn tự động (`tests/conftest.py`). Test ở thư mục khác mà cần dữ liệu thật thì gắn `@pytest.mark.needs_data("đường/dẫn")`.

## Luật chung

- **Không ra mạng.** `conftest.py` chặn mọi kết nối ngoài localhost. Test cần mạng thật thì gắn `@pytest.mark.live`.
- **Không ghi vào `data/` thật, không ghi lên R2.** Dùng `tmp_path`, và `monkeypatch` cho `settings.DATA_DIR`.
- **Một test kiểm tra một hành vi.** Tên test nói rõ hành vi đó, ví dụ `test_repost_does_not_write_new_file`.
- **Sửa lỗi thì có test tái hiện lỗi đó trước.** Test phải fail với code cũ và pass với code mới.
- **Test không được qua khi không kiểm tra gì.** Thiếu dữ liệu thì skip có lý do, không `if os.path.exists(...)` rồi im lặng qua.

## Quy trình làm một việc

1. **Đặc tả:** việc gì, vì sao, đầu vào, đầu ra, cái gì không làm.
2. **Prompt:** người dùng duyệt đặc tả.
3. **Mã giả:** người dùng review từng bước.
4. **Kế hoạch test:** bảng "trường hợp → kết quả mong đợi", chốt cùng người dùng.
5. **Làm:** viết test theo bảng (test fail), viết code (test pass), chạy `make test`, báo kết quả thật.
