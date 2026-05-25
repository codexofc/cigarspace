# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Adapter registry — maps parser_name (string) → adapter instance.

Adapters self-register at import time via `register_discovery` /
`register_extractor`. The `infrastructure/customs/__init__.py` imports
all sub-modules so that the registry is populated by the time use cases
look up a parser by name.

This is the seam that makes adding a new juridiction painless:
- write a new file `infrastructure/customs/discovery/foo.py`
- subclass `ICustomsDiscoveryAdapter`, set `name = "foo-bar"`
- the registry picks it up automatically as soon as the module is imported
"""

from __future__ import annotations

from typing import ClassVar

from application.ports.customs_discovery import ICustomsDiscoveryAdapter
from application.ports.customs_extractor import ICustomsExtractorAdapter


class CustomsRegistry:
    _discovery: ClassVar[dict[str, ICustomsDiscoveryAdapter]] = {}
    _extractor: ClassVar[dict[str, ICustomsExtractorAdapter]] = {}

    @classmethod
    def register_discovery(cls, adapter: ICustomsDiscoveryAdapter) -> None:
        cls._discovery[adapter.name] = adapter

    @classmethod
    def register_extractor(cls, adapter: ICustomsExtractorAdapter) -> None:
        cls._extractor[adapter.name] = adapter

    @classmethod
    def discovery(cls, name: str) -> ICustomsDiscoveryAdapter:
        try:
            return cls._discovery[name]
        except KeyError as exc:
            raise KeyError(
                f"No discovery adapter named {name!r}. Known: {sorted(cls._discovery)}"
            ) from exc

    @classmethod
    def extractor(cls, name: str) -> ICustomsExtractorAdapter:
        try:
            return cls._extractor[name]
        except KeyError as exc:
            raise KeyError(
                f"No extractor adapter named {name!r}. Known: {sorted(cls._extractor)}"
            ) from exc

    @classmethod
    def known_discovery_names(cls) -> list[str]:
        return sorted(cls._discovery)

    @classmethod
    def known_extractor_names(cls) -> list[str]:
        return sorted(cls._extractor)
