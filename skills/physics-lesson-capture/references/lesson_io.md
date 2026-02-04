# Lesson Capture IO

## Directory Layout

```
data/lessons/<lesson_id>/
  sources/               # original files (pdf/docx/images)
  manifest.json          # source manifest
  ocr/                   # raw OCR json per page/image
  text/                  # cleaned text per page/file
  examples/              # extracted example items
  examples.csv           # index of examples
  class_discussion.md    # teacher discussion summary
  lesson_summary.md      # lesson digest for diagnostics
```

## Manifest (manifest.json)
```json
{
  "lesson_id": "L2403_2026-02-04",
  "topic": "静电场综合",
  "sources": [
    {"file": "lesson.pdf", "type": "pdf"},
    {"file": "example_01.png", "type": "image"}
  ]
}
```

## examples.csv
- example_id
- lesson_id
- stem_text
- options
- answer (optional)
- kp_candidate (optional)
- difficulty (optional)
- source_ref (file + page)
- notes

## class_discussion.md
Use the template in `references/discussion_template.md`.

## lesson_summary.md
- Lesson topic
- Key misconceptions
- Focus knowledge points
- Example list
- Homework focus
