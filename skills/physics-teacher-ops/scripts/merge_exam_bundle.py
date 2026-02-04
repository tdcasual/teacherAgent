#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def to_rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path.resolve())


def read_csv(path: Path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_question_map(rows):
    mapping = {}
    for row in rows:
        raw_label = (row.get("raw_label") or "").strip() or row.get("question_id") or ""
        if not raw_label:
            continue
        if raw_label in mapping:
            continue
        mapping[raw_label] = {
            "raw_label": raw_label,
            "question_no": row.get("question_no") or "",
            "sub_no": row.get("sub_no") or "",
            "question_id": row.get("question_id") or "",
        }
    return list(mapping.values())


def main():
    parser = argparse.ArgumentParser(description="Bundle exam files into a manifest")
    parser.add_argument("--exam-id", required=True)
    parser.add_argument("--questions", required=True, help="questions.csv")
    parser.add_argument("--answers", required=True, help="answers.csv")
    parser.add_argument("--responses", required=True, help="responses.csv or responses_scored.csv")
    parser.add_argument("--out", help="manifest.json output path")
    parser.add_argument("--question-map-out", help="question_map.csv output path")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    questions = Path(args.questions)
    answers = Path(args.answers)
    responses = Path(args.responses)

    resp_rows = read_csv(responses)
    student_ids = {r.get("student_id") or r.get("student_name") for r in resp_rows}
    student_ids = {s for s in student_ids if s}

    question_map = build_question_map(resp_rows)

    if args.question_map_out:
        qmap_path = Path(args.question_map_out)
    else:
        qmap_path = root / "data" / "exams" / args.exam_id / "question_map.csv"

    qmap_path.parent.mkdir(parents=True, exist_ok=True)
    with qmap_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["raw_label", "question_no", "sub_no", "question_id"])
        writer.writeheader()
        for row in question_map:
            writer.writerow(row)

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = root / "data" / "exams" / args.exam_id / "manifest.json"

    manifest = {
        "exam_id": args.exam_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "files": {
            "questions": to_rel(questions, root),
            "answers": to_rel(answers, root),
            "responses": to_rel(responses, root),
            "question_map": to_rel(qmap_path, root),
        },
        "counts": {
            "students": len(student_ids),
            "responses": len(resp_rows),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Wrote {out_path}")
    print(f"[OK] Wrote {qmap_path}")


if __name__ == "__main__":
    main()
