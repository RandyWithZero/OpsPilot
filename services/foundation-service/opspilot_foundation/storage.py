from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

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

    def __init__(self) -> None:
        self.endpoint_url = os.environ.get("OPSPILOT_S3_ENDPOINT_URL", "")
        self.bucket = os.environ.get("OPSPILOT_S3_BUCKET", "")
        self.region = os.environ.get("OPSPILOT_S3_REGION", "")
        self.auto_create_bucket = os.environ.get("OPSPILOT_S3_AUTO_CREATE_BUCKET", "true").lower() != "false"

    def ensure_bucket(self) -> None:
        if not self.bucket:
            raise InvalidInput("OPSPILOT_S3_BUCKET is required for s3 storage")

    def put(self, key: str, content: bytes) -> None:
        raise NotImplementedError("S3-compatible object storage adapter is configured but no client is wired")

    def get(self, key: str) -> bytes:
        raise NotImplementedError("S3-compatible object storage adapter is configured but no client is wired")

    def delete(self, key: str) -> None:
        raise NotImplementedError("S3-compatible object storage adapter is configured but no client is wired")


def storage_from_env() -> ObjectStorage:
    adapter = os.environ.get("OPSPILOT_OBJECT_STORAGE_ADAPTER", "local").strip().lower()
    if adapter == "local":
        return LocalFileStorage()
    if adapter in {"s3", "minio"}:
        return S3CompatibleStorage()
    raise InvalidInput("unsupported object storage adapter")
