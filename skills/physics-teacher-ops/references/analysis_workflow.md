# Exam Analysis Workflow

Focus on knowledge-point coverage and loss concentration. Treat analysis as versioned output that is discussed with the teacher before saving.

## Auto Metrics (Draft)

- Coverage: knowledge points included and their weight by score
- Loss concentration: loss rate per knowledge point (sorted)
- High-error questions: low average score or high error rate
- Difficulty band: basic / medium / advanced distribution
- Distribution: class score histogram, average, median (optional)

## Discussion Overrides (Teacher Input)

Common overrides to capture in discussion notes:
- knowledge point mapping corrections (question_id -> kp_id)
- difficulty correction for a question or section
- key concept flag for a question
- remove/merge a knowledge point label

## Versioning Rules

- Each confirmed discussion produces a new version.
- Store auto metrics + discussion notes + overrides.
- Recompute later using the same raw responses and apply overrides as constraints.

## Output Structure (Summary)

- Exam context
- Knowledge point coverage (top 5)
- Loss concentration (top 5)
- Teacher discussion notes
- Teaching recommendations (next lesson focus)
