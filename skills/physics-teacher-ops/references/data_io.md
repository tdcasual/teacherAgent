# Data IO (CSV Fact Source)

Use CSV as the immutable fact source. Scripts normalize question numbers and sub-questions, then generate stable question_id values.

## Canonical CSV Schemas

responses.csv (fact source)
- exam_id
- student_id
- student_name
- class_name (optional)
- question_id (optional)
- question_no (integer)
- sub_no (string, optional; example: "a", "1")
- raw_label (optional; example: "12(1)")
- raw_value (string)
- raw_answer (optional; for non-numeric values like A/B/CD)
- score (number, optional; filled when numeric or after key match)

questions.csv
- question_id
- question_no
- sub_no (optional)
- order
- max_score
- stem_ref

answers.csv
- question_id
- answer_ref
- rubric_ref (optional)
- correct_answer (optional for objective items)

question_map.csv
- raw_label
- question_no
- sub_no
- question_id

knowledge_point_map.csv
- question_id
- kp_id (nullable)

## Question ID Rules

- If no sub-question: question_id = "Q{question_no}"
- If sub-question: question_id = "Q{question_no}{sub_no}" (example: Q12a or Q12-1)
- Keep raw_label for traceability.

## Student ID Rules

- If student_id is missing in the source, generate it from class_name + student_name.
- Normalize by trimming spaces and replacing internal spaces with underscores.
- Keep class_name in responses.csv when using generated IDs.

## Header Detection

- Header row is the first row containing both \"姓名\" and \"班级\" or \"姓名\" and \"准考证号\".
- The title row (e.g., \"【2025...】...小题得分明细\") is ignored.
- Question columns are those whose header looks like a number or number+sub (e.g., 12, 12(1), 12-1, 12a).
- Non-question columns (序号/姓名/准考证号/自定义考号/班级/总分/校次/班次) are ignored.

## Script Interfaces (CLI Draft)

parse_scores.py
- --scores <xls/xlsx>
- --exam-id <id>
- --class-name <name> (required if class_name column is missing)
- --header-row <n> (optional override)
- --sheet <n> (optional sheet index, 1-based)
- --sheet-name <name> (optional sheet name, overrides --sheet)
- --out <responses.csv>

parse_paper.py
- --paper <pdf/docx/md>
- --paper-id <id>
- --out <questions.csv>

parse_answer_key.py
- --answer <xls/xlsx/md>
- --out <answers.csv>

merge_exam_bundle.py
- --questions <questions.csv>
- --answers <answers.csv>
- --responses <responses.csv>
- --out <data/exams/{exam_id}/manifest.json>
- --question-map-out <question_map.csv>

compute_exam_metrics.py
- --exam <manifest.json>
- --knowledge-map <knowledge_point_map.csv>
- --out <draft.json>

apply_discussion_overrides.py
- --draft <draft.json>
- --overrides <overrides.json>
- --notes <notes.md>
- --out <analysis_vN.json>

apply_answer_key.py
- --responses <responses.csv>
- --answers <answers.csv>
- --questions <questions.csv>
- --out <responses_scored.csv>

## Objective Scoring Rules (Current)

- Single choice: exact match -> full score, else 0.
- Multiple choice: max score = 6.
  - Exact match -> 6
  - Subset (no wrong options) -> 3
  - Any wrong option -> 0
- If only raw answers exist, compute after loading correct_answer + max_score from the paper/answer key.
