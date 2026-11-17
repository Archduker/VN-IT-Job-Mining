# SD1 · Bức tranh toàn cảnh thị trường IT Việt Nam T9–T11/2026

> Tầng 1: BI (thống kê mô tả). Đề tài và bối cảnh: [00_de_tai.md](00_de_tai.md).

## 1. Bài toán nói đơn giản

Trước khi tìm quy luật hay train model, cần biết thị trường đang ra sao:

- Đang tuyển nghề gì, cấp nào, ở đâu.
- Bao nhiêu tin chịu công khai lương, và lương công khai nằm trong khoảng nào.
- Người mới (Intern/Fresher/Junior) bị đòi hỏi những gì so với người đã đi làm vài năm.

SD1 chỉ **đếm, chia nhóm và so sánh**. Không có model. Các SD sau dùng số của SD1 làm chuẩn so sánh. Ví dụ, SD4 so model với trung vị lương theo cấp × nghề lấy từ SD1.

## 2. Câu hỏi cần trả lời

| Mã | Câu hỏi |
|---|---|
| 1.1 | Thị trường đang tuyển những nhóm nghề nào, mỗi nhóm bao nhiêu tin? Từng trang tuyển dụng nghiêng về nhóm nghề nào? |
| 1.2 | Cơ cấu cấp bậc ra sao: bao nhiêu phần trăm tin dành cho Intern/Fresher, Junior, Middle, Senior, Lead/Manager? Cơ cấu này khác nhau thế nào giữa các nhóm nghề? |
| 1.3 | Tin tập trung ở tỉnh nào? Tỷ lệ remote, hybrid, onsite ra sao, khác nhau thế nào theo nghề? |
| 1.4 | Bao nhiêu tin công khai lương và bao nhiêu tin ghi "thỏa thuận" (theo trang, nghề, cấp)? Lương công khai nằm ở đâu (trung vị, khoảng tứ phân vị) theo nghề × cấp bậc và theo tỉnh? |
| 1.5 | So với tin Middle trở lên, tin cho người mới đòi bao nhiêu năm kinh nghiệm, bao nhiêu kỹ năng, bao nhiêu phần trăm JD viết bằng tiếng Anh, và lương công khai bao nhiêu? |
| 1.6 | Phúc lợi nào phổ biến nhất, và có khác nhau giữa các nghề và cấp bậc không? |
| 1.7 | Cơ cấu nghề và cấp bậc có khác nhau giữa các tháng T9, T10, T11 không? (Chỉ so tỷ lệ trong từng tháng, không so tổng số tin.) |

## 3. Dữ liệu dùng

Đầu vào là bảng sau bước `04_normalization` cộng `10_features`. Độ phủ hiện tại xem ở [00_de_tai.md mục 8](00_de_tai.md#8-ảnh-chụp-dữ-liệu-sẽ-đổi).

| Câu | Cột |
|---|---|
| 1.1 | `job_family`, `source` |
| 1.2 | `seniority` (5 nhãn: Intern/Fresher, Junior, Middle, Senior, Lead/Manager; xem `SENIORITY_ORDER_LABELS` trong `mining/config.py`), `level_inferred` |
| 1.3 | `tinh_chinh`, `work_mode` |
| 1.4 | `salary_status`, `salary_min_vnd_capped`, `salary_max_vnd_capped`, `is_outlier_salary` |
| 1.5 | `seniority`, `exp_min_years`, số kỹ năng (đếm từ `skills_std`), `language`, lương như ở 1.4 |
| 1.6 | `benefits_std` |
| 1.7 | `posted_month` (`YYYY-MM`), `posted_month_source`, `job_family`, `seniority` |

`posted_month` được tạo ở bước 03, thay cho `posted_date` trong dữ liệu sạch (PRE-37). Nguồn có ngày đăng thì lấy tháng đăng; nguồn không ghi ngày đăng (topcv, một phần topdev) thì lấy tháng của **lần cào đầu tiên**.

"Người mới" là tin có `seniority` thuộc Intern/Fresher hoặc Junior. Theo quyết định ngày 11/11 (PRE-33), tin dưới 1 năm kinh nghiệm được tính là Intern/Fresher.

## 4. Cách trả lời

Mọi câu đều dùng cùng một cách: **đếm, tính tỷ lệ, lập bảng chéo, lấy trung vị và tứ phân vị**. Lương dùng trung vị chứ không dùng trung bình, vì vài tin lương rất cao sẽ kéo trung bình lên.

- **1.1:**
  - Đếm tin theo `job_family`.
  - Lập bảng chéo `job_family` × `source`, tính tỷ lệ theo hàng để thấy mỗi trang nghiêng về nghề nào.
- **1.2:**
  - Đếm theo `seniority`, lập bảng chéo `seniority` × `job_family`.
  - Báo riêng phần cấp bậc lấy từ trang và phần tự suy ra (`level_inferred`), để người đọc biết bao nhiêu phần là suy luận.
- **1.3:**
  - Đếm theo `tinh_chinh`. Hiện top 10 tỉnh, các tỉnh còn lại gộp thành "Khác".
  - Lập bảng chéo `work_mode` × `job_family`.
- **1.4:**
  - Tỷ lệ công khai lương = số tin có lương ÷ tổng số tin, tách theo trang, nghề và cấp.
  - Với các tin có lương và không bị đánh dấu ngoại lai: lấy trung vị và khoảng tứ phân vị của lương min và lương max theo nghề × cấp bậc, rồi theo tỉnh.
- **1.5:** chia hai nhóm "người mới" và "Middle trở lên", so 4 chỉ số:
  - trung vị `exp_min_years`;
  - trung vị số kỹ năng;
  - tỷ lệ JD tiếng Anh;
  - trung vị lương công khai.
- **1.6:**
  - Đếm tần suất từng phúc lợi trong `benefits_std`, lấy top 15.
  - Lập bảng chéo top 5 phúc lợi × cấp bậc.
- **1.7:**
  - Lập bảng tỷ lệ `job_family` và `seniority` trong từng `posted_month`.
  - Tháng 9 chỉ có tin từ nguồn ghi ngày đăng, vì tháng 9 chưa cào. Khi so tháng 9 với tháng 10–11 thì chỉ dùng tin có `posted_month_source = posted`, hoặc tách hai bảng theo `posted_month_source`.
  - Không kết luận "tăng/giảm", vì số tin mỗi tháng phụ thuộc lịch cào.

Quy tắc báo số áp dụng cho mọi bảng: ghi n và độ phủ; ô có n < 30 ghi "ít dữ liệu"; không nói về xu hướng theo thời gian. Lương ước tính của tin "thỏa thuận" (lấy từ SD4) chỉ được hiện ở một cột riêng có nhãn "ước tính".

## 5. Đầu ra

| Đầu ra | Dạng |
|---|---|
| Bảng số cho 1.1–1.6 | JSON do script đọc bảng đã chuẩn hóa sinh ra. Script và đường dẫn chốt khi làm SD1, ghi lại vào file này |
| Biểu đồ | Cột: nghề, cấp, tỉnh. Cột chồng: work mode × nghề. Hộp (box): lương theo cấp × nghề. Cột đôi: người mới so với Middle trở lên |
| Trang Monitoring | Trang Insights đọc JSON trên. Không có dữ liệu thì hiện trạng thái rỗng, không hiện số giả (Nguyên tắc 1 trong `AGENTS.md`) |

## 6. Cách biết đã trả lời đúng

- Tổng số tin trong mọi bảng phải bằng số tin của bảng đầu vào. Bảng nào có cột bị thiếu thì phải có dòng "Không rõ" riêng.
- Đối chiếu tay 20 tin ngẫu nhiên: nghề, cấp, tỉnh và lương trong bảng phải khớp với trang gốc.
- Sanity check: trung vị lương phải tăng dần từ Intern/Fresher lên Lead/Manager. Hiện check này đang fail (Senior thấp hơn Middle, MINE-1), xem PRE-35.
- Mọi số trong báo cáo phải chạy lại ra đúng số đó từ cùng một file đầu vào.

## 7. Những gì không trả lời được

- Xu hướng theo thời gian: chỉ có khoảng 3 tháng, tháng của một phần tin là suy từ ngày cào, và số tin mỗi tháng phụ thuộc lịch cào.
- Ngày đăng chính xác: dữ liệu sạch chỉ giữ tháng (`posted_month`).
- Lương thật lúc nhận việc: dữ liệu chỉ có lương ghi trên tin. Kết luận về lương công khai chỉ đúng cho phần tin có công khai lương.
- Mức độ cạnh tranh, ví dụ số người nộp đơn cho mỗi tin: dữ liệu không có.
- Toàn bộ thị trường IT: dữ liệu chỉ phủ 8 trang. Tuyển qua giới thiệu nội bộ hay qua LinkedIn thì không có.

## 8. Code và spec liên quan

- Dữ liệu vào: `preprocessing/normalization/`, `processing/` (bước 10).
- Hiển thị: `monitoring/` (trang Insights), `docs/spec/09_monitoring_spec.md`.
- Chất lượng dữ liệu cần cho SD1: PRE-35, PRE-37 (`posted_month`) và PRE-12 trong `docs/KNOWN_ISSUED.md`. Ngưỡng n ≥ 30: PRE-36.
