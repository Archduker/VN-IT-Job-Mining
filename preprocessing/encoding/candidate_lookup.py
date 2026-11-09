"""Strict, review/candidate-only skill lookup; production encoder is unchanged.

Canonical names are always keys. Slugs name columns, never act as lookup keys.
There is no parent propagation, tokenization, fuzzy or substring matching.
"""

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from preprocessing.encoding.run import to_col_slug


@dataclass(frozen=True)
class CandidateLookup:
    canonical: tuple[str, ...]
    columns: tuple[str, ...]
    owners: Mapping[str, int]


@dataclass(frozen=True)
class CandidateEncoding:
    matrix: np.ndarray
    unmatched: tuple[frozenset[str], ...]
    missing: tuple[bool, ...]


def build_candidate_lookup(items: Sequence[Mapping], expected_count: int | None = None):
    """Validate ordered owners/aliases/column slugs before encoding any rows."""
    if expected_count is not None and len(items) != expected_count:
        raise ValueError(f"Expected {expected_count} skills, got {len(items)}")
    canonical, columns, owners, slug_owners = [], [], {}, {}
    for index, item in enumerate(items):
        name = item["canonical"]
        if not isinstance(name, str) or not name or name != name.strip():
            raise ValueError("Canonical must be a nonempty trimmed string")
        slug = to_col_slug(name)
        column = f"skill_{slug}"
        if slug in slug_owners:
            raise ValueError(f"Slug collision: {name} / {slug_owners[slug]}")
        if item.get("index", index) != index or item.get("column", column) != column:
            raise ValueError("Inconsistent vocabulary index/column")
        aliases = item.get("aliases", [])
        if not isinstance(aliases, (list, tuple)):
            raise ValueError("Aliases must be an array")
        for value in [name, *aliases]:
            if not isinstance(value, str) or not value:
                raise ValueError("Alias must be a nonempty string")
            key = value.casefold()
            if key in owners and owners[key] != index:
                raise ValueError(f"Alias collision: {value}")
            owners[key] = index  # repeated canonical/alias of this owner is harmless
        slug_owners[slug] = name
        canonical.append(name)
        columns.append(column)
    return CandidateLookup(tuple(canonical), tuple(columns), owners)


def load_candidate_lookup(path: str | Path, expected_count: int | None = None):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("status") != "proposed_not_production":
        raise ValueError("This loader only accepts explicitly proposed candidate mappings")
    return build_candidate_lookup(payload["items"], expected_count)


def encode_candidate_rows(rows: Iterable, lookup: CandidateLookup) -> CandidateEncoding:
    """Use exactly the same whole-value lookup for bits and unmatched values."""
    rows = list(rows)
    matrix = np.zeros((len(rows), len(lookup.canonical)), dtype=np.uint8)
    unmatched, missing = [], []
    for i, values in enumerate(rows):
        is_missing = values is None or (
            isinstance(values, (float, np.floating)) and np.isnan(values)
        )
        missing.append(is_missing)
        unknown = set()
        if not is_missing:
            if isinstance(values, (str, bytes, Mapping)) or not isinstance(values, Iterable):
                raise ValueError("Skills must be a nullable collection of whole strings")
            for value in values:
                if not isinstance(value, str):
                    raise ValueError("Skill elements must be strings")
                key = value.casefold()
                owner = lookup.owners.get(key)
                if owner is None:
                    unknown.add(key)
                else:
                    matrix[i, owner] = 1
        unmatched.append(frozenset(unknown))
    return CandidateEncoding(matrix, tuple(unmatched), tuple(missing))
