from urllib.parse import unquote, urlparse

from app.core.config import settings


def normalize_image_key(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        path = unquote(parsed.path.lstrip("/"))
        bucket_prefix = f"{settings.BUCKET_NAME}/"
        if path.startswith(bucket_prefix):
            path = path[len(bucket_prefix) :]
        return path or None
    return value


def build_image_url(image_key: str | None, s3_public_sign) -> str | None:
    if not image_key:
        return None
    return s3_public_sign.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.BUCKET_NAME, "Key": image_key},
        ExpiresIn=settings.PRESIGNED_URL_EXPIRES_SECONDS,
    )
