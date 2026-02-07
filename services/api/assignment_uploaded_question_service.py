from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class AssignmentUploadedQuestionDeps:
    safe_slug: Callable[[str], str]
    normalize_difficulty: Callable[[Any], str]


def write_uploaded_questions(
    out_dir: Path,
    assignment_id: str,
    questions: List[Dict[str, Any]],
    deps: AssignmentUploadedQuestionDeps,
) -> List[Dict[str, Any]]:
    stem_dir = out_dir / "uploaded_stems"
    answer_dir = out_dir / "uploaded_answers"
    stem_dir.mkdir(parents=True, exist_ok=True)
    answer_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    slug = deps.safe_slug(assignment_id)
    for idx, question in enumerate(questions, start=1):
        qid = f"UP-{slug}-{idx:03d}"
        stem = str(question.get("stem") or "").strip()
        answer = str(question.get("answer") or "").strip()
        kp = str(question.get("kp") or "uncategorized").strip() or "uncategorized"
        difficulty = deps.normalize_difficulty(question.get("difficulty"))
        qtype = str(question.get("type") or "upload").strip() or "upload"
        tags = question.get("tags") or []
        if isinstance(tags, list):
            tags_str = ",".join([str(tag) for tag in tags if tag])
        else:
            tags_str = str(tags)

        stem_ref = stem_dir / f"{qid}.md"
        stem_ref.write_text(stem or "【空题干】请补充题干。", encoding="utf-8")

        answer_ref = ""
        answer_text = ""
        if answer:
            answer_ref = str(answer_dir / f"{qid}.md")
            Path(answer_ref).write_text(answer, encoding="utf-8")
            answer_text = answer

        rows.append(
            {
                "question_id": qid,
                "kp_id": kp,
                "difficulty": difficulty,
                "type": qtype,
                "stem_ref": str(stem_ref),
                "answer_ref": answer_ref,
                "answer_text": answer_text,
                "source": "teacher_upload",
                "tags": tags_str,
            }
        )

    questions_path = out_dir / "questions.csv"
    if rows:
        with questions_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    return rows
