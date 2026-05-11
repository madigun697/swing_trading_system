"""Command-line interface for Swing system operations."""

from __future__ import annotations

import argparse
import json
from typing import Any, Sequence

from swing_trading_system.config import Settings
from swing_trading_system.db import check_database_connection, initialize_schema
from swing_trading_system.repositories.shared_market import SharedMarketRepository
from swing_trading_system.storage import check_minio_connection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swing trading system operational CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check-connection", help="Check PostgreSQL and MinIO connectivity")
    subparsers.add_parser("check-readiness", help="Check required Quant shared relations")
    subparsers.add_parser("init-db", help="Initialize Swing-owned schemas and tables")
    return parser


def _json_default(value: Any) -> str:
    return str(value)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, default=_json_default, sort_keys=True))


def handle_check_connection(settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    settings = settings or Settings()
    database = check_database_connection(settings)
    try:
        minio_ok = check_minio_connection(settings)
        minio_detail = "connected"
    except Exception as exc:
        minio_ok = False
        minio_detail = f"{type(exc).__name__}: {exc}"
    ok = database.ok and minio_ok
    return (
        0 if ok else 1,
        {
            "ok": ok,
            "database": {"ok": database.ok, "detail": database.detail},
            "minio": {"ok": minio_ok, "detail": minio_detail},
        },
    )


def handle_check_readiness(settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    readiness = SharedMarketRepository(settings).check_readiness()
    return (0 if readiness.ok else 1, readiness.to_dict())


def handle_init_db(settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    result = initialize_schema(settings)
    return (0, {"ok": True, **result})


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings()

    if args.command == "check-connection":
        code, payload = handle_check_connection(settings)
    elif args.command == "check-readiness":
        code, payload = handle_check_readiness(settings)
    elif args.command == "init-db":
        code, payload = handle_init_db(settings)
    else:  # pragma: no cover - argparse prevents this path.
        parser.error(f"unknown command: {args.command}")

    _print_json(payload)
    return code


def main(argv: Sequence[str] | None = None) -> None:
    raise SystemExit(run(argv))


if __name__ == "__main__":
    main()
