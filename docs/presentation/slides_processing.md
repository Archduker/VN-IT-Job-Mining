# Slide: Giai đoạn 3 – Processing (Feature Engineering + Encoding)

> Số liệu lấy từ `reports/preprocessing/*` và `data/processing/*` (chạy thật, 4.671 tin). Chỗ ghi [CHỜ] là số chưa có vì bước e5 đang chạy.

---

## Slide 1. Processing làm gì, nằm ở đâu

- Vào: 4.671 tin IT đã sạch, đã khử trùng, đã chuẩn hóa (đầu ra Pre-processing).
- Ra: bảng đặc trưng dạng số để Mining (phân cụm, luật kết hợp, bất thường, giảm chiều) dùng thẳng.
- 4 việc theo quy trình chuẩn: Selection → Extraction → Transformation → Construction, kèm Encoding.
- Tiêu chí chính: Consistency, Completeness. Số dòng giữ nguyên 4.671 qua mọi bước.

## Slide 2. Sơ đồ luồng dữ liệu

```
04 chuẩn hóa (103 cột)
 ├─ 07 tách section/bullet ─► 114.008 bullet (mo_ta 39.153 · yeu_cau 35.152 · phuc_loi 39.703)
 │    ├─ 08 kỹ năng (230 kỹ năng, 32.637 dòng JD–kỹ năng)
 │    ├─ 09 tách từ + stopword ─► 12_tfidf  (4.671 × 20.000, thưa)
 │    └─ 12_e5 embedding bullet ─► vector 768 chiều ─► vector từng JD
 └─ 10_features: rời rạc hóa → chọn → xây → mã hóa ─► 4.671 × 249 (toàn số)
```

## Slide 3. Bốn bước Feature Engineering

| Bước | Việc làm | Kết quả |
|---|---|---|
| Transformation (10) | Chia khoảng lương (10/20/35/60 triệu) và kinh nghiệm (<1, 1–3, 3–5, >5 năm); chưa rõ = -1 | `salary_bin_range`, `salary_bin_eqfreq5`, `exp_bin` |
| Selection (10b) | Kỹ năng xuất hiện ở dưới 15 tin gom vào `other_skill` | 171 cột kỹ năng, không mất tin nào |
| Construction (10c) | Tạo đặc trưng mới từ cột có sẵn | `n_skills`, `n_required`, `required_ratio`, `n_tokens`, `n_benefits`, `salary_mid`, `salary_range_ratio` |
| Extraction (12) | Biểu diễn văn bản JD thành vector | TF-IDF (unigram + bigram) và e5 embedding |

Thiếu thì để NaN, không điền số bịa (ví dụ lương thỏa thuận → `salary_status__unknown`).

## Slide 4. Encoding (đối chiếu đặc tả P5)

| Mục | Cách mã hóa | Ghi chú |
|---|---|---|
| Cấp bậc | thứ tự 0–4, chưa rõ = -1 | Intern/Fresher … Lead/Manager |
| Nhóm nghề | one-hot 16 nhóm + Other | Other 707/4.671 = 15,1% |
| Sàn, hình thức làm việc | one-hot | |
| Loại hình làm việc | one-hot theo luật từ khóa | 317 tin `unknown` |
| Tỉnh | multi-hot top 10 + other/unknown | `loc_remote`, `loc_ngoai_vn` là cờ riêng; 102 tin chưa rõ tỉnh |
| Kỹ năng | multi-hot 171 cột | |
| Số (lương log, kinh nghiệm, số người tuyển) | giữ số, thêm cột `__missing` | |
| Thời gian | tháng đăng, số ngày còn đến hạn nộp | tính từ ngày cào |

Không áp dụng: `it_status` (cả 4.671 tin đều là `it`, cột hằng), `*_prob` (bảng 04 không có).

## Slide 5. Extraction bằng văn bản

- TF-IDF: bigram nối bằng `|`, `min_df=5`, tối đa 20.000 từ, mỗi dòng chuẩn hóa L2.
- e5 (`multilingual-e5-base`): mỗi bullet một vector 768 chiều, tiền tố `passage: `, fp16 trên GPU 4 GB, cache theo sha1 của văn bản nên chạy lại không tính lại.
- Vector JD = trung bình mọi bullet, kèm vector riêng cho 3 section (mô tả, yêu cầu, phúc lợi). JD thiếu section thì vector 0, không bịa.
- Số bullet được embedding (sau khử trùng văn bản): 88.821 trên 114.008 bullet.

## Slide 6. Kiểm chứng

- Tests: 580 qua, 1 bỏ qua; 16 test riêng cho bước 10–12.
- Bảo toàn dòng: 4.671 vào, 4.671 ra ở mọi bước.
- Bộ nhãn vàng 100 JD: section đúng 84,5% (glints 48%), recall phúc lợi 0,60, F1 kỹ năng 0,27.
- e5 (xong 04:13): `bullet_emb` 114.008 × 768, `job_emb` 4.671 JD, không JD nào vector 0; test 580 qua, 1 bỏ qua.

## Slide 7. Hạn chế đã biết (nói thẳng)

- Tách section của glints chỉ đúng 48%.
- F1 kỹ năng thấp (0,27); chưa tìm ra nguyên nhân chắc chắn.
- Dịch EN→VI còn 222 tin thất bại.
- Nhóm nghề Other còn 15,1%.
- Chưa phân loại bullet theo loại (không có nhãn vàng để đo).
- Chọn đặc trưng mới dùng `min_df`, chưa có tiêu chí khác.

## Slide 8. Bước tiếp theo

- Xong e5 → kiểm vector, in vài cặp bullet gần nhau để xem bằng mắt.
- Sau đó sang Mining (không thuộc phần Processing).

---

## Phụ lục: Mining (chạy thật 11/11, 4.671 tin; hình: `clusters_3d.html`, `k_selection.html`, `mining_input.html`)

Nhóm nghề: 10 nhóm + Other (Web 1.853, Bridge 533, Data/AI 430, Tester 429, DevOps/Cloud 258, Security 254, Design 78, Game 61, IoT 38, Mobile 30; Other 707).

| Thuật toán | Kết quả |
|---|---|
| K-Means k=10 (kỹ năng .5 + e5 .5) | Silhouette 0,1015, Davies-Bouldin 2,49; ARI với nhóm nghề 0,071 (3.964 tin khác Other) |
| PCA 3D | giữ 18,9% phương sai |
| FP-Growth | 13.514 luật (26 vĩ mô) |
| Bất thường (GLOSH, Isolation Forest) | 282 tin (6,04%) |

Chọn k: Elbow không có khuỷu gãy rõ, Silhouette không có đỉnh trong k = 2–20 (tăng dần đến 0,12); k=10 do người dùng chốt. Cụm chồng lấn nhiều (Silhouette thấp, dữ liệu xáo ngẫu nhiên khoảng 0,04); cụm 1 chứa 292/293 tin không có kỹ năng. Nói thẳng trong slide, không chỉnh số.
