"""Driver Data Mining M0–M6 (docs/spec/mining/): chạy các bước và ghi artifacts vào mining/artifacts/.

Cách chạy:
    python -m mining.run_mining_pipeline                      # dữ liệu thật (Silver + features + e5 khóa job)
    python -m mining.run_mining_pipeline --synthetic          # dữ liệu giả, ghi vào mining/artifacts/_synthetic/
    python -m mining.run_mining_pipeline --only fp,cluster    # chỉ chạy một phần (xem STEPS)
    python -m mining.run_mining_pipeline --dry-run            # tính xong nhưng không ghi file

Đầu ra (spec 07 §5.3, nạp vào Mart bằng scripts/load_mart_from_parquet.py):
    skill_association_rules.parquet, job_clusters.parquet, job_anomalies.parquet,
    skill_salary_shap_values.parquet, trained_salary_rf_model.joblib, mining_metrics.json
Chỉ đọc file trên máy và ghi trong thư mục --out; không đụng R2 hay PostgreSQL.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # chạy trực tiếp bằng đường dẫn file
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mining.anomaly import detect_anomalies  # noqa: E402
from mining.bi import run_bi  # noqa: E402
from mining.association import run_association, write_hand_check  # noqa: E402
from mining.clustering import cluster_jobs  # noqa: E402
from mining.config import (  # noqa: E402
    ARTIFACT_FILES,
    ARTIFACTS_DIR,
    DEFAULT_E5,
    DEFAULT_ENCODING_DICT,
    DEFAULT_FEATURES,
    DEFAULT_JOB_SKILLS,
    DEFAULT_TABLE,
    SYNTHETIC_ARTIFACTS_DIR,
    MiningParams,
)
from mining.data_io import MiningData, file_sha256, load_mining_data, prepare_mining_data  # noqa: E402
from mining.salary_model import train_salary_model  # noqa: E402
from mining.sanity import run_sanity_checks, summarize  # noqa: E402

logger = logging.getLogger("mining")
# Chuỗi đã duyệt (spec 03 mục 7, M0.5). bi (M1) và recommend (M6) chưa có code: chọn thì báo lỗi rõ.
STEPS = ("bi", "fp", "cluster", "anomaly", "salary", "recommend")
NOT_BUILT = {"recommend": "M6"}
_sha256 = file_sha256


def _json_default(o: Any) -> Any:
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return o.as_posix()
    return str(o)


def run_pipeline(
    data: MiningData,
    out_dir: Path,
    steps: list[str],
    params: MiningParams | None = None,
    dry_run: bool = False,
    compute_shap: bool = True,
    extra_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Chạy các bước đã chọn trên MiningData; ghi artifacts nếu không dry_run. Trả metrics."""
    p = params or MiningParams()
    meta, skills = data.meta, data.skills
    metrics: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "random_state": p.random_state,
        "steps": steps,
        "dry_run": dry_run,
        **(extra_metrics or {}),
        "data": {"table_path": data.table_path.as_posix() if data.table_path else None,
                 "n_jobs": data.n_jobs, "n_skill_columns": int(skills.shape[1]),
                 "n_cols": {"skill": int(skills.shape[1]), "concept": int(data.concepts.shape[1]),
                            "soft": int(data.soft.shape[1])},
                 "skill_matrix_sparsity": round(float(1 - skills.to_numpy().mean()), 4) if skills.size else None,
                 "e5_shape": None if data.e5 is None else list(data.e5.shape),
                 "input_sha256": data.input_sha256,
                 "resolved_columns": data.resolved_columns, "row_log": data.row_log, "notes": data.notes},
    }
    outputs: dict[str, Any] = {}
    timings: dict[str, float] = {}

    if "bi" in steps:
        t = time.perf_counter()
        sd1, m = run_bi(data, p.bi)
        outputs.setdefault("json", {}).update(sd1)
        metrics["bi"] = m
        timings["bi"] = time.perf_counter() - t
        logger.info("BI: %d bảng, %d ô ít dữ liệu, tổng khớp: %s", m["n_tables"], m["n_cells_low_data"], m["totals_ok"])

    if "fp" in steps:
        t = time.perf_counter()
        rules, sd2, hand, m = run_association(data, p.association, p.bi)
        outputs["rules"], metrics["association"] = rules, m
        outputs.setdefault("json", {}).update(sd2)
        outputs["hand_check_rules"] = hand
        timings["fp"] = time.perf_counter() - t
        logger.info("FP-Growth: %d luật (%d vĩ mô)", m["n_rules_total"], m["n_rules_macro"])

    glosh = glosh_flag = None
    if "cluster" in steps:
        t = time.perf_counter()
        clusters, m = cluster_jobs(skills, meta, p.clustering, random_state=p.random_state, e5=data.e5,
                                   concepts=data.concepts)  # có e5 thì tự so thêm bản không e5 (without_e5)
        outputs["clusters"], metrics["clustering"] = clusters, m
        outputs.setdefault("json", {})["cluster_family_crosstab.json"] = {
            "crosstab": m["crosstab"], "hybrid_clusters": m["hybrid_clusters"], "niche": m["niche"],
            "clusters": [{k: c[k] for k in ("cluster_id", "cluster_name", "size", "dominant_job_family",
                                            "job_family_purity")} for c in m["clusters"]]}
        hc = clusters[clusters["family_mismatch"]]
        outputs["hand_check_mismatch"] = (hc.sample(min(20, len(hc)), random_state=p.random_state)
                                          [["job_id", "job_title", "job_family", "cluster_id", "cluster_name"]]
                                          .assign(dung=pd.NA, ghi_chu=pd.NA).reset_index(drop=True))
        # tin không vào phân cụm (M3.1b) không có GLOSH: 0 và không cờ
        glosh = np.nan_to_num(clusters["glosh_outlier_score"].to_numpy(dtype=float), nan=0.0)
        glosh_flag = clusters["is_outlier"].to_numpy()
        timings["cluster"] = time.perf_counter() - t
        logger.info("K-Means: k=%d, silhouette=%.4f", m["best_k"], m["silhouette"])

    if "anomaly" in steps:
        t = time.perf_counter()
        anomalies, m = detect_anomalies(meta, glosh, glosh_flag, p.anomaly, p.random_state)
        outputs["anomalies"], metrics["anomaly"] = anomalies, m
        timings["anomaly"] = time.perf_counter() - t
        logger.info("Anomaly: %d tin bị gắn cờ (%.2f%%)", m["n_flagged"], 100 * m["anomaly_rate"])

    skill_values = None
    if "salary" in steps:
        t = time.perf_counter()
        model, skill_values, m, extra = train_salary_model(meta, skills, p.salary, p.random_state, compute_shap,
                                                           concepts=data.concepts)
        outputs["shap"], outputs["model"], metrics["salary"] = skill_values, model, m
        if model is not None:
            outputs["estimates"] = extra["estimates"]
            outputs.setdefault("json", {})["salary_factor_importance.json"] = {
                "factor_importance": extra["factor_importance"], "salary_distribution": extra["distribution"],
                "notes": m["notes"]}
        timings["salary"] = time.perf_counter() - t
        if "holdout" in m:
            logger.info("Random Forest: R2(log)=%.4f, MAE=%.3f triệu", m["holdout"]["r2_log"], m["holdout"]["mae_mil"])
        else:
            logger.warning("Bỏ qua mô hình lương: %s", m.get("skipped"))

    checks = run_sanity_checks(meta, skills, skill_values)
    metrics["sanity_checks"] = checks
    metrics["sanity_summary"] = summarize(checks)
    metrics["targets_summary"] = _targets_summary(metrics)
    metrics["timings_sec"] = {k: round(v, 2) for k, v in timings.items()}

    if not dry_run:
        write_artifacts(outputs, metrics, out_dir, data)
    return metrics


def _targets_summary(m: dict[str, Any]) -> dict[str, Any]:
    s: dict[str, Any] = {}
    if "bi" in m:
        s["bi_totals_ok"] = m["bi"]["totals_ok"]
    if "association" in m:
        s["fp_min_rules"] = m["association"]["meets_min_rules_target"]
        s["fp_stability"] = m["association"].get("meets_stability_target")
    if "clustering" in m:
        s["cluster_silhouette"] = m["clustering"]["meets_silhouette_target"]
        s["cluster_min_k"] = m["clustering"]["meets_min_clusters"]
        s["cluster_davies_bouldin"] = m["clustering"]["meets_davies_bouldin_target"]
        s["cluster_stability"] = m["clustering"]["meets_stability_target"]
        s["cluster_min_share"] = m["clustering"]["meets_min_cluster_share"]
        s["cluster_no_skill_count_split"] = not m["clustering"]["skill_count_violations"]
    if "salary" in m and "holdout" in m["salary"]:
        s["salary_plan"] = m["salary"]["plan"]
        s["salary_beats_baseline_10pct"] = m["salary"]["meets_baseline_margin"]
        s["salary_cv_std"] = m["salary"]["meets_cv_std_target"]
        s["salary_no_company_overlap"] = m["salary"]["n_companies_overlap"] == 0
    s["sanity_all_passed"] = m["sanity_summary"]["all_passed"]
    return s


def write_artifacts(outputs: dict[str, Any], metrics: dict[str, Any], out_dir: Path, data: MiningData) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for key in ("rules", "clusters", "anomalies", "shap", "estimates"):
        df = outputs.get(key)
        if df is None:
            continue
        path = out_dir / ARTIFACT_FILES[key]
        df.to_parquet(path, engine="pyarrow", index=False)
        written[key] = {"path": path.as_posix(), "rows": int(len(df))}
    if outputs.get("model") is not None:
        import joblib

        path = out_dir / ARTIFACT_FILES["model"]
        bundle = {
            "model": outputs["model"],
            "feature_names": list(outputs["model"].feature_names_in_),
            "target": "log1p(salary_target_m, triệu VNĐ/tháng)",
            "config": metrics["salary"]["config_used"],
            "generated_at": metrics["generated_at"],
        }
        joblib.dump(bundle, path, compress=3)
        written["model"] = {"path": path.as_posix(), "bytes": path.stat().st_size}
    if outputs.get("hand_check_rules") is not None:
        path = out_dir / "sd2_hand_check.csv"
        if write_hand_check(outputs["hand_check_rules"], path):
            written["hand_check_rules"] = {"path": path.as_posix(), "rows": int(len(outputs["hand_check_rules"]))}
    if outputs.get("hand_check_mismatch") is not None:
        path = out_dir / "sd3_mismatch_hand_check.csv"
        if write_hand_check(outputs["hand_check_mismatch"], path):
            written["hand_check_mismatch"] = {"path": path.as_posix(), "rows": int(len(outputs["hand_check_mismatch"]))}
    for name, obj in (outputs.get("json") or {}).items():
        path = out_dir / name
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=_json_default), encoding="utf-8")
        written[name] = {"path": path.as_posix()}
    metrics["artifacts"] = written
    (out_dir / ARTIFACT_FILES["metrics"]).write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    logger.info("Đã ghi %d artifacts vào %s", len(written) + 1, out_dir)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", "--golden", dest="table", type=Path, default=DEFAULT_TABLE,
                    help=f"bảng Silver (mặc định {DEFAULT_TABLE}); --golden là bí danh cũ. Thiếu thì báo lỗi")
    ap.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    ap.add_argument("--encoding-dict", type=Path, default=DEFAULT_ENCODING_DICT)
    ap.add_argument("--job-skills", type=Path, default=DEFAULT_JOB_SKILLS, help="bảng 08 job_skills.parquet (M1, M6)")
    ap.add_argument("--e5", type=Path, default=DEFAULT_E5, help="job_emb.npz (khóa job); thiếu file thì phân cụm không dùng e5")
    ap.add_argument("--out", type=Path, default=None, help=f"mặc định {ARTIFACTS_DIR}")
    ap.add_argument("--only", type=str, default=",".join(s for s in STEPS if s not in NOT_BUILT), help="các bước, cách nhau dấu phẩy: " + ",".join(STEPS))
    ap.add_argument("--synthetic", action="store_true", help="chạy trên dữ liệu giả (mining/synthetic.py)")
    ap.add_argument("--synthetic-n", type=int, default=1500)
    ap.add_argument("--no-shap", action="store_true", help="bỏ TreeSHAP (chạy nhanh hơn)")
    ap.add_argument("--dry-run", action="store_true", help="tính xong nhưng không ghi file")
    ap.add_argument("--seed", type=int, default=None)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = _parse_args(argv)
    steps = [s.strip() for s in args.only.split(",") if s.strip()]
    unknown = sorted(set(steps) - set(STEPS))
    if unknown:
        logger.error("Bước không hợp lệ: %s (chọn trong %s)", unknown, STEPS)
        return 2
    pending = [s for s in steps if s in NOT_BUILT]
    if pending:
        logger.error("Bước %s chưa làm (%s); xem docs/prompting/mining/.", pending, [NOT_BUILT[s] for s in pending])
        return 2
    params = MiningParams()
    if args.seed is not None:
        params.random_state = args.seed

    extra: dict[str, Any] = {"synthetic": bool(args.synthetic)}
    if args.synthetic:
        from mining.synthetic import make_synthetic_jobs

        bundle = make_synthetic_jobs(n_jobs=args.synthetic_n, seed=params.random_state)
        skills_map = bundle.encoding_dict["skills"]["skills_map"]
        data = prepare_mining_data(bundle.golden, bundle.features, skills_map)
        data.notes.insert(0, "DỮ LIỆU GIẢ (mining/synthetic.py): không dùng để báo cáo.")
        out_dir = args.out or SYNTHETIC_ARTIFACTS_DIR
        extra["inputs"] = {"synthetic_n": args.synthetic_n}
    else:
        if not Path(args.table).exists():
            logger.error("Không tìm thấy bảng Silver %s. Chạy preprocessing trước, hoặc dùng --synthetic.", args.table)
            return 2
        data = load_mining_data(args.table, args.features, args.encoding_dict, args.e5, args.job_skills)
        out_dir = args.out or ARTIFACTS_DIR
        paths = {"table": args.table, "features": args.features, "encoding_dict": args.encoding_dict, "e5": args.e5,
                 "job_skills": args.job_skills}
        extra["inputs"] = {k: {"path": Path(v).as_posix(), "sha256_16": data.input_sha256.get(k)}
                           for k, v in paths.items()}

    metrics = run_pipeline(data, out_dir, steps, params, args.dry_run, not args.no_shap, extra)
    print(json.dumps({"targets": metrics["targets_summary"], "sanity": metrics["sanity_summary"],
                      "out_dir": None if args.dry_run else Path(out_dir).as_posix()},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
