# Profile Update Rules (Student)

- Only update derived fields (mastery estimates, recent weak KP, practice history).
- Do not alter raw scores or exam responses.
- Store a short interaction note for teacher review.
- Sensitive data must remain masked (ScoreBand/RankBand).

## Storage
- student profile file: `data/student_profiles/<student_id>.json`

## Automation
- Use `skills/physics-student-coach/scripts/update_profile.py` after each student interaction to auto write derived fields.
- For end-of-session automation, use `scripts/student_session_finalize.py` with a transcript or summary JSON.
