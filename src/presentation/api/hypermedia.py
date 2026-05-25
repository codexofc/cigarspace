# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Helpers to build HATEOAS ``_links`` objects and pagination links."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import Request

from presentation.api.schemas.base import Links, PageLinks


_API_PREFIX = "/api/v1"


def absolute(request: Request, path: str) -> str:
    """Build an absolute URL by combining the request's base URL with path."""
    base = str(request.base_url).rstrip("/")
    return f"{base}{path}"


def make_links(request: Request, self_path: str, **extra: str) -> Links:
    return Links(self=absolute(request, self_path), **extra)


def make_page_links(
    request: Request,
    *,
    path: str,
    page: int,
    page_size: int,
    total_pages: int,
    extra_query: dict[str, Any] | None = None,
) -> PageLinks:
    extra = dict(extra_query or {})

    def _build(p: int) -> str:
        q = {**extra, "page": p, "page_size": page_size}
        return absolute(request, f"{path}?{urlencode(q)}")

    return PageLinks(
        self=_build(page),
        first=_build(1),
        last=_build(max(total_pages, 1)),
        next=_build(page + 1) if page < total_pages else None,
        prev=_build(page - 1) if page > 1 else None,
    )


def add_pagination_headers(response, *, request: Request, links: PageLinks) -> None:
    """Set RFC 5988 ``Link`` headers + ``X-Total-*`` companion headers."""
    rels = [("first", links.first), ("last", links.last)]
    if links.next:
        rels.append(("next", links.next))
    if links.prev:
        rels.append(("prev", links.prev))
    response.headers["Link"] = ", ".join(f'<{url}>; rel="{rel}"' for rel, url in rels)


__all__ = [
    "absolute",
    "add_pagination_headers",
    "make_links",
    "make_page_links",
    "_API_PREFIX",
]
