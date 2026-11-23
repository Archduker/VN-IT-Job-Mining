# VN-IT-Job-Mining

**Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT**

Đồ án môn Khai phá dữ liệu. Dự án thu thập tin tuyển dụng IT từ 8 sàn việc làm Việt Nam, làm sạch và gộp thành một bảng dữ liệu thống nhất, rồi khai phá để trả lời 5 câu hỏi cho sinh viên IT và người mới vào nghề.

- **Phạm vi:** tin đăng tháng 9–11/2026, cào trong tháng 10–11/2026.
- **8 sàn:** TopCV, TopDev, VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO.
- **Dữ liệu:** chỉ có tin tuyển dụng, không có CV hay chương trình đào tạo. Vì vậy mọi kết luận đều nói về phía nhà tuyển dụng.

---

## 1. Năm mục tiêu (SD1–SD5)

Các mục tiêu được làm theo thứ tự: BI, rồi khai phá không giám sát, rồi train model. Chi tiết từng mục tiêu ở [`docs/target/`](docs/target/00_de_tai.md).

| Mục tiêu | Câu hỏi | Phương pháp |
|---|---|---|
| **SD1** | Thị trường cần ai? (nghề, cấp bậc, tỉnh, hình thức làm việc, lương công bố, yêu cầu với người mới) | Thống kê mô tả (BI) |
| **SD2** | Kỹ năng nào đi cùng nhau? Kỹ năng nào hiếm? | Luật kết hợp FP-Growth |
| **SD3** | Nhóm việc thật sự là gì? Tin nào "khác hoặc mới"? | K-Means + HDBSCAN; Isolation Forest + GLOSH |
| **SD4** | Kỹ năng nào đáng tiền? Lương ước tính của tin "thỏa thuận"? | Random Forest + SHAP |
| **SD5** | Người mới nên học gì, theo thứ tự nào? | Tổng hợp SD2 và SD4, kiểm bằng coverage@N |

## 2. Kết quả chính (chạy thật 22/11/2026)

| | Kết quả |
|---|---|
| Dữ liệu | 13.361 bản tin thô → **3.718 tin IT** đã làm sạch, khử trùng, 26 trường; 973 đặc trưng; vector e5 768 chiều |
| SD1 | Web, Bridge (BA/PM) và Data/AI chiếm khoảng một nửa số tin; Hà Nội và TP.HCM chiếm 89%. Tin cho người mới đòi trung vị 1 năm kinh nghiệm và 4 công cụ. Lương công bố tăng theo cấp: Intern 10,0 → Junior 15,5 → Middle 22,5 → Senior 37,5 triệu |
| SD2 | 12.642 luật, ví dụ java ⇒ spring_boot, docker ⇒ kubernetes, grafana ⇒ prometheus; 124 kỹ năng hiếm. Luật ổn định khi đổi ngưỡng support |
| SD3 | 10 cụm ổn định qua 5 seed (ARI 0,83). Data/AI tách thành học sâu và BI; "IT Manager" rơi vào cụm hạ tầng. 233 tin bất thường; không thấy nghề mới |
| SD4 | Mô hình lương thắng cách đoán theo trung vị 16,7% (MAE 6,1 so với 7,3 triệu). Kinh nghiệm và cấp bậc chiếm 67% tổng SHAP; mỗi kỹ năng lẻ chỉ gắn với thêm dưới 0,6 triệu/tháng |
| SD5 | Lộ trình cho 8 nghề, hơn baseline ở cả 8. 4 nghề ổn định: Bridge, Data/AI, Tester, Web |

**Giới hạn:**
- Silhouette chỉ 0,075: các nhóm việc IT chồng lấn nhau ở mọi k.
- Chỉ 44% tin công bố lương.
- Một số sàn ghi tỉnh theo trụ sở công ty, không theo nơi làm việc.
- Dữ liệu chỉ một kỳ 3 tháng, nên không kết luận được xu hướng hay quan hệ nhân quả.

Bảng nghiệm thu đầy đủ ở [`docs/spec/08_evaluation_spec.md`](docs/spec/08_evaluation_spec.md) mục 3. Slide kết quả ở [`docs/presentation/final_slides.html`](docs/presentation/final_slides.html): mở bằng trình duyệt, dùng phím ← → để chuyển slide; slide 11 là bản đồ cụm tương tác 2D/3D.

---

## 3. Kiến trúc và quy trình

```text
8 sàn tuyển dụng
   │  1. Collection: cào hai pha (Discovery → URL Ledger → Detail), raw JSON bất biến
   ▼
Cloudflare R2: url_ledger/, raw/
   │  2. Pre-processing (01 → 04): lọc IT, khử trùng, làm phẳng 8 nguồn, tách lương/kinh nghiệm,
   │     dịch JD tiếng Anh (envit5, chạy local), chuẩn hóa 34 tỉnh, chức danh, nhóm nghề
   ▼
data/preprocessing/04_normalization/silver.parquet (bảng sạch, 26 trường)
   │  3. Processing (07 → 12_e5): tách mục JD, trích kỹ năng bằng từ điển (tool / concept / soft),
   │     ma trận đặc trưng, vector multilingual-e5-base
   ▼
data/processing/10_features/, 08_skills/, 12_e5/
   │  4. Mining (M1 → M6): BI, FP-Growth, K-Means + HDBSCAN, Isolation Forest, Random Forest + SHAP, lộ trình
   ▼
mining/artifacts/ → Monitoring (FastAPI + React) và slide
```

Pipeline đánh giá dữ liệu theo 5 tiêu chí: completeness, accuracy, consistency, timeliness, uniqueness. Mỗi bước ghi báo cáo vào `reports/` kèm kiểm tra bảo toàn (số vào = số ra + số bỏ).

Phân loại tin IT, nhóm nghề và kỹ năng đều dùng **luật và từ điển đã duyệt**; pipeline không gọi LLM. Model duy nhất chạy trong pipeline là model dịch `VietAI/envit5-translation` và model nhúng `intfloat/multilingual-e5-base`, cả hai chạy trên máy. Các model ML ở bước Mining (K-Means, HDBSCAN, Isolation Forest, Random Forest) chạy trên dữ liệu thật và tái lập được với `random_state` 42.

---

## 4. Cài đặt

Cần Python 3.12, vì `collection/careerviet/crawler.py` dùng cú pháp f-string chỉ có từ 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate                       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r monitoring/backend/requirements.txt
pip install pytest ruff                         # công cụ test và lint
touch .env                                      # cấu hình chỉ nằm trong .env, repo không có file mẫu
```

- **`.env`:** chứa khóa Cloudflare R2 (và cấu hình Postgres nếu dùng Airflow). Không commit file này, không in giá trị ra màn hình.
- **Bước 12_e5:** cần GPU và model e5 đã tải.
- **Dịch JD (`--translate`):** cần model envit5.

## 5. Chạy pipeline

```bash
# 1. Collection (cào thật, ghi lên R2: chỉ chạy khi cần)
python run.py --source topcv --phase discover --max-pages 2 --sync-r2
python run.py --source topcv --phase detail --max-items 30 --sync-r2
python scripts/sync_cloud_lakehouse.py --status             # so dữ liệu trên máy với R2
python scripts/sync_cloud_lakehouse.py --download           # tải raw và ledger từ R2 về data/

# 2 + 3. Pre-processing và Processing (chuỗi 01 → 04 → 07 → 08 → 10 → 12_e5)
python scripts/run_preprocessing.py --step all --source all --dry-run
python scripts/run_preprocessing.py --step all --source all [--translate]

# 4. Mining (M1–M6) → mining/artifacts/
python -m mining.run_mining_pipeline --only bi,fp,cluster,anomaly,salary,recommend

# Biểu đồ cho slide, vẽ từ kết quả Mining
python scripts/build_mining_charts.py --inject
```

`scripts/run_staging_integration_pipeline.py` và `data/curated/curated_flat_golden_jobs.parquet` là pipeline cũ, không dùng cho việc mới.

## 6. Kiểm thử

```bash
pytest tests/                                   # toàn bộ; mạng ngoài localhost bị chặn
pytest tests/ -m unit -q                        # chỉ unit
```

Kết quả gần nhất (23/11/2026): **889 passed, 5 skipped, 0 failed**.

Các thư mục test:
- `tests/unit/`: test unit.
- `tests/integration/`: test integration.
- `tests/contract/`: chuẩn crawler C1–C14, chạy trên mẫu offline trong `tests/fixtures/<nguồn>/`.
- `tests/data/`: test cần dữ liệu thật; tự bỏ qua khi máy thiếu dữ liệu.

Máy có `make` thì dùng được `make test`, `make test-fast`, `make lint`, `make check`.

## 7. Monitoring

```bash
./start_monitoring.sh          # hoặc: make monitor
```

Lệnh này chạy FastAPI tại `http://127.0.0.1:8000/docs` và giao diện React + Vite tại `http://localhost:5173`. Các trang:
- Collection và R2.
- EDA.
- Pre-processing và Processing.
- Market Insights (SD1–SD5).
- Airflow.

Mọi số trên giao diện đều lấy từ dữ liệu thật. Khi chưa có dữ liệu, giao diện hiện trạng thái rỗng kèm lý do, không hiện số giả. Script không bao giờ bật Airflow scheduler, vì scheduler sẽ cào và ghi lên R2.

---

## 8. Cấu trúc thư mục

```text
VN-IT-Job-Mining/
├── run.py                 # điểm vào crawler: --source, --phase discover|detail|all
├── collection/            # 1. crawler hai pha cho 8 sàn, URL Ledger, kết nối R2
├── preprocessing/         # 2. bước 01–04: clean, integration, transformation, normalization; từ điển luật
├── processing/            # 3. bước 07–12_e5: tách mục JD, kỹ năng, đặc trưng, embedding
├── mining/                # 4. M1–M6 và mining/artifacts/ (kết quả, không vào git)
├── monitoring/            # backend FastAPI + frontend React/Vite
├── airflow/               # DAG lập lịch cào (chỉ dùng cho Collection)
├── scripts/               # driver pipeline, đồng bộ R2, báo cáo, vẽ biểu đồ
├── reports/               # báo cáo từng bước pipeline (Monitoring đọc)
├── docs/                  # đặc tả, mục tiêu, nhật ký lỗi, slide
└── tests/                 # unit, integration, contract, data
```

Mỗi thư mục code có một `CLAUDE.md` mô tả quy ước và các bẫy riêng của thư mục đó.

## 9. Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [`docs/target/`](docs/target/00_de_tai.md) | Đề tài và 5 mục tiêu SD1–SD5 (đọc trước tiên) |
| [`docs/spec/`](docs/spec/) | Đặc tả 01–13; chi tiết từng bước ở `spec/preprocessing/`, `spec/processing/`, `spec/mining/` |
| [`docs/spec/08_evaluation_spec.md`](docs/spec/08_evaluation_spec.md) | Tiêu chí nghiệm thu và kết quả |
| [`docs/issue_log.md`](docs/issue_log.md) | Nhật ký lỗi đã xử lý (lỗi → nguyên nhân → cách xử lý → kiểm chứng) |
| [`docs/KNOWN_ISSUED.md`](docs/KNOWN_ISSUED.md) | Việc còn mở |
| [`docs/presentation/final_slides.html`](docs/presentation/final_slides.html) | Slide kết quả cuối |

## 10. Quy tắc an toàn

- **Raw bất biến:** lỗi parse được sửa ở bước pre-processing, không sửa file raw.
- **Ghi hoặc xóa trên R2:** luôn chạy thử (`--dry-run`) trước và phải được người phụ trách đồng ý.
- **Bí mật:** chỉ nằm trong `.env`, không hardcode và không in giá trị ra màn hình.
- **Số liệu:** chỉ dùng số thật; dữ liệu giả (`--synthetic`) chỉ dùng cho test.

## 11. Đạo đức thu thập

Dữ liệu dùng cho nghiên cứu học thuật về thị trường lao động IT Việt Nam. Crawler nghỉ ngẫu nhiên 2–4,5 giây giữa các lần gọi, bỏ qua trang lỗi mà không dừng cả tiến trình, và không thu thập thông tin cá nhân của ứng viên.
