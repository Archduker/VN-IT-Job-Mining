"""Normalize locations to Vietnam's 34 current provincial-level units."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_DICTIONARY = Path(__file__).resolve().parents[1] / "dictionaries" / "provinces_34.json"


def _fold(value: str) -> str:
    value = value.casefold().replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _load_dictionary() -> dict[str, Any]:
    with _DICTIONARY.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if len(data.get("provinces", [])) != 34:
        raise ValueError("provinces_34.json must contain exactly 34 provincial units")
    return data


_DATA = _load_dictionary()
_ALIASES: list[tuple[str, str]] = []
for _province in _DATA["provinces"]:
    for _alias in [_province["canonical"], *_province.get("aliases", [])]:
        normalized = _fold(_alias)
        if normalized:
            _ALIASES.append((normalized, _province["canonical"]))
_ALIASES.sort(key=lambda item: len(item[0]), reverse=True)
_SPECIAL = {key: {_fold(value) for value in values} for key, values in _DATA.get("special_values", {}).items()}


def _is_missing(value: Any) -> bool:
    if value is None or value.__class__.__name__ in {"NAType", "NaTType"}:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return not value
    return False


def _flatten_location(value: Any) -> str:
    if isinstance(value, Mapping):
        preferred = ("address", "name", "city", "province", "location", "display_name")
        parts = [_flatten_location(value[key]) for key in preferred if key in value]
        return " ; ".join(part for part in parts if part)
    if isinstance(value, (list, tuple, set)):
        return " ; ".join(_flatten_location(item) for item in value if not _is_missing(item))
    return "" if _is_missing(value) else str(value)


def normalize_location(raw_location: Any) -> str | None:
    """Return canonical province, Remote, Toàn quốc, Nhiều địa điểm, or None."""
    if _is_missing(raw_location):
        return None
    text = _fold(_flatten_location(raw_location))
    if not text:
        return None
    for special_key, label in (("remote", "Remote"), ("nationwide", "Toàn quốc"),
                               ("multi_location", "Nhiều địa điểm")):
        for phrase in _SPECIAL.get(special_key, set()):
            if phrase and re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text):
                return label
    found: set[str] = set()
    for alias, canonical in _ALIASES:
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
            found.add(canonical)
    if len(found) == 1:
        return next(iter(found))
    if len(found) > 1:
        return "Nhiều địa điểm"
    return None


def select_location_source(working_locations: Any = None, raw_location_text: Any = None,
                           company_address: Any = None) -> Any:
    """Choose populated fields by priority while preserving multi-location lists."""
    for value in (working_locations, raw_location_text, company_address):
        if not _is_missing(value):
            return value
    return None


def normalize_location_from_fields(working_locations: Any = None, raw_location_text: Any = None,
                                   company_address: Any = None) -> str | None:
    return normalize_location(select_location_source(working_locations, raw_location_text, company_address))


def get_province_dictionary_version() -> str:
    return str(_DATA.get("version", "unknown"))


def get_province_count() -> int:
    return len(_DATA.get("provinces", []))
