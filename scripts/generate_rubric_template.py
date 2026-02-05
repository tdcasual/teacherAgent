#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def read_questions(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def write_questions(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


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


def normalize_choice(value: str) -> str:
    if not value:
        return ""
    letters = re.findall(r"[A-D]", value.upper())
    if not letters:
        return ""
    if len(letters) == 1:
        return letters[0]
    return "".join(sorted(set(letters)))


def detect_answer_type(expected: str) -> str:
    if not expected:
        return "unknown"
    normalized = normalize_symbols(expected).strip()
    choice = normalize_choice(normalized)
    if choice:
        return "mcq_multi" if len(choice) > 1 else "mcq_single"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", normalized):
        return "numeric"
    return "text"


def extract_answer_text(row: Dict[str, Any], questions_path: Path) -> str:
    answer_text = (row.get("answer_text") or "").strip()
    if answer_text:
        return answer_text
    ref = (row.get("answer_ref") or "").strip()
    if not ref:
        return ""
    ref_path = Path(ref)
    if not ref_path.is_absolute():
        candidate = questions_path.parent / ref
        if candidate.exists():
            ref_path = candidate
    if ref_path.exists():
        return ref_path.read_text(encoding="utf-8", errors="ignore").strip()
    return ""


def is_placeholder(text: str) -> bool:
    if not text:
        return True
    lowered = text.strip().lower()
    return any(token in lowered for token in ["待生成", "待录入", "空题干", "请补充", "todo"])


def split_lines(text: str) -> List[str]:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(line)
    return lines


def clean_step_text(text: str) -> str:
    text = normalize_symbols(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_keywords(text: str) -> List[str]:
    cleaned = clean_step_text(text)
    if not cleaned:
        return []
    parts = re.split(r"[，,。;；、/\s]+", cleaned)
    keywords = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part not in keywords:
            keywords.append(part)
    for num in re.findall(r"-?\d+(?:\.\d+)?", cleaned):
        if num not in keywords:
            keywords.append(num)
    if cleaned not in keywords:
        keywords.insert(0, cleaned)
    return keywords[:6]


def parse_steps(answer_text: str) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    lines = split_lines(answer_text)
    steps: List[Dict[str, Any]] = []
    total_score: Optional[float] = None

    step_no_re = re.compile(r"^\s*(?:\(?\s*(\d{1,3})\s*\)?[\.、:：\)]\s*)(.*)$")
    score_re = re.compile(r"(\d+(?:\.\d+)?)\s*分")

    for line in lines:
        raw = normalize_symbols(line)
        score_match = score_re.search(raw)
        score_val = float(score_match.group(1)) if score_match else None
        raw_wo_score = score_re.sub("", raw).strip()

        step_no = None
        content = raw_wo_score
        m = step_no_re.match(raw_wo_score)
        if m:
            step_no = int(m.group(1))
            content = m.group(2).strip()

        if not content and score_val is not None and total_score is None:
            total_score = score_val
            continue

        if not content:
            content = raw_wo_score.strip()

        step_id = f"step_{step_no if step_no is not None else len(steps) + 1}"
        step_score = score_val if score_val is not None else 1.0
        steps.append(
            {
                "id": step_id,
                "label": content,
                "score": step_score,
                "keywords": build_keywords(content),
                "regex": [],
            }
        )

    return steps, total_score


def main():
    parser = argparse.ArgumentParser(description="Generate rubric templates from assignment questions")
    parser.add_argument("--questions", help="path to questions.csv")
    parser.add_argument("--assignment-id", help="assignment id (uses data/assignments/<id>/questions.csv)")
    parser.add_argument("--rubric-dir", help="output rubric directory (default: <assignment>/rubrics)")
    parser.add_argument("--out-questions", help="output questions.csv (default: questions_with_rubrics.csv)")
    parser.add_argument("--in-place", action="store_true", help="update questions.csv in place")
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing rubric files")
    parser.add_argument("--include-missing", action="store_true", help="create stub rubric when answer is missing")
    args = parser.parse_args()

    if not args.questions and not args.assignment_id:
        raise SystemExit("Provide --questions or --assignment-id")

    questions_path = Path(args.questions) if args.questions else Path("data/assignments") / args.assignment_id / "questions.csv"
    if not questions_path.exists():
        raise SystemExit(f"questions.csv not found: {questions_path}")

    rows, fieldnames = read_questions(questions_path)
    if "rubric_ref" not in fieldnames:
        fieldnames.append("rubric_ref")

    rubric_dir = Path(args.rubric_dir) if args.rubric_dir else questions_path.parent / "rubrics"
    rubric_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0
    updated_rows = 0

    for row in rows:
        qid = (row.get("question_id") or "").strip()
        if not qid:
            continue
        existing_rubric = (row.get("rubric_ref") or row.get("rubric") or "").strip()
        if existing_rubric and not args.overwrite:
            skipped += 1
            continue

        answer_text = extract_answer_text(row, questions_path)
        if is_placeholder(answer_text):
            if not args.include_missing:
                skipped += 1
                continue
            answer_text = ""

        answer_type = detect_answer_type(answer_text) if answer_text else "unknown"
        if answer_type in {"mcq_single", "mcq_multi", "numeric"}:
            skipped += 1
            continue

        steps, total_score = parse_steps(answer_text)
        if not steps and not args.include_missing:
            skipped += 1
            continue

        rubric = {
            "question_id": qid,
            "source": "auto_template",
            "notes": "Generated from answer text. Please review and refine keywords/steps.",
            "steps": steps,
        }
        if total_score is not None:
            rubric["total_score"] = total_score

        rubric_path = rubric_dir / f"{qid}.json"
        if rubric_path.exists() and not args.overwrite:
            skipped += 1
            continue
        rubric_path.write_text(json.dumps(rubric, ensure_ascii=False, indent=2), encoding="utf-8")
        row["rubric_ref"] = str(rubric_path)
        created += 1
        updated_rows += 1

    if args.in_place:
        out_questions = questions_path
    else:
        out_questions = Path(args.out_questions) if args.out_questions else questions_path.parent / "questions_with_rubrics.csv"

    write_questions(out_questions, rows, fieldnames)

    print(f"[OK] Rubric templates created: {created}")
    print(f"[OK] Rows updated: {updated_rows}")
    print(f"[OK] Skipped: {skipped}")
    print(f"[OK] Questions output: {out_questions}")
    print(f"[OK] Rubric dir: {rubric_dir}")


if __name__ == "__main__":
    main()
