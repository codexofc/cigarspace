# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Extract price entries from a DILA JORF "consult" JSON response.

The DILA API returns a structured JSON for each text, where article bodies
are HTML embedded in fields. We grab every article HTML, run the existing
LegifranceHtmlExtractor on the concatenated HTML, and yield the entries.

This adapter is registered with name "legifrance-dila-json" — set
`extraction_parser_name = "legifrance-dila-json"` on the customs_source.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, ClassVar

import httpx

from application.ports.customs_extractor import (
    CustomsPriceExtraction,
)
from infrastructure.config import get_settings
from infrastructure.customs.extractors.legifrance_html import LegifranceHtmlExtractor
from infrastructure.customs.piste_oauth import PisteOAuthClient


class LegifranceDilaJsonExtractor:
    name: ClassVar[str] = "legifrance-dila-json"
    version: ClassVar[str] = "1.0"
    # /consult/jorf is POST-only + OAuth-protected. The generic GET fetch
    # in the use case would 400 → we self-fetch via fetch_document().
    requires_document_fetch: ClassVar[bool] = False

    def __init__(self) -> None:
        self._html = LegifranceHtmlExtractor()
        self._oauth: PisteOAuthClient | None = None

    def _client(self) -> PisteOAuthClient:
        if self._oauth is None:
            self._oauth = PisteOAuthClient(get_settings().piste)
        return self._oauth

    async def fetch_document(
        self,
        *,
        document_url: str,
        config: dict[str, Any],  # noqa: ARG002
    ) -> bytes:
        """Resolve the JORF text_cid from the discovery URL and POST it.

        Discovery URLs are minted as `{api_base}/consult/jorf/{TEXT_CID}` so
        the cid is the final path segment.
        """
        text_cid = document_url.rstrip("/").rsplit("/", 1)[-1]
        payload = await self._fetch_jorf_json(text_cid)
        return json.dumps(payload).encode("utf-8")

    async def extract(
        self,
        *,
        document_bytes: bytes,
        mime_type: str,
        default_currency: str,
        config: dict[str, Any],
    ) -> Iterable[CustomsPriceExtraction]:
        # The use case fetches /consult/jorf/{cid} via the regular fetcher,
        # but that endpoint is JSON behind PISTE auth → 401 without the
        # Authorization header. We re-fetch it ourselves with proper auth.
        #
        # `document_bytes` could be:
        #   (a) already JSON (auth happened upstream) — try to decode first
        #   (b) an HTML error page from the auth-less fetch — fall back to
        #       a manual fetch using the regulator_reference passed in config.
        payload = _try_parse_json(document_bytes)
        if payload is None:
            text_cid = config.get("text_cid") or config.get("regulator_reference")
            if not text_cid:
                return []
            payload = await self._fetch_jorf_json(text_cid)
        return await self._extract_from_payload(payload, default_currency=default_currency)

    async def _fetch_jorf_json(self, text_cid: str) -> dict[str, Any]:
        settings = get_settings()
        headers = await self._client().auth_headers()
        async with httpx.AsyncClient(
            base_url=settings.piste.api_base_url, timeout=30, headers=headers
        ) as client:
            response = await client.post(
                "/consult/jorf",
                json={"textCid": text_cid},
            )
            response.raise_for_status()
            return response.json()

    async def _extract_from_payload(
        self,
        payload: dict[str, Any],
        *,
        default_currency: str,
    ) -> Iterable[CustomsPriceExtraction]:
        # DILA articles contain HTML in `texteHtml` or `contenu` fields.
        html_chunks: list[str] = []
        for art in _iter_articles(payload):
            for field in ("texteHtml", "contenu", "texte"):
                value = art.get(field)
                if value and isinstance(value, str):
                    html_chunks.append(value)
                    break

        full_html = "<article>" + "\n".join(html_chunks) + "</article>"
        if not html_chunks:
            return []

        # Reuse the HTML extractor — same column-detection heuristics.
        return await self._html.extract(
            document_bytes=full_html.encode("utf-8"),
            mime_type="text/html",
            default_currency=default_currency,
            config={},
        )


def _try_parse_json(data: bytes) -> dict[str, Any] | None:
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    decoded = decoded.lstrip()
    if not decoded.startswith("{"):
        return None
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return None


def _iter_articles(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Walk the DILA tree and yield every article-like node."""
    candidates = [payload]
    while candidates:
        node = candidates.pop()
        if not isinstance(node, dict):
            continue
        if "texteHtml" in node or "contenu" in node:
            yield node
        for value in node.values():
            if isinstance(value, dict):
                candidates.append(value)
            elif isinstance(value, list):
                candidates.extend(v for v in value if isinstance(v, dict))
