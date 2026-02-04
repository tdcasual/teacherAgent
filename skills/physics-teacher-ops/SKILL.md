---
name: physics-teacher-ops
description: Teacher-facing physics instruction operations: ingest exams, answer keys, and scores (xls/xlsx); generate and discuss exam analyses; manage knowledge-point taxonomy; plan lessons; produce pre-class checks and post-class diagnostics; curate lesson plans and study guides; update student profiles. Use when collaborating with teachers on classroom discussion, exam review, lesson planning, or knowledge-point curation.
---

# Physics Teacher Ops

## Overview
Use this skill to run teacher-facing workflows for physics teaching. Ingest exams and scores, generate exam analyses, discuss classroom learning, curate knowledge points, and prepare lesson assets.

## Required Inputs
- Exam paper or question set (PDF/DOCX/Markdown)
- Answer key (inline or separate)
- Per-student question-level scores (xls/xlsx)
- Optional question metadata (difficulty, knowledge point)
- Optional student roster and class info

## Workflow: Exam Analysis (Auto -> Discuss -> Save)
1. Ingest paper, answer key, and scores at question level.
2. Normalize question IDs and align with paper order and point values.
3. Generate a draft analysis focused on knowledge-point coverage and loss concentration.
4. Present the draft and ask the teacher to confirm or correct using the Discussion Prompts.
5. Record overrides and discussion notes.
6. Save a new version as the confirmed analysis.
7. On recompute, re-run metrics and re-apply overrides.
8. After confirmation, write a concise summary to mem0 (teacher memory).

## Discussion Prompts (Use Verbatim)
- Confirm the knowledge point mapping for top loss questions.
- Adjust any question difficulty labels?
- Mark any question as a key concept?
- Merge, rename, or split any knowledge points?
- What should be the next-lesson focus?

## Workflow: Class Discussion & Student Situation
1. Summarize class-wide weak knowledge points and high-error questions.
2. Identify students needing attention with evidence from responses.
3. Capture teacher notes about misconceptions, pacing, and next steps.
4. Ask whether to write back derived profile updates.
5. Write back derived updates only after confirmation.
6. Write a concise discussion summary to mem0 (teacher memory).

## Workflow: Lesson Planning & Assets
1. Capture lesson topic, target knowledge points, and prerequisites.
2. Generate pre-class check items from prerequisites and target points.
3. Generate post-class diagnostics and personalized homework summaries.
4. Store lesson plan, precheck, and study guide assets.
5. Write lesson plan summary to mem0 when teacher confirms.

## Knowledge-Point Lifecycle (Draft -> Confirmed)
- Allow uncategorized questions when the taxonomy is blank.
- Propose new knowledge points as drafts.
- Request teacher confirmation before promotion.
- Record mapping changes for traceability and re-analysis.
- After confirmation, store a short “knowledge point decision” note in mem0.

## Data Rules
- Treat exam response data as immutable facts.
- Store subjective-question rubrics; do not store deduction reasons.
- Keep student profile updates separate from raw exam records.
- Only write confirmed summaries to mem0. Never store raw scores in mem0.

## Output Templates

Exam Analysis Summary:
```text
Exam: {exam_id} | Date: {date} | Class: {class}
Coverage (Top 5):
- {kp}: {weight}
Loss Concentration (Top 5):
- {kp}: {loss_rate}
High-Error Questions:
- {question_id}: {note}
Teacher Notes:
- {notes}
Next-Lesson Focus:
- {focus}
```

Class Discussion Summary:
```text
Lesson: {topic} | Date: {date}
Key Misconceptions:
- {misconception}
Pacing Notes:
- {note}
Next Steps:
- {action}
```

Pre-Class Check List:
```text
Lesson: {topic}
Targets: {target_kp}
Items:
- {question_id or prompt}
```

Post-Class Diagnostic (Per Student):
```text
Student: {name} | Exam: {exam_id}
Weak Points:
- {kp}: {evidence}
Assignments:
- {task} (why: {reason})
```

Knowledge Point Confirmation Request:
```text
Proposed Knowledge Points:
- {kp_name} (from questions: {question_ids})
Please confirm, rename, or reject each item.
```

## Resources
- references/data_model.md
- references/data_io.md
- references/analysis_workflow.md
- references/knowledge_points.md
