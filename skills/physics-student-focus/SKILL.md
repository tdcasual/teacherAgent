---
name: physics-student-focus
description: Teacher-side targeted student profiling from manual answer sheets or notes. OCR answer cards, summarize weaknesses, and update student profile when a teacher wants to focus on a specific student.
---

# Physics Student Focus (Teacher-side)

## Overview
Use this skill when a teacher wants to **manually focus on a specific student**. Inputs can include a student's answer sheet (photo/PDF), teacher notes, or a brief diagnosis. The output is a **derived profile update** (no raw scores), saved to `data/student_profiles/`.

## Required Inputs
- student_id (required)
- context (lesson/exam/assignment)
- teacher notes (optional)
- answer sheet files (optional; image/PDF)
- weak/strong KP (optional)

## Workflow
1. Collect student_id + context.
2. If answer sheet images/PDF are provided:
   - OCR using DeepSeek-OCR (SiliconFlow).
   - Save OCR output under `data/teacher_focus/<student_id>/<timestamp>/`.
3. Summarize weak/strong KP from teacher notes or OCR evidence.
4. Update profile using `skills/physics-student-coach/scripts/update_profile.py`.
   - If teacher discusses recent homework performance, pass `--discussion-notes` or `--recent-assignments`.
5. Confirm with teacher if they want to write a brief mem0 summary (optional).

## CLI Quick Start
```bash
python3 skills/physics-student-focus/scripts/teacher_focus_update.py \
  --student-id 高二2403班_武熙语 \
  --context "课堂针对性辅导" \
  --notes "电势差方向判断不稳，作图易错" \
  --weak-kp KP-E04,KP-M01 \
  --next-focus KP-E04 \
  --discussion-notes /path/to/homework_discussion.md \
  --recent-assignments /path/to/recent_homework.csv \
  --files /path/to/answer_sheet.jpg
```

## References
- references/input_schema.md
- references/answer_sheet_ocr.md
- references/update_profile.md
