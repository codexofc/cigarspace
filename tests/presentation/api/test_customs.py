# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs sources / publications / entries endpoint tests."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def test_list_sources(api_client, seeded_universe) -> None:
    r = await api_client.get("/api/v1/customs-sources")
    assert r.status_code == 200
    codes = {s["code"] for s in r.json()["items"]}
    assert seeded_universe["source_code"] in codes


async def test_source_detail_etag(api_client, seeded_universe) -> None:
    r1 = await api_client.get(f"/api/v1/customs-sources/{seeded_universe['source_code']}")
    assert r1.status_code == 200
    etag = r1.headers["etag"]
    r2 = await api_client.get(
        f"/api/v1/customs-sources/{seeded_universe['source_code']}",
        headers={"If-None-Match": etag},
    )
    assert r2.status_code == 304


async def test_publications_paginated(api_client, seeded_universe) -> None:
    r = await api_client.get(
        f"/api/v1/customs-sources/{seeded_universe['source_code']}/publications?page=1&page_size=10"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    pub = body["items"][0]
    assert pub["regulator_reference"] == "FR-TEST-1"


async def test_publication_detail_and_entries(api_client, seeded_universe) -> None:
    pid = seeded_universe["publication_id"]
    r1 = await api_client.get(f"/api/v1/customs-publications/{pid}")
    assert r1.status_code == 200
    r2 = await api_client.get(f"/api/v1/customs-publications/{pid}/entries?page=1&page_size=10")
    assert r2.status_code == 200
    body = r2.json()
    assert body["total"] >= 2
    pack_sizes = {e["pack_size"] for e in body["items"]}
    assert pack_sizes == {1, 10}
    brands = {e["raw_brand_label"] for e in body["items"]}
    assert brands == {"HABANOS"}


async def test_entry_detail(api_client, seeded_universe) -> None:
    r = await api_client.get(f"/api/v1/customs-entries/{seeded_universe['entry_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["currency_code"] == "EUR"
