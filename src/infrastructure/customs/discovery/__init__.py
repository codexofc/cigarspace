# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Discovery adapters — self-register in the CustomsRegistry on import.

Note: LegifranceDilaApiDiscovery is registered but defers all credential
validation until the first call — instantiation is safe when PISTE creds
are not set (the source `fr-legifrance-dila` simply remains is_active=false
until the operator provides credentials and flips it).
"""

from application.services.customs_registry import CustomsRegistry
from infrastructure.customs.discovery.douane_opendata import (
    DouaneOpenDataDiscovery,
)
from infrastructure.customs.discovery.generic_html_index import (
    GenericHtmlIndexDiscovery,
)
from infrastructure.customs.discovery.legifrance_dila_api import (
    LegifranceDilaApiDiscovery,
)
from infrastructure.customs.discovery.legifrance_jorf import LegifranceJorfDiscovery

CustomsRegistry.register_discovery(LegifranceJorfDiscovery())
CustomsRegistry.register_discovery(GenericHtmlIndexDiscovery())
CustomsRegistry.register_discovery(LegifranceDilaApiDiscovery())
CustomsRegistry.register_discovery(DouaneOpenDataDiscovery())

__all__ = [
    "DouaneOpenDataDiscovery",
    "GenericHtmlIndexDiscovery",
    "LegifranceDilaApiDiscovery",
    "LegifranceJorfDiscovery",
]
