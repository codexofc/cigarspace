# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs adapters root package.

Importing this package triggers the registration of every discovery and
extractor adapter into the application-level `CustomsRegistry`.
"""

from infrastructure.customs import discovery as _discovery  # noqa: F401
from infrastructure.customs import extractors as _extractors  # noqa: F401
