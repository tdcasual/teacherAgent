# App.py Migration Notes (Cleanup)

## Scope

This note records cleanup decisions made after the `app.py` composition-root migration, so future refactors do not re-open already-settled module boundaries.

## Confirmed Cleanup

- Removed unused module: `/Users/lvxiaoer/Documents/New project/services/api/chat_preflight.py`
  - Reason: no runtime imports from `app.py` or other `services/api/*` modules.
  - Current role-hint path is covered by:
    - `/Users/lvxiaoer/Documents/New project/services/api/chat_job_processing_service.py`
    - `/Users/lvxiaoer/Documents/New project/services/api/chat_start_service.py`

## Uncertain/Deferred Splits (Documented Intentionally)

During migration, several `* 2.py` drafts suggested finer-grained teacher-memory modules (for example: `conflict`, `dedupe`, `infer`, `proposal_store`, `session_index`, `telemetry`, `time`). These were **not** promoted as standalone production modules.

Current accepted layout keeps that logic consolidated in:

- `/Users/lvxiaoer/Documents/New project/services/api/teacher_memory_record_service.py`
- `/Users/lvxiaoer/Documents/New project/services/api/teacher_memory_rules_service.py`
- `/Users/lvxiaoer/Documents/New project/services/api/teacher_memory_store_service.py`

Reason for deferral:

- Avoid over-fragmenting the teacher-memory domain before clear ownership and stable contracts.
- Keep behavior parity and test stability after migration.

If future work requires stronger boundaries, split from these canonical modules with contract tests first.
