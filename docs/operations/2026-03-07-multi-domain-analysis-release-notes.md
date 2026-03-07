# Multi-Domain Analysis Runtime Release Notes

Date: 2026-03-07
Release: `main@d727fcd`
Scope: Unified teacher-side analysis runtime covering `survey`, `class_report`, and `video_homework`

## Summary

This release upgrades the existing teacher workflow from a survey-only analysis path into a unified multi-domain analysis runtime.

The front-facing interaction model does not change: `Coordinator` remains the only default user-facing agent. Domain specialists stay behind the control plane and are invoked only through explicit runtime selection.

The new runtime now supports:

- Survey analysis (`survey`)
- Self-hosted form / report analysis (`class_report`)
- Video homework analysis (`video_homework`)

## What Changed

### 1. Unified analysis plane

A shared platform layer now handles:

- analysis target resolution
- artifact normalization / adapters
- strategy planning and selection
- specialist runtime governance
- unified analysis reports
- unified review queue

Primary runtime contract:

- `docs/reference/analysis-runtime-contract.md`

Teacher-facing unified APIs:

- `GET /teacher/analysis/reports`
- `GET /teacher/analysis/reports/{report_id}`
- `POST /teacher/analysis/reports/{report_id}/rerun`
- `GET /teacher/analysis/review-queue`

## 2. Domain expansion

### Survey

Survey analysis remains supported, but now runs as a built-in strategy on the shared analysis plane.

Backward-compatible survey domain endpoints remain available:

- `POST /webhooks/surveys/provider`
- `GET /teacher/surveys/reports`
- `GET /teacher/surveys/reports/{report_id}`
- `POST /teacher/surveys/reports/{report_id}/rerun`
- `GET /teacher/surveys/review-queue`

Reference contract:

- `docs/reference/survey-analysis-contract.md`

### Class report

Class-report analysis is added for B-type evolution scenarios such as self-hosted form exports and web/PDF-like report inputs.

Implemented pieces include:

- report adapters for self-hosted form JSON, web export HTML, and PDF summary inputs
- class signal bundle artifact model
- class report orchestrator and specialist
- unified report/review integration on the common plane

### Video homework

Video-homework analysis is added for C-type evolution scenarios.

Implemented pieces include:

- multimodal submission bundle model
- upload / extraction / analyze flow
- video homework specialist
- teacher-side domain detail rendering in the shared workbench

Domain APIs:

- `POST /teacher/multimodal/submissions`
- `GET /teacher/multimodal/submissions/{submission_id}`
- `POST /teacher/multimodal/submissions/{submission_id}/extract`
- `POST /teacher/multimodal/submissions/{submission_id}/analyze`

## 3. Teacher workbench changes

Teacher workbench now reads from the unified analysis report plane instead of a survey-only report list.

Frontend changes include:

- shared analysis report list/review fetching
- unified report selection flow
- survey-compatible workbench behavior retained
- video-homework detail section for domain-specific rendering

Relevant frontend flags:

- `teacherAnalysisWorkbench`
- `teacherAnalysisWorkbenchShadow`
- `teacherSurveyAnalysis`
- `teacherSurveyAnalysisShadow`

## 4. Rollout and evaluation guardrails

This release adds cross-domain offline evaluation and rollout guardrails.

New guardrails include:

- cross-domain eval script: `scripts/analysis_strategy_eval.py`
- minimal golden fixtures for `survey`, `class_report`, and `video_homework`
- runtime contract documentation
- unified rollout checklist
- CI coverage for docs/eval rollout gates

Operational checklist:

- `docs/operations/multi-domain-analysis-rollout-checklist.md`

## Verification Snapshot

Validated locally on 2026-03-07 with Python `3.13.12`.

Results:

- Backend targeted verification: `93 passed`
- Frontend targeted unit tests: `4 passed`
- Teacher frontend build: passed
- Cross-domain eval: `fixture_count = 5`, `expectation_failures = 0`
- Docs / CI rollout tests: `10 passed`

## Backward Compatibility

- `Coordinator` remains the only default front-facing agent
- survey façade endpoints remain available
- low-confidence outputs still downgrade into review queue rather than surfacing as final teacher truth
- new domains extend the shared runtime instead of introducing a parallel agent platform

## Known Constraints

- This release does not turn the product into a generic open multi-agent platform
- `class_report` currently focuses on the planned B-type adapter-driven inputs
- `video_homework` currently focuses on the planned C-type teacher workflow and extraction/analyze loop
- future domain additions should extend `artifact + strategy + runtime + report/review` rather than duplicate the survey stack

## Recommended Next Actions

1. Use `docs/operations/multi-domain-analysis-rollout-checklist.md` as the release owner checklist.
2. Keep survey in controlled rollout if production enablement is still staged.
3. Enable multimodal only in environments where upload size, duration, and extraction timeout are explicitly set.
4. Use the unified review queue as the default downgrade path for any low-confidence multi-domain result.
