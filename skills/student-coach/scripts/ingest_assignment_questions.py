#!/usr/bin/env python3
import argparse
import csv
import re
import sys
from pathlib import Path
from typing import List

# Ensure skill script path available
SKILL_OCR = Path("skills/physics-lesson-capture/scripts/ocr_utils.py")
if SKILL_OCR.exists():
    sys.path.insert(0, str(SKILL_OCR.parent))

try:
    from ocr_utils import load_env_from_dotenv, ocr_with_sdk
except Exception:
    def load_env_from_dotenv(*args, **kwargs):
        pass

    def ocr_with_sdk(*args, **kwargs):
        raise RuntimeError("ocr_utils not available")


FIELDS = ["question_id", "kp_id", "difficulty", "type", "stem_ref", "answer_ref", "source", "tags"]


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def safe_slug(value: str) -> str:
    return re.sub(r"[^\w-]+", "_", value).strip("_")


def read_existing(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: List[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in FIELDS})


def main():
    parser = argparse.ArgumentParser(description="Ingest assignment questions from screenshots via OCR")
    parser.add_argument("--assignment-id", required=True)
    parser.add_argument("--files", nargs="+", required=True, help="image files")
    parser.add_argument("--kp-id", default="uncategorized")
    parser.add_argument("--difficulty", default="basic")
    parser.add_argument("--tags", default="ocr")
    parser.add_argument("--source", default="teacher")
    parser.add_argument("--ocr-mode", default="FREE_OCR")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--start-index", type=int, default=1)
    args = parser.parse_args()

    load_env_from_dotenv(Path(".env"))

    assignment_id = args.assignment_id
    out_dir = Path("data/assignments") / assignment_id
    out_dir.mkdir(parents=True, exist_ok=True)

    stem_dir = out_dir / "explicit_stems"
    ocr_dir = out_dir / "explicit_ocr"
    stem_dir.mkdir(parents=True, exist_ok=True)
    ocr_dir.mkdir(parents=True, exist_ok=True)

    existing_path = out_dir / "explicit_questions.csv"
    existing_rows = read_existing(existing_path)
    existing_ids = {row.get("question_id") for row in existing_rows}

    slug = safe_slug(assignment_id) or "assignment"
    new_rows = []
    idx = args.start_index
    for file in args.files:
        file_path = Path(file)
        if not file_path.exists():
            raise SystemExit(f"File not found: {file_path}")

        text = ocr_with_sdk(file_path, language=args.language, mode=args.ocr_mode)
        cleaned = clean_text(text)

        question_id = f"IMG-{slug}-{idx:03d}"
        while question_id in existing_ids:
            idx += 1
            question_id = f"IMG-{slug}-{idx:03d}"

        stem_ref = stem_dir / f"{question_id}.md"
        stem_ref.write_text(cleaned or "【OCR空白】请补充题干。", encoding="utf-8")

        ocr_dir.joinpath(f"{question_id}.txt").write_text(cleaned, encoding="utf-8")

        new_rows.append(
            {
                "question_id": question_id,
                "kp_id": args.kp_id or "uncategorized",
                "difficulty": args.difficulty,
                "type": "explicit_ocr",
                "stem_ref": str(stem_ref),
                "answer_ref": "",
                "source": args.source,
                "tags": args.tags,
            }
        )
        existing_ids.add(question_id)
        idx += 1

    rows = existing_rows + new_rows
    write_rows(existing_path, rows)

    print(f"[OK] Wrote explicit questions: {existing_path}")
    print("[OK] Question IDs:")
    for row in new_rows:
        print(row["question_id"])


if __name__ == "__main__":
    main()
