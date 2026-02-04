#!/usr/bin/env python3
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEACHER_SKILL = ROOT / "skills/physics-teacher-ops/SKILL.md"
STUDENT_SKILL = ROOT / "skills/physics-student-coach/SKILL.md"


def read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"Failed to read {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def extract_template(text: str, header: str) -> str:
    pattern = re.compile(rf"{re.escape(header)}\n```text\n(.*?)\n```", re.S)
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(1).strip()


def extract_band(text: str, label: str) -> str:
    pattern = re.compile(rf"Band scheme \({re.escape(label)}\): (.+)")
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(1).strip()


def print_section(title: str, body: str) -> None:
    if not body:
        return
    print(title)
    print(body)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Show mem0 memory templates and band scheme")
    parser.add_argument("--type", default="both", choices=["teacher", "student", "both"], help="which template to show")
    parser.add_argument("--no-bands", action="store_true", help="omit band scheme output")
    args = parser.parse_args()

    if args.type in ("teacher", "both"):
        teacher_text = read_text(TEACHER_SKILL)
        if not args.no_bands:
            score_band = extract_band(teacher_text, "ScoreBand")
            rank_band = extract_band(teacher_text, "RankBand")
            print_section("Band scheme (ScoreBand):", score_band)
            print_section("Band scheme (RankBand):", rank_band)
        template = extract_template(teacher_text, "Mem0 Teacher Memory Template:")
        print_section("Mem0 Teacher Memory Template:", template)

    if args.type in ("student", "both"):
        student_text = read_text(STUDENT_SKILL)
        if not args.no_bands:
            score_band = extract_band(student_text, "ScoreBand")
            rank_band = extract_band(student_text, "RankBand")
            print_section("Band scheme (ScoreBand):", score_band)
            print_section("Band scheme (RankBand):", rank_band)
        template = extract_template(student_text, "Mem0 Student Memory Template:")
        print_section("Mem0 Student Memory Template:", template)


if __name__ == "__main__":
    main()
