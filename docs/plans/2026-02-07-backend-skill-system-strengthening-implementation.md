# Backend Skill System Strengthening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a robust backend skill routing system with better auto-hit accuracy, stronger observability, and safe rollback behavior for teacher chat flows.

**Architecture:** Add a dedicated `skill_auto_router` layer that resolves requested vs effective skill before agent execution. Expand `skill.yaml` with structured `routing` metadata and threshold controls. Persist routing decisions to diagnostics and job/session records, then add a report script and regression tests as quality gates.

**Tech Stack:** Python 3, FastAPI service modules, YAML skill specs, unittest, shell scripts.

---

### Task 1: Add Routing Config Schema (`routing`) to Skill Spec

**Files:**
- Modify: `services/api/skills/spec.py`
- Create: `tests/test_skill_routing_config.py`
- Test: `tests/test_skill_routing_config.py`

**Step 1: Write the failing test**

```python
def test_parse_routing_fields_from_skill_yaml(self):
    loaded = load_skills(APP_ROOT / "skills")
    spec = loaded.skills["physics-homework-generator"]
    routing = spec.routing
    self.assertIn("生成作业", routing.keywords)
    self.assertIn("assignment_generate", routing.intents)
```

Also add a threshold parse test:

```python
self.assertGreaterEqual(routing.min_score, 1)
self.assertGreaterEqual(routing.min_margin, 0)
```

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_skill_routing_config -v
```

Expected: FAIL with `AttributeError` or parse mismatch because `SkillSpec` has no `routing`.

**Step 3: Write minimal implementation**

In `services/api/skills/spec.py`:
- Add `SkillRoutingSpec` dataclass with:
  - `keywords: List[str]`
  - `negative_keywords: List[str]`
  - `intents: List[str]`
  - `keyword_weights: Dict[str, int]`
  - `min_score: int`
  - `min_margin: int`
  - `confidence_floor: float`
  - `match_mode: str`
- Add `_parse_routing(...)` with safe defaults.
- Add `routing: SkillRoutingSpec` to `SkillSpec`.
- Expose `routing` in `as_public_dict`.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_skill_routing_config -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/skills/spec.py tests/test_skill_routing_config.py
git commit -m "feat(skills): add routing config schema and parser"
```

### Task 2: Build `skill_auto_router` with Threshold and Ambiguity Logic

**Files:**
- Create: `services/api/skill_auto_router.py`
- Create: `tests/test_skill_auto_router.py`
- Test: `tests/test_skill_auto_router.py`

**Step 1: Write the failing test**

Add tests covering:
- explicit requested skill preserved
- unknown/invalid requested skill auto-resolved
- teacher assignment request -> `physics-homework-generator`
- teacher routing request -> `physics-llm-routing`
- ambiguous low-margin request -> `reason` contains `ambiguous`
- student/teacher role gate fallback

Example:

```python
self.assertEqual(result["effective_skill_id"], "physics-homework-generator")
self.assertIn("auto_rule", result["reason"])
self.assertGreaterEqual(float(result["confidence"]), 0.0)
```

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_skill_auto_router -v
```

Expected: FAIL because module/function does not exist.

**Step 3: Write minimal implementation**

Implement `resolve_effective_skill(...)` in `services/api/skill_auto_router.py`:
- load skills and role-allowed candidates
- validate requested skill id format
- score by config keywords/intents + small hardcoded role rules
- apply `min_score` and `min_margin`
- compute confidence with gap-aware formula
- return structured payload:
  - `requested_skill_id`
  - `effective_skill_id`
  - `reason`
  - `confidence`
  - `matched_rule`
  - `candidates`
  - `best_score`
  - `second_score`
  - `threshold_blocked`
  - `load_errors`

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_skill_auto_router -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/skill_auto_router.py tests/test_skill_auto_router.py
git commit -m "feat(chat): add auto skill router with threshold controls"
```

### Task 3: Integrate Auto Router Into Chat Pipeline and Persistence

**Files:**
- Modify: `services/api/chat_job_processing_service.py`
- Modify: `services/api/app.py`
- Modify: `tests/test_chat_job_flow.py`
- Modify: `tests/test_chat_route_flow.py`
- Test: `tests/test_chat_job_flow.py`

**Step 1: Write the failing test**

In `tests/test_chat_job_flow.py`, add assertions after `/chat/status`:

```python
self.assertIn("skill_id_requested", payload)
self.assertIn("skill_id_effective", payload)
self.assertEqual(payload["skill_id_requested"], "")
self.assertEqual(payload["skill_id_effective"], "physics-homework-generator")
```

Also assert teacher session message meta includes both requested/effective IDs.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_chat_job_flow -v
```

Expected: FAIL because fields are missing.

**Step 3: Write minimal implementation**

In `services/api/chat_job_processing_service.py`:
- Extend `ComputeChatReplyDeps` with `resolve_effective_skill`.
- Resolve skill before preflight and agent call.
- Emit `diag_log("skill.resolve", ...)` and `diag_log("skill.resolve.failed", ...)`.
- Persist requested/effective skill IDs in:
  - job `done` payload
  - teacher session message `meta`
  - teacher inbound diagnostics

In `services/api/app.py`:
- Inject router dependency from `_compute_chat_reply_deps`.
- Wire `resolve_effective_skill` to `skill_auto_router.resolve_effective_skill`.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_chat_job_flow tests.test_chat_route_flow tests.test_chat_start_flow -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/chat_job_processing_service.py services/api/app.py tests/test_chat_job_flow.py tests/test_chat_route_flow.py
git commit -m "feat(chat): persist and log requested/effective skill routing decisions"
```

### Task 4: Add Routing Metadata to Skill YAMLs

**Files:**
- Modify: `skills/physics-homework-generator/skill.yaml`
- Modify: `skills/physics-llm-routing/skill.yaml`
- Modify: `skills/physics-lesson-capture/skill.yaml`
- Modify: `skills/physics-core-examples/skill.yaml`
- Modify: `skills/physics-student-focus/skill.yaml`
- Modify: `skills/physics-teacher-ops/skill.yaml`
- Modify: `skills/physics-student-coach/skill.yaml`
- Test: `scripts/validate_skills.py`

**Step 1: Write the failing test**

In `tests/test_skill_routing_config.py`, assert each skill has non-empty `routing` with intent + keywords.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_skill_routing_config -v
```

Expected: FAIL because `routing` sections are missing in YAML.

**Step 3: Write minimal implementation**

Add `routing:` blocks to each `skill.yaml`:
- domain keywords
- optional `negative_keywords`
- intents
- keyword weights
- threshold fields (`min_score`, `min_margin`, `confidence_floor`, `match_mode`)

Constraint:
- set short-token keywords (for example `ce`) to `word_boundary` behavior via config or omit short token.

**Step 4: Run validation**

Run:

```bash
python3 -m unittest tests.test_skill_routing_config -v
python3 scripts/validate_skills.py
```

Expected: both PASS.

**Step 5: Commit**

```bash
git add skills/*/skill.yaml tests/test_skill_routing_config.py services/api/skills/spec.py
git commit -m "feat(skills): add routing metadata and thresholds for all backend skills"
```

### Task 5: Add Routing Report Script and Tests

**Files:**
- Create: `scripts/skill_route_report.py`
- Create: `tests/test_skill_route_report_script.py`
- Test: `tests/test_skill_route_report_script.py`

**Step 1: Write the failing test**

Create `tests/test_skill_route_report_script.py`:
- build temp diagnostics log with `skill.resolve` events
- run script with `--format json`
- assert:
  - `total`
  - reason buckets
  - role buckets
  - effective skill counts
  - transitions include empty-request auto transitions
  - `auto_hit_rate/default_rate/ambiguous_rate`

**Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_skill_route_report_script -v
```

Expected: FAIL because script missing.

**Step 3: Write minimal implementation**

In `scripts/skill_route_report.py`:
- parse jsonl diagnostics
- filter `event == "skill.resolve"`
- aggregate:
  - totals
  - explicit/auto/default/ambiguous counts
  - reasons, roles, effective skills
  - requested->effective transitions (including empty requested as `(empty)`)
  - derived rates
- support `--format text|json`.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_skill_route_report_script -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/skill_route_report.py tests/test_skill_route_report_script.py
git commit -m "feat(observability): add skill routing diagnostics report script"
```

### Task 6: Full Verification Gate for This Feature

**Files:**
- Modify: `tests/test_skills_endpoint.py`
- Modify: `tests/test_skills_first_class.py`
- Modify: `tests/test_skills_policy_consistency.py`
- Modify: `tests/test_skill_prompt_module_security.py`
- Test: existing test suite listed below

**Step 1: Add/adjust assertions**

Ensure tests assert `routing` appears in skill public payload and parser defaults remain backward compatible.

**Step 2: Run targeted regression**

Run:

```bash
python3 -m unittest \
  tests.test_skill_auto_router \
  tests.test_skill_routing_config \
  tests.test_skill_route_report_script \
  tests.test_chat_job_flow \
  tests.test_chat_route_flow \
  tests.test_chat_start_flow \
  tests.test_chat_runtime_service \
  tests.test_skills_first_class \
  tests.test_skills_endpoint \
  tests.test_skills_policy_consistency \
  tests.test_skill_prompt_module_security -v
```

Expected: PASS.

**Step 3: Run skill config validation**

Run:

```bash
python3 scripts/validate_skills.py
```

Expected: `[OK] Validated <N> skills.`

**Step 4: Generate static routing report sample**

Run:

```bash
python3 scripts/skill_route_report.py --log tmp/diagnostics.log --format text
```

Expected: readable summary without traceback.

**Step 5: Commit**

```bash
git add tests services/api scripts skills
git commit -m "test(skill-routing): add regression gates for backend skill system"
```

---

## Rollout Checklist (Post-Implementation)

- Run in shadow mode first (log only, no behavior override).
- Compare 7-day baseline vs new routing:
  - Top1 >= 85%
  - Default <= 20%
  - Ambiguous <= 10%
- If any metric regresses, disable new threshold policy and fall back to role default strategy.

## Skills to Use During Execution

- `@test-driven-development` for each coding task
- `@systematic-debugging` for any failing test or mismatch
- `@verification-before-completion` before claiming success
- `@requesting-code-review` before merge/PR
