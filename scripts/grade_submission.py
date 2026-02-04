#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Ensure skill script path available
SKILL_OCR = Path('skills/physics-lesson-capture/scripts/ocr_utils.py')
if SKILL_OCR.exists():
    sys.path.insert(0, str(SKILL_OCR.parent))

try:
    from ocr_utils import load_env_from_dotenv, ocr_with_sdk
except Exception:
    def load_env_from_dotenv(*args, **kwargs):
        pass
    def ocr_with_sdk(*args, **kwargs):
        raise RuntimeError("ocr_utils not available")


def read_assignment_questions(path: Path):
    # assignment file format: csv with columns question_id, kp_id, stem_ref, answer_ref, answer_text(optional)
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def ocr_files(files: List[Path], out_dir: Path, language: str, mode: str):
    ensure_dir(out_dir)
    all_texts = []
    for idx, file in enumerate(files, start=1):
        try:
            text = ocr_with_sdk(file, language=language, mode=mode)
        except Exception as exc:
            raise SystemExit(f"OCR failed for {file}: {exc}")
        cleaned = clean_text(text)
        (out_dir / f"page_{idx}.json").write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / f"page_{idx}.txt").write_text(cleaned, encoding="utf-8")
        all_texts.append(cleaned)
    return "\n".join(all_texts)


def simple_match(answer_text: str, ocr_text: str) -> bool:
    if not answer_text:
        return False
    return answer_text.replace(" ", "") in ocr_text.replace(" ", "")


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


def get_expected_answer(row: dict) -> str:
    expected = (row.get("answer_text") or "").strip()
    if expected:
        return expected
    ref = row.get("answer_ref") or ""
    if ref:
        return extract_answer_from_ref(Path(ref))
    return ""


def load_profile(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_profile(path: Path, profile: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_assignment_id(text: str) -> Optional[str]:
    patterns = [
        r"Assignment\\s*ID\\s*[:：]\\s*([A-Za-z0-9_-]+)",
        r"Assignment\\s*[:：]\\s*([A-Za-z0-9_-]+)",
        r"作业\\s*[:：]\\s*([A-Za-z0-9_-]+)",
        r"练习\\s*[:：]\\s*([A-Za-z0-9_-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return None


def find_assignment_id_by_scan(text: str) -> Optional[str]:
    assignments_dir = Path("data/assignments")
    if not assignments_dir.exists():
        return None
    for folder in assignments_dir.iterdir():
        if not folder.is_dir():
            continue
        md = folder / "assignment.md"
        if not md.exists():
            continue
        content = md.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"Assignment\\s*ID\\s*[:：]\\s*([A-Za-z0-9_-]+)", content)
        if m:
            assignment_id = m.group(1).strip()
            if assignment_id and assignment_id in text:
                return assignment_id
    return None


def main():
    parser = argparse.ArgumentParser(description="Grade student submission from photos using OCR")
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--assignment-id", help="assignment id (optional if auto-detect)")
    parser.add_argument("--auto-assignment", action="store_true", help="auto-detect assignment id from OCR text")
    parser.add_argument("--files", nargs="+", required=True, help="image files")
    parser.add_argument("--assignment-questions", help="csv of assigned questions (optional if assignment id is detected)")
    parser.add_argument("--out-dir", default="data/student_submissions")
    parser.add_argument("--ocr-mode", default="FREE_OCR")
    parser.add_argument("--language", default="zh")
    args = parser.parse_args()

    load_env_from_dotenv(Path('.env'))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path(args.out_dir) / args.student_id / f"submission_{timestamp}"
    ensure_dir(base_dir)

    files = [Path(f) for f in args.files]
    for f in files:
        if not f.exists():
            raise SystemExit(f"File not found: {f}")

    ocr_dir = base_dir / "ocr"
    ocr_text = ocr_files(files, ocr_dir, args.language, args.ocr_mode)

    # detect assignment id from OCR if requested
    assignment_id = args.assignment_id
    if args.auto_assignment or not assignment_id:
        assignment_id = detect_assignment_id(ocr_text)
        if not assignment_id:
            assignment_id = find_assignment_id_by_scan(ocr_text)
    if not assignment_id:
        raise SystemExit("Could not detect assignment_id. Provide --assignment-id.")

    # resolve assignment questions path
    questions_path = Path(args.assignment_questions) if args.assignment_questions else Path("data/assignments") / assignment_id / "questions.csv"
    if not questions_path.exists():
        raise SystemExit(f"Assignment questions not found: {questions_path}")
    questions = read_assignment_questions(questions_path)

    # move submission into assignment bucket as well
    assignment_bucket = Path(args.out_dir) / assignment_id / args.student_id / f"submission_{timestamp}"
    assignment_bucket.mkdir(parents=True, exist_ok=True)

    # copy OCR artifacts to assignment bucket
    assignment_ocr = assignment_bucket / "ocr"
    assignment_ocr.mkdir(parents=True, exist_ok=True)
    for f in ocr_dir.glob("*"):
        if f.is_file():
            assignment_ocr.joinpath(f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

    # naive evaluation (placeholder): check if expected answer text appears in OCR
    results = []
    correct_count = 0
    ungraded_count = 0
    kp_stats = {}
    for q in questions:
        qid = q.get("question_id")
        kp_id = q.get("kp_id") or "uncategorized"
        expected = get_expected_answer(q)
        if expected:
            matched = simple_match(expected, ocr_text)
            status = "matched" if matched else "missed"
        else:
            matched = False
            status = "ungraded"
            ungraded_count += 1
        results.append({
            "question_id": qid,
            "kp_id": kp_id,
            "expected": expected,
            "matched": matched,
            "status": status,
        })
        if matched:
            correct_count += 1

        stat = kp_stats.setdefault(kp_id, {"correct": 0, "total": 0, "ungraded": 0})
        if status == "ungraded":
            stat["ungraded"] += 1
        else:
            stat["total"] += 1
            if matched:
                stat["correct"] += 1

    feedback_lines = []
    feedback_lines.append(f"Student: {args.student_id}")
    feedback_lines.append(f"Assignment: {assignment_id}")
    graded_total = len(questions) - ungraded_count
    feedback_lines.append(f"Total matched: {correct_count}/{len(questions)} (graded: {graded_total})")
    feedback_lines.append("")
    feedback_lines.append("Item Feedback:")
    for r in results:
        if r["status"] == "ungraded":
            status = "△"
        else:
            status = "✔" if r["matched"] else "✘"
        feedback_lines.append(f"- {r['question_id']} ({r['kp_id']}): {status}")

    feedback_path = base_dir / "feedback.md"
    feedback_path.write_text("\n".join(feedback_lines), encoding="utf-8")

    # also copy feedback into assignment bucket
    assignment_feedback = assignment_bucket / "feedback.md"
    assignment_feedback.write_text("\n".join(feedback_lines), encoding="utf-8")

    # profile update suggestion
    weak_kp = []
    strong_kp = []
    medium_kp = []
    for kp, stat in kp_stats.items():
        if stat["total"] < 2:
            continue
        acc = stat["correct"] / stat["total"] if stat["total"] else 0
        if acc < 0.5:
            weak_kp.append(kp)
        elif acc >= 0.8:
            strong_kp.append(kp)
        else:
            medium_kp.append(kp)

    profile_lines = []
    profile_lines.append(f"Student: {args.student_id}")
    profile_lines.append(f"Assignment: {assignment_id}")
    profile_lines.append(f"Graded: {graded_total} | Ungraded: {ungraded_count}")
    profile_lines.append("")
    profile_lines.append("Profile Update Suggestion (derived):")
    profile_lines.append(f"- recent_weak_kp: {', '.join(weak_kp) if weak_kp else '(none)'}")
    profile_lines.append(f"- strengths: {', '.join(strong_kp) if strong_kp else '(none)'}")
    profile_lines.append(f"- medium_kp: {', '.join(medium_kp) if medium_kp else '(none)'}")
    next_focus = weak_kp[0] if weak_kp else (medium_kp[0] if medium_kp else '(none)')
    profile_lines.append(f"- next_focus: {next_focus}")
    profile_lines.append(f"- practice_history: {assignment_id} completed, matched {correct_count}/{graded_total}")
    if graded_total < 3:
        profile_lines.append("- note: Low confidence (few graded items).")
    if ungraded_count > 0:
        profile_lines.append("- note: Some items ungraded (missing answer_ref).")

    profile_path = base_dir / "profile_update_suggestion.md"
    profile_path.write_text("\n".join(profile_lines), encoding="utf-8")
    assignment_profile = assignment_bucket / "profile_update_suggestion.md"
    assignment_profile.write_text("\n".join(profile_lines), encoding="utf-8")

    # auto write student profile (derived fields only)
    profile_store = Path("data/student_profiles") / f"{args.student_id}.json"
    profile = load_profile(profile_store)
    profile["student_id"] = args.student_id
    profile["last_updated"] = datetime.now().isoformat(timespec="seconds")
    profile["recent_weak_kp"] = weak_kp
    profile["recent_strong_kp"] = strong_kp
    profile["recent_medium_kp"] = medium_kp
    profile["next_focus"] = next_focus

    mastery_by_kp = profile.get("mastery_by_kp", {})
    for kp, stat in kp_stats.items():
        if stat["total"] <= 0:
            continue
        acc = stat["correct"] / stat["total"] if stat["total"] else 0
        mastery_by_kp[kp] = {
            "accuracy": round(acc, 3),
            "evidence": assignment_id,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    profile["mastery_by_kp"] = mastery_by_kp

    practice_history = profile.get("practice_history", [])
    practice_history.append({
        "assignment_id": assignment_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "matched": correct_count,
        "graded": graded_total,
        "ungraded": ungraded_count,
    })
    # keep last 20
    profile["practice_history"] = practice_history[-20:]
    profile["summary"] = f"{assignment_id}: matched {correct_count}/{graded_total}, next focus {next_focus}"

    save_profile(profile_store, profile)

    print(f"[OK] Saved OCR to {ocr_dir}")
    print(f"[OK] Saved feedback to {feedback_path}")
    print(f"[OK] Saved profile suggestion to {profile_path}")


if __name__ == "__main__":
    main()
