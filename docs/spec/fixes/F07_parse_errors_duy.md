# F07. Lỗi parse của Duy

Issue: PRE-23. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
Các ca tái hiện được: "tối thiểu 10 triệu", "2 tỷ", "Không yêu cầu", "Điện Biên Phủ" (nhầm là tỉnh), Python/PHP Developer và UI/UX bị phân nhóm sai.

## Nguyên nhân
Chưa xác định từng ca bằng đọc code; nhóm này cần tái hiện bằng test trước. (Không suy đoán nguyên nhân.)

## Giải pháp
Mỗi ca một test nhỏ trong `tests/unit/` (dữ liệu `tmp_path`/chuỗi), xem fail, rồi sửa parser/từ điển đúng chỗ. Embedded và UI/UX: chưa chốt, **không sửa** cho tới khi người dùng chốt.

## Xong khi
Mỗi ca có test pass; không làm regress test hiện có của Duy.

## Kiểm chứng
`pytest preprocessing/transformation/tests tests/unit -q` (sau F02).

## Rủi ro
Sửa từ điển nhóm nghề làm đổi phân phối nhóm; ghi số trước/sau.
