# Hướng Dẫn Vận Hành Apache Airflow & Lịch Cào Hai Pha Tối Ưu EC2 (VN-IT-Job-Mining)

Tài liệu này được tổng hợp và đối chiếu trực tiếp từ kiến trúc hệ thống **VN-IT-Job-Mining** kết hợp tài liệu chuẩn của **[Apache Airflow Documentation](https://airflow.apache.org/docs/)**, thiết kế riêng cho việc vận hành trên hạ tầng **AWS EC2 On-Demand** và **Cloudflare R2 / Cloudflare R2**.

---

## 1. Tổng Quan Kiến Trúc Điều Phối Hai Pha (Two-Phase Decoupled Architecture)

Hệ thống điều phối toàn diện **8 sàn tuyển dụng CNTT**: `topdev`, `vietnamworks`, `careerviet`, `vieclam24h`, `itviec`, `topcv`, `jobsgo`, `glints`.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CHẾ ĐỘ ĐIỀU PHỐI HAI PHA                                     │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│  [PHA 1: KHÁM PHÁ URL MỖI NGÀY] (Daily URL Discovery)                                            │
│  - Tần suất: 05:00 sáng hàng ngày (0 5 * * *)                                                    │
│  - Mục tiêu: Quét 1-2 trang mới nhất (sắp xếp theo sort=new) để bắt 100% tin tuyển dụng mới.   │
│  - Cơ chế: Đăng ký URL sạch vào UrlLedger với status = 'PENDING', không cào detail payload.     │
│  - Thời gian chạy: Chỉ 1 - 2 phút cho cả 8 nguồn (siêu nhẹ, không tốn tài nguyên).              │
│                                                                                                  │
│                                           │                                                      │
│                                           ▼ (Lưu vào Cloudflare R2 UrlLedger)                            │
│                                                                                                  │
│  [PHA 2: CÀO CHI TIẾT DỒN CUỐI TUẦN] (Weekend-Focused Adaptive Detail Extraction)                │
│  - Lập lịch Airflow: 0 9,14,18,21,22 * * * (5 ca/ngày)                                          │
│  - Điều phối bởi: AdaptiveRouteCheckOperator (Adaptive Workload Router)                          │
│  - Hạn ngạch cứng: Đúng 30 tin / ca (chạy 1.5 - 2 phút / ca).                                    │
│  - Phân luồng Ngày thường vs Cuối tuần:                                                          │
│    * Thứ 2 - Thứ 6 (Ban ngày): Tự động SKIP trong 0.05s (0 tải EC2, không bị Cloudflare soi).    │
│    * Thứ 2 - Thứ 6 (Ca tối 21:00): Chạy 1 ca bảo trì duy nhất (tối đa 30 tin).                  │
│    * Thứ 7 - Chủ Nhật (Cuối tuần): Chế độ xả hàng loạt (09h, 14h, 18h, 21h, 22h).               │
│      Nghỉ Cooldown an toàn tối thiểu 55 phút giữa các ca; Tự động dừng khi hàng đợi rỗng.        │
│                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Chi Tiết Lập Lịch & Cơ Chế Bắt Tin Mới Hàng Ngày (Pha 1)

### 2.1. Đảm Bảo Bắt Tin Mới Mỗi Ngày
Để đảm bảo **không bao giờ bỏ sót tin mới đăng**, Pha 1 (`dag_discovery_daily`) chạy cố định lúc **05:00 sáng mỗi ngày**:
- Quét các trang đầu (trang 1 và 2) của danh mục IT trên từng trang web.
- **TopCV URL sắp xếp theo ngày đăng mới nhất (`sort=new`):**
  ```
  https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257?sort=new&type_keyword=1&disable_auto_detect_type_keyword=1&category_family=r257&saturday_status=0&page={page}
  ```
  Tham số `sort=new` đảm bảo các tin vừa đăng trong 24 giờ qua luôn hiển thị ở trang 1-2 thay vì phụ thuộc vào thuật toán gợi ý của TopCV.
- Các URL được băm theo chuẩn SHA-256 (`clean_canonical_url`). Nếu là tin mới chưa từng thấy, hệ thống ghi nhận vào `UrlLedger` với trạng thái `PENDING`.

### 2.2. Song Song Nhẹ Nhàng Qua Airflow Pools
Để tránh xung đột tài nguyên giữa Pha 1 và Pha 2, mỗi nguồn sở hữu 1 Pool riêng biệt trong Airflow (`pool_topdev`, `pool_topcv`, ..., với `slots=1`):
```python
# Chạy thành 2 luồng song song nhẹ nhàng (mỗi luồng 4 nguồn nối tiếp)
[disc_topdev >> disc_careerviet >> disc_itviec >> disc_glints]
[disc_vietnamworks >> disc_vieclam24h >> disc_topcv >> disc_jobsgo]
```

---

## 3. Cơ Chế Xả Hàng Đợi Cuối Tuần & Tiết Kiệm EC2 On-Demand (Pha 2)

### 3.1. Tại Sao Lại Chọn Phương Án Xả Cuối Tuần Trên EC2 On-Demand?
1. **Tiết kiệm chi phí đám mây (Cloud Cost Optimization):**
   - Với gói EC2 On-Demand, việc duy trì crawler chạy liên tục 24/7 gây lãng phí CPU idle.
   - Nhờ `AdaptiveRouteCheckOperator`, các lần kích hoạt ban ngày trong tuần được **bỏ qua (Skip) ngay lập tức trong 0.05 giây**, tiêu thụ ~0% CPU.
2. **Chống chặn bot WAF / Cloudflare Rate Limiting (403 / 429 / Turnstile):**
   - Các sàn tuyển dụng (TopCV, Glints, TopDev) giám sát lưu lượng cao điểm trong giờ hành chính ngày thường rất gắt gao.
   - Cào chi tiết vào cuối tuần và đêm muộn ngày thường tránh được khung giờ cao điểm, giảm tỷ lệ bị captcha xuống gần như bằng 0.
3. **Duty-Cycle An Toàn (Khống Chế 30 Tin / Ca):**
   - Mỗi ca chỉ cào đúng 30 tin (thời gian chạy ~1.5 đến 2 phút).
   - Nghỉ Cooldown tối thiểu 55 phút giữa các ca cuối tuần để trình duyệt giải phóng bộ nhớ RAM và IP nguội hoàn toàn.

### 3.2. Bảng Phân Tuyến Hoạt Động (Adaptive Workload Router Matrix)

| Khung Thời Gian | Trạng Thái Hàng Đợi | Quyết Định Router | Hạn Ngạch (Quota) | Hành Động Hệ Thống |
| :--- | :--- | :--- | :--- | :--- |
| **Bất kỳ lúc nào** | Backlog = 0 (`IDLE`) | **SKIP** | 0 tin | Dừng ngay lập tức trong 0.05s |
| **Thứ 2 - Thứ 6 (08:00 - 19:59)** | Backlog > 0 | **SKIP** (`WEEKDAY_PAUSE`) | 0 tin | Bỏ qua, dồn tải để xả vào cuối tuần |
| **Thứ 2 - Thứ 6 (20:00 - 23:00)** | Backlog > 0 | **RUN** (`WEEKDAY_MAINTENANCE`) | Tối đa 30 tin | Chạy 1 ca duy nhất để bảo trì nhẹ |
| **Thứ 7 - CN (09h, 14h, 18h, 21h, 22h)** | Backlog > 0 (Đủ Cooldown) | **RUN** (`WEEKEND_FLUSH`) | Đúng 30 tin | Xả hàng đợi định kỳ, ghi nhận Cooldown |
| **Thứ 7 - CN** | Chưa đủ 55 phút Cooldown | **SKIP** (`WEEKEND_COOLDOWN`) | 0 tin | Nghỉ bảo vệ IP chống Cloudflare chặn |

---

## 4. Thông Tin Đăng Nhập & Khởi Động Airflow

### 4.1. Thông Tin Đăng Nhập Web UI
- **Địa chỉ:** `http://localhost:8080` (hoặc `http://<ec2-public-ip>:8080` nếu chạy trên EC2)
- **Username:** `admin`
- **Password:** `admin`
*(Role: Admin — toàn quyền xem log, kích hoạt DAG, kiểm tra XCom và trạng thái task).*

### 4.2. Khởi Động Trên Môi Trường Phát Triển / EC2
Mở 2 phiên Terminal (hoặc chạy ngầm qua `systemd` / `supervisor` trên EC2):

```bash
# Terminal 1: Khởi động Scheduler (Bộ điều phối & lập lịch)
cd /run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining
source .venv/bin/activate
export AIRFLOW_HOME=$(pwd)/airflow
export PYTHONPATH=.:$(pwd)/airflow/plugins
airflow scheduler

# Terminal 2: Khởi động Webserver (Giao diện điều khiển UI)
cd /run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining
source .venv/bin/activate
export AIRFLOW_HOME=$(pwd)/airflow
export PYTHONPATH=.:$(pwd)/airflow/plugins
airflow webserver --port 8080
```

---

## 5. Danh Sách Các DAGs Trong Hệ Thống

| DAG ID | Tên Sàn | Lịch Chạy (Schedule) | Vai Trò & Cơ Chế |
| :--- | :--- | :--- | :--- |
| `dag_discovery_daily` | Cả 8 Sàn | `0 5 * * *` (05:00 sáng mỗi ngày) | Quét URL mới (sort=new), nạp vào UrlLedger |
| `crawler_detail_topcv` | TopCV | `0 9,14,18,21,22 * * *` | Cào chi tiết theo Quota 30 tin (Xả cuối tuần) |
| `crawler_detail_topdev` | TopDev | `0 9,14,18,21,22 * * *` | Cào chi tiết theo Quota 30 tin (Xả cuối tuần) |
| `crawler_detail_vietnamworks` | VietnamWorks | `0 9,14,18,21,22 * * *` | Cào chi tiết theo Quota 30 tin (Xả cuối tuần) |
| `crawler_detail_careerviet` | CareerViet | `0 9,14,18,21,22 * * *` | Cào chi tiết theo Quota 30 tin (Xả cuối tuần) |
| `crawler_detail_vieclam24h` | ViecLam24h | `0 9,14,18,21,22 * * *` | Cào chi tiết theo Quota 30 tin (Xả cuối tuần) |
| `crawler_detail_itviec` | ITviec | `0 9,14,18,21,22 * * *` | Cào chi tiết theo Quota 30 tin (Xả cuối tuần) |
| `crawler_detail_jobsgo` | JobsGO | `0 9,14,18,21,22 * * *` | Cào chi tiết theo Quota 30 tin (Xả cuối tuần) |
| `crawler_detail_glints` | Glints | `0 9,14,18,21,22 * * *` | Cào chi tiết theo Quota 30 tin (Xả cuối tuần) |

---

## 6. Lệnh CLI Thao Tác Nhanh (Dành Cho Thuyết Minh & Kiểm Thử)

```bash
# 1. Kiểm tra tính toàn vẹn của tất cả DAGs (báo lỗi nếu sai cú pháp import)
python -c "from airflow.models import DagBag; bag = DagBag('airflow/dags'); assert len(bag.import_errors) == 0; print('DAGs OK!')"

# 2. Liệt kê toàn bộ DAGs của hệ thống qua CLI
airflow dags list

# 3. Test nhanh 1 task URL Discovery (Pha 1) của TopCV
airflow tasks test dag_discovery_daily discover_topcv 2026-10-25

# 4. Test nhanh 1 ca cào Pha 2 có kiểm tra Route Check
airflow tasks test crawler_detail_topcv check_route_topcv 2026-10-25

# 5. Chạy cào trực tiếp qua file điều phối chính run.py
python run.py --source topcv --phase discover --max-pages 2 --online
python run.py --source topcv --phase detail --max-items 30 --online
```
