# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Hybrid search + system endpoint tests."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def test_health_endpoint(api_client) -> None:
    r = await api_client.get("/api/v1/health")
    # status may be 200 or 503 depending on whether s3/redis are reachable
    # from the test environment; check the body shape regardless.
    assert r.status_code in (200, 503)
    body = r.json()
    assert "status" in body and "checks" in body
    names = {c["name"] for c in body["checks"]}
    assert "postgres" in names


async def test_version_endpoint(api_client) -> None:
    r = await api_client.get("/api/v1/version")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body


async def test_search_full_text_branch(api_client, seeded_universe) -> None:
    r = await api_client.get("/api/v1/cigars/search?q=Cohiba")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "Cohiba"
    # The seeded cigar has the substring "Cohiba" — trigram branch should
    # surface it. The vector branch may also if the fake embedder happens
    # to map it close enough; we don't assert on `matched_by` contents
    # because the fake embedder is deterministic but not semantically
    # meaningful.
    assert body["total"] >= 1
    assert any(item["cigar"]["slug"] == seeded_universe["cigar_slug"] for item in body["items"])


async def test_search_rejects_short_query(api_client) -> None:
    r = await api_client.get("/api/v1/cigars/search?q=a")
    assert r.status_code == 422


async def test_openapi_contract_completeness(api_client) -> None:
    """Every operation must declare a summary; every response must have a
    documented schema. Acts as a quality gate against drift."""

    r = await api_client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    schema = r.json()

    missing_summary: list[str] = []
    missing_response: list[str] = []
    for path, methods in schema["paths"].items():
        for method, op in methods.items():
            if method not in {"get", "post", "patch", "put", "delete"}:
                continue
            if not op.get("summary"):
                missing_summary.append(f"{method.upper()} {path}")
            responses = op.get("responses") or {}
            if (
                not any(r_obj.get("content") for r_obj in responses.values())
                and "204" not in responses
                and "307" not in responses
            ):
                missing_response.append(f"{method.upper()} {path}")

    assert not missing_summary, f"endpoints without summary: {missing_summary}"
    assert not missing_response, f"endpoints without response schema: {missing_response}"


async def test_security_invalid_token_returns_401(api_client) -> None:
    r = await api_client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


async def test_request_id_header_propagation(api_client) -> None:
    r = await api_client.get("/api/v1/version", headers={"X-Request-Id": "deadbeef-1234"})
    assert r.status_code == 200
    assert r.headers.get("x-request-id") == "deadbeef-1234"
