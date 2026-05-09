from __future__ import annotations

import json
from contextlib import contextmanager
from hashlib import sha256
from typing import Any, Iterator

import boto3
import psycopg
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from psycopg.rows import dict_row

from swing_trading_system.config import Settings, get_settings

_bucket_cache: dict[str, bool] = {}


def make_s3_client(settings: Settings | None = None) -> BaseClient:
    settings = settings or get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_root_user,
        aws_secret_access_key=settings.minio_root_password,
        region_name=settings.minio_region,
    )


@contextmanager
def postgres_connection(settings: Settings | None = None, *, read_only: bool = False) -> Iterator[psycopg.Connection]:
    settings = settings or get_settings()
    with psycopg.connect(settings.postgres_dsn, row_factory=dict_row) as conn:
        if read_only or settings.postgres_readonly:
            conn.execute("set transaction read only")
        yield conn


def ensure_bucket(bucket: str, settings: Settings | None = None) -> None:
    if bucket in _bucket_cache:
        return
    settings = settings or get_settings()
    client = make_s3_client(settings)
    try:
        client.head_bucket(Bucket=bucket)
        _bucket_cache[bucket] = True
    except ClientError:
        client.create_bucket(Bucket=bucket)
        _bucket_cache[bucket] = True


def upload_json(bucket: str, object_key: str, payload: Any, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    ensure_bucket(bucket, settings)
    body = json.dumps(payload, default=str, indent=2).encode("utf-8")
    checksum = sha256(body).hexdigest()
    make_s3_client(settings).put_object(
        Bucket=bucket,
        Key=object_key,
        Body=body,
        ContentType="application/json",
    )
    return checksum
