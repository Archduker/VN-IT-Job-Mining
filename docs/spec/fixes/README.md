# docs/spec/fixes: đặc tả giải pháp cho issue sau merge

Mỗi file nhóm các issue cùng nguyên nhân. Mục lục và trạng thái ở `docs/tasks/issues_merge.md`; nội dung issue ở `KNOWN_ISSUED.md`. Đây là bước 3 của quy trình; prompt (bước 4) ở `docs/prompting/issues/`.

| File | Issue | Thứ tự ưu tiên | Chờ quyết định |
|---|---|---|---|
| F01_test_env_mining.md | MERGE-3/4, MINE-2/3 | 1 (chặn CI) | cài gói vào venv |
| F02_test_collection.md | PRE-24, PRE-27 | 1 (chặn CI) | số phận `target_schema_formatter` (hỏi Phát) |
| F03_integration_hoang.md | PRE-18/19/20, GEN-7 | 2 | thiết kế I0, GEN-4 |
| F04_ledger_csv.md | PRE-25 | 2 | - |
| F05_seniority_5_levels.md | PRE-22 (code) | 2 | tên cột `seniority_ord` |
| F06_pipeline_wiring.md | PRE-16/17/21 | 2 | hỏi Tài, Hoàng, Duy về đường ra/vào |
| F07_parse_errors_duy.md | PRE-23 | 3 | Embedded vs UI/UX |
| F08_collection.md | SCRAPE-11/13/14/17/18, MERGE-9 | 3 | SCRAPE-18 |
| F09_it_filter_cohort.md | PRE-12/13/15/28 | 3 | cohort, dùng model |
| F10_mining.md | MINE-1/4/5/6 | 4 | khoảng k, F05, GEN-4 |
| F11_monitoring.md | VIZ-6/7 | 4 | docker |
| F12_docs_cleanup.md | MERGE-2, GEN-8, PRE-26 | 5 | thư mục docs của Phát |
| F13_r2_layout.md | GEN-4/7/9 | chờ | layout R2 |
