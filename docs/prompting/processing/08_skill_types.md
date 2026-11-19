# Prompt 08b: Nhãn tool / concept cho skills_v2 (K-tool)

> Đặc tả: [`docs/spec/processing/08_skills.md`](../../spec/processing/08_skills.md) K8.17; yêu cầu dữ liệu [`docs/target/06_yeu_cau_du_lieu.md`](../../target/06_yeu_cau_du_lieu.md) mục 2, 4.
> **Trạng thái:** viết 19/11/2026. Đặc tả và kế hoạch được người dùng duyệt cùng P0 ("oke i approve and countinue"). Lô nhãn chờ người dùng duyệt.
> Sau việc này: P2 (bước 08 ghi `type`, hàm `skill_view`, đo T1–T6).

## 1. Ngữ cảnh

**Đọc trước:** `docs/target/06_yeu_cau_du_lieu.md`; đặc tả 08 mục 2.3; `scripts/build_skills_v2.py`; `processing/extraction/skills.py`.

**Vì sao làm** (số đo 19/11): bước 08 trích trung vị 25 kỹ năng/tin, lẫn khái niệm chung (`information_security` ở 35% tin Web). Trên tin trùng với dữ liệu ngoài `vietnam-it-job-trends`, chỉ 36% kỹ năng của mình nằm trong `tech_stack ∪ keywords` của họ; lọc theo phần JD làm mất 30% công cụ thật. Người dùng chốt K-tool: lọc theo **loại** kỹ năng.

**Quyết định của người dùng:** "đún rồi tui đang hớng cái đó" (K-core theo loại); "oke được đó" (kế hoạch P0–P4, nhãn `tool`/`concept` theo lô có duyệt); không tự quyết ca ranh giới.

## 2. Việc cần sửa

**Input:** `processing/dictionaries/skills_v2.json`; `data/processing/08_skills/job_skills.parquet` (DF); Silver (ghép URL); `data/external/vnjt/step07.jsonl` (gitignore).

**Output:**

- `processing/dictionaries/skills_v2_decisions/types_t01.json` … `types_t10.json` (1.407 kỹ năng kỹ thuật DF ≥ 5, lô 150).
- `processing/dictionaries/skills_v2_decisions/types_claude.txt`: Claude đọc lại đề xuất theo luật, mỗi dòng `tool|con|hoi:<lớp> slug…`.
- `docs/presentation/processing_steps/skill_types.html`: trang duyệt.
- `skills_v2.json` có trường `type` (null tới khi lô được duyệt), `_meta.types`; version 2.1.0 khi có nhãn.

## 3. Pseudo code

```
ev = với mỗi tin trùng (cùng sàn, mã cuối URL, tiêu đề ≥ 0,5): slug của mình nằm ở tech_stack hay keywords của họ
với mỗi kỹ năng kỹ thuật DF ≥ 5:
    de_xuat = bằng chứng (≥ 5 tin; tỷ lệ tech_stack ≥ 0,7 → tool, ≤ 0,3 → concept)
              ngược nhóm (GROUP_PRIOR) → hoi; không đủ bằng chứng → theo nhóm; nhóm ranh giới → hoi
    nếu slug có trong types_claude.txt → de_xuat, lop_hoi theo Claude
ghi lô (không ghi đè lô đã có); dựng trang duyệt
build_skills_v2: lô có _meta.approved → type = quyet_dinh | approved.lop_hoi[lop] | de_xuat; còn hoi → lỗi
```

## 4. Ràng buộc

- Không dùng model để gán nhãn; dữ liệu ngoài chỉ là bằng chứng hiển thị, không trộn vào từ điển, không commit.
- Ca ranh giới (chuẩn, chứng chỉ, bộ văn phòng) hỏi người dùng theo lớp.
- Kỹ năng chưa có nhãn duyệt có `type = null`, không vào K-tool.
- Dựng lại từ điển không được đổi trường nào khác ngoài `type` (so trước và sau).

## 5. Ví dụ (thành test)

| Đầu vào | Kết quả mong đợi |
|---|---|
| Lô duyệt có `python: tool`, lô chưa duyệt có `docker: tool` | Chỉ `python` có `type` |
| `rest_api` `de_xuat = hoi`, lớp `chuan`, duyệt `lop_hoi: {chuan: concept}` | `concept` |
| `ccna` lớp `chung_chi` chưa chốt | Lỗi "chưa có nhãn" |
| `kafka` kỹ thuật không có trong lô; `communication` soft | Cả hai `type = null` |
| `types_claude.txt` có một slug ở hai dòng | Lỗi |
| Lệnh `n=C#  # ghi chú` | Tên "C#" (L-52) |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_skills_v2.py -q` | Xanh |
| Dựng lại không đổi gì khác | So `skills_v2.json` trước/sau bỏ `type` | Chỉ thêm `type` (và tên C#) |
| Trang duyệt | `skill_types.html` 1100px, 390px | Không tràn ngang |
| Người dùng | Đọc câu hỏi 3 lớp và các lô | Duyệt từng lô |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1–2 | Duyệt đặc tả, prompt | 19/11 | Người dùng duyệt kế hoạch P0–P4 và tài liệu yêu cầu dữ liệu ("oke i approve and countinue"); ngưỡng T1–T6 chốt | 8deaa45 |
| 3 | Test rồi code | 19/11 | `scripts/_vnjt.py` (ghép tin: chỉ so mã thì 53/470 cặp itviec sai tiêu đề, nên thêm tiêu đề ≥ 0,5 → 1.606 tin), `scripts/propose_skill_types.py`, `build_skills_v2.load_types/attach_types`; 6 test mới, 18 test qua. Sửa L-52 (C#) | (commit này) |
| 4 | Đề xuất | 19/11 | Luật: tool 467, concept 692, hỏi 248. Claude đọc hết 10 lô, ghi `types_claude.txt`: tool 532, concept 758, hỏi 117 (chuan 67, chung_chi 48, office 2). Ví dụ sửa: Linux, Windows, Android, iOS, Figma, Photoshop → tool; database, ERP, NoSQL, debugging, data analysis → concept | (commit này) |
| — | Duyệt lô | 19/11 | Người dùng: "oke continue" → duyệt 10 lô, lớp `chuan`, `chung_chi` → concept, `office` → tool. skills_v2 2.1.0: tool 534, concept 873 | 4e3e67a |
| — | P2: bước 08 ghi `type` | 19/11 | `extract_skills` thêm `type`; `skill_view`; report thêm `rows_by_type`. Chạy lại 07/08 trên bảng 04: cùng 111.128 cặp như trước (chỉ thêm cột). `scripts/eval_skill_views.py`: K-tool đạt T1–T4, T5 0,85, T6 0,69 (xem `docs/target/06_yeu_cau_du_lieu.md` mục 4) | (commit này) |
| — | Người dùng xem số P2 | 19/11 | "oke continue": chấp nhận T5/T6; bỏ alias `grid` (b007) và `ASP` (b010) thành not_skill; `min_df` 15 cho ba khối bước 10. Chạy lại 08: 111.116 dòng, K-tool 533 | (commit này) |
