# 🏆 CẨM NANG NHIỆM VỤ: PIPELINE INTEGRATION & EVALUATION
## THÀNH VIÊN PHỤ TRÁCH: THUẬN (TECH LEAD)

> **Hạn chót hoàn thành (Deadline):** **19:00 PM Chủ Nhật**  
> **Thư mục thực hiện chính (Folder Ownership):**  
> - `docs/reports/` (Kho báo cáo tổng hợp, báo cáo đánh giá mô hình, audit logs)  
> - `scripts/` (Các driver script chạy toàn trình E2E pipeline, đồng bộ lakehouse)  
> - `tests/integration/` (Hệ thống kiểm thử tích hợp liên phân hệ)  
> **Nhánh Git phụ trách:** `sprint/pipeline-delivery` (nhánh cơ sở tích hợp)  
> **Nhánh hợp nhất cuối cùng (Final Release):** `main`  
> **Tài liệu đặc tả đối chiếu:** [`docs/spec/08_evaluation_spec.md`](../spec/08_evaluation_spec.md), [`docs/spec/13_working_documentation.md`](../spec/13_working_documentation.md), [`agents.md`](../../agents.md)

---

## 1. Mục Tiêu & Các Vấn Đề Cốt Lõi Cần Giải Quyết

Thuận đóng vai trò là **Tổng Công Trình Sư & Trưởng Nhóm (Tech Lead)**, chịu trách nhiệm kết nối toàn bộ thành quả của 7 thành viên thành một hệ sinh thái duy nhất, đồng thời chủ trì phần Đánh giá tri thức (Module 08 Evaluation) để nghiệm thu đồ án tốt nghiệp:

1. **Điều Phối Tiến Độ & Gỡ Bỏ Rào Cản (Sprint Leadership):**
   - Theo dõi tiến độ hàng ngày của 7 thành viên (Khoa, Tài, Hoàng, Duy, Phát, Phúc, Sơn).
   - Kiểm tra việc tuân thủ ranh giới thư mục độc quyền (Folder Ownership); xử lý ngay nếu có nguy cơ chạm chéo file.
   - Tổ chức review mã nguồn và duyệt các Pull Request (PR) từ 7 nhánh con vào nhánh `sprint/pipeline-delivery` trước mốc 19:00 Chủ Nhật.
2. **Kiểm Thử Tích Hợp Toàn Trình (End-to-End Pipeline Integration):**
   - Xây dựng và hoàn thiện driver điều phối tích hợp trong `scripts/run_master_pipeline.py`:
     $$\text{Discovery} \longrightarrow \text{Detail} \longrightarrow \text{Clean} \longrightarrow \text{Integration} \longrightarrow \text{Transform} \longrightarrow \text{Normalize} \longrightarrow \text{Encode} \longrightarrow \text{Mining} \longrightarrow \text{PostgreSQL Mart}$$
   - Chạy kiểm thử tích hợp liên module trong `tests/integration/`: Đảm bảo dữ liệu từ R2 Lakehouse đi xuyên suốt tới PostgreSQL và hiển thị lên giao diện React mà không gặp bất kỳ lỗi schema hay kiểu dữ liệu.
3. **Chủ Trì Đánh Giá Học Thuật & Nghiệp Vụ (Module 08 Evaluation):**
   - **Trục Kỹ Thuật Thống Kê:**
     * Thẩm định quy luật kết hợp kỹ năng của Phúc: Xác thực $Lift > 1.20$, $Confidence \ge 0.60$.
     * Thẩm định phân cụm K-Means: Đo Silhouette Score $\ge 0.28$, Davies-Bouldin Index $< 1.80$.
     * Thẩm định mô hình lương: Đảm bảo $R^2 \ge 0.60$, $MAE \le 4.5\text{ triệu VNĐ}$ qua 5-Fold Cross Validation.
   - **Trục Thẩm Định Nghiệp Vụ Thị Trường (Market Sanity Checks):**
     * Thực hiện bộ 6 bài kiểm tra logic ngành (Sanity Checks S-01 đến S-06 trong `docs/spec/08_evaluation_spec.md`): Lương Senior phải cao hơn Junior, Hà Nội/TP.HCM chiếm $\ge 70\%$ thị phần, AI/Cloud có thặng dư lương dương.
     * Đối chiếu số liệu với Báo cáo thị trường IT Việt Nam của TopDev và ITviec.
   - **Đánh Giá Tính Ứng Dụng Cho Sinh Viên IT:**
     * Tính toán **Chỉ số Thâm hụt Kỹ năng (Skill Deficit Score - SDS)** cho phân khúc Intern/Fresher.
     * Mô phỏng tỷ lệ vượt qua bộ lọc ATS của sinh viên (từ 30% lên 75% khi bổ sung đúng các kỹ năng trong top combo).
4. **Nghiệm Thu Toàn Dự Án & Merge `main`:**
   - Soạn thảo báo cáo đánh giá toàn diện tại `docs/reports/final_evaluation_report.md`.
   - Sau khi toàn bộ test pass và đồ án chạy mượt mà, thực hiện merge nhánh `sprint/pipeline-delivery` vào `main`.

---

## 2. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Thuận làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Kiến Trúc Sư Trưởng & Tech Lead (Lead Systems Architect & Evaluator) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là tích hợp toàn bộ pipeline từ 7 thành viên, chạy kiểm thử toàn trình E2E và thực hiện Module 08 Evaluation (Đánh giá học thuật: Silhouette, Lift, R2, MAE; Thẩm định nghiệp vụ: 6 Sanity Checks, Skill Deficit Score cho sinh viên IT). Tham khảo đặc tả kỹ thuật tại docs/spec/08_evaluation_spec.md và docs/spec/13_working_documentation.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Thư mục phụ trách: `docs/reports/`, `scripts/`, `tests/integration/` và điều phối toàn bộ repo.
- Tuyệt đối tuân thủ nguyên tắc Real Numbers Only: Mọi con số trong báo cáo nghiệm thu phải tính toán từ tập dữ liệu Golden Master và kết quả mô hình thật, không dùng số liệu ước lượng cảm tính.
- Mọi thao tác đồng bộ với Cloudflare R2 phải dry-run trước khi apply.
- Quản lý nhánh: Đảm bảo toàn bộ 7 PR được rebase/merge sạch sẽ vào `sprint/pipeline-delivery` trước khi merge vào `main`.

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào: Toàn bộ code và artifacts từ 7 nhánh feature của nhóm.
- Đầu ra:
  * Script driver tích hợp E2E chạy thông suốt từ đầu đến cuối.
  * Báo cáo đánh giá hoàn chỉnh `docs/reports/final_evaluation_report.md`.
  * Bộ test tích hợp `tests/integration/` pass 100%.

### 4. YÊU CẦU THỰC HIỆN:
Hãy phân tích các nhánh hiện tại, lập kế hoạch tích hợp từng giai đoạn, chạy kiểm thử E2E và sinh báo cáo đánh giá đối chuẩn theo Module 08.
```

---

## 3. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [ ] **Bước 1 (Review PR):** Kiểm tra từng PR của 7 thành viên: Đảm bảo code sạch, chỉ sửa trong thư mục được giao, có báo cáo nghiệm thu đính kèm.
- [ ] **Bước 2 (Chạy kiểm thử toàn diện):**
  ```bash
  make test-fast
  pytest tests/integration/ -v
  ```
- [ ] **Bước 3 (Chạy E2E Pipeline Driver):**
  ```bash
  python scripts/run_staging_integration_pipeline.py
  python mining/run_mining_pipeline.py
  ```
  Xác nhận: Dữ liệu chảy mượt từ raw $\rightarrow$ `curated_flat_golden_jobs.parquet` $\rightarrow$ nạp bảng PostgreSQL $\rightarrow$ sinh đủ mining artifacts.
- [ ] **Bước 4 (Tính toán chỉ số Module 08):**
  * Chạy script tính toán các chỉ số thống kê (Silhouette, $R^2$, MAE, Lift).
  * Chạy kiểm tra 6 Sanity Checks S-01 đến S-06; xác nhận đạt $6/6$ tiêu chí.
- [ ] **Bước 5 (Kiểm tra Dashboard hoạt động):**
  ```bash
  ./start_monitoring.sh --check
  ```
  Mở trình duyệt, xác nhận cả Phân hệ Vận hành và Phân hệ Market Insights hiển thị số liệu thật, không có lỗi runtime.
- [ ] **Bước 6 (Bàn giao & Merge Main):** Merge `sprint/pipeline-delivery` vào `main`.

---

## 4. Mẫu Báo Cáo Nghiệm Thu Bàn Giao (Delivery Report Template)

*Sau khi nghiệm thu toàn bộ đồ án, Thuận điền thông tin vào mẫu dưới đây tại `docs/reports/final_evaluation_report.md`:*

```markdown
### BÁO CÁO TỔNG KẾT & NGHIỆM THU DỰ ÁN: VN-IT-JOB-MINING
- **Trưởng nhóm / Người thẩm định:** Bill Trần (Thuận)
- **Nhánh tích hợp:** `sprint/pipeline-delivery` -> Merge vào `main`
- **Thời điểm nghiệm thu:** [...]

#### 1. Tổng Kết Tiến Độ 8 Thành Viên:
- Khoa (Collection & Hotfixes): [Đạt / Ghi chú]
- Tài (Bước 1: Clean & Dedup): [Đạt / Ghi chú]
- Hoàng (Bước 2: Integration & Schema): [Đạt / Ghi chú]
- Duy (Bước 3 & 4: Transform & Normalize): [Đạt / Ghi chú]
- Phát (Bước 5: Feature Encoding): [Đạt / Ghi chú]
- Phúc (Data Mining Core): [Đạt / Ghi chú]
- Sơn (Monitoring Observatory): [Đạt / Ghi chú]
- Thuận (Integration & Evaluation): [Đạt / Ghi chú]

#### 2. Kết Quả Kiểm Thử Toàn Trình (E2E Test Results):
- Tổng số test cases: [...] passed / 0 failed
- Tổng số bản ghi thô thu thập: [...] tin tuyển dụng
- Tổng số bản ghi sạch Golden Master: [...] tin tuyển dụng (đã khử trùng lặp)

#### 3. Bảng Điểm Đánh Giá Học Thuật (Academic Evaluation Metrics):
- **Luật kết hợp kỹ năng (FP-Growth):** Top Lift = [...], Support = [...], Confidence = [...]
- **Phân cụm nghề nghiệp (K-Means):** Silhouette Score = [...] ($k = [...]$)
- **Hồi quy mức lương (Random Forest):** $R^2 = [...]$, $MAE = [...]$ triệu VNĐ

#### 4. Thẩm Định Nghiệp Vụ & Đóng Góp Cho Sinh Viên IT:
- Kết quả 6 Sanity Checks: 6/6 Đạt
- Top 3 combo kỹ năng giá trị nhất cho sinh viên mới ra trường:
  1. [...]
  2. [...]
  3. [...]
- Chỉ số thâm hụt kỹ năng trung bình của sinh viên (SDS): [...]%

#### 5. Đánh Giá Toàn Diện & Kế Hoạch Bảo Vệ Đồ Án:
- [Kết luận mức độ sẵn sàng bảo vệ trước Hội đồng chấm đồ án]
```
