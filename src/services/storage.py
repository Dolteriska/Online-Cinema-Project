# src/services/storage.py
import uuid
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from src.config.settings import settings


class S3StorageService:
    def __init__(self):
        self._internal_client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT_INTERNAL,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._public_client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT_PUBLIC,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self.bucket = settings.MINIO_BUCKET_NAME
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self._internal_client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._internal_client.create_bucket(Bucket=self.bucket)

    def upload_avatar(self, file_bytes: bytes, user_id: int, content_type: str) -> str:
        ext = content_type.split("/")[-1] or "jpg"
        key = f"avatars/{user_id}/{uuid.uuid4()}.{ext}"
        self._internal_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return key

    def get_avatar_url(self, key: str, expires_in: int = 3600) -> str:
        return self._public_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_avatar(self, key: str):
        self._internal_client.delete_object(Bucket=self.bucket, Key=key)


storage_service = S3StorageService()
