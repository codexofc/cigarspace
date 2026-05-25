# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Shared response schemas: pagination, links, job-accepted, etc."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class Links(BaseModel):
    """HATEOAS link map. Each value is an absolute or root-relative URL."""

    model_config = ConfigDict(extra="allow")

    self_: str = Field(alias="self", description="Canonical URL of this resource.")


class PageLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self_: str = Field(alias="self")
    first: str
    last: str
    next: str | None = None
    prev: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope returned by every list endpoint."""

    model_config = ConfigDict(extra="forbid")

    items: list[T] = Field(description="Page of items.")
    total: int = Field(ge=0, description="Total number of matching items.")
    page: int = Field(ge=1, description="Current page (1-indexed).")
    page_size: int = Field(ge=1, description="Number of items per page.")
    total_pages: int = Field(ge=0, description="Total page count for the query.")
    links: PageLinks = Field(alias="_links")


class JobAcceptedResponse(BaseModel):
    """202 Accepted body for endpoints that enqueue background work."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="Identifier of the enqueued background job.")
    status: str = Field(
        default="queued",
        description="Initial job status — always `queued` at creation time.",
    )
    links: Links = Field(alias="_links")
