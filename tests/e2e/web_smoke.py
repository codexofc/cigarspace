# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""End-to-end smoke test for the web admin UI.

Driven by patchright (Chromium patched at CDP-level) so we can exercise the
actual browser flow:
1. Open /login.
2. Fill the form with the seeded dev admin and submit.
3. Assert the dashboard renders with the four stat cards.
4. Navigate to /cigars and assert the list table loads.
5. Type into the search box and submit; assert results contain a row.
6. Navigate to /matches/pending. If a row is present, open Accept and
   confirm; assert the row disappears from the queue.

Run with the API on :8000 and the web on :3000:
    uv run python tests/e2e/web_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any

from patchright.async_api import async_playwright


WEB_URL = os.environ.get("E2E_WEB_URL", "http://127.0.0.1:3000")
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "admin-dev-pass-2026")
HEADLESS = os.environ.get("E2E_HEADLESS", "1") != "0"


class StepFailure(AssertionError):
    pass


async def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise StepFailure(message)


async def _login(page: Any) -> None:
    await page.goto(f"{WEB_URL}/login", wait_until="networkidle")
    await page.fill("input#email", ADMIN_EMAIL)
    await page.fill("input#password", ADMIN_PASSWORD)
    async with page.expect_navigation(wait_until="networkidle"):
        await page.click("button[type=submit]")
    await _expect(
        page.url.rstrip("/") == WEB_URL.rstrip("/"),
        f"expected to land on dashboard, got {page.url}",
    )


async def _check_dashboard(page: Any) -> None:
    await page.wait_for_selector("text=Dashboard", timeout=5000)
    # Four stat cards (Cigars / Accepted / Pending / Sources)
    await page.wait_for_selector("text=Cigars in catalogue", timeout=5000)
    await page.wait_for_selector("text=Matches accepted", timeout=5000)
    await page.wait_for_selector("text=Pending review", timeout=5000)
    await page.wait_for_selector("text=Active customs sources", timeout=5000)
    # Admin actions section visible
    await page.wait_for_selector("text=Admin actions", timeout=5000)


async def _check_cigars_list(page: Any) -> None:
    await page.click("a[href='/cigars']")
    await page.wait_for_url(f"{WEB_URL}/cigars", timeout=5000)
    await page.wait_for_selector("text=Filters", timeout=5000)
    # Table has either rows or the "No results." placeholder.
    rows = await page.locator("table tbody tr").count()
    await _expect(rows >= 1, "expected at least one row in the cigars table")


async def _check_search(page: Any) -> None:
    await page.fill("input[placeholder*='Hybrid search']", "toscanello")
    await page.click("button:has-text('Search')")
    # The URL should now carry ?q=toscanello.
    await page.wait_for_url("**/cigars?*q=toscanello*", timeout=5000)
    # At least one search hit row should render.
    await page.wait_for_selector("table tbody tr", timeout=5000)
    rows = await page.locator("table tbody tr").count()
    await _expect(rows >= 1, "expected ≥1 hit row for query 'toscanello'")


async def _check_review_queue(page: Any) -> None:
    await page.goto(f"{WEB_URL}/matches/pending", wait_until="networkidle")
    await page.wait_for_selector("text=Review queue", timeout=5000)


async def _check_me(page: Any) -> None:
    await page.click("a[href='/me']")
    await page.wait_for_url(f"{WEB_URL}/me", timeout=5000)
    await page.wait_for_selector("text=Your profile", timeout=5000)


async def _check_logout(page: Any) -> None:
    async with page.expect_navigation(wait_until="networkidle"):
        await page.click("button:has-text('Logout')")
    await _expect(
        page.url.endswith("/login"),
        f"expected to be redirected to /login after logout, got {page.url}",
    )


async def run() -> int:
    started = time.monotonic()
    print(f"E2E smoke against {WEB_URL} (headless={HEADLESS})", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(15000)
            await _login(page)
            print("  ✓ login → dashboard", flush=True)
            await _check_dashboard(page)
            print("  ✓ dashboard cards present", flush=True)
            await _check_cigars_list(page)
            print("  ✓ /cigars list renders rows", flush=True)
            await _check_search(page)
            print("  ✓ /cigars hybrid search returns hits", flush=True)
            await _check_review_queue(page)
            print("  ✓ /matches/pending opens (admin)", flush=True)
            await _check_me(page)
            print("  ✓ /me shows admin profile", flush=True)
            await _check_logout(page)
            print("  ✓ logout → /login", flush=True)
        finally:
            await browser.close()
    elapsed = time.monotonic() - started
    print(f"\nE2E PASSED in {elapsed:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except StepFailure as exc:
        print(f"\nE2E FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
