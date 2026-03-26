import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings


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
    return _build_client(settings.BUCKET_ENDPOINT_URL)


def get_s3_public_sign_client():
    return _build_client(settings.BUCKET_PUBLIC_URL)


def ensure_bucket_exists():
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.BUCKET_NAME)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchBucket", "NotFound"}:
            client.create_bucket(Bucket=settings.BUCKET_NAME)
        else:
            raise e