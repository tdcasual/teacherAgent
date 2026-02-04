#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Optional


def load_questions(path: Optional[Path]):
    if not path:
        return {}
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


def load_responses(path: Optional[Path]):
    if not path:
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def load_student_notes(path: Optional[Path]):
    if not path or not path.exists():
        return []
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


def decile_band(value_pct):
    floor = int(value_pct // 10) * 10
    ceil = min(floor + 9, 100)
    return floor, ceil


def percentile_rank(rank, count):
    if count <= 1:
        return 0.0
    return (rank - 1) / (count - 1) * 100


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


def kp_assignments(loss_rate: Optional[float], emphasis: bool = False):
    # based on practice rules: 60/30/10 and 3-5 items
    if loss_rate is None:
        return "2基础 + 1中档" if emphasis else "1基础"
    if loss_rate >= 0.8:
        return "3基础 + 1中档 + 1提高"
    if loss_rate >= 0.5:
        return "2基础 + 1中档"
    if loss_rate >= 0.3:
        return "1基础"
    return "无需重复"


def sanitize_name(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_")


def parse_notes(path: Optional[Path]):
    result = {
        "lesson": None,
        "misconceptions": [],
        "emphasis_kp": [],
        "observations": [],
        "homework_focus": [],
    }
    if not path or not path.exists():
        return result

    heading_map = {
        "key misconceptions": "misconceptions",
        "易错点": "misconceptions",
        "典型错误": "misconceptions",
        "常见错误": "misconceptions",
        "emphasis kp": "emphasis_kp",
        "重点知识点": "emphasis_kp",
        "重点": "emphasis_kp",
        "targets": "emphasis_kp",
        "class observations": "observations",
        "课堂观察": "observations",
        "课堂反馈": "observations",
        "教学观察": "observations",
        "homework focus": "homework_focus",
        "作业方向": "homework_focus",
        "课后练习": "homework_focus",
        "作业重点": "homework_focus",
        "lesson": "lesson",
        "课题": "lesson",
        "主题": "lesson",
    }

    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        lowered = line.lower()

        # detect heading
        for key, target in heading_map.items():
            if lowered.startswith(key):
                current = target
                # handle "Title: value" form
                if ":" in line or "：" in line:
                    sep = ":" if ":" in line else "："
                    _, value = line.split(sep, 1)
                    value = value.strip()
                    if target == "lesson" and value:
                        result["lesson"] = value
                    elif target != "lesson" and value:
                        # allow comma separated list
                        items = [v.strip() for v in value.replace("，", ",").split(",") if v.strip()]
                        result[target].extend(items)
                break
        else:
            # bullet item
            if line.startswith(("-", "•", "*")):
                item = line[1:].strip()
                if current == "lesson" and item:
                    result["lesson"] = item
                elif current:
                    result[current].append(item)

    return result


def split_kp_list(value: str):
    if not value:
        return []
    parts = [p.strip() for p in value.replace("，", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]


def main():
    parser = argparse.ArgumentParser(description="Generate post-class diagnostic and personalized homework (lesson-first)")
    parser.add_argument("--exam-id", required=True)
    parser.add_argument("--lesson-topic", default="待定", help="lesson topic")
    parser.add_argument("--discussion-notes", help="class discussion notes (md)")
    parser.add_argument("--lesson-plan", help="lesson plan (md)")
    parser.add_argument("--student-notes", help="student notes csv (columns: student_name, weak_kp, strength_kp, note, action)")
    parser.add_argument("--responses", help="responses_scored.csv (optional)")
    parser.add_argument("--questions", help="questions.csv (optional)")
    parser.add_argument("--knowledge-map", help="knowledge_point_map.csv")
    parser.add_argument("--include-exam", action="store_true", help="merge exam loss into post-class diagnostic")
    parser.add_argument("--top-kp", type=int, default=5, help="top KPs in class diagnostic")
    parser.add_argument("--top-questions", type=int, default=5, help="high-loss questions to show")
    parser.add_argument("--student-top-kp", type=int, default=3, help="top weak KPs per student")
    parser.add_argument("--out-class", help="output class diagnostic markdown")
    parser.add_argument("--out-students-dir", help="output per-student folder")
    args = parser.parse_args()

    # lesson notes (primary)
    discussion = parse_notes(Path(args.discussion_notes) if args.discussion_notes else None)
    plan = parse_notes(Path(args.lesson_plan) if args.lesson_plan else None)

    lesson_topic = args.lesson_topic
    if discussion.get("lesson"):
        lesson_topic = discussion.get("lesson")
    elif plan.get("lesson"):
        lesson_topic = plan.get("lesson")

    # KPs from lesson notes
    lesson_kp = []
    lesson_kp.extend(discussion.get("emphasis_kp", []))
    lesson_kp.extend(plan.get("emphasis_kp", []))
    # normalize
    lesson_kp = [kp for kp in lesson_kp if kp]

    # exam data (optional)
    rows = load_responses(Path(args.responses)) if args.responses else []
    max_scores = load_questions(Path(args.questions)) if args.questions else {}
    kp_map = load_kp_map(Path(args.knowledge_map)) if args.knowledge_map else {}

    question_metrics = {}
    kp_list = []
    high_loss_questions = []
    if args.include_exam and rows and max_scores:
        question_metrics = compute_question_metrics(rows, max_scores)
        kp_list = compute_kp_loss(question_metrics, kp_map)
        high_loss_questions = sorted(
            question_metrics.items(),
            key=lambda x: x[1]["loss_rate"],
            reverse=True,
        )[: args.top_questions]

    # class summary
    totals = []
    avg_total = None
    median_total = None
    if args.include_exam and rows and max_scores:
        student_totals = defaultdict(float)
        for r in rows:
            sid = r.get("student_id") or r.get("student_name")
            if not sid:
                continue
            student_totals[sid] += parse_score(r.get("score")) or 0.0
        totals = list(student_totals.values())
        avg_total = sum(totals) / len(totals) if totals else 0.0
        median_total = sorted(totals)[len(totals) // 2] if totals else 0.0

    class_lines = []
    class_lines.append(f"Lesson: {lesson_topic}")
    class_lines.append(f"Exam Source: {args.exam_id}")
    class_lines.append("")

    class_lines.append("Class Summary:")
    if avg_total is not None:
        class_lines.append(f"- Students: {len(totals)}")
        class_lines.append(f"- Avg (masked): {round(avg_total, 2)}")
        class_lines.append(f"- Median (masked): {round(median_total, 2)}")
    else:
        class_lines.append("- Exam data not included (lesson-first mode)")

    # misconceptions
    if discussion.get("misconceptions"):
        class_lines.append("")
        class_lines.append("Key Misconceptions:")
        for m in discussion["misconceptions"]:
            class_lines.append(f"- {m}")

    # lesson emphasis
    class_lines.append("")
    class_lines.append("Lesson Focus (from teacher notes):")
    if lesson_kp:
        for kp in lesson_kp:
            class_lines.append(f"- {kp}")
    else:
        class_lines.append("- (none provided)")

    # exam high loss questions
    if high_loss_questions:
        class_lines.append("")
        class_lines.append("High Loss Questions (exam):")
        for qid, qm in high_loss_questions:
            kp = kp_map.get(qid, "uncategorized") if kp_map else "uncategorized"
            class_lines.append(f"- {qid} (loss_rate={qm['loss_rate']:.2f}, KP={kp})")

    # knowledge point loss list
    if kp_list:
        class_lines.append("")
        class_lines.append("Knowledge Point Loss (exam):")
        for kp in kp_list[: args.top_kp]:
            class_lines.append(f"- {kp['kp_id']} (loss_rate={kp['loss_rate']:.2f}, count={kp['count']})")

    # class assignments
    class_lines.append("")
    class_lines.append("Class Assignments:")
    if lesson_kp:
        for kp in lesson_kp:
            class_lines.append(f"- {kp}: {kp_assignments(None, emphasis=True)}")
    elif kp_list:
        for kp in kp_list[: args.top_kp]:
            if kp["kp_id"] == "uncategorized":
                class_lines.append("- 未映射知识点：请先补充映射再生成作业")
            else:
                class_lines.append(f"- {kp['kp_id']}: {kp_assignments(kp['loss_rate'])}")
    else:
        class_lines.append("- (no assignments) 请提供课堂重点或考试数据")

    # observations and homework focus
    if discussion.get("observations"):
        class_lines.append("")
        class_lines.append("Class Observations:")
        for obs in discussion["observations"]:
            class_lines.append(f"- {obs}")

    if discussion.get("homework_focus"):
        class_lines.append("")
        class_lines.append("Homework Focus:")
        for item in discussion["homework_focus"]:
            class_lines.append(f"- {item}")

    class_output = "\n".join(class_lines)

    if args.out_class:
        out_class = Path(args.out_class)
        out_class.parent.mkdir(parents=True, exist_ok=True)
        out_class.write_text(class_output, encoding="utf-8")
        print(f"[OK] Wrote {out_class}")
    else:
        print(class_output)

    # per-student outputs (optional)
    if not args.out_students_dir:
        return

    out_dir = Path(args.out_students_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    student_notes = load_student_notes(Path(args.student_notes)) if args.student_notes else []
    notes_by_student = defaultdict(list)
    for row in student_notes:
        name = row.get("student_name") or row.get("name")
        if not name:
            continue
        notes_by_student[name].append(row)

    # build exam totals for masking
    totals_by_student = {}
    sorted_totals = []
    if args.include_exam and rows and max_scores:
        for r in rows:
            sid = r.get("student_id") or r.get("student_name")
            if not sid:
                continue
            totals_by_student.setdefault(sid, 0.0)
            totals_by_student[sid] += parse_score(r.get("score")) or 0.0
        sorted_totals = sorted(totals_by_student.items(), key=lambda x: x[1], reverse=True)
        max_total = sum(v for v in max_scores.values() if v)
    else:
        max_total = 0.0

    # per-student output based on notes
    for student, srows in notes_by_student.items():
        weak_kp = []
        strength_kp = []
        note_lines = []
        actions = []
        for row in srows:
            weak_kp.extend(split_kp_list(row.get("weak_kp", "")))
            strength_kp.extend(split_kp_list(row.get("strength_kp", "")))
            if row.get("note"):
                note_lines.append(row.get("note"))
            if row.get("action"):
                actions.append(row.get("action"))

        lines = []
        lines.append(f"Student: {student} | Exam: {args.exam_id}")

        if student in totals_by_student and max_total > 0 and sorted_totals:
            rank = next((i for i, (sid, _) in enumerate(sorted_totals, start=1) if sid == student), None)
            if rank is not None:
                score_pct = (totals_by_student[student] / max_total) * 100
                sb_floor, sb_ceil = decile_band(score_pct)
                percentile = percentile_rank(rank, len(sorted_totals))
                rb_floor, rb_ceil = decile_band(percentile)
                lines.append(f"Sensitive (masked): ScoreBand={sb_floor}–{sb_ceil}% | RankBand=P{rb_floor}–{rb_ceil}")
        else:
            lines.append("Sensitive (masked): ScoreBand=? | RankBand=?")

        lines.append("")
        lines.append("Diagnosis:")
        if weak_kp:
            for kp in weak_kp:
                lines.append(f"- Weak points: {kp}")
        else:
            lines.append("- Weak points: (from teacher notes not provided)")

        lines.append("")
        lines.append("Strengths:")
        if strength_kp:
            for kp in strength_kp:
                lines.append(f"- Strengths: {kp}")
        else:
            lines.append("- Strengths: (not noted)")

        if note_lines:
            lines.append("")
            lines.append("Teacher Notes:")
            for n in note_lines:
                lines.append(f"- {n}")

        lines.append("")
        lines.append("Assignments:")
        if actions:
            for a in actions:
                lines.append(f"- {a}")
        elif weak_kp:
            for kp in weak_kp:
                lines.append(f"- {kp}: {kp_assignments(None, emphasis=True)}")
        else:
            lines.append("- (no assignment) 请补充弱项或作业建议")

        lines.append("")
        lines.append("Next Focus:")
        if weak_kp:
            lines.append(f"优先补强 {weak_kp[0]}，同步修正相关题型方法与表达。")
        else:
            lines.append("根据课堂表现补充新的关注点。")

        out_path = out_dir / f"{sanitize_name(student)}.md"
        out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Wrote student diagnostics to {out_dir}")


if __name__ == "__main__":
    main()
