# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""S3-compatible storage adapter (used against SeaweedFS in dev / staging /
prod ; same code works against AWS S3, Cloudflare R2, Backblaze B2).

The storage_key layout is `<hash[:2]>/<hash>.<ext>` for a 256-bucket fan-out
that keeps any individual S3 "directory" small (~100 objects per bucket at
25k blobs).
"""

from __future__ import annotations

from typing import Any

import aioboto3

from infrastructure.media.errors import StorageError


def storage_key_for(content_hash: str, ext: str) -> str:
    return f"{content_hash[:2]}/{content_hash}.{ext}"


class SeaweedS3Storage:
    """IMediaStorage backed by an S3-compatible endpoint."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "us-east-1",
    ) -> None:
        self._endpoint_url = endpoint_url
        self._bucket = bucket
        self._session = aioboto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    async def ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist (idempotent, dev convenience)."""
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            try:
                await s3.head_bucket(Bucket=self._bucket)
            except Exception:
                try:
                    await s3.create_bucket(Bucket=self._bucket)
                except Exception as exc:  # noqa: BLE001
                    raise StorageError(f"create_bucket failed: {exc}") from exc

    async def put(
        self,
        *,
        content_hash: str,
        data: bytes,
        ext: str,
        mime_type: str,
    ) -> str:
        key = storage_key_for(content_hash, ext)
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            try:
                await s3.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=data,
                    ContentType=mime_type,
                    # Long Cache-Control: hash-based keys are content-immutable.
                    CacheControl="public, max-age=31536000, immutable",
                )
            except Exception as exc:  # noqa: BLE001
                raise StorageError(f"put_object failed: {exc}") from exc
        return key

    async def exists(self, *, storage_key: str) -> bool:
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=storage_key)
                return True
            except Exception:  # noqa: BLE001
                return False

    async def presigned_get(
        self,
        *,
        content_hash: str,
        ext: str,
        expires_in_seconds: int = 900,
    ) -> str:
        """Generate a pre-signed GET URL valid for the given TTL.

        Works against any S3-compatible backend; the API uses this so the
        bucket need not be publicly readable.
        """
        key = storage_key_for(content_hash, ext)
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in_seconds,
            )

    async def public_url(self, *, storage_key: str) -> str:
        """URL servable directly to a browser.

        SeaweedFS bucket-level anonymous Read (configured in s3.json) means
        GET on http://<host>/<bucket>/<key> just works. In prod with R2/S3
        a CDN sits in front and the API can either expose the same direct
        URL or generate a presigned one if needed.
        """
        return f"{self._endpoint_url.rstrip('/')}/{self._bucket}/{storage_key}"

    async def aclose(self) -> None:
        # aioboto3 sessions are short-lived (per-context-manager); no global
        # connection pool to drain.
        return None


def _coerce_kwargs(**kwargs: Any) -> dict[str, Any]:
    """Convenience for building from settings (kept open for future config)."""
    return {k: v for k, v in kwargs.items() if v is not None}
