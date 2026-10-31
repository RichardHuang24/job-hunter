"""File storage: a local folder, and S3 - against a stand-in client, or a
real S3-compatible server when TEST_S3_ENDPOINT is set (CI's Docker run
covers the Versity S3 Gateway end to end)."""

from __future__ import annotations

import os
import uuid

import pytest
from botocore.exceptions import ClientError

from app.config import Settings
from app.storage import LocalStorage, S3Storage, StorageError, check_key, get_storage


@pytest.mark.parametrize("key", ["../etc/passwd", "a/../../b", "/abs", "a//b", "", "a b", "x" * 300])
def test_keys_stay_inside(key):
    with pytest.raises(ValueError):
        check_key(key)


def test_local_storage(tmp_path):
    store = LocalStorage(tmp_path / "files")
    store.put("users/1/documents/a.pdf", b"%PDF", "application/pdf")
    assert store.get("users/1/documents/a.pdf") == b"%PDF"
    assert not list((tmp_path / "files").rglob("*.part"))
    store.delete("users/1/documents/a.pdf")
    store.delete("users/1/documents/a.pdf")  # already gone: fine
    with pytest.raises(StorageError, match="No file"):
        store.get("users/1/documents/a.pdf")


def test_which_storage(tmp_path):
    assert isinstance(get_storage(Settings(storage_backend="local", storage_dir=str(tmp_path))), LocalStorage)
    s3 = get_storage(Settings(storage_backend="s3", s3_bucket="b", s3_endpoint_url="http://storage:7070",
                              s3_access_key_id="k", s3_secret_access_key="s", s3_region="us-east-1"))
    assert isinstance(s3, S3Storage) and s3.client.meta.endpoint_url == "http://storage:7070"
    with pytest.raises(StorageError, match="local or s3"):
        get_storage(Settings(storage_backend="ftp"))


class Stub:
    """Just enough of a boto3 S3 client."""

    def __init__(self, bucket_exists=True):
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple] = []
        self.bucket_exists = bucket_exists

    @staticmethod
    def _error(code):
        return ClientError({"Error": {"Code": code, "Message": code}}, "op")

    def head_bucket(self, Bucket):
        self.calls.append(("head_bucket", Bucket))
        if not self.bucket_exists:
            raise self._error("404")

    def create_bucket(self, Bucket):
        self.calls.append(("create_bucket", Bucket))
        self.bucket_exists = True

    def put_object(self, Bucket, Key, Body, ContentType):
        self.calls.append(("put_object", Bucket, Key, ContentType))
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise self._error("NoSuchKey")

        class Body:
            def read(inner):
                return self.objects[Key]
        return {"Body": Body()}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)


def test_s3_storage_makes_its_bucket_once():
    stub = Stub(bucket_exists=False)
    store = S3Storage("job-hunter", client=stub)
    store.put("users/1/a.pdf", b"%PDF", "application/pdf")
    store.put("users/1/b.pdf", b"%PDF", "application/pdf")
    assert stub.calls[:3] == [("head_bucket", "job-hunter"), ("create_bucket", "job-hunter"),
                              ("put_object", "job-hunter", "users/1/a.pdf", "application/pdf")]
    assert [c[0] for c in stub.calls].count("head_bucket") == 1
    assert store.get("users/1/a.pdf") == b"%PDF"
    store.delete("users/1/a.pdf")
    with pytest.raises(StorageError, match="No file"):
        store.get("users/1/a.pdf")


def test_s3_errors_are_storage_errors():
    class Denied(Stub):
        def head_bucket(self, Bucket):
            raise self._error("403")
    with pytest.raises(StorageError, match="Can't use the bucket"):
        S3Storage("job-hunter", client=Denied()).put("a.pdf", b"x", "application/pdf")


ENDPOINT = os.environ.get("TEST_S3_ENDPOINT", "")


@pytest.mark.skipif(not ENDPOINT, reason="set TEST_S3_ENDPOINT (and TEST_S3_KEY, TEST_S3_SECRET) to use a real S3 server")
def test_a_real_s3_server():
    store = S3Storage(f"test-{uuid.uuid4().hex[:8]}", endpoint_url=ENDPOINT, region="us-east-1",
                      access_key_id=os.environ["TEST_S3_KEY"], secret_access_key=os.environ["TEST_S3_SECRET"])
    store.put("users/1/documents/x.pdf", b"%PDF-1.7 real", "application/pdf")
    assert store.get("users/1/documents/x.pdf") == b"%PDF-1.7 real"
    store.delete("users/1/documents/x.pdf")
    with pytest.raises(StorageError):
        store.get("users/1/documents/x.pdf")
