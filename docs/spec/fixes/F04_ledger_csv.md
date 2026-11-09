# F04. `ledger.csv` bị gitignore

Issue: PRE-25. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
`preprocessing/encoding/cohort.py` (dòng 135) và `finalize_cohort.py` đọc `ASSETS / "ledger.csv"` nhưng `.gitignore` dòng 35 có `*.csv`, nên clone sạch không có file.

## Nguyên nhân
Quy tắc `*.csv` chặn mọi csv, kể cả tài sản hợp đồng.

## Giải pháp
Thêm ngoại lệ trong `.gitignore`: `!preprocessing/encoding/assets/ledger.csv` (và các csv hợp đồng của Phát nếu có, kiểm bằng `git ls-files` so với file đang có). Nếu file không còn trong working tree thì hỏi Phát, không tự tạo.

## Xong khi
`git check-ignore -v preprocessing/encoding/assets/ledger.csv` không in gì và file đã được thêm vào git.

## Rủi ro
`cohort.py` còn kiểm hash cố định cho các csv; thêm file khác hash sẽ làm chạy fail, nên chỉ thêm đúng bản Phát đã dùng.
