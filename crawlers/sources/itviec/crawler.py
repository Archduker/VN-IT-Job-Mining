# -*- coding: utf-8 -*-
"""Crawler nguồn ITviec (https://itviec.com).

Owner: Phát

Flow (kien_truc_co_the.md §4):
    doc checkpoint → listing → trich URL job → loc tin da cào
    → tai detail → parse → validate → ghi JSONL → checkpoint moi 10 tin
    → tong ket batch.

KIẾN TRÚC HIỆN TẠI (2026-10-05):
    crawlers/common/ (http_client, checkpoint, jsonl_writer, schema,
    s3_uploader, telegram_notifier) CHƯA tồn tại trong repo — Thuận phụ trách
    (TASKS.md T-01). Các helper dưới đây mô phỏng đúng hành vi đã tài liệu
    hóa trong TASKS.md §4.2 / kien_truc_co_the.md §4 để sau này chỉ việc đổi
    import sang common module, không đụng logic.

    S3 upload + Telegram KHÔNG implement ở đây: cần AWS credentials và là
    phần của common module (leader). Crawler dừng ở JSONL local theo partition
    data/itviec/dt=YYYY-MM-DD/batch_<seq>.jsonl (data/ đã gitignore).

Cách chạy test local (run.py chưa có, chờ T-02 của Thuận):
    python crawlers/sources/itviec/crawler.py --max-items 1
    python crawlers/sources/itviec/crawler.py --max-items 30
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

repo_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:  # chạy như package hoặc trực tiếp
    from . import config, parser as job_parser
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config
    import parser as job_parser

from crawlers.common.json_writer import JsonWriter

log = logging.getLogger("itviec.crawler")

# ---------------------------------------------------------------- HTTP client
# Mô phỏng common/http_client.py: session + UA + delay ngẫu nhiên 2–5s +
# retry backoff cho lỗi mạng / 429 / 5xx.


class HttpClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)
        self._last_request_at = 0.0

    def get(self, url):
        """GET với delay lịch sự trước MỌI request và retry có backoff.

        Return: requests.Response (status 200). Raise RuntimeError hết retry.
        """
        for attempt in range(1, config.MAX_RETRIES + 1):
            wait = (config.REQUEST_DELAY_MIN
                    + random.uniform(0, config.REQUEST_DELAY_MAX - config.REQUEST_DELAY_MIN))
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < wait:
                time.sleep(wait - elapsed)
            self._last_request_at = time.monotonic()
            try:
                resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            except requests.RequestException as exc:
                log.warning("Lỗi mạng (lần %d/%d) %s: %s",
                            attempt, config.MAX_RETRIES, url, exc)
                self._backoff(attempt)
                continue
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 500, 502, 503, 504):
                log.warning("HTTP %d (lần %d/%d) %s",
                            resp.status_code, attempt, config.MAX_RETRIES, url)
                self._backoff(attempt)
                continue
            # 403/404…: không retry, bỏ qua tin/ trang này
            raise RuntimeError(f"HTTP {resp.status_code} cho {url}")
        raise RuntimeError(f"Hết retry cho {url}")

    @staticmethod
    def _backoff(attempt):
        time.sleep(min(config.BACKOFF_BASE * (2 ** (attempt - 1)), 30))


# ---------------------------------------------------------------- checkpoint
# Mô phỏng common/checkpoint.py: seen_ids + last_page, JSON file.


def load_checkpoint(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data.get("seen_ids"), list):
            return data
        log.warning("Checkpoint lạ, bỏ qua: %s", path)
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Không đọc được checkpoint (%s): %s", path, exc)
    return {"seen_ids": [], "sources": {}, "updated_at": None}


def save_checkpoint(path, seen_ids, extra=None):
    data = {
        "seen_ids": sorted(seen_ids),
        "updated_at": _now_iso(),
    }
    if extra:
        data["sources"] = extra
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)  # ghi nguyên tử, mất điện không hỏng checkpoint


# ---------------------------------------------------------------- JSON writer
# Sử dụng common/json_writer.py: atomic write mảng JSON [ ... ]


def open_json(date_str, batch_id):
    """Mở JsonWriter cho partition: data/itviec/dt=…/batch_….json."""
    day_dir = os.path.join(config.DATA_DIR, f"dt={date_str}")
    os.makedirs(day_dir, exist_ok=True)
    batch_seq_str = batch_id.rsplit("_", 1)[-1]
    try:
        batch_seq = int(batch_seq_str)
    except ValueError:
        batch_seq = 1
    run_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    parent_dir = os.path.dirname(config.DATA_DIR)
    return JsonWriter(
        source=config.SOURCE,
        output_dir=parent_dir,
        run_date=run_date,
        batch_seq=batch_seq,
        filename_override=f"batch_{batch_seq:03d}.json",
        validate_schema=False,
    )


def open_jsonl(date_str, batch_id):
    """Deprecated alias cho open_json."""
    return open_json(date_str, batch_id)


def write_record(target, record):
    """Ghi record vào JsonWriter hoặc file handle (tương thích ngược)."""
    if isinstance(target, JsonWriter):
        target.write(record)
    elif hasattr(target, "write"):
        target.write(json.dumps(record, ensure_ascii=False))
        target.write("\n")
        target.flush()
        if hasattr(target, "fileno"):
            try:
                os.fsync(target.fileno())
            except OSError:
                pass


# ---------------------------------------------------------------- helpers


def _now_iso():
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(config.TZ_NAME))
    except Exception:  # pragma: no cover — fallback nếu thiếu tzdata
        now = datetime.now(timezone(timedelta(hours=7)))
    return now.isoformat(timespec="seconds")


def make_batch_id(date_str, seq=1):
    """batch_id theo convention TASKS.md: 2026-10-07_itviec_001."""
    return f"{date_str}_{config.SOURCE}_{seq:03d}"


def build_record(raw, url, source_job_id, batch_id):
    """Ghép bản ghi {_meta, raw} theo data contract TASKS.md §4.1."""
    meta = {
        "source": config.SOURCE,
        "source_job_id": source_job_id,
        "url": url,
        "dedup_key": f"{config.SOURCE}:{source_job_id}",
        "crawled_at": _now_iso(),
        "batch_id": batch_id,
        "crawler_version": config.CRAWLER_VERSION,
    }
    return {"_meta": meta, "raw": raw}


def save_error_html(slug, html):
    """HTML parse lỗi → data/itviec/errors/ để debug, không im lặng bỏ qua."""
    os.makedirs(config.ERROR_DIR, exist_ok=True)
    path = os.path.join(config.ERROR_DIR, f"{slug}_{int(time.time())}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


def listing_page_url(location_path, page):
    url = config.BASE_URL + location_path
    if page > 1:
        url += f"?page={page}"
    return url


# ---------------------------------------------------------------- main crawl


def crawl(max_items=None, batch_id=None, client=None):
    """Chạy 1 batch. Return dict thống kê (giống payload báo cáo Telegram sau này)."""
    max_items = max_items or config.DEFAULT_MAX_ITEMS
    client = client or HttpClient()

    now = datetime.now(timezone.utc)
    date_str = now.astimezone(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
    if batch_id is None:
        batch_id = make_batch_id(date_str)

    checkpoint = load_checkpoint(config.CHECKPOINT_FILE)
    seen_ids = set(checkpoint["seen_ids"])
    log.info("Checkpoint: %d job đã thấy. batch_id=%s max_items=%d",
             len(seen_ids), batch_id, max_items)

    stats = {"written": 0, "failed": 0, "skipped_seen_on_listing": 0}
    writer = open_json(date_str, batch_id)
    since_checkpoint = 0
    try:
        for location in config.LISTING_LOCATIONS:
            if stats["written"] >= max_items:
                break
            for page in range(1, config.MAX_LISTING_PAGES + 1):
                if stats["written"] >= max_items:
                    break
                url = listing_page_url(location, page)
                try:
                    resp = client.get(url)
                except RuntimeError as exc:
                    log.error("Bỏ qua trang listing %s: %s", url, exc)
                    break  # sang location khác
                jobs = job_parser.parse_listing(resp.text)
                if not jobs:
                    log.info("Hết trang listing (trang %d trống).", page)
                    break
                new_jobs = [j for j in jobs if j["source_job_id"] not in seen_ids]
                stats["skipped_seen_on_listing"] += len(jobs) - len(new_jobs)
                log.info("Listing %s trang %d: %d tin, %d tin mới.",
                         location, page, len(jobs), len(new_jobs))
                for job in new_jobs:
                    if stats["written"] >= max_items:
                        break
                    if _crawl_one(client, job, seen_ids, batch_id, writer, stats):
                        since_checkpoint += 1
                        if since_checkpoint >= config.CHECKPOINT_INTERVAL:
                            save_checkpoint(config.CHECKPOINT_FILE, seen_ids)
                            since_checkpoint = 0
                            log.info("Checkpoint đã ghi (%d job).", len(seen_ids))
    finally:
        save_checkpoint(config.CHECKPOINT_FILE, seen_ids)
        writer.close()

    stats["output_file"] = str(writer.file_path)
    log.info("Hoàn thành batch %s: %s", batch_id, stats)
    return stats


def _crawl_one(client, job, seen_ids, batch_id, writer, stats):
    """Cào 1 tin detail. Return True nếu ghi thành công (đã tính checkpoint)."""
    slug, url = job["source_job_id"], job["url"]
    try:
        resp = client.get(url)
    except RuntimeError as exc:
        log.error("Lỗi tải detail %s: %s", url, exc)
        stats["failed"] += 1
        seen_ids.add(slug)  # tránh lặp vô hạn request hỏng giữa các batch
        return False
    try:
        raw = job_parser.parse_detail(resp.text)
    except Exception:
        path = save_error_html(slug, resp.text)
        log.exception("Parse lỗi %s — HTML lưu tại %s", url, path)
        stats["failed"] += 1
        seen_ids.add(slug)
        return False

    record = build_record(raw, url, slug, batch_id)
    errors = job_parser.validate_record(record)
    if errors:
        path = save_error_html(slug, resp.text)
        log.error("Record không hợp lệ %s: %s — HTML lưu tại %s", url, errors, path)
        stats["failed"] += 1
        seen_ids.add(slug)
        return False
    warnings = job_parser.record_warnings(record)
    if warnings:
        log.warning("Thiếu field (%s): %s", url, ", ".join(warnings))

    write_record(writer, record)
    seen_ids.add(slug)
    stats["written"] += 1
    log.info("✓ [%d] %s | %s", stats["written"], raw.get("title"), url)
    return True


# ---------------------------------------------------------------- CLI


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=(
            "Crawler ITviec (tạm thời chạy độc lập; sau này run.py của Thuận "
            "sẽ gọi crawl() với cùng giao diện --source/--max-items)."
        )
    )
    ap.add_argument("--max-items", type=int, default=config.DEFAULT_MAX_ITEMS,
                    help="Số tin mới tối đa trong 1 batch (mặc định 30).")
    ap.add_argument("--batch-id", default=None,
                    help="Vd: 2026-10-05_itviec_001 (mặc định sinh theo ngày).")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    stats = crawl(max_items=args.max_items, batch_id=args.batch_id)
    total = sum(stats.values())
    print(f"\nTóm tắt: ghi mới={stats['written']}, lỗi={stats['failed']}, "
          f"bỏ qua vì đã thấy ở listing={stats['skipped_seen_on_listing']}, "
          f"tổng processed={total}")
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
