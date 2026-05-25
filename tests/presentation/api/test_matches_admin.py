# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Match + admin endpoints tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from domain.entities.customs import CigarCustomsMatch
from domain.enums import Confidence, CustomsMatchStatus, MatchMethod
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.asyncio


async def _seed_match(
    session_factory,
    seeded_universe,
    *,
    status: CustomsMatchStatus,
    entry_key: str = "entry_id",
) -> str:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        match = await uow.customs_matches.add(
            CigarCustomsMatch(
                cigar_id=seeded_universe["cigar_id"],
                customs_entry_id=seeded_universe[entry_key],
                match_method=MatchMethod.HYBRID,
                score=Decimal("0.92"),
                confidence=Confidence.HIGH,
                status=status,
                pack_size_bucket=10,
                signals={"exact": 1.0},
                matched_at=datetime.now(tz=UTC),
                matched_by="test-matcher",
            )
        )
        await uow.commit()
        return str(match.id)


async def test_anonymous_user_cannot_list_matches(api_client) -> None:
    r = await api_client.get("/api/v1/matches")
    assert r.status_code == 401


async def test_reader_only_sees_accepted_matches(
    api_client, session_factory, seeded_universe, reader_token
) -> None:
    await _seed_match(session_factory, seeded_universe, status=CustomsMatchStatus.AUTO_ACCEPTED)
    pending = await _seed_match(
        session_factory,
        seeded_universe,
        status=CustomsMatchStatus.PENDING_REVIEW,
        entry_key="entry_id_single",
    )
    r = await api_client.get(
        "/api/v1/matches",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert r.status_code == 200
    statuses = {item["status"] for item in r.json()["items"]}
    assert statuses == {"auto_accepted"}
    # Pending row must 404 for reader.
    r2 = await api_client.get(
        f"/api/v1/matches/{pending}",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert r2.status_code == 404


async def test_admin_sees_pending_review(
    api_client, session_factory, seeded_universe, admin_token
) -> None:
    pending = await _seed_match(
        session_factory, seeded_universe, status=CustomsMatchStatus.PENDING_REVIEW
    )
    r = await api_client.get(
        "/api/v1/matches?status=pending_review",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    ids = {item["id"] for item in r.json()["items"]}
    assert pending in ids


async def test_admin_patch_match_to_human_accepted(
    api_client, session_factory, seeded_universe, admin_token
) -> None:
    pending = await _seed_match(
        session_factory, seeded_universe, status=CustomsMatchStatus.PENDING_REVIEW
    )
    r = await api_client.patch(
        f"/api/v1/matches/{pending}",
        json={"status": "human_accepted", "notes": "validated by test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "human_accepted"
    assert body["notes"] == "validated by test"


async def test_patch_match_requires_admin(
    api_client, session_factory, seeded_universe, reader_token
) -> None:
    pending = await _seed_match(
        session_factory, seeded_universe, status=CustomsMatchStatus.PENDING_REVIEW
    )
    r = await api_client.patch(
        f"/api/v1/matches/{pending}",
        json={"status": "human_rejected"},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert r.status_code == 403


async def test_match_jobs_requires_admin(api_client, seeded_universe, reader_token) -> None:
    r = await api_client.post(
        "/api/v1/match-jobs",
        json={"scope": "all"},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert r.status_code == 403


async def test_refresh_jobs_404_on_unknown_source(api_client, seeded_universe, admin_token) -> None:
    r = await api_client.post(
        "/api/v1/customs-sources/nope/refresh-jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404
