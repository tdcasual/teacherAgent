#!/usr/bin/env python3
import argparse
import csv
import re
from pathlib import Path


def parse_review_md(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_table = False
    rows = []
    for line in lines:
        if line.strip().startswith("| example_id"):
            in_table = True
            continue
        if in_table:
            if not line.strip().startswith("|"):
                break
            # skip separator
            if "---" in line:
                continue
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) < 3:
                continue
            ex_id, kp_candidates, confirm = parts[0], parts[1], parts[2]
            rows.append({
                "example_id": ex_id,
                "kp_candidates": kp_candidates,
                "confirm": confirm,
            })
    return rows


def extract_confirmed_kps(confirm: str, kp_candidates: str):
    # Accept checkbox markers: ☑, [x], [X], yes
    if any(tok in confirm for tok in ["☑", "[x]", "[X]", "yes", "是"]):
        return [kp.strip() for kp in kp_candidates.split(",") if kp.strip()]
    return []


def load_examples(path: Path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_examples(path: Path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main():
    parser = argparse.ArgumentParser(description="Apply confirmed KP candidates from lesson_review.md")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--base-dir", default="data/lessons")
    parser.add_argument("--review", help="path to lesson_review.md (defaults to lesson folder)")
    parser.add_argument("--examples", help="path to examples.csv (defaults to lesson folder)")
    parser.add_argument("--out", help="output examples.csv (defaults to overwrite)")
    args = parser.parse_args()

    lesson_dir = Path(args.base_dir) / args.lesson_id
    review_path = Path(args.review) if args.review else lesson_dir / "lesson_review.md"
    examples_path = Path(args.examples) if args.examples else lesson_dir / "examples.csv"

    if not review_path.exists():
        raise SystemExit(f"review file not found: {review_path}")
    if not examples_path.exists():
        raise SystemExit(f"examples file not found: {examples_path}")

    review_rows = parse_review_md(review_path)
    confirmed_map = {}
    for row in review_rows:
        confirmed = extract_confirmed_kps(row.get("confirm", ""), row.get("kp_candidates", ""))
        if confirmed:
            confirmed_map[row["example_id"]] = ",".join(confirmed)

    examples = load_examples(examples_path)
    updated = 0
    for ex in examples:
        ex_id = ex.get("example_id")
        if ex_id in confirmed_map:
            ex["kp_candidate"] = confirmed_map[ex_id]
            updated += 1

    out_path = Path(args.out) if args.out else examples_path
    save_examples(out_path, examples)

    print(f"[OK] Updated {updated} examples with confirmed KP candidates")
    print(f"[OK] Wrote {out_path}")


if __name__ == "__main__":
    main()
