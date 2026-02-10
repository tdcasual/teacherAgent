#!/usr/bin/env python3
import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List


def parse_list(value: str) -> List[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.replace("，", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]


def load_profile(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_profile(path: Path, profile: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write to reduce risk of partial writes under concurrent updates.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def acquire_lock(lock_path: Path, timeout_sec: float = 8.0) -> bool:
    start = time.monotonic()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"pid={os.getpid()} ts={datetime.now().isoformat(timespec='seconds')}\n")
            return True
        except FileExistsError:
            if (time.monotonic() - start) >= timeout_sec:
                return False
            time.sleep(0.05)


def release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except Exception:
        pass


def dedupe_list(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def main():
    parser = argparse.ArgumentParser(description="Update student profile (derived fields only)")
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--weak-kp", default="")
    parser.add_argument("--strong-kp", default="")
    parser.add_argument("--medium-kp", default="")
    parser.add_argument("--next-focus", default="")
    parser.add_argument("--interaction-note", default="")
    parser.add_argument("--assignment-id", default="")
    parser.add_argument("--matched", type=int, default=None)
    parser.add_argument("--graded", type=int, default=None)
    parser.add_argument("--ungraded", type=int, default=None)
    parser.add_argument("--history-file", help="csv with assignment_id, matched, graded, ungraded, note (optional)")
    parser.add_argument("--misconceptions", default="", help="semicolon-separated misconception descriptions")
    parser.add_argument("--mastery-json", default="", help="JSON string: {KP: {accuracy: float, attempts: int}}")
    parser.add_argument("--completion-status", default="", help="completed|partial|abandoned")
    parser.add_argument("--profile-dir", default="data/student_profiles")
    args = parser.parse_args()

    profile_path = Path(args.profile_dir) / f"{args.student_id}.json"
    lock_path = profile_path.with_suffix(profile_path.suffix + ".lock")
    if not acquire_lock(lock_path):
        raise SystemExit(f"Could not acquire profile lock: {lock_path}")
    try:
        profile = load_profile(profile_path)

        profile["student_id"] = args.student_id
        profile["last_updated"] = datetime.now().isoformat(timespec="seconds")

        weak_kp = parse_list(args.weak_kp)
        strong_kp = parse_list(args.strong_kp)
        medium_kp = parse_list(args.medium_kp)

        if weak_kp:
            profile["recent_weak_kp"] = weak_kp
        if strong_kp:
            profile["recent_strong_kp"] = strong_kp
        if medium_kp:
            profile["recent_medium_kp"] = medium_kp

        if args.next_focus:
            profile["next_focus"] = args.next_focus
        elif weak_kp:
            profile["next_focus"] = weak_kp[0]

        # interaction notes
        if args.interaction_note:
            notes = profile.get("interaction_notes", [])
            notes.append({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "note": args.interaction_note,
            })
            profile["interaction_notes"] = notes[-20:]

        # practice history update (single)
        if args.assignment_id:
            history = profile.get("practice_history", [])
            history.append({
                "assignment_id": args.assignment_id,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "matched": args.matched,
                "graded": args.graded,
                "ungraded": args.ungraded,
            })
            profile["practice_history"] = history[-20:]

        # practice history update (batch from csv)
        if args.history_file:
            history = profile.get("practice_history", [])
            import csv
            with Path(args.history_file).open(encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    assignment_id = row.get("assignment_id") or row.get("assignment") or ""
                    if not assignment_id:
                        continue
                    def to_int(val):
                        try:
                            return int(val)
                        except Exception:
                            return None
                    history.append({
                        "assignment_id": assignment_id,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "matched": to_int(row.get("matched")),
                        "graded": to_int(row.get("graded")),
                        "ungraded": to_int(row.get("ungraded")),
                        "note": row.get("note") or "",
                    })
            profile["practice_history"] = history[-20:]

        # completion status on latest practice entry
        if args.completion_status and profile.get("practice_history"):
            profile["practice_history"][-1]["status"] = args.completion_status

        # misconceptions
        if args.misconceptions:
            existing = profile.get("misconceptions", [])
            for desc in args.misconceptions.replace("；", ";").split(";"):
                desc = desc.strip()
                if not desc:
                    continue
                existing.append({
                    "description": desc,
                    "detected_at": datetime.now().isoformat(timespec="seconds"),
                })
            profile["misconceptions"] = existing[-20:]

        # mastery_by_kp incremental update
        if args.mastery_json:
            try:
                updates = json.loads(args.mastery_json)
                if isinstance(updates, dict):
                    mastery = profile.get("mastery_by_kp", {})
                    for kp, entry in updates.items():
                        if not isinstance(entry, dict):
                            continue
                        mastery[kp] = {
                            "accuracy": entry.get("accuracy", 0),
                            "attempts": entry.get("attempts", 0),
                            "last_updated": datetime.now().isoformat(timespec="seconds"),
                        }
                    profile["mastery_by_kp"] = mastery
            except (json.JSONDecodeError, TypeError):
                pass

        # summary
        summary_parts = []
        if weak_kp:
            summary_parts.append(f"weak: {','.join(weak_kp)}")
        if strong_kp:
            summary_parts.append(f"strong: {','.join(strong_kp)}")
        if args.next_focus:
            summary_parts.append(f"next: {args.next_focus}")
        if args.assignment_id:
            summary_parts.append(f"last_assignment: {args.assignment_id}")
        if summary_parts:
            profile["summary"] = " | ".join(summary_parts)

        save_profile(profile_path, profile)
        print(f"[OK] Updated profile: {profile_path}")
    finally:
        release_lock(lock_path)


if __name__ == "__main__":
    main()
