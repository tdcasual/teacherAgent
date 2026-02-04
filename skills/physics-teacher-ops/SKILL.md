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
8. After confirmation, write a concise summary to mem0 (teacher memory) using the template below.

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
6. Write a concise discussion summary to mem0 (teacher memory) using the template below.

## Workflow: Lesson Planning & Assets
1. Capture lesson topic, target knowledge points, and prerequisites.
2. Generate pre-class check items from prerequisites and target points.
3. Generate post-class diagnostics and personalized homework summaries.
4. Store lesson plan, precheck, and study guide assets.
5. Write lesson plan summary to mem0 when teacher confirms, using the template below.

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
- Mask sensitive data as decile bands.
- Band scheme (ScoreBand): 0–9%, 10–19%, 20–29%, 30–39%, 40–49%, 50–59%, 60–69%, 70–79%, 80–89%, 90–100% (score percentage of total).
- Band scheme (RankBand): P0–9, P10–19, P20–29, P30–39, P40–49, P50–59, P60–69, P70–79, P80–89, P90–100 (percentile; P0 is top, P100 is bottom).

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

Mem0 Teacher Memory Template:
```text
[MEM:TEACHER]
Scope: {exam_id | lesson_id | class_id}
Context: {考试分析 | 课堂讨论 | 备课 | 课后作业/练习}
Findings: {高失分题/薄弱知识点/课堂误区}
Decisions: {已确认的判断与修正}
Actions: {下一步教学动作}
Sensitive (masked): {ScoreBand=30–39% | RankBand=P70–79 | Trend=↓}
FactsRef: {exam_id / class_id / 数据文件引用}
Tags: {KP-ID, topic, class}
```

## Exam Pipeline (CLI)
1. Parse scores: `python3 skills/physics-teacher-ops/scripts/parse_scores.py --scores <xls/xlsx> --exam-id <id> --sheet-name 物理 --out data/staging/responses_physics.csv`
2. Apply answers: `python3 skills/physics-teacher-ops/scripts/apply_answer_key.py --responses data/staging/responses_physics.csv --answers data/staging/answers_physics.csv --questions data/staging/questions_physics.csv --out data/staging/responses_physics_scored.csv`
3. Compute draft: `python3 skills/physics-teacher-ops/scripts/compute_exam_metrics.py --exam-id <id> --responses data/staging/responses_physics_scored.csv --questions data/staging/questions_physics.csv --knowledge-map data/knowledge/knowledge_point_map.csv --out-json data/analysis/<id>/draft.json --out-md data/analysis/<id>/draft.md`
4. Bundle exam: `python3 skills/physics-teacher-ops/scripts/merge_exam_bundle.py --exam-id <id> --questions data/staging/questions_physics.csv --answers data/staging/answers_physics.csv --responses data/staging/responses_physics_scored.csv`
5. Confirm discussion: save notes/overrides, then `python3 skills/physics-teacher-ops/scripts/apply_discussion_overrides.py --draft data/analysis/<id>/draft.json --overrides <overrides.json> --notes <notes.md> --out data/analysis/<id>/vN.json`
6. Write mem0 summary after confirmation: `python3 scripts/memory_write.py --user-id teacher:physics --text \"...\"`
7. Student diagnosis (masked): `python3 skills/physics-teacher-ops/scripts/generate_student_diagnosis.py --exam-id <id> --responses data/staging/responses_physics_scored.csv --questions data/staging/questions_physics.csv --knowledge-map data/knowledge/knowledge_point_map.csv --student-name <name> --out data/analysis/<id>/students/<name>.md`
8. Pre-class checklist: `python3 skills/physics-teacher-ops/scripts/generate_preclass_checklist.py --exam-id <id> --responses data/staging/responses_physics_scored.csv --questions data/staging/questions_physics.csv --knowledge-map data/knowledge/knowledge_point_map.csv --lesson-topic <topic> --out data/analysis/<id>/preclass_checklist.md`
9. Post-class diagnostic + homework (lesson-first):
   - `python3 skills/physics-teacher-ops/scripts/generate_postclass_diagnostic.py --exam-id <id> --lesson-topic <topic> --discussion-notes <class_discussion.md> --lesson-plan <lesson_plan.md> --student-notes <student_notes.csv> --out-class data/analysis/<id>/postclass_diagnostic.md --out-students-dir data/analysis/<id>/postclass_students`
   - Optional exam merge: add `--include-exam --responses data/staging/responses_physics_scored.csv --questions data/staging/questions_physics.csv --knowledge-map data/knowledge/knowledge_point_map.csv`

## Resources
- references/data_model.md
- references/data_io.md
- references/analysis_workflow.md
- references/knowledge_points.md
- (Related) skills/physics-homework-generator/SKILL.md
- (Related) skills/physics-student-focus/SKILL.md
