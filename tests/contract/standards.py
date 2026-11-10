# -*- coding: utf-8 -*-
"""Kiểm tra dùng chung cho contract test của crawler (tiêu chuẩn C1–C14 trong collection/CLAUDE.md).

Mỗi file tests/contract/test_<nguồn>_contract.py chỉ cần cung cấp: cách bóc tách một mẫu thành envelope, và cách
chạy crawl_details offline với ledger tạm. Các hàm ở đây kiểm tra phần giống nhau giữa các nguồn.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.core.feature_targets import FEATURES, RAW_PATHS
from app.services.source_report_service import _match_paths, _value_at
from collection.common.r2_storage import canonicalize_lakehouse_key, to_r2_key

REQUIRED_METADATA = ("job_id", "source", "source_url", "scraped_at", "version", "content_hash")
MIN_FEATURE_COVERAGE = 0.9  # C11: mỗi trường F1–F8 có ở >= 90% bản ghi


def envelope_dict(envelope: Any) -> Dict[str, Any]:
    return envelope.model_dump() if hasattr(envelope, "model_dump") else dict(envelope)


def check_two_phase(crawler_cls) -> None:
    """C1."""
    for name in ("discover_urls", "crawl_details"):
        assert callable(getattr(crawler_cls, name, None)), f"{crawler_cls.__name__} thiếu {name}()"


def check_envelope(envelope: Any, source: str) -> None:
    """C4."""
    env = envelope_dict(envelope)
    meta, payload = env.get("metadata") or {}, env.get("raw_payload")
    missing = [k for k in REQUIRED_METADATA if meta.get(k) in (None, "")]
    assert not missing, f"metadata thiếu {missing}"
    assert meta["source"] == source
    assert isinstance(payload, dict) and payload, "raw_payload rỗng"


def filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def feature_coverage(envelopes: Iterable[Any], source: str) -> Dict[str, float]:
    """Tỉ lệ mẫu có giá trị cho từng F theo RAW_PATHS; trường nguồn không hiển thị (RAW_PATHS rỗng) bị bỏ qua."""
    envs = [envelope_dict(e) for e in envelopes]
    result = {}
    for feature in FEATURES:
        specs = RAW_PATHS[source].get(feature["code"], [])
        if not specs:
            continue
        hits = sum(
            1 for env in envs
            if any(filled(_value_at(env, p)) for spec in specs for p in _match_paths(env["raw_payload"], spec, ("raw_payload",)))
        )
        result[feature["code"]] = hits / len(envs)
    return result


def check_feature_coverage(envelopes: List[Any], source: str, allow_missing: Dict[str, str] | None = None) -> None:
    """C11. allow_missing: {mã F: lý do} cho trường biết trước là thiếu ở nguồn này (phải ghi lý do)."""
    allow_missing = allow_missing or {}
    low = {code: pct for code, pct in feature_coverage(envelopes, source).items()
           if pct < MIN_FEATURE_COVERAGE and code not in allow_missing}
    assert not low, f"{source}: trường dưới {MIN_FEATURE_COVERAGE:.0%} trên mẫu: {low}"


def check_r2_keys(keys: Iterable[str], source: str) -> None:
    """C8: key đã ghi lên R2 đúng layout chuẩn."""
    keys = list(keys)
    assert keys, "không có key nào được ghi lên R2"
    for key in keys:
        assert canonicalize_lakehouse_key(key) == to_r2_key(key), f"key sai layout: {key}"  # crawler phát khóa logic; R2RawStore đổi sang prefix R2
        assert key.split("/")[1] == source, f"key không thuộc nguồn {source}: {key}"


MIN_PAUSE, MAX_PAUSE = 2.0, 4.5  # C10
_PAUSE_PARAMS = ({"min_delay", "min_seconds"}, {"max_delay", "max_seconds"})


def _num(node: Any) -> float | None:
    return float(node.value) if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) else None


def check_random_pause(module: Any) -> None:
    """C10: vòng detail có nghỉ ngẫu nhiên (polite_sleep, uniform, hoặc DelayConfig/HttpClient) giữa các request,
    và mọi khoảng nghỉ viết bằng hằng số (polite_sleep, DelayConfig, giá trị mặc định min_/max_delay) phải >= 2,0–4,5 giây."""
    tree = ast.parse(inspect.getsource(module))
    names = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
             for n in ast.walk(tree) if isinstance(n, ast.Call)}
    has_pause = "polite_sleep" in names or "uniform" in names or "DelayConfig" in names
    assert has_pause, f"{module.__name__} không có nghỉ ngẫu nhiên giữa request"

    pairs: list[tuple[float, float, int]] = []  # (min, max, dòng)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) in {"polite_sleep", "DelayConfig"}:
            vals = [_num(a) for a in n.args[:2]] + [None] * 2
            kw = {k.arg: _num(k.value) for k in n.keywords}
            lo = vals[0] if vals[0] is not None else next((kw[k] for k in _PAUSE_PARAMS[0] if kw.get(k) is not None), None)
            hi = vals[1] if vals[1] is not None else next((kw[k] for k in _PAUSE_PARAMS[1] if kw.get(k) is not None), None)
            if lo is not None and hi is not None:
                pairs.append((lo, hi, n.lineno))
        elif isinstance(n, ast.FunctionDef):
            defaults = dict(zip([a.arg for a in n.args.args][-len(n.args.defaults):] if n.args.defaults else [], n.args.defaults))
            lo = next((_num(defaults[k]) for k in _PAUSE_PARAMS[0] if k in defaults), None)
            hi = next((_num(defaults[k]) for k in _PAUSE_PARAMS[1] if k in defaults), None)
            if lo is not None and hi is not None:
                pairs.append((lo, hi, n.lineno))
    bad = [(lo, hi, line) for lo, hi, line in pairs if lo < MIN_PAUSE or hi < MAX_PAUSE]
    assert not bad, f"{module.__name__}: nghỉ dưới chuẩn {MIN_PAUSE}-{MAX_PAUSE}s (min, max, dòng): {bad}"


def check_fixtures(folder: Path, expected: Iterable[str]) -> None:
    """C13."""
    missing = [name for name in expected if not (folder / name).exists()]
    assert not missing, f"thiếu mẫu trong {folder}: {missing}"


class FakeR2Store:
    """Thay R2RawStore: ghi nhận key, không ra mạng."""

    def __init__(self):
        self.keys: List[str] = []

    def put_json(self, key, data, *args, **kwargs):
        self.keys.append(key)
        return key
