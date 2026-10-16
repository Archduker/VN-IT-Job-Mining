"""tests/unit/test_push_raw_to_minio.py — Kiem thu `scripts/push_raw_to_minio.py`.

An toan: **tmp_path** + **mock boto3**, khong ket noi MinIO that, khong goi mang.
Bao phu 5 hanh vi thiet ke (docs/crawl/careerviet.md §13.2–§13.4):

1. `--dry-run` khong upload, khong import boto3.
2. `--no-clobber` (mac dinh): `head_object` OK -> `SKIPPED_EXISTS`, khong `put`.
3. `--overwrite` buoc `put` du key da ton tai.
4. `--job-id` loc dung danh sach `<jid>_v<n>.json`.
5. **Password va AK nguyen van khong xuat hien** trong log/caplog (test `--verbose`).
6. **Anh xa key**: `raw/dt=<date>/...` **va** `raw/<date>/...` -> `<prefix>/<date>/...`
   (script luon loai bo `dt=` khi sinh S3 key).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# dua scripts/ vao sys.path de import push_raw_to_minio
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import push_raw_to_minio as prm  # noqa: E402


# ==== helpers ====
def _make_env(root: Path, date: str, jid: str, ver: int = 1,
              dt_prefix: bool = False) -> Path:
    """Tao envelope gia: `root/raw/dt=<date>/<jid>_v<ver>.json` hoac bare."""
    folder = f"dt={date}" if dt_prefix else date
    d = root / "raw" / folder
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{jid}_v{ver}.json"
    p.write_text('{"metadata":{"job_id":"' + jid + '"},"raw_payload":{}}',
                 encoding="utf-8")
    return p


def _s3_head_missing(*a, **kw):
    raise RuntimeError("404 Not Found (botocore ClientError mock)")


# ==== Test mask ====
def test_mask_secret_none_and_short():
    assert prm.mask_secret(None).startswith("(")  # "(khong dat)"
    assert prm.mask_secret("") != ""
    assert "abc" not in prm.mask_secret("abc")     # <8 ky tu -> "***"
    assert prm.mask_secret("minioadmin") == "mini***dmin"


def test_mask_secret_long_keeps_prefix_suffix():
    v = "Sup3rS3cretPassw0rd123"
    m = prm.mask_secret(v)
    assert m == "Sup3***3ret123"[-6:] or m.startswith("Sup3***")
    assert v not in m  # nguyen van khong xuat hien


# ==== Anh xa key (assertion #6) ====
def test_iter_envelopes_maps_bare_and_dt_prefix(tmp_path):
    _make_env(tmp_path, "2026-10-16", "BBB22222", 1, dt_prefix=False)  # bare
    _make_env(tmp_path, "2026-10-17", "AAA11111", 1, dt_prefix=True)   # dt=
    envs = prm.iter_envelopes(tmp_path, "raw/careerviet")
    keys = sorted(e.s3_key for e in envs)
    assert keys == [
        "raw/careerviet/2026-10-16/BBB22222_v1.json",
        "raw/careerviet/2026-10-17/AAA11111_v1.json",
    ]
    # Chac chan `dt=` bi loai bo khoi key
    assert all("dt=" not in k for k in keys)


def test_iter_envelopes_skips_non_json_and_non_date(tmp_path):
    (tmp_path / "raw").mkdir(parents=True)
    # thu muc khong phai dang ngay -> bo qua
    bad = tmp_path / "raw" / "archive"
    bad.mkdir()
    (bad / "AAA11111_v1.json").write_text("{}", encoding="utf-8")
    # thu muc dung ngay nhung file khong dung pattern -> bo qua
    ok = tmp_path / "raw" / "2026-10-16"
    ok.mkdir()
    (ok / "readme.txt").write_text("x", encoding="utf-8")
    (ok / "notes.json").write_text("{}", encoding="utf-8")
    (ok / "GOOD1111_v1.json").write_text("{}", encoding="utf-8")
    envs = prm.iter_envelopes(tmp_path, "raw/careerviet")
    assert [e.s3_key for e in envs] == ["raw/careerviet/2026-10-16/GOOD1111_v1.json"]


# ==== Test dry-run (assertion #1) ====
def test_dry_run_no_boto3_no_put(tmp_path, caplog):
    _make_env(tmp_path, "2026-10-16", "AAA11111", 1)
    _make_env(tmp_path, "2026-10-16", "BBB22222", 1)
    caplog.set_level(logging.INFO, logger="push_raw_to_minio")
    args = prm.build_parser().parse_args([
        "--source", "careerviet",
        "--local-dir", str(tmp_path),
        "--dry-run",
    ])
    # _build_s3_client KHONG duoc goi (boto3 lazy)
    with patch.object(prm, "_build_s3_client") as mock_build:
        stats = prm.run(args)
    mock_build.assert_not_called()
    assert stats["planned"] == 2
    assert stats["uploaded"] == 0
    assert stats["errors"] == 0
    # Caplog chua [DRY] + key mapping
    assert "[DRY]" in caplog.text
    assert "raw/careerviet/2026-10-16/AAA11111_v1.json" in caplog.text


# ==== Test no-clobber (assertion #2) ====
def test_no_clobber_default_skips_existing_key(tmp_path):
    _make_env(tmp_path, "2026-10-16", "AAA11111", 1)
    fake_s3 = MagicMock()
    # head_object OK -> key da ton tai -> SKIPPED_EXISTS
    fake_s3.head_object.return_value = {"ETag": '"ignored"'}
    args = prm.build_parser().parse_args([
        "--source", "careerviet", "--local-dir", str(tmp_path),
    ])
    with patch.object(prm, "_build_s3_client", return_value=fake_s3):
        stats = prm.run(args)
    fake_s3.upload_file.assert_not_called()
    assert stats["skipped_exists"] == 1
    assert stats["uploaded"] == 0


# ==== Test overwrite (assertion #3) ====
def test_overwrite_flag_uploads_existing(tmp_path):
    _make_env(tmp_path, "2026-10-16", "AAA11111", 1)
    fake_s3 = MagicMock()
    fake_s3.head_object.return_value = {"ETag": '"x"'}  # key da ton tai
    args = prm.build_parser().parse_args([
        "--source", "careerviet", "--local-dir", str(tmp_path),
        "--overwrite",
    ])
    with patch.object(prm, "_build_s3_client", return_value=fake_s3):
        stats = prm.run(args)
    fake_s3.upload_file.assert_called_once()
    assert stats["overwritten"] == 1
    assert stats["skipped_exists"] == 0


# ==== Test job-id filter (assertion #4) ====
def test_job_id_filter_selects_only_requested(tmp_path):
    _make_env(tmp_path, "2026-10-16", "AAA11111", 1)
    _make_env(tmp_path, "2026-10-16", "BBB22222", 1)
    _make_env(tmp_path, "2026-10-16", "CCC33333", 1)
    fake_s3 = MagicMock()
    fake_s3.head_object.side_effect = _s3_head_missing  # key chua co -> upload
    args = prm.build_parser().parse_args([
        "--source", "careerviet", "--local-dir", str(tmp_path),
        "--job-id", "AAA11111", "--job-id", "CCC33333",
    ])
    with patch.object(prm, "_build_s3_client", return_value=fake_s3):
        stats = prm.run(args)
    assert stats["planned"] == 2
    assert stats["uploaded"] == 2
    keys = sorted(c.args[2] for c in fake_s3.upload_file.call_args_list)
    assert keys == [
        "raw/careerviet/2026-10-16/AAA11111_v1.json",
        "raw/careerviet/2026-10-16/CCC33333_v1.json",
    ]
    # BBB22222 (khong duoc chon) khong xuat hien
    assert all("BBB22222" not in k for k in keys)


# ==== Test date filter ====
def test_date_filter_selects_only_matching(tmp_path):
    _make_env(tmp_path, "2026-10-16", "AAA11111", 1)
    _make_env(tmp_path, "2026-10-17", "BBB22222", 1)
    fake_s3 = MagicMock()
    fake_s3.head_object.side_effect = _s3_head_missing
    args = prm.build_parser().parse_args([
        "--source", "careerviet", "--local-dir", str(tmp_path),
        "--date", "2026-10-17",
    ])
    with patch.object(prm, "_build_s3_client", return_value=fake_s3):
        stats = prm.run(args)
    assert stats["planned"] == 1
    assert stats["uploaded"] == 1
    k = fake_s3.upload_file.call_args_list[0].args[2]
    assert k == "raw/careerviet/2026-10-17/BBB22222_v1.json"


# ==== Test password khong bi lo (assertion #5) ====
def test_password_and_access_key_never_leak_to_log(tmp_path, caplog, monkeypatch):
    """--verbose bat log access_key da MASK. Password va AK nguyen van
    khong duoc xuat hien trong caplog (va do do cung khong len stdout)."""
    secret = "Sup3rS3cret-P@ssw0rd-DU-NHAT-KHONG-IN"
    ak = "AKIAIOSFODNN7EXAMPLE1234"
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", secret)
    monkeypatch.setenv("MINIO_ROOT_USER", ak)
    _make_env(tmp_path, "2026-10-16", "AAA11111", 1)
    fake_s3 = MagicMock()
    fake_s3.head_object.return_value = {"ETag": '"x"'}  # SKIPPED_EXISTS
    args = prm.build_parser().parse_args([
        "--source", "careerviet", "--local-dir", str(tmp_path), "--verbose",
    ])
    caplog.set_level(logging.DEBUG, logger="push_raw_to_minio")
    with patch.object(prm, "_build_s3_client", return_value=fake_s3):
        prm.run(args)

    # Assertion cot loi: khong duoc lo nguyen van
    assert secret not in caplog.text, \
        f"PASSWORD nguyen van xuat hien trong log: {caplog.text[:400]}"
    assert ak not in caplog.text, \
        f"ACCESS KEY nguyen van xuat hien trong log: {caplog.text[:400]}"
    # Mask dang `<4 dau>***<4 cuoi>` phai xuat hien it nhat 1 lan
    masked_ak = "AKIA***1234"
    masked_sk = secret[:4] + "***" + secret[-4:]
    assert masked_ak in caplog.text, f"Access key da mask `{masked_ak}` thieu trong log"
    assert masked_sk in caplog.text, f"Password da mask `{masked_sk}` thieu trong log"


# ==== Test verify-sha: ETag == MD5 -> VERIFY_OK ====
def test_verify_sha_ok_on_single_part_upload(tmp_path):
    import hashlib
    p = _make_env(tmp_path, "2026-10-16", "AAA11111", 1)
    body = p.read_bytes()
    md5 = hashlib.md5(body).hexdigest()
    fake_s3 = MagicMock()
    fake_s3.head_object.side_effect = [
        Exception("404 mock pre-upload"),
        {"ETag": f'"{md5}"'},
    ]
    args = prm.build_parser().parse_args([
        "--source", "careerviet", "--local-dir", str(tmp_path), "--verify-sha",
    ])
    with patch.object(prm, "_build_s3_client", return_value=fake_s3):
        stats = prm.run(args)
    assert stats["uploaded"] == 1
    assert stats["verify_ok"] == 1
    assert stats["verify_mismatch"] == 0


def test_verify_sha_multipart_skipped(tmp_path):
    """ETag chua `-` -> multipart -> VERIFY_MULTIPART_SKIP."""
    fake_s3 = MagicMock()
    stats_dict = {"uploaded": 0, "verify_skip": 0, "verify_ok": 0}
    p = _make_env(tmp_path, "2026-10-16", "AAA11111", 1)
    fake_s3.head_object.side_effect = [
        Exception("404 mock pre-upload"),
        {"ETag": '"abc-2"'},
    ]
    args = prm.build_parser().parse_args([
        "--source", "careerviet", "--local-dir", str(tmp_path), "--verify-sha",
    ])
    with patch.object(prm, "_build_s3_client", return_value=fake_s3):
        stats = prm.run(args)
    assert stats["uploaded"] == 1
    assert stats["verify_skip"] == 1


# ==== Test include-ledger ====
def test_include_ledger_adds_ledger_keys(tmp_path):
    _make_env(tmp_path, "2026-10-16", "AAA11111", 1)
    led = tmp_path / "url_ledger"
    led.mkdir()
    (led / "catalog_master.json").write_text("{}", encoding="utf-8")
    (led / "manifests").mkdir()
    (led / "manifests" / "manifest_2026-10-16.jsonl").write_text("", encoding="utf-8")
    envs = prm.iter_envelopes(tmp_path, "raw/careerviet")
    led_envs = prm.iter_ledger(tmp_path, "careerviet")
    all_keys = sorted([e.s3_key for e in envs + led_envs])
    assert "url_ledger/careerviet/catalog_master.json" in all_keys
    assert "url_ledger/careerviet/manifests/manifest_2026-10-16.jsonl" in all_keys
    assert "raw/careerviet/2026-10-16/AAA11111_v1.json" in all_keys


# ==== Test argparse mutual exclusion ====
def test_no_clobber_and_overwrite_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        prm.build_parser().parse_args(["--no-clobber", "--overwrite"])


# ==== Test max-files ====
def test_max_files_truncates(tmp_path):
    for jid in ["A1", "A2", "A3", "A4", "A5"]:
        _make_env(tmp_path, "2026-10-16", f"{jid}000000", 1)
    args = prm.build_parser().parse_args([
        "--source", "careerviet", "--local-dir", str(tmp_path),
        "--max-files", "2", "--dry-run",
    ])
    stats = prm.run(args)
    assert stats["planned"] == 2
