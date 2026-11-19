# Yêu cầu dữ liệu suy ngược từ SD1–SD5

> Trạng thái: **đã duyệt 19/11/2026** (ngưỡng T1–T6 chốt như mục 4). Số đo trên Silver ngày 19/11 (3.916 tin, 26 trường; 81 tin dịch hỏng đã cách ly theo Q1).

File này dịch mục 4–6 của [`01`](01_sd1_buc_tranh_thi_truong.md)–[`05`](05_sd5_lo_trinh_hoc.md) thành **điều kiện kiểm được trên dữ liệu**. Mỗi SD ghi: thuật toán đọc gì, trường nào, điều kiện, số đo 19/11, đạt hay chưa. Processing (bước 07–12) và Mining (M1–M6) phải đọc file này trước khi đổi luật.

## 1. Quyết định của người dùng ngày 19/11

| # | Quyết định | Lời người dùng |
|---|---|---|
| 1 | Kỹ năng dùng cho khai phá là **K-tool**: lọc theo **loại** kỹ năng (công cụ hay khái niệm), lấy ở mọi phần của JD, không lọc theo phần JD | "đún rồi tui đang hớng cái đó"; duyệt phương án K-tool với "oke được đó" |
| 2 | Giữ thẻ kỹ năng của sàn (`via = meta`) | "thẻ kỹ năng đó vẫn giữ chứ" |
| 3 | Lương Lead thấp hơn Senior là do thiếu lương không ngẫu nhiên (MNAR). Không sửa định nghĩa cấp bậc; báo cáo ghi rõ | "(b) Lệch do thiếu lương không ngẫu nhiên"; "không đó là do các lương thoả thuạn nhiều bị lêcjh" |
| 4 | Mục tiêu lương của SD4 = trung bình các cận có số; tin chỉ ghi một cận thì lấy cận đó | "lấy trung bình" |
| 5 | Đưa `source` vào model lương làm biến kiểm soát (sàn khác nhau có mặt bằng lương công bố khác nhau) | duyệt cùng kế hoạch: "oke được đó" |
| 6 | Không tự suy kỹ năng ngầm (Flutter → Dart, React → JavaScript). Tin không ghi thì không có | "tui nghĩ là không tự suy nếu không có thì thôi" |

## 2. Ba góc nhìn kỹ năng

Cả ba lấy từ cùng một file `data/processing/08_skills/job_skills.parquet`, qua **một** hàm dùng chung `skill_view(job_skills, view)` (sẽ thêm ở `processing/extraction/skills.py`), để bước 10, Silver và Mining không mỗi nơi định nghĩa một kiểu.

| View | Định nghĩa | Dùng cho |
|---|---|---|
| **K-tool** | `kind = technical` và `type = tool`; mọi phần JD, cả bản gốc, bản dịch và thẻ sàn | Giỏ FP-Growth (SD2), cột `skill__*` (SD3, SD4), cầu kỹ năng và thứ tự học (SD5), số công cụ của tin người mới (SD1 câu 1.5) |
| **K-concept** | `kind = technical` và `type = concept` | Bảng riêng ở SD2, mô tả cụm (SD3), đặc trưng phụ (SD4) |
| **K-soft** | `kind` là `soft` hoặc `language` | Bảng thứ hai ở SD2 và SD5 |

- **tool** = sản phẩm, ngôn ngữ, framework, nền tảng, dịch vụ có tên riêng, học và dùng được trực tiếp (Python, React, PostgreSQL, AWS, Figma, Jira, SAP MM).
- **concept** = lĩnh vực, phương pháp, kiến thức chung, hoạt động (bảo mật thông tin, API, CI/CD, Agile, kiểm thử phần mềm, troubleshooting, AI).
- Ca ranh giới (chuẩn như REST, OAuth; chứng chỉ; bộ Office) đưa vào danh sách hỏi người dùng, không tự quyết.
- Kỹ năng chưa có nhãn `type` đã duyệt thì **không vào K-tool**.

**Vì sao cần.** Bước 08 hiện trích trung vị 25 kỹ năng/tin (trung bình 28), lẫn nhiều khái niệm chung: `information_security` có ở 35% tin Web; `database`, `api`, `troubleshooting`, `ai` cũng phủ rộng. Đối chiếu với `tech_stack` của repo `vietnam-it-job-trends` trên 1.047 tin trùng URL (dữ liệu ngoài do LLM sinh, chỉ dùng trên máy để đối chiếu, không trộn vào dữ liệu):

| View đang có | Bắt được `tech_stack` của họ | Kỹ năng của mình nằm trong `tech_stack ∪ keywords` của họ |
|---|---|---|
| Mọi kỹ năng | 0,90 | 0,36 |
| Kỹ thuật, mọi phần JD | — | 0,46 |
| Kỹ thuật, chỉ phần yêu cầu + thẻ sàn | 0,60 (trung vị 10 kỹ năng/tin) | — |

Lọc theo phần JD làm mất 30% công cụ thật; phần thừa chủ yếu là khái niệm. Vì vậy lọc theo **loại** (quyết định 1).

## 3. Điều kiện theo từng SD

Ký hiệu: ✅ đạt, ⚠️ đạt một phần hoặc phải ghi giới hạn, ❌ chưa đạt, ⏳ chưa đo được.

### SD1 · Bức tranh thị trường (BI, M1)

| Thuật toán đọc | Trường | Điều kiện | Số 19/11 | |
|---|---|---|---|---|
| Đếm theo nghề, cấp, tỉnh, hình thức | `job_family`, `seniority`, `province`, `work_mode`, `employment_type` | Mỗi bảng ghi n và độ phủ; ô n < 30 ghi "ít dữ liệu" | Xem `reports/preprocessing/04_normalization/silver.json` | ✅ |
| Lương công bố theo nghề × cấp | `salary_min/max`, `salary_negotiable` | Ô có ≥ 30 tin có lương mới kết luận | 15/55 ô nghề × cấp đủ 30 tin | ⚠️ |
| Lương theo cấp | như trên | Ghi tỷ lệ thỏa thuận theo cấp cạnh trung vị (quyết định 3) | Trung vị (triệu): Intern 10, Junior 15,5, Middle 22,5, Senior 37,5, Lead 30. Senior ẩn lương 73% | ⚠️ MNAR, ghi rõ |
| Tháng | `posted_month` | So cơ cấu trong tháng, không so tổng; tháng 9 chỉ dùng 6 nguồn ghi ngày đăng | Theo `00_de_tai.md` mục 8 | ✅ |
| Câu 1.5: người mới bị đòi gì | `seniority` ∈ {Intern, Fresher, Junior}, **K-tool**, `n_tools` | Số công cụ/tin đo bằng K-tool, không bằng mọi kỹ năng | Đang đo trên mọi kỹ năng: trung vị 14 kỹ năng kỹ thuật | ❌ chờ K-tool |

### SD2 · Gói kỹ năng và kỹ năng hiếm (FP-Growth, M2)

| Thuật toán đọc | Trường | Điều kiện | Số 19/11 | |
|---|---|---|---|---|
| Giỏ = tập công cụ của một tin | K-tool | Luật không hiển nhiên do khái niệm chung chiếm giỏ; không công cụ nào phủ ≥ 20% ở cả 6 nghề lớn | `information_security` 35% tin Web (đang là kỹ năng) | ❌ chờ K-tool |
| Kiểm tra luật đã biết | K-tool | React ⇒ JavaScript/TypeScript có confidence ≥ 0,6 | 0,67 | ✅ |
| Flutter ⇒ Dart | K-tool | **Không** là tiêu chí lỗi trích: đo độ đầy đủ của JD (quyết định 6) | 0,39 | ⚠️ ghi giới hạn |
| Bảng khái niệm, bảng kỹ năng mềm | K-concept, K-soft | Bảng riêng, không trộn vào giỏ công cụ | Chưa có | ⏳ |
| Kỹ năng hiếm | K-tool, DF | DF < 5 không gán nhãn, bị gom ở bước 10b | Kỹ thuật dùng: 2.003; DF ≥ 5: 1.407; DF ≥ 10: 1.047 | ✅ |

### SD3 · Nhóm việc và tin khác hoặc mới (phân cụm, Isolation Forest; M3, M4)

| Thuật toán đọc | Trường | Điều kiện | Số 19/11 | |
|---|---|---|---|---|
| Vector nội dung | `job_emb.npz` (12_e5) | Vector tin = trung bình bullet `mo_ta` + `yeu_cau`, **không lấy `phuc_loi`** (phúc lợi giống nhau giữa nghề) | e5 đang chạy trên bullet cũ | ❌ chờ P4 |
| Khối kỹ năng | `skill__*` = K-tool | Cụm không tách theo số kỹ năng: khái niệm chung không nằm trong khối chính | Hiện là mọi kỹ năng | ❌ chờ K-tool |
| So với nhóm luật | `job_family` | Có đủ 10 nhóm + Other | 100% | ✅ |
| Mã lý do "khác hoặc mới" | `n_tools`, độ dài, lương | Ngưỡng đặt theo **phân vị** của bảng mới, không giữ số cũ | Ngưỡng cũ tính trên mọi kỹ năng | ❌ đặt lại khi làm M4 |

### SD4 · Kỹ năng nào đáng tiền (Random Forest + SHAP, M5)

| Thuật toán đọc | Trường | Điều kiện | Số 19/11 | |
|---|---|---|---|---|
| Mục tiêu | `salary_target_m` = trung bình các cận có số, triệu/tháng (quyết định 4) | Chỉ tin có lương, không ngoại lai; không làm đầu vào (chặn bằng `assert_no_leakage`) | 1.644 tin có lương, 978 công ty | ✅ |
| Biến kiểm soát | `job_family`, `seniority`, `exp_min_years`, `province`, `source` (quyết định 5) | Có đủ cột trong ma trận đặc trưng | `source` chưa có trong M5 | ❌ thêm khi làm M5 |
| Đặc trưng kỹ năng | `skill__*` (K-tool), `concept__*` phụ | Mỗi kỹ năng đưa vào SHAP có ≥ 30 tin có lương | 259 kỹ năng kỹ thuật có ≥ 30 tin (tính trên mọi kỹ năng) | ⏳ đo lại trên K-tool |
| Chia train/test | `company_id` | Chia theo công ty, không để một công ty ở cả hai phía | Có `company_id` | ✅ |
| Ước tính tin thỏa thuận | — | Ghi nhãn "ước tính"; nhắc MNAR (quyết định 3) | — | ⏳ |

### SD5 · Nên học gì, theo thứ tự nào (M6)

| Thuật toán đọc | Trường | Điều kiện | Số 19/11 | |
|---|---|---|---|---|
| Cầu kỹ năng của người mới theo nghề | K-tool, `job_family`, `seniority` | Nghề có ≥ 30 tin người mới | Web 514, Other 180, Tester 123, Data/AI 98, Bridge 94, Security 64, DevOps 45. Design, Game < 30; "Other" bỏ vì không phải một nghề | ⚠️ 6 nghề |
| coverage@N | K-tool | Top 10 công cụ phủ được ≥ 70% công cụ của phần lớn tin người mới | Trên mọi kỹ năng: chỉ 50% tin có thể đạt 70% với top 10 (trung vị 14 kỹ năng) | ❌ chờ K-tool |
| Thứ tự học | Luật SD2 (K-tool) + giá trị SD4 | Không tự suy kỹ năng tiền đề (quyết định 6) | — | ⏳ |
| Kỹ năng mềm | K-soft | Bảng riêng | — | ⏳ |

## 4. Ngưỡng nghiệm thu K-tool (chốt 19/11)

| # | Chỉ số | Ngưỡng | Đo bằng |
|---|---|---|---|
| T1 | Trung vị số công cụ của tin người mới | ≤ 10 | `scripts/eval_skill_views.py` |
| T2 | React ⇒ JavaScript/TypeScript | confidence ≥ 0,6 | như trên |
| T3 | Không công cụ nào phủ ≥ 20% ở **cả** 6 nghề lớn | 0 công cụ | như trên |
| T4 | Đọc tay 100 cặp (tin, công cụ) ngẫu nhiên, seed 42 | đúng ≥ 90% | `data/processing/skill_candidates/tool_check_100.csv` |
| T5 | Trên tin ghép với dữ liệu ngoài: bắt `tech_stack` của họ | ≥ 0,85 | dữ liệu ngoài ở `data/external/vnjt/` (gitignore) |
| T6 | Trên tin ghép với dữ liệu ngoài: công cụ của mình nằm trong `tech_stack ∪ keywords` của họ | ≥ 0,70 | như trên |

T5 và T6 chỉ là đối chiếu: dữ liệu ngoài do LLM sinh, không phải gold. Khi có bộ gold (`gold_labels.json`) thì F1 trên gold thay cho T5, T6.

**Kết quả đo 19/11** (`python scripts/eval_skill_views.py`, skills_v2 2.1.0, bước 08 chạy lại trên bảng 04; ghép ngoài 1.606 tin theo mã + tiêu đề, trong đó 1.045 trùng nguyên URL):

| View | Số kỹ năng | Trung vị/tin | T1 người mới | T2 | T3 | T5 / T6 (1.606 tin) | T5 / T6 (1.045 tin trùng URL) |
|---|---|---|---|---|---|---|---|
| Mọi kỹ năng | 2.077 | 25 | 19 | 0,67 | 6 (kỹ năng mềm) | 0,93 / 0,34 | 0,90 / 0,34 |
| Kỹ thuật | 2.003 | 19 | 14 | 0,67 | 0 | 0,93 / 0,40 | 0,90 / 0,41 |
| **K-tool** | **534** | **5** | **4 ✅** | **0,67 ✅** | **0 ✅** | **0,85 ✅ / 0,69 ❌** | **0,82 ❌ / 0,69 ❌** |
| K-concept | 873 | 14 | 10 | — | 0 | 0,06 / 0,27 | 0,07 / 0,30 |
| K-soft | 74 | 5 | 5 | — | 6 | 0 / 0,02 | 0 / 0,02 |

- **T4:** 94/100 cặp đúng ✅. Sáu cặp sai: OpenStack Swift (lưu trữ) khớp ngôn ngữ Swift; "ASP" trong "ASP .NET CORE" khớp ASP classic; Oracle là tên công ty; "EXCEL" là giá trị cốt lõi của VinUni; alias "grid" của Selenium Grid khớp "Grid System"; "quản lý phiên bản" của artifact registry khớp Git.
- **T5, T6 sát ngưỡng:** T6 thiếu 0,01. Phần chênh còn lại chủ yếu là công cụ mình bắt mà danh sách LLM của họ bỏ (họ trung bình 5,5 mục/tin), nên đây là đối chiếu, không phải gold.
- **SD5, coverage@10 trên K-tool** (tỷ lệ tin người mới mà top 10 công cụ của nghề phủ ≥ 70% công cụ của tin): Web 0,13; Bridge 0,44; Data/AI 0,18; Tester 0,28; DevOps/Cloud 0,09; Security 0,11. Tin người mới chỉ có trung vị 4 công cụ nhưng mỗi nghề có nhiều stack khác nhau, nên một danh sách top 10 chung không phủ được phần lớn tin. M6 cần tính theo gói (SD2) thay vì một danh sách.

**Người dùng chốt 19/11 sau khi xem số** ("oke continue"):

- Chấp nhận T5 0,85 / 0,82 và T6 0,69 (thiếu 0,01): danh sách ngoài do LLM sinh, trung bình 5,5 mục/tin, không phải gold. K-tool được dùng cho P3 và Mining.
- Sửa hai alias sai của T4: bỏ "grid" (Selenium Grid) và "ASP" (ASP classic), cả hai thành `not_skill` generic. Sau khi chạy lại 08: 111.116 dòng (bớt 12), K-tool 533 kỹ năng, các chỉ số T1–T6 không đổi. Bốn ca tên mơ hồ (Oracle, Swift, EXCEL, "quản lý phiên bản") giữ nguyên.
- `min_df` = 15 cho cả ba khối của bước 10: `skill__` 290 cột (phủ 92% dòng K-tool), `concept__` 561 (96%), `soft__` 62.

## 5. Điều kiện còn treo

- **SD1:** chỉ 15/55 ô nghề × cấp có ≥ 30 tin có lương; các ô còn lại ghi "ít dữ liệu".
- **SD1, SD4:** lương Lead < Senior do MNAR; không sửa cấp bậc, báo cáo ghi tỷ lệ thỏa thuận theo cấp.
- **SD2:** Flutter ⇒ Dart 0,39 là số đo độ đầy đủ của JD, không phải lỗi trích.
- **SD3:** ngưỡng mã lý do M4 đặt lại theo phân vị của `n_tools` khi làm M4.
- **SD5:** Design và Game không đủ 30 tin người mới; "Other" bỏ khỏi lộ trình.
- **Chung:** bước 07 chưa duyệt tiêu đề phần và dấu hiệu ưu tiên, nên mọi kỹ năng đang mang mức "required"; 154 ca lệch loại hợp đồng (T9b) chưa xem tay; bộ gold kỹ năng chưa có nên chưa đo được F1.

## 6. Việc kéo theo

| Giai đoạn | Việc |
|---|---|
| P1 | Nhãn `tool`/`concept` cho skills_v2 (luật K8.17), duyệt theo lô |
| P2 | Bước 08 ghi `type`; hàm `skill_view`; đo T1–T6 |
| P3 | Bước 10: ba khối `skill__` (K-tool), `concept__`, `soft__`; `n_tools`, `n_concepts`, `n_soft`; `salary_target_m`; `emp__` từ `employment_type`; `posted_month` dạng `YYYY-MM`; bỏ bước 09 |
| P4 | 12_e5 trên bullet mới, vector tin bỏ `phuc_loi` |
| Mining | M1 → M2 → M3/M4 → M5 → M6, mỗi bước kiểm điều kiện ở mục 3 |
