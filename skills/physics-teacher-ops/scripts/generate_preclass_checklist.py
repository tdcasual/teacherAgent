#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Optional


def load_questions(path: Path):
    max_scores = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qid = row.get("question_id")
            if not qid:
                continue
            try:
                max_scores[qid] = float(row.get("max_score") or 0)
            except Exception:
                max_scores[qid] = 0.0
    return max_scores


def load_kp_map(path: Optional[Path]):
    if not path or not path.exists():
        return {}
    mapping = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qid = row.get("question_id")
            kp = row.get("kp_id")
            if qid:
                mapping[qid] = kp or "uncategorized"
    return mapping


def load_responses(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def parse_score(value):
    try:
        return float(value)
    except Exception:
        return None


def compute_question_metrics(rows, max_scores):
    score_lists = defaultdict(list)
    for r in rows:
        qid = r.get("question_id")
        if not qid:
            continue
        score = parse_score(r.get("score"))
        if score is None:
            continue
        score_lists[qid].append(score)

    metrics = {}
    for qid, scores in score_lists.items():
        max_score = max_scores.get(qid, 0.0)
        avg = sum(scores) / len(scores) if scores else 0.0
        loss_rate = (max_score - avg) / max_score if max_score else 0.0
        metrics[qid] = {
            "avg_score": avg,
            "max_score": max_score,
            "loss_rate": loss_rate,
        }
    return metrics


def compute_kp_loss(question_metrics, kp_map):
    agg = defaultdict(lambda: {"max": 0.0, "avg": 0.0, "count": 0})
    for qid, qm in question_metrics.items():
        kp = kp_map.get(qid, "uncategorized") if kp_map else "uncategorized"
        agg[kp]["max"] += qm["max_score"]
        agg[kp]["avg"] += qm["avg_score"]
        agg[kp]["count"] += 1

    kp_list = []
    for kp, data in agg.items():
        if data["max"] <= 0:
            continue
        loss_rate = (data["max"] - data["avg"]) / data["max"] if data["max"] else 0.0
        kp_list.append({
            "kp_id": kp,
            "loss_rate": loss_rate,
            "count": data["count"],
        })
    kp_list.sort(key=lambda x: x["loss_rate"], reverse=True)
    return kp_list


def main():
    parser = argparse.ArgumentParser(description="Generate pre-class check list from exam data")
    parser.add_argument("--exam-id", required=True)
    parser.add_argument("--responses", required=True, help="responses_scored.csv")
    parser.add_argument("--questions", required=True, help="questions.csv")
    parser.add_argument("--knowledge-map", help="knowledge_point_map.csv")
    parser.add_argument("--lesson-topic", default="待定", help="lesson topic")
    parser.add_argument("--top-kp", type=int, default=3, help="number of target knowledge points")
    parser.add_argument("--items-per-kp", type=int, default=2, help="questions per knowledge point")
    parser.add_argument("--include-uncategorized", action="store_true", help="allow uncategorized kps")
    parser.add_argument("--out", help="output markdown file")
    args = parser.parse_args()

    rows = load_responses(Path(args.responses))
    max_scores = load_questions(Path(args.questions))
    kp_map = load_kp_map(Path(args.knowledge_map)) if args.knowledge_map else {}

    question_metrics = compute_question_metrics(rows, max_scores)
    kp_list = compute_kp_loss(question_metrics, kp_map)

    # select target KPs
    targets = []
    for kp in kp_list:
        if kp["kp_id"] == "uncategorized" and not args.include_uncategorized:
            continue
        targets.append(kp)
        if len(targets) >= args.top_kp:
            break

    # if still not enough, include uncategorized as fallback
    if len(targets) < args.top_kp:
        for kp in kp_list:
            if kp["kp_id"] == "uncategorized" and kp not in targets:
                targets.append(kp)
                if len(targets) >= args.top_kp:
                    break

    # map questions by kp
    q_by_kp = defaultdict(list)
    for qid, qm in question_metrics.items():
        kp = kp_map.get(qid, "uncategorized") if kp_map else "uncategorized"
        q_by_kp[kp].append({"question_id": qid, **qm})

    for kp, items in q_by_kp.items():
        items.sort(key=lambda x: x["loss_rate"], reverse=True)

    # build output
    lines = []
    lines.append(f"Lesson: {args.lesson_topic}")
    lines.append(f"Exam Source: {args.exam_id}")
    lines.append("Targets: " + ", ".join([t["kp_id"] for t in targets]) if targets else "Targets: (none)")
    lines.append("")
    lines.append("Items:")
    for t in targets:
        kp_id = t["kp_id"]
        questions = q_by_kp.get(kp_id, [])[: args.items_per_kp]
        if not questions:
            lines.append(f"- {kp_id}: (no questions found)")
            continue
        for q in questions:
            lines.append(f"- {q['question_id']} (KP: {kp_id})")

    # notes
    if any(t["kp_id"] == "uncategorized" for t in targets):
        lines.append("")
        lines.append("Notes:")
        lines.append("- 存在未映射知识点题目，建议补充映射后更新清单。")

    output = "\n".join(lines)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"[OK] Wrote {out_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
