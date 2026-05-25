# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Queue name constant — single source of truth shared by the worker
and any external enqueue callers (CLI, jobs that re-enqueue).

Kept in a tiny dedicated module to avoid circular imports between
jobs.py and worker.py.
"""

QUEUE_NAME = "cigars:default"
