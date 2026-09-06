---
name: homework-generator
description: Teacher-side homework generator. assignment.generate writes a draft only; publish with assignment.publish after the teacher confirms on the workbench.
---

# Homework Generator (Teacher-side)

## Overview
Use this skill to generate class homework as a **draft** (`visibility_status=draft`). Tell the teacher to confirm on the workbench (or call `assignment.publish`) before students can see it.

## Required Inputs
- assignment_id
- subject_id
- optional: date, due_at, class_name, knowledge points, question ids

## Workflow
1. Call `assignment.generate` with the teacher's identity. The tool writes a draft only.
2. Review the draft on the teacher workbench.
3. Publish with `assignment.publish` after the teacher confirms. Students cannot see drafts.

Do not generate homework from exam score files. Do not call deleted `physics-teacher-ops` scripts.

## CLI Quick Start
Teacher chat:

```
生成作业 HW_2026-09-01，学科 math，班级 高二2403班
```

The runtime stamps `teacher_id` from the authenticated teacher. Existing assignments owned by another teacher are rejected.

## References
- references/homework_templates.md
- references/student_notes_schema.md
