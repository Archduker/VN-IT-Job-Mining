# Kiểm tra input thật và khả năng tạo P4 — 08/11/2026

## Kết luận

Chưa tạo P4. Không có input P2/P3 Parquet chuẩn trên máy và chưa xác minh đầy đủ nguồn gốc ba JSON legacy. Không tải/sync R2, không chạy pipeline ghi dữ liệu, không sửa source P3/P4/P5. Những output và thay đổi có sẵn trong worktree được giữ nguyên.

## Bằng chứng local

SHA-256 được tính từ toàn bộ bytes của từng file; số dòng là số record JSON, không phải dòng vật lý.

| File (tương đối từ repo) | Bytes | Records | Trường top-level | SHA-256 |
|---|---:|---:|---:|---|
| `data/integration/integrated_flat_all_sources.json` | 3136731 | 931 | 37 | `b518f6aa69f6a3bf0d0e4fe5b495a69b6be8b779efce1e41299da668dc428de2` |
| `data/transformation/transformed_flat_all_sources.json` | 5218580 | 931 | 84 | `f3260ccbde23ada7aef798ab3edb3325b00d349944bafc52c743de4110c3c84c` |
| `data/staging/staging_normalized_all_sources.json` | 6226141 | 931 | 113 | `b490a8f02185ec01ec550da97ad7662164925263a98f168e85be6a3c1958d33d` |

Cả ba là JSON array of objects; mỗi file có 931 ID không rỗng và không trùng. Tập ID của ba file giống nhau. `source_platform` của toàn bộ records là `vietnamworks`. Có `source_url`, `source_job_id`, `crawled_at`; đây là metadata hỗ trợ truy vết, không phải chứng nhận nguồn gốc độc lập.

Schema legacy chính: ID/source/url/title là string; `raw_description_text`, `raw_requirements_text` là string; `skills_list`, `working_locations` là list; `auxiliary_features` là dict. Transformation có numeric/null `salary_min_vnd`, `salary_max_vnd`, `min_experience_years`; staging có `standardized_seniority`, `standardized_job_family`, `primary_city` là string, `log_salary_max` float/null, `hard_skills`, `soft_skills`, `domain_skills` là list. Đây là kiểu runtime JSON, không phải Arrow schema.

Staging thiếu các cột P5: `exp_min_years`, `exp_max_years`, `is_outlier_salary`, `job_family`, `locations`, `log_salary_min`, `seniority`, `skills_std`. Vì vậy không thể đổi đuôi JSON thành Parquet và coi là P4 chuẩn.

### Nguồn gốc và giới hạn xác minh

Audit cũ `logs/audit/RUN_20261027T172150Z_deff14c_vwonly_reports/reports/normalization/normalization_diff_visual_report.md` chứa cùng ID `vietnamworks_2111943`, URL và tiêu đề với record local. Đây là bằng chứng liên hệ một record với pipeline legacy, chưa chứng minh toàn bộ 931 records hoặc tính đúng nội dung. Không tìm thấy raw JSON trong `data/` để đối chiếu ngược. Không có bằng chứng checksum nguồn/sync gắn với ba checksum trên trong các báo cáo đã kiểm tra. Phân loại: dữ liệu legacy có metadata và dấu vết lịch sử, **chưa xác minh đầy đủ là input thật chuẩn cho pipeline hiện hành**.

Ba file không có record với `is_imputed_by_genai` truthy. Điều này không chứng minh toàn bộ lịch sử xử lý không dùng AI.

`reports/preprocessing/02_integration/_all.json`, `03_transformation/_all.json`, `04_normalization/_all.json` ghi mode applied, code_version `7dee2a4`, 5177 input/output records và conservation true. Tuy nhiên, cả ba file `data/preprocessing/<step>/all.parquet` tương ứng đều vắng mặt. Báo cáo lịch sử không chứng minh dữ liệu hiện diện; không gán con số 5177 cho ba JSON 931 records.

## R2: vị trí theo code, chưa xác minh object tồn tại

`preprocessing/common/r2_export.py` định nghĩa Silver `staging/<source>/preprocessing/<step>.parquet`, tách theo source. Prefix cần xem xét là:

- `staging/<source>/preprocessing/04_normalization.parquet`: ưu tiên lấy input đã chuẩn hóa trực tiếp cho P5.
- Nếu P4 chưa có: `staging/<source>/preprocessing/03_transformation.parquet` để chạy P4.
- Nếu P3 chưa có: `staging/<source>/preprocessing/02_integration.parquet` để chạy P3 rồi P4.

`<source>` là một trong `topcv`, `topdev`, `vietnamworks`, `careerviet`, `vieclam24h`, `itviec`, `glints`, `jobsgo`. Cần lấy đủ các source của snapshot được nhóm xác nhận, kiểm tra metadata/checksum và gộp thành file local chuẩn. Không mặc định snapshot các nguồn cùng phiên bản chỉ vì cùng tên object.

Gold mapping hiện có trong code: `curated/preprocessing/features.parquet`, `skill_cooccurrence.parquet`, `encoding_dictionary.json`. Script `scripts/sync_cloud_lakehouse.py` dùng cấu hình R2 chung tại `collection/common/r2_storage.py`, load `.env`; lần kiểm tra này không đọc/in credentials và không gọi S3 API. Bucket/object thực tế chưa được xác minh qua cloud. Không coi key do code định nghĩa là bằng chứng object tồn tại.

## P3–P4 và canonicalize_skills

Entrypoint được hỗ trợ: `scripts/run_preprocessing.py --step transformation` và `--step normalization` (thêm `--dry-run` để tránh ghi dataset, nhưng vẫn ghi reports). Không có khối main trong hai module `run.py`; chạy trực tiếp file không tương đương gọi hàm `run()`.

P3 đọc `data/preprocessing/02_integration/all.parquet`, tạo `03_transformation/all.parquet`. P4 đọc output đó, tạo `04_normalization/all.parquet`. P3 sinh `description_clean`, `requirements_clean`, `skills_clean`, `locations`, experience, ngày và headcount. P4 sinh `skills_std`, seniority/job_family, flags, capped salary và log salary. Về mặt source, tổ hợp này có các trường P5 cần; Arrow schema và chất lượng chỉ xác nhận được sau khi có dataset thật.

Đã gọi trực tiếp hàm hiện tại bằng `.venv/bin/python`, không dựa trên mock tests hoặc báo cáo cũ:

- `canonicalize_skills(['reactjs','React','TensorFlow','PyTorch','Unlisted Skill'])` trả `['React','Machine Learning','Unlisted Skill']`.
- `canonicalize_skills(None)` trả `[]`.
- `canonicalize_skills('Python')` trả `[]` (không chấp nhận scalar string).

Hàm giữ skill chưa biết, loại trùng không phân biệt hoa/thường; taxonomy hiện tại gộp TensorFlow/PyTorch vào Machine Learning. Nếu downstream cần các công nghệ riêng, Duy và Phát cần thống nhất taxonomy upstream, vì P5 không thể phục hồi chi tiết đã bị gộp chỉ từ `skills_std`.

Rủi ro source cần phối hợp Duy/Thuận: input thiếu được thay bằng DataFrame rỗng; code vẫn ghi reports, có thể che khuất báo cáo lịch sử nếu chạy vô điều kiện. P3/P4 group theo source nên cần kiểm tra source không null/ngoài danh sách trước chạy. Source-filtered runs có thể ghi đè output tổng bằng tập con. Các đề xuất là preflight fail khi input thiếu/schema sai, kiểm tra nguồn/ID và backup output lẫn reports trước chạy; chưa sửa source hoặc quy tắc.

## Bước tiếp theo

Thuận xác nhận snapshot chuẩn trên R2; Duy bàn giao P4 Parquet hoặc P2/P3 Parquet cùng provenance/checksum/schema. Khi có input xác minh được, Phát có thể chạy P3/P4 hiện có trong vùng output/report được bảo toàn, kiểm tra conservation, schema, ID, nguồn, missing và skill distribution trước EDA P5. Lần này điều kiện chạy chưa đạt: không có file Parquet chuẩn, chưa xác minh provenance JSON legacy, và JSON staging không khớp schema P5. Chưa có đề xuất thay đổi source bắt buộc để giải quyết việc thiếu file; ưu tiên bàn giao đúng snapshot trước.
