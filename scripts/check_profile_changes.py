#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_profile(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def detect_change(old: dict, new: dict, accuracy_delta: float = 0.2) -> int:
    # return change score
    score = 0
    if set(old.get("recent_weak_kp", [])) != set(new.get("recent_weak_kp", [])):
        score += 1
    if set(old.get("recent_strong_kp", [])) != set(new.get("recent_strong_kp", [])):
        score += 1
    if set(old.get("recent_medium_kp", [])) != set(new.get("recent_medium_kp", [])):
        score += 1
    if old.get("next_focus") != new.get("next_focus"):
        score += 1

    # mastery accuracy delta
    old_mastery = old.get("mastery_by_kp", {}) or {}
    new_mastery = new.get("mastery_by_kp", {}) or {}
    for kp, entry in new_mastery.items():
        try:
            new_acc = float(entry.get("accuracy"))
        except Exception:
            continue
        try:
            old_acc = float(old_mastery.get(kp, {}).get("accuracy"))
        except Exception:
            old_acc = None
        if old_acc is None:
            continue
        if abs(new_acc - old_acc) >= accuracy_delta:
            score += 1
            break

    return score


def main():
    parser = argparse.ArgumentParser(description="Detect profile change and suggest mem0 write")
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--profile", help="path to current profile json")
    parser.add_argument("--prev", help="path to previous profile snapshot json")
    parser.add_argument("--threshold", type=int, default=1, help="change score threshold")
    parser.add_argument("--accuracy-delta", type=float, default=0.2, help="accuracy delta threshold")
    args = parser.parse_args()

    profile_path = Path(args.profile) if args.profile else Path("data/student_profiles") / f"{args.student_id}.json"
    prev_path = Path(args.prev) if args.prev else profile_path.with_suffix(".prev.json")

    current = load_profile(profile_path)
    previous = load_profile(prev_path)

    score = detect_change(previous, current, accuracy_delta=args.accuracy_delta)
    if score >= args.threshold:
        print(f"CHANGE_DETECTED score={score}")
        # save snapshot
        prev_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(f"NO_CHANGE score={score}")


if __name__ == "__main__":
    main()
