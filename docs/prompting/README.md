# docs/prompting: prompt cho agent theo từng phase

Mỗi file là một prompt dán cho agent (Claude Code) để làm một phase. Prompt **trỏ về đặc tả**, không chép lại: đặc tả là luật, prompt là cách làm.

## Đặc tả hiện hành

Từ 17/11/2026, đặc tả các phase nằm trong bộ spec chính, không còn file đặc tả riêng cho từng phase:

| Phase | Prompt | Đặc tả hiện hành | Trạng thái |
|---|---|---|---|
| PH0 nền hạ tầng | `PH0_nen_ha_tang.md` | `docs/spec/05_preprocessing_spec.md` mục 2 | Đã làm |
| PH1 gold và profiling | `PH1_gold_va_profiling.md` | spec 05 mục 3.0 (bước 00), mục 2.2 (bộ gold) | Đã làm |
| PH2 schema và làm sạch ký tự | `PH2_schema_va_lam_sach_ky_tu.md` | spec 05 mục 3.3 (bước 02), 3.4 (T6) | Đã làm |
| PH3 lọc phạm vi và ngôn ngữ | `PH3_loc_pham_vi_va_ngon_ngu.md` | spec 05 mục 3.1 (bước 01), 3.4 (T6) | Đã làm |
| PH4 khử trùng 3 tầng | `PH4_khu_trung_3_tang_minhash.md` | spec 05 mục 3.2 (bước 01b) | Đã làm |
| PH5 dịch EN→VI | `PH5_dich_anh_viet_envit5.md` | spec 05 mục 3.4 (T6b) | Đã làm, còn PRE-34 |
| PH6 chuẩn hóa trường | `PH6_chuan_hoa_truong.md` | spec 05 mục 3.5 (bước 04) | Đã làm |
| PH7 thiếu và ngoại lai | `PH7_thieu_va_ngoai_lai.md` | spec 05 mục 3.5 (luật M), mục 4.3 | Đã làm |
| PH8 section, kỹ năng, tách từ | `PH8_tach_section_ky_nang_tach_tu.md` | `docs/spec/06_processing_spec.md` | Đã làm |
| PH9 nối pipeline, nghiệm thu | `PH9_noi_pipeline_nghiem_thu.md` | spec 05 mục 2, spec 06 | Đã làm |

Các prompt PH0–PH9 viết ngày 10/11, khi đặc tả còn nằm ở `docs/spec/preprocessing/spec/`. Các file đó đã gộp vào spec 05 và 06 và bị xóa ngày 17/11. Đường dẫn cũ trong thân prompt chỉ còn giá trị lịch sử; đọc spec 05 theo bảng trên.

## Khuôn prompt

```text
1. Ngữ cảnh       vì sao làm, đọc file nào trước, số liệu hiện tại
2. Việc cần sửa   Input (đường dẫn, dạng) → Output (đường dẫn, cột, báo cáo)
3. Pseudo code    các bước theo thứ tự, đủ để review trước khi viết code thật
4. Ràng buộc      ranh giới bước, luật an toàn của repo, việc KHÔNG làm
5. Ví dụ          vài dòng trước → sau, đúng như test sẽ kiểm
6. Cách review    bạn và agent kiểm gì, bằng lệnh nào, ngưỡng đạt
```

## Quy trình mỗi phase

1. Bạn duyệt đặc tả (mục tương ứng trong spec 05, 06, 07).
2. Bạn duyệt prompt, chủ yếu là pseudo code và ví dụ.
3. Agent viết test trước theo mục "Ví dụ", rồi viết code.
4. Agent chạy `--dry-run` trên `glints` rồi trên cả 8 nguồn, gửi bảng số.
5. Cùng review theo mục 6 của prompt. Đạt thì chạy thật, ghi `docs/issue_log.md`, xóa mục tương ứng trong `docs/KNOWN_ISSUED.md`.

## Các cách review dùng chung

| Cách | Làm thế nào | Dùng khi |
|---|---|---|
| Đối chiếu số | `input.rows = output.rows + bỏ`; so với lần chạy trước (report `_all.json`); lệch > 5% phải giải thích | mọi phase |
| Xem mẫu | Lấy ngẫu nhiên với seed cố định 10–50 dòng bị bỏ hoặc bị sửa và 10 dòng giữ nguyên; bạn gán nhãn tay đúng/sai | luật có phán đoán (lọc IT, nhóm nghề, cấp bậc) |
| Trước → sau | Đặt cột `raw_*` cạnh cột mới cho 20 dòng | parse lương, ngày, kinh nghiệm |
| Chạy nhỏ trước | `glints` → một nguồn lớn → cả 8 | mọi phase |
| Test từng luật | Mỗi luật một test, dữ liệu nhỏ trong `tmp_path`; `make test` xanh | mọi phase |
| Xem trên trang | Trang `/preprocessing` ở 1440px và 390px; số trên trang khớp file JSON | mọi phase có report |
| Gán nhãn IT theo nguồn | `data/preprocessing/review/it_<nguồn>.csv`; bạn điền `nhan_tay`; đo độ đúng luật, tìm nguyên nhân (crawler / nguồn / phân loại) | bước 01 |
| Kiểm bản dịch | 50 JD dịch (`scripts/build_translation_review_sample.py`); kỹ năng và số liệu không bị đổi | bước 03 T6b |
| Hai lần chạy giống nhau | Chạy `--dry-run` hai lần, báo cáo giống nhau (trừ `generated_at`) | mọi phase |

## Luật chung cho mọi prompt

- Không commit. Không ghi lên R2: đẩy lên R2 là việc riêng, chạy thử trước, bạn đồng ý mới chạy.
- Config chỉ trong `.env`, không in giá trị.
- Raw bất biến: không sửa `data/<nguồn>/raw/`.
- Không bật Airflow scheduler.
- Không dùng model để phân loại hay chuẩn hóa. Chỉ có fastText `lid.176` (ngôn ngữ) và `VietAI/envit5-translation` (dịch), cả hai chạy local (spec 05 mục 2.5).
