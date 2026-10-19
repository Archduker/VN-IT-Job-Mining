# -*- coding: utf-8 -*-
"""Báo cáo offline Raw Envelope CareerViet trên 30 HTML THẬT (chỉ ĐỌC, không mạng).

In: tỷ lệ rỗng từng khóa raw_payload, số trang có JSON-LD, 2 envelope NGUYÊN VĂN
(job_id nhỏ nhất + 1 job_id có tags), kiểm tra không còn số dính liền "Năm",
và hash lần 1 vs lần 2 của cùng file phải bằng nhau.

Cách chạy (PowerShell, repo root):
    python scripts/careerviet_raw_envelope_report.py `
        --html-dir data/raw/careerviet/html `
        --category-map data/careerviet/url_ledger/category_by_job_id.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawlers.sources.careerviet.raw_envelope import build_raw_envelope  # noqa: E402

BASE_URL = "https://careerviet.vn"
RAW_KEYS = ["title", "job-company-name", "detail-box", "detail-row",
            "job-tags", "map", "job-posting-schema"]


def _is_empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _job_id_from_file(fp: Path) -> str:
    return fp.name.rsplit(".html", 1)[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="CareerViet raw envelope offline report (read-only).")
    ap.add_argument("--html-dir", type=Path, default=Path("data/raw/careerviet/html"))
    ap.add_argument("--category-map", type=Path,
                    default=Path("data/careerviet/url_ledger/category_by_job_id.json"))
    args = ap.parse_args()

    category_map: dict[str, str] = {}
    if args.category_map.exists():
        category_map = json.loads(args.category_map.read_text(encoding="utf-8"))

    files = sorted(args.html_dir.glob("*.html"))
    if not files:
        print(f"KHONG thay file HTML nao trong {args.html_dir}")
        return 1

    envelopes: dict[str, dict] = {}
    empty_counter = {k: 0 for k in RAW_KEYS}
    jsonld_present = 0
    glue_hits = []          # (job_id, mau) so dinh lien "Nam"
    hash_stable = True

    for fp in files:
        html = fp.read_text(encoding="utf-8")
        job_id = _job_id_from_file(fp)
        url = f"{BASE_URL}/vi/tim-viec-lam/job.{job_id}.html"
        cat = category_map.get(job_id)

        env = build_raw_envelope(html, job_id, url, source_category=cat)
        envelopes[job_id] = env

        payload = env["raw_payload"]
        for k in RAW_KEYS:
            if _is_empty(payload.get(k)):
                empty_counter[k] += 1
        if payload.get("job-posting-schema") is not None:
            jsonld_present += 1

        # kiem tra so dinh lien "Năm" (vd "2Năm") trong toan bo text cua payload
        blob = json.dumps(payload, ensure_ascii=False)
        for m in re.finditer(r"(\d)(Năm|Tuần|Tháng)", blob):
            glue_hits.append((job_id, blob[m.start():m.start() + 12]))

        # hash on dinh: xay lai lan 2 -> content_hash phai bang nhau
        env2 = build_raw_envelope(html, job_id, url, source_category=cat)
        if env["metadata"]["content_hash"] != env2["metadata"]["content_hash"]:
            hash_stable = False

    n = len(files)
    print("=" * 70)
    print(f"SO FILE HTML doc duoc: {n}")
    print(f"JSON-LD (job-posting-schema) hien dien: {jsonld_present}/{n}")
    print("-" * 70)
    print("TY LE RONG TUNG KHOA raw_payload:")
    for k in RAW_KEYS:
        rate = empty_counter[k] / n * 100
        print(f"  {k:22s} rong {empty_counter[k]:2d}/{n}  ({rate:5.1f}%)")
    print("-" * 70)
    print(f"Kiem tra so DINH LIEN 'Nam' (\\d+Năm): {len(glue_hits)} vu")
    for jid, mau in glue_hits[:10]:
        print(f"    {jid}: {mau!r}")
    print("-" * 70)
    print(f"HASH LAN 1 vs LAN 2 cung file bang nhau: {hash_stable}")
    print("=" * 70)

    # chon 2 job_id: nho nhat va 1 cai co tags
    ids_sorted = sorted(envelopes)
    smallest = ids_sorted[0]
    with_tags = next((j for j in ids_sorted if envelopes[j]["raw_payload"]["job-tags"]), None)

    print(f"\n\n# ENVELOPE 1 — job_id nho nhat: {smallest}")
    print(json.dumps(envelopes[smallest], ensure_ascii=False, indent=2))

    print(f"\n\n# ENVELOPE 2 — job_id CO tags: {with_tags}")
    print(json.dumps(envelopes[with_tags], ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
