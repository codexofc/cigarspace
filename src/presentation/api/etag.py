# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""ETag / If-None-Match helpers.

The strategy is simple but effective for read endpoints: take the JSON
payload that would be returned, hash it with sha1, return that as the
``ETag`` header. If the client repeats the request with the same
``If-None-Match``, return ``304 Not Modified`` and skip the body.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import Request, Response, status


def compute_etag(payload: Any) -> str:
    """Stable sha1 hex of the JSON-encoded payload."""
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()


def maybe_not_modified(*, request: Request, etag: str, response: Response) -> Response | None:
    """If the client sent matching ``If-None-Match``, return a 304 response.

    Otherwise set the ``ETag`` header on ``response`` and return ``None``
    so the caller can return the full payload.
    """
    response.headers["ETag"] = etag
    cache_header = request.headers.get("if-none-match")
    if cache_header and etag in {tag.strip().strip('"') for tag in cache_header.split(",")}:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"ETag": etag},
        )
    return None
