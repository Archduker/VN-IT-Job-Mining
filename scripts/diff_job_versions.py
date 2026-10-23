#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Công cụ so sánh Diff giữa hai phiên bản JSON của một bài đăng tuyển dụng (CDC Version Diff).
Hỗ trợ:
1. Đọc 2 file JSON (v1 vs v2).
2. So sánh từng trường nghiệp vụ (salary, requirements, deadline, etc.).
3. Hiển thị báo cáo trực quan các trường thay đổi (Before vs After) và Git-style diff cho text dài.

Cách sử dụng:
    python scripts/diff_job_versions.py --file1 data/topcv/raw/2026-10-19/12345_v1.json --file2 data/topcv/raw/2026-10-19/12345_v2.json
"""

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any, Dict


def load_job_json(file_path: str) -> Dict[str, Any]:
    path = Path(file_path)
    if not path.is_file():
        print(f"❌ File không tồn tại: {file_path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_colored_diff(text1: str, text2: str, label: str):
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    diff = list(difflib.unified_diff(lines1, lines2, fromfile=f"Trước ({label})", tofile=f"Sau ({label})", lineterm=""))
    if not diff:
        print(f"  [Không có thay đổi dòng trong {label}]")
        return
    print(f"\n--- Unified Diff ({label}) ---")
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            print(f"\033[92m{line}\033[0m")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"\033[91m{line}\033[0m")
        else:
            print(line)


def compare_jobs(v1_data: Dict[str, Any], v2_data: Dict[str, Any]):
    p1 = v1_data.get("raw_payload", v1_data)
    p2 = v2_data.get("raw_payload", v2_data)

    m1 = v1_data.get("metadata", {})
    m2 = v2_data.get("metadata", {})

    print("=" * 70)
    print("   BÁO CÁO SO SÁNH PHIÊN BẢN TIN TUYỂN DỤNG (JSON CDC DIFF)")
    print("=" * 70)
    print(f"Job ID: {m1.get('job_id') or m2.get('job_id', 'Unknown')}")
    print(f"Nguồn: {m1.get('source') or m2.get('source', 'Unknown')}")
    print(f"Phiên bản 1: v{m1.get('version', 1)} ({m1.get('scraped_at', 'N/A')}) | Hash: {m1.get('content_hash', 'N/A')[:12]}...")
    print(f"Phiên bản 2: v{m2.get('version', 2)} ({m2.get('scraped_at', 'N/A')}) | Hash: {m2.get('content_hash', 'N/A')[:12]}...")
    print("-" * 70)

    # Lọc bỏ raw_html khi so sánh field
    ignore_keys = {"raw_html", "scraped_at", "version", "content_hash"}
    keys = sorted((set(p1.keys()) | set(p2.keys())) - ignore_keys)

    changes = []
    for k in keys:
        val1 = p1.get(k)
        val2 = p2.get(k)
        if val1 != val2:
            changes.append((k, val1, val2))

    if not changes:
        print("✅ KHÔNG CÓ THAY ĐỔI NỘI DUNG NGHIỆP VỤ giữa 2 phiên bản!")
        return

    print(f"⚠️ Phát hiện {len(changes)} trường bị thay đổi:")
    for k, val1, val2 in changes:
        print(f"\n🔹 Trường: \033[1m{k.upper()}\033[0m")
        if isinstance(val1, str) and isinstance(val2, str) and (len(val1) > 100 or len(val2) > 100 or "\n" in val1 or "\n" in val2):
            print_colored_diff(val1, val2, k)
        else:
            print(f"   - Trước: \033[91m{val1}\033[0m")
            print(f"   - Sau:   \033[92m{val2}\033[0m")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="So sánh chi tiết 2 phiên bản JSON của bài đăng tuyển dụng")
    parser.add_argument("--file1", required=True, help="Đường dẫn file JSON phiên bản cũ (v1)")
    parser.add_argument("--file2", required=True, help="Đường dẫn file JSON phiên bản mới (v2)")
    args = parser.parse_args()

    v1 = load_job_json(args.file1)
    v2 = load_job_json(args.file2)
    compare_jobs(v1, v2)


if __name__ == "__main__":
    main()
