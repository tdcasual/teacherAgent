#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def normalize_answer(value: str) -> str:
    s = (value or "").strip().upper()
    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return s
    return "".join(sorted(set(letters))) if len(letters) > 1 else "".join(letters)


def load_answers(path: Path):
    answers = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row.get("question_id") or row.get("question_no")
            if not qid:
                continue
            correct = normalize_answer(row.get("correct_answer", ""))
            if correct:
                answers[qid] = correct
    return answers


def load_max_scores(path: Path):
    scores = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row.get("question_id")
            if not qid:
                continue
            max_score = row.get("max_score")
            if max_score is None or max_score == "":
                continue
            try:
                scores[qid] = float(max_score)
            except Exception:
                continue
    return scores


def score_objective(raw_answer: str, correct: str, max_score: float):
    if not raw_answer:
        return 0.0, 0
    raw = normalize_answer(raw_answer)
    if not raw:
        return 0.0, 0

    if len(correct) == 1:
        return (max_score if raw == correct else 0.0), (1 if raw == correct else 0)

    correct_set = set(correct)
    raw_set = set(raw)
    if raw_set == correct_set:
        return max_score, 1
    if raw_set.issubset(correct_set):
        # Multi-select partial credit: no wrong option but missed some correct options.
        # Rule: 全对满分，漏选得一半分，错选 0 分。
        return max_score * 0.5, 0
    return 0.0, 0


def main():
    parser = argparse.ArgumentParser(description="Apply answer key to responses.csv")
    parser.add_argument("--responses", required=True, help="Input responses.csv")
    parser.add_argument("--answers", required=True, help="answers.csv with correct_answer")
    parser.add_argument("--questions", required=True, help="questions.csv with max_score")
    parser.add_argument("--out", required=True, help="Output responses_scored.csv")
    args = parser.parse_args()

    answers = load_answers(Path(args.answers))
    max_scores = load_max_scores(Path(args.questions))

    in_path = Path(args.responses)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with in_path.open(encoding="utf-8") as f_in, out_path.open("w", newline="", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])
        if "is_correct" not in fieldnames:
            fieldnames.append("is_correct")

        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            qid = row.get("question_id")
            raw_answer = row.get("raw_answer", "")
            score_val = row.get("score", "")

            if (score_val is None or score_val == "") and qid in answers and qid in max_scores:
                score, is_correct = score_objective(raw_answer, answers[qid], max_scores[qid])
                row["score"] = str(int(score)) if score.is_integer() else str(score)
                row["is_correct"] = str(is_correct)
            else:
                if "is_correct" not in row:
                    row["is_correct"] = ""
            writer.writerow(row)

    print(f"[OK] Wrote {out_path}")


if __name__ == "__main__":
    main()
