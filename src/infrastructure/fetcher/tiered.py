# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""TieredFetcher — automatic L0 → L1 → L2 → L3 escalation.

Tiers:
- L0 : httpx direct, no impersonation, fastest, weakest furtiveness
- L1 : curl_cffi with TLS impersonation Chrome (rotating UAs)
- L2 : curl_cffi over ProtonVPN proxy (rotating IP via Bouncing or country swap)
- L3 : curl_cffi over Tor SOCKS5 (last-resort, slow, public exit nodes)

Strategy:
- start every domain at L0
- on a ForbiddenError, immediately retry at the next tier; mark the
  domain after N forbids so subsequent calls start higher

Soft-ban detection: an L0 / L1 response with status 200 but matching a
challenge pattern (Cloudflare interstitial, captcha, …) is treated as a
synthetic ForbiddenError — triggering the same escalation flow.

robots.txt: enforced before any tier call. Disallowed URLs raise
RobotsBlockedError immediately; no fetch happens.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from application.ports.fetcher import (
    FetchRequest,
    FetchResponse,
    ForbiddenError,
    IFetcher,
)
from infrastructure.fetcher.robots import RobotsPolicy
from infrastructure.fetcher.soft_ban import SoftBanDetector
from infrastructure.observability.logging import get_logger
from infrastructure.rate_limit.domain_limiter import extract_domain


@dataclass
class _TierEntry:
    fetcher: IFetcher
    name: str


class TieredFetcher:
    def __init__(
        self,
        *,
        tiers: Sequence[tuple[str, IFetcher]],
        escalate_after_403: int = 1,
        soft_ban_detector: SoftBanDetector | None = None,
        robots_policy: RobotsPolicy | None = None,
    ) -> None:
        if not tiers:
            raise ValueError("tiers must contain at least one (name, fetcher)")
        if escalate_after_403 < 1:
            raise ValueError("escalate_after_403 must be >= 1")

        self._tiers: list[_TierEntry] = [_TierEntry(fetcher=f, name=name) for name, f in tiers]
        self._threshold = escalate_after_403
        self._soft_ban = soft_ban_detector
        self._robots = robots_policy
        # Per-domain: how many forbids each tier has seen,
        # and which tier the domain is currently pinned to (None = start at 0)
        self._forbids: dict[str, int] = {}
        self._pinned_tier: dict[str, int] = {}
        self._log = get_logger("fetcher.tiered")

    @classmethod
    def with_default_pipeline(
        cls,
        *,
        l0: IFetcher,
        l1: IFetcher,
        l2: IFetcher | None = None,
        l3: IFetcher | None = None,
        l4: IFetcher | None = None,
        escalate_after_403: int = 1,
        soft_ban_detector: SoftBanDetector | None = None,
        robots_policy: RobotsPolicy | None = None,
    ) -> TieredFetcher:
        tiers: list[tuple[str, IFetcher]] = [("l0", l0), ("l1", l1)]
        if l2 is not None:
            tiers.append(("l2", l2))
        if l3 is not None:
            tiers.append(("l3", l3))
        if l4 is not None:
            tiers.append(("l4", l4))
        return cls(
            tiers=tiers,
            escalate_after_403=escalate_after_403,
            soft_ban_detector=soft_ban_detector,
            robots_policy=robots_policy,
        )

    def tier_for(self, url: str) -> str:
        """Public helper for diagnostics / logging."""
        idx = self._pinned_tier.get(extract_domain(url), 0)
        return self._tiers[idx].name

    def _check_soft_ban(self, response: FetchResponse) -> ForbiddenError | None:
        if self._soft_ban is None:
            return None
        signal = self._soft_ban.inspect(
            content_type=response.headers.get("content-type", ""),
            body=response.body,
        )
        if signal is None:
            return None
        return ForbiddenError(
            f"soft_ban detected: {signal.label} ({signal.matched_pattern})",
            url=response.url,
        )

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        # Enforce robots.txt before any tier round-trip.
        if self._robots is not None:
            await self._robots.assert_allowed(request.url)

        domain = extract_domain(request.url)
        start_idx = self._pinned_tier.get(domain, 0)

        last_exc: ForbiddenError | None = None

        for idx in range(start_idx, len(self._tiers)):
            tier = self._tiers[idx]
            try:
                response = await tier.fetcher.fetch(request)
            except ForbiddenError as exc:
                last_exc = exc
                self._record_forbid(domain, idx)
                self._log.info(
                    "tier_forbid",
                    domain=domain,
                    tier=tier.name,
                    forbids_total=self._forbids[domain],
                )
                continue

            # Hard 200 — but maybe a soft ban?
            soft = self._check_soft_ban(response)
            if soft is None:
                if idx > start_idx:
                    self._log.info(
                        "tier_recovered",
                        domain=domain,
                        tier=tier.name,
                    )
                return response

            last_exc = soft
            self._record_forbid(domain, idx)
            self._log.warning(
                "tier_soft_ban",
                domain=domain,
                tier=tier.name,
                signal=soft.args[0] if soft.args else "?",
            )
            # fall through to next tier

        # All tiers exhausted
        assert last_exc is not None
        self._log.error("tier_exhausted", domain=domain, tiers=len(self._tiers))
        raise last_exc

    def _record_forbid(self, domain: str, idx: int) -> None:
        count = self._forbids.get(domain, 0) + 1
        self._forbids[domain] = count
        # Pin the domain one level above the failed tier (or the same if it's the last)
        target = min(idx + 1, len(self._tiers) - 1)
        if count >= self._threshold and self._pinned_tier.get(domain, 0) < target:
            self._pinned_tier[domain] = target
            self._log.warning(
                "tier_pinned",
                domain=domain,
                tier=self._tiers[target].name,
                after=count,
            )

    async def aclose(self) -> None:
        for tier in self._tiers:
            await tier.fetcher.aclose()
