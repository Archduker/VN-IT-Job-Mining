# -*- coding: utf-8 -*-
"""Script offline nạp URL CareerViet (Pha 1 đã khảo sát) vào UrlLedger chuẩn nhóm.

- Mặc định CHỈ ĐỌC các file `urls_c1_*.json`, `urls_c61_*.json`,
  `urls_developer_*.json` trong thư mục nguồn (mặc định `data/raw/careerviet/`).
  KHÔNG đọc `urls_c37_*` -> tổng mặc định giữ nguyên 748.
- Bật cờ `--include-c37` (mặc định TẮT) mới nạp thêm `urls_c37_*.json`.
  `source_category` của c37 được GIỮ NGUYÊN giá trị thật trong file
  (ví dụ `c37_digital_mkt`), KHÔNG hardcode/đổi tên.
- Ghi mới vào `data/careerviet/url_ledger/` (catalog_master.json + manifests/*.jsonl)
  qua UrlLedger chuẩn; không sửa giải thuật ledger.
- `source_category` thật (c1 / c61 / keyword:developer) được giữ trong file ánh xạ
  riêng `category_by_job_id.json` cạnh ledger (UrlLedgerRecord không có trường này).
- KHÔNG gọi mạng. Chỉ sync MinIO khi có cờ `--sync-minio` (mặc định tắt).
- An toàn ghi đè: nếu `category_by_job_id.json` đích đã tồn tại mà không có
  `--force`, script DỪNG trước khi ghi bất kỳ thay đổi nào.
- Chạy lần 2 (với --force): `register_url` theo url_hash là idempotent, không sinh
  record trùng lặp; chỉ cập nhật `last_seen_at`.

Cách chạy (từ repo root, PowerShell):
    python scripts/import_careerviet_urls_to_ledger.py `
        --urls-dir data/raw/careerviet `
        --storage-dir data/careerviet/url_ledger
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawlers.common.url_ledger import (  # noqa: E402
    UrlLedger,
    clean_canonical_url,
    generate_url_hash,
)

log = logging.getLogger("careerviet.import_urls")

SOURCE = "careerviet"
DEFAULT_URLS_DIR = Path("data/raw/careerviet")
DEFAULT_STORAGE_DIR = Path("data/careerviet/url_ledger")
CATEGORY_MAP_FILENAME = "category_by_job_id.json"
# Nhóm IT mặc định (luôn nạp).
URL_FILE_GLOBS = ("urls_c1_*.json", "urls_c61_*.json", "urls_developer_*.json")
# Nhóm c37: mặc định LOẠI (không chắc chắn là IT); chỉ nạp khi --include-c37.
URL_FILE_GLOB_C37 = "urls_c37_*.json"


def _resolve_globs(include_c37: bool) -> tuple[str, ...]:
    """Trả về glob patterns; thêm c37 chỉ khi include_c37=True."""
    if include_c37:
        return URL_FILE_GLOBS + (URL_FILE_GLOB_C37,)
    return URL_FILE_GLOBS


def load_url_records(
    urls_dir: Path,
    include_c37: bool = False,
) -> tuple[list[dict[str, str]], list[Path]]:
    """Đọc toàn bộ record từ các file URL được phép; lỗi nếu thiếu file hoặc sai schema.

    source_category được lấy NGUYÊN VĂN từ từng record trong file (kể cả c37);
    không suy luận hay ghi đè theo tên file.
    """
    if not urls_dir.is_dir():
        raise FileNotFoundError(f"Thư mục chứa file URL không tồn tại: {urls_dir}")

    records: list[dict[str, str]] = []
    used_files: list[Path] = []
    for pattern in _resolve_globs(include_c37):
        matched = sorted(urls_dir.glob(pattern))
        if not matched:
            raise FileNotFoundError(
                f"Không tìm thấy file nào khớp '{pattern}' trong {urls_dir}"
            )
        for fp in matched:
            payload = json.loads(fp.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
                raise ValueError(
                    f"File {fp} không phải dict có khóa 'records' (list): {type(payload).__name__}"
                )
            for i, rec in enumerate(payload["records"]):
                url = rec.get("url")
                job_id = rec.get("job_id")
                category = rec.get("source_category")
                if not url or not job_id or not category:
                    raise ValueError(
                        f"Record thiếu trường bắt buộc (url/job_id/source_category) "
                        f"tại {fp} phần tử thứ {i}"
                    )
                records.append(
                    {
                        "url": str(url),
                        "job_id": str(job_id),
                        "source_category": str(category),
                    }
                )
            used_files.append(fp)
    return records, used_files


def build_category_map(records: list[dict[str, str]]) -> tuple[dict[str, str], list[str]]:
    """job_id -> source_category; ghi nhận xung đột giá trị cho cùng một job_id."""
    mapping: dict[str, str] = {}
    collisions: list[str] = []
    for rec in records:
        jid = rec["job_id"]
        cat = rec["source_category"]
        if jid in mapping and mapping[jid] != cat:
            collisions.append(f"{jid}: {mapping[jid]} vs {cat}")
            continue
        mapping.setdefault(jid, cat)
    return mapping, collisions


def write_json_atomic(path: Path, obj: Any, force: bool) -> None:
    """Ghi JSON ra file tạm rồi thay thế atomic; dừng nếu đích tồn tại và không force."""
    if path.exists() and not force:
        raise FileExistsError(
            f"File đích đã tồn tại: {path}. Dùng --force nếu cố ý ghi đè."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def run_import(
    urls_dir: Path,
    storage_dir: Path,
    sync_minio: bool = False,
    force: bool = False,
    include_c37: bool = False,
) -> dict[str, Any]:
    """Nạp URL vào UrlLedger và ghi file ánh xạ category. Trả về thống kê."""
    urls_dir = Path(urls_dir)
    storage_dir = Path(storage_dir)
    category_map_path = storage_dir / CATEGORY_MAP_FILENAME

    # Fail-fast trước khi chạm file nào: kiểm tra đích tồn tại trước khi ghi ledger.
    if category_map_path.exists() and not force:
        raise FileExistsError(
            f"File đích đã tồn tại: {category_map_path}. Dùng --force nếu cố ý ghi đè."
        )

    records, used_files = load_url_records(urls_dir, include_c37=include_c37)

    ledger = UrlLedger(source=SOURCE, storage_dir=str(storage_dir))

    registered_new = 0
    already_present = 0
    for rec in records:
        canonical = clean_canonical_url(rec["url"])
        url_hash = generate_url_hash(canonical)
        is_new = url_hash not in ledger.records
        ledger.register_url(raw_url=rec["url"], job_id=rec["job_id"])
        if is_new:
            registered_new += 1
        else:
            already_present += 1

    ledger.save_catalog()
    manifest_path = ledger.export_daily_manifest()

    category_map, collisions = build_category_map(records)
    write_json_atomic(category_map_path, category_map, force=force)

    status_counts = Counter(r.get("status", "?") for r in ledger.records.values())
    category_counts = Counter(category_map.values())
    unique_job_ids = len({r["job_id"] for r in records})

    minio_synced = None
    if sync_minio:
        minio_synced = ledger.sync_to_minio()

    stats = {
        "files_read": [fp.as_posix() for fp in used_files],
        "records_read": len(records),
        "registered_new": registered_new,
        "already_present": already_present,
        "unique_job_ids": unique_job_ids,
        "total_ledger_records": len(ledger.records),
        "category_counts": dict(category_counts),
        "ledger_status_counts": dict(status_counts),
        "category_collisions": collisions,
        "catalog_path": ledger.catalog_file.as_posix(),
        "manifest_path": Path(manifest_path).as_posix(),
        "category_map_path": category_map_path.as_posix(),
        "minio_synced": minio_synced,
        "include_c37": include_c37,
    }
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Nap URL CareerViet (c1/c61/developer) vao UrlLedger — offline, khong mang."
    )
    parser.add_argument("--urls-dir", type=Path, default=DEFAULT_URLS_DIR,
                        help="Thư mục chứa các file urls_c1_*/urls_c61_*/urls_developer_* (mặc định: data/raw/careerviet)")
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR,
                        help="storage_dir của UrlLedger (mặc định: data/careerviet/url_ledger)")
    parser.add_argument("--sync-minio", action="store_true", default=False,
                        help="Đồng bộ ledger lên MinIO (mặc định: TẮT)")
    parser.add_argument("--force", action="store_true", default=False,
                        help="Cho phép ghi đè category_by_job_id.json đã tồn tại")
    parser.add_argument("--include-c37", action="store_true", default=False,
                        help="Nạp thêm urls_c37_*.json (mặc định: TẮT -> chỉ 748 IT)."
                             " source_category c37 giữ nguyên giá trị thật trong file.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    stats = run_import(
        urls_dir=args.urls_dir,
        storage_dir=args.storage_dir,
        sync_minio=args.sync_minio,
        force=args.force,
        include_c37=args.include_c37,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
