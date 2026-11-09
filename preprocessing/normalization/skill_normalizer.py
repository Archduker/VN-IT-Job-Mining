"""Taxonomy lookup and context-aware extraction of canonical IT skills."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

_DICTIONARY = (
    Path(__file__).resolve().parents[1]
    / "dictionaries"
    / "skills_taxonomy.json"
)

def _fold(value: str) -> str:
    value = value.casefold().replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value).strip()


def _as_text(value: Any) -> str:
    if value is None or value.__class__.__name__ in {"NAType", "NaTType"}:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, dict):
        order = ("name", "skill", "canonical", "value", "text", "label")
        preferred = [value[key] for key in order if key in value]
        remaining = [item for key, item in value.items() if key not in order]
        return " ".join(_as_text(item) for item in preferred + remaining)
    if isinstance(value, (list, tuple, set)):
        return " ".join(_as_text(item) for item in value)
    return str(value)


def _load_dictionary() -> dict[str, Any]:
    with _DICTIONARY.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if len(data.get("categories", [])) != 6:
        raise ValueError(
            "skills_taxonomy.json must contain six core taxonomy categories"
        )
    return data


_DATA = _load_dictionary()
SKILL_TAXONOMY: list[dict[str, Any]] = _DATA["categories"]


def _contains(text: str, alias: str) -> bool:
    """Boundary matching that preserves punctuation in terms such as C++, C#, CI/CD."""
    alias = _fold(alias)
    if not alias:
        return False
    if alias == "js":
        return re.search(r"(?<![a-z0-9.])js(?![a-z0-9])", text) is not None
    body = r"\s+".join(re.escape(part) for part in alias.split())
    return re.search(rf"(?<![a-z0-9]){body}(?![a-z0-9])", text) is not None


def _contains_short_token(text: str, token: str) -> bool:
    token = _fold(token)
    return bool(token and re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text))


def _near_context_matches(text: str, token: str, context_terms: list[str],
                          max_gap_words: int = 3) -> bool:
    """Require disambiguating context close to the ambiguous short token."""
    token_pattern = re.compile(rf"(?<![a-z0-9]){re.escape(_fold(token))}(?![a-z0-9])")
    for token_match in token_pattern.finditer(text):
        for term in context_terms:
            folded_term = _fold(term)
            if not folded_term:
                continue
            body = r"\s+".join(re.escape(part) for part in folded_term.split())
            term_pattern = re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")
            for term_match in term_pattern.finditer(text):
                if term_match.start() >= token_match.end():
                    gap = text[token_match.end():term_match.start()]
                elif term_match.end() <= token_match.start():
                    gap = text[term_match.end():token_match.start()]
                else:
                    gap = ""
                if len(gap.split()) <= max_gap_words:
                    return True
    return False


def extract_skills(*fields: Any) -> list[str]:
    """Extract canonical skills; ambiguous aliases require nearby technical context."""
    raw_text = " ".join(part for part in (_as_text(value) for value in fields) if part)
    if not raw_text:
        return []
    text = _fold(raw_text)
    found: list[str] = []

    for category in SKILL_TAXONOMY:
        for skill in category["skills"]:
            canonical = skill["canonical"]
            contextual_aliases = skill.get("contextual_aliases", {})
            contextual_keys = {_fold(key) for key in contextual_aliases}
            matched = any(
                _contains(text, alias)
                for alias in skill.get("aliases", [])
                if _fold(alias) not in contextual_keys
            )

            if skill.get("short_name"):
                context_terms = skill.get("context_keywords", [])
                if canonical == "Go":
                    explicit = any(_contains(text, alias) for alias in
                                   ("golang", "go developer", "golang developer", "go language", "lap trinh go"))
                    matched = matched or explicit or _near_context_matches(text, "go", context_terms, 3)
                elif canonical == "C":
                    explicit = any(_contains(text, alias) for alias in
                                   ("c/c++", "c/embedded", "embedded c", "c programming", "c language", "lap trinh c"))
                    matched = matched or explicit or _near_context_matches(text, "c", context_terms, 3)
                elif canonical == "R":
                    matched = matched or _near_context_matches(text, "r", context_terms, 4)
                elif canonical == "Artificial Intelligence":
                    matched = matched or _near_context_matches(text, "ai", context_terms, 3)

            for alias, terms in contextual_aliases.items():
                matched = matched or _near_context_matches(text, alias, terms, 3)

            if matched and canonical not in found:
                found.append(canonical)
    return found


def taxonomy_lookup(canonical_or_alias: str) -> dict[str, str] | None:
    """Resolve a canonical name/alias; return None for ambiguous aliases."""
    query = _fold(str(canonical_or_alias))
    if not query:
        return None
    matches: dict[str, dict[str, str]] = {}
    for category in SKILL_TAXONOMY:
        for skill in category["skills"]:
            aliases = [_fold(alias) for alias in skill.get("aliases", [])]
            if query == _fold(skill["canonical"]) or query in aliases:
                matches[skill["canonical"]] = {"canonical": skill["canonical"], "category": category["name"]}
    return next(iter(matches.values())) if len(matches) == 1 else None


def get_taxonomy_categories() -> list[str]:
    return [category["name"] for category in SKILL_TAXONOMY]


def get_taxonomy_skill_count() -> int:
    return sum(len(category["skills"]) for category in SKILL_TAXONOMY)


def validate_taxonomy() -> list[str]:
    warnings: list[str] = []
    canonical_seen: set[str] = set()
    alias_map: dict[str, set[str]] = {}
    for category in SKILL_TAXONOMY:
        for skill in category["skills"]:
            canonical = skill["canonical"]
            folded = _fold(canonical)
            if folded in canonical_seen:
                warnings.append(f"Duplicate canonical skill: {canonical}")
            canonical_seen.add(folded)
            for alias in skill.get("aliases", []):
                alias_map.setdefault(_fold(alias), set()).add(canonical)
    for alias, canonicals in alias_map.items():
        if len(canonicals) > 1:
            warnings.append(f"Ambiguous alias {alias!r}: {sorted(canonicals)}")
    return warnings
