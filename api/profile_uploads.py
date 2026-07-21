"""Shared helpers for profile logo/gallery file uploads."""

from __future__ import annotations

import json
from pathlib import Path

from typing import Optional

from fastapi import HTTPException, UploadFile

from . import config

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def uploads_base() -> Path:
    root = config.UPLOADS_ROOT
    if root:
        return Path(root).resolve()
    return Path(__file__).resolve().parent.parent / "uploads"


def ext_from_upload(filename: str, content_type: Optional[str]) -> str:
    suf = Path(filename).suffix.lower()
    if suf in _ALLOWED_EXT:
        return suf
    if content_type and content_type.split(";")[0].strip() in _CONTENT_TYPE_EXT:
        return _CONTENT_TYPE_EXT[content_type.split(";")[0].strip()]
    return ".png"


def next_gallery_name(gallery_dir: Path, ext: str) -> str:
    gallery_dir.mkdir(parents=True, exist_ok=True)
    n = 1
    while True:
        name = f"{n:03d}{ext}"
        if not (gallery_dir / name).exists():
            return name
        n += 1


def parse_gallery_urls(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, list):
        return [str(x) for x in data if x is not None and str(x).strip()]
    return []


def serialize_gallery(urls: list[str]) -> str:
    return json.dumps(urls)


ALLOWED_IMAGE_EXT = _ALLOWED_EXT


async def save_profile_logo(profile_id: int, file: UploadFile) -> str:
    """Write logo to uploads/profiles/{id}/logo.{ext}; returns public URL path."""
    ext = ext_from_upload(file.filename or "logo", file.content_type)
    if ext not in _ALLOWED_EXT:
        ext = ".png"

    base = uploads_base() / "profiles" / str(profile_id)
    base.mkdir(parents=True, exist_ok=True)

    dest = base / f"logo{ext}"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    dest.write_bytes(data)
    return f"/uploads/profiles/{profile_id}/logo{ext}"


async def append_profile_gallery(
    profile_id: int, files: list[UploadFile], existing_json: Optional[str]
) -> tuple[list[str], list[str]]:
    """Append images; returns (full gallery URL list, newly added URLs)."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    gallery_dir = uploads_base() / "profiles" / str(profile_id) / "gallery"
    gallery_dir.mkdir(parents=True, exist_ok=True)

    urls = parse_gallery_urls(existing_json)
    new_urls: list[str] = []

    for upload in files:
        ext = ext_from_upload(upload.filename or "image", upload.content_type)
        if ext not in _ALLOWED_EXT:
            ext = ".jpg"
        name = next_gallery_name(gallery_dir, ext)
        dest = gallery_dir / name
        data = await upload.read()
        if not data:
            continue
        dest.write_bytes(data)
        rel = f"/uploads/profiles/{profile_id}/gallery/{name}"
        urls.append(rel)
        new_urls.append(rel)

    return urls, new_urls
