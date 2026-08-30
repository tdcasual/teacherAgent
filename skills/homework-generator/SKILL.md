---
name: homework-generator
description: Teacher-side homework generator. assignment.generate writes a draft only; publish with assignment.publish after the teacher confirms on the workbench.
---

# Homework Generator (Teacher-side)

## Overview
Use this skill to generate class homework as a **draft** (`visibility_status=draft`). Tell the teacher to confirm on the workbench (or call `assignment.publish`) before students can see it.

## Required Inputs
- lesson_id
- lesson topic
- discussion notes (md)
- optional: lesson plan (pdf/docx/md)
- optional: student notes (csv)
- optional: exam data (responses_scored.csv + questions.csv + knowledge_point_map.csv)

## Workflow
1. Collect lesson materials and discussion notes
   - If lesson materials are provided, use `physics-lesson-capture` first to extract examples and build discussion summary.
   - Ensure `class_discussion.md` exists (see template in references).

2. Generate post-class diagnostics
   - Use `scripts/generate_postclass_diagnostic.py` (teacher ops) in lesson-first mode.
   - If exam data should be merged, add `--include-exam`.

3. Generate student-specific homework
   - Use `--student-notes` to inject teacher observations.
   - If exam data is not merged, student homework is derived from teacher notes only.

4. Review and discuss
   - Present the draft to the teacher for confirmation before any mem0 writeback.

5. Writeback (optional)
   - After confirmation, write a concise summary to mem0 using teacher template.
   - Do not store raw scores or rankings.

## Output Templates
- `postclass_diagnostic.md`
- `postclass_students/<name>.md`

## CLI Quick Start
```bash
python3 skills/physics-teacher-ops/scripts/generate_postclass_diagnostic.py \
  --exam-id EX2403_PHY \
  --lesson-topic "期中薄弱点回顾" \
  --discussion-notes data/analysis/EX2403_PHY/class_discussion.md \
  --student-notes data/analysis/EX2403_PHY/student_notes.csv \
  --out-class data/analysis/EX2403_PHY/postclass_diagnostic.md \
  --out-students-dir data/analysis/EX2403_PHY/postclass_students
```

Optional exam merge:
```bash
--include-exam \
--responses data/staging/responses_physics_scored.csv \
--questions data/staging/questions_physics.csv \
--knowledge-map data/knowledge/knowledge_point_map.csv
```

## References
- references/homework_templates.md
- references/student_notes_schema.md
- (Related) skills/physics-core-examples/SKILL.md
