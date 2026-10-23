"""tests/unit/test_careerviet_report_fill.py — Kiem thu `scripts/careerviet_report_fill.py`.

An toan: tmp_path, **CHI DOC**, khong goi mang, khong ghi de ledger/envelope that.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import careerviet_report_fill as rf  # noqa: E402


# ==== helpers ====
def _mk_env(root: Path, date: str, jid: str, ver: int = 1,
            payload: dict | None = None, dt_prefix: bool = False) -> Path:
    folder = f"dt={date}" if dt_prefix else date
    d = root / folder
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{jid}_v{ver}.json"
    env = {
        "metadata": {"job_id": jid, "source": "careerviet",
                     "source_category": "c1", "version": str(ver)},
        "raw_payload": payload or {},
    }
    p.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")
    return p


def _mk_catalog(root: Path, records: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    p = root / "catalog_master.json"
    p.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return p


# ==== scan_envelopes ====
def test_scan_accepts_bare_and_dt_prefix(tmp_path):
    _mk_env(tmp_path, "2026-10-16", "AAA11111")
    _mk_env(tmp_path, "2026-10-17", "BBB22222", dt_prefix=True)
    envs = rf.scan_envelopes(tmp_path)
    assert len(envs) == 2
    dates = sorted(e["date"] for e in envs)
    assert dates == ["2026-10-16", "2026-10-17"]
    jids = sorted(e["job_id"] for e in envs)
    assert jids == ["AAA11111", "BBB22222"]


def test_scan_skips_non_envelope_files(tmp_path):
    _mk_env(tmp_path, "2026-10-16", "GOOD0001")
    # File khong dung dinh dang _v<N>.json -> bo qua
    (tmp_path / "2026-10-16" / "readme.json").write_text("{}", encoding="utf-8")
    (tmp_path / "2026-10-16" / "no_version.json").write_text("{}", encoding="utf-8")
    # File hong (JSON parse loi) -> bo qua, khong crash
    (tmp_path / "2026-10-16" / "BAD00001_v1.json").write_text("{not-json}", encoding="utf-8")
    envs = rf.scan_envelopes(tmp_path)
    jids = {e["job_id"] for e in envs}
    assert "GOOD0001" in jids
    assert "BAD00001" not in jids
    assert len(envs) == 1


def test_scan_missing_dir_returns_empty(tmp_path):
    assert rf.scan_envelopes(tmp_path / "does_not_exist") == []


# ==== load_catalog ====
def test_load_catalog_missing(tmp_path):
    assert rf.load_catalog(tmp_path) == {}


def test_load_catalog_ok(tmp_path):
    _mk_catalog(tmp_path, {
        "h1": {"status": "DONE", "latest_version": 1},
        "h2": {"status": "PENDING"},
    })
    c = rf.load_catalog(tmp_path)
    assert len(c) == 2


# ==== status_counts ====
def test_status_counts(tmp_path):
    _mk_catalog(tmp_path, {
        "h1": {"status": "PENDING"},
        "h2": {"status": "PENDING"},
        "h3": {"status": "DONE"},
        "h4": {"status": "FAILED"},
    })
    c = rf.status_counts(rf.load_catalog(tmp_path))
    assert c == {"PENDING": 2, "DONE": 1, "FAILED": 1}


# ==== null_rate ====
def test_null_rate_empty_list_and_missing_key(tmp_path):
    envs = rf.scan_envelopes(tmp_path)  # khong co gi -> {}
    assert rf.null_rate_by_key(envs) == {
        k: (0, 0, 0.0) for k in rf.PAYLOAD_KEYS
    }


def test_null_rate_job_tags(tmp_path):
    _mk_env(tmp_path, "2026-10-16", "AAA11111", payload={
        "title": "x", "job-tags": ["Python"],
    })
    _mk_env(tmp_path, "2026-10-16", "BBB22222", payload={
        "title": "y", "job-tags": [],   # empty list = null
    })
    _mk_env(tmp_path, "2026-10-16", "CCC33333", payload={
        "title": "z",  # job-tags thuu thien = null
    })
    envs = rf.scan_envelopes(tmp_path)
    nr = rf.null_rate_by_key(envs)
    assert nr["job-tags"] == (2, 3, pytest.approx(66.7, abs=0.1))
    # title: 0 null
    assert nr["title"] == (0, 3, 0.0)


# ==== it_ratio ====
def test_it_ratio_counts_nganh_nghe_not_source_category(tmp_path):
    # 3 tin: 2 co CNTT, 1 khong (van co source_category='keyword:developer')
    _mk_env(tmp_path, "2026-10-16", "AAA11111", payload={
        "Ngành nghề": ["CNTT - Phần mềm"],
    })
    _mk_env(tmp_path, "2026-10-16", "BBB22222", payload={
        "Ngành nghề": ["Kế toán"],
    })
    _mk_env(tmp_path, "2026-10-16", "CCC33333", payload={
        "Ngành nghề": ["CNTT - Phần cứng / Mạng"],
    })
    envs = rf.scan_envelopes(tmp_path)
    ir = rf.it_ratio(envs)
    assert ir["it_count"] == 2
    assert ir["non_it_count"] == 1
    assert ir["total"] == 3
    assert ir["it_percent"] == pytest.approx(66.7, abs=0.1)


def test_it_ratio_empty(tmp_path):
    ir = rf.it_ratio([])
    assert ir["total"] == 0 and ir["it_count"] == 0 and ir["it_percent"] == 0.0


# ==== cdc_from_ledger ====
def test_cdc_from_ledger(tmp_path):
    _mk_catalog(tmp_path, {
        "h1": {"status": "DONE", "latest_version": 1},
        "h2": {"status": "DONE", "latest_version": 3},
        "h3": {"status": "DONE", "latest_version": 1, "repost_of_url_hash": "h9"},
        "h4": {"status": "CLOSED"},
        "h5": {"status": "PENDING"},
        "h6": {"status": "FAILED"},
    })
    c = rf.cdc_from_ledger(rf.load_catalog(tmp_path))
    assert c["NEW"] == 1       # h1 (h3 repost tinh rieng)
    assert c["UPDATED"] == 1   # h2
    assert c["REPOST"] == 1    # h3
    assert c["CLOSED"] == 1
    assert c["PENDING"] == 1
    assert c["FAILED"] == 1


# ==== top_tags / top_locations ====
def test_top_tags_and_locations(tmp_path):
    _mk_env(tmp_path, "2026-10-16", "AAA11111", payload={
        "job-tags": ["Python", "Django"], "map": "Hà Nội, Hồ Chí Minh",
    })
    _mk_env(tmp_path, "2026-10-16", "BBB22222", payload={
        "job-tags": ["Python"], "map": "Đà Nẵng",
    })
    envs = rf.scan_envelopes(tmp_path)
    tt = dict(rf.top_tags(envs))
    assert tt["Python"] == 2 and tt["Django"] == 1
    tl = dict(rf.top_locations(envs))
    assert tl["Hà Nội"] == 1 and tl["Hồ Chí Minh"] == 1 and tl["Đà Nẵng"] == 1


# ==== build_report + main end-to-end ====
def test_build_report_smoke(tmp_path):
    raw = tmp_path / "raw"
    _mk_env(raw, "2026-10-16", "AAA11111", payload={
        "title": "x", "Ngành nghề": ["CNTT - Phần mềm"],
        "job-tags": ["Python"], "map": "Hà Nội",
    })
    ledger = tmp_path / "ledger"
    _mk_catalog(ledger, {"h1": {"status": "DONE", "latest_version": 1}})
    args = rf.build_parser().parse_args([
        "--raw-dir", str(raw), "--ledger-dir", str(ledger),
    ])
    r = rf.build_report(args)
    assert r["envelope_count"] == 1
    assert r["ledger_records"] == 1
    assert r["it_ratio"]["it_count"] == 1
    assert r["cdc_from_ledger"]["NEW"] == 1
    assert r["top_tags"][0] == ("Python", 1)


def test_main_json_output_captures_stats(tmp_path, capsys):
    raw = tmp_path / "raw"
    _mk_env(raw, "2026-10-16", "AAA11111", payload={"Ngành nghề": ["CNTT"]})
    ledger = tmp_path / "ledger"
    _mk_catalog(ledger, {"h1": {"status": "PENDING"}})
    rc = rf.main([
        "--raw-dir", str(raw), "--ledger-dir", str(ledger), "--json",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["envelope_count"] == 1
    assert parsed["status_distribution"] == {"PENDING": 1}


def test_main_human_output_has_no_cjk(tmp_path, capsys):
    raw = tmp_path / "raw"
    _mk_env(raw, "2026-10-16", "AAA11111", payload={"title": "ok"})
    ledger = tmp_path / "ledger"
    _mk_catalog(ledger, {"h1": {"status": "PENDING"}})
    rf.main(["--raw-dir", str(raw), "--ledger-dir", str(ledger)])
    out = capsys.readouterr().out
    import re
    cjk = re.findall(
        r"[\u3040-\u30ff\u31f0-\u31ff\uac00-\ud7af\u4e00-\u9fff"
        r"\uff66-\uff9f\u3000-\u303f]",
        out,
    )
    assert not cjk, f"Phat hien CJK trong stdout: {cjk[:5]}"


# ==== Khong co envelope -> in ra "CHUA CO" ====
def test_no_envelope_hint(tmp_path, capsys):
    rc = rf.main([
        "--raw-dir", str(tmp_path / "not_here"),
        "--ledger-dir", str(tmp_path / "nope"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CHUA CO ENVELOPE" in out
