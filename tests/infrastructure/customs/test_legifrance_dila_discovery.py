# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import httpx
import respx

from infrastructure.config.settings import (
    AppSettings,
    LogSettings,
    MediaSettings,
    PisteSettings,
    PostgresSettings,
    RedisSettings,
    S3Settings,
)
from infrastructure.customs.discovery.legifrance_dila_api import (
    LegifranceDilaApiDiscovery,
)


class _Settings:
    """Stand-in for infrastructure.config.get_settings() — DILA tests only
    need .piste, but we expose the full surface for safety."""

    def __init__(self) -> None:
        self.app = AppSettings()
        self.postgres = PostgresSettings()
        self.redis = RedisSettings()
        self.log = LogSettings()
        self.s3 = S3Settings()
        self.media = MediaSettings()
        self.piste = PisteSettings(
            client_id="fake-id",
            client_secret="fake-secret",
            oauth_url="https://oauth.test/api/oauth/token",
            api_base_url="https://api.test/dila",
            scope="openid",
        )


@respx.mock
async def test_paginated_search_collects_publications() -> None:
    # Mock OAuth
    respx.post("https://oauth.test/api/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 1800})
    )
    # Mock 2 pages of search results — mirrors the real DILA shape:
    # `nor` and `datePublication` are at top level, only `cid` lives in titles[0].
    respx.post("https://api.test/dila/search").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "nor": "ECOI1932471A",
                            "datePublication": "2019-12-10T00:00:00.000+0000",
                            "nature": "ARRETE",
                            "titles": [
                                {
                                    "id": "JORFTEXT000041534567_01-01-2999",
                                    "cid": "JORFTEXT000041534567",
                                    "title": (
                                        "Arrêté du 4 décembre 2019 portant "
                                        "homologation des prix de vente au "
                                        "détail des tabacs manufacturés"
                                    ),
                                    "startDate": "2020-01-01",
                                    "endDate": None,
                                }
                            ],
                        },
                        {
                            "nor": "ECOI1928912A",
                            "datePublication": "2019-10-15T00:00:00.000+0000",
                            "nature": "ARRETE",
                            "titles": [
                                {
                                    "id": "JORFTEXT000041500001_01-01-2999",
                                    "cid": "JORFTEXT000041500001",
                                    "title": (
                                        "Arrêté du 11 octobre 2019 portant "
                                        "homologation des prix de vente au "
                                        "détail des tabacs manufacturés"
                                    ),
                                    "startDate": "2019-11-04",
                                    "endDate": None,
                                }
                            ],
                        },
                    ]
                },
            ),
            httpx.Response(200, json={"results": []}),
        ]
    )

    with patch(
        "infrastructure.customs.discovery.legifrance_dila_api.get_settings",
        return_value=_Settings(),
    ):
        discovery = LegifranceDilaApiDiscovery()
        result = await discovery.find_publications(
            index_html="",
            index_url="ignored",
            config={"page_size": 2, "max_pages": 3},
        )

    refs = {p.regulator_reference for p in result}
    assert refs == {"ECOI1932471A", "ECOI1928912A"}

    by_ref = {p.regulator_reference: p for p in result}
    assert by_ref["ECOI1932471A"].publication_date == date(2019, 12, 10)
    assert by_ref["ECOI1932471A"].effective_date == date(2020, 1, 1)
    assert by_ref["ECOI1932471A"].document_url == (
        "https://api.test/dila/consult/jorf/JORFTEXT000041534567"
    )
    assert by_ref["ECOI1932471A"].document_mime == "application/json"


@respx.mock
async def test_empty_results_returns_empty() -> None:
    respx.post("https://oauth.test/api/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 1800})
    )
    respx.post("https://api.test/dila/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    with patch(
        "infrastructure.customs.discovery.legifrance_dila_api.get_settings",
        return_value=_Settings(),
    ):
        discovery = LegifranceDilaApiDiscovery()
        result = await discovery.find_publications(index_html="", index_url="ignored", config={})
    assert list(result) == []
