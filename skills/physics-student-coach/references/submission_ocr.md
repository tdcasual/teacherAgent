# Submission OCR & Feedback

## Inputs
- Student photo(s) of completed work
- Assignment ID (can be auto-detected if included in the assignment sheet)

## OCR
- Use DeepSeek-OCR via SiliconFlow (same config as lesson capture)
- Save raw OCR and cleaned text for traceability
- If OCR quality is low, request a clearer image

## Evaluation
- Match OCR text to assignment questions
- Use rubric for subjective items when available
- Provide feedback in 3 parts: correctness, missing steps, next focus
 - If assignment_id is missing, try to detect it from OCR text or match against existing assignments

## Storage
- data/student_submissions/<student_id>/<timestamp>/ocr.json
- data/student_submissions/<student_id>/<timestamp>/feedback.md
- Update student profile (derived fields only)
