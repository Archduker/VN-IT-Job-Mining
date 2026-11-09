"""Review-only mapping tests; tiny fixtures are not reported as observed jobs."""

import pytest

from preprocessing.encoding import prepare_approval_package as package


def test_alias_frequency_is_union_of_jobs(monkeypatch):
    monkeypatch.setattr(package, "PROPOSED_RULES", {"test": "Go=Golang"})
    definitions, owners = package.make_proposal([{"Go", "Golang"}, {"Golang"}, set()])
    assert len(definitions) == 1
    assert definitions[0]["jobs"] == 2
    assert definitions[0]["decision"] == ""
    assert definitions[0]["status"] == "proposed"
    assert owners == {"Go": "Go", "Golang": "Go"}


def test_never_adds_unobserved_names(monkeypatch):
    monkeypatch.setattr(package, "PROPOSED_RULES", {"test": "Python\nUnseen"})
    definitions, _ = package.make_proposal([{"Python"}, {"Unknown metadata"}])
    assert [item["canonical"] for item in definitions] == ["Python"]
    assert package.make_proposal([set()]) == ([], {})


def test_alias_collision_fails(monkeypatch):
    monkeypatch.setattr(package, "PROPOSED_RULES", {"test": "A=shared\nB=shared"})
    with pytest.raises(ValueError, match="collision"):
        package.make_proposal([{"shared"}])


def test_case_variants_and_tie_order_are_deterministic(monkeypatch):
    monkeypatch.setattr(package, "PROPOSED_RULES", {"test": "Zulu\nPython"})
    definitions, _ = package.make_proposal([{"python", "Python", "Zulu"}])
    assert [(item["canonical"], item["jobs"]) for item in definitions] == [
        ("Python", 1), ("Zulu", 1)
    ]
