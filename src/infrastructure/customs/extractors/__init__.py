# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Extractor adapters — self-register in the CustomsRegistry on import."""

from application.services.customs_registry import CustomsRegistry
from infrastructure.customs.extractors.douane_ods import DouaneOdsExtractor
from infrastructure.customs.extractors.legifrance_dila_json import (
    LegifranceDilaJsonExtractor,
)
from infrastructure.customs.extractors.legifrance_html import LegifranceHtmlExtractor
from infrastructure.customs.extractors.ofdf_generic import OfdfGenericExtractor
from infrastructure.customs.extractors.pdf_table_extractor import PdfTableExtractor

CustomsRegistry.register_extractor(LegifranceHtmlExtractor())
CustomsRegistry.register_extractor(PdfTableExtractor())
CustomsRegistry.register_extractor(OfdfGenericExtractor())
CustomsRegistry.register_extractor(LegifranceDilaJsonExtractor())
CustomsRegistry.register_extractor(DouaneOdsExtractor())

__all__ = [
    "DouaneOdsExtractor",
    "LegifranceDilaJsonExtractor",
    "LegifranceHtmlExtractor",
    "OfdfGenericExtractor",
    "PdfTableExtractor",
]
