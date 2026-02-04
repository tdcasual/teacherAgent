---
name: physics-lesson-capture
description: Capture lesson content from images/PDF/DOCX, run OCR (DeepSeek-OCR), extract example questions, summarize classroom discussion, and prepare lesson-first post-class diagnostics. Use when teachers provide lesson materials or discuss classroom content.
---

# Physics Lesson Capture

## Overview
Use this skill when the teacher provides lesson materials (images/PDF/DOCX) or describes classroom content. The goal is to OCR/parse the materials, extract example questions, and produce a structured lesson summary and discussion notes that can drive post-class diagnostics and homework.

## Required Inputs
- lesson_id (e.g., L2403_2026-02-04)
- lesson topic (string)
- class (optional)
- sources: images, PDF, or DOCX files
- optional teacher notes: classroom misconceptions, emphasis KPs, homework focus

## Workflow (Lesson-First)
1. **Ingest sources**
   - Copy sources into `data/lessons/<lesson_id>/sources/`.
   - Record a manifest file with filenames and types (see `references/lesson_io.md`).

2. **Extract text**
   - PDF: if text-based, use pdfplumber; if scanned, render pages to images and OCR.
   - DOCX: extract text via python-docx; OCR embedded images.
   - Images: OCR directly.
   - Use DeepSeek-OCR via SiliconFlow for OCR (see `references/ocr_pipeline.md`).
   - Script: `scripts/lesson_capture.py` handles OCR + extraction end-to-end.
   - If OCR quality is low, ask the teacher for a clearer scan or export to PDF.

3. **Build artifacts**
   - Save raw OCR output under `ocr/` and cleaned text under `text/`.
   - Keep page references for traceability.

4. **Extract example questions**
   - Split by numbering and option patterns (A/B/C/D).
   - Create `examples.csv` with `example_id`, `stem_text`, `options`, `source_ref`, `page`.
   - See `references/extract_rules.md` for heuristics.

5. **Summarize classroom content**
   - Parse teacher notes (or request confirmation) into a structured `class_discussion.md`.
   - Use template in `references/discussion_template.md`.

6. **Knowledge point candidates**
   - Propose KP candidates based on examples.
   - Require teacher confirmation before updating `data/knowledge/knowledge_point_map.csv`.

7. **Lesson-first post-class diagnostic**
   - If requested, call `generate_postclass_diagnostic.py` with `--discussion-notes` and `--student-notes`.
   - Only merge exam data when explicitly requested.

8. **Write-back rules**
   - Never store raw student scores here.
   - Only write confirmed summaries to mem0 using the teacher memory template.

## Output Templates
- `class_discussion.md` (structured classroom summary)
- `lesson_summary.md` (lesson digest + key misconceptions)
- `examples.csv` (example questions index)
- `lesson_review.md` (visual review report for OCR + examples)

## References
- references/lesson_io.md
- references/ocr_pipeline.md
- references/extract_rules.md
- references/discussion_template.md
- (Related) skills/physics-core-examples/SKILL.md

## CLI (Quick Start)
```bash
python3 skills/physics-lesson-capture/scripts/lesson_capture.py \\
  --lesson-id L2403_2026-02-04 \\
  --topic \"静电场综合\" \\
  --sources /path/to/lesson.pdf /path/to/example.png \\
  --discussion-notes /path/to/class_discussion.md
```

Optional:
- `--lesson-plan` to include teacher plan (PDF/DOCX/MD)
- `--force-ocr` to OCR even text-based PDFs
- `--ocr-mode FREE_OCR|GROUNDING|OCR_IMAGE`

Review report:
```bash
python3 skills/physics-lesson-capture/scripts/lesson_review_report.py \\
  --lesson-id L2403_2026-02-04 \\
  --render-pdf
```

Confirm KP candidates from the review:
```bash
python3 skills/physics-lesson-capture/scripts/confirm_kp_candidates.py \\
  --lesson-id L2403_2026-02-04
```

Apply confirmed KP candidates to knowledge_point_map.csv:
```bash
python3 skills/physics-lesson-capture/scripts/apply_kp_to_question_map.py \\
  --lesson-id L2403_2026-02-04
```
