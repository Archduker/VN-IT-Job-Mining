# -*- coding: utf-8 -*-
"""crawlers.preprocessing.eda.pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
EDAPipeline - Bo dieu phoi phan tich EDA toan dien (VN-IT-Job-Mining).

Quy trinh:
  1. Doc du lieu mot lan duy nhat qua EDALoader (load_raw_records_with_report).
  2. Tach ban ghi hop le va phan tu khong hop le tu loader report.
  3. Chay EDAProfiler, SalaryAnalyzer, DateAnalyzer, TextAnalyzer, RiskDetector
     tren cung tap ban ghi hop le.
  4. Tong hop ket qua vao cau truc eda_results thong nhat.
  5. Do thoi gian thuc thi tung giai doan va tong thoi gian.
  6. Thu thap so lieu bo nho bang tracemalloc (Python-traced heap).
     KHONG dien giai thanh toan bo RAM vat ly.
  7. Xuat bao cao JSON hop le neu duoc yeu cau; khong ghi de du lieu dau vao.

Xu ly loi:
  - Neu mot analyzer that bai -> ghi nhan stage/error_type/message.
  - Cac analyzer khac tiep tuc chay doc lap.
  - status = PARTIAL neu bat ky analyzer nao that bai.
  - NaN/Infinity/datetime/set duoc lam sach truoc khi xuat JSON.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

# Dam bao thu muc goc du an luon co trong sys.path khi chay truc tiep dang script
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from crawlers.preprocessing.eda.loader import (
    EDALoader,
    EDALoaderError,
    InvalidJSONStructureError,
)
from crawlers.preprocessing.eda.profiler import EDAProfiler
from crawlers.preprocessing.eda.salary_analyzer import SalaryAnalyzer
from crawlers.preprocessing.eda.date_analyzer import DateAnalyzer
from crawlers.preprocessing.eda.text_analyzer import TextAnalyzer
from crawlers.preprocessing.eda.risk_detector import RiskDetector


# ---------------------------------------------------------------------------
# Hang so cau hinh pipeline
# ---------------------------------------------------------------------------

PIPELINE_VERSION = "2.3.0"

ANALYSIS_CONFIG: Dict[str, Any] = {
    "thin_content": {
        "min_bullets": 2,
        "min_words": 20,
        "description": "Noi dung mong khi bullet_count < 2 HOAC word_count < 20",
    },
    "out_of_it_rules": {
        "categories": [
            "CHEMISTRY", "TEXTILE_GARMENT", "HEALTHCARE_MEDICAL",
            "HOSPITALITY_SECURITY", "REAL_ESTATE", "LOGISTICS_DRIVER",
            "EARLY_EDUCATION", "PURE_ACCOUNTING",
        ],
        "safeguard": (
            "Bao ve boi IT safeguard regex; neu tieu de chua tu khoa IT manh "
            "thi khong gan co du khop quy tac ngoai nganh"
        ),
        "result_label": "CANDIDATE_FOR_MANUAL_REVIEW - khong tu dong xoa",
    },
    "salary_extreme_outliers": {
        "VND_MONTHLY_min": 500_000,
        "VND_MONTHLY_max": 500_000_000,
        "USD_MONTHLY_min": 50,
        "USD_MONTHLY_max": 30_000,
        "note": (
            "Chi ap dung khi currency VA pay_period cung xac dinh duoc; "
            "khong suy doan don vi con thieu"
        ),
    },
    "salary_unknown_period_anomalies": {
        "zero_or_negative": True,
        "VND_threshold_min": 20_000,
        "USD_threshold_min": 5,
        "note": (
            "Canh bao rieng cho cac muc luong bat thuong ro rang (<= 0 hoac duoi san toi thieu) "
            "khi chua xac dinh duoc ky luong (UNKNOWN). Khong tu suy doan thanh luong thang/nam."
        ),
    },
    "top_skills_count": 30,
}


# ---------------------------------------------------------------------------
# Tien ich JSON-safe serialization
# ---------------------------------------------------------------------------

def _sanitize_for_json(obj: Any) -> Any:
    """De quy lam sach doi tuong de dam bao tuan tu hoa JSON hop le.

    - float NaN / Infinity -> None
    - datetime -> ISO 8601 string
    - set -> sorted list
    - Cac kieu khac khong tuong thich -> str(obj)
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    if isinstance(obj, set):
        return [_sanitize_for_json(item) for item in sorted(obj, key=str)]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (int, str, bool)) or obj is None:
        return obj
    return str(obj)


# ---------------------------------------------------------------------------
# EDAPipeline
# ---------------------------------------------------------------------------

_T = TypeVar("_T")


class EDAPipeline:
    """Bo dieu phoi toan bo quy trinh EDA tu doc file den tong hop ket qua.

    Vi du su dung::

        pipeline = EDAPipeline()
        results = pipeline.run("data/processed/preClean/merged_jobs_clean.json")
        pipeline.save_report(results, "reports/eda_report.json")
    """

    def __init__(self) -> None:
        # Dem so lan Loader duoc goi thuc su (dung trong test de xac nhan load 1 lan)
        self._load_count: int = 0

    @property
    def load_count(self) -> int:
        """So lan load_raw_records_with_report thuc su duoc goi."""
        return self._load_count

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        file_path: Union[str, Path],
        *,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Chay toan bo pipeline EDA tren mot tep du lieu.

        Args:
            file_path: Duong dan toi tep JSON dau vao.
            output_path: (Tuy chon) Duong dan xuat bao cao JSON.
                         Phai khac file_path de tranh ghi de du lieu nguon.

        Returns:
            Dict ket qua EDA day du, an toan de tuan tu hoa thanh JSON.

        Raises:
            ValueError: Neu output_path trung voi file_path.
        """
        run_started_at = datetime.now(timezone.utc).isoformat()
        pipeline_start = time.perf_counter()

        stage_timings: Dict[str, Optional[float]] = {}
        errors: List[Dict[str, str]] = []
        partial = False
        mem_after_load: Dict[str, Any] = {}

        # Kiem tra output_path khong trung voi input
        input_path_resolved = Path(file_path).resolve()
        if output_path is not None:
            out_resolved = Path(output_path).resolve()
            if out_resolved == input_path_resolved:
                raise ValueError(
                    "output_path khong duoc trung voi file_path dau vao. "
                    "Pipeline tuyet doi khong ghi de du lieu nguon."
                )

        # ---- Buoc 1: Nap du lieu (mot lan duy nhat) ----------------------
        valid_records: List[Dict[str, Any]] = []
        loader_report: Dict[str, Any] = {}
        t0 = time.perf_counter()

        try:
            tracemalloc.start()
            valid_records, loader_report = EDALoader.load_raw_records_with_report(file_path)
            self._load_count += 1
            _mem_current, _mem_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            mem_after_load = {
                "peak_traced_bytes": _mem_peak,
                "peak_traced_mb": round(_mem_peak / (1024 * 1024), 4),
                "method": (
                    "tracemalloc - Python-traced heap peak; "
                    "KHONG dai dien cho toan bo RAM vat ly cua tien trinh"
                ),
            }
        except (
            FileNotFoundError, EDALoaderError, InvalidJSONStructureError,
            json.JSONDecodeError, ValueError
        ) as exc:
            if tracemalloc.is_tracing():
                tracemalloc.stop()
            elapsed = round(time.perf_counter() - pipeline_start, 4)
            failed_report: Dict[str, Any] = {
                "run_metadata": {
                    "pipeline_version": PIPELINE_VERSION,
                    "run_started_at": run_started_at,
                    "input_file": str(file_path),
                    "input_file_size_bytes": None,
                    "status": "FAILED",
                    "failure_reason": f"{type(exc).__name__}: {exc}",
                    "analysis_config": ANALYSIS_CONFIG,
                },
                "input_summary": {},
                "loader_report": {"error": str(exc)},
                "profiler": None,
                "salary_analysis": None,
                "date_analysis": None,
                "text_analysis": None,
                "risk_analysis": None,
                "performance": {
                    "total_elapsed_seconds": elapsed,
                    "stage_timings_seconds": {},
                    "memory": {},
                },
                "errors": [
                    {"stage": "loader", "error_type": type(exc).__name__, "message": str(exc)}
                ],
            }
            return failed_report

        stage_timings["loader"] = round(time.perf_counter() - t0, 4)

        total_raw = loader_report.get("total_raw_elements", 0)
        valid_count = len(valid_records)
        invalid_count = loader_report.get("invalid_element_count", 0)

        # ---- Cac giai doan phan tich (doc lap, tiep tuc khi mot giai doan loi) ----
        profiler_result = self._run_stage(
            stage_name="profiler",
            fn=lambda: EDAProfiler.profile_dataset(valid_records),
            stage_timings=stage_timings,
            errors=errors,
        )
        if profiler_result is None:
            partial = True

        salary_result = self._run_stage(
            stage_name="salary_analyzer",
            fn=lambda: SalaryAnalyzer.analyze(valid_records),
            stage_timings=stage_timings,
            errors=errors,
        )
        if salary_result is None:
            partial = True

        date_result = self._run_stage(
            stage_name="date_analyzer",
            fn=lambda: DateAnalyzer.analyze(valid_records),
            stage_timings=stage_timings,
            errors=errors,
        )
        if date_result is None:
            partial = True

        text_result = self._run_stage(
            stage_name="text_analyzer",
            fn=lambda: TextAnalyzer.analyze(valid_records),
            stage_timings=stage_timings,
            errors=errors,
        )
        if text_result is None:
            partial = True

        risk_result = self._run_stage(
            stage_name="risk_detector",
            fn=lambda: RiskDetector.analyze(valid_records),
            stage_timings=stage_timings,
            errors=errors,
        )
        if risk_result is None:
            partial = True

        # ---- Tong hop ket qua -----------------------------------------------
        total_elapsed = round(time.perf_counter() - pipeline_start, 4)
        status = "PARTIAL" if partial else "SUCCESS"

        eda_results: Dict[str, Any] = {
            "run_metadata": {
                "pipeline_version": PIPELINE_VERSION,
                "run_started_at": run_started_at,
                "input_file": str(file_path),
                "input_file_size_bytes": loader_report.get("file_size_bytes"),
                "status": status,
                "analysis_config": ANALYSIS_CONFIG,
            },
            "input_summary": {
                "total_raw_elements": total_raw,
                "valid_record_count": valid_count,
                "invalid_element_count": invalid_count,
                "note": (
                    "valid_record_count = phan tu dict trong mang JSON; "
                    "invalid_element_count = phan tu khong phai dict (null, so, v.v.)"
                ),
            },
            "loader_report": loader_report,
            "profiler": profiler_result,
            "salary_analysis": salary_result,
            "date_analysis": date_result,
            "text_analysis": text_result,
            "risk_analysis": risk_result,
            "performance": {
                "total_elapsed_seconds": total_elapsed,
                "stage_timings_seconds": stage_timings,
                "memory": mem_after_load,
            },
            "errors": errors,
        }

        eda_results = _sanitize_for_json(eda_results)

        if output_path is not None:
            self.save_report(eda_results, output_path)

        return eda_results

    # ------------------------------------------------------------------
    # Tien ich luu bao cao
    # ------------------------------------------------------------------

    @staticmethod
    def save_report(
        results: Dict[str, Any],
        output_path: Union[str, Path],
        *,
        indent: int = 2,
        ensure_ascii: bool = False,
    ) -> Path:
        """Ghi ket qua EDA thanh tep JSON an toan.

        Args:
            results: Dict ket qua EDA (da qua _sanitize_for_json).
            output_path: Duong dan tep dau ra.
            indent: So khoang cach le JSON (mac dinh 2).
            ensure_ascii: Giu nguyen ky tu Unicode khi False.

        Returns:
            Path da luu.

        Raises:
            ValueError: Neu output_path trung voi input_file trong results.
        """
        out_path = Path(output_path).resolve()
        input_file = results.get("run_metadata", {}).get("input_file", "")
        if input_file:
            try:
                if Path(input_file).resolve() == out_path:
                    raise ValueError(
                        f"output_path '{out_path}' trung voi du lieu dau vao. "
                        "Tuyet doi khong ghi de du lieu nguon."
                    )
            except OSError:
                pass

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=indent, ensure_ascii=ensure_ascii)
        return out_path

    # ------------------------------------------------------------------
    # Noi bo
    # ------------------------------------------------------------------

    @staticmethod
    def _run_stage(
        *,
        stage_name: str,
        fn: Callable[[], _T],
        stage_timings: Dict[str, Optional[float]],
        errors: List[Dict[str, str]],
    ) -> Optional[_T]:
        """Chay mot giai doan phan tich, do thoi gian va bat loi.

        Returns:
            Ket qua cua fn() neu thanh cong, None neu that bai.
        """
        t0 = time.perf_counter()
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            errors.append({
                "stage": stage_name,
                "error_type": type(exc).__name__,
                "message": str(exc),
            })
            return None
        finally:
            stage_timings[stage_name] = round(time.perf_counter() - t0, 4)


# ---------------------------------------------------------------------------
# Entrypoint CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    """Entrypoint CLI cho EDAPipeline.

    Ho tro cac tham so:
      input_path: Duong dan toi tep JSON dau vao (mac dinh: data/processed/preClean/merged_jobs_clean.json).
      output_path: Duong dan tep xuat bao cao JSON (mac dinh: eda_report_<timestamp>.json cung thu muc input).
      --fail-on-partial: Thoat voi exit code 2 neu trang thai phan tich la PARTIAL (mac dinh thoat voi ma 0).

    Chinh sach Process Exit Code:
      +---------+-------------------+-----------------------+
      | Status  | Default exit code | With --fail-on-partial|
      +---------+-------------------+-----------------------+
      | SUCCESS | 0                 | 0                     |
      | PARTIAL | 0                 | 2                     |
      | FAILED  | 1                 | 1                     |
      +---------+-------------------+-----------------------+
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="crawlers.preprocessing.eda.pipeline",
        description=f"EDAPipeline v{PIPELINE_VERSION} - Bo dieu phoi phan tich EDA toan dien (VN-IT-Job-Mining).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    default_input = Path("data/processed/preClean/merged_jobs_clean.json")
    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        default=default_input,
        help="Duong dan toi tep JSON dau vao.",
    )
    parser.add_argument(
        "output_path",
        nargs="?",
        type=Path,
        default=None,
        help="Duong dan tep xuat bao cao JSON (mac dinh: tu sinh eda_report_<timestamp>.json cung thu muc).",
    )
    parser.add_argument(
        "--fail-on-partial",
        action="store_true",
        default=False,
        help="Thoat voi exit code 2 neu trang thai phan tich la PARTIAL (mac dinh thoat voi ma 0).",
    )

    args = parser.parse_args(argv)

    input_path_cli = args.input_path
    if args.output_path is not None:
        output_path_cli = args.output_path
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path_cli = input_path_cli.parent / f"eda_report_{ts}.json"

    print(f"[EDAPipeline v{PIPELINE_VERSION}]")
    print(f"  Input : {input_path_cli}")
    print(f"  Output: {output_path_cli}")
    if args.fail_on_partial:
        print("  Policy: --fail-on-partial enabled (PARTIAL -> exit code 2)")
    print("-" * 60)

    pipeline = EDAPipeline()
    try:
        results = pipeline.run(input_path_cli, output_path=output_path_cli)
    except Exception as exc:
        print(f"  CRITICAL FAILURE: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    meta = results.get("run_metadata", {})
    inp = results.get("input_summary", {})
    perf = results.get("performance", {})
    errs = results.get("errors", [])
    status = meta.get("status")

    print(f"  Status : {status}")
    print(
        f"  Records: {inp.get('total_raw_elements', 0):,} raw -> "
        f"{inp.get('valid_record_count', 0):,} valid / "
        f"{inp.get('invalid_element_count', 0):,} invalid"
    )
    print(f"  Time   : {perf.get('total_elapsed_seconds', 0):.2f}s total")
    mem_mb = perf.get("memory", {}).get("peak_traced_mb", "N/A")
    print(f"  Memory : peak traced = {mem_mb} MB (Python heap, tracemalloc)")
    if errs:
        print(f"  ERRORS ({len(errs)}):")
        for e in errs:
            print(f"    [{e['stage']}] {e['error_type']}: {e['message']}")
    print(f"  Report : {output_path_cli}")

    # Anh xa status -> exit code
    if status == "SUCCESS":
        return 0
    elif status == "PARTIAL":
        return 2 if args.fail_on_partial else 0
    elif status == "FAILED":
        return 1
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
