# Các vấn đề đang chờ bạn quyết định

> **Cập nhật 10/11/2026:** mục 5 (cho phép OpenJev) bị đảo: bỏ JEV/OpenJev/Qwen, model duy nhất là `envit5-translation`.
>
> **Cập nhật 09/11/2026 (tối):** bạn đã trả lời mục 1, 2, 3, 4 (A, chờ phân tích kỹ năng), 5 (cho phép OpenJev), 7 (A), 9 (A), 10 (đã gán nhãn), 11. Các câu trả lời đã vào `KNOWN_ISSUED.md`. Mục còn mở (6 R2, 8 khoảng k, kỹ năng) đã đưa vào `docs/presentation/van_de_can_chot.html` để trình bày với nhóm.

Cập nhật 09/11/2026. Viết cho người không cần đọc code. Mỗi mục có: chuyện gì đang xảy ra, các lựa chọn, mình nghiêng về đâu (**chỉ là ý kiến của mình**, chưa phải quyết định), và nếu bạn chưa quyết thì chuyện gì xảy ra. Sau khi bạn chọn, mình ghi vào `KNOWN_ISSUED.md` / `docs/spec/fixes/` và đặc tả tiếp.

Gợi ý thứ tự: mục 1–3 nhỏ và nhanh; mục 4–6 ảnh hưởng nhiều nơi; mục 7 trở đi để sau.

## 1. Dòng dữ liệu hỏng: giữ hay bỏ? (PRE-18, issue F03)
- **Chuyện gì:** đôi khi một dòng trong file dữ liệu bị lỗi định dạng, máy không đọc được. Code của Hoàng **giữ lại** dòng đó thành một "tin giả" (tiêu đề là vài chữ đầu của dòng lỗi) để tổng số tin không bị hụt. Tài liệu P2 §8 lại ghi là **bỏ** dòng đó và ghi vào danh sách "đã bỏ".
- **Lựa chọn:**
  - A. Giữ như Hoàng nhưng đánh dấu "đây là tin giả" để bước sau lọc ra.
  - B. Bỏ dòng lỗi, ghi vào báo cáo "đã bỏ" (đúng tài liệu).
- **Mình nghiêng:** B. Tin giả lẫn vào dữ liệu có thể làm sai thống kê; số dòng bị bỏ vẫn được ghi lại nên không "mất dấu".
- **Nếu chưa quyết:** giữ như hiện tại (A không đánh dấu). Test đã sửa theo hành vi này.

## 2. Hai nhóm nghề: UI/UX hay Embedded? (PRE-22)
- **Chuyện gì:** tài liệu chia tin IT thành 12 nhóm nghề. Tài liệu gốc có nhóm "Thiết kế UI/UX" (không có "Embedded"). Code của Duy có "Embedded" (lập trình nhúng) và "Product" nhưng **không có UI/UX**, nên tin UI/UX Designer hiện bị để trống nhóm.
- **Số đo (09/11, 5.077 tin IT sau Clean, chỉ dựa vào tiêu đề):** tiêu đề UI/UX: 48 tin (0,9%); tiêu đề Embedded/nhúng/firmware: 71 tin (1,4%). Cả hai đều nhỏ.
- **Lựa chọn:**
  - A. Theo Duy (có Embedded, không UI/UX). Tin UI/UX rơi vào "Khác"/trống.
  - B. Theo tài liệu gốc (có UI/UX, không Embedded).
  - C. Thêm cả hai, thành 13 nhóm, sửa tài liệu "12 nhóm" thành 13.
- **Mình nghiêng:** C nếu bạn chịu đổi con số 12 trong tài liệu; còn không thì A cho đỡ phải sửa code. Cần nói rõ với Duy.
- **Nếu chưa quyết:** giữ A (code hiện tại); tin UI/UX để trống nhóm.

## 3. Cột cấp bậc tên gì? (F05)
- **Chuyện gì:** bạn đã chốt 5 cấp. Còn hai cột trùng việc: `seniority_level` (Duy, 0–4) và `seniority_ord` (Phát, đang 0–5). Phải về một thang.
- **Lựa chọn:** A. Giữ cả hai tên, cùng thang 0–4. B. Bỏ `seniority_ord`, dùng `seniority_level`.
- **Mình nghiêng:** B, nhưng hỏi Phát vì tên cột nằm trong hợp đồng encoding của Phát.
- **Nếu chưa quyết:** mình chưa sửa code cấp bậc (F05 đứng yên).

## 4. Số phận của cohort Phát (PRE-28)
- **Chuyện gì:** bước 5 của Phát chỉ giữ 5.104 trong 5.177 tin. Trong đó 17,1% tin không khớp kỹ năng nào trong bộ 230 kỹ năng, và bảng kỹ năng thưa 98,15% (task yêu cầu 95–98%). 5.092 tin chưa ai duyệt tay.
- **Hiểu đơn giản:** "thưa" nghĩa là hầu hết ô trong bảng kỹ năng bằng 0 (tin nào cũng chỉ có vài kỹ năng trong 230). Vượt ngưỡng một chút nghĩa là bảng hơi "trống" hơn kế hoạch.
- **Lựa chọn:** A. Chấp nhận như hiện tại. B. Nới bộ lọc để giữ nhiều tin hơn. C. Thêm kỹ năng vào bộ 230 để giảm 17,1% tin không có kỹ năng.
- **Mình nghiêng:** A tạm thời, vì con số này chưa kiểm lại; kiểm trước rồi mới quyết C.
- **Nếu chưa quyết:** giữ A.

## 5. Có dùng model để lấy lại tin bị loại nhầm không? (PRE-15)
- **Chuyện gì:** bộ lọc IT của Tài đã loại 5.409 tin "không phải IT" bằng luật, chưa ai kiểm từng tin. Bạn nói sau này sẽ dùng model để phân loại lại. Nhưng `preprocessing/CLAUDE.md` đang ghi **"không dùng model/LLM"** (quyết định 04/11).
- **Cần quyết:** khi nào bắt đầu, và cho phép dùng model ở bước nào? Dùng model nghĩa là gửi nội dung tin tuyển dụng cho dịch vụ bên ngoài (hoặc chạy model cục bộ) và tốn tiền hoặc tài nguyên.
- **Bước cần trước:** có nhãn tay (xem mục 10) để biết model tốt hơn luật hay không.
- **Nếu chưa quyết:** không làm gì; luật cũ vẫn chạy.

## 6. Lưu dữ liệu trên R2 theo đâu? (GEN-4, GEN-9)
- **Chuyện gì:** bạn đã quyết: giữ `raw/`, `url_ledger/`; trong `silver/` chỉ một file `all.parquet`; `gold/` có `gold_master_jobs.parquet`, `features.parquet`, `matrices/`; xóa `quality/`, `integration/`, `transformation/` và 32 file `staging/`. **Chưa chốt:** các bạn trong nhóm đang đọc/ghi thư mục nào, và `features.parquet` nằm ở đâu (Phát đẩy `curated/preprocessing/features.parquet`, Phúc đọc local `data/curated/...`).
- **Cần bạn:** hỏi nhóm xem ai đang dùng thư mục nào trên R2 trước khi xóa. Mình không xóa gì cho tới lúc bạn đồng ý sau khi chạy thử (dry-run).
- **Nếu chưa quyết:** R2 giữ nguyên; code đã có công cụ chạy thử, chưa chạy thật.

## 7. Cào tin ngoài IT ở TopDev (SCRAPE-18, SCRAPE-15)
- **Chuyện gì:** TopDev trả cả tin ngoài IT (API bỏ qua tham số lọc). Code lọc IT ở bước thu thập lại dùng bộ lọc của bước tiền xử lý (code thu thập "gọi ngược" sang tiền xử lý).
- **Lựa chọn:** A. Bỏ lọc ở thu thập, để bước Clean lọc (cào hơi dư, code gọn). B. Giữ lọc ở thu thập nhưng chuyển bộ lọc sang thư mục dùng chung.
- **Mình nghiêng:** A, vì Clean đã lọc đủ.
- **Nếu chưa quyết:** giữ nguyên.

## 8. Khoảng số cụm K-Means (MINE-4)
- **Chuyện gì:** ba tài liệu ghi ba khoảng thử k khác nhau: task 6–12, checklist 4–14, spec 07 3–15. Code dùng 4–14.
- **Mình nghiêng:** giữ 4–14 (khớp code), sửa hai tài liệu còn lại.
- **Nếu chưa quyết:** code vẫn 4–14.

## 9. Thời gian nghỉ giữa các lần cào (SCRAPE-13)
- **Chuyện gì:** chuẩn dự án là nghỉ 2,0–4,5 giây giữa các request; JobsGO, VietnamWorks, TopDev đang nghỉ ngắn hơn (1–2,5 giây), hai nguồn sau gọi API.
- **Lựa chọn:** A. Nâng cả ba lên chuẩn (an toàn hơn trước bị chặn, cào lâu hơn). B. Ghi ngoại lệ cho nguồn gọi API.
- **Nếu chưa quyết:** giữ nguyên, test báo "lệch chuẩn".

## 10. Nhãn tay (PRE-12) — việc của bạn, không phải quyết định
- Mình đã chuẩn bị file mẫu và bật công cụ gán nhãn (xem `scripts/label_tool.py --web`, http://localhost:8765): 643 tin chờ bạn gán "IT" hoặc "không IT". Gán xong mình đo độ đúng của bộ lọc IT.
- Cần quyết riêng: đo "đúng" như thế nào (ngưỡng ≥ 95% trên bộ nào) — Tài đã để mở câu này, xem PRE-12.

## 11. Việc nhỏ cần "ừ"
- Cài `mlxtend`, `shap`, `hdbscan` vào môi trường Python (F01): mình cần bạn đồng ý vì là cài gói.
- Nhánh `hotfix` local (`83f8432`): giữ hay xóa.
- Đẩy (push) nhánh `sprint/pipeline-delivery` lên GitHub khi nào.
- Thư mục tài liệu của Phát (`docs/preprocessing/encoding/`): giữ chỗ đó hay dời vào `docs/spec/preprocessing/encoding/` (F12).
- PRE-11 (5 câu hỏi A/B cho thầy ở slide cuối): chờ thầy trả lời; không việc nào của mình phụ thuộc trực tiếp.
- PRE-26: dọn 95 file nặng trong `reports/preprocessing/05_encoding` khi nào.

## Phát hiện mới trong lượt này
Chạy lại bước Clean trên raw mới tải về máy (09/11): đầu ra 5.077 tin (VietnamWorks 800), trong khi báo cáo của Hoàng ghi 5.177 (VietnamWorks 900). Chênh 100 tin ở VietnamWorks, chưa biết do đâu (code Clean đã sửa sau, hay raw khác). Ghi vào PRE-16; không đoán nguyên nhân. Mình đã hoàn lại các file báo cáo `reports/preprocessing/01_clean` về bản trong git để không ghi đè số cũ.
