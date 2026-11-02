#!/usr/bin/env bash
# Giữ để tương thích với tài liệu cũ; script chính là start_monitoring.sh ở thư mục gốc.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/start_monitoring.sh" --no-db "$@"
