"""Chạy riêng bước Transformation trên dữ liệu đã được Integration."""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from preprocessing.transformation.record_transformer import (  # noqa: E402
    parse_date_to_iso,
    transform_job_record,
)
from preprocessing.transformation.salary_parser import (  # noqa: E402
    USD_VND_EXCHANGE_RATE,
    parse_salary_cascade,
)

SOURCES = (
    "careerviet",
    "glints",
    "itviec",
    "jobsgo",
    "topcv",
    "topdev",
    "vieclam24h",
    "vietnamworks",
)

logger = logging.getLogger("transformation_runner")
FRANKFURTER_API_URL = "https://api.frankfurter.dev/v1"
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_nans_to_none(obj: Any) -> Any:
    """Đệ quy chuyển đổi toàn bộ float('nan') thành None để serialize thành null chuẩn RFC 8259."""
    if isinstance(obj, float):
        return None if math.isnan(obj) else obj
    if isinstance(obj, dict):
        return {k: clean_nans_to_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nans_to_none(x) for x in obj]
    return obj


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = clean_nans_to_none(value)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(cleaned, output_file, ensure_ascii=False, indent=2, allow_nan=False)


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy dữ liệu Integration: {path}. "
            "Hãy chạy preprocessing.integration.run_integration trước."
        )

    with path.open(encoding="utf-8") as input_file:
        records = json.load(input_file)
    if not isinstance(records, list):
        raise ValueError(f"Dữ liệu Integration phải là JSON array: {path}")
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ValueError(f"Bản ghi thứ {index} trong {path} không phải JSON object.")
    return records


def _effective_fx_date(record: Mapping[str, Any]) -> str | None:
    for field in ("raw_posted_date", "crawled_at"):
        parsed_date = parse_date_to_iso(record.get(field))
        if parsed_date:
            return parsed_date
    return None


def _load_sgd_usd_rates(start_date: str, end_date: str) -> dict[str, float]:
    if not _DATE_PATTERN.fullmatch(start_date) or not _DATE_PATTERN.fullmatch(end_date):
        raise ValueError("Khoảng ngày tỷ giá phải ở định dạng YYYY-MM-DD.")

    url = (
        f"{FRANKFURTER_API_URL}/{start_date}..{end_date}"
        "?base=SGD&symbols=USD"
    )
    try:
        with urlopen(url, timeout=20) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Frankfurter API không khả dụng (%s). Sử dụng tỷ giá SGD/USD tham chiếu ngoại tuyến 0.75.",
            exc,
        )
        return {end_date: 0.75, start_date: 0.75}

    rates = payload.get("rates")
    if not isinstance(rates, dict):
        logger.warning("Frankfurter không trả về rates hợp lệ. Dùng tỷ giá fallback 0.75.")
        return {end_date: 0.75, start_date: 0.75}

    parsed_rates: dict[str, float] = {}
    for rate_date, currencies in rates.items():
        rate = currencies.get("USD") if isinstance(currencies, dict) else None
        if isinstance(rate, bool) or not isinstance(rate, int | float):
            raise ValueError(f"Tỷ giá SGD/USD không hợp lệ tại ngày {rate_date}.")
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError(f"Tỷ giá SGD/USD không hợp lệ tại ngày {rate_date}.")
        parsed_rates[rate_date] = float(rate)
    return parsed_rates


def _rate_for_date(
    requested_date: str, daily_rates: Mapping[str, float]
) -> tuple[float, str]:
    available_dates = sorted(rate_date for rate_date in daily_rates if rate_date <= requested_date)
    if not available_dates:
        if daily_rates:
            rate_date = min(daily_rates.keys())
            return daily_rates[rate_date] * USD_VND_EXCHANGE_RATE, rate_date
        raise ValueError(
            f"Không có tỷ giá SGD/USD tại hoặc trước ngày {requested_date}."
        )
    rate_date = available_dates[-1]
    return daily_rates[rate_date] * USD_VND_EXCHANGE_RATE, rate_date


def _transform_source_records(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    sgd_record_dates: dict[int, str] = {}
    for index, record in enumerate(records):
        jd_text = " ".join(
            str(record.get(field) or "")
            for field in ("raw_description_text", "raw_requirements_text")
        ).strip()
        salary = parse_salary_cascade(record.get("raw_salary_text"), jd_text)
        if (
            salary["salary_currency_original"] == "SGD"
            and (
                salary.get("salary_min_original") is not None
                or salary.get("salary_max_original") is not None
            )
        ):
            fx_date = _effective_fx_date(record)
            if not fx_date:
                job_id = record.get("job_id_global", f"record index {index}")
                raise ValueError(
                    f"Không thể quy đổi lương SGD cho {job_id}: thiếu ngày đăng và ngày crawl."
                )
            sgd_record_dates[index] = fx_date

    daily_rates: dict[str, float] = {}
    rate_range: tuple[str, str] | None = None
    if sgd_record_dates:
        earliest_date = min(sgd_record_dates.values())
        end_date = max(sgd_record_dates.values())
        start_date = (
            datetime.strptime(earliest_date, "%Y-%m-%d").date() - timedelta(days=14)
        ).isoformat()
        daily_rates = _load_sgd_usd_rates(start_date, end_date)
        rate_range = (start_date, end_date)

    transformed_records = []
    for index, record in enumerate(records):
        rate = None
        rate_date = None
        if index in sgd_record_dates:
            rate, rate_date = _rate_for_date(sgd_record_dates[index], daily_rates)
        transformed = transform_job_record(
            record,
            sgd_to_vnd_rate=rate,
            sgd_fx_rate_date=rate_date,
        )
        if any(
            isinstance(value, float) and not math.isfinite(value)
            for value in transformed.values()
        ):
            raise ValueError(f"Bản ghi thứ {index} chứa giá trị số không hữu hạn.")
        transformed_records.append(transformed)

    if rate_range:
        logger.info(
            "SGD FX range %s..%s fetched; rates effective on the nearest prior business day",
            *rate_range,
        )
    return transformed_records


def _build_report(source: str, records: Sequence[Mapping[str, Any]], output_path: Path) -> dict[str, Any]:
    currencies = Counter(
        str(record.get("salary_currency") or "unknown") for record in records
    )
    raw_date_fields = (
        ("raw_posted_date", "posted_date"),
        ("raw_updated_at", "updated_date"),
        ("raw_deadline", "deadline_date"),
        ("crawled_at", "crawled_at_iso"),
    )
    date_metrics = {
        output_field: {
            "input_non_empty": sum(bool(record.get(raw_field)) for record in records),
            "parsed": sum(bool(record.get(output_field)) for record in records),
        }
        for raw_field, output_field in raw_date_fields
    }

    return {
        "step": "transformation",
        "source_platform": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_records": len(records),
        "output_records": len(records),
        "records_with_salary_min_vnd": sum(
            record.get("salary_min_vnd") is not None for record in records
        ),
        "records_with_salary_max_vnd": sum(
            record.get("salary_max_vnd") is not None for record in records
        ),
        "salary_sources": dict(
            Counter(str(record.get("salary_source") or "unknown") for record in records)
        ),
        "salary_currencies": dict(currencies),
        "sgd_converted_records": sum(
            record.get("salary_currency") == "SGD"
            and record.get("salary_fx_rate_to_vnd") is not None
            for record in records
        ),
        "sgd_fx_dates": dict(
            Counter(
                str(record["salary_fx_rate_date"])
                for record in records
                if record.get("salary_currency") == "SGD"
                and record.get("salary_fx_rate_date")
            )
        ),
        "unconverted_non_vnd_records": sum(
            record.get("salary_currency") not in (None, "VND")
            and (
                record.get("salary_min_original") is not None
                or record.get("salary_max_original") is not None
            )
            and record.get("salary_min_vnd") is None
            and record.get("salary_max_vnd") is None
            for record in records
        ),
        "negotiable_salary_records": sum(
            record.get("is_salary_negotiable_declared") == 1 for record in records
        ),
        "records_with_education_parsed": sum(
            record.get("standardized_education") is not None for record in records
        ),
        "records_with_seniority_parsed": sum(
            record.get("standardized_seniority") is not None for record in records
        ),
        "records_with_age_parsed": sum(
            (record.get("age_min") is not None or record.get("age_max") is not None)
            for record in records
        ),
        "records_with_company_scale_parsed": sum(
            record.get("company_size_min") is not None for record in records
        ),
        "records_with_saturday_work_declared": sum(
            record.get("is_saturday_work") is not None for record in records
        ),
        "records_with_stub_jd": sum(
            bool(record.get("is_stub_jd")) for record in records
        ),
        "salaries_extracted_from_benefits": sum(
            record.get("salary_source") == "benefits_regex" for record in records
        ),
        "language_distribution": dict(
            Counter(str(record.get("primary_language") or "unknown") for record in records)
        ),
        "dates": date_metrics,
        "output_file": str(output_path),
    }


def _salary_range_records(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Lọc các tin có ít nhất một đầu mút lương VND để xuất báo cáo xếp hạng."""
    salary_records = [
        dict(record)
        for record in records
        if record.get("salary_min_vnd") is not None
        or record.get("salary_max_vnd") is not None
    ]

    def sort_key(record: Mapping[str, Any]) -> tuple[bool, float, float, str]:
        salary_min = record.get("salary_min_vnd")
        salary_max = record.get("salary_max_vnd")
        if salary_min is not None:
            sort_value = float(salary_min)
            range_end = float(salary_max) if salary_max is not None else sort_value
        elif salary_max is not None:
            sort_value = float(salary_max)
            range_end = sort_value
        else:
            raise ValueError("Salary report contains a record without a numeric VND salary.")
        return (
            salary_min is None,
            sort_value,
            range_end,
            str(record.get("job_id_global") or ""),
        )

    salary_records.sort(key=sort_key)
    return salary_records


def transform_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Biến đổi danh sách JSON objects; không sửa danh sách hoặc các bản ghi đầu vào."""
    if any(not isinstance(record, Mapping) for record in records):
        invalid_index = next(
            index for index, record in enumerate(records) if not isinstance(record, Mapping)
        )
        raise ValueError(f"Bản ghi thứ {invalid_index} không phải mapping.")
    return _transform_source_records(records)


def run_transformation(
    sources: Sequence[str] = SOURCES,
    input_dir: Path | None = None,
    output_dir: Path | None = None,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Đọc các file Integration theo nguồn, xuất file đã transform và báo cáo kiểm kê."""
    input_dir = input_dir or PROJECT_ROOT / "data" / "integration"
    output_dir = output_dir or PROJECT_ROOT / "data" / "transformation"
    reports_dir = reports_dir or PROJECT_ROOT / "reports" / "transformation"

    invalid_sources = set(sources) - set(SOURCES)
    if invalid_sources:
        raise ValueError(f"Nguồn không hợp lệ: {', '.join(sorted(invalid_sources))}")

    start_time = time.perf_counter()
    all_transformed: list[dict[str, Any]] = []
    source_reports: dict[str, dict[str, Any]] = {}

    for source in sources:
        source_started_at = time.perf_counter()
        input_path = input_dir / source / f"{source}_integrated_flat.json"
        records = _load_records(input_path)
        transformed = transform_records(records)

        output_path = output_dir / source / f"{source}_transformed_flat.json"
        salary_report_path = output_dir / source / f"{source}_salary_sorted_vnd.json"
        report_path = reports_dir / f"{source}_transformation_report.json"
        _write_json(output_path, transformed)
        salary_records = _salary_range_records(transformed)
        _write_json(salary_report_path, salary_records)
        report = _build_report(source, transformed, output_path)
        report["input_file"] = str(input_path)
        report["salary_range_report"] = {
            "output_file": str(salary_report_path),
            "records_with_numeric_vnd_salary": len(salary_records),
            "sort_order": "salary_min_vnd ascending, then salary_max_vnd ascending",
            "retains_all_records_in_transformed_output": True,
        }
        report["duration_seconds"] = round(time.perf_counter() - source_started_at, 3)
        _write_json(report_path, report)
        source_reports[source] = report
        all_transformed.extend(transformed)
        logger.info("%s: transformed %s records", source, len(transformed))

    master_report: dict[str, Any] = {
        "step": "transformation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sgd_fx_policy": {
            "formula": "historical SGD/USD from Frankfurter x fixed project USD/VND",
            "fixed_usd_vnd_rate": USD_VND_EXCHANGE_RATE,
            "rate_date_policy": "posted date, fallback crawl date, previous available business day",
            "rate_api": FRANKFURTER_API_URL,
        },
        "sources": source_reports,
        "total_input_records": sum(report["input_records"] for report in source_reports.values()),
        "total_output_records": len(all_transformed),
        "duration_seconds": round(time.perf_counter() - start_time, 3),
    }

    if len(sources) > 1:
        raw_for_outlier_path = output_dir / "raw_for_outlier.json"
        master_output_path = output_dir / "transformed_flat_all_sources.json"
        master_salary_report_path = output_dir / "salary_sorted_all_sources_vnd.json"
        master_report_path = reports_dir / "master_transformation_report.json"
        _write_json(raw_for_outlier_path, all_transformed)
        _write_json(master_output_path, all_transformed)
        master_salary_records = _salary_range_records(all_transformed)
        _write_json(master_salary_report_path, master_salary_records)
        master_report["output_file"] = str(raw_for_outlier_path)
        master_report["raw_for_outlier_file"] = str(raw_for_outlier_path)
        master_report["legacy_output_file"] = str(master_output_path)
        master_report["salary_range_report"] = {
            "output_file": str(master_salary_report_path),
            "records_with_numeric_vnd_salary": len(master_salary_records),
            "sort_order": "salary_min_vnd ascending, then salary_max_vnd ascending",
            "retains_all_records_in_transformed_output": True,
        }
        _write_json(master_report_path, master_report)

    return master_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Transform integrated job records.")
    parser.add_argument(
        "--source",
        choices=(*SOURCES, "all"),
        default="all",
        help="Nguồn cần chạy; mặc định chạy đủ 8 nguồn.",
    )
    args = parser.parse_args()
    selected_sources = SOURCES if args.source == "all" else (args.source,)
    run_transformation(selected_sources)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
