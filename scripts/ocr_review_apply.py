#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"grading_report.json not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to read report: {exc}")


def write_report(path: Path, report: Dict[str, Any]):
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_list(value: str) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def load_decisions(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"review decisions not found: {path}")
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("items", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise SystemExit("JSON decisions must be a list or contain items[]")
        rows = items
    else:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

    decisions: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        qid = (row.get("question_id") or "").strip()
        if not qid:
            continue
        decisions[qid] = row
    return decisions


def update_review_queue(queue_path: Path, decisions: Dict[str, Dict[str, Any]]):
    if not queue_path.exists():
        return
    try:
        payload = json.loads(queue_path.read_text(encoding="utf-8"))
    except Exception:
        return
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return
    now = datetime.now().isoformat(timespec="seconds")
    for item in items:
        qid = item.get("question_id")
        if not qid or qid not in decisions:
            continue
        dec = decisions[qid]
        item["final_status"] = (dec.get("final_status") or dec.get("status") or item.get("status"))
        item["final_score"] = dec.get("final_score") or dec.get("score") or item.get("score")
        item["final_confidence"] = dec.get("final_confidence") or dec.get("confidence") or item.get("confidence")
        item["reviewed_at"] = now
        item["review_notes"] = dec.get("notes") or dec.get("review_notes") or ""
    payload["reviewed_at"] = now
    queue_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_profile(path: Path, profile: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


def update_profile(report: Dict[str, Any], profile_path: Path):
    student_id = report.get("student_id") or profile_path.stem
    assignment_id = report.get("assignment_id") or "unknown"
    items = report.get("items", [])

    kp_stats: Dict[str, Dict[str, int]] = {}
    correct_count = 0
    ungraded = 0
    for item in items:
        status = item.get("status")
        kp_id = item.get("kp_id") or "uncategorized"
        stat = kp_stats.setdefault(kp_id, {"correct": 0, "total": 0, "ungraded": 0})
        if status == "ungraded":
            ungraded += 1
            stat["ungraded"] += 1
            continue
        stat["total"] += 1
        if status == "matched":
            stat["correct"] += 1
            correct_count += 1

    graded_total = len(items) - ungraded

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

    profile = load_profile(profile_path)
    profile["student_id"] = student_id
    profile["last_updated"] = datetime.now().isoformat(timespec="seconds")
    profile["recent_weak_kp"] = weak_kp
    profile["recent_strong_kp"] = strong_kp
    profile["recent_medium_kp"] = medium_kp
    next_focus = weak_kp[0] if weak_kp else (medium_kp[0] if medium_kp else "")
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

    history = profile.get("practice_history", [])
    found = False
    for entry in history:
        if entry.get("assignment_id") == assignment_id:
            entry.update(
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "matched": correct_count,
                    "graded": graded_total,
                    "ungraded": ungraded,
                }
            )
            found = True
            break
    if not found:
        history.append(
            {
                "assignment_id": assignment_id,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "matched": correct_count,
                "graded": graded_total,
                "ungraded": ungraded,
            }
        )
    profile["practice_history"] = history[-20:]
    profile["summary"] = f"{assignment_id}: matched {correct_count}/{graded_total}, next focus {next_focus}"

    save_profile(profile_path, profile)


def infer_assignment_bucket(report: Dict[str, Any], report_path: Path) -> Optional[Path]:
    assignment_id = report.get("assignment_id")
    student_id = report.get("student_id")
    if not assignment_id or not student_id:
        return None
    base = Path("data/student_submissions") / assignment_id / student_id / report_path.parent.name
    if base.exists():
        return base
    return None


def main():
    parser = argparse.ArgumentParser(description="Apply manual review decisions to grading_report.json")
    parser.add_argument("--report", help="path to grading_report.json")
    parser.add_argument("--submission-dir", help="submission directory containing grading_report.json")
    parser.add_argument("--decisions", help="review decisions CSV/JSON (default: review_decisions.csv in submission dir)")
    parser.add_argument("--update-profile", action="store_true", help="update student profile after applying decisions")
    args = parser.parse_args()

    if not args.report and not args.submission_dir:
        raise SystemExit("Provide --report or --submission-dir")

    report_path = Path(args.report) if args.report else Path(args.submission_dir) / "grading_report.json"
    submission_dir = report_path.parent

    decisions_path = Path(args.decisions) if args.decisions else submission_dir / "review_decisions.csv"
    report = load_report(report_path)
    decisions = load_decisions(decisions_path)

    now = datetime.now().isoformat(timespec="seconds")
    items = report.get("items", [])
    if not isinstance(items, list):
        raise SystemExit("Invalid report: items should be a list")

    updated = 0
    for item in items:
        qid = item.get("question_id")
        if not qid or qid not in decisions:
            continue
        dec = decisions[qid]
        status = dec.get("final_status") or dec.get("status")
        if status:
            item["status"] = status
        score = dec.get("final_score") or dec.get("score")
        if score not in (None, ""):
            try:
                item["score"] = float(score)
            except Exception:
                item["score"] = score
        conf = dec.get("final_confidence") or dec.get("confidence")
        if conf not in (None, ""):
            try:
                item["confidence"] = round(float(conf), 3)
            except Exception:
                item["confidence"] = conf
        reason = dec.get("reason")
        if reason:
            item["reason"] = reason
        matched_steps = dec.get("matched_steps")
        if matched_steps:
            item["matched_steps"] = parse_list(matched_steps)
        missing_steps = dec.get("missing_steps")
        if missing_steps:
            item["missing_steps"] = parse_list(missing_steps)
        item["reviewed_at"] = now
        notes = dec.get("notes") or dec.get("review_notes")
        if notes:
            item["review_notes"] = notes
        updated += 1

    # recompute summary stats
    ungraded = sum(1 for item in items if item.get("status") == "ungraded")
    correct = sum(1 for item in items if item.get("status") == "matched")
    graded_total = len(items) - ungraded
    report["graded_total"] = graded_total
    report["ungraded"] = ungraded
    report["correct"] = correct
    report["reviewed_at"] = now

    write_report(report_path, report)

    # update mirrored assignment bucket if present
    bucket = infer_assignment_bucket(report, report_path)
    if bucket:
        bucket_report = bucket / "grading_report.json"
        if bucket_report.exists():
            write_report(bucket_report, report)
        bucket_queue = bucket / "review_queue.json"
        update_review_queue(bucket_queue, decisions)

    update_review_queue(submission_dir / "review_queue.json", decisions)

    if args.update_profile:
        profile_path = Path("data/student_profiles") / f"{report.get('student_id')}.json"
        update_profile(report, profile_path)

    print(f"[OK] Applied decisions: {updated}")
    print(f"[OK] Updated report: {report_path}")
    if bucket:
        print(f"[OK] Updated assignment bucket report: {bucket / 'grading_report.json'}")
    if args.update_profile:
        profile_path = Path("data/student_profiles") / f"{report.get('student_id')}.json"
        print(f"[OK] Updated profile: {profile_path}")


if __name__ == "__main__":
    main()
