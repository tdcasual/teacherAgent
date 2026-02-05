#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def normalize_symbols(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "×": "x",
        "＊": "x",
        "*": "x",
        "＝": "=",
        "－": "-",
        "—": "-",
        "–": "-",
        "＋": "+",
        "·": ".",
        "．": ".",
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
    }
    out = text
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


def extract_answer_from_ref(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "答案" in line or line.lower().startswith("answer"):
            if "：" in line:
                return line.split("：", 1)[1].strip()
            if ":" in line:
                return line.split(":", 1)[1].strip()
            return line
    return text.splitlines()[0].strip() if text.strip() else ""


def get_expected_answer(row: Dict[str, Any], questions_path: Path) -> str:
    expected = (row.get("answer_text") or "").strip()
    if expected:
        return expected
    ref = (row.get("answer_ref") or "").strip()
    if not ref:
        return ""
    ref_path = Path(ref)
    if not ref_path.is_absolute():
        candidate = questions_path.parent / ref
        if candidate.exists():
            ref_path = candidate
    return extract_answer_from_ref(ref_path)


def read_questions(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return {row.get("question_id", ""): row for row in rows if row.get("question_id")}


def load_question_blocks(submission_dir: Path) -> Dict[str, str]:
    block_path = submission_dir / "ocr" / "question_blocks.json"
    if not block_path.exists():
        return {}
    try:
        data = json.loads(block_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    blocks: Dict[str, str] = {}
    if isinstance(data, list):
        for item in data:
            qid = item.get("question_id")
            text = item.get("text")
            if qid and text:
                blocks[str(qid)] = str(text)
    return blocks


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def iter_reports(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return list(root.rglob("grading_report.json"))


def main():
    parser = argparse.ArgumentParser(description="Prepare OCR grading baseline review CSV")
    parser.add_argument("--root", default="data/student_submissions", help="root dir to scan for grading_report.json")
    parser.add_argument("--out", help="output CSV path")
    parser.add_argument("--only-review", action="store_true", help="use review_queue.json items if present")
    parser.add_argument("--min-confidence", type=float, help="only include items with confidence <= value")
    parser.add_argument("--max-items", type=int, help="limit output rows")
    parser.add_argument("--truncate", type=int, default=400, help="truncate OCR text length")
    args = parser.parse_args()

    root = Path(args.root)
    reports = iter_reports(root)
    if not reports:
        raise SystemExit(f"No grading_report.json found under {root}")

    rows: List[Dict[str, Any]] = []
    for report_path in reports:
        submission_dir = report_path.parent
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        assignment_id = report.get("assignment_id") or ""
        student_id = report.get("student_id") or ""

        review_items = []
        if args.only_review:
            review_path = submission_dir / "review_queue.json"
            if review_path.exists():
                try:
                    review_data = json.loads(review_path.read_text(encoding="utf-8"))
                    review_items = review_data.get("items", []) if isinstance(review_data, dict) else []
                except Exception:
                    review_items = []

        items = review_items if review_items else report.get("items", [])
        if not isinstance(items, list):
            continue

        questions_map: Dict[str, Dict[str, Any]] = {}
        questions_path = None
        if assignment_id:
            qpath = Path("data/assignments") / assignment_id / "questions.csv"
            if qpath.exists():
                questions_map = read_questions(qpath)
                questions_path = qpath

        question_blocks = load_question_blocks(submission_dir)

        for item in items:
            qid = item.get("question_id") or ""
            if not qid:
                continue
            confidence = float(item.get("confidence") or 0.0)
            if args.min_confidence is not None and confidence > args.min_confidence:
                continue

            question_row = questions_map.get(qid, {})
            expected = ""
            rubric_ref = question_row.get("rubric_ref") or question_row.get("rubric") or ""
            if questions_path:
                expected = get_expected_answer(question_row, questions_path)

            ocr_text = question_blocks.get(qid, "")
            ocr_text = truncate(normalize_symbols(ocr_text), args.truncate) if ocr_text else ""

            rows.append(
                {
                    "assignment_id": assignment_id,
                    "student_id": student_id,
                    "submission_dir": str(submission_dir),
                    "question_id": qid,
                    "kp_id": item.get("kp_id") or "",
                    "status": item.get("status") or "",
                    "reason": item.get("reason") or "",
                    "score": item.get("score") or "",
                    "confidence": confidence,
                    "expected": expected,
                    "rubric_ref": rubric_ref,
                    "ocr_text": ocr_text,
                    "human_status": "",
                    "human_score": "",
                    "human_notes": "",
                }
            )

            if args.max_items and len(rows) >= args.max_items:
                break
        if args.max_items and len(rows) >= args.max_items:
            break

    if not rows:
        raise SystemExit("No rows collected. Adjust filters or review queue availability.")

    out_path = Path(args.out) if args.out else Path("output") / "ocr_eval" / f"ocr_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"[OK] Wrote baseline review CSV: {out_path}")
    print(f"[OK] Rows: {len(rows)}")


if __name__ == "__main__":
    main()
