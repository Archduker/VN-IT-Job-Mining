#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dựng lại bản ghi URL Ledger từ các file raw đã cào (SCRAPE-4).

Dùng khi raw đã lên R2 nhưng ledger chưa được đồng bộ, ví dụ crawler chạy không bật sync rồi raw được
đẩy riêng. Không có ledger đúng thì lần chạy detail sau sẽ cào lại các tin đó.

    python scripts/reconcile_ledger_from_raw.py --source topdev          # chạy thử, chỉ in kế hoạch
    python scripts/reconcile_ledger_from_raw.py --source all --apply     # ghi ledger trên máy
    python scripts/reconcile_ledger_from_raw.py --source topdev --push   # ghi trên máy rồi đẩy lên R2
    python scripts/reconcile_ledger_from_raw.py --source vietnamworks \
        --register-batch-missing data/vietnamworks/raw/2026-10-16/raw_batch.json [--apply | --push]

Luật:
    * job_id chưa có trong ledger -> tạo bản ghi DONE từ source_url.
    * snapshot mới hơn last_scraped_at quá 1 giờ -> cập nhật DONE, last_scraped_at, content_hash,
      latest_version = max(cũ, version của snapshot).
    * Không xóa bản ghi, không đụng bản ghi CLOSED.
    * Bản ghi repost mà có snapshot mới hơn: lần cào đó đã lưu raw, tức crawler coi là tin thật, nên cập nhật
      như trên và bỏ repost_of_url_hash. Repost không có snapshot mới hơn thì giữ nguyên.
    * --push sao lưu ledger hiện tại trên R2 vào data/<nguồn>/url_ledger/backups/ trước khi đẩy.
    * --register-batch-missing <file batch>: tin trong file batch cũ (list envelope) mà chưa có file raw riêng và
      chưa có trong ledger thì đăng ký PENDING (chưa có hash) để pha detail cào lại bằng crawler hiện tại.
      File batch không được sửa và không được đẩy lên R2.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from collection.common.r2_storage import LAKEHOUSE_SOURCES, to_r2_key  # noqa: E402
from collection.common.url_ledger import UrlLedger, clean_canonical_url, generate_url_hash  # noqa: E402
from collection.common.utils import parse_iso_utc  # noqa: E402

LAG = timedelta(hours=1)
SKIP_DIRS = {"_index", "_quality", "_listing"}


_parse_time = parse_iso_utc  # collection/common/utils.py


def latest_snapshots(raw_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Snapshot mới nhất theo job_id. Bỏ file batch cũ (list) và thư mục phụ."""
    latest: Dict[str, Dict[str, Any]] = {}
    if not raw_dir.exists():
        return latest
    for path in sorted(raw_dir.rglob("*.json")):
        if SKIP_DIRS & set(path.relative_to(raw_dir).parts):
            continue
        try:
            env = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(env, dict) or not isinstance(env.get("metadata"), dict):
            continue
        meta = env["metadata"]
        job_id = str(meta.get("job_id") or meta.get("source_job_id") or "").strip()
        scraped = _parse_time(meta.get("scraped_at"))
        if not job_id or not scraped:
            continue
        snap = {
            "job_id": job_id,
            "scraped_at": scraped,
            "version": int(meta.get("version") or 1),
            "content_hash": meta.get("content_hash"),
            "source_url": meta.get("source_url") or meta.get("url"),
            "file": str(path.relative_to(raw_dir)),
        }
        cur = latest.get(job_id)
        if cur is None or (snap["scraped_at"], snap["version"]) > (cur["scraped_at"], cur["version"]):
            latest[job_id] = snap
    return latest


def plan(ledger: UrlLedger, snapshots: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_job: Dict[str, List[str]] = {}
    for url_hash, rec in ledger.records.items():
        jid = str(rec.get("job_id") or "").strip()
        if jid:
            by_job.setdefault(jid, []).append(url_hash)
    result: Dict[str, List[Dict[str, Any]]] = {"create": [], "update": [], "skip_closed": [], "skip_repost": []}
    for job_id, snap in sorted(snapshots.items()):
        hashes = by_job.get(job_id, [])
        if not hashes:
            if snap["source_url"]:
                result["create"].append({"snap": snap})
            continue
        # Nhiều URL cùng job_id: ưu tiên bản ghi trùng URL của snapshot, rồi bản ghi không phải repost
        snap_hash = generate_url_hash(clean_canonical_url(snap["source_url"])) if snap["source_url"] else None
        hashes.sort(key=lambda h: (h != snap_hash, bool(ledger.records[h].get("repost_of_url_hash"))))
        url_hash = hashes[0]
        rec = ledger.records[url_hash]
        if rec.get("status") == "CLOSED":
            result["skip_closed"].append({"snap": snap, "url_hash": url_hash})
            continue
        last = _parse_time(rec.get("last_scraped_at"))
        if rec.get("repost_of_url_hash") and not (last is None or snap["scraped_at"] - last > LAG):
            result["skip_repost"].append({"snap": snap, "url_hash": url_hash})
            continue
        if last is None or snap["scraped_at"] - last > LAG or rec.get("status") != "DONE":
            if last is not None and snap["scraped_at"] <= last:
                continue  # bản ghi FAILED/PENDING cào sau snapshot: để crawler xử lý
            result["update"].append({"snap": snap, "url_hash": url_hash})
    return result


def apply_plan(ledger: UrlLedger, source: str, actions: Dict[str, List[Dict[str, Any]]]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for item in actions["create"]:
        snap = item["snap"]
        url = clean_canonical_url(snap["source_url"])
        url_hash = generate_url_hash(url)
        ledger.records[url_hash] = {
            "url_hash": url_hash, "canonical_url": url, "source": source, "job_id": snap["job_id"],
            "discovered_at": snap["scraped_at"].isoformat(), "status": "DONE",
            "last_seen_at": snap["scraped_at"].isoformat(), "last_scraped_at": snap["scraped_at"].isoformat(),
            "content_hash": snap["content_hash"], "latest_version": snap["version"],
            "error_log": None, "retry_count": 0, "reconciled_from_raw_at": now,
        }
    for item in actions["update"]:
        snap, rec = item["snap"], ledger.records[item["url_hash"]]
        rec.update({
            "status": "DONE", "last_scraped_at": snap["scraped_at"].isoformat(),
            "content_hash": snap["content_hash"] or rec.get("content_hash"),
            "latest_version": max(int(rec.get("latest_version") or 0), snap["version"]),
            "error_log": None, "reconciled_from_raw_at": now,
        })
        if rec.pop("repost_of_url_hash", None):
            rec["reconciled_cleared_repost"] = True
    ledger.by_job_id = ledger._build_job_id_index()
    ledger.save_catalog()


def backup_remote(source: str, ledger_dir: Path) -> Optional[Path]:
    from sync_cloud_lakehouse import get_s3_client

    s3, bucket, _ = get_s3_client()
    key = to_r2_key(f"url_ledger/{source}/catalog_master.json")
    try:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except Exception as exc:
        print(f"  [{source}] không tải được {key} để sao lưu: {exc}")
        return None
    dest = ledger_dir / "backups" / f"catalog_master_r2_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return dest


def run_source(source: str, data_dir: Path, apply: bool, push: bool) -> Dict[str, int]:
    ledger_dir = data_dir / source / "url_ledger"
    ledger = UrlLedger(source=source, storage_dir=str(ledger_dir))
    actions = plan(ledger, latest_snapshots(data_dir / source / "raw"))
    counts = {k: len(v) for k, v in actions.items()}
    print(f"[{source}] tạo mới {counts['create']}, cập nhật {counts['update']}, "
          f"bỏ qua CLOSED {counts['skip_closed']}, bỏ qua repost {counts['skip_repost']}")
    for kind in ("create", "update"):
        for item in actions[kind][:5]:
            snap = item["snap"]
            print(f"    {kind}: {snap['job_id']} v{snap['version']} cào lúc {snap['scraped_at']:%Y-%m-%d %H:%M} ({snap['file']})")
    if (apply or push) and (counts["create"] or counts["update"]):
        apply_plan(ledger, source, actions)
        print(f"  [{source}] đã ghi {ledger.catalog_file}")
    if push:
        backup = backup_remote(source, ledger_dir)
        if backup is None:
            print(f"  [{source}] dừng đẩy vì chưa sao lưu được bản trên R2")
            return counts
        print(f"  [{source}] đã sao lưu bản trên R2 vào {backup}")
        ledger.sync_final()
        print(f"  [{source}] đã đẩy ledger lên R2")
    return counts


def _batch_title(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("jobTitle", "title", "job_title"):
        if payload.get(key):
            return str(payload[key])
    return None


def register_batch_missing(source: str, data_dir: Path, batch_file: Path, apply: bool, push: bool) -> List[Dict[str, Any]]:
    """Đăng ký PENDING cho tin trong file batch cũ chưa có file raw riêng và chưa có trong ledger."""
    ledger_dir = data_dir / source / "url_ledger"
    ledger = UrlLedger(source=source, storage_dir=str(ledger_dir))
    if push:
        ledger.pull_from_r2()  # đăng ký trên bản mới nhất, để sync_final không đè bản trên R2
    has_file = set(latest_snapshots(data_dir / source / "raw"))  # file từng tin trên máy (khớp với R2 sau --download)
    in_ledger = {str(r.get("job_id") or "").strip() for r in ledger.records.values()}
    in_ledger |= {r.get("url_hash") for r in ledger.records.values()}
    found: List[Dict[str, Any]] = []
    for env in json.loads(batch_file.read_text(encoding="utf-8")):
        meta, payload = env.get("metadata") or {}, env.get("raw_payload") or {}
        job_id, src_url = str(meta.get("job_id") or "").strip(), meta.get("source_url") or meta.get("url")
        if not job_id or not src_url or job_id in has_file or job_id in in_ledger:
            continue
        if generate_url_hash(clean_canonical_url(src_url)) in in_ledger:
            continue
        found.append({"job_id": job_id, "url": src_url, "title": _batch_title(payload)})
        in_ledger.add(job_id)
    print(f"[{source}] {batch_file.name}: {len(found)} tin chưa có file riêng và chưa có trong ledger")
    for item in found[:5]:
        print(f"    PENDING: {item['job_id']} {item['title']}")
    if not (apply or push) or not found:
        return found
    rel = str(batch_file.resolve().relative_to(data_dir.resolve().parent)) if batch_file.resolve().is_relative_to(
        data_dir.resolve().parent) else str(batch_file)
    for item in found:
        ledger.register_url(item["url"], job_id=item["job_id"], preliminary_title=item["title"])
        url_hash = generate_url_hash(clean_canonical_url(item["url"]))
        ledger.records[url_hash]["registered_from_batch"] = rel
    ledger.save_catalog()
    print(f"  [{source}] đã ghi {ledger.catalog_file}")
    if push:
        backup = backup_remote(source, ledger_dir)
        if backup is None:
            print(f"  [{source}] dừng đẩy vì chưa sao lưu được bản trên R2")
            return found
        print(f"  [{source}] đã sao lưu bản trên R2 vào {backup}")
        ledger.sync_final()
        print(f"  [{source}] đã đẩy ledger lên R2")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="Tên nguồn hoặc all")
    parser.add_argument("--apply", action="store_true", help="Ghi ledger trên máy")
    parser.add_argument("--push", action="store_true", help="Ghi trên máy, sao lưu bản trên R2, rồi đẩy lên R2")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--register-batch-missing", type=Path, metavar="FILE_BATCH",
                        help="Đăng ký PENDING cho tin trong file batch cũ chưa có file riêng và chưa có trong ledger")
    args = parser.parse_args()
    sources = list(LAKEHOUSE_SOURCES) if args.source == "all" else [args.source]
    unknown = [s for s in sources if s not in LAKEHOUSE_SOURCES]
    if unknown:
        parser.error(f"Nguồn không hợp lệ: {unknown}")
    if not (args.apply or args.push):
        print("CHẠY THỬ: không ghi gì. Thêm --apply để ghi trên máy, --push để đẩy lên R2.")
    if args.register_batch_missing:
        if len(sources) != 1:
            parser.error("--register-batch-missing cần đúng một --source")
        register_batch_missing(sources[0], args.data_dir.resolve(), args.register_batch_missing, args.apply, args.push)
        return 0
    for source in sources:
        run_source(source, args.data_dir.resolve(), args.apply, args.push)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
