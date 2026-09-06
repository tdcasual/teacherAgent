#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.assignment.store import (  # noqa: E402
    SCHEMA_V2,
    connect,
    ensure,
    has_migration,
)
from services.api.config import DATA_DIR  # noqa: E402


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "One-shot import of assignment JSON into auth_registry.sqlite3. "
            "Default --apply is a no-op after migrations v2. "
            "--force-scan resurrects crash orphans and is ops-only, not a boot path."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply schema/import. No-op when assignment_schema_migrations v2 is present.",
    )
    parser.add_argument(
        "--force-scan",
        action="store_true",
        help="Re-scan JSON after v2. Resurrects crash orphans; do not use on boot.",
    )
    parser.add_argument(
        "--data-dir",
        default=str(DATA_DIR),
        help="Tenant data directory containing assignments/ and auth/.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    data_dir = Path(args.data_dir)
    conn = connect(data_dir)
    try:
        try:
            already = has_migration(conn, SCHEMA_V2)
        except sqlite3.OperationalError:
            already = False
        if args.apply or args.force_scan:
            ensure(conn, data_dir=data_dir, force_scan=bool(args.force_scan))
        try:
            applied = has_migration(conn, SCHEMA_V2)
        except sqlite3.OperationalError:
            applied = False
    finally:
        conn.close()
    print(
        json.dumps(
            {
                "ok": True,
                "data_dir": str(data_dir),
                "v2_applied": applied,
                "noop": bool(already) and not args.force_scan,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
