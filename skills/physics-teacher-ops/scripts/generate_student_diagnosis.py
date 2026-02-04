#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path
from collections import defaultdict
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


def read_rows(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def resolve_student(rows, name=None, student_id=None):
    if student_id:
        matches = [r for r in rows if r.get("student_id") == student_id]
        if matches:
            return student_id
    if name:
        exact = [r for r in rows if r.get("student_name") == name]
        if exact:
            # prefer student_id if present
            sid = exact[0].get("student_id")
            return sid or name
        # fallback: partial match on name or id
        candidates = set()
        for r in rows:
            sname = r.get("student_name") or ""
            sid = r.get("student_id") or ""
            if name in sname or name in sid:
                candidates.add(sid or sname)
        if len(candidates) == 1:
            return candidates.pop()
        if candidates:
            raise SystemExit("Ambiguous name, matches: " + ", ".join(sorted(candidates)))
    raise SystemExit("Student not found. Provide --student-name or --student-id.")


def decile_band(value_pct):
    floor = int(value_pct // 10) * 10
    ceil = min(floor + 9, 100)
    return floor, ceil


def percentile_rank(rank, count):
    if count <= 1:
        return 0.0
    return (rank - 1) / (count - 1) * 100


def main():
    parser = argparse.ArgumentParser(description="Generate per-student diagnosis (masked bands)")
    parser.add_argument("--exam-id", required=True)
    parser.add_argument("--responses", required=True, help="responses_scored.csv")
    parser.add_argument("--questions", required=True, help="questions.csv")
    parser.add_argument("--knowledge-map", help="knowledge_point_map.csv")
    parser.add_argument("--student-name", help="student name")
    parser.add_argument("--student-id", help="student id")
    parser.add_argument("--out", help="output markdown path")
    args = parser.parse_args()

    rows = read_rows(Path(args.responses))
    max_scores = load_questions(Path(args.questions))
    kp_map = load_kp_map(Path(args.knowledge_map)) if args.knowledge_map else {}

    target = resolve_student(rows, args.student_name, args.student_id)

    # totals
    student_totals = defaultdict(float)
    for row in rows:
        sid = row.get("student_id") or row.get("student_name")
        if not sid:
            continue
        try:
            score = float(row.get("score") or 0)
        except Exception:
            score = 0.0
        student_totals[sid] += score

    sorted_totals = sorted(student_totals.items(), key=lambda x: x[1], reverse=True)
    rank = next((i for i, (sid, _) in enumerate(sorted_totals, start=1) if sid == target), None)
    if rank is None:
        raise SystemExit(f"Student '{target}' not found in totals. Check name/id in responses.")
    count = len(sorted_totals)
    total_score = student_totals[target]
    max_total = sum(v for v in max_scores.values() if v)
    score_pct = (total_score / max_total) * 100 if max_total else 0.0

    sb_floor, sb_ceil = decile_band(score_pct)
    percentile = percentile_rank(rank, count)
    rb_floor, rb_ceil = decile_band(percentile)

    # per-question
    student_rows = [r for r in rows if (r.get("student_id") == target or r.get("student_name") == target)]
    per_q = []
    for r in student_rows:
        qid = r.get("question_id")
        if not qid:
            continue
        try:
            score_q = float(r.get("score") or 0)
        except Exception:
            score_q = 0.0
        max_q = max_scores.get(qid) or 0.0
        loss = max_q - score_q
        loss_rate = (loss / max_q) if max_q else 0.0
        per_q.append((qid, score_q, max_q, loss_rate))

    per_q_sorted = sorted(per_q, key=lambda x: (x[3], x[2]), reverse=True)
    weak_q = [q for q in per_q_sorted if q[2] > 0 and q[3] >= 0.5]
    strong_q = [q for q in per_q_sorted if q[2] > 0 and q[3] <= 0.25]

    # kp aggregation
    kp_weak = defaultdict(list)
    for qid, _, _, loss_rate in weak_q:
        kp = kp_map.get(qid, "uncategorized") if kp_map else "uncategorized"
        kp_weak[kp].append(qid)

    # suggestions
    suggestions = []
    for kp, qids in sorted(kp_weak.items(), key=lambda x: (-len(x[1]), x[0])):
        if kp == "uncategorized":
            suggestions.append("补充未映射题的知识点后再生成针对性作业。")
        else:
            suggestions.append(f"{kp}: 2-3 道基础题 + 1 道综合题（结合 {', '.join(qids[:3])}）")

    # output
    lines = []
    lines.append(f"Student: {target} | Exam: {args.exam_id}")
    lines.append(f"Sensitive (masked): ScoreBand={sb_floor}–{sb_ceil}% | RankBand=P{rb_floor}–{rb_ceil}")
    lines.append("")
    lines.append("Diagnosis:")
    if kp_weak:
        for kp, qids in sorted(kp_weak.items(), key=lambda x: (-len(x[1]), x[0])):
            lines.append(f"- Weak points: {kp} (evidence: {', '.join(qids)})")
    else:
        lines.append("- Weak points: none flagged (loss_rate < 0.5)")

    lines.append("")
    lines.append("Strengths:")
    if strong_q:
        strong_ids = [qid for qid, _, _, _ in strong_q[:5]]
        lines.append(f"- High performance questions: {', '.join(strong_ids)}")
    else:
        lines.append("- No strong questions detected")

    lines.append("")
    lines.append("Assignments:")
    if suggestions:
        for s in suggestions:
            lines.append(f"- {s}")
    else:
        lines.append("- Maintain current mastery; add 2 mixed review problems")

    lines.append("")
    lines.append("Next Focus:")
    if kp_weak:
        top_kp = sorted(kp_weak.items(), key=lambda x: (-len(x[1]), x[0]))[0][0]
        lines.append(f"优先补强 {top_kp}，同步修正相关题型方法与表达。")
    else:
        lines.append("巩固已掌握题型，提升综合题稳定性。")

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
