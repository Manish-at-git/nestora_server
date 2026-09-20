"""Cloudinary adapter for image and video uploads."""

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings


async def upload_to_cloudinary(file: UploadFile) -> dict:
    """Upload visual media without exposing provider details to feature modules."""
    settings = get_settings()
    if not all((settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloudinary storage is not configured",
        )
    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=True,
        )
        result = cloudinary.uploader.upload(
            file.file,
            resource_type="auto",
            folder=settings.cloudinary_folder,
            use_filename=True,
            unique_filename=True,
        )
    except ImportError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Cloudinary dependency is not installed") from exc
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Cloudinary upload failed") from exc
    return {
        "ok": True,
        "url": result["secure_url"],
        "filename": file.filename,
        "asset_type": "media",
        "provider": "cloudinary",
    }
