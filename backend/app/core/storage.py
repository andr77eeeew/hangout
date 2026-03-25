import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.BUCKET_URL,
        aws_access_key_id=settings.BUCKET_USER,
        aws_secret_access_key=settings.BUCKET_PASSWORD,
        region_name=settings.BUCKET_REGION,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket_exists():
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.BUCKET_NAME)
    except ClientError:
        client.create_bucket(Bucket=settings.BUCKET_NAME)