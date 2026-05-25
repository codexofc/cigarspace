# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import pytest

from infrastructure.fetcher.soft_ban import SoftBanDetector


def test_invalid_max_scan_rejected() -> None:
    with pytest.raises(ValueError):
        SoftBanDetector(max_scan_bytes=100)


def test_skips_non_html_content_types() -> None:
    d = SoftBanDetector()
    body = b'{"error": "Just a moment"}'
    assert d.inspect(content_type="application/json", body=body) is None


def test_detects_cloudflare_interstitial() -> None:
    d = SoftBanDetector()
    body = b"<html><body><h1>Just a moment...</h1><p>Checking your browser</p></body></html>"
    sig = d.inspect(content_type="text/html; charset=utf-8", body=body)
    assert sig is not None
    assert "cloudflare" in sig.label


def test_detects_cloudflare_turnstile() -> None:
    d = SoftBanDetector()
    body = b'<html><body><div class="cf-turnstile"></div></body></html>'
    sig = d.inspect(content_type="text/html", body=body)
    assert sig is not None
    assert sig.label == "cloudflare_turnstile"


def test_detects_datadome() -> None:
    d = SoftBanDetector()
    body = b"<html><body>Welcome <script>var _dd_g=1;</script></body></html>"
    # DataDome is matched via the substring 'datadome' or 'ddg_8_test', not _dd_g
    # so this should NOT match — verify negative path
    assert d.inspect(content_type="text/html", body=body) is None

    body2 = b"<html><body>Powered by datadome captcha</body></html>"
    sig = d.inspect(content_type="text/html", body=body2)
    assert sig is not None
    assert "datadome" in sig.label


def test_detects_generic_captcha_text() -> None:
    d = SoftBanDetector()
    body = b"<html><body><p>Please verify you are human to continue</p></body></html>"
    sig = d.inspect(content_type="text/html", body=body)
    assert sig is not None
    assert sig.label == "generic_captcha"


def test_normal_html_passes_through() -> None:
    d = SoftBanDetector()
    body = b"""<html>
        <body>
            <h1>Cohiba Behike BHK 52</h1>
            <p>Longueur: 119 mm, cepo 52, fait main \xc3\xa0 Cuba.</p>
        </body>
    </html>"""
    assert d.inspect(content_type="text/html", body=body) is None


def test_case_insensitive_match() -> None:
    d = SoftBanDetector()
    body = b"<html><body><h1>JUST A MOMENT...</h1></body></html>"
    sig = d.inspect(content_type="text/html", body=body)
    assert sig is not None


def test_extra_patterns_extend_detection() -> None:
    d = SoftBanDetector(extra_patterns=(("My Custom WAF Block", "mywaf"),))
    body = b"<html><body>My Custom WAF Block triggered</body></html>"
    sig = d.inspect(content_type="text/html", body=body)
    assert sig is not None
    assert sig.label == "mywaf"


def test_only_scans_first_n_bytes() -> None:
    # A pattern beyond max_scan_bytes is NOT detected
    d = SoftBanDetector(max_scan_bytes=2048)
    body = b"<html><body>" + b"x" * 4000 + b"Just a moment..." + b"</body></html>"
    sig = d.inspect(content_type="text/html", body=body)
    assert sig is None
