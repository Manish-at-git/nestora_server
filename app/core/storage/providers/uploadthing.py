"""UploadThing adapter for documents and non-visual files."""

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings


async def upload_to_uploadthing(file: UploadFile) -> dict:
    """Use the official UploadThing server SDK through the small local bridge."""
    settings = get_settings()
    if not settings.uploadthing_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "UploadThing storage is not configured")
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file must have a filename")

    suffix = Path(file.filename).suffix or ".bin"
    contents = await file.read()
    if not contents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
        temporary.write(contents)
        temporary_path = temporary.name
    try:
        command = [
            settings.uploadthing_node_binary,
            str(settings.uploadthing_helper_path),
            temporary_path,
            file.filename,
            file.content_type or "application/octet-stream",
        ]
        environment = {**os.environ, "UPLOADTHING_TOKEN": settings.uploadthing_token}
        result = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            env=environment,
            cwd=str(settings.uploadthing_helper_path.parent),
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "UploadThing upload failed")
        payload = json.loads(result.stdout)
        if not payload.get("ok") or not payload.get("url"):
            raise RuntimeError(payload.get("error", "UploadThing returned no URL"))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, RuntimeError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "UploadThing upload failed") from exc
    finally:
        Path(temporary_path).unlink(missing_ok=True)
    return {
        "ok": True,
        "url": payload["url"],
        "filename": file.filename,
        "asset_type": "document",
        "provider": "uploadthing",
    }
