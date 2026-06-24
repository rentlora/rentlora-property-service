"""Image storage module for Rentlora property images.

Production flow (S3_BUCKET is set):
  1. Backend generates a presigned PUT URL for direct browser→S3 upload.
  2. Browser uploads the file directly to S3 (no data through EC2).
  3. An S3-triggered Lambda resizes the image into thumbnail/medium/original variants.
  4. CloudFront serves all variants globally.

Local dev flow (S3_BUCKET is empty):
  1. Backend receives the file, resizes it with Pillow, and saves locally.
  2. The file is served via FastAPI's StaticFiles mount at /uploads/.
"""

import io
import logging
import os
import uuid

import boto3
from config import get_settings
from fastapi import HTTPException, UploadFile
from metrics import emit_metric
from PIL import Image

logger = logging.getLogger("property-service.storage")
settings = get_settings()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


def _get_s3_client():
    return boto3.client("s3", region_name=settings.aws_default_region)


def _safe_extension(filename: str, content_type: str) -> str:
    """Derive a safe file extension from the filename or content type."""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in ALLOWED_EXTENSIONS:
            return ext
    # Fallback from content type
    return content_type.split("/")[-1].replace("jpeg", "jpg")


# ─── Production: Presigned URL flow (browser uploads direct to S3) ───

def generate_presigned_upload(property_id: int, filename: str, content_type: str) -> dict:
    """Return a presigned S3 PUT URL so the browser can upload directly.

    Also returns the final CDN URLs for all three image variants
    (the Lambda will create medium/ and thumbnails/ copies automatically).
    """
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only jpg, png, webp files are allowed")
    if not settings.s3_bucket:
        raise HTTPException(status_code=503, detail="S3 is not configured — use local upload endpoint")

    ext = _safe_extension(filename, content_type)
    image_id = str(uuid.uuid4())
    key = f"originals/properties/{property_id}/{image_id}.{ext}"

    s3 = _get_s3_client()
    try:
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.s3_bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=300,  # 5 minutes
        )
    except Exception as e:
        logger.error("Failed to generate presigned URL: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")

    cdn_base = f"https://{settings.cloudfront_domain}" if settings.cloudfront_domain else f"https://{settings.s3_bucket}.s3.{settings.aws_default_region}.amazonaws.com"

    cdn_urls = {
        "original": f"{cdn_base}/originals/properties/{property_id}/{image_id}.{ext}",
        "medium": f"{cdn_base}/medium/properties/{property_id}/{image_id}.webp",
        "thumbnail": f"{cdn_base}/thumbnails/properties/{property_id}/{image_id}.webp",
    }

    logger.info(
        "Generated presigned upload URL for property %d (key=%s)",
        property_id,
        key,
    )

    return {
        "upload_url": upload_url,
        "key": key,
        "cdn_urls": cdn_urls,
    }


# ─── Local dev: Direct upload through EC2 (PIL resize + local storage) ───

async def upload_property_image_local(property_id: int, file: UploadFile) -> str:
    """Handle image upload in local dev mode (no S3).

    Receives the file, resizes with Pillow, and saves to local disk.
    Returns the local URL path.
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only jpg, png, webp files are allowed")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 5MB limit")

    try:
        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)

        compressed_io = io.BytesIO()
        img.save(compressed_io, format="WEBP", quality=80, method=4)
        compressed_data = compressed_io.getvalue()
        logger.info("Compressed image for property %d to %d bytes", property_id, len(compressed_data))
    except Exception as e:
        logger.error("Failed to process image for property %d: %s", property_id, e)
        raise HTTPException(status_code=500, detail="Failed to process image")

    base_dir = os.path.abspath(settings.uploads_dir)
    target_dir = os.path.join(base_dir, "properties", str(property_id))
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}.webp"
    target_path = os.path.join(target_dir, filename)

    with open(target_path, "wb") as f:
        f.write(compressed_data)

    emit_metric("Rentlora", "ImageUploadCount", 1, dimensions={"Service": "property-service"})
    emit_metric("Rentlora", "ImageUploadSize", len(compressed_data), unit="Bytes", dimensions={"Service": "property-service"})

    return f"/uploads/properties/{property_id}/{filename}"
