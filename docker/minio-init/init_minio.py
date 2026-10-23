"""Wait for the local MinIO S3 endpoint and idempotently initialize its bucket.

This helper intentionally does not depend on `curl`, `mc`, or a particular shell
being installed in the MinIO server image.
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


def wait_for_server(endpoint: str, timeout_seconds: int) -> None:
    health_url = endpoint.rstrip("/") + "/minio/health/live"
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=3) as response:
                if 200 <= response.status < 300:
                    print(f"[minio-init] MinIO API ready: {health_url}", flush=True)
                    return
                last_error = RuntimeError(f"HTTP {response.status}")
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(2)
    raise TimeoutError(
        f"MinIO did not become ready within {timeout_seconds}s. Last error: {last_error}"
    )



def remove_public_read_policy(s3, bucket: str) -> bool:
    """Remove an existing unconditional wildcard read policy from prior configs.

    Older project Compose versions set the whole bucket to anonymous download.
    This narrowly detects public-read statements and removes the bucket policy so
    upgrading to the private-by-default config actually takes effect.
    """
    try:
        raw_policy = s3.get_bucket_policy(Bucket=bucket).get("Policy", "{}")
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"NoSuchBucketPolicy", "NoSuchPolicy", "404", "NotFound"} or status == 404:
            return False
        raise

    policy = json.loads(raw_policy) if isinstance(raw_policy, str) else raw_policy
    statements = policy.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]

    def is_wildcard(principal) -> bool:
        if principal == "*":
            return True
        if isinstance(principal, dict):
            for value in principal.values():
                if value == "*" or (isinstance(value, list) and "*" in value):
                    return True
        return False

    kept_statements = []
    removed_public_read = False
    for statement in statements:
        if not isinstance(statement, dict) or statement.get("Effect") != "Allow":
            kept_statements.append(statement)
            continue
        if statement.get("Condition") or not is_wildcard(statement.get("Principal")):
            kept_statements.append(statement)
            continue
        actions = statement.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        is_public_read = any(
            action == "*" or action in {"s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"}
            for action in actions
        )
        if is_public_read:
            removed_public_read = True
        else:
            kept_statements.append(statement)

    if not removed_public_read:
        return False
    if kept_statements:
        policy["Statement"] = kept_statements
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
    else:
        s3.delete_bucket_policy(Bucket=bucket)
    print(
        "[minio-init] Removed unconditional public-read statement(s) left by an older setup.",
        flush=True,
    )
    return True


def main() -> int:
    endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000").rstrip("/")
    access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    bucket = os.getenv("MINIO_BUCKET", "vn-it-jobs")
    timeout = max(10, int(os.getenv("MINIO_WAIT_SECONDS", "120")))

    try:
        wait_for_server(endpoint, timeout)
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=10,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
            region_name="us-east-1",
        )

        existing = {item["Name"] for item in s3.list_buckets().get("Buckets", [])}
        if bucket not in existing:
            s3.create_bucket(Bucket=bucket)
            print(f"[minio-init] Created bucket: {bucket}", flush=True)
        else:
            print(f"[minio-init] Bucket already exists: {bucket}", flush=True)

        # Undo the previous project's known anonymous-download default without
        # touching conditional or non-public policies. New deployments are private.
        remove_public_read_policy(s3, bucket)

        # S3 has prefixes, not real directories. Keep small marker objects so the
        # four requested lakehouse layers are visible in a freshly initialized UI.
        for prefix in ("url_ledger/", "raw/", "staging/", "curated/"):
            key = prefix + ".keep"
            try:
                s3.head_object(Bucket=bucket, Key=key)
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code not in {"404", "NoSuchKey", "NotFound"}:
                    raise
                s3.put_object(Bucket=bucket, Key=key, Body=b"")
            print(f"[minio-init] Verified layer: {prefix}", flush=True)

        print(
            "[minio-init] Initialization complete. Bucket stays private by default; "
            "no anonymous policy was applied.",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(f"[minio-init] ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
