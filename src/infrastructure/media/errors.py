# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Errors specific to the media pipeline."""

from __future__ import annotations


class ImageValidationError(Exception):
    """Raised when a downloaded payload is not a valid image or violates limits."""


class StorageError(Exception):
    """Raised when the object storage backend rejects a put/get."""
