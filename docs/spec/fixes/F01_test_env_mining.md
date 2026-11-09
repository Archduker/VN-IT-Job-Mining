# F01. Môi trường test mining thiếu thư viện

Issue: MERGE-3, MERGE-4, MINE-2, MINE-3. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
3 file test mining lỗi collect (`test_mining_association.py`, `test_mining_pipeline.py`, `test_mining_sanity.py`), 2 lỗi `test_mining_salary_model.py`, và `test_outlier_ratio_follows_quantile` fail.

## Nguyên nhân
`mlxtend`, `shap`, `hdbscan` đã khai trong `requirements.txt` (78bebfc) nhưng venv chưa cài. Test outlier fail vì thiếu `hdbscan` nên rơi về fallback sklearn (ghi chú ngay trong `requirements.txt`).

## Giải pháp
1. `pip install -r requirements.txt` trong `.venv` (cần người dùng đồng ý vì cài gói).
2. Chạy lại `pytest tests/unit/test_mining_*.py`.
3. Nếu `test_outlier_ratio_follows_quantile` vẫn fail khi đã có `hdbscan`: mới sửa code (khi đó là lỗi thật, mở issue riêng).

## Xong khi
5 test trên pass hoặc có lý do ghi vào issue. `make test` không còn lỗi collect do thư viện.

## Kiểm chứng
`pytest tests/unit -q` và đối chiếu với mốc 440 pass / 6 skip trước đó.

## Rủi ro
`hdbscan` cần build C trên một số máy; nếu không cài được thì test cần `pytest.importorskip` thay vì fail (chọn khi gặp, hỏi lại).
