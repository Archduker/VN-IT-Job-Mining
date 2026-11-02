# -*- coding: utf-8 -*-
"""Báo cáo theo nguồn cho trang Raw: 8 feature target, đơn biến, mẫu raw có chú thích."""

from collections import Counter
import json
import logging
import re
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from app.core.config import settings
from app.core.data_paths import iter_raw_files, load_json_report, read_raw_envelopes
from app.core.feature_targets import FEATURES, RAW_PATHS, SOURCE_DOMAINS, SOURCE_ISSUES
from app.core.r2_client import r2_client
from app.services.ledger_service import ledger_service

logger = logging.getLogger("source_report")

MAX_SAMPLE_IDS = 200
NO_STAGING = "Chưa có {name}: cần chạy pipeline tiền xử lý cho nguồn này."


def _experience_years(text: Any) -> Optional[float]:
    """Số năm kinh nghiệm tối thiểu trong chuỗi; không yêu cầu → 0."""
    if text is None:
        return None
    value = str(text).lower()
    if "không yêu cầu" in value or "no experience" in value or "chưa có" in value:
        return 0.0
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:\+\s*)?(?:năm|years?|yrs?)", value)
    return float(match.group(1).replace(",", ".")) if match else None


def _integration_report(source: str) -> Optional[Dict[str, Any]]:
    return load_json_report(
        settings.ROOT_DIR / "reports" / "integration" / f"{source}_integration_report.json"
    )


def _health_card(source: str) -> Optional[Dict[str, Any]]:
    return load_json_report(
        settings.ROOT_DIR / "reports" / source / f"{source}_quality_health_card.json"
    )


def _feature_completeness(audit: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Độ đầy đủ của từng feature: feature nhiều trường lấy trường tốt nhất."""
    result: Dict[str, Optional[float]] = {}
    for feature in FEATURES:
        values = [audit[f]["completeness_pct"] for f in feature["fields"] if f in audit]
        result[feature["code"]] = max(values) if values else None
    return result


def _key_label(path: Sequence[str]) -> str:
    parts = [p[3:].strip("^()") if p.startswith("re:") else p for p in path]
    return " · ".join(parts)


class SourceReportService:
    def list_overview(self) -> List[Dict[str, Any]]:
        """Dữ liệu cho thanh chọn 8 nguồn."""
        items = []
        for source in settings.SUPPORTED_SOURCES:
            report = _integration_report(source)
            completeness = None
            if report:
                values = [v for v in _feature_completeness(report.get("field_completeness_audit", {})).values()
                          if v is not None]
                completeness = round(sum(values) / len(values), 1) if values else None
            items.append({"source": source, "completeness_pct": completeness})
        return items

    def get_report(self, source: str) -> Dict[str, Any]:
        report = _integration_report(source)
        card = _health_card(source)
        audit = (report or {}).get("field_completeness_audit", {})
        completeness = _feature_completeness(audit)
        known = {k: v for k, v in completeness.items() if v is not None}
        weakest = min(known, key=known.get) if known else None
        names = {f["code"]: f["name"] for f in FEATURES}

        targets = []
        issues = []
        overrides = SOURCE_ISSUES.get(source, {})
        for feature in FEATURES:
            code = feature["code"]
            paths = RAW_PATHS[source].get(code, [])
            targets.append({
                "code": code, "name": feature["name"], "use": feature["use"], "std": feature["std"],
                "raw_key": ", ".join(_key_label(p) for p in paths) or None,
            })
            issue = overrides.get(code, {})
            problem = issue.get("problem", feature["problem"])
            where = issue.get("where", feature["where"])
            fix = issue.get("fix", feature["fix"])
            if completeness.get(code) == 0 and code not in overrides:
                problem = "Trường này trống ở toàn bộ bản ghi đã tích hợp"
                where, fix = "Scraper", "Kiểm tra lại flattener và selector của nguồn"
            issues.append({
                "code": code, "label": f"{code} {feature['name']}", "problem": problem,
                "where": where, "fix": fix, "_order": 101 if completeness.get(code) is None else completeness[code],
            })
        issues.sort(key=lambda r: r.pop("_order"))

        ledger = ledger_service.get_system_enum_summary().get("by_source", {}).get(source)
        return {
            "source": source,
            "domain": SOURCE_DOMAINS[source],
            "overview": {
                "integrated_records": report.get("total_integrated_records") if report else None,
                "clean_records": card.get("total_clean_records") if card else None,
                "stub_removed": card.get("stub_jds_removed_policy_1b") if card else None,
                "report_time": report.get("timestamp") if report else None,
                "completeness_pct": round(sum(known.values()) / len(known), 1) if known else None,
                "weakest": f"{weakest} {names[weakest]}" if weakest else None,
                "weakest_pct": known.get(weakest) if weakest else None,
                "ledger": ledger,
            },
            "unavailable_reason": None if report else "Chưa có báo cáo Integration của nguồn này.",
            "targets": targets,
            "issues": issues,
        }

    def _staging_frame(self, source: str, columns: List[str]):
        import pandas as pd

        path = settings.DATA_DIR / "staging" / source / f"{source}_flat_clean.parquet"
        if not path.exists():
            return None
        return pd.read_parquet(path, columns=columns)

    def get_univariate(self, source: str, code: str) -> Dict[str, Any]:
        """Phân bố một feature trên bảng staging; chưa có bảng thì trả trống."""
        import pandas as pd

        name = f"{source}_flat_clean.parquet"
        columns = {
            "F1": ["job_family"], "F2": ["company_name"], "F3": ["primary_city"],
            "F4": ["salary_min_vnd", "salary_max_vnd"], "F5": ["raw_experience_text"],
            "F6": ["job_seniority"], "F7": ["skills_list"],
            "F8": ["raw_posted_date", "crawled_at"],
        }.get(code)
        if columns is None:
            return {"code": code, "kind": "empty", "unavailable_reason": "Feature không hợp lệ."}
        df = self._staging_frame(source, columns)
        if df is None:
            return {"code": code, "kind": "empty", "unavailable_reason": NO_STAGING.format(name=name)}

        total = len(df)
        pct = lambda n, base=None: round(100 * n / max(base or total, 1), 1)  # noqa: E731

        def numeric(title: str, values, edges: List[float], labels: List[str], unit: str,
                    stats: List[Dict[str, Any]]) -> Dict[str, Any]:
            binned = pd.cut(values, bins=edges, labels=labels, right=False)
            counts = binned.value_counts().reindex(labels, fill_value=0)
            items = [{"label": k, "count": int(v), "pct": pct(int(v), len(values))} for k, v in counts.items()]
            return {"code": code, "kind": "num", "title": title, "unit": unit, "base": int(len(values)),
                    "items": items, "stats": stats, "unavailable_reason": None}

        def categorical(title: str, series, top: int = 10) -> Dict[str, Any]:
            present = series.dropna()
            present = present[present.astype(str).str.strip() != ""]
            counts = present.value_counts()
            items = [{"label": str(k), "count": int(v), "pct": pct(int(v), len(present))}
                     for k, v in counts.head(top).items()]
            stats = [
                {"k": "Tin có giá trị", "v": int(len(present))},
                {"k": "Giá trị khác nhau", "v": int(counts.size)},
                {"k": "Phổ biến nhất", "v": items[0]["label"] if items else None},
                {"k": "Thiếu", "v": f"{pct(total - len(present))}%"},
            ]
            return {"code": code, "kind": "cat", "title": title, "base": int(len(present)),
                    "items": items, "stats": stats, "unavailable_reason": None}

        if code == "F1":
            return categorical("Nhóm nghề suy từ title", df["job_family"])
        if code == "F2":
            return categorical("Công ty đăng nhiều tin nhất", df["company_name"])
        if code == "F3":
            return categorical("Tỉnh/thành sau chuẩn hóa", df["primary_city"])
        if code == "F6":
            return categorical("Cấp bậc sau chuẩn hóa", df["job_seniority"])
        if code == "F7":
            lists = df["skills_list"].dropna()
            exploded = pd.Series([s for row in lists for s in list(row) if str(s).strip()], dtype=object)
            result = categorical("Top 10 kỹ năng", exploded)
            filled = sum(1 for row in lists if len(row))
            result["base"] = total
            for item in result["items"]:
                item["pct"] = pct(item["count"])
            result["stats"][0] = {"k": "Tin có kỹ năng", "v": filled}
            result["stats"][3] = {"k": "Thiếu", "v": f"{pct(total - filled)}%"}
            return result
        if code == "F4":
            mid = df[["salary_min_vnd", "salary_max_vnd"]].mean(axis=1, skipna=True).dropna() / 1_000_000
            stats = [
                {"k": "Trung vị", "v": f"{mid.median():.0f} tr" if len(mid) else None},
                {"k": "Trung bình", "v": f"{mid.mean():.0f} tr" if len(mid) else None},
                {"k": "Có lương dạng số", "v": int(len(mid))},
                {"k": "Không có số", "v": f"{pct(total - len(mid))}%"},
            ]
            return numeric("Phân bố lương (triệu VND/tháng, điểm giữa min–max)", mid,
                           [0, 10, 20, 30, 45, 60, 80, 100, float("inf")],
                           ["< 10", "10–20", "20–30", "30–45", "45–60", "60–80", "80–100", "> 100"],
                           "triệu", stats)
        if code == "F5":
            years = df["raw_experience_text"].map(_experience_years).dropna()
            stats = [
                {"k": "Trung vị", "v": f"{years.median():g} năm" if len(years) else None},
                {"k": "Không yêu cầu", "v": f"{pct(int((years == 0).sum()), len(years))}%"},
                {"k": "Từ 5 năm trở lên", "v": f"{pct(int((years >= 5).sum()), len(years))}%"},
                {"k": "Chưa parse được", "v": f"{pct(total - len(years))}%"},
            ]
            return numeric("Số năm kinh nghiệm tối thiểu", years, [0, 1, 2, 3, 4, 5, 8, float("inf")],
                           ["0", "1", "2", "3", "4", "5–7", "8+"], "năm", stats)
        posted = pd.to_datetime(df["raw_posted_date"], errors="coerce", dayfirst=True, utc=True, format="mixed")
        crawled = pd.to_datetime(df["crawled_at"], errors="coerce", utc=True, format="mixed")
        age = (crawled - posted).dt.days.dropna()
        age = age[age >= 0]
        stats = [
            {"k": "Tin có ngày đọc được", "v": int(len(age))},
            {"k": "Tin mới ≤ 7 ngày", "v": f"{pct(int((age <= 7).sum()), len(age))}%"},
            {"k": "Tin cũ > 30 ngày", "v": f"{pct(int((age > 30).sum()), len(age))}%"},
            {"k": "Không đọc được", "v": f"{pct(total - len(age))}%"},
        ]
        return numeric("Tuổi tin lúc cào (ngày)", age, [0, 4, 8, 15, 31, float("inf")],
                       ["0–3", "4–7", "8–14", "15–30", "> 30"], "ngày", stats)

    def _iter_local(self, source: str) -> Iterator[Dict[str, Any]]:
        for _, path in iter_raw_files(source):
            yield from read_raw_envelopes(path)

    def list_samples(self, source: str, query: str = "") -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        origin = None
        needle = query.strip().lower()
        for envelope in self._iter_local(source):
            meta = envelope.get("metadata") or envelope.get("_meta") or {}
            payload = envelope.get("raw_payload") or envelope.get("raw") or {}
            job_id = str(meta.get("job_id") or meta.get("source_job_id") or "")
            title = payload.get("title") or payload.get("jobTitle") or payload.get("job-title")
            if not job_id or (needle and needle not in f"{job_id} {title}".lower()):
                continue
            origin = "local"
            items.append({"id": job_id, "title": title})
            if len(items) >= MAX_SAMPLE_IDS:
                break
        if not items:
            client = r2_client.get_client()
            if client:
                try:
                    pages = client.get_paginator("list_objects_v2").paginate(
                        Bucket=r2_client.bucket_name, Prefix=f"raw/{source}/", MaxKeys=MAX_SAMPLE_IDS)
                    for page in pages:
                        for obj in page.get("Contents", []):
                            stem = obj["Key"].rsplit("/", 1)[-1].removesuffix(".json")
                            job_id = re.sub(r"_v\d+$", "", stem)
                            if needle in job_id.lower():
                                items.append({"id": job_id, "title": None, "key": obj["Key"]})
                        if len(items) >= MAX_SAMPLE_IDS:
                            break
                    origin = "r2" if items else None
                except Exception as exc:
                    logger.warning("Không liệt kê được raw trên R2 cho %s: %s", source, exc)
        return {
            "source": source, "origin": origin, "items": items[:MAX_SAMPLE_IDS],
            "unavailable_reason": None if items else "Không có bản ghi raw cục bộ, và chưa đọc được từ R2.",
        }

    def _find_envelope(self, source: str, job_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        for envelope in self._iter_local(source):
            meta = envelope.get("metadata") or envelope.get("_meta") or {}
            if str(meta.get("job_id") or meta.get("source_job_id") or "") == job_id:
                return envelope, "local"
        for item in self.list_samples(source, job_id)["items"]:
            key = item.get("key")
            if item["id"] == job_id and key:
                try:
                    body = r2_client.get_client().get_object(Bucket=r2_client.bucket_name, Key=key)["Body"].read()
                    return json.loads(body), "r2"
                except Exception as exc:
                    logger.warning("Không tải được %s từ R2: %s", key, exc)
        return None, None

    def get_sample(self, source: str, job_id: str) -> Optional[Dict[str, Any]]:
        envelope, origin = self._find_envelope(source, job_id)
        if envelope is None:
            return None
        return {
            "source": source, "id": job_id, "origin": origin, "raw": envelope,
            **annotate_envelope(source, envelope),
        }


def _match_paths(node: Any, spec: Sequence[str], prefix: Tuple[Any, ...]) -> Iterator[Tuple[Any, ...]]:
    """Tìm các đường dẫn thật trong raw theo một mẫu của RAW_PATHS."""
    if not spec:
        if node not in (None, "", [], {}):
            yield prefix
        return
    head, rest = spec[0], spec[1:]
    if head.startswith("re:") and isinstance(node, list):
        for index, item in enumerate(node):
            if isinstance(item, str) and re.search(head[3:], item.strip()):
                yield prefix + (index,)
    elif isinstance(node, dict) and head in node:
        yield from _match_paths(node[head], rest, prefix + (head,))


def _duplicate_paths(node: Any, prefix: Tuple[Any, ...]) -> Iterator[Tuple[Any, ...]]:
    """Các dòng lặp lại y hệt trong một list chuỗi."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _duplicate_paths(value, prefix + (key,))
    elif isinstance(node, list):
        seen = set()
        for index, item in enumerate(node):
            if isinstance(item, str):
                if item in seen:
                    yield prefix + (index,)
                seen.add(item)
            else:
                yield from _duplicate_paths(item, prefix + (index,))


def _value_at(root: Any, path: Sequence[Any]) -> Any:
    for part in path:
        root = root[part]
    return root


def _short(value: Any, limit: int = 160) -> Optional[str]:
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _normalized_values(flat: Dict[str, Any]) -> Dict[str, Tuple[Optional[str], bool]]:
    """Giá trị chuẩn hóa thật từ các hàm preprocessing, kèm cờ suy từ trường khác."""
    from preprocessing.normalization.cross_deduplicator import normalize_company_name
    from preprocessing.normalization.text_cleaner import (
        classify_job_family, clean_job_title, normalize_city, normalize_seniority,
    )
    from preprocessing.transformation.salary_parser import parse_salary_cascade

    title = flat.get("job_title")
    jd = f"{flat.get('raw_description_text') or ''}\n{flat.get('raw_requirements_text') or ''}"
    salary = parse_salary_cascade(flat.get("raw_salary_text"), jd)
    s_min, s_max = salary.get("salary_min_vnd"), salary.get("salary_max_vnd")
    money = lambda v: f"{int(v):,}".replace(",", ".") if v else "?"  # noqa: E731
    years = _experience_years(flat.get("raw_experience_text"))
    seniority_raw = flat.get("raw_seniority_text")
    location = flat.get("raw_location_text")
    locations = flat.get("working_locations") or []
    return {
        "F1": (f"{clean_job_title(title)} · {classify_job_family(title, flat.get('skills_list'))}" if title else None, False),
        "F2": (normalize_company_name(flat.get("company_name")) or None, False),
        "F3": (normalize_city(location or locations[0]) if location or locations else None, not location),
        "F4": (f"{money(s_min)} – {money(s_max)} VND" if s_min or s_max else None,
               salary.get("salary_source") not in ("header", None)),
        "F5": (f"{years:g} năm (tối thiểu)" if years is not None else None, False),
        "F6": (normalize_seniority(seniority_raw, title), not seniority_raw),
        "F7": (", ".join(flat.get("skills_list") or []) or None, False),
        "F8": (" → ".join(v for v in (flat.get("raw_posted_date"), flat.get("raw_deadline")) if v) or None, False),
    }


def annotate_envelope(source: str, envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Tạo chú thích F1–F8 và danh sách dòng cần tô cho một bản ghi raw."""
    from preprocessing.integration.json_flattener import flatten_raw_job_record

    payload = envelope.get("raw_payload") or envelope.get("raw") or {}
    key = "raw_payload" if "raw_payload" in envelope else "raw"
    flat = flatten_raw_job_record(envelope, source_fallback=source)
    normalized = _normalized_values(flat)
    duplicates = {(key,) + p for p in _duplicate_paths(payload, ())}

    highlights: List[Dict[str, Any]] = [{"path": list(p), "kind": "dup", "feature": None} for p in duplicates]
    notes: List[Dict[str, Any]] = []
    overrides = SOURCE_ISSUES.get(source, {})
    for feature in FEATURES:
        code = feature["code"]
        specs = RAW_PATHS[source].get(code, [])
        found = [p for spec in specs for p in _match_paths(payload, spec, (key,))]
        found = [p for p in found if p not in duplicates]
        for path in found:
            highlights.append({"path": list(path), "kind": "feature", "feature": code})
        raw_text = " · ".join(filter(None, (_short(_value_at(envelope, p)) for p in found))) or None
        value, inferred = normalized[code]
        status = "missing"
        if value:
            status = "fallback" if inferred or not found else "ok"
        elif found:
            status = "fail"
        warning = overrides.get(code, {}).get("problem") if source == "careerviet" and code == "F7" else None
        if warning and status == "ok":
            status = "warn"
        notes.append({
            "code": code, "name": feature["name"], "status": status,
            "path": ", ".join(".".join(str(x) for x in p) for p in found[:3]) or None,
            "raw": raw_text, "normalized": value, "how": warning or feature["how"],
        })
    meta = envelope.get("metadata") or envelope.get("_meta") or {}
    title = flat.get("job_title")
    return {"title": title, "scraped_at": meta.get("scraped_at") or meta.get("crawled_at"),
            "highlights": highlights, "notes": notes,
            "features_in_raw": sum(1 for n in notes if n["raw"])}


source_report_service = SourceReportService()
