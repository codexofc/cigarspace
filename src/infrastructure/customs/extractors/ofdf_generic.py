# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Swiss OFDF/BAZG generic extractor — dispatch by mime type.

The actual format used by OFDF (PDF vs HTML, exact column names) isn't
confirmed yet. This adapter is registered so the source
`ch-ofdf` can be activated as soon as the operator identifies the URL —
no code change required.

Dispatch:
- application/pdf → PdfTableExtractor with config_json passed through
- text/html       → LegifranceHtmlExtractor (same heuristics : headers
                    Marque/Désignation/Prix work for most European
                    regulatory tables; CHF accepted by parse_price)
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar

from application.ports.customs_extractor import (
    CustomsPriceExtraction,
)
from infrastructure.customs.extractors.legifrance_html import LegifranceHtmlExtractor
from infrastructure.customs.extractors.pdf_table_extractor import PdfTableExtractor


class OfdfGenericExtractor:
    name: ClassVar[str] = "ofdf-generic"
    version: ClassVar[str] = "1.0"

    def __init__(self) -> None:
        self._pdf = PdfTableExtractor()
        self._html = LegifranceHtmlExtractor()

    async def extract(
        self,
        *,
        document_bytes: bytes,
        mime_type: str,
        default_currency: str,
        config: dict[str, Any],
    ) -> Iterable[CustomsPriceExtraction]:
        mime = (mime_type or "").lower()
        if "pdf" in mime:
            return await self._pdf.extract(
                document_bytes=document_bytes,
                mime_type=mime_type,
                default_currency=default_currency,
                config=config,
            )
        return await self._html.extract(
            document_bytes=document_bytes,
            mime_type=mime_type,
            default_currency=default_currency,
            config=config,
        )
