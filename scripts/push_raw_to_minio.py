#!/usr/bin/env python3
"""push_raw_to_minio.py — Day raw envelope (va tuy chon ledger) cua CareerViet
len MinIO/S3 ma KHONG sua file dung chung `crawlers/common/url_ledger.py`.

Cau truc dich (theo docs/01 §3 va docs/02 §3.1, 479 dong doc crawl §13):

    s3://<bucket>/raw/<source>/<YYYY-MM-DD>/<job_id>_v<version>.json

Anh xa key dia phuong -> MinIO:

    <local-dir>/raw/dt=<date>/<jid>_v<n>.json
      -> <prefix>/<date>/<jid>_v<n>.json

    vi du: data/careerviet/raw/dt=2026-10-16/35C81470_v1.json
      -> raw/careerviet/2026-10-16/35C81470_v1.json

An toan:
- Idempotent: mac dinh SKIPPED_EXISTS neu key da ton tai (head_object truoc put).
- Dung `--overwrite` de buoc ghi de.
- `boto3` lazy import → `--dry-run` khong can cai boto3.
- Khong bao gio in gia tri `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (chi in
  da mask khi `--verbose`).
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LOG = logging.getLogger("push_raw_to_minio")

# Thu muc ngay dang local: ca 2 khai niem
#   - CareerViet crawler (line 722): date_str = "%Y-%m-%d" -> `raw/<YYYY-MM-DD>/...`
#   - convention topcv/_dryrun: `raw/dt=<YYYY-MM-DD>/...`
# Ca 2 deu duoc chap nhan va loai bo `dt=` khi anh xa S3 key.
DT_DIR_RE = re.compile(r"^(?:dt=)?(\d{4}-\d{2}-\d{2})$")
# <JOB_ID>_v<N>.json (JOB_ID hex in hoa/thuong + chu so)
ENV_RE = re.compile(r"^(?P<jid>[A-Za-z0-9]+)_v(?P<ver>\d+)\.json$")


# ==== An toan bi mat ====
def mask_secret(v: str | None) -> str:
    """Tra ve `XXXX***YYYY` neu v dai >8 ky tu; nguoc lai `***` (de nghi).**"""
    if not v:
        return "(khong dat)"
    if len(v) <= 8:
        return "***"
    return f"{v[:4]}***{v[-4:]}"


# ==== Kieu du lieu ====
@dataclass
class PushItem:
    path: Path
    s3_key: str
    date: str
    job_id: str
    version: int


# ==== Danh sach file ====
def iter_envelopes(
    local_dir: Path,
    prefix: str,
    dates: Iterable[str] | None = None,
    job_ids: Iterable[str] | None = None,
) -> list[PushItem]:
    """Quet envelope local. Chap nhan 3 convention (theo thu tu uu tien):

    (a) `<local_dir>/raw/<YYYY-MM-DD>/*_v<n>.json`
        (CareerViet crawler mac dinh: `--local-dir data/careerviet`)
    (b) `<local_dir>/raw/dt=<YYYY-MM-DD>/*_v<n>.json`
        (Hive/topcv convention va `_dryrun`)
    (c) `<local_dir>/*_v<n>.json` hoac `<local_dir>/dt=<...>/...
        khi `local_dir` **khong** chua subfolder `raw/`
        (vd: `--local-dir data/careerviet/raw` — guoc bo tang cap trung)

    Cac thu muc bat dau bang `_` (nhu `_dryrun`, `_blocked`, `_backup_*`) **luon**
    bi loai vi DT_DIR_RE khong match. Ledger **khong** nam o day (xem iter_ledger).
    """
    raw = local_dir / "raw"
    if not raw.is_dir():
        # (c) fallback: local_dir chinh no la raw root
        raw = local_dir
    if not raw.exists():
        return []
    d_set = set(dates) if dates else None
    j_set = set(job_ids) if job_ids else None
    out: list[PushItem] = []
    for dt_dir in sorted(raw.iterdir()):
        if not dt_dir.is_dir():
            continue
        m = DT_DIR_RE.match(dt_dir.name)
        if not m:
            continue
        date = m.group(1)
        if d_set and date not in d_set:
            continue
        for f in sorted(dt_dir.glob("*.json")):
            em = ENV_RE.match(f.name)
            if not em:
                continue
            if j_set and em.group("jid") not in j_set:
                continue
            out.append(
                PushItem(
                    path=f,
                    s3_key=f"{prefix}/{date}/{f.name}",
                    date=date,
                    job_id=em.group("jid"),
                    version=int(em.group("ver")),
                )
            )
    return out


def iter_ledger(local_dir: Path, source: str) -> list[PushItem]:
    """Quet `local_dir/url_ledger/**` -> PushItem (chi dung khi --include-ledger)."""
    led = local_dir / "url_ledger"
    if not led.exists():
        return []
    out: list[PushItem] = []
    for f in sorted(led.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(led).as_posix()
        out.append(
            PushItem(
                path=f,
                s3_key=f"url_ledger/{source}/{rel}",
                date="-",
                job_id=source,
                version=0,
            )
        )
    return out


# ==== S3 client (lazy) ====
def _build_s3_client(endpoint: str, ak: str, sk: str):
    """Tao S3 client (boto3 lazy). Khuon mau giong `UrlLedger.sync_to_minio`."""
    import boto3  # noqa: WPS433 (lazy import y thuc)
    from botocore.client import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        config=Config(
            signature_version="s3v4",
            connect_timeout=3,
            retries={"max_attempts": 2},
        ),
        region_name="us-east-1",
    )


def _head_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:  # botocore ClientError / 404
        return False


def _verify_etag(s3, bucket: str, key: str, path: Path) -> str:
    """Tra ve 'VERIFY_OK' / 'VERIFY_MULTIPART_SKIP' / 'VERIFY_MISMATCH:...'.

    Mac dinh single-part upload -> ETag == MD5 (botocore cat bao dau `"`).
    Neu ETag chua `-` -> multipart -> khong phai MD5, bo qua doi chieu.
    """
    try:
        md5 = hashlib.md5(path.read_bytes()).hexdigest()
        h = s3.head_object(Bucket=bucket, Key=key)
        etag = (h.get("ETag", "") or "").strip('"')
        if "-" in etag:
            return "VERIFY_MULTIPART_SKIP"
        if etag.lower() == md5.lower():
            return "VERIFY_OK"
        return f"VERIFY_MISMATCH:local={md5};remote={etag}"
    except Exception as exc:  # pragma: no cover - hiem
        return f"VERIFY_HEAD_FAIL:{exc}"


# ==== Upload ====
def upload_one(
    s3,
    bucket: str,
    item: PushItem,
    clobber: bool,
    verify: bool,
) -> str:
    """Tra ve chuoi trang thai: 'SKIPPED_EXISTS' | 'UPLOADED' | 'OVERWRITTEN'
    (kem '+VERIFY_*' khi --verify-sha)."""
    exists = _head_exists(s3, bucket, item.s3_key)
    if exists and not clobber:
        return "SKIPPED_EXISTS"
    s3.upload_file(str(item.path), bucket, item.s3_key)
    base = "OVERWRITTEN" if exists else "UPLOADED"
    if verify:
        base += "+" + _verify_etag(s3, bucket, item.s3_key, item.path)
    return base


# ==== CLI ====
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Day raw envelope (va tuy chon ledger) len MinIO/S3.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--source", default="careerviet",
                   help="Ten source (dung trong prefix mac dinh + ledger key)")
    p.add_argument("--local-dir", default=None,
                   help="Goc chua raw/ va url_ledger/ (mac dinh: data/<source>)")
    p.add_argument("--prefix", default=None,
                   help="Prefix S3 dich (mac dinh: raw/<source>)")
    p.add_argument("--bucket", default=None,
                   help="Overide MINIO_BUCKET")
    p.add_argument("--endpoint", default=None,
                   help="Overide MINIO_ENDPOINT")
    p.add_argument("--date", dest="dates", action="append", default=[],
                   metavar="YYYY-MM-DD",
                   help="Loc theo ngay (lap duoc nhieu lan)")
    p.add_argument("--job-id", dest="job_ids", action="append", default=[],
                   metavar="JOB_ID",
                   help="Loc theo job_id (lap duoc nhieu lan)")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--no-clobber", dest="clobber", action="store_false",
                     default=False,
                     help="(MAC DINH) head_object truoc khi put; key da ton tai -> SKIPPED_EXISTS")
    grp.add_argument("--overwrite", dest="clobber", action="store_true",
                     help="Buoc put_object (ghi de key da co)")
    p.add_argument("--dry-run", action="store_true",
                   help="In danh sach key, KHONG upload, KHONG can boto3")
    p.add_argument("--include-ledger", action="store_true",
                   help="Kem upload url_ledger/* -> url_ledger/<source>/*")
    p.add_argument("--max-files", type=int, default=None,
                   help="Gioi han N file (de kiem thu)")
    p.add_argument("--verify-sha", action="store_true",
                   help="Sau upload: head_object doi chieu ETag (MD5 single-part)")
    p.add_argument("--verbose", action="store_true",
                   help="Log access-key da mask; moi file 1 dong ket qua")
    return p


def run(args) -> dict:
    """Chay toan bo pipeline push. Tra ve stats dict (de test bat duoc)."""
    local_dir = Path(args.local_dir or f"data/{args.source}")
    prefix = args.prefix or f"raw/{args.source}"
    bucket = args.bucket or os.getenv("MINIO_BUCKET", "vn-it-jobs")

    stats: dict = {
        "planned": 0,
        "uploaded": 0,
        "overwritten": 0,
        "skipped_exists": 0,
        "verify_ok": 0,
        "verify_skip": 0,
        "verify_mismatch": 0,
        "errors": 0,
    }

    envs = iter_envelopes(local_dir, prefix, args.dates, args.job_ids)
    if args.include_ledger:
        envs += iter_ledger(local_dir, args.source)
    if args.max_files is not None:
        envs = envs[: args.max_files]
    stats["planned"] = len(envs)

    # --dry-run: in ra danh sach key, khong import boto3
    if args.dry_run:
        for e in envs:
            LOG.info("[DRY] %s -> s3://%s/%s", e.path, bucket, e.s3_key)
        LOG.info("[DRY] Tong %d file se duoc push (KHONG upload, KHONG can boto3)",
                 len(envs))
        return stats

    # ==== Upload that (boto3 lazy) ====
    try:
        import boto3  # noqa: F401
    except ImportError:
        LOG.error("boto3 chua cai. Chay: pip install -r requirements.txt")
        stats["errors"] += 1
        return stats

    endpoint = args.endpoint or os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    ak = os.getenv("MINIO_ROOT_USER", "minioadmin")
    sk = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")

    if args.verbose:
        # Chi in gia tri DA MASK. KHONG bao gio in sk nguyen van.
        LOG.info("endpoint=%s bucket=%s access_key=%s secret_key=%s",
                 endpoint, bucket, mask_secret(ak), mask_secret(sk))

    try:
        s3 = _build_s3_client(endpoint, ak, sk)
    except Exception as exc:  # pragma: no cover
        LOG.error("Khong ket noi duoc MinIO (%s): %s", endpoint, exc)
        stats["errors"] += 1
        return stats

    for e in envs:
        try:
            status = upload_one(s3, bucket, e, args.clobber, args.verify_sha)
        except Exception as exc:
            LOG.error("Loi upload %s: %s", e.s3_key, exc)
            stats["errors"] += 1
            continue
        # Dem stats
        if status.startswith("SKIPPED_EXISTS"):
            stats["skipped_exists"] += 1
        elif status.startswith("UPLOADED"):
            stats["uploaded"] += 1
        elif status.startswith("OVERWRITTEN"):
            stats["overwritten"] += 1
        if "+VERIFY_OK" in status:
            stats["verify_ok"] += 1
        elif "+VERIFY_MULTIPART_SKIP" in status:
            stats["verify_skip"] += 1
        elif "+VERIFY_MISMATCH" in status or "+VERIFY_HEAD_FAIL" in status:
            stats["verify_mismatch"] += 1
        if args.verbose:
            LOG.info("%s -> %s", e.s3_key, status)

    LOG.info(
        "[push_raw_to_minio] Ket thuc: planned=%d uploaded=%d overwritten=%d "
        "skipped_exists=%d verify_ok=%d verify_skip=%d verify_mismatch=%d errors=%d",
        stats["planned"], stats["uploaded"], stats["overwritten"],
        stats["skipped_exists"], stats["verify_ok"], stats["verify_skip"],
        stats["verify_mismatch"], stats["errors"],
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    # Nap .env (neu co) — giong cach scripts/setup_minio.py lam.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    p = build_parser()
    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
