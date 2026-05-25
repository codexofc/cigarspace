# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Image validation + normalisation pipeline (Pillow).

Inputs : raw bytes from a fetcher (any format Pillow recognises — JPEG,
PNG, WebP, GIF, …).

Output : a NormalizedImage with:
- bytes converted to WebP at quality `webp_quality` (default 85)
- EXIF orientation applied (so rotated phone photos render right)
- alpha channel preserved (transparent PNG → transparent WebP)
- dimensions and final byte size reported

Hard limits:
- raw payload must fit in `max_bytes` (default 8 MiB), else ImageValidationError
- the output must remain a still raster (animated GIF/WebP rejected here —
  could be supported later as a separate code path)
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from infrastructure.media.errors import ImageValidationError


@dataclass(frozen=True)
class NormalizedImage:
    data: bytes
    width: int
    height: int
    mime_type: str
    ext: str


# Animated formats we refuse for the canonical pipeline.
_ANIMATED_MIMES = frozenset({"image/gif"})


def validate_and_normalize(
    raw: bytes,
    *,
    max_bytes: int = 8 * 1024 * 1024,
    webp_quality: int = 85,
) -> NormalizedImage:
    if not raw:
        raise ImageValidationError("empty payload")
    if len(raw) > max_bytes:
        raise ImageValidationError(f"payload too large: {len(raw)} > {max_bytes} bytes")

    # First open: cheap verify pass that detects truncated / fake-extension files.
    try:
        Image.open(io.BytesIO(raw)).verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageValidationError(f"not a valid image: {exc}") from exc

    # Re-open for actual processing (verify() invalidates the file object).
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageValidationError(f"could not decode image: {exc}") from exc

    # Refuse animations on this canonical path
    is_animated = getattr(img, "is_animated", False)
    if is_animated or Image.MIME.get(img.format or "") in _ANIMATED_MIMES:
        raise ImageValidationError(f"animated images not supported (format={img.format})")

    # Apply EXIF rotation before any pixel work — phone photos report
    # landscape orientation in the EXIF tag instead of rotating the raster.
    img = ImageOps.exif_transpose(img)

    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    target_mode = "RGBA" if has_alpha else "RGB"
    if img.mode != target_mode:
        img = img.convert(target_mode)

    # Encode to WebP
    out = io.BytesIO()
    img.save(
        out,
        format="WEBP",
        quality=webp_quality,
        method=6,  # max compression effort
        lossless=False,
    )
    payload = out.getvalue()

    return NormalizedImage(
        data=payload,
        width=img.width,
        height=img.height,
        mime_type="image/webp",
        ext="webp",
    )
