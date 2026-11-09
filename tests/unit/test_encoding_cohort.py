"""Ledger invariants and legacy-entrypoint overwrite regressions, offline."""

import importlib

import pandas as pd
import pytest

from preprocessing.encoding.cohort import validate_approved_ids, validate_ledger


def ledger():
    return pd.DataFrame(dict(job_id_global=["a", "b", "c"], disposition=["include", "exclude", "quarantine"],
        review_status=["retained_unreviewed", "excluded_by_approved_policy", "unresolved_quarantined"],
        reason=["not_flagged_by_targeted_rules", "explicit approved exclusion", "insufficient evidence"],
        evidence_reference=["source#a", "source#b", "source#c"], decision_reference=["decision#1"]*3))


def test_complete_disjoint_ledger_in_original_order():
    assert validate_ledger(["a", "b", "c"], ledger()) == {"include": 1, "exclude": 1, "quarantine": 1}
    with pytest.raises(ValueError, match="exactly once"):
        validate_ledger(["a", "b", "c"], ledger().iloc[::-1])
    with pytest.raises(ValueError, match="exactly once"):
        validate_ledger(["a", "b", "c"], pd.concat([ledger(), ledger().iloc[:1]]))


def test_unreviewed_cannot_be_claimed_excluded_or_verified():
    rows = ledger()
    rows.loc[0, "disposition"] = "exclude"
    with pytest.raises(ValueError, match="contradicts"):
        validate_ledger(["a", "b", "c"], rows)
    rows = ledger()
    rows.loc[0, "review_status"] = "verified_IT"
    with pytest.raises(ValueError, match="Invalid"):
        validate_ledger(["a", "b", "c"], rows)


def test_approved_retained_ids_cannot_be_excluded():
    rows = ledger()
    approved = pd.DataFrame(dict(job_id_global=["a", "b"], proposed_decision=["retain_proposed", "exclude_proposed"]))
    validate_approved_ids(rows, approved)
    rows.loc[0, "disposition"] = "quarantine"
    with pytest.raises(ValueError, match="approved"):
        validate_approved_ids(rows, approved)


def test_legacy_module_cannot_write_a_prototype_bundle(tmp_path, monkeypatch):
    old = importlib.import_module("preprocessing.encoding.run")
    sentinel = tmp_path / "features.parquet"
    sentinel.write_bytes(b"approved-cohort-bundle")
    monkeypatch.setattr(old, "OUT_FEATURES_FILE", sentinel)
    for dry_run in [True, False]:
        with pytest.raises(ValueError, match="Legacy P5 writer is disabled"):
            old.run(dry_run=dry_run)
    assert sentinel.read_bytes() == b"approved-cohort-bundle"


def test_legacy_apply_cli_fails_before_delegate(tmp_path, monkeypatch):
    cli = importlib.import_module("preprocessing.encoding.run_encoding")
    runner = importlib.import_module("preprocessing.encoding.execute")
    monkeypatch.setattr(runner, "main", lambda args: pytest.fail("prototype mode must not delegate"))
    assert cli.main(["--apply"]) == 1
    assert cli.main(["--source", "all", "--apply"]) == 1


def test_explicit_cli_delegates_to_only_full_implementation(monkeypatch):
    cli = importlib.import_module("preprocessing.encoding.run_encoding")
    runner = importlib.import_module("preprocessing.encoding.execute")
    calls = []
    monkeypatch.setattr(runner, "main", lambda args: calls.append(args) or 0)
    args = ["--input-manifest", "fixture.json", "--cohort-ledger", "ledger.csv", "--dry-run"]
    assert cli.main(args) == 0 and calls == [args]
