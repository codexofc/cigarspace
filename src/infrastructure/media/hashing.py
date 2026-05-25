# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Content-addressable hashing (BLAKE3).

BLAKE3 is faster than SHA-256 (~3 GB/s on modern x86), cryptographically
strong, and produces a 32-byte (64-hex-char) digest by default. We use
the full digest for collision resistance even at billions-of-blobs scale.
"""

from __future__ import annotations

from blake3 import blake3


def blake3_hex(data: bytes) -> str:
    """Return the BLAKE3 hex digest (64 chars) of `data`."""
    return blake3(data).hexdigest()
