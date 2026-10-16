#!/usr/bin/env python3
"""careerviet_report_fill.py — IN RA Cac So Lieu Can Dien Bao Cao (CHI DOC).

Script nay doc local, **KHONG goi mang**, **KHONG ghi de** bat ky file nao,
**KHONG sua** ledger/envelope. Dung SAU dot chay online de lay so lieu that
dien vao:

- docs/crawl/careerviet.md §9.4 (Ket qua online)
- reports/careerviet_inventory.md §1 (%null), §2 (CDC), §3.3 (toc do)
- reports/careerviet_eda.md §1.1 (null), §3.1 (Top tag), §3.2 (dia diem),
  §3.3 (CDC), §3.4 (ti le CNTT)

Thong ke in ra:

1. So envelope theo ngay (dem file `*_v<N>.json`).
2. Phan bo trang thai ledger: PENDING / DONE / RECHECK_DUE / FAILED / CLOSED.
3. % null cua tung khoa trong `raw_payload` (8 khoa CSS selector goc).
4. Ti le CNTT theo `raw_payload["Ngành nghề"]` (rule: chua "CNTT" hoac
   "Phần mềm", **KHONG dung** `metadata.source_category`).
5. CDC suy ra tu ledger: `latest_version == 1` (NEW), `> 1` (UPDATED),
   `repost_of_url_hash != None` (REPOST), `status == CLOSED` (CLOSED).
6. Top tag (job-tags) va Top tinh (map tach dau `,`) — tan suat phan loai.

SAC MAU:
- "CHỜ ONLINE" neu duong dan RAW khong ton tai hoac 0 file envelope.
- Du lieu demo (20 file o `_dryrun/raw/`) se duoc in neu tai duong dan `--raw-dir`.

Vi du chay:

    python -X utf8 scripts/careerviet_report_fill.py                # duong dan mac dinh
    python -X utf8 scripts/careerviet_report_fill.py --raw-dir data/careerviet/_dryrun/raw
    python -X utf8 scripts/careerviet_report_fill.py --json         # xuat JSON cho may doc
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_RAW_DIR = "data/careerviet/raw"
DEFAULT_LEDGER_DIR = "data/careerviet/url_ledger"
DEFAULT_IT_KEYWORDS = ("CNTT", "Phần mềm", "Phan mem")
PAYLOAD_KEYS = (
    "title", "job-company-name", "detail-box", "detail-row",
    "job-tags", "map", "Ngành nghề", "job-posting-schema",
)
DATE_DIR_RE = re.compile(r"^(?:dt=)?(\d{4}-\d{2}-\d{2})$")
ENV_RE = re.compile(r"^(?P<jid>[A-Za-z0-9]+)_v(?P<ver>\d+)\.json$")


# ==== Envelope I/O ====
def scan_envelopes(raw_dir: Path) -> list[dict]:
    """Doc tat ca `*_v<N>.json` duoi `raw_dir/` (quy 2 cap: `<date>/<file>` hoac
    `dt=<date>/<file>`). Tra ve list[{path, date, job_id, version, envelope}].
    File hong (JSON khong parse duoc) -> bo qua, dem vao `errors`."""
    if not raw_dir.exists():
        return []
    out: list[dict] = []
    for f in sorted(raw_dir.rglob("*.json")):
        em = ENV_RE.match(f.name)
        if not em:
            continue
        # date = ten thu muc cha gan nhat khop DATE_DIR_RE (hoac '-' if khong co)
        date = "-"
        for parent in f.parents:
            if DATE_DIR_RE.match(parent.name):
                date = DATE_DIR_RE.match(parent.name).group(1)
                break
        try:
            env = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append({
            "path": f,
            "date": date,
            "job_id": em.group("jid"),
            "version": int(em.group("ver")),
            "envelope": env,
        })
    return out


# ==== Ledger I/O ====
def load_catalog(ledger_dir: Path) -> dict[str, dict]:
    """Doc `catalog_master.json` (dict<url_hash, record>). Khong ton tai -> {}."""
    p = ledger_dir / "catalog_master.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ==== Thong ke ====
def status_counts(catalog: dict) -> dict[str, int]:
    c: dict[str, int] = collections.Counter()
    for rec in catalog.values():
        c[rec.get("status", "?")] += 1
    return dict(c)


def null_rate_by_key(envelopes: list[dict]) -> dict[str, tuple[int, int, float]]:
    """ Voi moi khoa trong PAYLOAD_KEYS: tra ve (null_count, total, percent).
    Null = value is None, empty list/dict/str, hoac key thuu thien."""
    total = len(envelopes)
    out: dict[str, tuple[int, int, float]] = {}
    for key in PAYLOAD_KEYS:
        n_null = 0
        for e in envelopes:
            payload = e["envelope"].get("raw_payload", {}) or {}
            if key not in payload:
                n_null += 1
                continue
            v = payload[key]
            if v is None or (isinstance(v, (list, dict, str)) and len(v) == 0):
                n_null += 1
        pct = (n_null / total * 100.0) if total else 0.0
        out[key] = (n_null, total, pct)
    return out


def it_ratio(envelopes: list[dict], keywords: tuple[str, ...] = DEFAULT_IT_KEYWORDS
             ) -> dict[str, Any]:
    """Dem tin co Nganh nghe chua tu khoa IT (case-insensitive substring).
    KHONG dung metadata.source_category (xem docs/careerviet.md §8.1)."""
    total = len(envelopes)
    it = 0
    nganh_values: collections.Counter = collections.Counter()
    for e in envelopes:
        payload = e["envelope"].get("raw_payload", {}) or {}
        ng = payload.get("Ngành nghề") or []
        if isinstance(ng, str):
            ng = [ng]
        joined = " | ".join(str(x) for x in ng)
        for x in ng:
            nganh_values[str(x)] += 1
        if any(kw.lower() in joined.lower() for kw in keywords):
            it += 1
    pct = (it / total * 100.0) if total else 0.0
    return {
        "it_count": it,
        "non_it_count": total - it,
        "total": total,
        "it_percent": round(pct, 1),
        "top_nganh": nganh_values.most_common(10),
    }


def cdc_from_ledger(catalog: dict) -> dict[str, int]:
    """Suy ra CDC tu record (latest_version, repost_of_url_hash, status).

    Quy uoc phan loai MUTUALLY EXCLUSIVE (moi record thuoc DUNG 1 nho):

    - REPOST   : repost_of_url_hash khong None (uu tien cao nhat, bat ra
                 khoi NEW/UPDATED de khong dem trung - crawler.py:635 set
                 tag 'repost' va KHONG bump version).
    - NEW      : status=DONE, latest_version<=1, khong phai repost.
    - UPDATED  : status=DONE, latest_version>=2, khong phai repost.
    - ACTIVE   : (khong phat hien doc lap tu ledger; quy uoc gop vao NEW).
    - CLOSED / FAILED / PENDING / RECHECK_DUE : theo status tu ledger.

    Vi du: 6 record trong do co 1 repost (v=1, DONE) -> dem vao REPOST,
    KHONG dem vao NEW nua (neu dem trung se sai DoD 2).
    """
    out = {"NEW": 0, "UPDATED": 0, "REPOST": 0, "CLOSED": 0,
           "FAILED": 0, "PENDING": 0, "RECHECK_DUE": 0}
    for rec in catalog.values():
        st = rec.get("status", "?")
        ver = rec.get("latest_version") or 0
        try:
            ver = int(ver)
        except (TypeError, ValueError):
            ver = 0
        if rec.get("repost_of_url_hash"):
            # Repost da duoc phat hien o `_process_detail_record` (crawler.py)
            # va gan nhu chắc chắn co status=DONE; tinh rieng REPOST,
            # KHONG rớt vào NEW/UPDATED.
            out["REPOST"] += 1
            continue
        if st == "DONE":
            if ver >= 2:
                out["UPDATED"] += 1
            else:
                out["NEW"] += 1
        elif st in out:
            out[st] += 1
    return out


def top_tags(envelopes: list[dict], n: int = 15) -> list[tuple[str, int]]:
    c: collections.Counter = collections.Counter()
    for e in envelopes:
        payload = e["envelope"].get("raw_payload", {}) or {}
        tags = payload.get("job-tags") or []
        for t in tags:
            c[str(t)] += 1
    return c.most_common(n)


def top_locations(envelopes: list[dict], n: int = 10) -> list[tuple[str, int]]:
    c: collections.Counter = collections.Counter()
    for e in envelopes:
        payload = e["envelope"].get("raw_payload", {}) or {}
        m = payload.get("map")
        if not m:
            continue
        if isinstance(m, str):
            for piece in m.split(","):
                piece = piece.strip()
                if piece:
                    c[piece] += 1
    return c.most_common(n)


def envelope_by_date(envelopes: list[dict]) -> dict[str, int]:
    c: collections.Counter = collections.Counter()
    for e in envelopes:
        c[e["date"]] += 1
    return dict(c)


# ==== Report ====
def build_report(args) -> dict[str, Any]:
    raw_dir = Path(args.raw_dir)
    ledger_dir = Path(args.ledger_dir)
    envelopes = scan_envelopes(raw_dir)
    catalog = load_catalog(ledger_dir)
    kw = tuple(args.it_keyword) if args.it_keyword else DEFAULT_IT_KEYWORDS
    return {
        "raw_dir": str(raw_dir),
        "ledger_dir": str(ledger_dir),
        "envelope_count": len(envelopes),
        "envelope_by_date": envelope_by_date(envelopes),
        "ledger_records": len(catalog),
        "status_distribution": status_counts(catalog),
        "null_rate_by_payload_key": null_rate_by_key(envelopes),
        "it_ratio": it_ratio(envelopes, kw),
        "cdc_from_ledger": cdc_from_ledger(catalog),
        "top_tags": top_tags(envelopes, args.top_n),
        "top_locations": top_locations(envelopes, args.top_n),
    }


def print_human(r: dict) -> None:
    print("=" * 74)
    print("CAREERVIET REPORT FILL — so lieu cho docs §9.4 / inventory / EDA")
    print("=" * 74)
    print(f"RAW dir     : {r['raw_dir']}  (envelope = {r['envelope_count']})")
    print(f"LEDGER dir  : {r['ledger_dir']}  (records = {r['ledger_records']})")
    if r["envelope_count"] == 0:
        print(">> CHUA CO ENVELOPE o RAW dir. Dien 'CHO ONLINE' vao bao cao.")
    print()
    print("--- 1. Envelope theo ngay ---")
    for d, n in sorted(r["envelope_by_date"].items()):
        print(f"  {d}: {n}")
    print()
    print("--- 2. Phan bo trang thai ledger ---")
    for st, n in sorted(r["status_distribution"].items(), key=lambda kv: -kv[1]):
        print(f"  {st:>12s}: {n}")
    print()
    print("--- 3. % null theo khoa raw_payload ---")
    print(f"  {'key':<22s}  {'null':>6s}  {'total':>6s}  {'%':>6s}")
    for k, (n_null, total, pct) in r["null_rate_by_payload_key"].items():
        print(f"  {k:<22s}  {n_null:>6d}  {total:>6d}  {pct:>5.1f}%")
    print()
    print("--- 4. Ti le CNTT (Nganh nghe, KHONG dung source_category) ---")
    ir = r["it_ratio"]
    print(f"  IT    = {ir['it_count']:>5d}  ({ir['it_percent']} %)")
    print(f"  Khong = {ir['non_it_count']:>5d}")
    print(f"  Top Nganh nghe:")
    for name, cnt in ir["top_nganh"][:8]:
        print(f"    - {name}: {cnt}")
    print()
    print("--- 5. CDC suy ra tu ledger ---")
    for k, v in r["cdc_from_ledger"].items():
        print(f"  {k:>13s}: {v}")
    print()
    print("--- 6. Top tags (job-tags) ---")
    if not r["top_tags"]:
        print("  (khong co du lieu)")
    for t, cnt in r["top_tags"]:
        print(f"  {t}  :  {cnt}")
    print()
    print("--- 7. Top locations (map tach ',') ---")
    if not r["top_locations"]:
        print("  (khong co du lieu)")
    for loc, cnt in r["top_locations"]:
        print(f"  {loc}  :  {cnt}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=(
        "IN so lieu dien bao cao CareerViet (CHI DOC, khong goi mang)."))
    p.add_argument("--raw-dir", default=DEFAULT_RAW_DIR,
                   help=f"Thu muc envelope (mac dinh: {DEFAULT_RAW_DIR})")
    p.add_argument("--ledger-dir", default=DEFAULT_LEDGER_DIR,
                   help=f"Thu muc ledger (mac dinh: {DEFAULT_LEDGER_DIR})")
    p.add_argument("--it-keyword", dest="it_keyword", action="append", default=[],
                   metavar="KW",
                   help="Tu khoa IT trong Nganh nghe (lap duoc; "
                        f"mac dinh: {'; '.join(DEFAULT_IT_KEYWORDS)})")
    p.add_argument("--top-n", type=int, default=15,
                   help="So luong max trong Top tags/locations")
    p.add_argument("--json", action="store_true",
                   help="Xuat JSON (de tool khac doc), thay vi in human-readable")
    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    r = build_report(args)
    if args.json:
        # Path object -> str de JSON-able
        print(json.dumps(r, ensure_ascii=False, default=str, indent=2))
    else:
        print_human(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
