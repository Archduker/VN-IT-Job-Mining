# EDA của P5

Bắt đầu từ [handoff P5](../docs/preprocessing/encoding/05_p5_handoff_2026-11-08.md); [manifest canonical](../data/preprocessing/05_encoding/artifact_manifest.json) xác định run dữ liệu.

| Notebook / HTML | Vai trò |
|---|---|
| [eda_p5_final_cohort.ipynb](eda_p5_final_cohort.ipynb) / [HTML](eda_p5_final_cohort.html) | Bản bàn giao hiện hành, 5.104 included jobs |
| [eda_p5_encoding.ipynb](eda_p5_encoding.ipynb) / [HTML](eda_p5_encoding.html) | Bằng chứng lịch sử trên snapshot 5.177 jobs; giữ nguyên |

Mở notebook cuối từ repo root hoặc `notebooks/`, chọn kernel Python dự án **3.14.4**, Restart Kernel → Run All. Cell đầu tìm repo root qua `pyproject.toml` và `preprocessing/encoding/execute.py`, thêm root vào sys.path rồi đọc manifest để chọn run. `covered` được tạo trước cell so sánh. Nếu mở ngoài cây repo, notebook báo lỗi rõ; không tự dò một dataset khác.

Để chạy bằng kernel mới và xuất HTML đồng bộ, từ repo root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m preprocessing.encoding.build_cohort_notebook \
  --output-dir /tmp/p5-final-eda-check
```

Thư mục output phải chưa có cặp file EDA này; builder bảo vệ file đã có. Kernel mặc định khởi động tại `notebooks/` và dùng chính Python gọi builder. Có thể thêm `--kernel-cwd .` để kiểm từ repo root. HTML được sinh từ notebook vừa execute; không xuất HTML từ notebook còn output cũ.

Builder cần `nbformat`, `nbclient`, `nbconvert`; kernel cần `ipykernel`, `matplotlib` và các dependencies P5. Danh sách công cụ notebook ở [requirements-notebook.txt](../preprocessing/encoding/requirements-notebook.txt). Không cài cả `requirements-review.txt` vào venv artifact: môi trường review lịch sử pin Pandas khác phiên bản artifact.

Trong máy bàn giao, công cụ notebook đã có riêng tại `/tmp/p5_review_tools`. Lệnh kiểm chứng thực tế dùng `PYTHONPATH=/tmp/p5_review_tools` trước lệnh trên. Builder ưu tiên site-packages của Python dự án trong kernel để giữ đúng Pandas/NumPy; không inject repo root qua môi trường kernel, nhờ đó kiểm được bootstrap của notebook. Thư mục `/tmp` chỉ là cách cung cấp công cụ ở máy này, không phải runtime dependency của Encoding hoặc input dữ liệu.

Sau khi kiểm notebook/HTML tạm, việc cập nhật cặp canonical phải đồng bộ hai SHA trong `manifest.EDA` và bản manifest evidence, bảo toàn bản trước nếu còn được manifest cũ tham chiếu. Refactor hiện tại không tái fit hoặc thay artifact dữ liệu.
