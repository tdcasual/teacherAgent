# Multi-Domain Analysis Go-Live Summary

Date: 2026-03-07
Target release: `main@d727fcd`
Status: Ready for controlled rollout

## Release Decision

Go decision: `GO for controlled rollout`, not blanket full release.

Reason:

- implementation plan is complete
- final targeted verification passed in Python `3.13.12`
- unified runtime contract, rollout checklist, and eval guardrails are present
- current architecture still preserves the single front-facing `Coordinator`

## What Is Shipping

This go-live covers a unified teacher analysis runtime for:

- `survey`
- `class_report`
- `video_homework`

The release includes:

- unified analysis reports and review queue
- explicit analysis target routing
- artifact adapters for new B-type sources
- multimodal extraction and analysis loop for C-type video homework
- cross-domain evaluation and rollout guardrails

## Recommended Rollout Shape

### Stage 1: Internal / shadow

Recommended immediately after deployment:

- Survey: keep controlled enablement with `SURVEY_SHADOW_MODE=1` unless an explicit beta plan is already approved
- Class report: internal-only validation on representative self-hosted form / exported report fixtures
- Video homework: internal-only validation on sample teacher submissions and extraction timings

### Stage 2: Small cohort

Only after Stage 1 remains stable:

- Survey: expand via `SURVEY_BETA_TEACHER_ALLOWLIST`
- Class report: open to selected internal or partner teachers with known input patterns
- Video homework: open to a small teacher cohort with upload size and duration controls confirmed

### Stage 3: Broader rollout

Proceed only after:

- review queue pressure remains manageable
- rerun flow works for all three domains
- no cross-teacher data isolation issue appears
- teacher workbench remains stable under mixed-domain usage

## Required Runtime Controls

Survey controls:

- `SURVEY_ANALYSIS_ENABLED`
- `SURVEY_SHADOW_MODE`
- `SURVEY_BETA_TEACHER_ALLOWLIST`
- `SURVEY_REVIEW_CONFIDENCE_FLOOR`

Multimodal controls:

- `MULTIMODAL_ENABLED`
- `MULTIMODAL_MAX_UPLOAD_BYTES`
- `MULTIMODAL_MAX_DURATION_SEC`
- `MULTIMODAL_EXTRACT_TIMEOUT_SEC`

Teacher frontend controls:

- `teacherAnalysisWorkbench`
- `teacherAnalysisWorkbenchShadow`
- `teacherSurveyAnalysis`
- `teacherSurveyAnalysisShadow`

## Verification Evidence

Final local verification completed on 2026-03-07:

- Backend targeted suite: `93 passed`
- Frontend targeted suite: `4 passed`
- Teacher build: passed
- Cross-domain eval: `expectation_failures = 0`
- Docs / CI rollout tests: `10 passed`

## Operational Watchpoints

Primary watchpoints during rollout:

- report generation success rate by domain
- review queue inflow rate and unresolved backlog
- multimodal extraction timeout / failure rate
- rerun request volume by domain
- teacher-reported false positives / misleading summaries
- any cross-tenant or cross-teacher data access anomaly

## No-Go / Rollback Triggers

Treat any of the following as immediate stop-or-rollback conditions:

- teacher workbench becomes unstable or misleading
- cross-teacher data isolation issue
- multimodal uploads or extraction repeatedly fail under normal traffic
- review queue volume spikes beyond on-call handling capacity
- low-confidence results bypass review queue and surface as final outputs

## Source Documents

- Runtime contract: `docs/reference/analysis-runtime-contract.md`
- Rollout checklist: `docs/operations/multi-domain-analysis-rollout-checklist.md`
- Survey contract: `docs/reference/survey-analysis-contract.md`
- Implementation plan: `docs/plans/2026-03-07-agent-system-bc-evolution-implementation-plan.md`
