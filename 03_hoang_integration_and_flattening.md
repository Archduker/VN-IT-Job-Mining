# BÁO CÁO NHIỆM VỤ BƯỚC 2: INTEGRATION & SCHEMA FLATTEN

* **Người thực hiện:** Đỗ Nhật Hoàng
* **Nhánh Git:** `feature/p2-integration-flatten`
* **Thư mục thực hiện:** `preprocessing/integration/`
* **Tệp đầu ra chính:** `data/preprocessing/02_integration/all.parquet`
* **Tệp kiểm toán hệ thống:** `reports/preprocessing/02_integration/_all.json`

---

## 1. Mục tiêu và Nguyên tắc Kỹ thuật
* **Hợp nhất đa nguồn:** Hợp nhất dữ liệu tuyển dụng IT từ 8 nguồn (`topcv`, `topdev`, `itviec`, `vietnamworks`, `careerviet`, `glints`, `jobsgo`, `vieclam24h`) sau bước P1 Clean về một bảng phẳng duy nhất.
* **Cấu trúc lưu trữ:** Xuất tệp tổng hợp duy nhất dưới định dạng **Apache Parquet (`all.parquet`)** bằng engine `pyarrow` để tối ưu dung lượng lưu trữ và tốc độ truy vấn.
* **Bảo toàn Hợp đồng Dữ liệu (Data Contract - Zero-Drop):**
  $$\sum_{i=1}^{8} N_{clean\_input}^{(i)} = N_{integrated\_output} = N_{master}$$
  Bảo toàn 100% số lượng bản ghi, không drop bất kỳ dòng nào. Bản ghi lỗi cú pháp JSON được đưa qua cơ chế fallback an toàn để bảo toàn nguyên vẹn số lượng.
* **Ngăn chặn Sneaky Null:** Mọi trường khuyết thiếu được làm sạch về `None` / `NULL`, không ép kiểu chuỗi `"None"`, `"nan"` hay `""`, đảm bảo tương thích cho các bước tiếp theo (P3 bóc tách và P4 xử lý missing).
* **Định danh duy nhất:** Tạo `job_id_global` kết hợp `{source}_{source_job_id}` để triệt tiêu hoàn toàn rủi ro đụng độ khóa chính giữa các sàn.
* **Tự động hóa Cloud Lakehouse (Cloudflare R2):** Tích hợp hàm `ensure_p1_data_from_r2` tự động kiểm tra và tải dữ liệu P1 Clean từ bucket Cloudflare R2 về local trước khi tiến hành xử lý tích hợp.

---

## 2. Kết quả Kiểm toán Bản ghi (Audit Summary)

| STT | Sàn tuyển dụng (Source) | Đầu vào P1 Clean ($N_{in}$) | Đầu ra P2 Flatten ($N_{out}$) | Chênh lệch (Dropped) | Hợp đồng Data Contract |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | **TopCV** | 1.561 | 1.561 | 0 | **PASS (Zero-drop)** |
| 2 | **TopDev** | 227 | 227 | 0 | **PASS (Zero-drop)** |
| 3 | **ITViec** | 905 | 905 | 0 | **PASS (Zero-drop)** |
| 4 | **VietnamWorks** | 900 | 900 | 0 | **PASS (Zero-drop)** |
| 5 | **CareerViet** | 448 | 448 | 0 | **PASS (Zero-drop)** |
| 6 | **Glints** | 271 | 271 | 0 | **PASS (Zero-drop)** |
| 7 | **JobsGO** | 683 | 683 | 0 | **PASS (Zero-drop)** |
| 8 | **Vieclam24h** | 182 | 182 | 0 | **PASS (Zero-drop)** |
| **Σ** | **TỔNG HỢP (all.parquet)** | **5.177** | **5.177** | **0** | **100% BẢO TOÀN** |

*(Ghi chú: Bản log chi tiết các trường dữ liệu và số lượng của từng lần chạy được máy tự động xuất tại `reports/preprocessing/02_integration/_all.json`).*

---

## 3. Đặc tả 28 Cột Chuẩn Trong Schema Thống Nhất (`all.parquet`)

1. **Nhóm Khóa & Nguồn gốc (5 trường):**
   * `job_id_global`: Định danh duy nhất toàn hệ thống (`{source}_{source_job_id}`).
   * `source_platform`: Tên sàn tuyển dụng (`lowercase`).
   * `source_job_id`: ID gốc từ sàn.
   * `source_url`: Link bài tuyển dụng gốc.
   * `crawled_at`: Thời gian cào dữ liệu.
2. **Nhóm Metadata Clean từ P1 (5 trường):**
   * `it_rule`, `it_rule_level`, `it_status`, `dedup_key`, `also_on`.
3. **Nhóm Thông tin phẳng cốt lõi (18 trường):**
   * `job_title`, `company_name`, `company_address`, `raw_category_text`.
   * `raw_location_text`, `working_locations` (list), `raw_posted_date`, `raw_deadline`.
   * `raw_salary_text`, `raw_employment_type`, `raw_experience_text`, `raw_seniority_text`.
   * `raw_education_text`, `raw_headcount`.
   * `skills_list` (list), `benefits_list` (list).
   * `raw_description_text`, `raw_requirements_text`.

---

## 4. Danh mục File Bàn giao Trong Nhánh `feature/p2-integration-flatten`
1. `preprocessing/integration/__init__.py`: Package init file.
2. `preprocessing/integration/json_flattener.py`: Mô-đun làm phẳng chuẩn hóa 8 sàn.
3. `preprocessing/integration/run.py`: Kịch bản thực thi, kiểm toán Data Contract, kết nối R2 và gộp `all.parquet`.
4. `preprocessing/integration/run_integration.py`: Wrapper điều phối runner.
5. `data/preprocessing/02_integration/all.parquet`: Tệp dữ liệu tổng hợp hoàn chỉnh dạng Parquet.
6. `reports/preprocessing/02_integration/_all.json`: Tệp kiểm toán tự động của hệ thống.
7. `docs/preprocessing/integration/03_hoang_integration_and_flattening.md`: Báo cáo nghiệm thu kỹ thuật.