from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import Mock

from botocore.exceptions import ClientError

MODULE_PATH = Path(__file__).resolve().parents[2] / "docker" / "minio-init" / "init_minio.py"
SPEC = importlib.util.spec_from_file_location("minio_init", MODULE_PATH)
minio_init = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(minio_init)


def test_removes_known_unconditional_public_read_policy():
    s3 = Mock()
    s3.get_bucket_policy.return_value = {
        "Policy": '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":["s3:GetObject"],"Resource":"arn:aws:s3:::vn-it-jobs/*"}]}'
    }

    assert minio_init.remove_public_read_policy(s3, "vn-it-jobs") is True
    s3.delete_bucket_policy.assert_called_once_with(Bucket="vn-it-jobs")


def test_does_not_remove_conditional_public_policy():
    s3 = Mock()
    s3.get_bucket_policy.return_value = {
        "Policy": '{"Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject","Condition":{"IpAddress":{"aws:SourceIp":"192.0.2.0/24"}}}]}'
    }

    assert minio_init.remove_public_read_policy(s3, "vn-it-jobs") is False
    s3.delete_bucket_policy.assert_not_called()


def test_missing_bucket_policy_is_ok():
    s3 = Mock()
    s3.get_bucket_policy.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucketPolicy", "Message": "No policy"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
        "GetBucketPolicy",
    )

    assert minio_init.remove_public_read_policy(s3, "vn-it-jobs") is False
    s3.delete_bucket_policy.assert_not_called()


def test_removes_public_read_but_preserves_other_policy_statements():
    s3 = Mock()
    keep_statement = {"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
                      "Action": ["s3:PutObject"], "Resource": "arn:aws:s3:::vn-it-jobs/*"}
    s3.get_bucket_policy.return_value = {
        "Policy": __import__("json").dumps({"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject",
             "Resource": "arn:aws:s3:::vn-it-jobs/*"},
            keep_statement,
        ]})
    }

    assert minio_init.remove_public_read_policy(s3, "vn-it-jobs") is True
    s3.delete_bucket_policy.assert_not_called()
    s3.put_bucket_policy.assert_called_once()
    saved = __import__("json").loads(s3.put_bucket_policy.call_args.kwargs["Policy"])
    assert saved["Statement"] == [keep_statement]
