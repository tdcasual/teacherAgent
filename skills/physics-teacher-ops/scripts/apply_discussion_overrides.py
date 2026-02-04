#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from pathlib import Path


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_notes(path: Path):
    if not path:
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(line)
    return lines


def main():
    parser = argparse.ArgumentParser(description="Apply discussion notes and overrides to a draft analysis")
    parser.add_argument("--draft", required=True, help="draft.json")
    parser.add_argument("--overrides", help="overrides.json")
    parser.add_argument("--notes", help="notes.md (one note per line)")
    parser.add_argument("--version", type=int, help="explicit version number")
    parser.add_argument("--out", required=True, help="output analysis json")
    args = parser.parse_args()

    draft = load_json(Path(args.draft))
    overrides = load_json(Path(args.overrides)) if args.overrides else {}
    notes = load_notes(Path(args.notes)) if args.notes else []

    version = args.version
    if version is None:
        base = draft.get("version")
        if isinstance(base, int):
            version = base + 1
        else:
            version = 1

    final = dict(draft)
    final["generated_at"] = datetime.now().isoformat(timespec="seconds")
    final["version"] = version
    final["status"] = "confirmed"
    if notes:
        final["discussion_notes"] = notes
    if overrides:
        final["overrides"] = overrides

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Wrote {out_path}")


if __name__ == "__main__":
    main()
