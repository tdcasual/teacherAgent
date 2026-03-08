# Agent Design Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Strengthen the current teacher-side agent control plane so new analysis domains are easier to add, specialist execution is more governable, reports are version-traceable, and review outcomes feed quality operations.

**Architecture:** Keep `Coordinator` as the only default front-facing agent and continue extending the unified analysis plane rather than introducing open-ended multi-agent behavior. Focus this wave on four layers: manifest-driven runtime assembly, stronger governed specialist execution, report lineage, and quality operations. Land each change behind targeted tests, small commits, and explicit rollout-safe behavior.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, pytest, JSON/JSONL metadata, Markdown docs, existing teacher frontend workbench.

---

## Scope and Execution Notes

- Execute this plan in a dedicated worktree.
- Use TDD for every code task: fail first, implement minimally, rerun targeted tests, then broaden verification.
- Do not turn specialists into user-facing agents.
- Do not introduce generic plugin loading or free-form agent-to-agent chat loops.
- Preserve backward compatibility for existing `survey`, `class_report`, and `video_homework` flows.

## Recommended Execution Order

1. Task 1 — manifest-driven runtime assembly
2. Task 2 — typed specialist output validation
3. Task 3 — report lineage and version stamps
4. Task 4 — specialist metrics and observability
5. Task 5 — review feedback loop into eval
6. Task 6 — controlled video-homework job graph
7. Task 7 — replay harness and extension template

---

### Task 1: Generalize domain runtime assembly

**Files:**
- Create: `services/api/domains/runtime_builder.py`
- Modify: `services/api/domains/manifest_models.py`
- Modify: `services/api/domains/manifest_registry.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Modify: `services/api/artifacts/registry.py`
- Test: `tests/test_domain_runtime_builder.py`
- Test: `tests/test_domain_manifest_registry.py`
- Test: `tests/test_artifact_registry.py`

**Step 1: Write the failing test**

Add a new test that proves a single builder can assemble domain runtime metadata for `survey`, `class_report`, and `video_homework` without domain-specific wiring duplication.

```python
def test_runtime_builder_creates_specialist_runtime_from_manifest() -> None:
    manifests = build_default_domain_manifest_registry()
    runtime = build_domain_specialist_runtime(domain_id='survey', manifests=manifests, core=_Core())
    result = runtime.run(_survey_handoff())
    assert result.agent_id == 'survey_analyst'
```

Add a second test that fails when a manifest omits required runtime binding fields.

```python
def test_manifest_requires_runtime_binding_metadata() -> None:
    with pytest.raises(ValueError):
        build_domain_specialist_runtime(domain_id='broken', manifests=_broken_registry(), core=_Core())
```

**Step 2: Run tests to verify they fail**

Run: `python3.13 -m pytest -q tests/test_domain_runtime_builder.py tests/test_domain_manifest_registry.py tests/test_artifact_registry.py`

Expected: FAIL because the generic runtime builder and required manifest binding fields do not exist yet.

**Step 3: Write minimal implementation**

Add manifest fields for runtime binding, for example:

```python
class DomainRuntimeBinding(BaseModel):
    specialist_deps_factory: str
    payload_constraint_key: str
    teacher_context_constraint_key: str = 'teacher_context'
```

Create a builder that resolves a manifest plus binding metadata into:

```python
def build_domain_specialist_runtime(*, domain_id: str, manifests: DomainManifestRegistry, core: Any) -> SpecialistAgentRuntime:
    ...
```

Refactor `survey_wiring.py` so each domain uses the common builder instead of hand-written registry setup.

**Step 4: Run tests to verify they pass**

Run: `python3.13 -m pytest -q tests/test_domain_runtime_builder.py tests/test_domain_manifest_registry.py tests/test_artifact_registry.py tests/test_specialist_agent_runtime.py`

Expected: PASS.

**Step 5: Update runtime docs**

Document the new assembly truth source and the required manifest binding fields in:

- `docs/reference/analysis-runtime-contract.md`
- `docs/architecture/module-boundaries.md`

**Step 6: Commit**

```bash
git add services/api/domains/runtime_builder.py services/api/domains/manifest_models.py services/api/domains/manifest_registry.py services/api/wiring/survey_wiring.py services/api/artifacts/registry.py tests/test_domain_runtime_builder.py tests/test_domain_manifest_registry.py tests/test_artifact_registry.py docs/reference/analysis-runtime-contract.md docs/architecture/module-boundaries.md
git commit -m "refactor(agents): generalize manifest-driven runtime assembly"
```

---

### Task 2: Enforce typed specialist output validation

**Files:**
- Create: `services/api/specialist_agents/output_schemas.py`
- Modify: `services/api/specialist_agents/contracts.py`
- Modify: `services/api/specialist_agents/governor.py`
- Modify: `services/api/specialist_agents/survey_analyst.py`
- Modify: `services/api/specialist_agents/class_signal_analyst.py`
- Modify: `services/api/specialist_agents/video_homework_analyst.py`
- Test: `tests/test_specialist_output_validation.py`
- Test: `tests/test_specialist_agent_governor.py`
- Test: `tests/test_specialist_agent_runtime.py`

**Step 1: Write the failing test**

Add tests requiring invalid specialist output to fail closed instead of passing as any non-empty dict.

```python
def test_governor_rejects_missing_required_output_fields() -> None:
    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        governor.run(handoff=_handoff(), spec=_spec(output_schema={'type': 'survey.analysis_artifact'}), runner=_bad_runner)
    assert exc_info.value.code == 'invalid_output'
```

Add a passing test for valid normalized output.

```python
def test_governor_accepts_valid_survey_analysis_artifact() -> None:
    result = governor.run(...)
    assert result.output['executive_summary'] == 'ok'
```

**Step 2: Run tests to verify they fail**

Run: `python3.13 -m pytest -q tests/test_specialist_output_validation.py tests/test_specialist_agent_governor.py tests/test_specialist_agent_runtime.py`

Expected: FAIL because output schemas are not enforced yet.

**Step 3: Write minimal implementation**

Create typed schema validators, for example:

```python
class SurveyAnalysisArtifact(BaseModel):
    executive_summary: str
    key_signals: list[dict]
    teaching_recommendations: list[str]
    confidence_and_gaps: dict
```

Update the governor to validate by `output_schema['type']` and raise `invalid_output` on mismatch.

```python
def _validate_output(self, spec: SpecialistAgentSpec, result: SpecialistAgentResult) -> None:
    schema = get_output_schema(spec.output_schema)
    schema.model_validate(result.output)
```

Keep specialist runners returning normalized outputs so they remain backward-compatible.

**Step 4: Run tests to verify they pass**

Run: `python3.13 -m pytest -q tests/test_specialist_output_validation.py tests/test_specialist_agent_governor.py tests/test_specialist_agent_runtime.py tests/test_class_report_orchestrator_service.py tests/test_multimodal_orchestrator_service.py`

Expected: PASS.

**Step 5: Update runtime docs**

Document invalid-output downgrade behavior and required per-domain output contract in:

- `docs/reference/analysis-runtime-contract.md`

**Step 6: Commit**

```bash
git add services/api/specialist_agents/output_schemas.py services/api/specialist_agents/contracts.py services/api/specialist_agents/governor.py services/api/specialist_agents/survey_analyst.py services/api/specialist_agents/class_signal_analyst.py services/api/specialist_agents/video_homework_analyst.py tests/test_specialist_output_validation.py tests/test_specialist_agent_governor.py tests/test_specialist_agent_runtime.py docs/reference/analysis-runtime-contract.md
git commit -m "feat(agents): enforce typed specialist output validation"
```

---

### Task 3: Stamp version lineage into analysis reports

**Files:**
- Modify: `services/api/analysis_report_models.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `services/api/strategies/contracts.py`
- Modify: `services/api/artifacts/contracts.py`
- Modify: `services/api/specialist_agents/contracts.py`
- Modify: `services/api/strategies/planner.py`
- Modify: `services/api/survey_report_service.py`
- Modify: `services/api/class_report_service.py`
- Modify: `services/api/multimodal_report_service.py`
- Test: `tests/test_analysis_version_stamps.py`
- Test: `tests/test_analysis_report_service.py`

**Step 1: Write the failing test**

Add a test requiring each report detail to include lineage fields.

```python
def test_analysis_report_includes_strategy_prompt_adapter_and_runtime_versions(tmp_path: Path) -> None:
    detail = get_analysis_report(report_id='report_1', teacher_id='teacher_1', domain='survey', deps=deps)
    assert detail['report']['strategy_version'] == 'v1'
    assert detail['report']['prompt_version'] == 'v1'
    assert detail['report']['adapter_version'] == 'v1'
    assert detail['report']['runtime_version'] == 'v1'
```

**Step 2: Run tests to verify they fail**

Run: `python3.13 -m pytest -q tests/test_analysis_version_stamps.py tests/test_analysis_report_service.py`

Expected: FAIL because lineage fields are not modeled or persisted yet.

**Step 3: Write minimal implementation**

Extend contracts and report models.

```python
class AnalysisReportSummary(BaseModel):
    ...
    strategy_version: str | None = None
    prompt_version: str | None = None
    adapter_version: str | None = None
    runtime_version: str | None = None
```

Add lineage stamping in planner / report write paths so all domains populate the same metadata keys.

**Step 4: Run tests to verify they pass**

Run: `python3.13 -m pytest -q tests/test_analysis_version_stamps.py tests/test_analysis_report_service.py tests/test_analysis_report_routes.py tests/test_class_report_orchestrator_service.py tests/test_multimodal_orchestrator_service.py`

Expected: PASS.

**Step 5: Update release docs**

Update:

- `docs/reference/analysis-runtime-contract.md`
- `docs/operations/multi-domain-analysis-rollout-checklist.md`

Add lineage expectations for rerun, audit, and rollout comparison.

**Step 6: Commit**

```bash
git add services/api/analysis_report_models.py services/api/analysis_report_service.py services/api/strategies/contracts.py services/api/artifacts/contracts.py services/api/specialist_agents/contracts.py services/api/strategies/planner.py services/api/survey_report_service.py services/api/class_report_service.py services/api/multimodal_report_service.py tests/test_analysis_version_stamps.py tests/test_analysis_report_service.py tests/test_analysis_report_routes.py docs/reference/analysis-runtime-contract.md docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(reports): stamp lineage metadata into analysis reports"
```

---

### Task 4: Promote specialist events into operational metrics

**Files:**
- Create: `services/api/analysis_metrics_service.py`
- Modify: `services/api/specialist_agents/events.py`
- Modify: `services/api/specialist_agents/governor.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Modify: `services/api/settings.py`
- Test: `tests/test_analysis_metrics_service.py`
- Test: `tests/test_specialist_agent_governor.py`
- Doc: `docs/operations/slo-and-observability.md`

**Step 1: Write the failing test**

Add a test that proves specialist lifecycle events are aggregated by `domain`, `strategy_id`, `agent_id`, and `phase`.

```python
def test_metrics_service_counts_completed_failed_and_timeout_events() -> None:
    service = AnalysisMetricsService()
    service.record(_event(phase='completed', domain='survey', strategy_id='survey.teacher.report'))
    assert service.snapshot()['by_phase']['completed'] == 1
```

Add a second test for downgrade visibility.

```python
def test_metrics_service_counts_review_downgrades() -> None:
    ...
    assert snapshot['by_reason']['review_required'] == 1
```

**Step 2: Run tests to verify they fail**

Run: `python3.13 -m pytest -q tests/test_analysis_metrics_service.py tests/test_specialist_agent_governor.py`

Expected: FAIL because there is no metrics aggregator or enriched event model yet.

**Step 3: Write minimal implementation**

Extend runtime events with optional domain and strategy fields, and create a simple aggregator.

```python
class SpecialistRuntimeEvent(BaseModel):
    phase: str
    handoff_id: str
    agent_id: str
    task_kind: str
    domain: str | None = None
    strategy_id: str | None = None
```

Wire the governor event sink to emit to both diagnostics and metrics.

**Step 4: Run tests to verify they pass**

Run: `python3.13 -m pytest -q tests/test_analysis_metrics_service.py tests/test_specialist_agent_governor.py tests/test_analysis_rollout_flags.py`

Expected: PASS.

**Step 5: Update ops docs**

Document the new metrics in:

- `docs/operations/slo-and-observability.md`
- `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Step 6: Commit**

```bash
git add services/api/analysis_metrics_service.py services/api/specialist_agents/events.py services/api/specialist_agents/governor.py services/api/wiring/survey_wiring.py services/api/settings.py tests/test_analysis_metrics_service.py tests/test_specialist_agent_governor.py docs/operations/slo-and-observability.md docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(observability): add specialist runtime metrics aggregation"
```

---

### Task 5: Feed review queue outcomes into offline evaluation

**Files:**
- Create: `services/api/review_feedback_service.py`
- Modify: `services/api/review_queue_service.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `scripts/analysis_strategy_eval.py`
- Test: `tests/test_review_feedback_service.py`
- Test: `tests/test_review_queue_operations.py`
- Test: `tests/test_analysis_strategy_eval.py`
- Doc: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Step 1: Write the failing test**

Add a test that proves review operations are exported as normalized quality signals.

```python
def test_review_feedback_service_aggregates_rejections_and_retries(tmp_path: Path) -> None:
    summary = build_review_feedback_summary(...)
    assert summary['by_action']['reject'] == 1
    assert summary['by_action']['retry'] == 1
```

Add a second test that proves the eval script can ingest the summary.

```python
def test_analysis_strategy_eval_reads_review_feedback(tmp_path: Path) -> None:
    result = run_eval(..., review_feedback_path=feedback_path)
    assert result['review_feedback']['total_items'] == 2
```

**Step 2: Run tests to verify they fail**

Run: `python3.13 -m pytest -q tests/test_review_feedback_service.py tests/test_review_queue_operations.py tests/test_analysis_strategy_eval.py`

Expected: FAIL because there is no review feedback aggregation path yet.

**Step 3: Write minimal implementation**

Create a feedback summarizer that reads review queue operations and produces a machine-readable summary.

```python
def build_review_feedback_summary(*, items: list[dict]) -> dict:
    return {
        'total_items': len(items),
        'by_action': {...},
        'by_domain': {...},
        'by_reason_code': {...},
    }
```

Pass this summary into the eval output JSON under a stable key.

**Step 4: Run tests to verify they pass**

Run: `python3.13 -m pytest -q tests/test_review_feedback_service.py tests/test_review_queue_operations.py tests/test_analysis_strategy_eval.py tests/test_analysis_report_service.py`

Expected: PASS.

**Step 5: Update rollout docs**

Document how release owners should use review feedback drift in:

- `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Step 6: Commit**

```bash
git add services/api/review_feedback_service.py services/api/review_queue_service.py services/api/analysis_report_service.py scripts/analysis_strategy_eval.py tests/test_review_feedback_service.py tests/test_review_queue_operations.py tests/test_analysis_strategy_eval.py docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(quality): feed review outcomes into analysis eval"
```

---

### Task 6: Add a controlled job graph pilot for video homework

**Files:**
- Create: `services/api/specialist_agents/job_graph_models.py`
- Create: `services/api/specialist_agents/job_graph_runtime.py`
- Modify: `services/api/specialist_agents/governor.py`
- Modify: `services/api/multimodal_orchestrator_service.py`
- Test: `tests/test_specialist_job_graph_runtime.py`
- Test: `tests/test_multimodal_orchestrator_service.py`
- Doc: `docs/reference/analysis-runtime-contract.md`

**Step 1: Write the failing test**

Add a test requiring a fixed graph to execute under the governed runtime.

```python
def test_job_graph_runtime_executes_extract_analyze_verify_in_order() -> None:
    result = runtime.run(_graph())
    assert result.status == 'completed'
    assert result.trace == ['extract', 'analyze', 'verify']
```

Add a second test for fail-closed behavior.

```python
def test_job_graph_runtime_stops_on_invalid_verify_step() -> None:
    with pytest.raises(SpecialistAgentRuntimeError):
        runtime.run(_failing_graph())
```

**Step 2: Run tests to verify they fail**

Run: `python3.13 -m pytest -q tests/test_specialist_job_graph_runtime.py tests/test_multimodal_orchestrator_service.py`

Expected: FAIL because the fixed graph runtime does not exist yet.

**Step 3: Write minimal implementation**

Define a bounded graph contract.

```python
class SpecialistJobGraph(BaseModel):
    nodes: list[JobNode]
    edges: list[JobEdge]
    max_nodes: int = 6
```

Implement sequential fixed-graph execution under the same governor and integrate it only for the `video_homework` pilot path.

**Step 4: Run tests to verify they pass**

Run: `python3.13 -m pytest -q tests/test_specialist_job_graph_runtime.py tests/test_multimodal_orchestrator_service.py tests/test_specialist_agent_governor.py tests/test_specialist_agent_runtime.py`

Expected: PASS.

**Step 5: Update runtime docs**

Clarify that this is controlled orchestration, not free-form multi-agent chat, in:

- `docs/reference/analysis-runtime-contract.md`

**Step 6: Commit**

```bash
git add services/api/specialist_agents/job_graph_models.py services/api/specialist_agents/job_graph_runtime.py services/api/specialist_agents/governor.py services/api/multimodal_orchestrator_service.py tests/test_specialist_job_graph_runtime.py tests/test_multimodal_orchestrator_service.py docs/reference/analysis-runtime-contract.md
git commit -m "feat(agents): add controlled job graph pilot for video homework"
```

---

### Task 7: Add replay support and a domain extension template

**Files:**
- Create: `scripts/replay_analysis_run.py`
- Create: `tests/test_replay_analysis_run.py`
- Create: `docs/reference/analysis-domain-extension-template.md`
- Modify: `docs/reference/analysis-runtime-contract.md`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`
- Modify: `docs/INDEX.md`

**Step 1: Write the failing test**

Add a replay test that reconstructs one stored report from its lineage metadata.

```python
def test_replay_analysis_run_rebuilds_report_inputs(tmp_path: Path) -> None:
    result = replay_analysis_run(report_path=report_path)
    assert result['lineage']['strategy_version'] == 'v1'
```

**Step 2: Run tests to verify they fail**

Run: `python3.13 -m pytest -q tests/test_replay_analysis_run.py`

Expected: FAIL because the replay script does not exist yet.

**Step 3: Write minimal implementation**

Create a replay script that reads stored lineage and artifact metadata and outputs a comparison-ready payload.

```python
def replay_analysis_run(*, report_path: Path) -> dict:
    report = json.loads(report_path.read_text())
    return {'lineage': report['report'], 'artifact_meta': report.get('artifact_meta', {})}
```

Create a domain extension template documenting the minimum required pieces for adding a fourth domain.

**Step 4: Run tests to verify they pass**

Run: `python3.13 -m pytest -q tests/test_replay_analysis_run.py tests/test_domain_manifest_registry.py tests/test_analysis_report_service.py`

Expected: PASS.

**Step 5: Update docs index**

Link the new replay and domain extension docs from:

- `docs/INDEX.md`

**Step 6: Commit**

```bash
git add scripts/replay_analysis_run.py tests/test_replay_analysis_run.py docs/reference/analysis-domain-extension-template.md docs/reference/analysis-runtime-contract.md docs/operations/multi-domain-analysis-rollout-checklist.md docs/INDEX.md
git commit -m "docs(analysis): add replay support and domain extension template"
```

---

## Milestones

- `M1`: Generic manifest-driven runtime assembly lands without breaking current domains.
- `M2`: Specialist output validation becomes typed and fail-closed.
- `M3`: All analysis reports become lineage-aware and replay-friendly.
- `M4`: Runtime events and review actions become operational quality inputs.
- `M5`: `video_homework` proves controlled internal graph execution safely.
- `M6`: Replay and onboarding docs reduce future domain extension cost.

## Final Verification

Run targeted verification after all tasks:

```bash
python3.13 -m pytest -q \
  tests/test_domain_runtime_builder.py \
  tests/test_domain_manifest_registry.py \
  tests/test_artifact_registry.py \
  tests/test_specialist_output_validation.py \
  tests/test_specialist_agent_governor.py \
  tests/test_specialist_agent_runtime.py \
  tests/test_analysis_version_stamps.py \
  tests/test_analysis_report_service.py \
  tests/test_analysis_metrics_service.py \
  tests/test_review_feedback_service.py \
  tests/test_review_queue_operations.py \
  tests/test_analysis_strategy_eval.py \
  tests/test_specialist_job_graph_runtime.py \
  tests/test_multimodal_orchestrator_service.py \
  tests/test_replay_analysis_run.py
```

Expected: PASS.

Then run a broader confidence sweep:

```bash
python3.13 -m pytest -q tests/test_analysis_report_routes.py tests/test_analysis_rollout_flags.py tests/test_class_report_orchestrator_service.py tests/test_chat_start_service.py
```

Expected: PASS.

## Acceptance Criteria

- Adding a new analysis domain no longer requires copying full registry/runtime glue.
- Specialist outputs are validated against typed domain contracts.
- Analysis reports carry enough lineage metadata for audit and replay.
- Runtime events and review outcomes are visible as quality signals, not only logs.
- `video_homework` demonstrates safe controlled internal orchestration without introducing open-ended multi-agent behavior.
- The repository contains a clear replay path and a reusable domain extension template.
