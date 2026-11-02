# -*- coding: utf-8 -*-
"""Tổng hợp số liệu thật cho trang Collection: tin theo ngày, lịch chạy, tiến độ."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.data_paths import iter_raw_files, load_catalog_records, read_raw_envelopes
from app.core.r2_client import r2_client
from app.services.airflow_service import airflow_service
from app.services.ledger_service import ledger_service

logger = logging.getLogger("collection_monitor")

VN_TZ = timezone(timedelta(hours=7))
DOW = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
DISCOVERY_DAG = "dag_discovery_daily"
DETAIL_PREFIX = "crawler_detail_"
NO_AIRFLOW = "Chưa kết nối được cơ sở dữ liệu Airflow nên chưa có lịch sử lần chạy."


def _to_vn_date(value: Any) -> Optional[date]:
    """Đổi chuỗi hoặc datetime về ngày theo giờ Việt Nam."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(VN_TZ).date()


def _hhmm(value: Any) -> Optional[str]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(VN_TZ).strftime("%H:%M")


def _daily_counts(source: str) -> Tuple[Counter, Optional[str]]:
    """Đếm tin đã cào theo ngày: ưu tiên ledger, không có thì đếm file raw."""
    counts: Counter = Counter()
    for rec in load_catalog_records(source):
        day = _to_vn_date(rec.get("last_scraped_at") or rec.get("last_crawled_at"))
        if day:
            counts[day] += 1
    if counts:
        return counts, "ledger"
    for day, path in iter_raw_files(source):
        if day:
            counts[day] += len(read_raw_envelopes(path)) if "batch" in path.name else 1
    return counts, "raw" if counts else None


def _aggregate_status(states: List[str]) -> Optional[str]:
    """Gộp các lần chạy trong ngày thành một trạng thái."""
    if not states:
        return None
    if any(s in ("running", "queued") for s in states):
        return "running"
    failed = sum(1 for s in states if s == "failed")
    if failed == 0:
        return "done"
    return "fail" if failed == len(states) else "partial"


def _read_schedule() -> List[Dict[str, Any]]:
    """Đọc lịch trực tiếp từ file DAG để vẫn hiển thị khi Airflow tắt."""
    path = settings.ROOT_DIR / "airflow" / "dags" / "crawler_dags.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    pairs = re.findall(r'dag_id="([^"]+)".*?schedule="([^"]+)"', text, flags=re.S)
    crons = dict(pairs)
    result = []
    discovery = crons.get(DISCOVERY_DAG)
    detail = next((c for d, c in pairs if d.startswith(DETAIL_PREFIX)), None)
    for label, cron in (("Discovery", discovery), ("Crawl chi tiết", detail)):
        if not cron:
            continue
        minute, hours = cron.split()[:2]
        times = [f"{int(h):02d}:{int(minute):02d}" for h in hours.split(",")]
        result.append({"label": label, "times": times, "note": "hằng ngày"})
    if len(result) == 2:
        result[1]["note"] = "cuối tuần đủ các ca; T2–T6 chỉ chạy ca 21:00"
    return result


def _unique_total() -> Optional[int]:
    """Số bản ghi trong golden dataset, None nếu chưa chạy pipeline."""
    path = settings.DATA_DIR / "curated" / "curated_flat_golden_jobs.parquet"
    if not path.exists():
        return None
    try:
        import pyarrow.parquet as pq

        return pq.read_metadata(path).num_rows
    except Exception as exc:
        logger.warning("Không đọc được golden dataset: %s", exc)
        return None


def _runs_by_day(runs: Optional[List[Dict[str, Any]]]) -> Dict[Tuple[date, str], List[Dict[str, Any]]]:
    grouped: Dict[Tuple[date, str], List[Dict[str, Any]]] = {}
    for run in runs or []:
        day = _to_vn_date(run["start_date"])
        if day:
            grouped.setdefault((day, run["dag_id"]), []).append(run)
    return grouped


def _progress(all_counts: Counter, today: date, window: List[date]) -> Dict[str, Any]:
    target = settings.TARGET_UNIQUE
    target_date = date.fromisoformat(settings.TARGET_DATE)
    points: List[Dict[str, Any]] = []
    start = min(all_counts) if all_counts else None
    for day in window:
        actual = sum(n for d, n in all_counts.items() if d <= day)
        plan = None
        if start and target_date > start:
            ratio = min(1.0, max(0.0, (day - start).days / (target_date - start).days))
            plan = round(target * ratio)
        points.append({"date": day.isoformat(), "actual": actual, "plan": plan})
    return {"target": target, "target_date": target_date.isoformat(), "points": points}


def _today_steps(grouped: Dict[Tuple[date, str], List[Dict[str, Any]]], today: date,
                 airflow_ok: bool) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    if airflow_ok:
        disc = grouped.get((today, DISCOVERY_DAG), [])
        steps.append({
            "time": _hhmm(disc[0]["start_date"]) if disc else None,
            "name": "Discovery 8 nguồn",
            "status": _aggregate_status([r["state"] for r in disc]),
            "detail": "Chưa chạy hôm nay" if not disc else f"{len(disc)} lần chạy",
        })
        ran = {dag for (d, dag) in grouped if d == today and dag.startswith(DETAIL_PREFIX)}
        states = [r["state"] for (d, dag), rs in grouped.items()
                  if d == today and dag.startswith(DETAIL_PREFIX) for r in rs]
        starts = [r["start_date"] for (d, dag), rs in grouped.items()
                  if d == today and dag.startswith(DETAIL_PREFIX) for r in rs]
        steps.append({
            "time": _hhmm(min(starts)) if starts else None,
            "name": "Crawl chi tiết",
            "status": _aggregate_status(states),
            "detail": f"{len(ran)}/8 nguồn đã chạy hôm nay",
        })
    try:
        sync = r2_client.get_full_cloud_sync_status()
    except Exception as exc:
        logger.warning("Không lấy được trạng thái R2: %s", exc)
        sync = None
    if sync and sync.get("connected"):
        last = sync.get("last_synced_at")
        steps.append({
            "time": _hhmm(datetime.fromisoformat(last)) if last else None,
            "name": "Đẩy dữ liệu lên R2",
            "status": "done" if sync.get("overall_sync_pct", 0) >= 100 else "partial",
            "detail": f"{sync.get('total_cloud_raw', 0):,} / {sync.get('total_local_raw', 0):,} file raw đã có trên R2".replace(",", "."),
        })
    else:
        steps.append({"time": None, "name": "Đẩy dữ liệu lên R2", "status": None,
                      "detail": "Chưa kết nối được Cloudflare R2"})
    return steps


class CollectionMonitorService:
    """Không sinh số: thiếu nguồn dữ liệu thì trả null kèm lý do."""

    def get_collection(self, days: int = 14) -> Dict[str, Any]:
        today = datetime.now(VN_TZ).date()
        window = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
        sources = settings.SUPPORTED_SOURCES

        per_source = {s: _daily_counts(s) for s in sources}
        runs = airflow_service.get_run_history(days=max(days, 14))
        airflow_ok = runs is not None
        grouped = _runs_by_day(runs)

        rows = []
        for day in window:
            by_source: Dict[str, Any] = {}
            for src in sources:
                dag_runs = grouped.get((day, f"{DETAIL_PREFIX}{src}"), [])
                starts = [r["start_date"] for r in dag_runs if r["start_date"]]
                ends = [r["end_date"] for r in dag_runs if r["end_date"]]
                by_source[src] = {
                    "count": per_source[src][0].get(day, 0),
                    "status": _aggregate_status([r["state"] for r in dag_runs]),
                    "runs": len(dag_runs),
                    "failed_runs": sum(1 for r in dag_runs if r["state"] == "failed"),
                    "first_start": _hhmm(min(starts)) if starts else None,
                    "last_end": _hhmm(max(ends)) if ends else None,
                }
            rows.append({
                "date": day.isoformat(),
                "dow": DOW[day.weekday()],
                "is_today": day == today,
                "total": sum(c["count"] for c in by_source.values()),
                "by_source": by_source,
            })

        all_counts: Counter = Counter()
        for counts, _ in per_source.values():
            all_counts.update(counts)

        detail_runs = [r for r in runs or [] if r["dag_id"].startswith(DETAIL_PREFIX)]
        done_runs = [r for r in detail_runs if r["state"] == "success"]
        total = sum(r["total"] for r in rows)
        unique = _unique_total()
        queue = ledger_service.get_system_enum_summary()

        return {
            "generated_at": datetime.now(VN_TZ).isoformat(),
            "days": rows,
            "count_origin": {s: per_source[s][1] for s in sources},
            "kpi": {
                "today": all_counts.get(today, 0),
                "yesterday": all_counts.get(today - timedelta(days=1), 0),
                "total": total,
                "avg_per_day": round(total / days, 1),
                "runs_ok": len(done_runs) if airflow_ok else None,
                "runs_total": len(detail_runs) if airflow_ok else None,
                "unique_total": unique,
                "unique_reason": None if unique is not None else "Chưa có data/curated: cần chạy pipeline tiền xử lý.",
            },
            "queue": {
                "total": queue["total"],
                **{k: queue[k]["count"] for k in ("pending", "done", "recheck_due", "failed")},
            },
            "progress": _progress(all_counts, today, window),
            "schedule": _read_schedule(),
            "today_steps": _today_steps(grouped, today, airflow_ok),
            "airflow_available": airflow_ok,
            "unavailable_reason": None if airflow_ok else NO_AIRFLOW,
            "has_data": bool(all_counts),
        }


collection_monitor_service = CollectionMonitorService()
