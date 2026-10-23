#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thống kê chất lượng tầng thô (Raw As-Is) cho nguồn CareerViet - envelope mới.

Bản viết lại này đọc các RAW ENVELOPE ``{metadata, raw_payload}`` mà
``crawlers/sources/careerviet/crawler.py`` sinh ra (mỗi tin 1 file JSON,
tên ``{job_id}_v{version}.json``), và báo cáo:

1. Tổng số envelope đã đọc.
2. Tỷ lệ rỗng của TỪNG khóa trong ``raw_payload`` (title, job-company-name,
   detail-box, detail-row, job-tags, map, "Ngành nghề", job-posting-schema).
   "Rỗng" = thiếu khóa, hoặc giá trị falsy (None / "" / [] / {}).
3. Số tin CÓ JSON-LD JobPosting (khóa ``job-posting-schema`` khác rỗng).
4. Phân bố số ``version`` (CDC) theo ``metadata.version``.

CHỈ ĐỌC, KHÔNG GHI ĐÈ input. Mặc định in ra stdout; truyền ``--out`` thì ghi
sang MỘT FILE MỚI (từ chối ghi đè nếu file đã tồn tại).

Cách dùng:
    python scripts/careerviet_raw_stats.py --raw-dir data/careerviet/raw
    python scripts/careerviet_raw_stats.py --raw-dir data/careerviet/_dryrun/raw
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Khóa raw_payload bắt buộc theo envelope Careerviet (thứ tự để in báo cáo ổn định).
PAYLOAD_KEYS: tuple[str, ...] = (
    "title",
    "job-company-name",
    "detail-box",
    "detail-row",
    "job-tags",
    "map",
    "Ngành nghề",
    "job-posting-schema",
)
JSONLD_KEY = "job-posting-schema"


def is_empty(value: Any) -> bool:
    """Rỗng = None, chuỗi trống, list/dict rỗng (hoặc khóa thiếu -> mặc định None)."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def find_envelope_files(raw_dir: Path) -> list[Path]:
    """Mọi file ``*.json`` dưới ``raw_dir`` (đệ quy, bắt cả phân vùng dt=/ngày)."""
    return sorted(p for p in raw_dir.rglob("*.json") if p.is_file())


def load_envelopes(files: list[Path]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Đọc envelope; trả (danh_sach_hop_le, danh_sach_loi_<ten_file>_<nguyen_nhan>).

    Một file hợp lệ phải là dict có ``raw_payload`` (kiểm tra lỏng để không âm
    thầm bỏ qua dữ liệu thật; file checkpoint/khác schema sẽ bị liệt vào lỗi).
    """
    envelopes: list[dict] = []
    errors: list[tuple[str, str]] = []
    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append((fp.name, f"khong doc duoc JSON: {exc}"))
            continue
        if not isinstance(data, dict) or "raw_payload" not in data:
            errors.append((fp.name, "khong phai envelope (thieu khoa raw_payload)"))
            continue
        envelopes.append(data)
    return envelopes, errors


def compute_stats(envelopes: list[dict]) -> dict[str, Any]:
    """Tính tổng số envelope, tỷ lệ rỗng từng khóa, số có JSON-LD, phân bố version."""
    total = len(envelopes)
    empty_counts: dict[str, int] = {}
    for key in PAYLOAD_KEYS:
        empty_counts[key] = sum(
            1 for env in envelopes if is_empty(env["raw_payload"].get(key))
        )
    missing_rate = {
        key: (empty_counts[key] / total if total else 0.0) for key in PAYLOAD_KEYS
    }

    jsonld_present = sum(
        1 for env in envelopes if not is_empty(env["raw_payload"].get(JSONLD_KEY))
    )

    version_counter: Counter = Counter(
        env.get("metadata", {}).get("version") for env in envelopes
    )

    return {
        "total_envelopes": total,
        "empty_counts": empty_counts,
        "missing_rate": missing_rate,
        "jsonld_present": jsonld_present,
        "jsonld_missing": total - jsonld_present,
        "version_distribution": dict(sorted(version_counter.items(), key=lambda kv: str(kv[0]))),
    }


def format_report(stats: dict[str, Any], skipped: list[tuple[str, str]]) -> str:
    """Định dạng báo cáo thành văn bản ASCII-anh (khong ky tu CJK)."""
    total = stats["total_envelopes"]
    lines: list[str] = []
    lines.append("=== CAREERVIET RAW-ENVELOPE STATS ===")
    lines.append(f"tong_so_envelope = {total}")
    if skipped:
        lines.append(f"so_file_bo_qua_khong_phai_envelope = {len(skipped)}")

    lines.append("")
    lines.append("-- Ty le rong tung khoa raw_payload --")
    lines.append(f"{'key':<20}{'rong':>8}{'le':>10}")
    for key in PAYLOAD_KEYS:
        cnt = stats["empty_counts"][key]
        rate = stats["missing_rate"][key]
        lines.append(f"{key:<20}{cnt:>8}{rate:>9.1%}")

    lines.append("")
    lines.append("-- JSON-LD JobPosting --")
    lines.append(f"co_jsonld    = {stats['jsonld_present']}")
    lines.append(f"khong_jsonld = {stats['jsonld_missing']}")

    lines.append("")
    lines.append("-- Phan bo version (metadata.version) --")
    for ver, cnt in stats["version_distribution"].items():
        lines.append(f"version {ver!r}: {cnt}")

    if skipped:
        lines.append("")
        lines.append("-- File bo qua --")
        for name, reason in skipped:
            lines.append(f"  {name}: {reason}")

    return "\n".join(lines)


def run(raw_dir: Path) -> tuple[str, dict[str, Any]]:
    """Đọc toàn bộ envelope trong ``raw_dir`` và trả (bao_cao, stats)."""
    files = find_envelope_files(raw_dir)
    envelopes, errors = load_envelopes(files)
    stats = compute_stats(envelopes)
    report = format_report(stats, errors)
    return report, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Thống kê raw-envelope Careerviet (chi doc).")
    parser.add_argument(
        "--raw-dir",
        default="data/careerviet/raw",
        help="Thu muc chua envelope *.json (de quy). Mac dinh: data/careerviet/raw",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="File MOI de ghi bao cao (mac dinh: in stdout). Tu choi ghi de.",
    )
    args = parser.parse_args(argv)

    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists():
        print(f"KHONG CO thu muc: {raw_dir}", file=sys.stderr)
        return 2

    report, _stats = run(raw_dir)

    if args.out:
        out_path = Path(args.out)
        if out_path.exists():
            print(f"File dich da ton tai: {out_path}. Khong ghi de.", file=sys.stderr)
            return 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report + "\n", encoding="utf-8")
        print(f"Da ghi bao cao -> {out_path}", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
