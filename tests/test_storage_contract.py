"""Storage registry and LocalStorage contract tests."""

from __future__ import annotations

import os
import uuid

import pytest

from src.infrastructure.storage.factory import get_storage, reset_storage
from src.infrastructure.storage.local import LocalStorage
from src.infrastructure.storage.registry import (
    STORAGE_REGISTRY,
    create_storage,
    list_storage_backends,
)


def test_list_storage_backends_includes_aliases():
    names = list_storage_backends()
    assert names == sorted(["local", "s3", "minio", "r2"])
    assert set(STORAGE_REGISTRY.keys()) == set(names)


def test_create_storage_local():
    backend = create_storage("local")
    assert isinstance(backend, LocalStorage)


def test_create_storage_unknown():
    with pytest.raises(ValueError, match="Unknown STORAGE_BACKEND"):
        create_storage("azure-blob")


def test_get_storage_singleton_reset(monkeypatch):
    reset_storage()
    monkeypatch.setattr(
        "src.infrastructure.storage.registry.settings.STORAGE_BACKEND", "local"
    )
    a = get_storage()
    b = get_storage()
    assert a is b
    reset_storage()
    c = get_storage()
    assert c is not a


def test_local_storage_contract():
    store = LocalStorage()
    prefix = f"data/uploads/contract-{uuid.uuid4().hex}"
    key = f"{prefix}/demo.bin"
    other = f"{prefix}/other.bin"

    store.put_bytes(key, b"hello")
    assert store.exists(key)
    assert store.get_size(key) == 5
    assert store.health_check() is True

    size = store.append_bytes(key, b"-world")
    assert size == 11
    assert store.get_size(key) == 11

    local = store.ensure_local(key)
    assert local.exists()
    assert local.read_bytes() == b"hello-world"

    store.put_bytes(other, b"x")
    store.delete_prefix(prefix)
    assert not store.exists(key)
    assert not store.exists(other)


@pytest.mark.skipif(
    os.environ.get("STORAGE_CONTRACT", "").lower() not in {"minio", "r2"},
    reason="Set STORAGE_CONTRACT=minio|r2 to run remote object storage contracts",
)
def test_optional_remote_storage_contract():
    reset_storage()
    name = os.environ.get("STORAGE_CONTRACT", "").lower()
    store = create_storage(name)
    key = f"contract/remote-{uuid.uuid4().hex}.bin"
    store.put_bytes(key, b"remote-ok")
    assert store.exists(key)
    assert store.get_size(key) == 9
    store.delete(key)
    assert not store.exists(key)
    reset_storage()


def test_create_storage_r2_requires_endpoint(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.storage.r2.settings.S3_ENDPOINT_URL", ""
    )
    with pytest.raises(ValueError, match="S3_ENDPOINT_URL"):
        create_storage("r2")


def test_r2_defaults_region_auto_and_path_style(monkeypatch):
    from unittest.mock import patch

    from src.infrastructure.storage.r2 import R2Storage

    monkeypatch.setattr(
        "src.infrastructure.storage.r2.settings.S3_ENDPOINT_URL",
        "https://abc123.r2.cloudflarestorage.com",
    )
    monkeypatch.setattr(
        "src.infrastructure.storage.r2.settings.S3_REGION", "us-east-1"
    )
    monkeypatch.setattr(
        "src.infrastructure.storage.r2.settings.S3_ADDRESSING_STYLE", ""
    )
    monkeypatch.setattr(
        "src.infrastructure.storage.r2.settings.S3_BUCKET", "onstream"
    )
    monkeypatch.setattr(
        "src.infrastructure.storage.s3.settings.S3_BUCKET", "onstream"
    )
    monkeypatch.setattr(
        "src.infrastructure.storage.s3.settings.S3_ACCESS_KEY", "key"
    )
    monkeypatch.setattr(
        "src.infrastructure.storage.s3.settings.S3_SECRET_KEY", "secret"
    )
    monkeypatch.setattr(
        "src.infrastructure.storage.s3.settings.S3_ADDRESSING_STYLE", ""
    )

    with patch("boto3.client") as client:
        R2Storage()
        kwargs = client.call_args.kwargs
        assert kwargs["region_name"] == "auto"
        assert kwargs["endpoint_url"] == "https://abc123.r2.cloudflarestorage.com"
        assert kwargs["config"].s3["addressing_style"] == "path"


def test_minio_requires_endpoint_in_production(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.storage.registry.settings.ENV", "production"
    )
    monkeypatch.setattr(
        "src.infrastructure.storage.registry.settings.S3_ENDPOINT_URL", ""
    )
    with pytest.raises(ValueError, match="S3_ENDPOINT_URL"):
        create_storage("minio")
