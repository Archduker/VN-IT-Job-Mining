# EDA của P5

Bắt đầu từ [handoff P5](../docs/preprocessing/encoding/05_p5_handoff_2026-11-08.md); [manifest canonical](../data/preprocessing/05_encoding/artifact_manifest.json) xác định run dữ liệu.

| Notebook / HTML | Vai trò |
|---|---|
| [eda_p5_final_cohort.ipynb](eda_p5_final_cohort.ipynb) / [HTML](eda_p5_final_cohort.html) | Bản bàn giao hiện hành, 5.104 included jobs |


Mở notebook cuối từ repo root hoặc `notebooks/`, chọn kernel Python dự án **3.14.4**, Restart Kernel → Run All. Cell đầu tìm repo root qua `pyproject.toml` và `preprocessing/encoding/execute.py`, thêm root vào sys.path rồi đọc manifest để chọn run. `covered` được tạo trước cell so sánh. Nếu mở ngoài cây repo, notebook báo lỗi rõ; không tự dò một dataset khác.

Để chạy bằng kernel mới và xuất HTML đồng bộ, từ repo root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m preprocessing.encoding.build_cohort_notebook \
  --output-dir /tmp/p5-final-eda-check
```

Thư mục output phải chưa có cặp file EDA này; builder bảo vệ file đã có. Kernel mặc định khởi động tại `notebooks/` và dùng chính Python gọi builder. Có thể thêm `--kernel-cwd .` để kiểm từ repo root. HTML được sinh từ notebook vừa execute; không xuất HTML từ notebook còn output cũ.

Builder cần `nbformat`, `nbclient`, `nbconvert`; kernel cần `ipykernel`, `matplotlib` và các dependencies P5. Danh sách công cụ notebook ở [requirements-notebook.txt](../preprocessing/encoding/requirements-notebook.txt). Các công cụ còn dùng từ requirements-review cũ đã gộp vào requirements-notebook; giữ Pandas/NumPy của artifact runtime.

Trong lượt _01, công cụ notebook/Ruff được cài riêng tại `/tmp/p5-tighten-20261109-9onitfnz/tools`; lệnh kiểm chứng dùng PYTHONPATH trỏ tới thư mục này. Đây là môi trường tạm, cần cung cấp lại từ requirements-notebook khi /tmp được dọn, không phải công cụ đã cài trong venv dự án. Builder ưu tiên site-packages của Python dự án trong kernel để giữ đúng Pandas/NumPy; không inject repo root qua môi trường kernel, nhờ đó kiểm được bootstrap của notebook. Thư mục `/tmp` chỉ là cách cung cấp công cụ ở máy này, không phải runtime dependency của Encoding hoặc input dữ liệu.

Sau khi kiểm notebook/HTML tạm, việc cập nhật cặp canonical phải đồng bộ hai SHA trong `manifest.EDA` và bản manifest evidence, bảo toàn bản trước nếu còn được manifest cũ tham chiếu. Refactor hiện tại không tái fit hoặc thay artifact dữ liệu.

EDA 5.177 và builder cũ đã retire theo _01. Notebook cuối chỉ cần parent metrics để so sánh; parent metrics còn ở reports/preprocessing/05_encoding/p5_2026-11-09_frozen_v2/metrics.json. Không cần tạo lại notebook lịch sử.
