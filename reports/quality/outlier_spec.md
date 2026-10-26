# 📋 BẢNG KẾ HOẠCH XỬ LÝ NGOẠI LAI & LUẬT CHẤT LƯỢNG (OUTLIER SPEC)

> **Thành viên phụ trách:** Phan Nhật Tài — Bước 5, Giai đoạn 3 (TASKS.md mục 6.3.5)
> **Nhánh Git:** `feature/outliers-quality`
> **Cơ sở trích xuất:** Bệnh án EDA 8 sàn (`eda_all.json` — sinh từ `collection/reports/EDA_<source>.ipynb` qua `scripts/read_eda_diagnosis.py`), trích riêng **Trụ cột 4 (Distribution & Outliers)** ngày 2026-10-26.
> **Nguyên tắc:** EDA-First Protocol — mọi ngưỡng/cơ chế xử lý bên dưới đều truy xuất trực tiếp từ bệnh án, không áp đặt công thức chung.

---

## 1. Kết luận chung từ bệnh án 8 sàn (Đồng thuận toàn hệ thống)

Cả 8 sàn đều được EDA cảnh báo cùng một mô hình phân phối và kèm 3 quy tắc bất khả xâm phạm:

| # | Kết luận EDA | Hành vi bắt buộc trong `outlier_handler.py` |
| :-: | :--- | :--- |
| 1 | Phân phối lương **lệch phải (Right-skewed)**; tương quan kinh nghiệm–lương đồng biến | Tính IQR trên giá trị gốc; ghi chú log-transform $\log(1+x)$ thuộc tầng modeling (không làm ở bước này) |
| 2 | Ngoại lai IQR lương cao **phần lớn là TRUE outlier** (thị trường cấp cao Tech Lead/Quản lý), **không phải lỗi gõ nhầm** | **Tuyệt đối KHÔNG drop dòng** — bảo toàn kỹ năng đi kèm |
| 3 | Giải pháp được EDA "chỉ định" là **Winsorization Capping P1–P99** (hoặc RobustScaler khi train) | Capping tại phân vị 1% và 99%, gắn cờ `is_outlier_capped = True` cho từng hàng bị cap |

---

## 2. Bảng phân tầng xử lý theo từng sàn

| Sàn | Đặc điểm Trụ cột 4 từ bệnh án | Định mức sai biệt (Differential Handling) |
| :--- | :--- | :--- |
| **careerviet** | Cấp 'Nhân viên' áp đảo **80.5%**; Quản lý 6.2%, Trưởng nhóm 7.0%, Thực tập sinh 2.0%; kinh nghiệm trung bình **2.65 năm** (nhóm 1–2 năm và 3–5 năm chiếm 73.8%) | ⚠️ **Sàn có bằng chứng lỗi nhập liệu rõ nhất**: cấu trúc mẫu nghiêng về non-Director → bật đủ **3 rule sửa lỗi số**, đặc biệt rule Over-zeroing (`> 300 triệu` cho vị trí non-Director là đáng ngờ cao). Lương năm dạng "300–450 triệu/năm" đã được Trụ cột 2 cảnh báo → kiểm tra rule nhầm lương năm. |
| **glints** | Lệch phải; lương ngoại tệ USD/SGD (remote package tới $2,000/tháng); Tech Lead lương cực cao là **hàng thật** | Capping P1–P99 tiêu chuẩn; **thận trọng rule USD-vào-VNĐ**: giá trị nhỏ (100–50.000) có thể là USD **chưa quy đổi** hợp pháp do Tầng 1 Header Regex của Khoa chưa bắt → chỉ sửa + ghi log, không sửa ngầm. |
| **itviec** | Lệch phải; sàn top lương cao nhất thị trường ($1,200–$3,500 USD ≈ 30–89 triệu VND/tháng); Middle & Senior > 80%, gần như không có Fresher/Intern | Ngưỡng trên của IQR **sẽ cao hơn các sàn khác** — bắt buộc tính phân vị **theo từng sàn (per-source)**, KHÔNG dùng bound chung toàn table, nếu sẽ cap nhầm lương thật. |
| **topcv** | Lệch phải, ngoại lai thị trường cấp cao | Capping tiêu chuẩn theo từng sàn. |
| **topdev** | Lệch phải, ngoại lai thị trường cấp cao | Capping tiêu chuẩn theo từng sàn. |
| **jobsgo** | Lệch phải, ngoại lai thị trường cấp cao | Capping tiêu chuẩn theo từng sàn. |
| **vieclam24h** | Lệch phải, ngoại lai thị trường cấp cao | Capping tiêu chuẩn theo từng sàn; lưu ý dữ liệu JD hay bị ngắt bullet (thuộc Phát, ảnh hưởng `jd_text` khi dò từ khóa "năm/annual"). |
| **vietnamworks** | Lệch phải, ngoại lai thị trường cấp cao; marker `salary = 0` đặc thù đã được Sơn xử lý ở Bước 4 | Chỉ tính IQR trên NaN-sạch; đảm nhận thêm kiểm tra `salary_min <= salary_max` vì Algolia trả dải min/max độc lập. |

---

## 3. Ba lỗi nhập liệu số — Luật sửa (theo TASKS.md 6.3.5, đối chiếu bệnh án)

Áp dụng **trước** khi winsorize, trên `salary_max_vnd` (và tương tự `salary_min_vnd`):

| Rule | Điều kiện phát hiện | Hành động sửa | Cờ ghi vết |
| :-: | :--- | :--- | :--- |
| **R1. Gõ USD vào ô VNĐ** | $100 < \text{salary} < 50.000$ (VNĐ/tháng không thể rẻ thế) | $\times\ 25.400$ | `salary_fix_applied = 'usd_to_vnd'` |
| **R2. Thừa số 0 (Over-zeroing)** | $\text{salary} > 300.000.000$ **và** cấp bậc non-Director (dùng `standardized_seniority` của Phát; careerviet 80.5% là Nhân viên → rule này rất hữu dụng) | Chia về dải hợp lý theo logic bậc 10 | `salary_fix_applied = 'over_zeroing'` |
| **R3. Nhầm lương năm vào tháng** | $\text{salary} > 200.000.000$ **và** `jd_text` chứa "năm/annual/year" (careerviet trụ cột 2 nêu ví dụ "300–450 triệu/năm") | $/\ 12$ | `salary_fix_applied = 'annual_to_monthly'` |

> 📌 **Khoảng trống code hiện tại** (`preprocessing/missing_outlier/outlier_handler.py`):
> - R2 (Over-zeroing) **chưa cài đặt** — thêm vào `fix_common_salary_input_errors()`;
> - Dải R1 hiện wrote `100–10.000`, TASKS.md yêu cầu `< 50.000` — nới theo chuẩn nghiệm thu;
> - Winsorize **chưa gắn cờ** `is_outlier_capped` — sửa `winsorize_series()` hoặc bọc hàm mới trả kèm mask cờ.

---

## 4. Các cột áp dụng kiểm định

| Cột | Phương pháp | Ghi chú |
| :--- | :--- | :--- |
| `salary_min_vnd`, `salary_max_vnd` | IQR ($1.5 \times$) để **báo cáo** + Winsorize P1–P99 để **xử lý** | Tính **theo từng sàn** (per-source quantile) — lý do xem bảng mục 2 (itviec) |
| `min_experience_years` | IQR + Winsorize P1–P99 | Trần thực tế ≤ ~20 năm; giá trị âm → luật chất lượng QR2 bên dưới |
| `raw_headcount` (nếu Khoa parse được số) | IQR, chỉ báo cáo không cap |headcount | Đặc thù ngoại lai số người, tùy chọn |

## 5. Luật chất lượng (`quality_rules.py`) & `quality_score`

- **QR1:** `salary_min_vnd <= salary_max_vnd` (vi phạm → trừ điểm)
- **QR2:** `min_experience_years >= 0` và `<= 30`
- **QR3:** `raw_deadline >= raw_posted_date` (sau khi Khoa chuẩn hóa ISO 8601)
- **QR4:** Không có giá trị âm ở cột lương
- **QR5:** Bản ghi bị cả 3 rule R1–R3 sửa cùng lúc → nghi ngờ nặng, trừ điểm sâu
- **`quality_score`** (0.0–1.0): khởi điểm 1.0, trừ dần theo trọng số vi phạm QR và số lần sửa lỗi số; hàng `is_imputed_by_genai = True` bị trừ nhẹ (minh bạch kiểm toán, không loại bỏ).

## 6. Số liệu chưa chốt — Cần đo lại sau khi module Transformation (Khoa) có output

Bệnh án EDA **không ghi sẵn con số $Q_1, Q_3$, Bound, P1, P99 cụ thể** cho từng sàn (trừ các mô tả định tính ở mục 2). Do đó:

- [ ] Chạy `detect_iqr_outliers()` trên bảng staging thật per-source sau Bước 2+4 → điền bảng kết quả vào báo cáo audit;
- [ ] Đối chiếu tỷ lệ cap thực tế với mô tả "lệch phải" — nếu một sàn cap > 5% dữ liệu → nghi ngờ transform của Khoa sinh lỗi hệ thống, báo lại leader thay vì cap mù;
- [ ] Xác nhận `is_salary_negotiable = 1` (MNAR, NaN) được loại đúng khỏi tính phân vị.

## 7. việc kế tiếp theo_spec

1. `git checkout -b feature/outliers-quality`
2. Hoàn thiện `outlier_handler.py` (R2 + cờ `is_outlier_capped` + nới dải R1)
3. Viết mới `quality_rules.py`
4. Viết `tests/test_outliers_quality.py` — chứng minh 2 điều kiện DoD (sửa đúng 3 lỗi; cap đúng P1–P99, không crash khi NaN)
5. Chạy trên dữ liệu thật → xuất `reports/quality/outlier_and_quality_audit_report.md`
6. PR về `integration/Thuan`
