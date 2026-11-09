"""Candidate-only strict lookup; fixtures are logic cases, not reported job data."""

import json

import numpy as np
import pytest

from preprocessing.encoding.candidate_lookup import (
    build_candidate_lookup,
    encode_candidate_rows,
    load_candidate_lookup,
)
from preprocessing.encoding.prepare_approval_package_v2 import CANONICAL_CHECKS


@pytest.mark.parametrize("canonical", CANONICAL_CHECKS)
def test_canonical_matches_when_absent_from_aliases(canonical):
    lookup = build_candidate_lookup([dict(canonical=canonical, aliases=["other explicit name"])])
    result = encode_candidate_rows([[canonical.swapcase()]], lookup)
    assert result.matrix.tolist() == [[1]]
    assert result.unmatched == (frozenset(),)


def test_alias_union_bits_and_counts_use_same_owner():
    lookup = build_candidate_lookup([dict(canonical="Go", aliases=["Golang", "GO", "Golang"])])
    encoded = encode_candidate_rows([["Go", "GOLANG", "Go"], ["golang"], ["unknown", "UNKNOWN"]], lookup)
    assert encoded.matrix.tolist() == [[1], [1], [0]]
    assert encoded.matrix.sum(axis=0).tolist() == [2]
    assert [len(values) for values in encoded.unmatched] == [0, 0, 1]
    assert len(lookup.owners) == 2


def test_unicode_casefold_is_used():
    lookup = build_candidate_lookup([dict(canonical="Straße", aliases=[])])
    assert encode_candidate_rows([["STRASSE"]], lookup).matrix.tolist() == [[1]]


def test_alias_collision_between_owners_fails():
    with pytest.raises(ValueError, match="Alias collision"):
        build_candidate_lookup([dict(canonical="A", aliases=["Shared"]), dict(canonical="B", aliases=["SHARED"])])


def test_slug_collision_between_owners_fails():
    with pytest.raises(ValueError, match="Slug collision"):
        build_candidate_lookup([dict(canonical="Data-Quality"), dict(canonical="Data Quality")])


def test_c_cpp_csharp_and_dotnet_keep_punctuation():
    lookup = build_candidate_lookup([dict(canonical=name) for name in ["C", "C++", "C#", ".NET"]])
    assert lookup.columns == ("skill_c", "skill_cpp", "skill_csharp", "skill_dotnet")
    result = encode_candidate_rows([["C"], ["C++"], ["C#"], [".net"], ["cpp", "csharp", "dotnet", "C/C++"]], lookup)
    np.testing.assert_array_equal(result.matrix[:4], np.eye(4, dtype=np.uint8))
    assert result.matrix[4].sum() == 0
    assert len(result.unmatched[4]) == 4


def test_no_parent_substring_or_fuzzy_propagation():
    lookup = build_candidate_lookup([dict(canonical=name) for name in ["AWS", "AWS Lambda", "TensorFlow", "TensorFlow Serving"]])
    result = encode_candidate_rows([["AWS Lambda", "TensorFlow Serving", "AWS developer", "Tensor Flow"]], lookup)
    assert result.matrix.tolist() == [[0, 1, 0, 1]]
    assert len(result.unmatched[0]) == 2


def test_null_empty_and_unmatched_are_distinct():
    lookup = build_candidate_lookup([dict(canonical="Python")])
    result = encode_candidate_rows([None, [], ["outside"], ["Python"]], lookup)
    assert result.missing == (True, False, False, False)
    assert result.matrix.tolist() == [[0], [0], [0], [1]]
    assert [len(row) for row in result.unmatched] == [0, 0, 1, 0]


@pytest.mark.parametrize("values", ["Python", {"Python": 1}, [None], [1]])
def test_malformed_skill_collection_fails(values):
    with pytest.raises(ValueError):
        encode_candidate_rows([values], build_candidate_lookup([dict(canonical="Python")]))


def test_json_loader_preserves_order_and_requires_width(tmp_path):
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(dict(status="proposed_not_production", items=[
        dict(canonical="Java", aliases=[], index=0, column="skill_java"),
        dict(canonical="Python", aliases=[], index=1, column="skill_python"),
    ])))
    lookup = load_candidate_lookup(path, expected_count=2)
    assert lookup.canonical == ("Java", "Python")
    with pytest.raises(ValueError, match="Expected 230"):
        load_candidate_lookup(path, expected_count=230)


def test_explicit_missing_index_and_column_are_rejected():
    with pytest.raises(ValueError, match="index/column"):
        build_candidate_lookup([dict(canonical="Python", index=1)])
    with pytest.raises(ValueError, match="index/column"):
        build_candidate_lookup([dict(canonical="Python", column="skill_wrong")])


def test_empty_or_duplicate_canonical_fails():
    with pytest.raises(ValueError):
        build_candidate_lookup([dict(canonical="")])
    with pytest.raises(ValueError):
        build_candidate_lookup([dict(canonical="Python"), dict(canonical="python")])
