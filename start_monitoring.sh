#!/usr/bin/env bash
# Mở hệ thống monitoring bằng một lệnh: kiểm tra .env, cài phụ thuộc khi cần,
# bật PostgreSQL (cho thẻ Airflow), chạy backend :8000 và frontend :5173, mở trình duyệt.
#
#   ./start_monitoring.sh               chạy đầy đủ
#   ./start_monitoring.sh --check       chỉ kiểm tra, không cài và không bật gì
#   ./start_monitoring.sh --no-db       không bật PostgreSQL
#   ./start_monitoring.sh --no-browser  không mở trình duyệt
#
# Không bật Airflow scheduler: scheduler tự chạy DAG cào và ghi lên R2.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
FRONTEND="$ROOT/monitoring/frontend"
BACKEND="$ROOT/monitoring/backend"
LOG_DIR="$ROOT/logs/monitoring"
ENV_FILE="$ROOT/.env"
BACKEND_PORT=8000
FRONTEND_PORT=5173

CHECK_ONLY=0
WITH_DB=1
OPEN_BROWSER=1
for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=1 ;;
        --no-db) WITH_DB=0 ;;
        --no-browser) OPEN_BROWSER=0 ;;
        -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Không hiểu tùy chọn: $arg (xem --help)"; exit 2 ;;
    esac
done

if [ -t 1 ]; then
    G=$'\033[0;32m'; Y=$'\033[1;33m'; R=$'\033[0;31m'; B=$'\033[1m'; N=$'\033[0m'
else
    G=""; Y=""; R=""; B=""; N=""
fi
ok()   { echo "${G}[OK]${N}   $*"; }
warn() { echo "${Y}[WARN]${N} $*"; WARNINGS=$((WARNINGS + 1)); }
fail() { echo "${R}[LỖI]${N} $*"; exit 1; }
step() { echo; echo "${B}== $* ==${N}"; }
WARNINGS=0

# Khóa có giá trị trong .env hay không; không bao giờ in giá trị.
env_has() { grep -Eq "^[[:space:]]*(export[[:space:]]+)?$1[[:space:]]*=[[:space:]]*[^[:space:]#]" "$ENV_FILE"; }

hash_files() { cat "$@" | sha256sum | cut -d' ' -f1; }

# In mô tả tiến trình đang giữ cổng; không in gì nếu cổng trống.
# Coi mọi socket LISTEN là bận, kể cả khi không xem được chủ sở hữu (tiến trình của user khác, docker-proxy).
port_busy() {
    local port=$1 line who
    if command -v ss >/dev/null; then
        line=$(ss -ltnpH "sport = :$port" 2>/dev/null | head -1)
        [ -z "$line" ] && return 0
        who=$(echo "$line" | grep -o 'users:(([^)]*' | head -1 | sed 's/users:((//')
    elif command -v lsof >/dev/null; then
        line=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sed -n 2p)
        [ -z "$line" ] && return 0
        who=$(echo "$line" | awk '{print $1" pid="$2}')
    elif (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
        who=""
    else
        return 0
    fi
    echo "${who:-một tiến trình không xem được (user khác hoặc docker)}"
}

wait_http() {  # url, pid, tên, log, số giây
    local url=$1 pid=$2 name=$3 log=$4 limit=${5:-60} i
    for ((i = 0; i < limit; i++)); do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "--- 20 dòng cuối $log ---"; tail -n 20 "$log"
            fail "$name dừng khi đang khởi động."
        fi
        curl -sf -o /dev/null "$url" && return 0
        sleep 1
    done
    echo "--- 20 dòng cuối $log ---"; tail -n 20 "$log"
    fail "$name chưa phản hồi sau ${limit} giây."
}

cd "$ROOT" || exit 1

step "1. Cấu hình .env"
if [ ! -s "$ENV_FILE" ]; then
    fail "Chưa có .env hoặc file đang trống ($ENV_FILE). Cấu hình chỉ quản lý trong .env: điền khóa R2 và kết nối PostgreSQL rồi lưu file."
fi
ok ".env có $(grep -Ec '^[[:space:]]*(export[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=' "$ENV_FILE") khóa"
missing=()
for key in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET_NAME; do env_has "$key" || missing+=("$key"); done
env_has R2_ENDPOINT_URL || env_has R2_ACCOUNT_ID || missing+=("R2_ENDPOINT_URL hoặc R2_ACCOUNT_ID")
if [ ${#missing[@]} -eq 0 ]; then ok "Đủ khóa Cloudflare R2"
else warn "Thiếu khóa R2: ${missing[*]}. Monitoring vẫn chạy, các thẻ R2 sẽ báo chưa cấu hình."; fi
if env_has AIRFLOW__DATABASE__SQL_ALCHEMY_CONN; then ok "Có kết nối PostgreSQL của Airflow"
else warn "Thiếu AIRFLOW__DATABASE__SQL_ALCHEMY_CONN; backend sẽ thử mặc định postgresql://airflow:airflow@localhost:5432/airflow."; fi

step "2. Python (.venv)"
deps_hash=$(hash_files "$ROOT/requirements-dev.txt" "$ROOT/requirements.txt" "$BACKEND/requirements.txt")
if [ ! -x "$VENV/bin/python" ]; then
    [ $CHECK_ONLY -eq 1 ] && fail "Chưa có .venv. Chạy lại không kèm --check để tự tạo."
    echo "Tạo .venv bằng Python 3.12 ..."
    if command -v uv >/dev/null; then uv venv -q --python 3.12 "$VENV" || fail "uv không tạo được .venv"
    elif command -v python3.12 >/dev/null; then python3.12 -m venv "$VENV" || fail "python3.12 không tạo được .venv"
    else fail "Cần Python 3.12 (hoặc uv) để tạo .venv."; fi
fi
if [ "$(cat "$VENV/.deps-hash" 2>/dev/null)" != "$deps_hash" ]; then
    [ $CHECK_ONLY -eq 1 ] && fail "Phụ thuộc Python chưa cài hoặc đã đổi. Chạy lại không kèm --check."
    echo "Cài phụ thuộc Python ..."
    if command -v uv >/dev/null; then
        VIRTUAL_ENV="$VENV" uv pip install -q -r requirements-dev.txt -r "$BACKEND/requirements.txt" || fail "Cài phụ thuộc Python lỗi"
    else
        "$VENV/bin/pip" install -q -r requirements-dev.txt -r "$BACKEND/requirements.txt" || fail "Cài phụ thuộc Python lỗi"
    fi
    echo "$deps_hash" > "$VENV/.deps-hash"
fi
ok "$("$VENV/bin/python" -V), phụ thuộc đã cài"

step "3. Node (frontend)"
command -v npm >/dev/null || fail "Chưa có Node.js/npm."
lock="$FRONTEND/package-lock.json"; marker="$FRONTEND/node_modules/.package-lock.json"
if [ ! -f "$marker" ] || [ "$lock" -nt "$marker" ]; then
    [ $CHECK_ONLY -eq 1 ] && fail "node_modules chưa cài hoặc cũ hơn package-lock.json. Chạy lại không kèm --check."
    echo "Chạy npm ci ..."
    (cd "$FRONTEND" && npm ci --no-audit --no-fund) || fail "npm ci lỗi"
fi
ok "Node $(node -v), node_modules khớp package-lock.json"

step "4. PostgreSQL (cho thẻ Airflow)"
if [ $WITH_DB -eq 0 ]; then
    warn "Bỏ qua theo --no-db. Các thẻ Airflow sẽ báo chưa kết nối nếu PostgreSQL chưa chạy."
elif ! command -v docker >/dev/null; then
    warn "Không có docker. Các thẻ Airflow sẽ báo chưa kết nối."
elif ! docker info >/dev/null 2>&1; then
    warn "Không gọi được docker (thường do thiếu quyền). Thêm user vào nhóm docker: sudo usermod -aG docker \$USER, đăng nhập lại rồi chạy lại."
elif [ $CHECK_ONLY -eq 1 ]; then
    state=$(docker inspect -f '{{.State.Health.Status}}' vn_it_jobs_postgres 2>/dev/null || echo "chưa chạy")
    ok "Docker dùng được, PostgreSQL: $state"
else
    docker compose up -d postgres >/dev/null || fail "docker compose up postgres lỗi"
    for ((i = 0; i < 30; i++)); do
        [ "$(docker inspect -f '{{.State.Health.Status}}' vn_it_jobs_postgres 2>/dev/null)" = healthy ] && break
        sleep 1
    done
    if [ "$(docker inspect -f '{{.State.Health.Status}}' vn_it_jobs_postgres 2>/dev/null)" = healthy ]; then ok "PostgreSQL chạy ở localhost:5432"
    else warn "PostgreSQL chưa healthy sau 30 giây. Xem: docker compose logs postgres"; fi
fi

step "5. Cổng $BACKEND_PORT và $FRONTEND_PORT"
for port in $BACKEND_PORT $FRONTEND_PORT; do
    owner=$(port_busy "$port")
    [ -n "$owner" ] && fail "Cổng $port đang bị dùng bởi $owner. Tắt tiến trình đó rồi chạy lại."
done
ok "Hai cổng còn trống"

if [ $CHECK_ONLY -eq 1 ]; then
    echo; echo "${B}Kiểm tra xong, $WARNINGS cảnh báo.${N} Chạy ./start_monitoring.sh để mở monitoring."
    exit 0
fi

step "6. Chạy backend và frontend"
mkdir -p "$LOG_DIR"
PIDS=()
cleanup() {
    trap - INT TERM EXIT
    echo; echo "Đang tắt backend và frontend ..."
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null; done
    wait 2>/dev/null
    if [ $WITH_DB -eq 1 ] && docker info >/dev/null 2>&1; then
        echo "PostgreSQL vẫn chạy. Tắt bằng: docker compose stop postgres"
    fi
}
trap 'cleanup; exit 0' INT TERM
trap cleanup EXIT

(cd "$BACKEND" && exec "$VENV/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT) \
    > "$LOG_DIR/backend.log" 2>&1 &
PIDS+=($!)
wait_http "http://127.0.0.1:$BACKEND_PORT/" "${PIDS[0]}" "Backend" "$LOG_DIR/backend.log"
ok "Backend: http://localhost:$BACKEND_PORT/docs"

(cd "$FRONTEND" && exec ./node_modules/.bin/vite --host 127.0.0.1 --port $FRONTEND_PORT --strictPort) \
    > "$LOG_DIR/frontend.log" 2>&1 &
PIDS+=($!)
wait_http "http://127.0.0.1:$FRONTEND_PORT/" "${PIDS[1]}" "Frontend" "$LOG_DIR/frontend.log"
ok "Frontend: http://localhost:$FRONTEND_PORT"

if [ $OPEN_BROWSER -eq 1 ]; then
    if command -v xdg-open >/dev/null; then xdg-open "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1 &
    elif command -v open >/dev/null; then open "http://localhost:$FRONTEND_PORT"
    fi
fi

echo
echo "${B}Monitoring đang chạy${N} ($WARNINGS cảnh báo). Log: logs/monitoring/. Nhấn Ctrl+C để tắt."
while kill -0 "${PIDS[0]}" 2>/dev/null && kill -0 "${PIDS[1]}" 2>/dev/null; do sleep 1; done
echo "${R}Một dịch vụ đã dừng.${N} Xem log trong logs/monitoring/."
exit 1
