# -*- coding: utf-8 -*-
"""Unit test cho scripts/careerviet_it_check.py (kiem ke CNTT, chi doc envelope).

Dung tmp_path + pathlib, KHONG phu thuoc data/ cuc bo, khong goi mang.
"""

import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "careerviet_it_check",
    Path(__file__).resolve().parents[2] / "scripts" / "careerviet_it_check.py",
)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write_env(path: Path, job_id, industry, *, version=1, category="c37_digital_mkt",
               title="Job"):
    path.mkdir(parents=True, exist_ok=True)
    obj = {
        "metadata": {"job_id": job_id, "version": version, "source": "careerviet",
                     "source_category": category},
        "raw_payload": {"title": title, "Ngành nghề": industry},
    }
    (path / f"{job_id}_v{version}.json").write_text(
        json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def test_detects_cntt_and_counts(tmp_path):
    raw = tmp_path / "2026-10-16"
    _write_env(raw, "AAAA01", ["CNTT - Phần mềm"])          # CO
    _write_env(raw, "AAAA02", ["Marketing"])                # KHONG
    _write_env(raw, "AAAA03", None)                         # KHONG (rong)
    _write_env(raw, "AAAA04", ["Kinh nghiệm", "CNTT"])      # CO (co CNTT trong list)

    rows, skipped = mod.collect_latest(str(tmp_path), date="2026-10-16")
    by = {r["job_id"]: r for r in rows}
    assert by["AAAA01"]["has_it"] is True
    assert by["AAAA02"]["has_it"] is False
    assert by["AAAA03"]["has_it"] is False
    assert by["AAAA04"]["has_it"] is True
    assert sum(r["has_it"] for r in rows) == 2
    assert len(rows) == 4 and skipped == []


def test_picks_latest_version_per_job(tmp_path):
    raw = tmp_path / "d"
    _write_env(raw, "BBBB01", ["Marketing"], version=1)
    _write_env(raw, "BBBB01", ["CNTT - Phần mềm"], version=2)
    rows, _ = mod.collect_latest(str(tmp_path), date="d")
    assert len(rows) == 1
    assert rows[0]["version"] == 2 and rows[0]["has_it"] is True


def test_filter_by_category(tmp_path):
    raw = tmp_path / "d"
    _write_env(raw, "C1JOB", ["CNTT - Phần mềm"], category="c1")
    _write_env(raw, "C37JOB", ["CNTT - Phần mềm"], category="c37_digital_mkt")
    rows, _ = mod.collect_latest(str(tmp_path), date="d", category="c37_digital_mkt")
    assert [r["job_id"] for r in rows] == ["C37JOB"]


def test_non_envelope_skipped(tmp_path):
    raw = tmp_path / "d"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "junk.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    _write_env(raw, "GOOD01", ["CNTT - Phần mềm"])
    rows, skipped = mod.collect_latest(str(tmp_path), date="d")
    assert [r["job_id"] for r in rows] == ["GOOD01"]
    assert len(skipped) == 1


def test_main_prints_total(capsys, tmp_path):
    raw = tmp_path / "d"
    _write_env(raw, "AAAA01", ["CNTT - Phần mềm"])
    _write_env(raw, "AAAA02", ["Marketing"])
    rc = mod.main(["--raw-dir", str(tmp_path), "--date", "d"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "TONG so tin co CNTT / tong so envelope: 1 / 2" in out
