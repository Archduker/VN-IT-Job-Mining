# F05. Đưa code về thang cấp bậc 5 cấp

Issue: PRE-22 (phần code). Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
Đã chốt 5 cấp của Duy (09/11/2026), tài liệu đã sửa. Code còn hai thang: Duy 5 nhãn (`seniority_level` 0–4) và Phát/Phúc 6 nhãn (`seniority_ord` 0–5).

## Nguyên nhân
Spec cũ ghi 6 cấp; Duy làm 5; Phát (encoding) và Phúc (mining) làm theo spec cũ và viết adapter ở `mining/data_io.py` để dịch 0–4 sang 0–5 (không phục hồi được phần tách Thực tập / Mới tốt nghiệp).

## Giải pháp
1. `preprocessing/encoding/run.py:50-58` và `execution_features.py:40`: `SENIORITY_ORDER` còn 5 nhãn, cột `seniority_ord` 0–4 (hoặc dùng thẳng `seniority_level`; hỏi Phát để không đổi tên cột đang có trong hợp đồng).
2. `preprocessing/normalization/run.py:103` (`SENIOR_LEVELS`) và `text_cleaner.py:24`: bỏ nhãn "Trưởng nhóm/Quản lý", dùng "Lead/Manager".
3. `mining/config.py:81` còn 5 nhãn; `mining/data_io.py` bỏ nhánh dịch 0–4 sang 0–5; `mining/synthetic.py` sinh thang 5.
4. Sửa `docs/tasks/06_phuc_data_mining_algorithms.md` và các dòng nhắc thang 6 trong docs/tasks.
5. Chạy lại `tests/unit/test_mining_*` và test encoding.

## Xong khi
`grep -rn "Trưởng nhóm/Quản lý" preprocessing mining` chỉ còn trong chuỗi tương thích có chú thích; mọi cột cấp bậc cùng thang 0–4.

## Kiểm chứng
Test chuyển đổi nhãn → số cho 5 nhãn và -1; pipeline `--dry-run` trên `glints`.

## Rủi ro
Đổi tên/giá trị cột `seniority_ord` làm vỡ artifact encoding đã commit trong `reports/preprocessing/05_encoding` (số cũ theo 6 nhãn); phải chạy lại hoặc ghi chú rõ. Phụ thuộc F02 (test của Duy chạy được).
