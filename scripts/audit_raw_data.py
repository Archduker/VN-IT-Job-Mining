#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra chất lượng dữ liệu cào (raw + URL Ledger) trước khi trực quan hóa và pre-processing.

Chỉ đọc: không sửa data/, không ghi lên R2. Kết quả ghi ra reports/data_audit_<ngày>.md và .json.

    python scripts/audit_raw_data.py                 # đọc data/ trên máy
    python scripts/audit_raw_data.py --r2            # thêm kiểm tra layout key trên R2 (chỉ liệt kê)
    python scripts/audit_raw_data.py --data-dir /tmp/x --out-dir /tmp/y
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "monitoring" / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.core import data_paths  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.feature_targets import FEATURES, RAW_PATHS  # noqa: E402
from app.services.source_report_service import _match_paths, _value_at  # noqa: E402
from collection.common.url_ledger import is_due_for_recrawl  # noqa: E402
from collection.common.utils import parse_iso_utc  # noqa: E402

SOURCES: List[str] = list(settings.SUPPORTED_SOURCES)
# Thư mục cấp 1 hợp lệ trong data/ ngoài thư mục của 8 nguồn
KNOWN_LAYERS = {"integration", "quality", "staging", "curated", "url_ledger"}
CANONICAL_R2_LAYERS = {"raw", "url_ledger", "staging", "curated"}
BLOCK_MARKERS = ("just a moment", "captcha", "cf-chl", "access denied", "attention required", "verify you are human")
MIN_TEXT_CHARS = 300  # tổng độ dài chữ trong payload dưới mức này coi là trang cào lỗi
BLOCKED_MAX_CHARS = 1000  # JD thật có thể nhắc "captcha"; chỉ coi là trang chặn khi payload ngắn
LEDGER_LAG = timedelta(hours=1)  # raw mới hơn ledger quá mức này nghĩa là ledger chưa được đồng bộ


_parse_time = parse_iso_utc  # collection/common/utils.py


def _text_len(node: Any) -> int:
    if isinstance(node, str):
        return len(node.strip())
    if isinstance(node, dict):
        return sum(_text_len(v) for v in node.values())
    if isinstance(node, list):
        return sum(_text_len(v) for v in node)
    return 0


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _day_of(path: Path, meta: Dict[str, Any]) -> Optional[date]:
    try:
        return date.fromisoformat(path.parent.name)
    except ValueError:
        pass
    stamp = meta.get("scraped_at") or meta.get("crawled_at")
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).date() if stamp else None
    except ValueError:
        return None


def check_layout(data_dir: Path) -> Dict[str, Any]:
    """File nằm ngoài data/<nguồn>/raw/<YYYY-MM-DD>/, monitoring sẽ không đọc tới."""
    unexpected_dirs = {}
    misplaced_by_source: Counter = Counter()
    if data_dir.exists():
        for child in sorted(p for p in data_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
            if child.name in SOURCES or child.name in KNOWN_LAYERS:
                continue
            files = [f for f in child.rglob("*") if f.is_file()]
            unexpected_dirs[child.name] = len(files)
            for f in files:
                hit = next((part for part in f.relative_to(child).parts if part in SOURCES), None)
                if hit:
                    misplaced_by_source[hit] += 1
    off_date = {}
    for src in SOURCES:
        raw_dir = data_dir / src / "raw"
        if not raw_dir.exists():
            continue
        bad = [f for f in raw_dir.rglob("*.json") if not _is_date_dir(f.parent.name)]
        if bad:
            off_date[src] = {"count": len(bad), "folders": sorted({str(f.parent.relative_to(raw_dir)) for f in bad})[:5]}
    return {"unexpected_dirs": unexpected_dirs, "misplaced_by_source": dict(misplaced_by_source),
            "raw_outside_date_folder": off_date}


def _is_date_dir(name: str) -> bool:
    try:
        date.fromisoformat(name)
        return True
    except ValueError:
        return False


def check_r2_layout(keys: Iterable[str]) -> Dict[str, Any]:
    layers: Counter = Counter()
    off_layout: Counter = Counter()
    samples: Dict[str, str] = {}
    for key in keys:
        parts = key.split("/")
        if parts[-1].startswith("."):
            continue  # file giữ chỗ như .keep
        layers[parts[0]] += 1
        if parts[0] in ("raw", "url_ledger", "staging") and (len(parts) < 2 or parts[1] not in SOURCES):
            bucket = f"{parts[0]}/{parts[1] if len(parts) > 1 else ''}"
            off_layout[bucket] += 1
            samples.setdefault(bucket, key)
    return {
        "layers": dict(layers),
        "non_canonical_layers": {k: v for k, v in layers.items() if k not in CANONICAL_R2_LAYERS},
        "keys_outside_source_folders": dict(off_layout),
        "examples": samples,
    }


def audit_source(src: str, today: date) -> Dict[str, Any]:
    files = 0
    parse_errors: List[str] = []
    files_without_envelope: List[str] = []
    envelopes = 0
    empty_payload = 0
    by_job: Dict[str, set] = defaultdict(set)  # chỉ file một envelope, để đếm trùng
    raw_jobs: set = set()
    latest_scrape: Dict[str, datetime] = {}
    batch_files = 0
    batch_job_ids: set = set()
    by_url: Dict[str, set] = defaultdict(set)
    by_hash: Counter = Counter()
    per_day: Counter = Counter()
    feature_hits: Counter = Counter()
    no_title = 0
    short_text = 0
    blocked = 0
    suspicious: List[str] = []

    for _, path in data_paths.iter_raw_files(src):
        files += 1
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            parse_errors.append(f"{path.name}: {str(exc)[:80]}")
            continue
        items = content if isinstance(content, list) else [content]
        envs = [i for i in items if isinstance(i, dict) and ("raw_payload" in i or "raw" in i)]
        if not envs:
            files_without_envelope.append(path.name)
            continue
        is_batch = isinstance(content, list)
        batch_files += is_batch
        for env in envs:
            envelopes += 1
            meta = env.get("metadata") or env.get("_meta") or {}
            payload = env.get("raw_payload") or env.get("raw") or {}
            key = "raw_payload" if "raw_payload" in env else "raw"
            job_id = str(meta.get("job_id") or meta.get("source_job_id") or "")
            if job_id:
                raw_jobs.add(job_id)
                if is_batch:
                    batch_job_ids.add(job_id)  # file batch cũ gom nhiều tin, không tính là trùng
                else:
                    by_job[job_id].add(str(path.relative_to(settings.DATA_DIR)))
                # File batch cũ không phải lần cào của crawler hiện tại; tin chỉ có trong batch được đăng ký
                # PENDING để cào lại (reconcile --register-batch-missing), nên không tính vào "ledger chậm hơn raw"
                scraped = None if is_batch else _parse_time(meta.get("scraped_at") or meta.get("crawled_at"))
                if scraped and (job_id not in latest_scrape or scraped > latest_scrape[job_id]):
                    latest_scrape[job_id] = scraped
            url = meta.get("source_url") or meta.get("url")
            if url:
                by_url[str(url).split("?")[0].rstrip("/")].add(job_id)
            digest = meta.get("content_hash") or hashlib.sha256(
                json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            by_hash[digest] += 1
            day = _day_of(path, meta)
            if day:
                per_day[day] += 1
            if not payload:
                empty_payload += 1
                continue
            for feature in FEATURES:
                specs = RAW_PATHS[src].get(feature["code"], [])
                if specs and any(_filled(_value_at(env, p)) for spec in specs for p in _match_paths(payload, spec, (key,))):
                    feature_hits[feature["code"]] += 1
            title = payload.get("title") or payload.get("job-title") or payload.get("jobTitle")
            if not _filled(title):
                no_title += 1
            text = json.dumps(payload, ensure_ascii=False).lower()
            title_text = str(title or "").lower()
            if (any(m in title_text for m in BLOCK_MARKERS)
                    or (any(m in text[:20000] for m in BLOCK_MARKERS) and _text_len(payload) < BLOCKED_MAX_CHARS)):
                blocked += 1
                if len(suspicious) < 5:
                    suspicious.append(f"{path.name} (có dấu hiệu trang chặn bot)")
            elif _text_len(payload) < MIN_TEXT_CHARS:
                short_text += 1
                if len(suspicious) < 5:
                    suspicious.append(f"{path.name} (chỉ {_text_len(payload)} ký tự)")

    dup_jobs = {j: sorted(paths) for j, paths in by_job.items() if len(paths) > 1}
    dup_urls = {u: sorted(j for j in ids if j) for u, ids in by_url.items() if len({j for j in ids if j}) > 1}
    dup_hash = sum(n - 1 for n in by_hash.values() if n > 1)

    days = sorted(per_day)
    gaps = []
    if days:
        cur = days[0]
        while cur <= days[-1]:
            if per_day[cur] == 0:
                gaps.append(cur.isoformat())
            cur += timedelta(days=1)

    records = data_paths.load_catalog_records(src)
    status = Counter(r.get("status", "UNKNOWN") for r in records)
    errors = Counter(str(r.get("error_log"))[:90] for r in records if r.get("status") == "FAILED" and r.get("error_log"))
    due = sum(1 for r in records if r.get("status") == "DONE"
              and is_due_for_recrawl(r.get("last_scraped_at") or r.get("last_crawled_at")))
    ledger_jobs = {str(r.get("job_id")) for r in records if r.get("job_id")}
    # Repost (cùng nội dung với URL khác) được đánh DONE nhưng cố ý không sinh snapshot mới
    reposts = sum(1 for r in records if r.get("status") == "DONE" and r.get("repost_of_url_hash"))
    done_jobs = {str(r.get("job_id")) for r in records
                 if r.get("status") == "DONE" and r.get("job_id") and not r.get("repost_of_url_hash")}
    # Ledger chậm hơn raw: có snapshot cào sau lần cập nhật cuối của ledger, tức lần chạy đó chưa đồng bộ ledger
    ledger_last: Dict[str, Optional[datetime]] = {}
    for r in records:
        # CLOSED không bao giờ được mở lại (collection/CLAUDE.md), nên raw mới hơn của tin CLOSED không tính là lệch
        if r.get("job_id") and r.get("status") != "CLOSED":
            stamp = _parse_time(r.get("last_scraped_at") or r.get("last_crawled_at"))
            prev = ledger_last.get(str(r["job_id"]))
            ledger_last[str(r["job_id"])] = max(filter(None, (prev, stamp)), default=None)
    behind = sorted(j for j, scraped in latest_scrape.items()
                    if j in ledger_last and (ledger_last[j] is None or scraped - ledger_last[j] > LEDGER_LAG))
    last_raw = max(latest_scrape.values(), default=None)
    last_ledger = max(filter(None, ledger_last.values()), default=None)

    return {
        "source": src,
        "raw": {
            "files": files, "envelopes": envelopes, "unique_job_ids": len(raw_jobs),
            "parse_errors": len(parse_errors), "parse_error_examples": parse_errors[:5],
            "files_without_envelope": len(files_without_envelope), "files_without_envelope_examples": files_without_envelope[:5],
            "empty_payload": empty_payload,
            "legacy_batch_files": batch_files, "batch_job_ids": len(batch_job_ids),
            "batch_job_ids_also_single": len(batch_job_ids & set(by_job)),
        },
        "duplicates": {
            "job_id_in_many_files": len(dup_jobs), "examples": dict(list(dup_jobs.items())[:3]),
            "url_with_many_job_ids": len(dup_urls), "url_examples": dict(list(dup_urls.items())[:3]),
            "same_content_extra_copies": dup_hash,
        },
        "ledger": {
            "exists": bool(records), "total": len(records), "status": dict(status),
            "done_due_for_recrawl": due, "top_failed_reasons": errors.most_common(5),
            "reposts": reposts,
            "done_without_raw": len(done_jobs - raw_jobs) if raw_jobs else None,
            "raw_not_in_ledger": len(raw_jobs - ledger_jobs) if records else None,
            "raw_not_in_ledger_examples": sorted(raw_jobs - ledger_jobs)[:5] if records else [],
            "ledger_behind_raw": len(behind) if records else None,
            "ledger_behind_examples": behind[:5] if records else [],
            "last_raw_scrape": last_raw.isoformat() if last_raw else None,
            "last_ledger_update": last_ledger.isoformat() if last_ledger else None,
        },
        "timeline": {
            "first_day": days[0].isoformat() if days else None,
            "last_day": days[-1].isoformat() if days else None,
            "days_since_last": (today - days[-1]).days if days else None,
            "per_day": {d.isoformat(): per_day[d] for d in days},
            "gap_days": gaps,
        },
        # None: nguồn không có trường này trên trang (RAW_PATHS rỗng) hoặc không có envelope
        "features": {
            f["code"]: round(100 * feature_hits[f["code"]] / envelopes, 1)
            if envelopes and RAW_PATHS[src].get(f["code"]) else None for f in FEATURES
        },
        "suspect": {"no_title": no_title, "blocked_page": blocked, "short_text": short_text, "examples": suspicious},
    }


def find_issues(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Gom vấn đề, xếp theo mức: cao (mất hoặc sai dữ liệu), trung bình, thấp."""
    issues: List[Dict[str, str]] = []

    def add(level: str, source: str, text: str) -> None:
        issues.append({"level": level, "source": source, "text": text})

    layout = result["layout"]
    for name, count in layout["unexpected_dirs"].items():
        detail = ", ".join(f"{s}: {n}" for s, n in sorted(layout["misplaced_by_source"].items())) if name == "crawling" else ""
        # Chỉ mức cao khi thư mục lạ chứa raw của nguồn (monitoring bỏ sót tin); còn lại là file phụ tải từ R2
        add("cao" if detail else "trung bình", "chung",
            f"`data/{name}/` có {count} file nằm ngoài layout chuẩn nên monitoring và pipeline không đọc"
            + (f" (theo nguồn: {detail})" if detail else ""))
    for src, info in layout["raw_outside_date_folder"].items():
        add("thấp", src, f"{info['count']} file raw không nằm trong thư mục ngày (ví dụ `{info['folders'][0]}`)")
    r2 = result.get("r2")
    if r2:
        for bucket, count in r2["keys_outside_source_folders"].items():
            add("cao", "R2", f"{count} key dưới `{bucket}/` không theo layout `<tầng>/<nguồn>/...` (ví dụ `{r2['examples'][bucket]}`)")
        for layer, count in r2["non_canonical_layers"].items():
            add("trung bình", "R2", f"tầng `{layer}/` ({count} object) nằm ngoài 4 tầng chuẩn raw, url_ledger, staging, curated")

    for s in result["sources"]:
        src, raw, dup, led, tl, sus = s["source"], s["raw"], s["duplicates"], s["ledger"], s["timeline"], s["suspect"]
        if raw["files"] == 0:
            add("cao", src, "không có file raw nào trên máy")
            continue
        if raw["parse_errors"]:
            add("cao", src, f"{raw['parse_errors']} file JSON hỏng (ví dụ {raw['parse_error_examples'][0]})")
        if raw["files_without_envelope"]:
            add("trung bình", src, f"{raw['files_without_envelope']} file trong raw/ không phải envelope (log lỗi hoặc file phụ)")
        if raw["empty_payload"]:
            add("cao", src, f"{raw['empty_payload']} envelope có raw_payload rỗng")
        if sus["blocked_page"]:
            add("cao", src, f"{sus['blocked_page']} bản ghi có dấu hiệu là trang chặn bot hoặc captcha")
        if sus["no_title"]:
            add("trung bình", src, f"{sus['no_title']} bản ghi không có title")
        if sus["short_text"]:
            add("trung bình", src, f"{sus['short_text']} bản ghi gần như không có nội dung (< {MIN_TEXT_CHARS} ký tự)")
        if raw["legacy_batch_files"]:
            add("thấp", src, f"{raw['legacy_batch_files']} file batch cũ chứa {raw['batch_job_ids']} job_id, "
                f"{raw['batch_job_ids_also_single']} trong số đó đã có file riêng (cần khử trùng khi pre-processing)")
        if dup["job_id_in_many_files"]:
            add("thấp", src, f"{dup['job_id_in_many_files']} job_id xuất hiện ở nhiều file (phiên bản cào lại hoặc trùng)")
        if dup["url_with_many_job_ids"]:
            add("trung bình", src, f"{dup['url_with_many_job_ids']} URL ứng với nhiều job_id khác nhau")
        if not led["exists"]:
            add("cao", src, "không có URL Ledger trên máy")
        else:
            if led["done_without_raw"]:
                add("cao", src, f"{led['done_without_raw']} URL đã DONE trong ledger nhưng không có raw tương ứng")
            if led["raw_not_in_ledger"]:
                add("trung bình", src, f"{led['raw_not_in_ledger']} job_id có raw nhưng không có trong ledger "
                    f"(ví dụ {', '.join(led['raw_not_in_ledger_examples'][:3])})")
            if led["ledger_behind_raw"]:
                add("cao", src, f"ledger chưa ghi nhận {led['ledger_behind_raw']} lần cào: raw mới nhất lúc "
                    f"{(led['last_raw_scrape'] or '')[:16]}, ledger cập nhật lần cuối lúc {(led['last_ledger_update'] or '')[:16]}. "
                    "Lần chạy sau sẽ cào lại các tin này")
            failed = led["status"].get("FAILED", 0)
            if failed and failed >= 0.1 * led["total"]:
                reason = led["top_failed_reasons"][0][0] if led["top_failed_reasons"] else "không ghi lý do"
                add("cao", src, f"{failed}/{led['total']} URL FAILED; lý do hay gặp: {reason}")
        if tl["days_since_last"] is not None and tl["days_since_last"] > 3:
            add("trung bình", src, f"lần cào gần nhất cách đây {tl['days_since_last']} ngày ({tl['last_day']})")
        if len(tl["gap_days"]) > 0:
            add("thấp", src, f"{len(tl['gap_days'])} ngày không có tin giữa {tl['first_day']} và {tl['last_day']}")
        for code, pct in s["features"].items():
            if pct is not None and pct < 50:
                add("trung bình", src, f"{code} chỉ có ở {pct}% bản ghi raw")
    order = {"cao": 0, "trung bình": 1, "thấp": 2}
    return sorted(issues, key=lambda i: (order[i["level"]], i["source"]))


def render_markdown(result: Dict[str, Any]) -> str:
    codes = [f["code"] for f in FEATURES]
    lines = [
        f"# Kiểm tra dữ liệu cào ngày {result['date']}",
        "",
        f"Tạo bởi `scripts/audit_raw_data.py` lúc {result['generated_at']}. Script chỉ đọc `data/`"
        + (" và liệt kê key trên R2." if result.get("r2") else "."),
        "",
        "## Tóm tắt theo nguồn",
        "",
        "| Nguồn | File raw | Envelope | job_id | JSON hỏng | Ledger | DONE | PENDING | FAILED | Đến hạn cào lại | Repost | DONE thiếu raw | Raw ngoài ledger | Ledger chậm hơn raw | Ngày cuối |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for s in result["sources"]:
        raw, led, tl = s["raw"], s["ledger"], s["timeline"]
        st = led["status"]
        lines.append(
            f"| {s['source']} | {raw['files']} | {raw['envelopes']} | {raw['unique_job_ids']} | {raw['parse_errors']} | "
            f"{led['total']} | {st.get('DONE', 0)} | {st.get('PENDING', 0)} | {st.get('FAILED', 0)} | "
            f"{led['done_due_for_recrawl']} | {led.get('reposts', 0)} | {_dash(led['done_without_raw'])} | {_dash(led['raw_not_in_ledger'])} | "
            f"{_dash(led.get('ledger_behind_raw'))} | "
            f"{tl['last_day'] or '—'} |"
        )
    lines += ["", "## 8 feature target có trong raw (%)", "",
              "`—`: nguồn không hiển thị trường này trên trang.", "",
              "| Nguồn | " + " | ".join(codes) + " |", "|---|" + "---:|" * len(codes)]
    for s in result["sources"]:
        lines.append(f"| {s['source']} | " + " | ".join(_dash(s["features"][c]) for c in codes) + " |")
    lines += ["", "## Vấn đề, xếp theo mức ảnh hưởng", ""]
    if not result["issues"]:
        lines.append("Không phát hiện vấn đề.")
    for level in ("cao", "trung bình", "thấp"):
        group = [i for i in result["issues"] if i["level"] == level]
        if group:
            lines += [f"### Mức {level}", ""] + [f"- **{i['source']}**: {i['text']}" for i in group] + [""]
    lines += ["## Số tin theo ngày", ""]
    for s in result["sources"]:
        per_day = s["timeline"]["per_day"]
        if per_day:
            lines.append(f"- **{s['source']}**: " + ", ".join(f"{d[5:]}: {n}" for d, n in per_day.items()))
    return "\n".join(lines) + "\n"


def _dash(v: Any) -> str:
    return "—" if v is None else str(v)


def list_r2_keys() -> List[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from sync_cloud_lakehouse import get_s3_client  # noqa: E402

    client_info = get_s3_client()
    s3, bucket = client_info[0], client_info[1]
    keys: List[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        keys += [item["Key"] for item in page.get("Contents", [])]
    from collection.common.r2_storage import to_logical_key  # noqa: E402

    return [to_logical_key(k) for k in keys]  # audit kiểm theo tên tầng logic, không phụ thuộc prefix R2


def run(data_dir: Path, out_dir: Path, with_r2: bool = False, today: Optional[date] = None) -> Dict[str, Any]:
    settings.DATA_DIR = data_dir
    today = today or datetime.now(timezone.utc).date()
    result: Dict[str, Any] = {
        "date": today.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "layout": check_layout(data_dir),
        "sources": [audit_source(src, today) for src in SOURCES],
    }
    if with_r2:
        result["r2"] = check_r2_layout(list_r2_keys())
    result["issues"] = find_issues(result)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"data_audit_{today.isoformat()}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out_dir / f"data_audit_{today.isoformat()}.md").write_text(render_markdown(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports")
    parser.add_argument("--r2", action="store_true", help="Liệt kê key trên R2 để kiểm tra layout (chỉ đọc)")
    args = parser.parse_args()
    result = run(args.data_dir.resolve(), args.out_dir.resolve(), with_r2=args.r2)
    counts = Counter(i["level"] for i in result["issues"])
    print(f"Đã ghi {args.out_dir}/data_audit_{result['date']}.md: "
          f"{counts['cao']} vấn đề mức cao, {counts['trung bình']} trung bình, {counts['thấp']} thấp.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
