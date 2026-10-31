"""Where generated files (CV PDFs) are kept.

STORAGE_BACKEND picks one:

- "local" (the default, for development and tests): files under STORAGE_DIR.
- "s3": any S3-compatible service - the Versity S3 Gateway in the Docker
  setup, or Cloudflare R2, AWS S3 and the like in production
  (docs/self-hosting.md). The bucket is created on first use if it's missing.

Keys look like "users/<id>/documents/<id>.pdf". Nothing here is public:
files are served through the API, to their owner only.
"""

from __future__ import annotations

import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import Settings, get_settings

_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")


class StorageError(RuntimeError):
    pass


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


def check_key(key: str) -> str:
    if not _KEY.match(key) or ".." in key.split("/") or "//" in key:
        raise ValueError(f"Not a storage key: {key!r}")
    return key


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / check_key(key)).resolve()
        if self.root not in path.parents:
            raise ValueError(f"Not a storage key: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(path.name + ".part")
        partial.write_bytes(data)
        os.replace(partial, path)  # readers never see half a file

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(f"No file at {key}") from exc

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self, bucket: str, *, endpoint_url: str = "", region: str = "", access_key_id: str = "",
                 secret_access_key: str = "", client=None):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = client or boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region or None,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            # Path-style works with every S3-compatible server; R2 and AWS accept it too.
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3, "mode": "standard"},
                          connect_timeout=5, read_timeout=30, signature_version="s3v4"),
        )
        self._ready = False
        self._lock = threading.Lock()

    def _ensure_bucket(self) -> None:
        if self._ready:
            return
        from botocore.exceptions import ClientError

        with self._lock:
            if self._ready:
                return
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except ClientError as exc:
                if str(exc.response.get("Error", {}).get("Code")) not in ("404", "NoSuchBucket", "NotFound"):
                    raise StorageError(f"Can't use the bucket {self.bucket!r}: {exc}") from exc
                self.client.create_bucket(Bucket=self.bucket)
            self._ready = True

    def _call(self, what: str, fn, **kwargs):
        from botocore.exceptions import BotoCoreError, ClientError

        self._ensure_bucket()
        try:
            return fn(Bucket=self.bucket, **kwargs)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code"))
            if code in ("NoSuchKey", "404", "NotFound"):
                raise StorageError(f"No file at {kwargs.get('Key')}") from exc
            raise StorageError(f"Storage couldn't {what}: {code}") from exc
        except BotoCoreError as exc:
            raise StorageError(f"Storage couldn't {what}: {exc}") from exc

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._call("save the file", self.client.put_object, Key=check_key(key), Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self._call("read the file", self.client.get_object, Key=check_key(key))["Body"].read()

    def delete(self, key: str) -> None:
        self._call("delete the file", self.client.delete_object, Key=check_key(key))


@lru_cache
def _cached(backend: str, location: str, endpoint: str, region: str, key_id: str, secret: str) -> Storage:
    if backend == "s3":
        return S3Storage(location, endpoint_url=endpoint, region=region, access_key_id=key_id, secret_access_key=secret)
    return LocalStorage(location)


def get_storage(settings: Settings | None = None) -> Storage:
    settings = settings or get_settings()
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise StorageError("STORAGE_BACKEND is s3 but S3_BUCKET isn't set.")
        return _cached("s3", settings.s3_bucket, settings.s3_endpoint_url, settings.s3_region,
                       settings.s3_access_key_id, settings.s3_secret_access_key)
    if settings.storage_backend != "local":
        raise StorageError(f"STORAGE_BACKEND must be local or s3, not {settings.storage_backend!r}.")
    return _cached("local", settings.storage_dir or str(Path("data") / "files"), "", "", "", "")
