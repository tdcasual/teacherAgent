#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def load_examples(path: Path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_question_map(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_question_map(path: Path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Apply confirmed KP candidates to knowledge_point_map.csv")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--base-dir", default="data/lessons")
    parser.add_argument("--examples", help="examples.csv path (default: lesson folder)")
    parser.add_argument("--question-map", default="data/knowledge/knowledge_point_map.csv")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    lesson_dir = Path(args.base_dir) / args.lesson_id
    examples_path = Path(args.examples) if args.examples else lesson_dir / "examples.csv"
    question_map_path = Path(args.question_map)

    if not examples_path.exists():
        raise SystemExit(f"examples file not found: {examples_path}")

    examples = load_examples(examples_path)
    qmap = load_question_map(question_map_path)

    # Build mapping: example_id -> kp_candidate
    confirmed = {}
    for ex in examples:
        kp = (ex.get("kp_candidate") or "").strip()
        ex_id = ex.get("example_id")
        if kp and ex_id:
            confirmed[ex_id] = kp

    updated = 0
    if qmap:
        for row in qmap:
            qid = row.get("question_id")
            if qid in confirmed:
                row["kp_id"] = confirmed[qid]
                updated += 1
    else:
        # create new mapping file
        qmap = []
        for ex_id, kp in confirmed.items():
            qmap.append({"question_id": ex_id, "kp_id": kp})
        updated = len(qmap)

    if args.dry_run:
        print(f"[DRY RUN] would update {updated} rows in {question_map_path}")
        return

    question_map_path.parent.mkdir(parents=True, exist_ok=True)
    save_question_map(question_map_path, qmap)
    print(f"[OK] Updated {updated} rows in {question_map_path}")


if __name__ == "__main__":
    main()
