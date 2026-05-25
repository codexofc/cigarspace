# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Brands / Lines / Cigars catalogue endpoint tests."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def test_list_brands_paginated(api_client, seeded_universe) -> None:
    r = await api_client.get("/api/v1/brands?page=1&page_size=10")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert body["page"] == 1 and body["page_size"] == 10
    assert any(item["slug"] == "cohiba" for item in body["items"])
    # Link header has at least `self`, `first`, `last`.
    link_header = r.headers["link"]
    assert 'rel="first"' in link_header
    assert 'rel="last"' in link_header


async def test_brand_detail_404(api_client) -> None:
    r = await api_client.get("/api/v1/brands/unknown-brand")
    assert r.status_code == 404
    body = r.json()
    assert body["type"] == "errors/not-found"
    assert body["instance"].endswith("/brands/unknown-brand")


async def test_brand_detail_etag_roundtrip(api_client, seeded_universe) -> None:
    r1 = await api_client.get("/api/v1/brands/cohiba")
    assert r1.status_code == 200
    etag = r1.headers["etag"]
    r2 = await api_client.get("/api/v1/brands/cohiba", headers={"If-None-Match": etag})
    assert r2.status_code == 304


async def test_list_cigars_with_filters(api_client, seeded_universe) -> None:
    r = await api_client.get("/api/v1/cigars?is_cuban=true&format=robusto")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    item = body["items"][0]
    assert item["format_category"] == "robusto"


async def test_cigar_detail_carries_links(api_client, seeded_universe) -> None:
    r = await api_client.get(f"/api/v1/cigars/{seeded_universe['cigar_slug']}")
    assert r.status_code == 200
    body = r.json()
    assert body["_links"]["self"].endswith(f"/api/v1/cigars/{seeded_universe['cigar_slug']}")
    assert body["_links"]["packages"].endswith("/packages")


async def test_lines_for_brand(api_client, seeded_universe) -> None:
    r = await api_client.get("/api/v1/brands/cohiba/lines")
    assert r.status_code == 200
    assert any(line["slug"] == "behike" for line in r.json())


async def test_cigars_for_line(api_client, seeded_universe) -> None:
    r = await api_client.get("/api/v1/lines/behike/cigars")
    assert r.status_code == 200
    items = r.json()
    assert any(c["slug"] == seeded_universe["cigar_slug"] for c in items)
