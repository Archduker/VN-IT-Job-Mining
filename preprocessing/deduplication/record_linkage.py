# -*- coding: utf-8 -*-
"""Record linkage for intra-platform reposts and cross-platform job duplicates.

This module is deliberately downstream of Integration, Transformation, Missing/Outlier,
and Text/Skill normalization. It does not mutate raw files or infer missing fields.

Algorithm:
1. Blocking on normalized company + primary city + standardized job family.
2. Pair scoring with Jaro-Winkler title similarity and TF-IDF cosine similarity for
   the JD text and skills list.
3. High-precision linking: title >= 0.88 AND (JD cosine >= 0.88 OR skills cosine >= 0.88).
4. Connected components receive a deterministic cluster_id. Input rows are retained;
   Golden Record resolution is handled by golden_record_resolver.py.

The thresholds are configurable for evaluation, but the specified defaults are kept at
0.88. Missing blocking keys are not imputed and such rows are not matched automatically.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import unicodedata
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KNOWN_PLATFORMS: Tuple[str, ...] = (
    "topcv",
    "topdev",
    "vietnamworks",
    "itviec",
    "careerviet",
    "vieclam24h",
    "glints",
    "jobsgo",
)

_MISSING_STRINGS = {
    "", "-", "--", "—", "n/a", "na", "n.a.", "none", "null", "nan",
    "unknown", "khong ro", "chua cap nhat", "khong xac dinh",
}

_LEGAL_ENTITY_PATTERNS = (
    r"\bcong ty co phan\b",
    r"\bcong ty trach nhiem huu han\b",
    r"\bcong ty\b",
    r"\btrach nhiem huu han\b",
    r"\bco phan\b",
    r"\btnhh\b",
    r"\bmtv\b",
    r"\bcp\b",
    r"\bjsc\b",
    r"\bjoint stock company\b",
    r"\blimited liability company\b",
    r"\bco\b",
    r"\blimited\b",
    r"\bltd\b",
    r"\bincorporated\b",
    r"\binc\b",
    r"\bcorporation\b",
    r"\bcorp\b",
    r"\btap doan\b",
    r"\bgroup\b",
    r"\bviet nam\b",
    r"\bvietnam\b",
    r"\bvn\b",
)

_TITLE_NOISE = {
    "tuyen", "dung", "gap", "can", "viec", "lam", "job", "hiring", "urgent",
}


@dataclass(frozen=True)
class LinkageConfig:
    """Thresholds and model-size settings for blocking and pair matching."""

    title_similarity_threshold: float = 0.88
    content_cosine_threshold: float = 0.88
    max_features: int = 5000
    ngram_range: Tuple[int, int] = (1, 2)
    prefer_semantic_embeddings: bool = True
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    def __post_init__(self) -> None:
        for name, value in (
            ("title_similarity_threshold", self.title_similarity_threshold),
            ("content_cosine_threshold", self.content_cosine_threshold),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value!r}")
        if self.max_features < 1:
            raise ValueError("max_features must be >= 1")


def _is_missing(value: Any) -> bool:
    """Safely identify Python/pandas/NumPy nulls and common empty-key placeholders."""
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    if isinstance(value, str):
        normalized = _remove_diacritics(value).strip().casefold()
        return normalized in _MISSING_STRINGS
    if isinstance(value, (list, tuple, set, dict, np.ndarray)):
        return len(value) == 0
    try:
        result = pd.isna(value)
        if result is pd.NA:
            return True
        return bool(result) if isinstance(result, (bool, np.bool_)) else False
    except (TypeError, ValueError):
        return False


def _remove_diacritics(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _safe_str(value: Any) -> str:
    if _is_missing(value):
        return ""
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return " ".join(_safe_str(item) for item in value if not _is_missing(item))
    if isinstance(value, Mapping):
        return " "
    return str(value).strip()


def _first_nonempty(record: Mapping[str, Any], columns: Sequence[str]) -> Any:
    for column in columns:
        value = record.get(column)
        if not _is_missing(value):
            return value
    return None


def normalize_company_name(name: Any) -> str:
    """Normalize a company name for blocking, including common legal suffixes.

    The function only creates a comparison key; it does not overwrite company_name.
    """
    value = _safe_str(name)
    if not value:
        return ""
    value = _remove_diacritics(unicodedata.normalize("NFKC", value)).casefold()
    for pattern in _LEGAL_ENTITY_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_city(city: Any) -> str:
    """Canonicalize a provided primary city without guessing a missing city."""
    value = _safe_str(city)
    if not value:
        return ""
    value = _remove_diacritics(unicodedata.normalize("NFKC", value)).casefold().strip()
    value = re.sub(r"[()[\]]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,.-")
    # Canonical aliases common in Vietnamese job listings.
    compact = re.sub(r"[^a-z0-9]", "", value)
    if compact in {"hcm", "hcmc", "tphcm", "tphochiminh", "hochiminhcity", "saigon"}:
        return "ho chi minh"
    if compact in {"hanoi", "hn", "thanhphohanoi"}:
        return "ha noi"
    if compact in {"danang", "thanhphodanang"}:
        return "da nang"
    if compact in {"remote", "workfromhome", "wfh"}:
        return "remote"
    # When a city is followed by a country, keep the city token only if the input
    # has a clearly separated, canonical first component.
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if parts:
        value = parts[0]
    return re.sub(r"\s+", " ", value).strip()


def normalize_job_family(value: Any) -> str:
    """Normalize a standardized job-family label for exact blocking."""
    text = _safe_str(value)
    if not text:
        return ""
    text = _remove_diacritics(unicodedata.normalize("NFKC", text)).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalized_title(value: Any) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    text = _remove_diacritics(unicodedata.normalize("NFKC", text)).casefold()
    tokens = re.findall(r"[a-z0-9+#.]+", text)
    tokens = [token for token in tokens if token not in _TITLE_NOISE]
    return " ".join(tokens)


def _jaro_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    match_distance = max(len(left), len(right)) // 2 - 1
    match_distance = max(0, match_distance)
    left_matches = [False] * len(left)
    right_matches = [False] * len(right)
    matches = 0

    for i, char in enumerate(left):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len(right))
        for j in range(start, end):
            if right_matches[j] or char != right[j]:
                continue
            left_matches[i] = True
            right_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    matched_left = [left[i] for i, matched in enumerate(left_matches) if matched]
    matched_right = [right[i] for i, matched in enumerate(right_matches) if matched]
    transpositions = sum(a != b for a, b in zip(matched_left, matched_right)) / 2.0
    return (
        matches / len(left)
        + matches / len(right)
        + (matches - transpositions) / matches
    ) / 3.0


def jaro_winkler_similarity(left: Any, right: Any, prefix_scale: float = 0.1) -> float:
    """Return Jaro-Winkler similarity in [0, 1] for job-title comparison.

    In addition to the usual ordered form, a token-order-invariant Jaro-Winkler
    comparison is used to tolerate common title word reordering between platforms.
    The returned score is the larger of the two Jaro-Winkler scores.
    """
    a = _normalized_title(left)
    b = _normalized_title(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    def score(x: str, y: str) -> float:
        jaro = _jaro_similarity(x, y)
        prefix = 0
        for cx, cy in zip(x[:4], y[:4]):
            if cx != cy:
                break
            prefix += 1
        return jaro + prefix * prefix_scale * (1.0 - jaro)

    ordered = score(a, b)
    bag_left = " ".join(sorted(a.split()))
    bag_right = " ".join(sorted(b.split()))
    reordered = score(bag_left, bag_right)
    return max(ordered, reordered)


def _normalize_text_for_vectorizer(value: Any) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = _remove_diacritics(unicodedata.normalize("NFKC", text)).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _record_jd_text(record: Mapping[str, Any]) -> str:
    # Prefer cleaned fields when present, but retain raw requirements/description
    # because some sources have not populated the clean fields for every record.
    fields = (
        "jd_clean_text",
        "job_description_raw",
        "raw_description_text",
        "description_text",
        "job_description",
        "raw_requirements_text",
        "requirements_clean_text",
        "requirements_text",
    )
    parts: List[str] = []
    seen: Set[str] = set()
    for field in fields:
        text = _normalize_text_for_vectorizer(record.get(field))
        if text and text not in seen:
            seen.add(text)
            parts.append(text)
    return " ".join(parts)


def _record_skills_text(record: Mapping[str, Any]) -> str:
    fields = ("skills_list", "extracted_skills", "raw_skill_tags", "skills", "skill_tags")
    tokens: List[str] = []
    seen: Set[str] = set()
    for field in fields:
        value = record.get(field)
        if _is_missing(value):
            continue
        values: Iterable[Any]
        if isinstance(value, str):
            # String fields are fallback-only and can be comma/semicolon separated.
            values = re.split(r"[,;|\n]", value)
        elif isinstance(value, Mapping):
            values = value.values()
        elif isinstance(value, Iterable):
            values = value
        else:
            values = [value]
        for item in values:
            skill = _normalize_text_for_vectorizer(item)
            if skill and skill not in seen:
                seen.add(skill)
                tokens.append(skill)
    return " ".join(tokens)


def _load_local_sentence_transformer(config: LinkageConfig) -> Any | None:
    """Load MiniLM only when it is already available locally; never download a model silently."""
    if not config.prefer_semantic_embeddings:
        return None
    model_path = os.environ.get("VN_IT_JOBS_DEDUP_MODEL_PATH")
    candidate_paths: List[Path] = []
    if model_path:
        candidate_paths.append(Path(model_path).expanduser())
    direct = Path(config.embedding_model_name).expanduser()
    if direct.exists():
        candidate_paths.append(direct)
    cache = Path.home() / ".cache" / "huggingface" / "hub" / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots"
    if cache.is_dir():
        candidate_paths.extend(sorted((path for path in cache.iterdir() if path.is_dir()), reverse=True))

    usable_path = next((path for path in candidate_paths if path.is_dir()), None)
    if usable_path is None:
        return None
    try:
        from sentence_transformers import SentenceTransformer  # optional, not a required dependency
        return SentenceTransformer(str(usable_path), device="cpu")
    except Exception:
        # Model cache/dependency errors must not crash data inspection; the chosen
        # backend is returned in metrics so the fallback is transparent.
        return None


def _cosine_matrix(texts: Sequence[str], config: LinkageConfig, model: Any | None = None) -> np.ndarray:
    """Build an all-pairs cosine matrix using MiniLM when cached, else TF-IDF.

    Empty text comparisons always score zero. The model is optional so unit tests and
    offline environments can run without downloading a neural network.
    """
    n = len(texts)
    matrix = np.zeros((n, n), dtype=float)
    if n == 0:
        return matrix
    for i, text in enumerate(texts):
        if text:
            matrix[i, i] = 1.0
    nonempty = [i for i, text in enumerate(texts) if text.strip()]
    if len(nonempty) < 2:
        return matrix
    try:
        selected_texts = [texts[i] for i in nonempty]
        if model is not None:
            vectors = model.encode(
                selected_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            sims = cosine_similarity(np.asarray(vectors, dtype=float))
        else:
            vectorizer = TfidfVectorizer(
                lowercase=True,
                strip_accents="unicode",
                ngram_range=config.ngram_range,
                max_features=config.max_features,
                token_pattern=r"(?u)\b\w+\b",
                sublinear_tf=True,
            )
            vectors = vectorizer.fit_transform(selected_texts)
            sims = cosine_similarity(vectors)
        for row_pos, i in enumerate(nonempty):
            for col_pos, j in enumerate(nonempty):
                matrix[i, j] = float(sims[row_pos, col_pos])
    except (ValueError, RuntimeError):
        # Empty vocabulary / unusable embedding is not evidence of a match.
        pass
    return matrix


def _source_platform(record: Mapping[str, Any]) -> str:
    return _safe_str(_first_nonempty(record, ("source_platform", "source"))).casefold()


def _job_identity(record: Mapping[str, Any], index: int) -> str:
    for field in ("job_id_global", "source_job_id", "source_url", "url"):
        value = _safe_str(record.get(field))
        if value:
            return f"{field}:{value}"
    fingerprint_parts = (
        _source_platform(record),
        _safe_str(record.get("job_title")),
        _safe_str(record.get("company_name")),
        _safe_str(record.get("primary_city")),
        _safe_str(record.get("raw_description_text"))[:150],
    )
    payload = "|".join(fingerprint_parts)
    return f"row:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:12]}:{index}"


def _make_cluster_id(identities: Sequence[str]) -> str:
    payload = "\n".join(sorted(identities))
    return "cluster_" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _blocking_values(record: Mapping[str, Any]) -> Tuple[str, str, str]:
    company_value = _first_nonempty(record, ("normalized_company", "company_name", "company"))
    city_value = _first_nonempty(record, ("primary_city", "work_location_city", "standardized_city"))
    family_value = _first_nonempty(record, ("standardized_job_family", "job_family"))
    return (
        normalize_company_name(company_value),
        normalize_city(city_value),
        normalize_job_family(family_value),
    )


def _classify_cluster(source_names: Sequence[str]) -> str:
    counts: Dict[str, int] = defaultdict(int)
    for source in source_names:
        if source:
            counts[source] += 1
    nonempty = set(counts)
    repeated_within_platform = any(count > 1 for count in counts.values())
    if len(nonempty) <= 1:
        return "intra_platform_repost"
    if repeated_within_platform:
        return "mixed_intra_and_cross_platform"
    return "cross_platform_duplicate"


def _build_platform_matrices(
    records: Sequence[Mapping[str, Any]],
    pair_matches: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, float]], Dict[str, int]]:
    platform_counts: Dict[str, int] = {platform: 0 for platform in KNOWN_PLATFORMS}
    for record in records:
        source = _source_platform(record) or "unknown"
        platform_counts[source] = platform_counts.get(source, 0) + 1

    platforms = list(KNOWN_PLATFORMS)
    unknown = sorted(set(platform_counts) - set(platforms))
    platforms.extend(unknown)
    count_matrix = {a: {b: 0 for b in platforms} for a in platforms}
    matched_ids: Dict[Tuple[str, str], Tuple[Set[str], Set[str]]] = {}

    for pair in pair_matches:
        left_source = _safe_str(pair.get("left_source_platform")) or "unknown"
        right_source = _safe_str(pair.get("right_source_platform")) or "unknown"
        if not left_source or not right_source or left_source == right_source:
            continue
        a, b = sorted((left_source, right_source))
        count_matrix.setdefault(a, {}).setdefault(b, 0)
        count_matrix.setdefault(b, {}).setdefault(a, 0)
        count_matrix[a][b] += 1
        count_matrix[b][a] += 1
        left_id = _safe_str(pair.get("left_job_id"))
        right_id = _safe_str(pair.get("right_job_id"))
        key = (a, b)
        if key not in matched_ids:
            matched_ids[key] = (set(), set())
        # Tuple positions follow canonical sorted platform order, not pair direction.
        side_a, side_b = matched_ids[key]
        if left_source == a:
            if left_id:
                side_a.add(left_id)
            if right_id:
                side_b.add(right_id)
        else:
            if right_id:
                side_a.add(right_id)
            if left_id:
                side_b.add(left_id)

    rate_matrix = {a: {b: 0.0 for b in platforms} for a in platforms}
    for (a, b), (ids_a, ids_b) in matched_ids.items():
        total_a, total_b = platform_counts.get(a, 0), platform_counts.get(b, 0)
        # Directional rate: cell A->B means the share of all records on A that
        # have at least one confirmed pair with B. Unlike a symmetric minimum,
        # this shows asymmetry when the two platforms have different dataset sizes.
        rate_matrix[a][b] = round(len(ids_a) / total_a * 100.0, 2) if total_a else 0.0
        rate_matrix[b][a] = round(len(ids_b) / total_b * 100.0, 2) if total_b else 0.0
    return count_matrix, rate_matrix, platform_counts


def link_duplicate_records(
    df: pd.DataFrame,
    config: Optional[LinkageConfig] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Find duplicate jobs while retaining every input row.

    Returns:
        (linked_df, metrics), where linked_df contains all original rows plus
        cluster_id/is_duplicate/duplicate_count/source_platforms/duplicate_type.
        metrics includes matched-pair scores and an 8-platform cross-match matrix.

    Blocking requires non-empty normalized company, primary city and standardized job
    family. Missing key values are reported and left unmatched rather than imputed.
    """
    config = config or LinkageConfig()
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    records = df.to_dict(orient="records")
    n_records = len(records)
    result = df.copy().reset_index(drop=True)
    for column in ("cluster_id", "is_duplicate", "duplicate_count", "source_platforms", "duplicate_type"):
        if column in result.columns:
            # These are outputs of this deterministic run; discard stale values.
            result = result.drop(columns=[column])

    if n_records == 0:
        for column, dtype_value in (
            ("cluster_id", pd.Series(dtype="object")),
            ("is_duplicate", pd.Series(dtype="bool")),
            ("duplicate_count", pd.Series(dtype="int64")),
            ("source_platforms", pd.Series(dtype="object")),
            ("duplicate_type", pd.Series(dtype="object")),
        ):
            result[column] = dtype_value
        empty_matrices = {p: {q: 0 for q in KNOWN_PLATFORMS} for p in KNOWN_PLATFORMS}
        empty_rates = {p: {q: 0.0 for q in KNOWN_PLATFORMS} for p in KNOWN_PLATFORMS}
        return result, {
            "total_input_records": 0,
            "total_clusters": 0,
            "duplicate_cluster_count": 0,
            "duplicate_records_count": 0,
            "pairwise_candidate_count": 0,
            "matched_pair_count": 0,
            "intra_platform_pair_count": 0,
            "cross_platform_pair_count": 0,
            "blocking_missing_records": 0,
            "blocking_missing_details": [],
            "source_counts": {p: 0 for p in KNOWN_PLATFORMS},
            "source_duplicate_records": {p: 0 for p in KNOWN_PLATFORMS},
            "source_intra_platform_duplicate_records": {p: 0 for p in KNOWN_PLATFORMS},
            "source_cross_platform_duplicate_records": {p: 0 for p in KNOWN_PLATFORMS},
            "platform_pair_matrix_counts": empty_matrices,
            "platform_pair_matrix_rate_pct": empty_rates,
            "matched_pairs": [],
            "cluster_sizes": [],
            "config": config.__dict__.copy(),
        }

    semantic_model = _load_local_sentence_transformer(config)
    similarity_backend = "all-MiniLM-L6-v2" if semantic_model is not None else "tfidf_fallback"
    identities = [_job_identity(record, idx) for idx, record in enumerate(records)]
    # Make identity strings unique even if a malformed input repeats a global id.
    seen_identities: Dict[str, int] = defaultdict(int)
    for idx, identity in enumerate(identities):
        seen_identities[identity] += 1
        if seen_identities[identity] > 1:
            identities[idx] = f"{identity}#row{idx}"

    blocks: Dict[Tuple[str, str, str], List[int]] = defaultdict(list)
    blocking_missing_details: List[Dict[str, Any]] = []
    for idx, record in enumerate(records):
        company_key, city_key, family_key = _blocking_values(record)
        if not company_key or not city_key or not family_key:
            missing = []
            if not company_key:
                missing.append("normalized_company")
            if not city_key:
                missing.append("primary_city")
            if not family_key:
                missing.append("standardized_job_family")
            blocking_missing_details.append({"job_id": identities[idx], "missing_keys": missing})
            continue
        blocks[(company_key, city_key, family_key)].append(idx)

    parent = list(range(n_records))
    rank = [0] * n_records

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            return
        if rank[root_left] < rank[root_right]:
            parent[root_left] = root_right
        elif rank[root_left] > rank[root_right]:
            parent[root_right] = root_left
        else:
            parent[root_right] = root_left
            rank[root_left] += 1

    matched_pairs: List[Dict[str, Any]] = []
    candidate_count = 0
    for block_key, indices in blocks.items():
        if len(indices) < 2:
            continue
        candidate_count += len(indices) * (len(indices) - 1) // 2
        block_records = [records[idx] for idx in indices]
        jd_texts = [_record_jd_text(record) for record in block_records]
        skill_texts = [_record_skills_text(record) for record in block_records]
        jd_matrix = _cosine_matrix(jd_texts, config, semantic_model)
        # For skill sets, token/phrase overlap is more interpretable than a sentence
        # embedding; both channels still use cosine similarity and the same threshold.
        skill_matrix = _cosine_matrix(skill_texts, config, None)

        for local_i in range(len(indices)):
            for local_j in range(local_i + 1, len(indices)):
                i, j = indices[local_i], indices[local_j]
                title_i = _first_nonempty(records[i], ("job_title", "title", "job-title"))
                title_j = _first_nonempty(records[j], ("job_title", "title", "job-title"))
                title_sim = jaro_winkler_similarity(title_i, title_j)
                jd_sim = float(jd_matrix[local_i, local_j])
                skill_sim = float(skill_matrix[local_i, local_j])

                # Precision-first rule: title and at least one independent content
                # channel must cross the contracted threshold.
                is_match = (
                    title_sim >= config.title_similarity_threshold
                    and max(jd_sim, skill_sim) >= config.content_cosine_threshold
                )
                if not is_match:
                    continue
                union(i, j)
                left_source, right_source = _source_platform(records[i]), _source_platform(records[j])
                matched_pairs.append({
                    "left_index": i,
                    "right_index": j,
                    "left_job_id": _safe_str(records[i].get("job_id_global")) or identities[i],
                    "right_job_id": _safe_str(records[j].get("job_id_global")) or identities[j],
                    "left_source_platform": left_source,
                    "right_source_platform": right_source,
                    "match_type": "intra_platform_repost" if left_source == right_source else "cross_platform_duplicate",
                    "title_jaro_winkler": round(title_sim, 4),
                    "jd_cosine_similarity": round(jd_sim, 4),
                    "skills_cosine_similarity": round(skill_sim, 4),
                    "blocking_key": {
                        "normalized_company": block_key[0],
                        "primary_city": block_key[1],
                        "standardized_job_family": block_key[2],
                    },
                })

    components: Dict[int, List[int]] = defaultdict(list)
    for idx in range(n_records):
        components[find(idx)].append(idx)
    clusters = list(components.values())
    # Stable output ordering follows first-seen row order.
    clusters.sort(key=lambda group: min(group))

    cluster_sizes: List[int] = []
    duplicate_records_count = 0
    duplicate_cluster_count = 0
    cluster_ids_by_index: Dict[int, str] = {}
    duplicate_by_index: Dict[int, bool] = {}
    count_by_index: Dict[int, int] = {}
    platforms_by_index: Dict[int, List[str]] = {}
    type_by_index: Dict[int, str] = {}

    for members in clusters:
        cluster_id = _make_cluster_id([identities[idx] for idx in members])
        sources = list(dict.fromkeys(_source_platform(records[idx]) for idx in members if _source_platform(records[idx])))
        duplicated = len(members) > 1
        cluster_type = _classify_cluster([_source_platform(records[idx]) for idx in members]) if duplicated else "unique"
        cluster_sizes.append(len(members))
        if duplicated:
            duplicate_cluster_count += 1
            duplicate_records_count += len(members)
        for idx in members:
            cluster_ids_by_index[idx] = cluster_id
            duplicate_by_index[idx] = duplicated
            count_by_index[idx] = len(members)
            platforms_by_index[idx] = sources
            type_by_index[idx] = cluster_type

    result["cluster_id"] = [cluster_ids_by_index[i] for i in range(n_records)]
    result["is_duplicate"] = [duplicate_by_index[i] for i in range(n_records)]
    result["duplicate_count"] = [count_by_index[i] for i in range(n_records)]
    result["source_platforms"] = [platforms_by_index[i] for i in range(n_records)]
    result["duplicate_type"] = [type_by_index[i] for i in range(n_records)]

    intra_pairs = sum(pair["match_type"] == "intra_platform_repost" for pair in matched_pairs)
    cross_pairs = len(matched_pairs) - intra_pairs
    count_matrix, rate_matrix, source_counts = _build_platform_matrices(records, matched_pairs)
    source_duplicate_counts: Dict[str, int] = {source: 0 for source in source_counts}
    for idx, record in enumerate(records):
        if duplicate_by_index[idx]:
            source = _source_platform(record) or "unknown"
            source_duplicate_counts[source] = source_duplicate_counts.get(source, 0) + 1

    intra_member_indices: Set[int] = set()
    cross_member_indices: Set[int] = set()
    for pair in matched_pairs:
        if pair["match_type"] == "intra_platform_repost":
            intra_member_indices.update((int(pair["left_index"]), int(pair["right_index"])))
        elif pair["match_type"] == "cross_platform_duplicate":
            cross_member_indices.update((int(pair["left_index"]), int(pair["right_index"])))
    source_intra_counts: Dict[str, int] = {source: 0 for source in source_counts}
    source_cross_counts: Dict[str, int] = {source: 0 for source in source_counts}
    for idx in intra_member_indices:
        source = _source_platform(records[idx]) or "unknown"
        source_intra_counts[source] = source_intra_counts.get(source, 0) + 1
    for idx in cross_member_indices:
        source = _source_platform(records[idx]) or "unknown"
        source_cross_counts[source] = source_cross_counts.get(source, 0) + 1

    metrics: Dict[str, Any] = {
        "total_input_records": n_records,
        "total_clusters": len(clusters),
        "duplicate_cluster_count": duplicate_cluster_count,
        "duplicate_records_count": duplicate_records_count,
        "pairwise_candidate_count": candidate_count,
        "matched_pair_count": len(matched_pairs),
        "intra_platform_pair_count": intra_pairs,
        "cross_platform_pair_count": cross_pairs,
        "blocking_missing_records": len(blocking_missing_details),
        "blocking_missing_details": blocking_missing_details,
        "source_counts": source_counts,
        "source_duplicate_records": source_duplicate_counts,
        "source_intra_platform_duplicate_records": source_intra_counts,
        "source_cross_platform_duplicate_records": source_cross_counts,
        "platform_pair_matrix_counts": count_matrix,
        "platform_pair_matrix_rate_pct": rate_matrix,
        "matched_pairs": matched_pairs,
        "cluster_sizes": cluster_sizes,
        "similarity_backend": similarity_backend,
        "config": config.__dict__.copy(),
    }
    return result, metrics


def render_deduplication_report(metrics: Mapping[str, Any]) -> str:
    """Render an auditable Markdown report from real ``link_duplicate_records`` metrics."""
    config = metrics.get("config", {})
    sources = list(KNOWN_PLATFORMS)
    source_counts = metrics.get("source_counts", {})
    source_dupes = metrics.get("source_duplicate_records", {})
    source_intra_dupes = metrics.get("source_intra_platform_duplicate_records", {})
    source_cross_dupes = metrics.get("source_cross_platform_duplicate_records", {})
    count_matrix = metrics.get("platform_pair_matrix_counts", {})
    rate_matrix = metrics.get("platform_pair_matrix_rate_pct", {})
    rows = [
        "# Deduplication & Record Linkage Report",
        "",
        "> Phạm vi: khử trùng lặp nội sàn (repost) và xuyên sàn cho 8 nền tảng tuyển dụng.",
        "> Nguyên tắc: đọc EDA trước; không sửa dữ liệu Raw As-Is; không tự suy diễn khóa blocking còn thiếu.",
        "",
        "## 1. Kết quả chạy",
        "",
        f"- Tổng bản ghi đầu vào: **{metrics.get('total_input_records', 'N/A')}**",
        f"- Tổng cụm sau liên kết (bao gồm singleton): **{metrics.get('total_clusters', 'N/A')}**",
        f"- Cụm có trùng lặp: **{metrics.get('duplicate_cluster_count', 'N/A')}**",
        f"- Bản ghi thuộc cụm trùng lặp: **{metrics.get('duplicate_records_count', 'N/A')}**",
        f"- Cặp ứng viên trong cùng block: **{metrics.get('pairwise_candidate_count', 'N/A')}**",
        f"- Cặp được xác nhận: **{metrics.get('matched_pair_count', 'N/A')}**",
        f"- Cặp nội sàn: **{metrics.get('intra_platform_pair_count', 'N/A')}**",
        f"- Cặp xuyên sàn: **{metrics.get('cross_platform_pair_count', 'N/A')}**",
        f"- Bản ghi thiếu khóa Blocking nên không tự động ghép: **{metrics.get('blocking_missing_records', 'N/A')}**",
        f"- Backend JD cosine: **{metrics.get('similarity_backend', 'N/A')}**",
        "",
        "## 2. Evidence từ EDA — Trụ cột 3 (Uniqueness & Duplication)",
        "",
        "| Sàn | Kết luận EDA liên quan đến trùng lặp | Hệ quả thiết kế |",
        "|---|---|---|",
        "| CareerViet | EDA báo cáo 0% trùng vật lý và 0% trùng `job_id`; trùng lặp logic theo `title + company + map` khoảng 10,4%. Cảnh báo các đợt tuyển nhiều vị trí có thể cùng tiêu đề. | Không gộp chỉ dựa trên công ty/tiêu đề/địa điểm; cần xác nhận nội dung JD hoặc skills. |",
        "| Glints | EDA mô tả trùng khóa ID gần 0 nhờ SHA-256/URL Ledger; logic duplicate có thể do tuyển nhiều slot hoặc đăng lại theo chu kỳ khoảng 14 ngày. | Phân biệt ID/URL trùng vật lý với trùng logic; giữ dấu vết nguồn và thời gian. |",
        "| ITviec | EDA mô tả trùng khóa ID gần 0; cùng công ty có thể tuyển nhiều slot hoặc đăng lại theo chu kỳ khoảng 14 ngày. | Yêu cầu so khớp tiêu đề cùng nội dung/skills, không dùng title-only. |",
        "| JobsGO | EDA mô tả trùng khóa ID gần 0; có thể xuất hiện nhiều slot hoặc repost theo chu kỳ khoảng 14 ngày. | Áp dụng ngưỡng bảo thủ và giữ mọi member record trong JSON provenance. |",
        "| TopCV | EDA mô tả trùng khóa ID gần 0; logic duplicate có thể do nhiều slot hoặc repost theo chu kỳ khoảng 14 ngày. | Không gộp khi thiếu một trong 3 khóa Blocking hoặc thiếu chứng cứ nội dung. |",
        "| TopDev | EDA mô tả trùng khóa ID gần 0; logic duplicate có thể do nhiều slot hoặc repost theo chu kỳ khoảng 14 ngày. | So sánh JD và kỹ năng sau bước chuẩn hóa. |",
        "| Vieclam24h | EDA mô tả trùng khóa ID gần 0; logic duplicate có thể do nhiều slot hoặc repost theo chu kỳ khoảng 14 ngày. | Chuẩn hóa cùng một cách các khóa company/city/family; không sửa dữ liệu thô. |",
        "| VietnamWorks | EDA mô tả trùng khóa ID gần 0; logic duplicate có thể do nhiều slot hoặc repost theo chu kỳ khoảng 14 ngày. | Không dùng salary hoặc trường missing làm căn cứ độc lập để gộp. |",
        "",
        "## 2.1. Chất lượng trường dùng để matching (đối chiếu EDA các trụ cột còn lại)",
        "",
        "| Nguồn | Phát hiện EDA liên quan đến khóa/nội dung | Kiểm soát trong module |",
        "|---|---|---|",
        "| CareerViet | Trường địa chỉ văn phòng chi tiết thiếu khoảng 34,2%; 13 mẫu không có `detail-box`. | Blocking chỉ dùng `primary_city` đã chuẩn hóa; thiếu khóa thì không tự suy diễn. |",
        "| TopDev | `skills_arr` rỗng khoảng 55,7% theo EDA; kỹ năng có thể cần lấy từ trường đã chuẩn hóa khác. | Kênh skills rỗng không là bằng chứng trùng; JD vẫn có thể là kênh nội dung. |",
        "| Vieclam24h | Trường tag kỹ năng cấu trúc rỗng 100%; EDA cảnh báo `keywords` có thể chứa địa danh. | Không tự bù kỹ năng ở bước dedup; chỉ dùng skills đầu vào đã chuẩn hóa cùng JD. |",
        "| ITviec | EDA ghi nhận khoảng 74,7% mức lương hiển thị UI bị ẩn. | Lương không phải đặc trưng matching; chỉ dùng sau đó cho survivorship khi trường số đáng tin cậy. |",
        "| VietnamWorks | EDA ghi nhận khoảng 70,5% tin ẩn lương có thể biểu diễn salary min/max bằng 0. | Không dùng salary hoặc số 0 giả làm tín hiệu để ghép. |",
        "| Glints | EDA lưu ý lương UI có thể ẩn nhưng JSON-LD còn trường dữ liệu; xử lý lương thuộc Transformation. | Không parse hoặc suy luận lương trong module linkage. |",
        "| JobsGO / TopCV | EDA nhấn mạnh bảo toàn dữ liệu thô và chuẩn hóa riêng trong các bước tiền xử lý trước. | Module không ghi đè title/JD/skills đầu vào, chỉ thêm kết quả linkage. |",
        "",
        "## 3. Quy tắc Matching đã áp dụng",
        "",
        "1. **Blocking** chính xác theo `(normalized_company, primary_city, standardized_job_family)`. Nếu thiếu một khóa, bản ghi được giữ riêng và tính vào báo cáo thiếu khóa.",
        f"2. **Title matching:** Jaro-Winkler ≥ `{config.get('title_similarity_threshold', 0.88)}`.",
        f"3. **Content matching:** Jaro-Winkler đạt ngưỡng và ít nhất một kênh độc lập (JD hoặc skills) có Cosine Similarity ≥ `{config.get('content_cosine_threshold', 0.88)}`. Backend JD thực tế: `{metrics.get('similarity_backend', 'N/A')}`; kênh skills dùng TF-IDF Cosine.",
        "4. Mỗi cặp đạt điều kiện được nối vào graph; các connected components nhận `cluster_id` ổn định. Module này giữ lại mọi dòng đầu vào; việc tạo một dòng Golden Record/cụm thực hiện ở `golden_record_resolver.py`.",
        "",
        "## 4. Ma trận trùng chéo 8 sàn",
        "",
        "Ô **count** là số cặp đã xác nhận giữa hai sàn (đối xứng). Ô **rate** là tỷ lệ đối xứng: giá trị nhỏ hơn giữa tỷ lệ bản ghi đã liên kết của từng sàn trong cặp; mẫu số là tổng bản ghi của từng sàn. Ma trận được tính trên dữ liệu truyền vào hàm, không phải ước lượng từ EDA.",
        "",
        "### 4.1 Số cặp xuyên sàn",
        "",
        "| Sàn | " + " | ".join(sources) + " |",
        "|---|" + "|".join(["---:"] * len(sources)) + "|",
    ]
    for a in sources:
        cell_values = [str(count_matrix.get(a, {}).get(b, 0)) for b in sources]
        rows.append("| " + a + " | " + " | ".join(cell_values) + " |")

    rows.extend(["", "### 4.2 Tỷ lệ trùng chéo (%)", "", "| Sàn | " + " | ".join(sources) + " |", "|---|" + "|".join(["---:"] * len(sources)) + "|"])
    for a in sources:
        cell_values = [f"{rate_matrix.get(a, {}).get(b, 0.0):.2f}" for b in sources]
        rows.append("| " + a + " | " + " | ".join(cell_values) + " |")

    rows.extend([
        "",
        "## 5. Repost nội sàn theo nguồn",
        "",
        "| Sàn | Bản ghi đầu vào | Bản ghi tham gia cặp nội sàn | Tỷ lệ nội sàn (%) | Bản ghi tham gia cặp xuyên sàn | Bản ghi thuộc mọi cluster duplicate |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for source in sources:
        total = int(source_counts.get(source, 0))
        intra_dupes = int(source_intra_dupes.get(source, 0))
        cross_dupes = int(source_cross_dupes.get(source, 0))
        any_dupes = int(source_dupes.get(source, 0))
        rate = (intra_dupes / total * 100.0) if total else 0.0
        rows.append(f"| {source} | {total} | {intra_dupes} | {rate:.2f} | {cross_dupes} | {any_dupes} |")

    rows.extend([
        "",
        "## 6. Giới hạn và kiểm soát chất lượng",
        "",
        "- EDA chỉ nêu dấu hiệu và giả thuyết về trùng lặp; các tỷ lệ trong phần kết quả phải đến từ lần chạy thực tế trên bảng đã chuẩn hóa.",
        "- Ngưỡng 0,88 là đặc tả ban đầu, không tự động chứng minh Precision ≥ 90%; cần đánh giá cặp đúng/sai trên bộ mẫu được gán nhãn.",
        "- Cặp không nằm cùng block sẽ không được so sánh ở phiên bản này; cần theo dõi tỷ lệ thiếu khóa để tránh che khuất false negatives.",
        "- Golden Record lưu toàn bộ bản ghi thành viên trong `duplicate_member_records_json` để truy xuất và audit; kỹ năng/quyền lợi được hợp nhất theo thứ tự ổn định.",
        "",
    ])
    return "\n".join(rows)
