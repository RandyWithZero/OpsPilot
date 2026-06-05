from __future__ import annotations

import os
import secrets
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .domain import InvalidInput, NotFound


class ObjectStorage(ABC):
    provider = "unknown"

    @abstractmethod
    def ensure_bucket(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def put(self, key: str, content: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    def capability_url(self, purpose: str, capability_id: str) -> str:
        if purpose not in {"upload", "download"}:
            raise InvalidInput("unsupported file capability")
        token = secrets.token_urlsafe(18)
        return f"opspilot://file-capabilities/{purpose}/{capability_id}/{token}"


class LocalFileStorage(ObjectStorage):
    provider = "local"

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or os.environ.get("OPSPILOT_FILE_STORAGE_ROOT", "/tmp/opspilot-foundation-files"))

    def ensure_bucket(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, content: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise NotFound("stored object not found")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def _path(self, key: str) -> Path:
        if key.startswith("/") or ".." in Path(key).parts:
            raise InvalidInput("storage key is invalid")
        return self.root / key


class S3CompatibleStorage(ObjectStorage):
    provider = "s3"

    def __init__(self, client: Any | None = None) -> None:
        self.endpoint_url = os.environ.get("OPSPILOT_S3_ENDPOINT_URL", "")
        self.bucket = os.environ.get("OPSPILOT_S3_BUCKET", "")
        self.region = os.environ.get("OPSPILOT_S3_REGION", "")
        self.auto_create_bucket = os.environ.get("OPSPILOT_S3_AUTO_CREATE_BUCKET", "true").lower() != "false"
        self.client = client

    def ensure_bucket(self) -> None:
        if not self.bucket:
            raise InvalidInput("OPSPILOT_S3_BUCKET is required for s3 storage")
        client = self._client()
        try:
            client.head_bucket(Bucket=self.bucket)
        except Exception as exc:
            if not self.auto_create_bucket:
                raise NotFound("s3 bucket not found") from exc
            kwargs: dict[str, Any] = {"Bucket": self.bucket}
            if self.region and self.region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
            client.create_bucket(**kwargs)

    def put(self, key: str, content: bytes) -> None:
        self._validate_key(key)
        self._client().put_object(Bucket=self.bucket, Key=key, Body=content)

    def get(self, key: str) -> bytes:
        self._validate_key(key)
        try:
            response = self._client().get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise NotFound("stored object not found") from exc
        body = response["Body"]
        return body.read() if hasattr(body, "read") else bytes(body)

    def delete(self, key: str) -> None:
        self._validate_key(key)
        self._client().delete_object(Bucket=self.bucket, Key=key)

    def _client(self) -> Any:
        if self.client is None:
            try:
                import boto3  # type: ignore
            except ImportError as exc:
                raise RuntimeError("S3-compatible object storage requires the optional boto3 package") from exc
            kwargs: dict[str, Any] = {}
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            if self.region:
                kwargs["region_name"] = self.region
            self.client = boto3.client("s3", **kwargs)
        return self.client

    def _validate_key(self, key: str) -> None:
        if key.startswith("/") or ".." in Path(key).parts:
            raise InvalidInput("storage key is invalid")


def storage_from_env() -> ObjectStorage:
    adapter = os.environ.get("OPSPILOT_OBJECT_STORAGE_ADAPTER", "local").strip().lower()
    if adapter == "local":
        return LocalFileStorage()
    if adapter in {"s3", "minio"}:
        return S3CompatibleStorage()
    raise InvalidInput("unsupported object storage adapter")
