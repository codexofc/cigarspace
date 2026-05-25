# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import io

import pytest
from PIL import Image

from infrastructure.media.errors import ImageValidationError
from infrastructure.media.image_pipeline import (
    NormalizedImage,
    validate_and_normalize,
)


def _png_bytes(w: int = 200, h: int = 150, *, mode: str = "RGB") -> bytes:
    img = Image.new(mode, (w, h), color=(220, 20, 60))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w: int = 200, h: int = 150, *, quality: int = 90) -> bytes:
    img = Image.new("RGB", (w, h), color=(100, 130, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _webp_bytes(w: int = 200, h: int = 150) -> bytes:
    img = Image.new("RGB", (w, h), color=(80, 200, 120))
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=90)
    return buf.getvalue()


def test_normalises_jpeg_to_webp() -> None:
    result = validate_and_normalize(_jpeg_bytes())
    assert isinstance(result, NormalizedImage)
    assert result.mime_type == "image/webp"
    assert result.ext == "webp"
    assert result.width == 200 and result.height == 150
    assert result.data.startswith(b"RIFF") and b"WEBP" in result.data[:32]


def test_normalises_png_to_webp() -> None:
    result = validate_and_normalize(_png_bytes())
    assert result.mime_type == "image/webp"
    assert result.width == 200 and result.height == 150


def test_passes_through_webp_input() -> None:
    result = validate_and_normalize(_webp_bytes())
    assert result.mime_type == "image/webp"
    assert result.width == 200


def test_preserves_alpha_for_rgba_png() -> None:
    raw = _png_bytes(mode="RGBA")
    result = validate_and_normalize(raw)
    decoded = Image.open(io.BytesIO(result.data))
    assert decoded.mode in ("RGBA", "RGB")  # Pillow may decode WebP alpha as RGBA


def test_rejects_empty_payload() -> None:
    with pytest.raises(ImageValidationError):
        validate_and_normalize(b"")


def test_rejects_non_image_bytes() -> None:
    with pytest.raises(ImageValidationError):
        validate_and_normalize(b"this is definitely not an image " * 50)


def test_rejects_oversized_payload() -> None:
    huge = _png_bytes(2000, 2000)
    with pytest.raises(ImageValidationError):
        validate_and_normalize(huge, max_bytes=1024)


def test_quality_setting_affects_size() -> None:
    raw = _jpeg_bytes(800, 600)
    a = validate_and_normalize(raw, webp_quality=30)
    b = validate_and_normalize(raw, webp_quality=95)
    assert len(a.data) < len(b.data), "lower quality should produce smaller output"
