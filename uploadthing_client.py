"""Small UploadThing REST client for the Python backend.

UploadThing only publishes a JavaScript SDK. This module follows their documented
REST flow: request a v7 presigned upload, put the file into storage, and keep the
returned public URL in Supabase.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests


API_ROOT = "https://api.uploadthing.com"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOCUMENT_TYPES = {"application/pdf"}


class UploadThingError(RuntimeError):
    pass


@dataclass(frozen=True)
class UploadedFile:
    url: str
    key: str
    name: str


def _decode_token(token: str) -> dict:
    """Decode the SDK v7 token and return its JSON payload."""
    try:
        padded = token.strip() + "=" * (-len(token.strip()) % 4)
        return json.loads(base64.b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UploadThingError("UPLOADTHING_TOKEN is not a valid SDK v7 token") from exc


def _api_key() -> str:
    token = os.getenv("UPLOADTHING_TOKEN", "").strip()
    if not token:
        raise UploadThingError("UPLOADTHING_TOKEN is not configured")
    api_key = _decode_token(token).get("apiKey")
    if not api_key:
        raise UploadThingError("UPLOADTHING_TOKEN does not contain an apiKey")
    return api_key


def _app_id() -> str:
    token = os.getenv("UPLOADTHING_TOKEN", "").strip()
    if not token:
        raise UploadThingError("UPLOADTHING_TOKEN is not configured")
    app_id = _decode_token(token).get("appId")
    if not app_id:
        raise UploadThingError("UPLOADTHING_TOKEN does not contain an appId")
    return app_id


def _headers() -> dict[str, str]:
    return {
        "x-uploadthing-api-key": _api_key(),
        "x-uploadthing-fe-package": "portfolio-python-backend",
        "content-type": "application/json",
    }


def validate_upload(content: bytes, content_type: str, *, document: bool = False) -> None:
    allowed = ALLOWED_DOCUMENT_TYPES if document else ALLOWED_IMAGE_TYPES
    limit = MAX_DOCUMENT_BYTES if document else MAX_IMAGE_BYTES
    if content_type not in allowed:
        expected = "PDF" if document else "JPG, PNG, WebP, or GIF"
        raise UploadThingError(f"Unsupported file type. Please upload {expected}.")
    if not content:
        raise UploadThingError("The selected file is empty")
    if len(content) > limit:
        raise UploadThingError(f"File is too large. Maximum size is {limit // 1024 // 1024}MB.")


def upload_bytes(filename: str, content: bytes, content_type: str) -> UploadedFile:
    safe_name = f"{Path(filename or 'upload').stem[:80]}{Path(filename or '').suffix.lower()}"
    request_body = {
        "fileName": safe_name,
        "fileSize": len(content),
        "fileType": content_type,
        "acl": "public-read",
        "contentDisposition": "inline",
    }

    try:
        prepared_response = requests.post(
            f"{API_ROOT}/v7/prepareUpload",
            headers=_headers(),
            json=request_body,
            timeout=30,
        )
        prepared_response.raise_for_status()
        prepared_payload = prepared_response.json()
        prepared = prepared_payload.get("data", prepared_payload)
        storage_response = requests.put(
            prepared["url"],
            files={"file": (safe_name, content, content_type)},
            timeout=60,
        )
        storage_response.raise_for_status()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        detail = getattr(getattr(exc, "response", None), "text", "")
        raise UploadThingError(f"UploadThing upload failed{': ' + detail[:200] if detail else ''}") from exc

    key = prepared.get("key") or urlparse(prepared.get("url", "")).path.rsplit("/", 1)[-1]
    url = prepared.get("ufsUrl") or prepared.get("fileUrl") or (f"https://{_app_id()}.ufs.sh/f/{key}" if key else None)
    if not url or not key:
        raise UploadThingError("UploadThing returned an incomplete upload response")
    return UploadedFile(url=url, key=key, name=safe_name)


def file_key_from_url(url: str) -> str | None:
    """Extract keys from both legacy /f/<key> and current /a/<app>/<key> URLs."""
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    if host not in {"utfs.io", "uploadthing.com"} and not host.endswith(".ufs.sh"):
        return None
    parts = [part for part in urlparse(url).path.split("/") if part]
    return parts[-1] if parts else None


def delete_file_by_url(url: str) -> bool:
    key = file_key_from_url(url)
    if not key:
        return False
    try:
        response = requests.post(
            f"{API_ROOT}/v6/deleteFiles",
            headers=_headers(),
            json={"fileKeys": [key]},
            timeout=30,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        raise UploadThingError("UploadThing could not delete the file") from exc
