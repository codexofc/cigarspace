# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import infrastructure.customs  # noqa: F401  triggers registry population
from application.services.customs_registry import CustomsRegistry


def test_known_discovery_adapters() -> None:
    names = set(CustomsRegistry.known_discovery_names())
    assert {"legifrance-jorf", "generic-html-index"}.issubset(names)


def test_known_extractor_adapters() -> None:
    names = set(CustomsRegistry.known_extractor_names())
    assert {"legifrance-html", "pdf-table", "ofdf-generic"}.issubset(names)


def test_lookup_returns_adapter_instance() -> None:
    d = CustomsRegistry.discovery("legifrance-jorf")
    assert d.name == "legifrance-jorf"
    e = CustomsRegistry.extractor("legifrance-html")
    assert e.name == "legifrance-html"
    assert e.version == "1.0"


def test_unknown_name_raises_with_known_set_in_message() -> None:
    import pytest

    with pytest.raises(KeyError) as ei:
        CustomsRegistry.discovery("does-not-exist")
    assert "does-not-exist" in str(ei.value)
    assert "legifrance-jorf" in str(ei.value)
