"""Single storage entry point with provider routing kept out of feature modules."""

from fastapi import UploadFile

from app.core.storage.providers.cloudinary import upload_to_cloudinary
from app.core.storage.providers.uploadthing import upload_to_uploadthing


class StorageService:
    """Route visual media to Cloudinary and other files to UploadThing."""

    async def upload(self, file: UploadFile) -> dict:
        content_type = (file.content_type or "application/octet-stream").lower()
        if content_type.startswith("image/") or content_type.startswith("video/"):
            return await upload_to_cloudinary(file)
        return await upload_to_uploadthing(file)
