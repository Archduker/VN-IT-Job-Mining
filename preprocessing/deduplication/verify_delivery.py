"""Tái chạy dữ liệu thật vào thư mục riêng; không ghi đè snapshot bàn giao.

python -m preprocessing.deduplication.verify_delivery --output-dir <thư-mục-mới>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from preprocessing.clean import run as clean
from preprocessing.common import REPO_ROOT, SOURCES, step_report
from preprocessing.deduplication import inter_source as inter
from preprocessing.deduplication import run as dedup
from preprocessing.integration.json_flattener import flatten_raw_job_record


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def source_hashes():
    return {str(p.relative_to(REPO_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("clean", "deduplication")
            for p in (REPO_ROOT / "preprocessing" / folder).glob("*.py")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    protected = [step_report.REPORTS_ROOT.resolve(),
                 *[(REPO_ROOT / "data" / s / "raw").resolve() for s in SOURCES]]
    if any(output.is_relative_to(path) for path in protected):
        parser.error("không ghi bằng chứng vào raw hoặc reports chính")
    if output.exists():
        parser.error("output-dir phải là thư mục mới để bảo toàn các kết quả trước")
    output.mkdir(parents=True)
    original_reports = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in step_report.REPORTS_ROOT.rglob("*.json")}
    baseline = dedup.OUT_DIR / "golden_master_jobs.jsonl"
    original_gold = read_rows(baseline) if baseline.exists() else []
    hashes = source_hashes()
    saved = (step_report.REPORTS_ROOT, clean.OUT_DIR, clean.REVIEW_DIR, dedup.IN_DIR, dedup.OUT_DIR,
             dedup.REJECTED_DIR)
    try:
        step_report.REPORTS_ROOT = output / "reports"
        clean.OUT_DIR = output / "01_clean"
        clean.REVIEW_DIR = output / "review"
        dedup.IN_DIR = clean.OUT_DIR
        dedup.OUT_DIR = output / dedup.STEP
        dedup.REJECTED_DIR = output / "rejected"
        print("Replaying Clean from local raw...", flush=True)
        clean.run(SOURCES, dry_run=False)
        print("Replaying Dedup...", flush=True)
        dedup.run(SOURCES, dry_run=False)
        reports = {
            step: json.loads((step_report.REPORTS_ROOT / step / "_all.json").read_text(encoding="utf-8"))
            for step in (clean.STEP, dedup.STEP)}
        gold = read_rows(dedup.OUT_DIR / "golden_master_jobs.jsonl")
        inputs = {f"{s}:{i['metadata']['job_id']}": i
                  for s in SOURCES for i in read_rows(clean.OUT_DIR / f"{s}.jsonl")}
        represented = [ref for g in gold for ref in g["source_job_ids"]]
        represented += [f"{r['source']}:{r['job_id']}" for g in gold for r in g["repost_records"]]
        counts = Counter(represented)
        lineage_ok = set(counts) == set(inputs) and all(v == 1 for v in counts.values())
        assert lineage_ok, "Mỗi input Clean phải ánh xạ đến đúng một master"
        old_by_id = {g["master_id"]: g for g in original_gold}
        changed_dates = [g["master_id"] for g in gold if g["master_id"] in old_by_id
                         and g["first_posted_at"] != old_by_id[g["master_id"]]["first_posted_at"]]
        date_errors = []
        for g in gold:
            dates = [inter.parse_date(flatten_raw_job_record(inputs[ref], ref.split(":", 1)[0]).get(
                "raw_posted_date")) for ref in g["source_job_ids"]]
            valid = [d for d in dates if d is not None]
            if valid and inter.parse_date(g["first_posted_at"]) != min(valid):
                date_errors.append(g["master_id"])
        assert not date_errors
        partial = {}
        for module in (clean, dedup):
            paths = list((step_report.REPORTS_ROOT / module.STEP).glob("*.json"))
            before = {p: p.read_bytes() for p in paths}
            module.main(["--source", "glints", "--dry-run"])
            partial[module.STEP] = all(p.read_bytes() == data for p, data in before.items())
            assert partial[module.STEP]
        assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in original_reports.items())
        assert source_hashes() == hashes, "Mã nguồn đã đổi trong lúc đo; chạy lại trước khi bàn giao"
        summary = {
            "reports": reports, "golden_rows": len(gold), "lineage_rows": len(represented),
            "lineage_exactly_once": lineage_ok, "changed_first_posted": changed_dates,
            "date_errors": date_errors, "partial_preserves_reports": partial,
            "original_reports_unchanged": True, "baseline_available": baseline.exists(),
            "source_sha256": hashes}
        (output / "verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Verified: {len(gold)} golden rows; {len(represented)} input references; "
              f"{len(changed_dates)} changed first-posted dates", flush=True)
    finally:
        (step_report.REPORTS_ROOT, clean.OUT_DIR, clean.REVIEW_DIR,
         dedup.IN_DIR, dedup.OUT_DIR, dedup.REJECTED_DIR) = saved
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
