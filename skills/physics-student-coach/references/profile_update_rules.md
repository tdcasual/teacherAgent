# Profile Update Rules (Student)

## Core Rules
- Only update derived fields (mastery estimates, recent weak KP, practice history).
- Do not alter raw scores or exam responses.
- Store structured interaction notes for teacher review (max 200 chars).
- Sensitive data must remain masked (ScoreBand/RankBand).

## Two-Layer Update Strategy

### Layer 1: Per-Turn Rule Extraction (real-time)
- **Trigger:** Every chat turn in student session.
- **Method:** Regex + keyword matching on LLM reply text.
- **Updates:** `weak_kp`, `strong_kp`, `next_focus`, `interaction_notes`.
- **Cost:** Zero (no extra LLM call).
- **Precision:** Moderate — captures explicit signals only.

### Layer 2: Session-Level LLM Summary (on assignment completion)
- **Trigger:** Student completes assignment (front-end signal).
- **Method:** LLM extracts structured diagnostics from full session transcript.
- **Updates:** All Layer 1 fields + `mastery_by_kp`, `misconceptions`, `summary`.
- **Cost:** One LLM call per session.
- **Precision:** High — understands context and nuance.
- Layer 2 results **override** Layer 1 results for the same session.

## Storage
- Profile file: `data/student_profiles/<student_id>.json`
- Lock file: `data/student_profiles/<student_id>.json.lock`
- Snapshot: `data/student_profiles/<student_id>.prev.json`

## Automation
- Layer 1: Integrated into `chat_handlers.py` → `update_profile.py`
- Layer 2: `scripts/student_session_finalize.py` or `session_finalize_service.py`
- Change detection: `scripts/check_profile_changes.py`
- Mem0 write: `scripts/profile_to_mem0.py` (requires teacher confirmation)
