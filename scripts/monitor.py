#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN-IT-Job-Mining — Monitoring Dashboard
========================================
Hiển thị bảng trạng thái thời gian thực của toàn bộ pipeline thu thập dữ liệu.

Đọc từ (read-only, không ghi vào):
  - data/<source>/<source>_checkpoint.json  →  total_collected, last_updated_at
  - data/queue/<source>_queue_*.json        →  số tin đang chờ Phase 2 (Task 1)
  - data/<source>/dt=*/batch_*.json         →  số records thực tế đã lưu
  - airflow/airflow.db                      →  trạng thái DAG run gần nhất
  - logs/crawl_reports/crawl_report_*.json  →  báo cáo tổng hợp Weekly

Cách dùng:
  python scripts/monitor.py            # Snapshot 1 lần rồi thoát
  python scripts/monitor.py --watch    # Tự động refresh mỗi 10 giây

Yêu cầu: Python 3.8+ stdlib thuần (json, sqlite3, pathlib, argparse, time, os)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Đường dẫn gốc dự án ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
AIRFLOW_DB = PROJECT_ROOT / "airflow" / "airflow.db"
QUEUE_DIR = DATA_DIR / "queue"
REPORTS_DIR = PROJECT_ROOT / "logs" / "crawl_reports"

ALL_SOURCES = [
    "topdev",
    "careerviet",
    "itviec",
    "vietnamworks",
    "topcv",
    "vieclam24h",
    "glints",
    "jobsgo",
]

# ── Màu sắc terminal (ANSI codes) ─────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    CYAN    = "\033[96m"
    BLUE    = "\033[94m"
    GREY    = "\033[90m"
    WHITE   = "\033[97m"

def _color(text: str, *codes: str) -> str:
    """Bao text trong ANSI color codes."""
    return "".join(codes) + str(text) + C.RESET


# ── Đọc dữ liệu từ checkpoint ────────────────────────────────────────────────
def read_checkpoint(source: str) -> Dict[str, Any]:
    """Đọc file checkpoint của từng nguồn."""
    # Task 1 lưu ở data/<source>/<source>_checkpoint.json
    ckpt_path = DATA_DIR / source / f"{source}_checkpoint.json"
    if not ckpt_path.exists():
        return {}
    try:
        with open(ckpt_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def count_records_in_batches(source: str) -> int:
    """Đếm tổng số records đã ghi vào tất cả batch files của nguồn."""
    pattern = str(DATA_DIR / source / "dt=*" / "batch_*.json")
    total = 0
    for fpath in glob.glob(pattern):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    total += len(data)
        except Exception:
            pass
    return total


def count_queue_items(source: str) -> int:
    """Đếm số items đang chờ trong queue file gần nhất (Task 1 Phase 2)."""
    if not QUEUE_DIR.exists():
        return 0
    pattern = str(QUEUE_DIR / f"{source}_queue_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        return 0
    # Đọc file mới nhất
    try:
        with open(files[-1], "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data.get("items", [])
            # Chỉ đếm items chưa SUCCESS
            return len([i for i in items if i.get("reason") != "SUCCESS"])
    except Exception:
        return 0


CATALOG_DB = DATA_DIR / "state" / "job_catalog.db"


def read_catalog_stats() -> Dict[str, Dict[str, int]]:
    """Đọc thống kê trạng thái từ JobStateCatalog SQLite (Task 1)."""
    if not CATALOG_DB.exists():
        return {}
    res: Dict[str, Dict[str, int]] = {}
    try:
        con = sqlite3.connect(str(CATALOG_DB))
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "SELECT source, crawl_status, count(*) as cnt "
            "FROM job_state_catalog GROUP BY source, crawl_status"
        )
        for row in cur.fetchall():
            s = row["source"].lower().strip()
            if s not in res:
                res[s] = {"SUCCESS": 0, "FAILED_RETRY_NEXT_RUN": 0, "DISCOVERED": 0, "total": 0}
            status = row["crawl_status"]
            cnt = row["cnt"]
            res[s][status] = cnt
            res[s]["total"] += cnt
        con.close()
    except Exception:
        pass
    return res


# ── Đọc Airflow DB (sqlite3) ──────────────────────────────────────────────────
def read_airflow_dag_runs() -> Dict[str, Dict[str, Any]]:
    """
    Đọc trạng thái DAG run gần nhất từ Airflow SQLite DB.

    Returns:
        dict: { dag_id: { "state": str, "end_date": str } }
    """
    if not AIRFLOW_DB.exists():
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    try:
        con = sqlite3.connect(str(AIRFLOW_DB))
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        # Airflow 2.x schema: bảng dag_run
        cur.execute("""
            SELECT dag_id, state, end_date, execution_date
            FROM dag_run
            WHERE end_date IS NOT NULL
            ORDER BY end_date DESC
        """)
        seen_dags: set[str] = set()
        for row in cur.fetchall():
            dag_id = row["dag_id"]
            if dag_id not in seen_dags:
                seen_dags.add(dag_id)
                results[dag_id] = {
                    "state": row["state"],
                    "end_date": row["end_date"],
                }
        con.close()
    except Exception:
        pass
    return results


def _dag_id_for_source(source: str) -> List[str]:
    """Trả về danh sách DAG IDs có thể liên quan đến source."""
    return [
        f"crawler_{source}",
        "crawler_weekly_all",
        "periodic_it_job_mining_4days",
    ]


# ── Đọc báo cáo tổng hợp mới nhất ────────────────────────────────────────────
def read_latest_report() -> Optional[Dict[str, Any]]:
    """Đọc crawl_report JSON mới nhất từ logs/crawl_reports/."""
    if not REPORTS_DIR.exists():
        return None
    files = sorted(REPORTS_DIR.glob("crawl_report_*.json"))
    if not files:
        return None
    try:
        with open(files[-1], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ── Tổng hợp dữ liệu một nguồn ───────────────────────────────────────────────
def collect_source_stats(
    source: str,
    dag_runs: Dict[str, Any],
    catalog_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Thu thập tất cả metrics cho một nguồn (kết hợp cả Checkpoint và SQLite Catalog)."""
    ckpt = read_checkpoint(source)
    total_seen     = ckpt.get("total_collected", 0)
    last_updated   = ckpt.get("last_updated_at", "")
    seen_ids_count = len(ckpt.get("seen_ids", []))

    # Tích hợp Task 1 Catalog
    cat_info = (catalog_stats or {}).get(source, {})
    cat_total = cat_info.get("total", 0)
    effective_total_seen = max(total_seen, seen_ids_count, cat_total)

    records_in_files = count_records_in_batches(source)
    queue_waiting    = count_queue_items(source)

    # Tìm dag run gần nhất liên quan
    dag_state = "—"
    dag_date  = "—"
    for dag_id in _dag_id_for_source(source):
        run = dag_runs.get(dag_id)
        if run:
            dag_state = run.get("state", "—")
            end_dt    = run.get("end_date", "")
            if end_dt:
                # Cắt ngắn về dạng YYYY-MM-DD HH:MM
                dag_date = end_dt[:16].replace("T", " ")
            break

    # Định dạng last_updated
    if last_updated:
        try:
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            dt_local = dt.astimezone()
            last_updated_str = dt_local.strftime("%Y-%m-%d %H:%M")
        except Exception:
            last_updated_str = last_updated[:16]
    else:
        last_updated_str = "—"

    return {
        "source":            source,
        "total_seen":        effective_total_seen,
        "records_in_files":  records_in_files,
        "queue_waiting":     queue_waiting,
        "last_updated":      last_updated_str,
        "dag_state":         dag_state,
        "dag_date":          dag_date,
    }


# ── Render bảng ───────────────────────────────────────────────────────────────
def _state_icon(state: str) -> str:
    icons = {
        "success": _color("✅ success", C.GREEN),
        "failed":  _color("❌ failed",  C.RED),
        "running": _color("⏳ running", C.CYAN),
        "queued":  _color("🕐 queued",  C.YELLOW),
        "—":       _color("⏸  —",       C.GREY),
    }
    return icons.get(state.lower() if state != "—" else "—", _color(state, C.GREY))


def render_dashboard(all_stats: List[Dict[str, Any]], report: Optional[Dict[str, Any]]) -> str:
    """Tạo chuỗi bảng dashboard."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    width = 106

    lines: List[str] = []

    # Header
    lines.append(_color("=" * width, C.BOLD + C.CYAN))
    title = f"  VN-IT-Job-Mining  │  Monitoring Dashboard  │  {now}"
    lines.append(_color(title, C.BOLD + C.WHITE))
    lines.append(_color("=" * width, C.BOLD + C.CYAN))

    # Column headers
    header = (
        f"  {'NGUỒN':<14} │ {'TỔNG ĐÃ THẤY':>12} │ {'RECORDS FILE':>12} │"
        f" {'QUEUE ĐỢI':>9} │ {'CẬP NHẬT GẦN NHẤT':<18} │ {'DAG RUN GẦN NHẤT':<20}"
    )
    lines.append(_color(header, C.BOLD + C.BLUE))
    lines.append(_color("─" * width, C.GREY))

    total_seen = 0
    total_records = 0
    total_queue = 0

    for s in all_stats:
        source          = s["source"]
        seen            = s["total_seen"]
        records         = s["records_in_files"]
        queue           = s["queue_waiting"]
        last_upd        = s["last_updated"]
        dag_state       = s["dag_state"]
        dag_date        = s["dag_date"]

        total_seen    += seen
        total_records += records
        total_queue   += queue

        # Màu nguồn
        src_colored = _color(f"{source:<14}", C.CYAN if seen > 0 else C.GREY)
        seen_str    = _color(f"{seen:>12,}", C.WHITE if seen > 0 else C.GREY)
        rec_str     = _color(f"{records:>12,}", C.GREEN if records > 0 else C.GREY)
        queue_str   = _color(f"{queue:>9}", C.YELLOW if queue > 0 else C.GREY)
        upd_str     = _color(f"{last_upd:<18}", C.WHITE if last_upd != "—" else C.GREY)
        state_icon  = _state_icon(dag_state)
        date_str    = _color(f"{dag_date}", C.WHITE if dag_date != "—" else C.GREY)

        row = (
            f"  {src_colored} │ {seen_str} │ {rec_str} │"
            f" {queue_str} │ {upd_str} │ {state_icon} {date_str}"
        )
        lines.append(row)

    # Total row
    lines.append(_color("─" * width, C.GREY))
    total_row = (
        f"  {'TỔNG CỘNG':<14} │ {total_seen:>12,} │ {total_records:>12,} │"
        f" {total_queue:>9} │ {'':18} │"
    )
    lines.append(_color(total_row, C.BOLD + C.WHITE))
    lines.append(_color("=" * width, C.BOLD + C.CYAN))

    # Ghi chú
    lines.append("")
    lines.append(_color("  📖 TỔNG ĐÃ THẤY   ", C.BOLD) + "= Tổng ID đã cào (checkpoint — dedup base)")
    lines.append(_color("  📁 RECORDS FILE   ", C.BOLD) + "= Bản ghi thực tế đã lưu vào data/")
    lines.append(_color("  🕐 QUEUE ĐỢI      ", C.BOLD) + "= Tin đang chờ cào Phase 2 (từ hàng đợi 2 giai đoạn)")

    # Report tổng hợp mới nhất
    if report:
        run_date       = report.get("run_date", "—")
        total_new      = report.get("total_new_jobs", 0)
        total_skipped  = report.get("total_skipped", 0)
        total_errors   = report.get("total_errors", 0)
        lines.append("")
        lines.append(_color(f"  📊 Báo cáo tổng hợp gần nhất ({run_date}):", C.BOLD + C.YELLOW))
        lines.append(
            f"     Tin MỚI = {_color(total_new, C.GREEN)}   "
            f"Bỏ qua (đã có) = {_color(total_skipped, C.GREY)}   "
            f"Lỗi = {_color(total_errors, C.RED)}"
        )

    lines.append("")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
def run_once() -> None:
    dag_runs      = read_airflow_dag_runs()
    catalog_stats = read_catalog_stats()
    all_stats     = [collect_source_stats(src, dag_runs, catalog_stats) for src in ALL_SOURCES]
    report        = read_latest_report()
    print(render_dashboard(all_stats, report))


def run_watch(interval: int = 10) -> None:
    print(_color(f"👀 Watch mode — Refresh mỗi {interval} giây  │  Ctrl+C để thoát\n", C.YELLOW))
    try:
        while True:
            os.system("clear")
            run_once()
            for remaining in range(interval, 0, -1):
                sys.stdout.write(
                    f"\r  {_color('⏱', C.CYAN)} Refresh sau {remaining}s ...   "
                )
                sys.stdout.flush()
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n" + _color("  👋 Đã thoát monitor.", C.YELLOW))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VN-IT-Job-Mining — Monitoring Dashboard",
        epilog="""
Ví dụ:
  python scripts/monitor.py            # Snapshot 1 lần
  python scripts/monitor.py --watch    # Auto-refresh mỗi 10 giây
  python scripts/monitor.py --watch --interval 30
        """,
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Chạy liên tục, tự động refresh",
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=10,
        help="Khoảng cách refresh khi dùng --watch (giây, mặc định: 10)",
    )
    args = parser.parse_args()

    if args.watch:
        run_watch(interval=args.interval)
    else:
        run_once()


if __name__ == "__main__":
    main()
