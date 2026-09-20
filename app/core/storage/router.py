"""Authenticated upload endpoints shared by all feature modules."""

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.dependencies import require_csrf
from app.core.responses import success_response
from app.core.storage import StorageService


router = APIRouter(prefix="", tags=["Storage"])


@router.post("/upload")
async def upload_asset(_: object = Depends(require_csrf), file: UploadFile = File(...)) -> dict:
    """Legacy-compatible upload route using the same provider-neutral storage service."""
    return success_response(await StorageService().upload(file))


@router.post("/upload-media-asset")
async def upload_media_asset(_: object = Depends(require_csrf), file: UploadFile = File(...)) -> dict:
    """Upload an image or video to Cloudinary."""
    return success_response(await StorageService().upload(file))


@router.post("/upload-document-asset")
async def upload_document_asset(_: object = Depends(require_csrf), file: UploadFile = File(...)) -> dict:
    """Upload a document or other non-media file to UploadThing."""
    return success_response(await StorageService().upload(file))
