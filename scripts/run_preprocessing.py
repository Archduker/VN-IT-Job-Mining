# -*- coding: utf-8 -*-
"""Driver chuỗi PH9: Clean → Dedup → Integration → Transformation → Normalization → Encoding, rồi processing 07/08/09.

    python scripts/run_preprocessing.py --step clean --source glints --dry-run
    python scripts/run_preprocessing.py --step all --source all [--dry-run] [--translate]

Báo cáo: reports/preprocessing/<bước>/ (07-09 ghi ở reports/processing/<bước>/ và được sao sang reports/preprocessing/<bước>/).
Mỗi báo cáo có khối `samples` (seed 42). Tóm tắt chuỗi: reports/pipeline/chain_run.json (chain_dry_run.json khi --dry-run).
Dry-run: bước thiếu đầu ra của bước trước báo INPUT_MISSING, không điền 0. --translate (mặc định TẮT) chỉ áp cho 03 khi chạy thật.
Chỉ ghi trên máy, không đụng R2. Đặc tả: docs/spec/preprocessing/spec/P0_pipeline_contract.md, PH9_*.md.
"""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from preprocessing.common import SOURCES, STEPS  # noqa: E402

PROCESSING_STEPS = ("07_sections", "08_skills", "09_tokens")
CHAIN = (*STEPS, *PROCESSING_STEPS)
MODULES = {
    "01_clean": "preprocessing.clean.run",
    "01b_deduplication": "preprocessing.deduplication.run",
    "02_integration": "preprocessing.integration.run",
    "03_transformation": "preprocessing.transformation.run",
    "04_normalization": "preprocessing.normalization.run",
    "05_encoding": "preprocessing.encoding.run",
    "07_sections": "processing.extraction.run",  # 07 và 08 do cùng một lần gọi
    "08_skills": "processing.extraction.run",
    "09_tokens": "processing.transformation.run",
}
# 03 → 04: cột chung; 03 đọc từ 02: cặp (trường, cột trước, cột sau)
PAIRS03 = [("description_clean", "raw_description_text", "description_clean"),
           ("requirements_clean", "raw_requirements_text", "requirements_clean"),
           ("job_title_clean", "job_title", "job_title_clean"),
           ("salary_min_vnd", "raw_salary_text", "salary_min_vnd"),
           ("exp_min_years", "raw_experience_text", "exp_min_years"),
           ("posted_date", "raw_posted_date", "posted_date"),
           ("headcount", "raw_headcount", "headcount")]


def missing_inputs(step: str, sources, root: Path = ROOT) -> list[str]:
    """Đường dẫn đầu vào còn thiếu của bước (tương đối root); rỗng = đủ."""
    P = root / "data" / "preprocessing"
    if step == "01_clean":
        need = [root / "data" / s / "raw" for s in sources]
    elif step == "01b_deduplication":
        need = [P / "01_clean" / f"{s}.jsonl" for s in sources]
    elif step == "02_integration":
        need = [P / "01b_deduplication" / f"{s}.jsonl" for s in sources]
    else:
        prev = {"03_transformation": "02_integration"}.get(step, "03_transformation" if step == "04_normalization" else "04_normalization")
        need = [P / prev / "all.parquet"]
    return [p.relative_to(root).as_posix() for p in need if not p.exists()]


def _samples(step: str, sources, root: Path) -> dict:
    import pandas as pd

    from preprocessing.common.samples import dropped_samples, pair_samples
    P = root / "data" / "preprocessing"
    rd = lambda n: pd.read_parquet(P / n / "all.parquet")  # noqa: E731
    if step in ("01_clean", "01b_deduplication", "02_integration"):
        spec = {"01_clean": ("job_title", "job_title", "DROPPED {rule}: {reason}"),
                "01b_deduplication": ("duplicate_of", "job_id", "DROPPED {drop_rule} -> {duplicate_of}"),
                "02_integration": ("rejected_line", "job_id", "REJECTED {rule}: {reason}")}[step]
        return {s: dropped_samples(P / "rejected" / step / f"{s}.jsonl", s, field=spec[0], before_key=spec[1],
                                   after_fmt=spec[2]) for s in sources}
    if step == "03_transformation":
        return pair_samples(rd("02_integration"), rd("03_transformation"), PAIRS03)
    if step == "04_normalization":
        b, a = rd("03_transformation"), rd("04_normalization")
        cols = [c for c in b.columns if c in a.columns and c not in ("job_id_global", "source_platform")]
        return pair_samples(b, a, [(c, c, c) for c in cols])
    b = rd("04_normalization")
    O = root / "data" / "processing"
    if step == "07_sections":
        x = pd.read_parquet(O / step / "all.parquet").groupby("job_id_global")["section"].agg(lambda v: v.value_counts().to_dict())
        return pair_samples(b, x.rename("sections").reset_index(), [("sections", "description_clean", "sections")])
    if step == "08_skills":
        x = pd.read_parquet(O / step / "job_skills.parquet").groupby("job_id_global")["slug"].agg(lambda v: sorted(set(v)))
        return pair_samples(b, x.rename("skills").reset_index(), [("skills", "skills_list", "skills")])
    if step == "09_tokens":
        x = pd.read_parquet(O / step / "all.parquet")[["job_id_global", "tokens_nostop"]]
        return pair_samples(b, x, [("tokens_nostop", "description_clean", "tokens_nostop")])
    return {}


def _finish_reports(step, sources, dry_run, root, partial):
    """Gắn samples vào báo cáo; 07-09 sao báo cáo từ reports/processing sang reports/preprocessing."""
    from preprocessing.common.samples import inject_samples
    rep = root / "reports"
    pre = rep / "preprocessing" / ("_partial" if partial and step in STEPS[:2] else "")
    try:
        by_src, reason = ({}, "DRY_RUN_NO_OUTPUT") if dry_run else (_samples(step, sources, root), None)
    except Exception as e:  # mẫu lỗi không được làm hỏng chuỗi; ghi lý do trung thực
        by_src, reason = {}, f"SAMPLES_ERROR: {type(e).__name__}: {str(e)[:120]}"
    if step in PROCESSING_STEPS:
        inject_samples(rep / "processing", step, by_src, reason, [*sources])
        if (rep / "processing" / step).is_dir():
            (pre / step).mkdir(parents=True, exist_ok=True)
            for f in (rep / "processing" / step).glob("*.json"):
                shutil.copy2(f, pre / step / f.name)
    else:
        inject_samples(pre, step, by_src, reason, [*sources])


def _totals(reports: dict) -> dict:
    per = {k: v for k, v in reports.items() if k != "_all" and hasattr(v, "data")}
    ins = sum(r.data["input"]["rows"] for r in per.values())
    out = sum(r.data["output"]["rows"] for r in per.values())
    drop = sum(d["rows"] for r in per.values() for d in r.data["dropped"])
    return {"input": ins, "output": out, "dropped": drop, "conserved": ins == out + drop,
            "mode": next(iter(per.values())).data["mode"] if per else None,
            "rejected": {k: sum(d["rows"] for d in r.data["dropped"]) for k, r in per.items()}}


def run_chain(steps, sources, dry_run: bool, translate: bool = False, root: Path = ROOT, write_summary: bool = True) -> list[dict]:
    results, done = [], {}
    partial = set(sources) != set(SOURCES)
    for step in steps:  # đúng thứ tự, không đảo
        res = {"step": step, "status": "OK", "missing": [], "input": None, "output": None, "dropped": None,
               "conserved": None, "mode": "dry_run" if dry_run else "applied"}
        results.append(res)
        if not dry_run and partial and step in ("02_integration", "03_transformation", "04_normalization"):
            raise ValueError(f"{step}: chạy thật thiếu nguồn sẽ ghi đè all.parquet bằng một phần; dùng --source all")
        miss = missing_inputs(step, sources, root)
        if miss:
            res.update(status="INPUT_MISSING", missing=miss)
            print(f"{step}: INPUT_MISSING {miss} → chạy thật bước trước đó trước")
            if not dry_run:
                break
            continue
        mod = MODULES[step]
        try:
            if mod not in done or step not in done[mod]:
                m = importlib.import_module(mod)
                kw = {"translate": translate} if step == "03_transformation" else {}
                out = m.run(sources, dry_run=dry_run, **kw)
                if step in PROCESSING_STEPS and mod == "processing.extraction.run":
                    done[mod] = out  # {07: reps, 08: reps}
                else:
                    done[mod] = {step: out}
            reports = done[mod][step]
        except ValueError as e:  # 05_encoding cần cấu hình tường minh (xem preprocessing/encoding)
            res.update(status="SKIPPED", note=str(e)[:160])
            print(f"{step}: SKIPPED - {str(e)[:100]}")
            continue
        res.update(_totals(reports))
        print(f"{step}: input {res['input']} → output {res['output']} + bỏ {res['dropped']} ({res['mode']}), "
              f"bảo toàn={res['conserved']}")
        for src, r in reports.items():
            if src != "_all" and hasattr(r, "data"):
                d = r.data
                print(f"  {src}: input {d['input']['rows']} → output {d['output']['rows']} bỏ {sum(x['rows'] for x in d['dropped'])}")
        _finish_reports(step, sources, dry_run, root, partial)
    if write_summary:
        out = root / "reports" / "pipeline" / ("chain_dry_run.json" if dry_run else "chain_run.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                   "sources": list(sources), "translate": translate, "steps": results},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def main(argv=None) -> int:
    step_map = {s.split("_", 1)[1]: s for s in CHAIN}
    step_map.update({s: s for s in CHAIN})
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--step", required=True, choices=[*step_map.keys(), "all"])
    parser.add_argument("--source", default="all", choices=[*SOURCES, "all"])
    parser.add_argument("--dry-run", action="store_true", help="chỉ đọc và ghi báo cáo, không ghi dữ liệu")
    parser.add_argument("--translate", action="store_true", help="dịch JD tiếng Anh (envit5), mặc định TẮT; bỏ qua khi --dry-run")
    args = parser.parse_args(argv)
    steps = list(CHAIN) if args.step == "all" else [step_map[args.step]]
    sources = list(SOURCES) if args.source == "all" else [args.source]
    res = run_chain(steps, sources, args.dry_run, args.translate)
    return 1 if any(r["status"] == "INPUT_MISSING" for r in res) and not args.dry_run else 0


if __name__ == "__main__":
    sys.exit(main())
