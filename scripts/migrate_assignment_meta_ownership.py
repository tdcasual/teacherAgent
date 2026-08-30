#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.assignment_meta_ownership_migrate_service import (  # noqa: E402
    MigrationPreflightError,
    migrate_assignment_meta_ownership,
)
from services.api.config import DATA_DIR, UPLOADS_DIR  # noqa: E402


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate assignment meta.json ownership without DEFAULT_TEACHER_ID."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write migrated meta.json files. Default is dry-run.",
    )
    parser.add_argument(
        "--data-dir",
        default=str(DATA_DIR),
        help="Tenant data directory containing assignments/ and auth/.",
    )
    parser.add_argument(
        "--uploads-dir",
        default=str(UPLOADS_DIR),
        help="Uploads directory containing assignment_jobs/.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        result = migrate_assignment_meta_ownership(
            data_dir=Path(args.data_dir),
            uploads_dir=Path(args.uploads_dir),
            apply=bool(args.apply),
        )
    except MigrationPreflightError as exc:
        print(exc.code, file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    counts = result.get("counts") or {}
    print(
        "migrated={migrated} skipped={skipped} orphan={orphan} "
        "needs_subject_review={needs_subject_review} "
        "needs_roster_review={needs_roster_review} retired_auto={retired_auto}".format(
            migrated=counts.get("migrated", 0),
            skipped=counts.get("skipped", 0),
            orphan=counts.get("orphan", 0),
            needs_subject_review=counts.get("needs_subject_review", 0),
            needs_roster_review=counts.get("needs_roster_review", 0),
            retired_auto=counts.get("retired_auto", 0),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
