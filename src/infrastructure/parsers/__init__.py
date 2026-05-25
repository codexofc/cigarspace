# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Parser registry — pick the right listing/product parser per domain.

Adding a new merchant is a 3-line change: drop the parser module in this
package and register it in ``_REGISTRY`` below. ``cigars ingest-url`` and
the arq jobs auto-detect the parser from the URL hostname.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

from application.ports.parser import (
    ListingExtraction,
    ProductExtraction,
)
from infrastructure.parsers.cigarpassion import (
    CigarpassionListingParser,
    CigarpassionProductParser,
)
from infrastructure.parsers.mistercigar import (
    MistercigarListingParser,
    MistercigarProductParser,
)


class IListingParser:
    """Structural protocol — duck-typed via attribute access only."""

    def parse_listing(self, *, html: str, page_url: str) -> ListingExtraction: ...


class IProductParser:
    def parse_product(self, *, html: str, page_url: str) -> ProductExtraction: ...


@dataclass(frozen=True)
class ParserPair:
    name: str
    listing: Callable[[], IListingParser]
    product: Callable[[], IProductParser]


# Mapping host suffix → ParserPair. We match by suffix so subdomains and
# ``www.`` variants pick the same parser.
_REGISTRY: dict[str, ParserPair] = {
    "mistercigar.com": ParserPair(
        name="mistercigar",
        listing=MistercigarListingParser,
        product=MistercigarProductParser,
    ),
    "cigarpassion.ch": ParserPair(
        name="cigarpassion",
        listing=CigarpassionListingParser,
        product=CigarpassionProductParser,
    ),
}


class UnknownDomainError(LookupError):
    """Raised when a URL points to an unsupported merchant."""


def pair_for_url(url: str) -> ParserPair:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for suffix, pair in _REGISTRY.items():
        if host == suffix or host.endswith(f".{suffix}"):
            return pair
    raise UnknownDomainError(
        f"No parser registered for host {host!r}. Supported: {sorted(_REGISTRY)}"
    )


def listing_parser_for_url(url: str):
    return pair_for_url(url).listing()


def product_parser_for_url(url: str):
    return pair_for_url(url).product()


__all__ = [
    "CigarpassionListingParser",
    "CigarpassionProductParser",
    "MistercigarListingParser",
    "MistercigarProductParser",
    "ParserPair",
    "UnknownDomainError",
    "listing_parser_for_url",
    "pair_for_url",
    "product_parser_for_url",
]
