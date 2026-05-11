"""Shared storage clients for PostgreSQL and MinIO."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import boto3
import psycopg
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from psycopg.rows import dict_row

from swing_trading_system.config import Settings, get_settings


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
def postgres_connection(settings: Settings | None = None) -> Iterator[psycopg.Connection]:
    settings = settings or get_settings()
    with psycopg.connect(settings.postgres_dsn, row_factory=dict_row) as conn:
        yield conn


def check_minio_connection(settings: Settings | None = None) -> bool:
    client = make_s3_client(settings)
    client.list_buckets()
    return True


def ensure_bucket(bucket: str, settings: Settings | None = None) -> None:
    client = make_s3_client(settings)
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        client.create_bucket(Bucket=bucket)
