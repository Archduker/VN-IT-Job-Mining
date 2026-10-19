#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate auditable preliminary EDA from real Glints/JobsGO MinIO snapshots.

Run from the project root:
    python scripts/run_glints_jobsgo_eda.py

Only raw detail snapshots in MinIO are analyzed. Synthetic fixtures are never read.
Salary comparability is conservative: currency and monthly pay period must be known.
USD conversion is disabled unless FX_VND_PER_USD is explicitly configured in .env.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import boto3
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from bs4 import BeautifulSoup
    from botocore.client import Config
    from dotenv import load_dotenv
except ImportError as exc:  # friendly error for students starting the project
    raise SystemExit(
        f"Thiếu thư viện {exc}. Hãy cài dependencies từ project root: "
        "python -m pip install -r requirements.txt"
    ) from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)
SOURCES = ("glints", "jobsgo")
SNAPSHOT_RE = re.compile(
    r"^raw/(?P<source>glints|jobsgo)/\d{4}-\d{2}-\d{2}/.+_v(?P<version>\d+)\.json$"
)
SKILL_PATTERNS = {
    "Python": r"(?<![A-Za-z0-9])Python(?![A-Za-z0-9])",
    "Java": r"(?<![A-Za-z0-9])Java(?![A-Za-z0-9])",
    "JavaScript": r"(?<![A-Za-z0-9])JavaScript(?![A-Za-z0-9])",
    "TypeScript": r"(?<![A-Za-z0-9])TypeScript(?![A-Za-z0-9])",
    "C#": r"(?<![A-Za-z0-9])C#(?![A-Za-z0-9])",
    "C++": r"(?<![A-Za-z0-9])C\+\+(?![A-Za-z0-9])",
    ".NET": r"(?<![A-Za-z0-9])\.NET(?![A-Za-z0-9])",
    "Go": r"(?<![A-Za-z0-9])Go(?:lang)?(?![A-Za-z0-9])",
    "PHP": r"(?<![A-Za-z0-9])PHP(?![A-Za-z0-9])",
    "SQL": r"(?<![A-Za-z0-9])SQL(?![A-Za-z0-9])",
    "MySQL": r"(?<![A-Za-z0-9])MySQL(?![A-Za-z0-9])",
    "PostgreSQL": r"(?<![A-Za-z0-9])PostgreSQL(?![A-Za-z0-9])",
    "React": r"(?<![A-Za-z0-9])React(?![A-Za-z0-9])",
    "Vue.js": r"(?<![A-Za-z0-9])Vue\.js(?![A-Za-z0-9])",
    "Angular": r"(?<![A-Za-z0-9])Angular(?![A-Za-z0-9])",
    "Node.js": r"(?<![A-Za-z0-9])Node\.js(?![A-Za-z0-9])",
    "Django": r"(?<![A-Za-z0-9])Django(?![A-Za-z0-9])",
    "Flask": r"(?<![A-Za-z0-9])Flask(?![A-Za-z0-9])",
    "FastAPI": r"(?<![A-Za-z0-9])FastAPI(?![A-Za-z0-9])",
    "Docker": r"(?<![A-Za-z0-9])Docker(?![A-Za-z0-9])",
    "Kubernetes": r"(?<![A-Za-z0-9])Kubernetes(?![A-Za-z0-9])",
    "AWS": r"(?<![A-Za-z0-9])AWS(?![A-Za-z0-9])",
    "Azure": r"(?<![A-Za-z0-9])Azure(?![A-Za-z0-9])",
    "GCP": r"(?<![A-Za-z0-9])GCP(?![A-Za-z0-9])",
    "Linux": r"(?<![A-Za-z0-9])Linux(?![A-Za-z0-9])",
    "Git": r"(?<![A-Za-z0-9])Git(?![A-Za-z0-9])",
    "CI/CD": r"(?<![A-Za-z0-9])CI/CD(?![A-Za-z0-9])",
    "TensorFlow": r"(?<![A-Za-z0-9])TensorFlow(?![A-Za-z0-9])",
    "PyTorch": r"(?<![A-Za-z0-9])PyTorch(?![A-Za-z0-9])",
    "Machine Learning": r"(?<![A-Za-z0-9])Machine\s+Learning(?![A-Za-z0-9])",
    "Data Engineering": r"(?<![A-Za-z0-9])Data\s+Engineering(?![A-Za-z0-9])",
    "Cybersecurity": r"(?<![A-Za-z0-9])Cybersecurity(?![A-Za-z0-9])",
    "Agile": r"(?<![A-Za-z0-9])Agile(?![A-Za-z0-9])",
    "Scrum": r"(?<![A-Za-z0-9])Scrum(?![A-Za-z0-9])",
}


def project_paths() -> tuple[Path, Path]:
    reports = PROJECT_ROOT / "reports" / "generated"
    figures = reports / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    return reports, figures


def connect_s3():
    # Local MinIO is the default for this task. Use R2 only when explicitly selected.
    provider = os.getenv("S3_PROVIDER", "minio").strip().casefold()
    if provider in {"cloudflare_r2", "r2"}:
        endpoint = os.getenv("S3_ENDPOINT_URL") or os.getenv("R2_ENDPOINT_URL")
        bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("R2_BUCKET_NAME") or os.getenv("MINIO_BUCKET", "vn-it-jobs")
        access = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("R2_ACCESS_KEY_ID")
        secret = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("R2_SECRET_ACCESS_KEY")
        if not endpoint or not access or not secret:
            raise ValueError("S3_PROVIDER=cloudflare_r2 nhưng thiếu endpoint/access key/secret key trong .env.")
    else:
        endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        bucket = os.getenv("MINIO_BUCKET", "vn-it-jobs")
        access = os.getenv("MINIO_ROOT_USER", "minioadmin")
        secret = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    region = "auto" if "r2.cloudflarestorage.com" in endpoint else os.getenv("AWS_REGION", "us-east-1")
    client = boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=access, aws_secret_access_key=secret,
        config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=30,
                      retries={"max_attempts": 3, "mode": "standard"}), region_name=region,
    )
    client.head_bucket(Bucket=bucket)
    return client, bucket, endpoint


def list_keys(s3, bucket: str, prefix: str) -> list[str]:
    paginator = s3.get_paginator("list_objects_v2")
    found: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        found.extend(str(item["Key"]) for item in page.get("Contents", []) or [])
    return found


def load_latest_snapshots(s3, bucket: str, source: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    latest: dict[str, tuple[int, str, dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    for key in list_keys(s3, bucket, f"raw/{source}/"):
        match = SNAPSHOT_RE.match(key)
        if not match:
            continue  # exclude listing payloads, fixture folders and non-detail objects
        try:
            payload = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("snapshot JSON root is not an object")
            meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
            raw = payload.get("raw") if isinstance(payload.get("raw"), dict) else {}
            job_id = str(meta.get("source_job_id") or key)
            version = int(meta.get("version") or match.group("version"))
            previous = latest.get(job_id)
            if previous is None or (version, key) > (previous[0], previous[1]):
                latest[job_id] = (version, key, payload)
        except Exception as exc:
            errors.append({"source": source, "object_key": key, "error": str(exc)})
    rows = []
    for job_id, (version, key, payload) in sorted(latest.items()):
        rows.append({"source": source, "job_id": job_id, "version": version,
                     "snapshot_key": key, "snapshot": payload})
    return rows, errors


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _strings(child)


def find_jsonld(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            kind = candidate.get("@type")
            if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                return candidate
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict):
                        kind = item.get("@type")
                        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                            return item
    return {}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").strip())
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _native_salary_number(text: str, million: bool = False) -> float | None:
    try:
        compact = text.replace(" ", "")
        return float(compact.replace(",", ".")) if million else float(re.sub(r"[,.]", "", compact))
    except (TypeError, ValueError):
        return None


def parse_salary(source: str, html: str, listing: dict[str, Any], fx_vnd_per_usd: float | None = None) -> dict[str, Any]:
    min_value = max_value = None
    currency = period = salary_text = None
    input_unit = "currency_native"
    monthly_markers = re.compile(r"(?:/\s*tháng|mỗi\s*tháng|per\s*month|/\s*month|monthly|\btháng\b)", re.I)
    negotiable = re.compile(r"(?:thỏa\s*thuận|thoả\s*thuận|cạnh\s*tranh|negotiable|competitive)", re.I)
    soup_text = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)

    if source == "glints":
        salaries = listing.get("salaries") or []
        if isinstance(salaries, list) and salaries and isinstance(salaries[0], dict):
            item = salaries[0]
            min_value = _number(item.get("minAmount"))
            max_value = _number(item.get("maxAmount"))
            currency = item.get("CurrencyCode") or item.get("currency")
            # `salaryMode` is recorded as provided; never assume it means monthly.
            period = item.get("salaryMode")
        posting = find_jsonld(html)
        base = posting.get("baseSalary") if isinstance(posting.get("baseSalary"), dict) else {}
        value = base.get("value") if isinstance(base.get("value"), dict) else {}
        if min_value is None:
            min_value = _number(value.get("minValue"))
        if max_value is None:
            max_value = _number(value.get("maxValue"))
        currency = base.get("currency") or currency
        period = value.get("unitText") or period
        if min_value is not None or max_value is not None:
            salary_text = f"{min_value if min_value is not None else ''} - {max_value if max_value is not None else ''} {currency or ''} / {period or 'unknown period'}".strip(" -")
    else:
        card_text = str(listing.get("card_text") or "")
        texts = [card_text, soup_text]
        full_text = " ".join(part for part in texts if part)
        m = re.search(r"(?:mức\s*lương|salary)\s*:?\s*(thỏa\s*thuận|thoả\s*thuận|cạnh\s*tranh|negotiable|competitive)", full_text, re.I)
        if m:
            salary_text = m.group(1)
        million_range = re.compile(r"(?P<min>\d+(?:[.,]\d+)?)\s*(?:-|–|đến|to)\s*(?P<max>\d+(?:[.,]\d+)?)\s*(?P<unit>triệu|tr\b)(?:\s*(?:VNĐ|VND|đ))?", re.I)
        million_lower = re.compile(r"(?:từ|from)\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>triệu|tr\b)", re.I)
        million_upper = re.compile(r"(?:đến|tối đa|up\s*to)\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>triệu|tr\b)", re.I)
        currency_first_range = re.compile(r"(?P<currency>USD|\$)\s*(?P<min>\d[\d.,]*)\s*(?:-|–|to)\s*(?P<max>\d[\d.,]*)", re.I)
        currency_first_single = re.compile(r"(?P<currency>USD|\$)\s*(?P<amount>\d[\d.,]*)", re.I)
        native_range = re.compile(r"(?P<min>\d[\d.,]*)\s*(?:-|–|đến|to)\s*(?P<max>\d[\d.,]*)\s*(?P<currency>VNĐ|VND|USD|đ|\$)", re.I)
        native_single = re.compile(r"(?P<amount>\d[\d.,]*)\s*(?P<currency>VNĐ|VND|USD|đ|\$)", re.I)
        if not salary_text:
            for text in texts:
                for pattern in (million_range, million_lower, million_upper, currency_first_range, currency_first_single, native_range, native_single):
                    match = pattern.search(text)
                    if not match:
                        continue
                    salary_text = match.group(0)
                    if "unit" in match.groupdict() and match.groupdict().get("unit"):
                        currency, input_unit = "VND", "million"
                        context = text[max(0, match.start() - 35): min(len(text), match.end() + 55)]
                        period = "month" if monthly_markers.search(context) else None
                        if "min" in match.groupdict() and match.groupdict().get("min") is not None:
                            min_value = _native_salary_number(match.group("min"), million=True)
                        if "max" in match.groupdict() and match.groupdict().get("max") is not None:
                            max_value = _native_salary_number(match.group("max"), million=True)
                        if "amount" in match.groupdict() and match.groupdict().get("amount") is not None:
                            if pattern is million_upper:
                                max_value = _native_salary_number(match.group("amount"), million=True)
                            else:
                                min_value = _native_salary_number(match.group("amount"), million=True)
                    else:
                        if "min" in match.groupdict() and match.groupdict().get("min") is not None:
                            min_value = _native_salary_number(match.group("min"))
                        if "max" in match.groupdict() and match.groupdict().get("max") is not None:
                            max_value = _native_salary_number(match.group("max"))
                        if "amount" in match.groupdict() and match.groupdict().get("amount") is not None:
                            min_value = _native_salary_number(match.group("amount"))
                        currency = "USD" if match.group("currency").upper() in {"USD", "$"} else "VND"
                        context = text[max(0, match.start() - 35): min(len(text), match.end() + 55)]
                        period = "month" if monthly_markers.search(context) else None
                    break
                if salary_text:
                    break
    if source == "jobsgo" and min_value is None and max_value is None:
        posting = find_jsonld(html)
        base = posting.get("baseSalary") if isinstance(posting.get("baseSalary"), dict) else {}
        value = base.get("value") if isinstance(base.get("value"), dict) else {}
        min_value, max_value = _number(value.get("minValue")), _number(value.get("maxValue"))
        currency = base.get("currency") or currency
        period = value.get("unitText") or period
        if min_value is not None or max_value is not None:
            salary_text = f"{min_value if min_value is not None else ''} - {max_value if max_value is not None else ''} {currency or ''} / {period or 'unknown period'}".strip(" -")

    period_norm = str(period or "").casefold().replace("_", " ").strip()
    monthly = any(token in period_norm for token in ("month", "monthly", "tháng"))
    currency_norm = str(currency or "").upper()
    min_monthly = max_monthly = None
    if monthly and currency_norm == "VND":
        scale = 1.0 if input_unit == "million" else 1.0 / 1_000_000
        min_monthly = min_value * scale if min_value is not None else None
        max_monthly = max_value * scale if max_value is not None else None
    elif monthly and currency_norm in {"USD", "$"} and fx_vnd_per_usd:
        scale = fx_vnd_per_usd / 1_000_000
        min_monthly = min_value * scale if min_value is not None else None
        max_monthly = max_value * scale if max_value is not None else None
    return {
        "salary_text": salary_text, "salary_min_raw": min_value, "salary_max_raw": max_value,
        "salary_currency": currency, "salary_period": period, "salary_input_unit": input_unit,
        "salary_min_million_vnd_month": min_monthly, "salary_max_million_vnd_month": max_monthly,
        "salary_public_numeric": min_value is not None or max_value is not None,
        "salary_negotiable": bool(salary_text and negotiable.search(str(salary_text))),
        "salary_missing": not salary_text and min_value is None and max_value is None,
        "salary_comparable_monthly": min_monthly is not None or max_monthly is not None,
    }


def parse_experience(source: str, html: str, listing: dict[str, Any], posting: dict[str, Any]) -> float | None:
    if source == "glints":
        for val in (listing.get("minYearsOfExperience"), listing.get("min_years_of_experience")):
            number = _number(val)
            if number is not None:
                return number
        months = (posting.get("experienceRequirements") or {}).get("monthsOfExperience") if isinstance(posting.get("experienceRequirements"), dict) else None
        number = _number(months)
        return number / 12 if number is not None else None
    visible = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    if re.search(r"kinh nghiệm\s*:?\s*(?:không yêu cầu|không cần|no experience required)", visible, re.I):
        return 0.0
    match = re.search(r"kinh nghiệm\s*:?\s*(\d+(?:[.,]\d+)?)\s*(?:-|đến)?\s*(\d+(?:[.,]\d+)?)?\s*năm", visible, re.I)
    return float(match.group(1).replace(",", ".")) if match else None


def _find_labeled_text(soup: BeautifulSoup, labels: str) -> str | None:
    pattern = re.compile(labels, re.I)
    for element in soup.find_all(["p", "li", "dd", "div", "span", "strong", "b"]):
        text = element.get_text(" ", strip=True)
        match = re.match(r"(?:" + labels + r")\s*:?\s*(.+)$", text, re.I)
        if match and len(match.group(1)) <= 300:
            return match.group(1).strip() or None
    return None


def extract_record(row: dict[str, Any], fx_vnd_per_usd: float | None = None) -> dict[str, Any]:
    snapshot = row["snapshot"]
    meta = snapshot.get("_meta") if isinstance(snapshot.get("_meta"), dict) else {}
    raw = snapshot.get("raw") if isinstance(snapshot.get("raw"), dict) else {}
    html = raw.get("html") if isinstance(raw.get("html"), str) else ""
    listing = raw.get("listing_payload") if isinstance(raw.get("listing_payload"), dict) else {}
    soup = BeautifulSoup(html, "html.parser")
    posting = find_jsonld(html)
    title = listing.get("title") or posting.get("title")
    if not title and soup.find("h1"):
        title = soup.find("h1").get_text(" ", strip=True)
    company_obj = listing.get("company") if isinstance(listing.get("company"), dict) else {}
    company = listing.get("company") if isinstance(listing.get("company"), str) else None
    company = company or company_obj.get("brandName") or company_obj.get("name")
    hiring = posting.get("hiringOrganization") if isinstance(posting.get("hiringOrganization"), dict) else {}
    company = company or hiring.get("name")
    visible = soup.get_text(" ", strip=True)
    salary = parse_salary(row["source"], html, listing, fx_vnd_per_usd)

    if row["source"] == "glints":
        location_obj = listing.get("location") if isinstance(listing.get("location"), dict) else {}
        location = location_obj.get("formattedName") or location_obj.get("name")
        skills_raw = listing.get("skills")
        if isinstance(skills_raw, list):
            skills = [str(item.get("skill", {}).get("name")) for item in skills_raw
                      if isinstance(item, dict) and isinstance(item.get("skill"), dict) and item["skill"].get("name")]
        else:
            skills = []
        description = posting.get("description") or visible
        seniority = listing.get("seniorityLevel") or listing.get("level")
        employment_type = listing.get("type")
    else:
        location = listing.get("location") or _find_labeled_text(soup, r"địa điểm|nơi làm việc|location|work location")
        skills_raw = None
        skills = []
        description = visible
        seniority = _find_labeled_text(soup, r"cấp bậc|seniority|level")
        employment_type = _find_labeled_text(soup, r"loại hình|hình thức làm việc|employment type")
        if not company:
            for anchor in soup.select("a[href]"):
                href = str(anchor.get("href") or "").casefold()
                text = anchor.get_text(" ", strip=True)
                if text and any(token in href for token in ("cong-ty", "/company", "nha-tuyen-dung")):
                    company = text
                    break

    exp = parse_experience(row["source"], html, listing, posting)
    search_text = " ".join([str(title or ""), str(description or ""), visible])
    found_skills = [name for name, pattern in SKILL_PATTERNS.items() if re.search(pattern, search_text, flags=re.I)]
    for skill in skills:
        if skill not in found_skills:
            found_skills.append(skill)
    desc_text = BeautifulSoup(str(description or ""), "html.parser").get_text(" ", strip=True)
    return {
        "source": row["source"], "job_id": str(meta.get("source_job_id") or row.get("job_id") or ""),
        "version": row["version"], "snapshot_key": row["snapshot_key"], "url": meta.get("url"),
        "title": title, "company": company, "location": location, "seniority_level": seniority,
        "employment_type": employment_type, "salary_text": salary["salary_text"],
        "salary_min_raw": salary["salary_min_raw"], "salary_max_raw": salary["salary_max_raw"],
        "salary_currency": salary["salary_currency"], "salary_period": salary["salary_period"],
        "salary_input_unit": salary["salary_input_unit"],
        "salary_min_million_vnd_month": salary["salary_min_million_vnd_month"],
        "salary_max_million_vnd_month": salary["salary_max_million_vnd_month"],
        "salary_public_numeric": bool(salary["salary_public_numeric"]),
        "salary_negotiable": bool(salary["salary_negotiable"]), "salary_missing": bool(salary["salary_missing"]),
        "salary_comparable_monthly": bool(salary["salary_comparable_monthly"]),
        "min_experience_years": exp, "description_chars": len(desc_text),
        "description_words": len(desc_text.split()), "html_chars": len(html),
        "skill_tags_raw": skills_raw if row["source"] == "glints" else None,
        "skill_count": len(set(skills)), "skills_keyword_scan": found_skills,
    }


def field_inventory(snapshot_rows: list[dict[str, Any]]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for source in SOURCES:
        subset = [r for r in snapshot_rows if r["source"] == source]
        denominator = len(subset)
        if denominator == 0:
            records.append({"source": source, "field_or_selector": "(no snapshots)", "records_checked": 0,
                            "records_present": 0, "presence_rate_pct": None, "records_non_null": 0,
                            "non_null_rate_pct": None, "null_or_empty_when_present_pct": None,
                            "absent_rate_pct": None, "example_value": ""})
            continue
        presence = Counter()
        non_null = Counter()
        examples: dict[str, str] = {}
        for row in subset:
            raw = row["snapshot"].get("raw") if isinstance(row["snapshot"].get("raw"), dict) else {}
            listing = raw.get("listing_payload") if isinstance(raw.get("listing_payload"), dict) else {}
            per_row_present: set[str] = set()
            per_row_non_null: set[str] = set()
            for path, value in flatten_paths(listing):
                name = "listing_field:" + path
                per_row_present.add(name)
                if is_non_null_value(value):
                    per_row_non_null.add(name)
                    examples.setdefault(name, str(value)[:160])
            for name in per_row_present:
                presence[name] += 1
            for name in per_row_non_null:
                non_null[name] += 1
            for selector in html_selector_presence(raw.get("html") or ""):
                presence[selector] += 1
        for field, present in sorted(presence.items()):
            is_json = field.startswith("listing_field:")
            good = non_null[field] if is_json else None
            records.append({
                "source": source, "field_or_selector": field, "records_checked": denominator,
                "records_present": present, "presence_rate_pct": round(present / denominator * 100, 2),
                "records_non_null": good,
                "non_null_rate_pct": round(good / denominator * 100, 2) if is_json else None,
                "null_or_empty_when_present_pct": round((present - good) / present * 100, 2) if is_json and present else None,
                "absent_rate_pct": round((denominator - present) / denominator * 100, 2),
                "example_value": examples.get(field, "") if is_json else "",
            })
    return pd.DataFrame(records)


def flatten_paths(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    output: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        if not value and prefix:
            output.append((prefix, value))
        for key, child in value.items():
            output.extend(flatten_paths(child, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        if not value:
            output.append((f"{prefix}[]", value))
        else:
            for child in value:
                output.extend(flatten_paths(child, f"{prefix}[]"))
    else:
        output.append((prefix, value))
    return output


def is_non_null_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def html_selector_presence(html: str) -> set[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    found = set()
    for tag in soup.find_all(True):
        classes = sorted(c for c in (tag.get("class") or []) if c)
        safe_classes = [re.sub(r"[^A-Za-z0-9_-]", "-", c) for c in classes]
        found.add("html_selector:" + tag.name + "".join("." + c for c in safe_classes))
        for attr in tag.attrs:
            if attr not in {"class", "style"}:
                found.add(f"html_attribute:{tag.name}[{attr}]")
    return found


def missing_rate_table(df: pd.DataFrame) -> pd.DataFrame:
    fields = ("title", "company", "salary_text", "location", "min_experience_years", "description_chars", "skill_tags_raw")
    output = []
    for source in SOURCES:
        part = df[df["source"].eq(source)] if not df.empty else pd.DataFrame()
        n = len(part)
        for field in fields:
            if n == 0:
                output.append({"source": source, "field": field, "records": 0, "missing_count": 0, "missing_rate_pct": None})
                continue
            values = part[field] if field in part.columns else pd.Series([None] * n, index=part.index)
            def missing(value: Any) -> bool:
                if value is None:
                    return True
                if isinstance(value, float) and math.isnan(value):
                    return True
                if isinstance(value, str):
                    return not value.strip()
                if isinstance(value, (list, dict, tuple, set)):
                    return len(value) == 0
                return False
            flags = values.map(missing)
            if field == "description_chars":
                flags = pd.to_numeric(values, errors="coerce").fillna(0).le(0)
            output.append({"source": source, "field": field, "records": n,
                           "missing_count": int(flags.sum()), "missing_rate_pct": round(float(flags.mean() * 100), 2)})
    return pd.DataFrame(output)


def source_summary(df: pd.DataFrame, snapshot_rows: list[dict[str, Any]], s3, bucket: str) -> pd.DataFrame:
    rows = []
    for source in SOURCES:
        part = df[df["source"].eq(source)] if not df.empty else pd.DataFrame()
        catalog = {}
        try:
            obj = s3.get_object(Bucket=bucket, Key=f"url_ledger/{source}/catalog_master.json")
            candidate = json.loads(obj["Body"].read().decode("utf-8"))
            if isinstance(candidate, dict):
                catalog = candidate
        except Exception:
            catalog = {}
        states = Counter(str(item.get("status", "UNKNOWN")) for item in catalog.values() if isinstance(item, dict))
        failure_keys: list[str] = []
        last_failure = ""
        try:
            failure_keys = sorted(k for k in list_keys(s3, bucket, f"raw/{source}/_listing_failures/") if k.endswith(".json"))
            if failure_keys:
                latest_failure = json.loads(s3.get_object(Bucket=bucket, Key=failure_keys[-1])["Body"].read().decode("utf-8"))
                if isinstance(latest_failure, dict):
                    last_failure = str(latest_failure.get("error") or f"HTTP {latest_failure.get('http_status', 'unknown')}")[:180]
        except Exception:
            # Failure diagnostics must not prevent otherwise useful EDA output.
            failure_keys = []
            last_failure = ""
        total = len(part)
        rows.append({
            "source": source,
            "latest_detail_snapshots": total,
            "catalog_urls": len(catalog),
            "catalog_pending": states.get("PENDING", 0),
            "catalog_done": states.get("DONE", 0),
            "catalog_recheck_due": states.get("RECHECK_DUE", 0),
            "catalog_failed": states.get("FAILED", 0),
            "catalog_closed": states.get("CLOSED", 0),
            "listing_failure_count": len(failure_keys),
            "last_listing_failure": last_failure,
            "numeric_salary_count": int(part["salary_public_numeric"].sum()) if total else 0,
            "numeric_salary_pct": round(float(part["salary_public_numeric"].mean() * 100), 2) if total else None,
            "negotiable_salary_count": int(part["salary_negotiable"].sum()) if total else 0,
            "missing_salary_count": int(part["salary_missing"].sum()) if total else 0,
            "comparable_monthly_salary_count": int(part["salary_comparable_monthly"].sum()) if total else 0,
        })
    return pd.DataFrame(rows)


def iqr_summary(df: pd.DataFrame) -> pd.DataFrame:
    output = []
    for source in SOURCES:
        part = df[df["source"].eq(source)] if not df.empty else pd.DataFrame()
        for column in ("salary_min_million_vnd_month", "salary_max_million_vnd_month"):
            values = pd.to_numeric(part[column], errors="coerce").dropna() if column in part else pd.Series(dtype=float)
            if values.empty:
                output.append({"source": source, "field": column, "n": 0, "q1": None, "median": None, "q3": None,
                               "iqr": None, "lower_bound": None, "upper_bound": None, "outlier_count": 0, "outlier_rate_pct": None})
                continue
            q1, median, q3 = values.quantile(.25), values.median(), values.quantile(.75)
            spread = q3 - q1
            lower, upper = max(0.0, q1 - 1.5 * spread), q3 + 1.5 * spread
            outliers = (values < lower) | (values > upper)
            output.append({"source": source, "field": column, "n": len(values), "q1": round(float(q1), 4),
                           "median": round(float(median), 4), "q3": round(float(q3), 4), "iqr": round(float(spread), 4),
                           "lower_bound": round(float(lower), 4), "upper_bound": round(float(upper), 4),
                           "outlier_count": int(outliers.sum()), "outlier_rate_pct": round(float(outliers.mean() * 100), 2)})
    return pd.DataFrame(output)


def skill_frequency(df: pd.DataFrame) -> pd.DataFrame:
    counts = Counter()
    for skills in df["skills_keyword_scan"].dropna() if "skills_keyword_scan" in df else []:
        counts.update(set(skills or []))
    total = sum(counts.values())
    cumulative = 0
    rows = []
    for skill, count in counts.most_common(100):
        cumulative += count
        rows.append({"skill": skill, "job_count": count, "share_pct_of_detected_skill_mentions": round(count / total * 100, 2) if total else None,
                     "cumulative_share_pct": round(cumulative / total * 100, 2) if total else None})
    return pd.DataFrame(rows)


def _save_empty_plot(path: Path, title: str, message: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axis("off")
    ax.set_title(title)
    ax.text(.5, .5, message, ha="center", va="center", wrap=True)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _save_correlations(df: pd.DataFrame, method: str, path: Path) -> pd.DataFrame:
    numeric_columns = ["salary_min_million_vnd_month", "salary_max_million_vnd_month",
                       "min_experience_years", "description_words", "skill_count", "html_chars"]
    if df.empty:
        _save_empty_plot(path, f"{method.title()} correlation", "No real detail snapshots available.")
        return pd.DataFrame()
    numeric = df[[c for c in numeric_columns if c in df.columns]].apply(pd.to_numeric, errors="coerce")
    valid = [col for col in numeric if numeric[col].notna().sum() >= 2 and numeric[col].nunique(dropna=True) > 1]
    if len(valid) < 2:
        _save_empty_plot(path, f"{method.title()} correlation", "Insufficient paired numeric data for a correlation matrix.")
        return pd.DataFrame()
    corr = numeric[valid].corr(method=method, min_periods=2)
    fig, ax = plt.subplots(figsize=(max(6, len(valid) * 1.1), max(5, len(valid) * .9)))
    image = ax.imshow(corr.to_numpy(), vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(valid)), labels=valid, rotation=45, ha="right")
    ax.set_yticks(range(len(valid)), labels=valid)
    for r in range(len(valid)):
        for c in range(len(valid)):
            value = corr.iloc[r, c]
            ax.text(c, r, f"{value:.2f}" if pd.notna(value) else "N/A", ha="center", va="center", fontsize=8)
    ax.set_title(f"{method.title()} correlation matrix — comparable numeric fields")
    fig.colorbar(image, ax=ax, fraction=.046, pad=.04)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return corr


def generate_charts(df: pd.DataFrame, skills: pd.DataFrame, figures: Path) -> dict[str, pd.DataFrame]:
    # 1) Distribution: comparable salary per month only
    salary_values = pd.concat([pd.to_numeric(df.get("salary_min_million_vnd_month", pd.Series(dtype=float)), errors="coerce"),
                               pd.to_numeric(df.get("salary_max_million_vnd_month", pd.Series(dtype=float)), errors="coerce")]).dropna()
    if salary_values.empty:
        _save_empty_plot(figures / "01_salary_distribution.png", "Salary distribution", "No salary values are comparable in million VND/month.\nRaw currency/period is preserved; no zeros were imputed.")
    else:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.hist(salary_values, bins=min(20, max(5, int(math.sqrt(len(salary_values))))))
        ax.set_title("Distribution of comparable monthly salary bounds")
        ax.set_xlabel("Million VND / month")
        ax.set_ylabel("Observed salary bounds")
        fig.tight_layout()
        fig.savefig(figures / "01_salary_distribution.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    # 2) Relationship: experience vs maximum comparable monthly salary
    relation = df.copy() if not df.empty else pd.DataFrame()
    if not relation.empty:
        relation["min_experience_years"] = pd.to_numeric(relation["min_experience_years"], errors="coerce")
        relation["salary_max_million_vnd_month"] = pd.to_numeric(relation["salary_max_million_vnd_month"], errors="coerce")
        relation = relation.dropna(subset=["min_experience_years", "salary_max_million_vnd_month"])
    if len(relation) < 2:
        _save_empty_plot(figures / "02_experience_salary_relationship.png", "Experience vs salary", "Fewer than two records have both experience and comparable monthly salary.")
    else:
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        for source, part in relation.groupby("source"):
            ax.scatter(part["min_experience_years"], part["salary_max_million_vnd_month"], alpha=.7, label=source)
        if relation["min_experience_years"].nunique() > 1:
            x = relation["min_experience_years"].to_numpy(dtype=float)
            y = relation["salary_max_million_vnd_month"].to_numpy(dtype=float)
            coeffs = np.polyfit(x, y, 1)
            grid = np.linspace(x.min(), x.max(), 80)
            ax.plot(grid, coeffs[0] * grid + coeffs[1], label="Descriptive linear trend")
        ax.set_title("Minimum required experience vs maximum comparable monthly salary")
        ax.set_xlabel("Minimum experience (years)")
        ax.set_ylabel("Million VND / month")
        ax.legend()
        fig.tight_layout()
        fig.savefig(figures / "02_experience_salary_relationship.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    # 3) Dispersion: salary by source
    grouped = []
    labels = []
    for source in SOURCES:
        values = pd.to_numeric(df.loc[df["source"].eq(source), "salary_max_million_vnd_month"], errors="coerce").dropna() if not df.empty else pd.Series(dtype=float)
        if not values.empty:
            grouped.append(values.to_numpy())
            labels.append(source)
    if not grouped:
        _save_empty_plot(figures / "03_salary_dispersion_by_source.png", "Salary dispersion by source", "No comparable monthly salary values are available.")
    else:
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        ax.boxplot(grouped, tick_labels=labels)
        ax.set_title("Dispersion of maximum comparable monthly salary by source")
        ax.set_ylabel("Million VND / month")
        fig.tight_layout()
        fig.savefig(figures / "03_salary_dispersion_by_source.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    # 4) Correlation matrices: Pearson and Spearman
    pearson = _save_correlations(df, "pearson", figures / "04_pearson_correlation.png")
    spearman = _save_correlations(df, "spearman", figures / "05_spearman_correlation.png")

    # 5) Categorical frequency + Pareto curve
    if skills.empty:
        _save_empty_plot(figures / "06_skills_pareto.png", "Technical-skill keyword frequency and Pareto", "No skills were found by the conservative keyword scan.")
    else:
        top = skills.head(20).copy()
        fig, ax1 = plt.subplots(figsize=(10, 5.5))
        ax1.bar(top["skill"][::-1], top["job_count"][::-1])
        ax1.set_ylabel("Jobs mentioning keyword")
        ax1.set_xlabel("Detected technology keyword")
        ax1.tick_params(axis="x", rotation=50)
        ax2 = ax1.twinx()
        ax2.plot(top["skill"], top["cumulative_share_pct"], marker="o")
        ax2.set_ylabel("Cumulative share of detected mentions (%)")
        ax2.axhline(80, linestyle="--")
        ax2.set_ylim(0, 105)
        ax1.set_title("Top skills and Pareto cumulative share (heuristic scan)")
        fig.tight_layout()
        fig.savefig(figures / "06_skills_pareto.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    # Quality comparison charts
    if df.empty:
        _save_empty_plot(figures / "07_salary_disclosure_by_source.png", "Salary disclosure by source", "No real detail snapshots available.")
        _save_empty_plot(figures / "08_missing_rate_by_source.png", "Missing rate by source", "No real detail snapshots available.")
    else:
        source_counts = df.groupby("source")["salary_public_numeric"].mean().reindex(SOURCES) * 100
        fig, ax = plt.subplots(figsize=(7, 4))
        source_counts.plot(kind="bar", ax=ax)
        ax.set_title("Numeric salary disclosure among latest detail snapshots")
        ax.set_ylabel("Jobs with numeric salary (%)")
        ax.set_ylim(0, 100)
        fig.tight_layout()
        fig.savefig(figures / "07_salary_disclosure_by_source.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

        missing = missing_rate_table(df)
        fig, ax = plt.subplots(figsize=(10, 5))
        pivot = missing.pivot(index="field", columns="source", values="missing_rate_pct").reindex(
            ["title", "company", "salary_text", "location", "min_experience_years", "description_chars", "skill_tags_raw"]
        )
        pivot.plot(kind="bar", ax=ax)
        ax.set_title("Missing rate of key fields by source")
        ax.set_ylabel("Missing records (%)")
        ax.set_ylim(0, 100)
        ax.tick_params(axis="x", rotation=35)
        fig.tight_layout()
        fig.savefig(figures / "08_missing_rate_by_source.png", dpi=160, bbox_inches="tight")
        plt.close(fig)
    return {"pearson": pearson, "spearman": spearman}


def _pct(num: Any, den: int) -> str:
    return "N/A (no snapshots)" if den == 0 else f"{float(num) / den * 100:.2f}%"


def render_report(summary: pd.DataFrame, missing: pd.DataFrame, iqr: pd.DataFrame,
                  skills: pd.DataFrame, inventory: pd.DataFrame, errors: list[dict[str, str]],
                  endpoint: str, bucket: str, run_time: str, figures_dir: Path) -> str:
    lines = [
        "# Kết quả EDA thực nghiệm — Glints & JobsGO", "",
        f"- **Thời điểm chạy (UTC):** `{run_time}`",
        f"- **Endpoint:** `{endpoint}` | **Bucket:** `{bucket}`",
        "- **Đơn vị phân tích:** snapshot version mới nhất theo `source_job_id`; snapshot listing, test fixture và HTML sample không tham gia thống kê.",
        "- **Nguyên tắc lương:** không gán 0 cho lương thiếu/thỏa thuận; chỉ so sánh theo tháng khi period + currency nhận diện được; USD chỉ quy đổi nếu `FX_VND_PER_USD` được đặt rõ trong `.env`.",
        "", "## 1. Tổng quan theo nguồn", "",
        "| Nguồn | URL catalog | Latest snapshots | Lương số | Lương thương lượng | Thiếu lương | Lương tháng so sánh được | FAILED ledger | Listing errors | Lỗi listing gần nhất |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in summary.iterrows():
        last_failure = str(r.get("last_listing_failure") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r['source']} | {int(r['catalog_urls'])} | {int(r['latest_detail_snapshots'])} | {int(r['numeric_salary_count'])} ({_pct(r['numeric_salary_count'], int(r['latest_detail_snapshots']))}) | {int(r['negotiable_salary_count'])} | {int(r['missing_salary_count'])} | {int(r['comparable_monthly_salary_count'])} | {int(r['catalog_failed'])} | {int(r.get('listing_failure_count', 0))} | {last_failure or 'N/A'} |")
    lines += ["", "## 2. Missing rate các trường chính", "", "| Nguồn | Trường | Record | Thiếu | Missing rate |", "|---|---|---:|---:|---:|"]
    for _, r in missing.iterrows():
        rate = "N/A" if pd.isna(r["missing_rate_pct"]) else f"{r['missing_rate_pct']:.2f}%"
        lines.append(f"| {r['source']} | `{r['field']}` | {int(r['records'])} | {int(r['missing_count'])} | {rate} |")
    lines += ["", "## 3. Lương ngoại lai — IQR", "", "Đơn vị: triệu VND/tháng; bảng chỉ có giá trị khi tiền tệ và kỳ trả lương đủ rõ.", "",
              "| Nguồn | Trường | n | Q1 | Median | Q3 | IQR | Cận dưới | Cận trên | Outlier | Tỷ lệ |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in iqr.iterrows():
        def fmt(x): return "N/A" if pd.isna(x) else f"{float(x):.3f}"
        rate = "N/A" if pd.isna(r["outlier_rate_pct"]) else f"{r['outlier_rate_pct']:.2f}%"
        lines.append(f"| {r['source']} | `{r['field']}` | {int(r['n'])} | {fmt(r['q1'])} | {fmt(r['median'])} | {fmt(r['q3'])} | {fmt(r['iqr'])} | {fmt(r['lower_bound'])} | {fmt(r['upper_bound'])} | {int(r['outlier_count'])} | {rate} |")
    lines += ["", "## 4. Từ khóa kỹ năng (heuristic, không phải taxonomy chuẩn)", "", "| Kỹ năng | Số tin có từ khóa | Tỷ lệ lũy tích trên lượt nhắc |", "|---|---:|---:|"]
    if skills.empty:
        lines.append("| Chưa đủ dữ liệu để nhận diện | 0 | N/A |")
    else:
        for _, r in skills.head(20).iterrows():
            lines.append(f"| {r['skill']} | {int(r['job_count'])} | {r['cumulative_share_pct']:.2f}% |")
    lines += ["", "## 5. Biểu đồ được tạo", ""]
    for path in sorted(figures_dir.glob("*.png")):
        lines.append(f"- `{path.relative_to(PROJECT_ROOT).as_posix()}`")
    lines += ["", "## 6. Raw field/HTML selector inventory", "",
              f"- Tổng mục trường/selector quan sát được: **{len(inventory)}** (field JSON và selector HTML được báo cáo riêng).",
              "- `presence_rate_pct` đo số snapshot có field/selector; `non_null_rate_pct` chỉ áp dụng trường JSON. `absent_rate_pct` phân biệt với field có nhưng null/empty.",
              "", "## 7. Lỗi đọc snapshot", "", f"Số đối tượng không đọc/parse được: **{len(errors)}**."]
    if errors:
        lines += ["", "| Nguồn | Object key | Lỗi |", "|---|---|---|"]
        for error in errors[:30]:
            message = error["error"].replace("|", "\\|").replace("\n", " ")[:240]
            lines.append(f"| {error['source']} | `{error['object_key']}` | {message} |")
    lines += ["", "## 8. Diễn giải và giới hạn", "",
              "- Đây là EDA trên dữ liệu thực sự hiện diện trong MinIO ở thời điểm chạy, không phải ước lượng độ phủ của toàn website.",
              "- Không so sánh mức lương nếu currency/period chưa xác định; tỷ lệ lương dạng số có thể cao hơn tỷ lệ lương tháng so sánh được.",
              "- IQR đánh dấu điểm nghi vấn chứ không khẳng định dữ liệu sai; cần đối chiếu HTML gốc trước mọi xử lý outlier.",
              "- Skill frequency dùng keyword-boundary scan từ title/description/HTML; rà soát thủ công trước khi dùng cho phân tích thị trường chính thức.",
              "- Nếu một nguồn có 0 snapshot, phần trăm của nguồn đó là N/A; cần xử lý blocker crawl (ví dụ HTTP 403/selector thay đổi) trước khi so sánh hai nguồn.", ""]
    return "\n".join(lines)


def run_eda() -> dict[str, Any]:
    s3, bucket, endpoint = connect_s3()
    reports_dir, figures_dir = project_paths()
    fx_raw = os.getenv("FX_VND_PER_USD", "").strip()
    fx_rate = _number(fx_raw) if fx_raw else None
    if fx_raw and (fx_rate is None or fx_rate <= 0):
        raise ValueError("FX_VND_PER_USD phải là tỷ giá VND/USD dương hoặc để trống để tắt quy đổi.")

    snapshot_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for source in SOURCES:
        rows, read_errors = load_latest_snapshots(s3, bucket, source)
        snapshot_rows.extend(rows)
        errors.extend(read_errors)
    records = [extract_record(row, fx_rate) for row in snapshot_rows]
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=[
            "source", "job_id", "version", "snapshot_key", "url", "title", "company", "location",
            "seniority_level", "employment_type", "salary_text", "salary_min_raw", "salary_max_raw", "salary_currency",
            "salary_period", "salary_input_unit", "salary_min_million_vnd_month", "salary_max_million_vnd_month",
            "salary_public_numeric", "salary_negotiable", "salary_missing", "salary_comparable_monthly",
            "min_experience_years", "description_chars", "description_words", "html_chars", "skill_tags_raw",
            "skill_count", "skills_keyword_scan",
        ])
    summary = source_summary(df, snapshot_rows, s3, bucket)
    missing = missing_rate_table(df)
    iqr = iqr_summary(df)
    skills = skill_frequency(df)
    inventory = field_inventory(snapshot_rows)
    corr = generate_charts(df, skills, figures_dir)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    run_day = datetime.now().strftime("%Y-%m-%d")

    summary.to_csv(reports_dir / f"glints_jobsgo_source_summary_{run_day}.csv", index=False)
    missing.to_csv(reports_dir / f"glints_jobsgo_missing_rate_{run_day}.csv", index=False)
    iqr.to_csv(reports_dir / f"glints_jobsgo_iqr_{run_day}.csv", index=False)
    skills.to_csv(reports_dir / f"glints_jobsgo_skill_frequency_{run_day}.csv", index=False)
    inventory.to_csv(reports_dir / f"glints_jobsgo_raw_field_inventory_{run_day}.csv", index=False)
    pd.DataFrame(errors, columns=["source", "object_key", "error"]).to_csv(reports_dir / f"glints_jobsgo_read_errors_{run_day}.csv", index=False)
    export_df = df.drop(columns=["skill_tags_raw", "skills_keyword_scan"], errors="ignore")
    export_df.to_csv(reports_dir / f"glints_jobsgo_eda_rows_{run_day}.csv", index=False)
    for name, corr_df in corr.items():
        if not corr_df.empty:
            corr_df.to_csv(reports_dir / f"glints_jobsgo_{name}_correlation_{run_day}.csv")

    report = render_report(summary, missing, iqr, skills, inventory, errors, endpoint, bucket, now_utc, figures_dir)
    report_path = reports_dir / f"glints_jobsgo_eda_summary_{run_day}.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")
    update_report_section(PROJECT_ROOT / "reports" / "glints_jobsgo_eda.md", "AUTO-GENERATED EDA RESULTS", report)
    update_report_section(PROJECT_ROOT / "reports" / "glints_jobsgo_inventory.md", "AUTO-GENERATED MEASURED INVENTORY", inventory_summary_markdown(summary, missing, inventory, now_utc))

    print(f"[EDA] MinIO: {endpoint} | bucket: {bucket}")
    print(f"[EDA] Latest detail snapshots: {len(df)} | unreadable objects: {len(errors)}")
    print(summary.to_string(index=False))
    print(f"[EDA] Report: {report_path}")
    print(f"[EDA] Figures: {figures_dir}")
    return {"df": df, "summary": summary, "missing_rate": missing, "iqr": iqr, "skills": skills,
            "inventory": inventory, "errors": errors, "report_path": report_path, "figures_dir": figures_dir,
            "pearson": corr["pearson"], "spearman": corr["spearman"]}


def inventory_summary_markdown(summary: pd.DataFrame, missing: pd.DataFrame, inventory: pd.DataFrame, run_time: str) -> str:
    lines = [f"**Đo tự động lúc:** {run_time}", "", "| Nguồn | URL catalog | Latest snapshots | FAILED | Listing errors | Lỗi gần nhất |", "|---|---:|---:|---:|---:|---|"]
    for _, row in summary.iterrows():
        failure = str(row.get("last_listing_failure") or "N/A").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row['source']} | {int(row['catalog_urls'])} | {int(row['latest_detail_snapshots'])} | {int(row['catalog_failed'])} | {int(row.get('listing_failure_count', 0))} | {failure} |")
    lines += ["", "### Missing rate theo snapshot detail mới nhất", "", "| Nguồn | Trường | n | Missing count | Missing rate |", "|---|---|---:|---:|---:|"]
    for _, row in missing.iterrows():
        rate = "N/A" if pd.isna(row["missing_rate_pct"]) else f"{row['missing_rate_pct']:.2f}%"
        lines.append(f"| {row['source']} | `{row['field']}` | {int(row['records'])} | {int(row['missing_count'])} | {rate} |")
    lines += ["", f"Raw inventory measured: {len(inventory)} JSON field / HTML selector rows; see `reports/generated/glints_jobsgo_raw_field_inventory_*.csv` for detailed presence/null rates."]
    return "\n".join(lines)


def update_report_section(path: Path, marker: str, content: str) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    start_marker, end_marker = f"<!-- BEGIN {marker} -->", f"<!-- END {marker} -->"
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 or end < start:
        return
    start += len(start_marker)
    text = text[:start] + "\n\n" + content.rstrip() + "\n\n" + text[end:]
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    try:
        run_eda()
    except Exception as exc:
        print(f"[EDA] ERROR: {exc}", file=sys.stderr)
        print("Kiểm tra Docker/MinIO, file .env, bucket và xem các object raw/<source>/YYYY-MM-DD/*_vN.json.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
