# Hướng dẫn chi tiết Setup AWS EC2 & S3 cho Dự án VN-IT-Job-Mining

> **Mục tiêu:** Giúp bạn (Thuận - Leader) tự tay thiết lập một hệ thống tự động hoàn chỉnh trên đám mây AWS (sử dụng 100% gói miễn phí Free Tier) để kéo code của cả nhóm về, cào dữ liệu định kỳ theo batching và lưu trữ an toàn vào Data Lake S3.

---

## 1. Khái niệm cơ bản (Hiểu nhanh trong 2 phút)

- **AWS EC2 (Elastic Compute Cloud):** Là một "máy tính ảo" (Virtual Private Server - VPS) chạy hệ điều hành Linux (Ubuntu) trên trung tâm dữ liệu của Amazon. Máy này sẽ hoạt động 24/7 thay cho laptop của bạn để tự động chạy cào dữ liệu mà không lo bị mất mạng hay tắt máy.
- **AWS S3 (Simple Storage Service):** Là "kho chứa file" dạng Data Lake trên đám mây. Bạn có thể lưu trữ hàng chục ngàn file dữ liệu (JSONL, Parquet) với chi phí cực rẻ, phân tầng rõ ràng (Raw, Staging, Curated) và không bao giờ lo mất dữ liệu.

---

## 2. Bước 1: Bảo đảm an toàn chi phí (Tránh mất tiền ngoài ý muốn)

> [!IMPORTANT]
> Tài khoản AWS mới sẽ có **12 tháng miễn phí (Free Tier)**:
> - **EC2:** 750 giờ/tháng cho loại máy `t2.micro` hoặc `t3.micro` (đủ chạy liên tục 24/7 cả tháng không tốn 1 xu).
> - **S3:** 5 GB dung lượng lưu trữ + 20.000 request đọc/ghi mỗi tháng (bộ dữ liệu 10.000 tin của nhóm chỉ tốn ~50–100 MB).

### Cài đặt cảnh báo chi phí (Budget Alert):
1. Đăng nhập vào [AWS Management Console](https://console.aws.amazon.com/).
2. Trên thanh tìm kiếm, gõ **AWS Budgets** → Chọn **Create budget**.
3. Chọn mẫu **Zero spend budget** (Cảnh báo khi chi phí vượt quá $0.01).
4. Nhập email của bạn (ví dụ: `billtranthuan@gmail.com`) → Nhấn **Create budget**.
5. *Kết quả:* Nếu phát sinh bất kỳ khoản phí nào dù chỉ 1 cent, AWS sẽ gửi email báo ngay lập tức.

---

## 3. Bước 2: Tạo S3 Bucket làm Data Lake

1. Trên thanh tìm kiếm AWS, gõ **S3** → Chọn dịch vụ **S3**.
2. Nhấn nút **Create bucket**.
3. Điền các thông số:
   - **Bucket name:** `vn-it-job-mining-data-lake-thuan` (tên phải là duy nhất trên toàn cầu, viết thường, không dấu cách).
   - **AWS Region:** Chọn `Asia Pacific (Singapore) ap-southeast-1` (gần Việt Nam nhất, tốc độ nhanh nhất).
   - **Block Public Access:** **TÍCH CHỌN** `Block all public access` (Bảo mật tối đa, không để lộ dữ liệu ra ngoài).
   - **Bucket Versioning:** Chọn `Disable` (để tiết kiệm dung lượng).
4. Nhấn **Create bucket** ở cuối trang.
5. Sau khi tạo xong, click vào tên bucket vừa tạo → Tạo sẵn 4 thư mục (Folders):
   - `raw/`
   - `staging/`
   - `curated/`
   - `logs/`

---

## 4. Bước 3: Tạo IAM User & Cấp quyền truy cập S3

Tuyệt đối không dùng tài khoản Root để cào dữ liệu. Chúng ta sẽ tạo một tài khoản kỹ thuật (IAM User) có quyền ghi vào S3:

1. Trên thanh tìm kiếm AWS, gõ **IAM** → Chọn dịch vụ **IAM**.
2. Chọn menu **Users** ở cột trái → Nhấn **Create user**.
3. **User name:** `crawler-ec2-bot` → Nhấn **Next**.
4. Ở trang *Set permissions*, chọn **Attach policies directly**.
5. Trong ô tìm kiếm policy, gõ `AmazonS3FullAccess` → Tích chọn policy này → Nhấn **Next** → Nhấn **Create user**.
6. Click vào user `crawler-ec2-bot` vừa tạo → Chuyển sang tab **Security credentials**.
7. Kéo xuống mục **Access keys** → Nhấn **Create access key**.
8. Chọn trường hợp sử dụng: **Application running outside AWS** (hoặc CLI) → Nhấn **Next** → **Create access key**.
9. **LƯU LẠI NGAY:**
   - `Access Key ID` (dạng: `AKIA...`)
   - `Secret Access Key` (dạng: `wJalrXUtn...` - chỉ hiện 1 lần duy nhất, tải file CSV về lưu bí mật).

---

## 5. Bước 4: Khởi tạo máy ảo EC2 (Ubuntu Linux)

1. Trên thanh tìm kiếm AWS, gõ **EC2** → Chọn dịch vụ **EC2**.
2. Nhấn nút màu cam **Launch instance**.
3. Cấu hình instance:
   - **Name:** `crawler-vm-ubuntu`
   - **Application and OS Images:** Chọn **Ubuntu** (chọn bản `Ubuntu Server 24.04 LTS` hoặc `22.04 LTS`, có nhãn *Free tier eligible*).
   - **Instance type:** Chọn `t2.micro` hoặc `t3.micro` (bắt buộc chọn loại có nhãn *Free tier eligible* - 1 vCPU, 1 GiB RAM).
   - **Key pair (login):**
     - Nhấn **Create new key pair**.
     - Đặt tên: `ec2-crawler-key`.
     - Key pair type: `RSA`.
     - Private key file format: `.pem` (cho Linux/Mac/Windows OpenSSH).
     - Nhấn **Create key pair** → Trình duyệt sẽ tải về file `ec2-crawler-key.pem`. Hãy cất file này cẩn thận, ví dụ để tại `~/.ssh/ec2-crawler-key.pem` hoặc trong máy của bạn.
   - **Network settings:** Giữ mặc định:
     - Tích chọn `Allow SSH traffic from Anywhere` (hoặc `My IP` để an toàn hơn).
   - **Configure storage:** Giữ mặc định `8 GiB gp3` (Free tier cho phép tối đa 30 GiB).
4. Nhấn **Launch instance**. Đợi khoảng 1-2 phút cho trạng thái chuyển sang **Running**.
5. Bấm vào Instance ID để xem thông tin: ghi lại địa chỉ **Public IPv4 address** (ví dụ: `18.141.22.45`).

---

## 6. Bước 5: Kết nối vào EC2 và Cài đặt Môi trường

Mở Terminal trên máy Linux của bạn (máy hiện tại), chạy lệnh sau:

### 6.1. Phân quyền và SSH vào EC2
```bash
# Đổi quyền file key pem để bảo mật
chmod 400 /đường/dẫn/tới/ec2-crawler-key.pem

# Kết nối vào máy ảo (thay IP thật của bạn vào)
ssh -i /đường/dẫn/tới/ec2-crawler-key.pem ubuntu@<PUBLIC_IP_CUA_EC2>
```
*Khi hỏi `Are you sure you want to continue connecting (yes/no)?`, gõ `yes` và bấm Enter.* Bạn đã vào trong máy ảo EC2!

### 6.2. Cài đặt các gói công cụ cần thiết trên EC2
Chạy các lệnh sau trong terminal của EC2:
```bash
# 1. Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# 2. Cài Python, Pip, venv, Git, cron
sudo apt install -y python3-pip python3-venv git curl htop cron

# 3. Clone source code dự án từ GitHub
cd ~
git clone https://github.com/Archduker/VN-IT-Job-Mining.git
cd VN-IT-Job-Mining

# 4. Tạo môi trường ảo Python (Virtual Environment)
python3 -m venv venv
source venv/bin/activate

# 5. Cài đặt các thư viện cơ bản
pip install --upgrade pip
pip install requests beautifulsoup4 boto3 python-dotenv
```

### 6.3. Cấu hình biến môi trường trên EC2
Tạo file `.env` chứa chìa khóa AWS vừa tạo ở Bước 3:
```bash
nano .env
```
Dán nội dung sau vào (thay key thật của bạn):
```env
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=ap-southeast-1
S3_BUCKET=vn-it-job-mining-data-lake-thuan
```
*Bấm `Ctrl + O` rồi Enter để lưu, `Ctrl + X` để thoát nano.*

### 6.4. Kiểm tra kết nối EC2 tới S3
Chạy thử lệnh Python kiểm tra:
```bash
python3 -c "
import boto3, os
from dotenv import load_dotenv
load_dotenv()
s3 = boto3.client('s3', region_name=os.getenv('AWS_REGION'))
print('S3 Buckets:', [b['Name'] for b in s3.list_buckets()['Buckets']])
"
```
Nếu màn hình in ra tên bucket của bạn (`vn-it-job-mining-data-lake-thuan`) nghĩa là kết nối đã thành công 100%!

---

## 7. Bước 6: Chiến lược Batching & Lập lịch chạy tự động

### Phân tích ý tưởng của bạn: "Mỗi ngày cào một web"
- **Nhận xét:** Ý tưởng này **RẤT TỐT VÀ KHẢ THI** vì:
  1. EC2 `t2.micro` chỉ có 1 GB RAM, nếu chạy cùng lúc 6 web có thể bị tràn RAM (OOM Crash). Chạy luân phiên mỗi ngày 1 web giúp máy chạy cực kỳ nhẹ nhàng (chỉ tốn ~50–100 MB RAM).
  2. Giảm tải request cho các trang tuyển dụng, không bị WAF nghi ngờ hay chặn IP.
  3. Quota mỗi web: chỉ cần cào **400–500 tin/lần chạy/ngày**. Với delay 2–3s, mỗi phiên cào chỉ mất khoảng **20–30 phút**.
  4. Lịch trình 6 ngày/tuần:
     - **Thứ 2:** TopDev (Sơn)
     - **Thứ 3:** VietnamWorks (Khoa)
     - **Thứ 4:** CareerViet (Tài)
     - **Thứ 5:** ITviec (Phát)
     - **Thứ 6:** Nguồn mới (Phúc)
     - **Thứ 7:** TopCV (Thuận - batch nhỏ thử nghiệm)
     - **Chủ Nhật:** Script tự động tổng hợp tuần, loại trùng, sao lưu sang S3 Staging.

### Cài đặt Cron tự động trên EC2
Trên terminal của EC2, mở crontab:
```bash
crontab -e
```
*(Nếu hỏi chọn editor, gõ `1` để chọn nano).*

Thêm các dòng sau vào cuối file (ví dụ chạy vào lúc 21:00 mỗi tối):
```cron
# Đường dẫn làm việc chuẩn
PROJECT_DIR=/home/ubuntu/VN-IT-Job-Mining
PYTHON_BIN=/home/ubuntu/VN-IT-Job-Mining/venv/bin/python

# Thứ 2: TopDev
0 21 * * 1 cd $PROJECT_DIR && git pull origin main && $PYTHON_BIN run.py --source topdev --max-items 450 >> logs/cron.log 2>&1

# Thứ 3: VietnamWorks
0 21 * * 2 cd $PROJECT_DIR && git pull origin main && $PYTHON_BIN run.py --source vietnamworks --max-items 450 >> logs/cron.log 2>&1

# Thứ 4: CareerViet
0 21 * * 3 cd $PROJECT_DIR && git pull origin main && $PYTHON_BIN run.py --source careerviet --max-items 450 >> logs/cron.log 2>&1

# Thứ 5: ITviec
0 21 * * 4 cd $PROJECT_DIR && git pull origin main && $PYTHON_BIN run.py --source itviec --max-items 450 >> logs/cron.log 2>&1

# Thứ 6: Nguồn Phúc
0 21 * * 5 cd $PROJECT_DIR && git pull origin main && $PYTHON_BIN run.py --source <nguon_phuc> --max-items 450 >> logs/cron.log 2>&1

# Thứ 7: TopCV
0 21 * * 6 cd $PROJECT_DIR && git pull origin main && $PYTHON_BIN run.py --source topcv --max-items 150 >> logs/cron.log 2>&1

# Chủ Nhật 22:00: Chạy script ELT tổng hợp dữ liệu tuần sang Staging
0 22 * * 0 cd $PROJECT_DIR && $PYTHON_BIN etl/weekly_sync.py >> logs/elt.log 2>&1
```
*Lợi ích:* Trước mỗi lần cào, lệnh `git pull origin main` sẽ tự động kéo code mới nhất mà nhóm đã đẩy lên GitHub về máy ảo để chạy!

---

## 8. Các lệnh hữu ích khi quản trị EC2

```bash
# Xem log cron đang chạy theo thời gian thực
tail -f ~/VN-IT-Job-Mining/logs/cron.log

# Kiểm tra dung lượng RAM, CPU đang dùng
htop

# Kiểm tra danh sách file đã upload lên S3
aws s3 ls s3://vn-it-job-mining-data-lake-thuan/raw/ --recursive
```
