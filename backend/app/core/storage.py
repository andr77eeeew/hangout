import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

_s3_client = None
_s3_public_sign_client = None


def _build_client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.BUCKET_USER,
        aws_secret_access_key=settings.BUCKET_PASSWORD.get_secret_value(),
        region_name=settings.BUCKET_REGION,
        config=Config(signature_version="s3v4"),
    )


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = _build_client(settings.BUCKET_ENDPOINT_URL)
    return _s3_client


def get_s3_public_sign_client():
    global _s3_public_sign_client
    if _s3_public_sign_client is None:
        _s3_public_sign_client = _build_client(settings.BUCKET_PUBLIC_URL)
    return _s3_public_sign_client


async def ensure_bucket_exists():
    client = get_s3_client()
    try:
        await run_in_threadpool(client.head_bucket, Bucket=settings.BUCKET_NAME)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchBucket", "NotFound"}:
            await run_in_threadpool(client.create_bucket, Bucket=settings.BUCKET_NAME)
        else:
            raise
