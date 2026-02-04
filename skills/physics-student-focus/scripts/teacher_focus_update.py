#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# ensure ocr_utils available
OCR_UTILS = Path("skills/physics-lesson-capture/scripts/ocr_utils.py")
if OCR_UTILS.exists():
    sys.path.insert(0, str(OCR_UTILS.parent))

try:
    from ocr_utils import load_env_from_dotenv, ocr_with_sdk
except Exception:
    def load_env_from_dotenv(*args, **kwargs):
        pass
    def ocr_with_sdk(*args, **kwargs):
        raise RuntimeError("ocr_utils not available")


def save_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Teacher-side focused student update")
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--weak-kp", default="")
    parser.add_argument("--strong-kp", default="")
    parser.add_argument("--medium-kp", default="")
    parser.add_argument("--next-focus", default="")
    parser.add_argument("--assignment-id", default="")
    parser.add_argument("--discussion-notes", help="teacher discussion notes file")
    parser.add_argument("--recent-assignments", help="csv of recent assignment performance")
    parser.add_argument("--files", nargs="+", help="answer sheet images/PDF")
    parser.add_argument("--ocr-mode", default="FREE_OCR")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--out-dir", default="data/teacher_focus")
    args = parser.parse_args()

    load_env_from_dotenv(Path('.env'))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path(args.out_dir) / args.student_id / timestamp
    base_dir.mkdir(parents=True, exist_ok=True)

    interaction_note = f"Context: {args.context}"
    if args.notes:
        interaction_note += f" | Notes: {args.notes}"

    if args.discussion_notes:
        note_path = Path(args.discussion_notes)
        if note_path.exists():
            text = note_path.read_text(encoding="utf-8", errors="ignore")
            save_text(base_dir / "discussion.md", text)
            short = text.strip().replace("\n", " ")
            if len(short) > 200:
                short = short[:200] + "..."
            if short:
                interaction_note += f" | Discussion: {short}"

    if args.files:
        ocr_dir = base_dir / "ocr"
        ocr_dir.mkdir(parents=True, exist_ok=True)
        texts = []
        for idx, f in enumerate(args.files, start=1):
            file_path = Path(f)
            if not file_path.exists():
                raise SystemExit(f"File not found: {f}")
            text = ocr_with_sdk(file_path, mode=args.ocr_mode, language=args.language)
            save_text(ocr_dir / f"page_{idx}.txt", text)
            texts.append(text)
        interaction_note += f" | OCR saved: {ocr_dir}"
        save_text(base_dir / "ocr_summary.txt", "\n".join(texts))

    # call update_profile.py
    updater = Path("skills/physics-student-coach/scripts/update_profile.py")
    cmd = [
        sys.executable,
        str(updater),
        "--student-id",
        args.student_id,
        "--weak-kp",
        args.weak_kp,
        "--strong-kp",
        args.strong_kp,
        "--medium-kp",
        args.medium_kp,
        "--next-focus",
        args.next_focus,
        "--interaction-note",
        interaction_note,
    ]
    if args.assignment_id:
        cmd.extend(["--assignment-id", args.assignment_id])
    if args.recent_assignments:
        cmd.extend(["--history-file", args.recent_assignments])
    os.spawnv(os.P_WAIT, sys.executable, cmd)

    print(f"[OK] Focus update saved in {base_dir}")


if __name__ == "__main__":
    main()
