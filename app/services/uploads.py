import io
import os
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError


ALLOWED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


async def read_validated_image(file: UploadFile) -> bytes:
    maximum = int(os.getenv("MAX_UPLOAD_BYTES", "10485760"))
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(415, "Format d'image non autorisé")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(415, "Extension d'image non autorisée")
    content = await file.read(maximum + 1)
    if not content:
        raise HTTPException(400, "Image vide")
    if len(content) > maximum:
        raise HTTPException(413, "Image trop volumineuse")
    try:
        Image.MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", "40000000"))
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            if image.format != ALLOWED_MIME_TYPES[file.content_type]:
                raise HTTPException(415, "Le contenu ne correspond pas au type déclaré")
            max_width = int(os.getenv("MAX_IMAGE_WIDTH", "8192"))
            max_height = int(os.getenv("MAX_IMAGE_HEIGHT", "8192"))
            if image.width > max_width or image.height > max_height:
                raise HTTPException(413, "Dimensions d'image excessives")
            image.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "Image invalide") from None
    return content
