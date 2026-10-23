#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/recrawl_missing_careerviet.py
======================================
Phát hiện các bản ghi CareerViet bị thiếu dữ liệu một phần trong raw JSON,
sau đó đặt trạng thái RECHECK_DUE trong URL Ledger để trigger re-crawl Phase 2.

Chỉ các tin BỊ THIẾU mới được re-crawl — tin đầy đủ giữ nguyên trạng thái DONE.

Cách dùng:
    python scripts/recrawl_missing_careerviet.py
    python scripts/recrawl_missing_careerviet.py --raw-dir data/careerviet/raw
    python scripts/recrawl_missing_careerviet.py --dry-run        # Chỉ scan, không cập nhật ledger
"""
import argparse
import json
import glob
import sys
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from crawlers.common.url_ledger import UrlLedger

# ─── Các tiêu chí phát hiện thiếu dữ liệu ───────────────────────────────────
# Mỗi key là tên trường, value là hàm kiểm tra raw_payload.
# Trả về True = có dữ liệu (OK), False = thiếu.
MISSING_CHECKS: dict[str, callable] = {
    "location": lambda rp: bool(rp.get("map")) or any(
        any(k in l.lower() for k in ["địa điểm", "nơi làm việc"])
        for l in (rp.get("detail-box") or [])
    ),
    "education": lambda rp: any(
        any(k in l.lower() for k in ["bằng cấp", "trình độ", "học vấn"])
        for l in (rp.get("detail-box") or [])
    ) or any(
        any(k in l.lower() for k in ["bằng cấp", "trình độ", "học vấn"])
        for l in _flatten_detail_row(rp)
    ),
    "age": lambda rp: any(
        any(k in l.lower() for k in ["độ tuổi", " tuổi"])
        for l in (rp.get("detail-box") or [])
    ) or any(
        any(k in l.lower() for k in ["độ tuổi", " tuổi"])
        for l in _flatten_detail_row(rp)
    ),
}


def _flatten_detail_row(rp: dict) -> list[str]:
    """Lấy tất cả text trong detail-row dict để kiểm tra."""
    result = []
    for v in (rp.get("detail-row") or {}).values():
        if isinstance(v, str):
            result.append(v)
        elif isinstance(v, list):
            result.extend(str(x) for x in v)
    return result


def scan_missing(raw_dir: str) -> dict[str, list[str]]:
    """Scan toàn bộ raw JSON và trả về {job_id: [danh sách trường thiếu]}."""
    report: dict[str, list[str]] = {}
    total = 0
    for path in glob.glob(f"{raw_dir}/**/*.json", recursive=True):
        total += 1
        try:
            with open(path, encoding="utf-8") as f:
                env = json.load(f)
        except Exception as e:
            print(f"  [WARN] Không đọc được {path}: {e}")
            continue

        rp = env.get("raw_payload", {})
        jid = env.get("metadata", {}).get("job_id", "unknown")

        missing_fields = [name for name, check in MISSING_CHECKS.items() if not check(rp)]
        if missing_fields:
            report[jid] = missing_fields

    print(f"[scan] Đã quét {total} file. Phát hiện {len(report)} bản ghi thiếu dữ liệu.")
    return report


def mark_recheck_due(missing: dict[str, list[str]], ledger: UrlLedger) -> int:
    """Đặt RECHECK_DUE cho các job_id thiếu trong ledger. Trả về số record đã đánh dấu."""
    marked = 0
    missing_ids = set(missing.keys())
    for url_hash, rec in ledger.records.items():
        if rec.get("job_id") in missing_ids:
            rec["status"] = "RECHECK_DUE"
            rec["error_log"] = f"Partial data missing: {missing[rec['job_id']]} — set by recrawl_missing_careerviet.py @ {datetime.now(timezone.utc).isoformat()}"
            marked += 1
    return marked


def main():
    parser = argparse.ArgumentParser(description="Scan và mark RECHECK_DUE cho CareerViet records thiếu dữ liệu.")
    parser.add_argument("--raw-dir", default="data/careerviet/raw", help="Thư mục raw JSON (default: data/careerviet/raw)")
    parser.add_argument("--ledger-dir", default="data/careerviet/url_ledger", help="Thư mục URL Ledger")
    parser.add_argument("--output", default="missing_report.json", help="File output báo cáo (default: missing_report.json)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ scan, không cập nhật ledger")
    args = parser.parse_args()

    # 1. Scan missing
    print(f"[1/3] Scan raw JSON tại: {args.raw_dir}")
    missing = scan_missing(args.raw_dir)

    # 2. Ghi báo cáo
    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(missing, f, ensure_ascii=False, indent=2)
    print(f"[2/3] Đã lưu báo cáo → {out_path}  ({len(missing)} job cần re-crawl)")

    if not missing:
        print("[✓] Không có bản ghi nào thiếu dữ liệu. Không cần re-crawl.")
        return

    if args.dry_run:
        print("[dry-run] Bỏ qua cập nhật ledger. Chi tiết xem missing_report.json.")
        return

    # 3. Cập nhật ledger
    print(f"[3/3] Cập nhật URL Ledger tại: {args.ledger_dir}")
    ledger = UrlLedger(source="careerviet", storage_dir=args.ledger_dir)
    marked = mark_recheck_due(missing, ledger)
    ledger.save_catalog()

    print(f"[✓] Đã đặt RECHECK_DUE cho {marked}/{len(missing)} URL trong ledger.")
    print()
    print("Bước tiếp theo — chạy re-crawl Phase 2:")
    print("  python crawlers/sources/careerviet/crawler.py \\")
    print("    --phase detail \\")
    print("    --ledger-dir data/careerviet/url_ledger \\")
    print("    --raw-dir data/careerviet/raw")


if __name__ == "__main__":
    main()
