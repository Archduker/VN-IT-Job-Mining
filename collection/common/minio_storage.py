"""Compatibility forwarding module: redirects all legacy storage calls to Cloudflare R2."""

from __future__ import annotations

from collection.common.r2_storage import (
    get_r2_client,
    upload_file_to_r2,
    upload_file_to_minio,
    canonicalize_lakehouse_key,
)

__all__ = ["get_r2_client", "upload_file_to_r2", "upload_file_to_minio", "canonicalize_lakehouse_key"]
