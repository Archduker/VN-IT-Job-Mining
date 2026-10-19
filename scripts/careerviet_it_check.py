# -*- coding: utf-8 -*-
"""careerviet_it_check.py — KIEM KE sau luot cao: doc THANG cac raw envelope va in,
moi tin mot dong: job_id | title | "Ngành nghề" nguyen van | co CNTT? | HTTP status.
Kem TONG so tin co CNTT / tong so tin. CHI DOC, ghi ra stdout (khong ghi de file nao).

Cach dung (sau luot online):
    python -X utf8 scripts/careerviet_it_check.py --raw-dir data/careerviet/raw --date 2026-10-16
    python -X utf8 scripts/careerviet_it_check.py --raw-dir data/careerviet/raw --category c37_digital_mkt

Luu y ve HTTP status: envelope chi duoc sinh ra khi fetch thanh cong (HttpClient
raise_on_status=True -> moi ma 4xx/5xx khong tao envelope). Vi vay moi envelope ton tai
tuong duong "HTTP 200 (suy ra)". Tin duoc chon ma KHONG co envelope = chua tai duoc
(PENDING/FAILED), khong xuat hien o day; muon liet ke phan nay thi dung --phase view.
"""

import argparse
import json
from pathlib import Path

INDUSTRY_KEY = "Ngành nghề"
IT_TOKENS = ("cntt", "công nghệ thông tin")


def _has_it(industry_value) -> bool:
    """CNTT? = chu 'CNTT' (khong phan biet hoa thuong) xuat hien trong 'Ngành nghề'."""
    if industry_value is None:
        return False
    if isinstance(industry_value, str):
        parts = [industry_value]
    elif isinstance(industry_value, (list, tuple)):
        parts = [str(p) for p in industry_value]
    else:
        parts = [str(industry_value)]
    joined = " | ".join(parts).lower()
    return any(tok in joined for tok in IT_TOKENS)


def _fmt_industry(industry_value) -> str:
    if industry_value is None:
        return "None"
    if isinstance(industry_value, (list, tuple)):
        return json.dumps(list(industry_value), ensure_ascii=False)
    return str(industry_value)


def collect_latest(raw_dir: str, date: str | None = None,
                   category: str | None = None):
    """Tra ve (rows, skipped): rows = moi job_id phien ban cao nhat, skipped = file khong phai envelope."""
    root = Path(raw_dir)
    if date:
        root = root / date
    latest: dict[str, dict] = {}
    skipped: list[str] = []
    if not root.exists():
        return [], [f"KHONG TIM THAY THU MUC: {root}"]
    for fp in sorted(root.rglob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:
            skipped.append(f"{fp} (khong doc duoc JSON: {exc})")
            continue
        if not isinstance(data, dict) or "raw_payload" not in data:
            skipped.append(f"{fp} (khong phai raw envelope)")
            continue
        meta = data.get("metadata", {})
        rp = data.get("raw_payload", {})
        jid = str(meta.get("job_id") or fp.stem)
        if category and meta.get("source_category") != category:
            continue
        ver = meta.get("version", 1) or 0
        rec = {
            "job_id": jid,
            "version": ver,
            "title": rp.get("title"),
            "industry": rp.get(INDUSTRY_KEY),
            "source_category": meta.get("source_category"),
            "has_it": _has_it(rp.get(INDUSTRY_KEY)),
            "path": str(fp),
        }
        if jid not in latest or ver > latest[jid]["version"]:
            latest[jid] = rec
    return list(latest.values()), skipped


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Kiem ke CNTT trong raw envelope (chi doc).")
    p.add_argument("--raw-dir", default=str(Path("data") / "careerviet" / "raw"),
                   help="Thu muc chua envelope (mac dinh data/careerviet/raw)")
    p.add_argument("--date", default=None,
                   help="Loc theo ngay duoi raw-dir (vd 2026-10-16)")
    p.add_argument("--category", default=None,
                   help="Loc theo source_category (vd c37_digital_mkt)")
    args = p.parse_args(argv)

    rows, skipped = collect_latest(args.raw_dir, args.date, args.category)
    rows.sort(key=lambda r: r["job_id"])

    print("==== CAREERVIET IT CHECK (chi doc envelope) ====")
    print(f"raw_dir={args.raw_dir} date={args.date} category={args.category}")
    print(f"{'job_id':<12} {'CNTT':<5} {'ver':<4} {'HTTP':<16} title | Ngành nghề")
    print("-" * 90)
    n_it = 0
    for r in rows:
        n_it += 1 if r["has_it"] else 0
        print(f"{r['job_id']:<12} {'CO' if r['has_it'] else 'KHONG':<5} "
              f"{str(r['version']):<4} {'200 (suy ra)':<16} "
              f"{r['title']!r} | {_fmt_industry(r['industry'])}")

    print("-" * 90)
    print(f"TONG so tin co CNTT / tong so envelope: {n_it} / {len(rows)}")
    if skipped:
        print(f"(Bo qua {len(skipped)} khong phai envelope hop le)")
        for s in skipped:
            print("  -", s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
