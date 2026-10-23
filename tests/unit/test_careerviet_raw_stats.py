# -*- coding: utf-8 -*-
"""Unit test cho scripts/careerviet_raw_stats.py (ban envelope moi).

Dung tmp_path + pathlib, KHONG phu thuoc data/ cuc bo, khong goi mang.
"""

import importlib.util
import json
from pathlib import Path

# Script khong nam trong goi import duoc -> nap bang duong dan file.
_SPEC = importlib.util.spec_from_file_location(
    "careerviet_raw_stats",
    Path(__file__).resolve().parents[2] / "scripts" / "careerviet_raw_stats.py",
)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _env(job_id, *, version=1, title="T", company="C", detail_box=None,
         detail_row=None, job_tags=None, map_=None, nganh=None, jsonld=None):
    return {
        "metadata": {"job_id": job_id, "version": version, "source": "careerviet"},
        "raw_payload": {
            "title": title,
            "job-company-name": company,
            "detail-box": detail_box if detail_box is not None else ["Luong: x"],
            "detail-row": detail_row if detail_row is not None else {"Mo ta": "abc"},
            "job-tags": job_tags if job_tags is not None else ["Python"],
            "map": map_,
            "Ngành nghề": nganh,
            "job-posting-schema": jsonld,
        },
    }


def _write_env(raw_dir: Path, job_id, envelope, version=1):
    d = raw_dir / "2026-10-16"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{job_id}_v{version}.json").write_text(
        json.dumps(envelope, ensure_ascii=False), encoding="utf-8"
    )


def test_is_empty_rules():
    assert mod.is_empty(None)
    assert mod.is_empty("")
    assert mod.is_empty("   ")
    assert mod.is_empty([])
    assert mod.is_empty({})
    assert not mod.is_empty("x")
    assert not mod.is_empty(["a"])
    assert not mod.is_empty({"k": 1})
    assert not mod.is_empty(0)  # so 0 khong tinh la rong


def test_run_counts_missing_rate_and_versions(tmp_path):
    raw = tmp_path / "raw"
    _write_env(raw, "AAAA", _env("AAAA", map_="HN", nganh=["CNTT"],
                                 jsonld={"@type": "JobPosting"}))
    #rong map, nganh, jsonld; version 2
    _write_env(raw, "BBBB", _env("BBBB", version=2, map_=None, nganh=None, jsonld=None), version=2)
    # job-tags rong, title rong
    _write_env(raw, "CCCC", _env("CCCC", title="", job_tags=[]), )

    report, stats = mod.run(raw)

    assert stats["total_envelopes"] == 3
    # map rong o BBBB+CCCC = 2/3
    assert stats["empty_counts"]["map"] == 2
    assert abs(stats["missing_rate"]["map"] - 2 / 3) < 1e-9
    # title rong o CCCC = 1
    assert stats["empty_counts"]["title"] == 1
    # job-tags rong o CCCC = 1
    assert stats["empty_counts"]["job-tags"] == 1
    # chi 1 tin co JSON-LD
    assert stats["jsonld_present"] == 1
    assert stats["jsonld_missing"] == 2
    # phan bo version 1->2, 2->1
    assert stats["version_distribution"] == {1: 2, 2: 1}
    # bao cao la chuoi co chua tieu de
    assert "tong_so_envelope = 3" in report


def test_non_envelope_files_are_skipped(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "checkpoint.json").write_text(
        json.dumps({"last_url": "x"}), encoding="utf-8"
    )
    _write_env(raw, "AAAA", _env("AAAA"))

    report, stats = mod.run(raw)

    assert stats["total_envelopes"] == 1
    assert "so_file_bo_qua_khong_phai_envelope = 1" in report
    assert "checkpoint.json" in report


def test_empty_dir_returns_zero(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    report, stats = mod.run(raw)
    assert stats["total_envelopes"] == 0
    assert stats["missing_rate"]["map"] == 0.0
    assert "tong_so_envelope = 0" in report
