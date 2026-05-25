# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Argon2id password hashing.

The PasswordHasher instance is module-level and stateless; safe to share
across the entire process.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Return an argon2id-encoded hash for ``plain``."""
    return _hasher.hash(plain)


def verify_password(plain: str, stored_hash: str) -> bool:
    """Return True iff ``plain`` matches ``stored_hash``.

    Never raises; returns False on any verification or hash-format error.
    """
    try:
        return _hasher.verify(stored_hash, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    """Return True if argon2 parameters in ``stored_hash`` are outdated."""
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return False
