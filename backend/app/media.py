from __future__ import annotations

import mimetypes
from pathlib import Path


_IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def detect_image_mime(data: bytes, filename: str | Path | None = None) -> str | None:
    """Identify supported image data without trusting a remote URL suffix.

    Public image CDNs often serve extension-free URLs, so a `.bin` file can
    still contain a valid image. Conversely, an image-looking URL may return
    HTML or a blocked-page payload. The magic bytes are therefore authoritative.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    # A known extension remains useful for test fixtures and formats whose
    # short signature is not available, but never maps an unknown `.bin` to
    # application/octet-stream for a vision request.
    if filename is not None:
        guessed = mimetypes.guess_type(str(filename))[0]
        if guessed in _IMAGE_EXTENSIONS:
            return guessed
    return None


def image_suffix(data: bytes, filename: str | Path | None = None) -> str | None:
    mime = detect_image_mime(data, filename)
    return _IMAGE_EXTENSIONS.get(mime) if mime else None
