# Current Agent System Priority Optimization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden the current single-front-facing `Coordinator` architecture into a more extensible, governable, and observable internal multi-specialist system without turning the product into an open multi-agent platform.

**Architecture:** Keep `Coordinator` as the only default front-facing agent and continue routing domain work through the unified analysis plane: `target resolver -> artifact adapter -> strategy selector -> specialist runtime -> analysis report / review queue`. Prioritize explicit target contracts, manifest-driven registration, stronger review/observability loops, and controlled internal orchestration for future B/C domain expansion.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, pytest, React 19, TypeScript, Vitest, Markdown docs, GitHub Actions.

---

## Scope

This plan is for the **next optimization wave** of the current agent system. It is not a re-architecture into a generic agent marketplace.

### In Scope

- Better extensibility for new analysis domains and new homework modalities
- Stronger governance for specialist execution
- Better analysis target clarity
- Better review queue operations and release safety
- Better observability, replayability, and rollout control

### Out of Scope

- Direct specialist-to-user takeover
- Open-ended agent-to-agent free conversation runtime
- Generic plugin marketplace / arbitrary third-party agent loading
- Replacing the current teacher workflow shell with a new product model

## Principles

1. `Coordinator` remains the only default front-facing agent.
2. Low-confidence outputs go to `review queue`, not directly to teacher truth.
3. New domains should mostly add `artifact + strategy + specialist + fixtures`, not duplicate the survey stack.
4. Any increase in internal agent sophistication must improve observability and rollback, not reduce it.
5. All behavior changes should land with targeted tests, rollout guardrails, and documentation.

---

## Phase P0: Must-Have Hardening

### Task 1: Replace centralized domain wiring with manifest-driven registration

**Files:**
- Create: `services/api/domains/manifest_models.py`
- Create: `services/api/domains/manifest_registry.py`
- Create: `tests/test_domain_manifest_registry.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Modify: `services/api/artifacts/registry.py`
- Modify: `services/api/strategies/selector.py`
- Modify: `docs/reference/analysis-runtime-contract.md`

**Steps:**
1. Write failing tests that require the runtime to load domain registration metadata from a manifest-style registry rather than only from hardcoded wiring functions.
2. Run `./.venv/bin/python -m pytest -q tests/test_domain_manifest_registry.py` and verify the tests fail for the expected missing registry behavior.
3. Implement manifest models for `domain`, `artifact_type`, `task_kind`, `strategy_id`, `specialist_agent`, rollout metadata, and feature flags.
4. Implement a registry loader that can expose all currently supported domains: `survey`, `class_report`, and `video_homework`.
5. Refactor current domain wiring so existing runtime registration flows through the manifest registry instead of domain-specific ad hoc registration.
6. Re-run the targeted tests and keep all existing selector / artifact / runtime tests green.
7. Update runtime docs to describe manifest-driven extension rules for future domains.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_domain_manifest_registry.py tests/test_artifact_registry.py tests/test_strategy_selector.py`
- Expected: PASS.

**Acceptance:**
- New domain registration is no longer concentrated in a single hot wiring file.
- Adding a future domain mainly requires one manifest entry plus domain-specific implementation pieces.

**Commit:**
```bash
git add services/api/domains/manifest_models.py services/api/domains/manifest_registry.py services/api/wiring/survey_wiring.py services/api/artifacts/registry.py services/api/strategies/selector.py tests/test_domain_manifest_registry.py docs/reference/analysis-runtime-contract.md
git commit -m "refactor(agents): add manifest-driven domain registration"
```

### Task 2: Make analysis target a first-class explicit contract

**Files:**
- Modify: `services/api/analysis_target_models.py`
- Modify: `services/api/analysis_target_resolution_service.py`
- Modify: `services/api/chat_start_service.py`
- Modify: `services/api/api_models.py`
- Modify: `frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`
- Create: `tests/test_analysis_target_contract.py`
- Modify: `tests/test_analysis_target_resolution_service.py`
- Modify: `tests/test_chat_start_service.py`

**Steps:**
1. Write failing tests that require report / submission / class-level targets to flow explicitly through a target contract, not only via text extraction.
2. Run `./.venv/bin/python -m pytest -q tests/test_analysis_target_contract.py tests/test_analysis_target_resolution_service.py tests/test_chat_start_service.py` and confirm the new tests fail.
3. Extend target models so the same structure can represent `report`, `submission`, and future target types.
4. Update chat start and request serialization to carry explicit analysis targets where available.
5. Keep text-based fallback extraction only as compatibility behavior, not the primary contract.
6. Update the teacher chat API layer so explicit target metadata can be passed without relying on synthetic text-only hints.
7. Re-run targeted tests and verify old routes remain compatible.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_analysis_target_contract.py tests/test_analysis_target_resolution_service.py tests/test_chat_start_service.py`
- Expected: PASS.

**Acceptance:**
- Analysis target selection is explicit, inspectable, and reusable across survey, class report, and multimodal domains.
- Future domains do not need fragile text parsing as the primary handoff method.

**Commit:**
```bash
git add services/api/analysis_target_models.py services/api/analysis_target_resolution_service.py services/api/chat_start_service.py services/api/api_models.py frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts tests/test_analysis_target_contract.py tests/test_analysis_target_resolution_service.py tests/test_chat_start_service.py
git commit -m "feat(analysis): make analysis targets explicit across chat and runtime"
```

### Task 3: Turn review queue into an operational control surface

**Files:**
- Modify: `services/api/review_queue_models.py`
- Modify: `services/api/review_queue_service.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `services/api/routes/analysis_report_routes.py`
- Modify: `frontend/apps/teacher/src/features/workbench/hooks/useAnalysisReports.ts`
- Create: `tests/test_review_queue_operations.py`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Steps:**
1. Write failing tests for reason taxonomy, unresolved backlog listing, retry / dismiss / escalation states, and per-domain review statistics.
2. Run `./.venv/bin/python -m pytest -q tests/test_review_queue_operations.py tests/test_review_queue_service.py tests/test_analysis_report_service.py` and verify failure.
3. Extend review queue models with stable reason codes, timestamps, operator notes, and current disposition.
4. Extend review queue service to return per-domain summaries and operator-facing state transitions.
5. Expose these summaries and state changes via analysis report service and routes.
6. Extend teacher workbench data fetching to surface richer review metadata.
7. Update rollout docs so review queue thresholds become explicit go / no-go gates.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_review_queue_operations.py tests/test_review_queue_service.py tests/test_analysis_report_routes.py`
- Expected: PASS.

**Acceptance:**
- Review queue is no longer just a passive sink.
- Release decisions can use review queue pressure and reason distribution as operational evidence.

**Commit:**
```bash
git add services/api/review_queue_models.py services/api/review_queue_service.py services/api/analysis_report_service.py services/api/routes/analysis_report_routes.py frontend/apps/teacher/src/features/workbench/hooks/useAnalysisReports.ts tests/test_review_queue_operations.py docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(review): add operational review queue controls"
```

### Task 4: Expand cross-domain offline evaluation to realistic edge cases

**Files:**
- Modify: `scripts/analysis_strategy_eval.py`
- Create: `tests/fixtures/analysis_reports/class_report/web_export_complex.json`
- Create: `tests/fixtures/analysis_reports/class_report/pdf_summary_low_confidence.json`
- Create: `tests/fixtures/multimodal/video_homework/long_duration_trimmed.json`
- Create: `tests/fixtures/multimodal/video_homework/ocr_noise_case.json`
- Create: `tests/fixtures/surveys/provider_attachment_noise.json`
- Modify: `tests/test_analysis_strategy_eval.py`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Steps:**
1. Write failing tests that require eval output to report edge-case coverage, failure reasons, and per-domain minimum fixture counts.
2. Run `./.venv/bin/python -m pytest -q tests/test_analysis_strategy_eval.py` and verify the new cases fail.
3. Add realistic fixtures covering noisy OCR, low-confidence parsing, longer multimodal submissions, and provider attachment noise.
4. Extend the eval script to summarize edge-case buckets, expectation failures by reason, and recommended rollout thresholds.
5. Update rollout docs to tie rollout gates to richer eval output instead of only “script passes”.
6. Re-run the eval tests and the eval script itself.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_analysis_strategy_eval.py`
- Run: `./.venv/bin/python scripts/analysis_strategy_eval.py --fixtures tests/fixtures --json --summary-only`
- Expected: PASS with `expectation_failures == 0`.

**Acceptance:**
- Offline evaluation better approximates real rollout risk.
- Edge-case coverage is visible before expanding domains or cohorts.

**Commit:**
```bash
git add scripts/analysis_strategy_eval.py tests/fixtures/analysis_reports/class_report/web_export_complex.json tests/fixtures/analysis_reports/class_report/pdf_summary_low_confidence.json tests/fixtures/multimodal/video_homework/long_duration_trimmed.json tests/fixtures/multimodal/video_homework/ocr_noise_case.json tests/fixtures/surveys/provider_attachment_noise.json tests/test_analysis_strategy_eval.py docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "test(eval): expand multi-domain analysis fixtures and thresholds"
```

### Task 5: Add domain-level and strategy-level kill switches

**Files:**
- Modify: `services/api/settings.py`
- Modify: `services/api/strategies/selector.py`
- Modify: `services/api/survey_orchestrator_service.py`
- Modify: `services/api/class_report_orchestrator_service.py`
- Modify: `services/api/multimodal_orchestrator_service.py`
- Create: `tests/test_analysis_rollout_flags.py`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Steps:**
1. Write failing tests for domain disablement, strategy disablement, and safe downgrade-to-review behavior.
2. Run `./.venv/bin/python -m pytest -q tests/test_analysis_rollout_flags.py tests/test_strategy_selector.py` and confirm failure.
3. Add settings helpers for domain-level and strategy-level rollout flags.
4. Update strategy selection and orchestrators so disabled domains fail safely and can optionally downgrade to review-only behavior.
5. Update rollout checklist with explicit per-domain and per-strategy rollback commands.
6. Re-run targeted tests and verify no existing enabled paths regress.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_analysis_rollout_flags.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py`
- Expected: PASS.

**Acceptance:**
- Rollback no longer requires disabling an entire broad capability when only one strategy is unstable.
- Release owners can contain failures with smaller blast radius.

**Commit:**
```bash
git add services/api/settings.py services/api/strategies/selector.py services/api/survey_orchestrator_service.py services/api/class_report_orchestrator_service.py services/api/multimodal_orchestrator_service.py tests/test_analysis_rollout_flags.py docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(rollout): add domain and strategy level kill switches"
```

---

## Phase P1: Capability and Operability Upgrades

### Task 6: Add controlled internal multi-specialist job graphs

**Files:**
- Create: `services/api/specialist_agents/job_graph_models.py`
- Create: `services/api/specialist_agents/job_graph_runtime.py`
- Create: `tests/test_specialist_job_graph_runtime.py`
- Modify: `services/api/specialist_agents/governor.py`
- Modify: `services/api/class_report_orchestrator_service.py`
- Modify: `services/api/multimodal_orchestrator_service.py`
- Modify: `docs/reference/analysis-runtime-contract.md`

**Steps:**
1. Write failing tests requiring a controlled graph such as `extract -> analyze -> verify -> merge` to run under the same governed runtime.
2. Run `./.venv/bin/python -m pytest -q tests/test_specialist_job_graph_runtime.py` and confirm failure.
3. Define job graph node / edge / budget contracts.
4. Implement a runtime that executes a small fixed graph under the existing governor rather than free-form agent-to-agent chatting.
5. Integrate one pilot flow for a higher-risk domain, preferably `video_homework`.
6. Document that this is controlled orchestration, not a free conversation mesh.
7. Re-run targeted tests and existing specialist runtime tests.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_specialist_job_graph_runtime.py tests/test_specialist_agent_runtime.py tests/test_specialist_agent_governor.py`
- Expected: PASS.

**Acceptance:**
- Internal collaboration depth increases without exposing open-ended multi-agent behavior to end users.
- Complex domains can compose specialist stages safely.

### Task 7: Stamp strategy, prompt, adapter, and runtime versions into reports

**Files:**
- Modify: `services/api/analysis_report_models.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `services/api/strategies/contracts.py`
- Modify: `services/api/artifacts/contracts.py`
- Modify: `services/api/specialist_agents/contracts.py`
- Create: `tests/test_analysis_version_stamps.py`

**Steps:**
1. Write failing tests requiring report metadata to include `strategy_version`, `prompt_version`, `adapter_version`, and `runtime_version`.
2. Run `./.venv/bin/python -m pytest -q tests/test_analysis_version_stamps.py tests/test_analysis_report_service.py` and confirm failure.
3. Extend contracts and report models to carry version stamps.
4. Thread version metadata through strategy selection, artifact adaptation, specialist execution, and report persistence.
5. Re-run targeted tests and verify old reads remain compatible.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_analysis_version_stamps.py tests/test_analysis_report_service.py`
- Expected: PASS.

**Acceptance:**
- Reports become traceable and replayable across prompt / strategy changes.
- Future regressions can be debugged against exact runtime versions.

### Task 8: Promote specialist events into operational metrics

**Files:**
- Create: `services/api/specialist_agents/metrics_service.py`
- Modify: `services/api/specialist_agents/events.py`
- Modify: `services/api/specialist_agents/governor.py`
- Modify: `services/api/observability.py`
- Create: `tests/test_specialist_metrics_service.py`
- Modify: `docs/operations/slo-and-observability.md`

**Steps:**
1. Write failing tests that require aggregation for success rate, timeout rate, invalid output rate, budget rejection rate, and fallback counts.
2. Run `./.venv/bin/python -m pytest -q tests/test_specialist_metrics_service.py` and confirm failure.
3. Implement metrics aggregation over specialist runtime events.
4. Wire the governor to publish structured metrics in addition to lifecycle events.
5. Document dashboards / alert thresholds in observability docs.
6. Re-run targeted tests.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_specialist_metrics_service.py tests/test_specialist_agent_governor.py`
- Expected: PASS.

**Acceptance:**
- Specialist quality regressions become visible before they turn into rollout incidents.

### Task 9: Add workbench operations mode for cross-domain analysis management

**Files:**
- Modify: `frontend/apps/teacher/src/features/workbench/hooks/useAnalysisReports.ts`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.tsx`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.test.tsx`
- Modify: `frontend/apps/teacher/src/types/workflow.ts`
- Modify: `services/api/routes/analysis_report_routes.py`
- Create: `tests/test_analysis_report_ops_routes.py`

**Steps:**
1. Write failing frontend and backend tests for bulk rerun, domain summary counters, and operator-focused review filters.
2. Run the targeted frontend and backend tests and confirm failure.
3. Add operator-focused summary endpoints or enrich existing analysis routes.
4. Add an ops section in the teacher workbench for domain filters, summary counters, and safe bulk actions.
5. Re-run targeted tests and teacher build.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_analysis_report_ops_routes.py`
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.test.tsx`
- Run: `cd frontend && npm run build:teacher`
- Expected: PASS.

**Acceptance:**
- The workbench becomes a practical cross-domain operations surface, not only a passive report viewer.

### Task 10: Standardize domain onboarding and extension templates

**Files:**
- Create: `docs/reference/analysis-domain-onboarding-contract.md`
- Create: `docs/plans/templates/analysis-domain-extension-template.md`
- Modify: `docs/reference/analysis-runtime-contract.md`
- Modify: `docs/INDEX.md`

**Steps:**
1. Draft a domain onboarding contract requiring artifact contract, strategy spec, specialist policy, fixtures, eval, rollout plan, and rollback path.
2. Create a reusable plan template for future domain additions.
3. Update runtime docs to make this the canonical onboarding path.
4. Index the new docs.
5. Run doc guardrail tests.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_docs_architecture_presence.py`
- Expected: PASS.

**Acceptance:**
- Future domain additions become more repeatable and less dependent on tribal knowledge.

---

## Phase P2: Longer-Term Platformization

### Task 11: Add reviewer / critic specialists for high-risk domains

**Files:**
- Create: `services/api/specialist_agents/reviewer_analyst.py`
- Create: `tests/test_reviewer_analyst.py`
- Modify: `services/api/strategies/selector.py`
- Modify: `services/api/specialist_agents/job_graph_runtime.py`
- Modify: `docs/reference/analysis-runtime-contract.md`

**Steps:**
1. Write failing tests for a reviewer step that checks a primary specialist output before final delivery.
2. Implement a reviewer specialist that produces critique metadata instead of final user-facing takeover.
3. Integrate the reviewer only for designated high-risk strategies.
4. Re-run targeted tests.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py`
- Expected: PASS.

**Acceptance:**
- Higher-risk domains gain a second layer of internal quality control without exposing agent debates to users.

### Task 12: Create a human-review feedback loop into eval and tuning inputs

**Files:**
- Create: `services/api/review_feedback_models.py`
- Create: `services/api/review_feedback_service.py`
- Create: `tests/test_review_feedback_service.py`
- Modify: `scripts/analysis_strategy_eval.py`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Steps:**
1. Write failing tests for recording structured human review outcomes and exporting them back into evaluation reports.
2. Implement review feedback storage and aggregation.
3. Extend the eval script to ingest aggregated review feedback signals.
4. Re-run targeted tests.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_review_feedback_service.py tests/test_analysis_strategy_eval.py`
- Expected: PASS.

**Acceptance:**
- Human review becomes a learning signal rather than only a manual escape hatch.

### Task 13: Build replay / simulation harness for analysis runs

**Files:**
- Create: `scripts/replay_analysis_run.py`
- Create: `tests/test_replay_analysis_run.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `docs/reference/analysis-runtime-contract.md`

**Steps:**
1. Write failing tests for replaying a stored report under a different strategy / prompt / adapter version.
2. Implement a replay harness that can reconstruct the artifact + strategy + runtime inputs from stored metadata.
3. Add documentation for replay-based debugging and release comparison.
4. Re-run targeted tests.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_replay_analysis_run.py`
- Expected: PASS.

**Acceptance:**
- Strategy regressions can be debugged with repeatable replay, not only live guesswork.

### Task 14: Introduce an internal analysis-domain package boundary

**Files:**
- Create: `services/api/domains/__init__.py`
- Create: `services/api/domains/contracts.py`
- Create: `services/api/domains/loaders.py`
- Create: `tests/test_domain_package_loader.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Modify: `services/api/artifacts/registry.py`
- Modify: `services/api/strategies/selector.py`

**Steps:**
1. Write failing tests for loading a domain package with artifact / strategy / specialist declarations.
2. Implement a minimal internal package boundary for analysis domains.
3. Migrate one existing domain to prove the boundary works.
4. Re-run targeted tests.

**Validation:**
- Run: `./.venv/bin/python -m pytest -q tests/test_domain_package_loader.py tests/test_domain_manifest_registry.py`
- Expected: PASS.

**Acceptance:**
- The system gains internal pluggability for future domains without becoming a public plugin marketplace.

---

## Recommended Execution Order

1. Task 1 — manifest-driven registration
2. Task 2 — explicit analysis target contract
3. Task 3 — review queue control surface
4. Task 4 — eval expansion
5. Task 5 — kill switches
6. Task 6 — controlled internal job graph
7. Task 7 — version stamping
8. Task 8 — runtime observability
9. Task 9 — workbench ops mode
10. Task 10 — onboarding template
11. Task 11 — reviewer specialist
12. Task 12 — feedback loop
13. Task 13 — replay harness
14. Task 14 — internal domain packages

## Milestones

- `M1` (P0-1 / P0-2): extensibility foundation and explicit target clarity
- `M2` (P0-3 / P0-4 / P0-5): operational safety and rollout hardening
- `M3` (P1-6 / P1-7 / P1-8): governed internal collaboration and traceability
- `M4` (P1-9 / P1-10): operator usability and repeatable extension path
- `M5` (P2): advanced quality control, replay, and internal package boundaries

## Final Verification

After all tasks are complete, run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_domain_manifest_registry.py \
  tests/test_analysis_target_contract.py \
  tests/test_review_queue_operations.py \
  tests/test_analysis_strategy_eval.py \
  tests/test_analysis_rollout_flags.py \
  tests/test_specialist_job_graph_runtime.py \
  tests/test_analysis_version_stamps.py \
  tests/test_specialist_metrics_service.py \
  tests/test_analysis_report_ops_routes.py \
  tests/test_reviewer_analyst.py \
  tests/test_review_feedback_service.py \
  tests/test_replay_analysis_run.py \
  tests/test_domain_package_loader.py
cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.test.tsx
cd frontend && npm run build:teacher
./.venv/bin/python scripts/analysis_strategy_eval.py --fixtures tests/fixtures --json --summary-only
./.venv/bin/python -m pytest -q tests/test_docs_architecture_presence.py tests/test_ci_backend_hardening_workflow.py
```

## Acceptance Criteria

- `Coordinator` remains the only default front-facing agent.
- New domains can be added with mostly manifest / contract work, not duplicated orchestration stacks.
- Analysis targets are explicit and auditable across chat and report flows.
- Review queue becomes an operational decision surface, not just a passive fallback bucket.
- Rollout controls can disable a broken domain or strategy without broad collateral rollback.
- Internal specialist collaboration becomes stronger without exposing open-ended multi-agent behavior.
- Reports become versioned, replayable, and more observable across strategy evolution.
