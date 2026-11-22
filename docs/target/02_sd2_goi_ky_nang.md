# SD2 · Gói kỹ năng và kỹ năng hiếm

> Tầng 2: khai phá không giám sát (luật kết hợp). Đề tài và bối cảnh: [00_de_tai.md](00_de_tai.md).

## 1. Bài toán nói đơn giản

Doanh nghiệp hiếm khi tuyển người chỉ biết một kỹ năng. Họ thường tuyển theo **gói**, ví dụ "Java thì kèm Spring Boot, SQL, Docker". SD2 cho máy đọc toàn bộ tin và tự tìm ra những kỹ năng **hay xuất hiện cùng nhau trong một tin**, mạnh hơn mức trùng hợp ngẫu nhiên. Từ đó trả lời câu hỏi "học X thì thường phải biết thêm gì".

SD2 cũng chỉ ra **kỹ năng hiếm**: ít tin đòi, nhưng hễ xuất hiện thì gắn chặt với một gói nào đó hoặc với cấp cao.

Phần này không có nhãn đúng/sai cho trước. Máy chỉ đếm và tìm quy luật, nên gọi là khai phá **không giám sát**.

## 2. Câu hỏi cần trả lời

| Mã | Câu hỏi |
|---|---|
| 2.1 | Với mỗi nhóm nghề, những kỹ năng nào được đòi nhiều nhất (top 15)? Kỹ năng kỹ thuật và kỹ năng mềm, ngoại ngữ xếp hai bảng riêng (spec 07 mục 4) |
| 2.2 | Những gói kỹ năng nào hay đi cùng nhau? Cụ thể là các luật dạng "tin đã đòi A và B thì thường đòi thêm C", kèm độ mạnh của luật. |
| 2.3 | Gói kỹ năng của từng nhóm nghề và từng cấp bậc khác nhau ra sao, ví dụ gói của Intern/Fresher so với gói của Senior trong cùng nghề Web? |
| 2.4 | Kỹ năng nào là **kỹ năng hiếm**? |

Định nghĩa kỹ năng hiếm ở câu 2.4: xuất hiện ở dưới 2% số tin, **và** thỏa ít nhất một điều kiện sau:

- nằm trong một luật có lift ≥ 2;
- có từ 60% số lần xuất hiện trở lên nằm ở tin Senior hoặc Lead/Manager.

Các ngưỡng 2%, lift 2 và 60% (chốt 22/11, L-60).

## 3. Dữ liệu dùng

| Cột | Ghi chú |
|---|---|
| Ma trận kỹ năng multi-hot ở `10_features` (`skill__*`) | Mỗi tin là một "giỏ", mỗi kỹ năng là một "món hàng". Các cột `SKILL_EXCLUDE_COLUMNS` trong `mining/config.py` bị bỏ |
| `job_family`, `seniority` | Để chia tầng ở câu 2.3 và 2.4 |

Tin không có kỹ năng nào thì bỏ khỏi SD2, và ghi rõ số tin bị bỏ. Chất lượng rút kỹ năng hiện còn thấp (PRE-35, PRE-33). Kết quả SD2 chỉ đáng tin khi phần này đạt tiêu chí sạch.

## 4. Cách trả lời

- **2.1:** đếm tỷ lệ tin có từng kỹ năng trong mỗi nhóm nghề, xếp giảm dần.
- **2.2:** dùng thuật toán **FP-Growth** để tìm các tập kỹ năng hay đi cùng nhau, rồi sinh luật A, B ⇒ C. Mỗi luật có 4 chỉ số:
  - **Support:** bao nhiêu phần trăm tin có đủ cả A, B và C. Cho biết luật phổ biến tới đâu.
  - **Confidence:** trong các tin có A và B, bao nhiêu phần trăm có thêm C. Cho biết "đã học A, B thì khả năng bị đòi C" là bao nhiêu.
  - **Lift:** confidence chia cho tỷ lệ chung của C. Lift lớn hơn 1 nghĩa là A, B thật sự kéo C theo, không phải do C vốn phổ biến.
  - **Conviction:** luật sai ít đến mức nào. Càng cao thì luật càng ít ngoại lệ.

  Ngưỡng hiện tại lấy từ `mining/config.py`: support ≥ 5% cho toàn bộ dữ liệu, ≥ 2% cho từng nhóm nghề; confidence ≥ 0,60; lift ≥ 1,20.
- **2.3:** chạy lại FP-Growth riêng cho từng nhóm nghề và từng cấp bậc (`mine_stratified_rules`), dùng ngưỡng support 2%. Sau đó so các luật giữa hai nhóm: luật nào chỉ có ở nhóm này, luật nào có ở cả hai.
- **2.4:** lọc theo định nghĩa ở mục 2. Mỗi kỹ năng hiếm phải ghi kèm số lần xuất hiện, luật mạnh nhất mà nó nằm trong, và tỷ lệ tin cấp cao.

## 5. Đầu ra

| Đầu ra | Dạng |
|---|---|
| Top kỹ năng theo nghề (2.1) | Bảng: nghề, kỹ năng, số tin, tỷ lệ |
| Danh sách luật (2.2, 2.3) | Bảng: phạm vi (toàn bộ / nghề / cấp), A, B ⇒ C, support, confidence, lift, conviction. Code hiện có `format_rules` trong `mining/association.py` |
| Danh sách kỹ năng hiếm (2.4) | Bảng: kỹ năng, số tin, lý do hiếm (luật hay cấp cao) |
| Biểu đồ | Mạng kỹ năng: nút là kỹ năng, cạnh là luật, độ dày cạnh theo lift. Heatmap kỹ năng × nghề |

## 6. Cách biết đã trả lời đúng

- **Sanity check bằng các cặp hiển nhiên** (`mining/sanity.py`): React ⇒ JavaScript/TypeScript và Flutter ⇒ Dart phải có confidence cao. Hiện hai cặp này đang fail (MINE-1). Nếu sau khi dữ liệu đạt tiêu chí sạch mà vẫn fail, phải tìm nguyên nhân trước khi dùng kết quả.
- Mọi luật được báo cáo phải có lift ≥ 1,20 và đủ ngưỡng support của phạm vi đó.
- Kiểm tay 20 luật mạnh nhất: luật phải hợp lý với người làm nghề. Luật nào vô nghĩa thì ghi lại và tìm nguyên nhân, thường do rút kỹ năng sai.
- Chạy lại với ngưỡng support thấp hơn và cao hơn một bậc: các luật mạnh nhất không được thay đổi lớn.

## 7. Những gì không trả lời được

- **Thứ tự học:** luật chỉ nói A và C hay đi cùng nhau, không nói học cái nào trước. Thứ tự học do SD5 suy ra, kèm giả định riêng.
- **Quan hệ nhân quả:** doanh nghiệp đòi C không phải *vì* đã đòi A.
- **Kỹ năng ngoài từ điển:** kỹ năng không có trong từ điển chuẩn, hoặc xuất hiện dưới ngưỡng `min_df` 15 tin, sẽ không được thấy.
- **Mức thành thạo:** dữ liệu chỉ có kỹ năng được nêu tên, không biết doanh nghiệp đòi "biết qua" hay "thành thạo".

## 8. Code và spec liên quan

- Code: `mining/association.py` (`mine_rules`, `mine_stratified_rules`, `pair_stats`), `mining/sanity.py`, các ngưỡng trong `mining/config.py`.
- Spec: `docs/spec/07_mining_spec.md` mục 3.2 (M2), `docs/spec/08_evaluation_spec.md` mục 3.2.
- Chất lượng dữ liệu cần cho SD2: PRE-35, PRE-33 (đo kỹ năng so với nhãn gold) trong `docs/KNOWN_ISSUED.md`.
