# SD5 · Nên học kỹ năng gì, theo thứ tự nào

> Tầng 3: tổng hợp kết quả SD1, SD2 và model của SD4. Đề tài và bối cảnh: [00_de_tai.md](00_de_tai.md).

## 1. Bài toán nói đơn giản

Một sinh viên muốn vào nghề Web, Data/AI hay Tester thường hỏi: "Em nên học gì trước, học gì sau, cái gì để sau cũng được?" SD5 trả lời câu này **chỉ bằng dữ liệu tin tuyển dụng**, gộp ba thứ đã có:

- **Doanh nghiệp đòi gì ở người mới.** Đây là tỷ lệ kỹ năng trong tin Intern/Fresher và Junior, lấy từ SD1 và SD2.
- **Kỹ năng nào kéo theo kỹ năng nào.** Lấy từ các luật của SD2.
- **Kỹ năng nào đáng tiền.** Lấy từ model SD4.

Kết quả là, với mỗi nghề, một **danh sách kỹ năng ưu tiên có điểm** và một **thứ tự học**. Mỗi bước đều kèm số liệu dẫn chứng. SD5 không đưa ra lời khuyên nào mà không chỉ được về số liệu.

## 2. Câu hỏi cần trả lời

Áp dụng cho các nhóm nghề có ít nhất 30 tin cho người mới (Intern/Fresher, Junior).

Mọi ngưỡng số trong file này (30 tin, 5%, gấp 3 lần, 70%, 10 điểm phần trăm) là đề xuất, chờ chốt ở PRE-36.

| Mã | Câu hỏi |
|---|---|
| 5.1 | Với nghề X, người mới nên ưu tiên những kỹ năng nào, xếp theo điểm ưu tiên? Kỹ năng kỹ thuật và kỹ năng mềm, ngoại ngữ xếp hai danh sách riêng (spec 07 mục 4) |
| 5.2 | Nên học theo thứ tự nào: kỹ năng nào là nền, kỹ năng nào học sau vì thường đi kèm với kỹ năng nền? |
| 5.3 | Kỹ năng nào **chưa nên đầu tư sớm**, vì hầu như chỉ xuất hiện ở tin Senior hoặc Lead/Manager? |
| 5.4 | Nếu học đủ top N kỹ năng đề xuất, người mới đáp ứng được bao nhiêu phần trăm số tin dành cho người mới của nghề đó? |

## 3. Dữ liệu dùng

| Đầu vào | Lấy từ |
|---|---|
| Tỷ lệ tin người mới của nghề X có kỹ năng k: `demand(k)` | Ma trận kỹ năng, lọc `job_family` = X và `seniority` ∈ {Intern/Fresher, Junior} (SD1, SD2) |
| Luật A ⇒ B của nghề X và độ tin cậy | SD2, chạy theo từng nghề (`mine_stratified_rules`) |
| Mức cộng lương của kỹ năng k: `premium(k)` | SD4, giá trị kỹ năng (triệu VNĐ, hoặc bậc khung nếu SD4 dùng phương án B) |
| Tỷ lệ kỹ năng k xuất hiện ở tin Senior/Lead của nghề X | Ma trận kỹ năng, lọc theo cấp |

## 4. Cách trả lời

- **5.1, điểm ưu tiên:**

  `điểm(k) = demand(k) × (1 + premium_chuẩn_hóa(k))`

  - `premium_chuẩn_hóa(k)` là mức cộng lương của k chia cho mức cộng lớn nhất trong nghề X. Giá trị nằm trong khoảng [−1, 1].
  - Như vậy điểm chủ yếu dựa vào **nhu cầu thật ở người mới**. Lương chỉ cộng hoặc trừ tối đa gấp đôi.
  - Kỹ năng mà SD4 không định giá được (ít dữ liệu) thì lấy `premium` = 0.
  - Chỉ xếp hạng kỹ năng có `demand(k)` ≥ 5%.
- **5.2, thứ tự học:** xếp các kỹ năng trong top ưu tiên thành các bậc.
  - **Bậc 1 (nền):** kỹ năng có `demand` cao nhất và không phải là vế sau (⇒ B) của một luật mạnh nào trong nhóm top. Luật mạnh là luật có confidence ≥ 0,60 và lift ≥ 1,20.
  - **Bậc 2 trở đi:** kỹ năng B đứng sau A nếu có luật A ⇒ B mạnh, tức là "tin đã đòi A thì thường đòi thêm B".
  - Nếu hai kỹ năng không có luật nào nối với nhau thì xếp theo điểm ưu tiên.
  - Giả định cần ghi rõ: "hay đi kèm" được dùng **thay cho** "học sau". Dữ liệu không chứng minh được thứ tự học, nên mỗi bước phải ghi luật dùng để suy ra.
- **5.3, chưa nên đầu tư sớm:** kỹ năng mà, trong nghề X, tỷ lệ xuất hiện ở tin Senior/Lead **gấp từ 3 lần trở lên** so với ở tin người mới, và `demand(k)` ở người mới dưới 5%.
- **5.4, độ phủ (coverage@N):** với N = 5, 10, 15, tính tỷ lệ tin người mới của nghề X mà top N kỹ năng đề xuất đáp ứng được **ít nhất 70%** số kỹ năng tin đó đòi.

## 5. Đầu ra

| Đầu ra | Dạng |
|---|---|
| Danh sách ưu tiên (5.1) | Bảng theo nghề: kỹ năng, `demand`, `premium`, điểm, hạng |
| Lộ trình (5.2) | Bảng theo nghề: bậc, kỹ năng, luật dẫn chứng (A ⇒ B, confidence, lift) |
| Danh sách để sau (5.3) | Bảng theo nghề: kỹ năng, tỷ lệ ở tin Senior/Lead, tỷ lệ ở tin người mới |
| Độ phủ (5.4) | Bảng theo nghề: N, coverage@N |
| Trình bày cho sinh viên | Mỗi nghề một trang. Ở mỗi bậc, mỗi kỹ năng có một câu giải thích kèm số, ví dụ "62% tin Web cho người mới đòi JavaScript" |

## 6. Cách biết đã trả lời đúng

- **Độ phủ:** coverage@10 của mỗi nghề được báo cáo phải cao hơn baseline "top 10 kỹ năng phổ biến nhất của toàn thị trường". Nếu không cao hơn, lộ trình theo nghề không mang thêm giá trị nào.
- **Kiểm tra tách tập:** tính điểm trên 80% số tin người mới, rồi đo coverage@N trên 20% còn lại. Kết quả không được thấp hơn quá 10 điểm phần trăm so với khi đo trên chính tập dùng để tính điểm.
- **Truy được nguồn:** mọi kỹ năng trong lộ trình phải truy được về số `demand`, luật SD2 và giá trị SD4 tương ứng.
- **Đọc tay:** người làm nghề đọc lộ trình của 2 nghề. Bước nào ngược lẽ thường (ví dụ Docker đứng trước ngôn ngữ lập trình) thì ghi lại và tìm nguyên nhân.

## 7. Những gì không trả lời được

- **Sinh viên còn thiếu gì:** dữ liệu không có thông tin về người học hay chương trình đào tạo. SD5 chỉ nói thị trường đòi gì, không đo khoảng cách của một người cụ thể.
- **Thứ tự học sư phạm:** thứ tự ở 5.2 suy ra từ việc kỹ năng hay đi kèm nhau trong tin, không phải từ cách dạy học.
- **Kỹ năng mai sau cần:** không có chuỗi thời gian dài, nên không dự báo được kỹ năng sẽ hot.
- **Nghề có ít hơn 30 tin cho người mới:** chỉ ghi "ít dữ liệu", không có lộ trình.

## 8. Code và spec liên quan

- Phụ thuộc: [01_sd1_buc_tranh_thi_truong.md](01_sd1_buc_tranh_thi_truong.md), [02_sd2_goi_ky_nang.md](02_sd2_goi_ky_nang.md), [04_sd4_gia_tri_ky_nang.md](04_sd4_gia_tri_ky_nang.md).
- Code: hiện **chưa có**. Khi làm sẽ đặt trong `mining/` và dùng lại `mine_stratified_rules`, `skill_values_from_shap`.
- Spec: `docs/spec/07_mining_spec.md` mục 3.6 (M6), `docs/spec/08_evaluation_spec.md` mục 3.5 (đã bỏ "Skill Gap Matrix" ngày 17/11).
- Chất lượng dữ liệu cần cho SD5: PRE-35 (số tin người mới, kiểm lại khoảng 317 tin itviec ghi "0,8 năm") trong `docs/KNOWN_ISSUED.md`.
