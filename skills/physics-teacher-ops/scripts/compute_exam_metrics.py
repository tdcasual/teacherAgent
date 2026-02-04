#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def read_questions(path: Path):
    questions = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row.get("question_id")
            if not qid:
                continue
            max_score = row.get("max_score")
            try:
                max_score = float(max_score)
            except Exception:
                max_score = None
            questions[qid] = {
                "question_id": qid,
                "question_no": row.get("question_no"),
                "sub_no": row.get("sub_no"),
                "order": row.get("order"),
                "max_score": max_score,
            }
    return questions


def read_knowledge_map(path: Path):
    if not path or not path.exists():
        return {}
    mapping = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row.get("question_id")
            kp = row.get("kp_id")
            if qid:
                mapping[qid] = kp or "uncategorized"
    return mapping


def parse_score(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Compute exam metrics and draft analysis")
    parser.add_argument("--exam-id", required=True, help="Exam ID")
    parser.add_argument("--responses", required=True, help="responses_scored.csv")
    parser.add_argument("--questions", required=True, help="questions.csv")
    parser.add_argument("--knowledge-map", help="knowledge_point_map.csv")
    parser.add_argument("--out-json", required=True, help="Output draft.json")
    parser.add_argument("--out-md", help="Output draft.md")
    args = parser.parse_args()

    questions = read_questions(Path(args.questions))
    kp_map = read_knowledge_map(Path(args.knowledge_map)) if args.knowledge_map else {}

    # per-student totals and per-question stats
    student_totals = defaultdict(float)
    question_scores = defaultdict(list)
    question_correct = defaultdict(list)

    with Path(args.responses).open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row.get("question_id")
            if not qid:
                continue
            score = parse_score(row.get("score"))
            if score is None:
                continue
            student_id = row.get("student_id") or row.get("student_name")
            if student_id:
                student_totals[student_id] += score
            question_scores[qid].append(score)
            is_correct = row.get("is_correct")
            if is_correct not in (None, ""):
                try:
                    question_correct[qid].append(int(is_correct))
                except Exception:
                    pass

    max_total = sum(q["max_score"] for q in questions.values() if q["max_score"])
    totals = list(student_totals.values())
    totals_sorted = sorted(totals)
    avg_total = sum(totals) / len(totals) if totals else 0
    median_total = totals_sorted[len(totals_sorted) // 2] if totals_sorted else 0

    question_metrics = []
    for qid, q in questions.items():
        scores = question_scores.get(qid, [])
        avg = sum(scores) / len(scores) if scores else 0
        max_score = q.get("max_score") or 0
        loss_rate = (max_score - avg) / max_score if max_score else None
        correct_rate = None
        if qid in question_correct and question_correct[qid]:
            correct_rate = sum(question_correct[qid]) / len(question_correct[qid])
        question_metrics.append({
            "question_id": qid,
            "question_no": q.get("question_no"),
            "max_score": max_score,
            "avg_score": round(avg, 3),
            "loss_rate": round(loss_rate, 4) if loss_rate is not None else None,
            "correct_rate": round(correct_rate, 4) if correct_rate is not None else None,
        })

    question_metrics_sorted = sorted(
        question_metrics,
        key=lambda x: (x["loss_rate"] is None, -(x["loss_rate"] or 0)),
    )

    # knowledge point aggregation
    kp_stats = defaultdict(lambda: {"max_score": 0.0, "avg_score": 0.0, "count": 0})
    for qm in question_metrics:
        qid = qm["question_id"]
        kp = kp_map.get(qid, "uncategorized") if kp_map else "uncategorized"
        kp_stats[kp]["max_score"] += qm["max_score"] or 0
        kp_stats[kp]["avg_score"] += qm["avg_score"] or 0
        kp_stats[kp]["count"] += 1

    kp_metrics = []
    for kp, data in kp_stats.items():
        if data["count"] == 0:
            continue
        avg_score = data["avg_score"] / data["count"]
        max_score = data["max_score"] / data["count"]
        loss_rate = (max_score - avg_score) / max_score if max_score else None
        kp_metrics.append({
            "kp_id": kp,
            "avg_score": round(avg_score, 3),
            "loss_rate": round(loss_rate, 4) if loss_rate is not None else None,
            "coverage_count": data["count"],
            "coverage_score": round(data["max_score"], 3),
        })

    kp_metrics_sorted = sorted(
        kp_metrics,
        key=lambda x: (x["loss_rate"] is None, -(x["loss_rate"] or 0)),
    )

    draft = {
        "exam_id": args.exam_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "totals": {
            "student_count": len(totals),
            "max_total": max_total,
            "avg_total": round(avg_total, 3),
            "median_total": round(median_total, 3),
        },
        "knowledge_points": kp_metrics_sorted,
        "high_loss_questions": question_metrics_sorted[:5],
        "question_metrics": question_metrics_sorted,
        "notes": "Knowledge point mapping missing; all questions labeled as 'uncategorized'."
        if not kp_map
        else "",
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.out_md:
        lines = []
        lines.append(f"Exam: {args.exam_id}")
        lines.append(f"Generated: {draft['generated_at']}")
        lines.append("")
        lines.append("Totals:")
        lines.append(f"- Students: {draft['totals']['student_count']}")
        lines.append(f"- Max total: {draft['totals']['max_total']}")
        lines.append(f"- Avg total: {draft['totals']['avg_total']}")
        lines.append(f"- Median total: {draft['totals']['median_total']}")
        lines.append("")
        lines.append("Knowledge Points (loss rate desc):")
        for kp in draft["knowledge_points"][:5]:
            lines.append(f"- {kp['kp_id']}: loss_rate={kp['loss_rate']} coverage={kp['coverage_count']}")
        lines.append("")
        lines.append("High Loss Questions:")
        for q in draft["high_loss_questions"]:
            lines.append(
                f"- {q['question_id']} (avg={q['avg_score']}, loss_rate={q['loss_rate']}, max={q['max_score']})"
            )
        if draft.get("notes"):
            lines.append("")
            lines.append(f"Notes: {draft['notes']}")

        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Wrote {out_json}")
    if args.out_md:
        print(f"[OK] Wrote {args.out_md}")


if __name__ == "__main__":
    main()
