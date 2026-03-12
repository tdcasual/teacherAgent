# Workflow Routing Manifest Truth Tightening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不重写 skill router 的前提下，把当前最稳定的 workflow routing 真相进一步迁回 skill manifests，并用回归夹具锁定 teacher 路由边界。

**Architecture:** 保留现有 `resolve_effective_skill()` 主流程与 `auto_route_rules.py` 作为兜底启发式，只新增一个最小 routing 扩展字段 `regex_keywords`，把目前散落在 Python 中的稳定正则命中迁回 skill YAML。先补 fixture regression，再做 spec/parser/scoring 的最小实现，最后收缩 legacy hardcode，避免一次性设计新的 routing DSL。

**Tech Stack:** Python 3.13、pytest、JSON fixtures、现有 skill YAML、现有 `scripts/eval_teacher_workflow_routing.py`。

---

> **Scope note:** `tool_dispatch` 的 `skill-aware ACL` 与 `tests/test_tool_dispatch_skill_policy.py` 已存在，因此下一阶段不重复做 ACL，而是直接进入路线图里更靠前的“routing truth closer to manifests”这条线。

### Task 1: 扩充 routing 回归夹具并锁定边界案例

**Files:**
- Modify: `tests/fixtures/teacher_workflow_routing_cases.json`
- Modify: `tests/test_teacher_workflow_routing_regression.py`
- Modify: `tests/test_skill_auto_router.py`
- Modify: `scripts/eval_teacher_workflow_routing.py`

**Step 1: Write the failing test**

在 `tests/fixtures/teacher_workflow_routing_cases.json` 追加 4 个 case，覆盖本轮要保护的边界：

```json
{
  "name": "negated_homework_falls_back_to_teacher_ops",
  "role_hint": "teacher",
  "requested_skill_id": "",
  "last_user_text": "不要生成作业，先做考试分析和讲评提纲。",
  "expected_skill_id": "physics-teacher-ops",
  "expected_reason": "auto_rule",
  "min_confidence": 0.28,
  "first_candidate_skill_id": "physics-teacher-ops"
}
```

```json
{
  "name": "ce_id_routes_to_core_examples",
  "role_hint": "teacher",
  "requested_skill_id": "",
  "last_user_text": "登记核心例题 CE042，并补两道变式题。",
  "expected_skill_id": "physics-core-examples",
  "expected_reason": "auto_rule",
  "min_confidence": 0.28,
  "first_candidate_skill_id": "physics-core-examples"
}
```

```json
{
  "name": "single_student_profile_routes_to_student_focus",
  "role_hint": "teacher",
  "requested_skill_id": "",
  "last_user_text": "帮我看某个学生的画像和最近作业表现。",
  "expected_skill_id": "physics-student-focus",
  "expected_reason": "auto_rule",
  "min_confidence": 0.28,
  "first_candidate_skill_id": "physics-student-focus"
}
```

```json
{
  "name": "generic_analysis_keeps_default_fallback",
  "role_hint": "teacher",
  "requested_skill_id": "",
  "last_user_text": "我想做一个分析。",
  "expected_skill_id": "physics-teacher-ops",
  "expected_reason": "role_default_low_margin",
  "min_confidence": 0.28,
  "first_candidate_skill_id": "physics-homework-generator"
}
```

并在 `tests/test_skill_auto_router.py` 新增两个直接单测，固定：
- `CE042` 命中 `physics-core-examples`
- “某个学生 + 画像/表现” 命中 `physics-student-focus`

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_teacher_workflow_routing_regression.py tests/test_skill_auto_router.py
./.venv/bin/python scripts/eval_teacher_workflow_routing.py
```

Expected:
- regression 或 direct router tests FAIL；
- `eval_teacher_workflow_routing.py` 输出 `mismatches>0`。

**Step 3: Write minimal implementation**

先只更新测试辅助脚本，让它在失败时输出 case 名称和 top candidate，方便后续调路由：

```python
if actual_skill != expected_skill or actual_reason != expected_reason:
    first_candidate = ((result.get('candidates') or [{}])[0]).get('skill_id')
    mismatches.append(
        f"- {case.get('name')}: expected {expected_skill}/{expected_reason}, got {actual_skill}/{actual_reason}, first_candidate={first_candidate}"
    )
```

`tests/test_teacher_workflow_routing_regression.py` 同时把 case 数量断言从固定区间改成“至少当前数量”，避免每次补 fixture 都要反改测试：

```python
self.assertGreaterEqual(len(cases), 24)
```

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_teacher_workflow_routing_regression.py tests/test_skill_auto_router.py
./.venv/bin/python scripts/eval_teacher_workflow_routing.py
```

Expected:
- 这一步通常仍然 FAIL；如果恰好因现有 hardcode 已覆盖而 PASS，也继续进入 Task 2，不要删测试。

**Step 5: Commit**

```bash
git add tests/fixtures/teacher_workflow_routing_cases.json tests/test_teacher_workflow_routing_regression.py tests/test_skill_auto_router.py scripts/eval_teacher_workflow_routing.py
git commit -m "test(router): lock workflow routing boundary cases"
```

---

### Task 2: 为 skill routing 增加最小 `regex_keywords` 支持

**Files:**
- Modify: `services/api/skills/spec.py`
- Modify: `services/api/skill_auto_router.py`
- Modify: `tests/test_skill_auto_router.py`

**Step 1: Write the failing test**

在 `tests/test_skill_auto_router.py` 增加一个 parser + scoring 回归测试，要求 manifest 中的 regex 命中能驱动路由：

```python
def test_teacher_auto_routes_ce_identifier_via_manifest_regex():
    result = resolve_effective_skill(
        app_root=APP_ROOT,
        role_hint="teacher",
        requested_skill_id="",
        last_user_text="登记核心例题 CE042",
        detect_assignment_intent=detect_assignment_intent,
    )
    self.assertEqual(result.get("effective_skill_id"), "physics-core-examples")
    self.assertEqual(result.get("reason"), "auto_rule")
```

这一步依赖 Task 3 的 YAML 变更，当前应该先红。

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_skill_auto_router.py::SkillAutoRouterTest::test_teacher_auto_routes_ce_identifier_via_manifest_regex
```

Expected:
- FAIL，因为 `SkillRoutingSpec` 还不认识 `regex_keywords`。

**Step 3: Write minimal implementation**

在 `services/api/skills/spec.py` 给 `SkillRoutingSpec` 增加一个新字段：

```python
@dataclass(frozen=True)
class SkillRoutingSpec:
    keywords: List[str]
    negative_keywords: List[str]
    intents: List[str]
    keyword_weights: Dict[str, int]
    regex_keywords: Dict[str, int]
    min_score: int
    min_margin: int
    confidence_floor: float
    match_mode: str
```

在 parser 中支持从 YAML 读取：

```python
regex_keywords_raw = _as_dict(routing_raw.get("regex_keywords"))
regex_keywords: Dict[str, int] = {}
for pattern, value in regex_keywords_raw.items():
    normalized = str(pattern or "").strip()
    weight = _as_int(value, 0)
    if not normalized or weight <= 0:
        continue
    regex_keywords[normalized] = min(50, max(1, weight))
```

在 `services/api/skill_auto_router.py` 新增最小 helper：

```python
def _score_regex_matches(text: str, patterns: Dict[str, int]) -> tuple[int, list[str]]:
    score = 0
    hits: list[str] = []
    for pattern, weight in patterns.items():
        try:
            if re.search(pattern, text, flags=re.I):
                score += max(1, int(weight))
                hits.append(f"cfg-regex:{pattern}")
        except re.error:
            continue
    return score, hits
```

并把它并入 `_score_from_skill_config()`：

```python
regex_score, regex_hits = _score_regex_matches(text, regex_keywords)
score = pos_score + neg_score + intent_score + regex_score
hits = pos_hits + neg_hits + intent_hits + regex_hits
```

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_skill_auto_router.py::SkillAutoRouterTest::test_teacher_auto_routes_ce_identifier_via_manifest_regex tests/test_teacher_workflow_routing_regression.py
```

Expected:
- direct test PASS；
- regression 可能还有剩余 FAIL，进入 Task 3 继续收口。

**Step 5: Commit**

```bash
git add services/api/skills/spec.py services/api/skill_auto_router.py tests/test_skill_auto_router.py
git commit -m "feat(router): support manifest regex keywords"
```

---

### Task 3: 把稳定 regex 命中从 Python hardcode 迁回 skill manifests

**Files:**
- Modify: `skills/physics-core-examples/skill.yaml`
- Modify: `skills/physics-student-focus/skill.yaml`
- Modify: `skills/physics-homework-generator/skill.yaml`
- Modify: `services/api/skills/auto_route_rules.py`
- Modify: `tests/fixtures/teacher_workflow_routing_cases.json`
- Modify: `tests/test_teacher_workflow_routing_regression.py`
- Modify: `scripts/eval_teacher_workflow_routing.py`

**Step 1: Write the failing test**

在 YAML 中准备把下面这些稳定命中迁回配置：

`skills/physics-core-examples/skill.yaml`

```yaml
routing:
  regex_keywords:
    "\\bCE\\d+\\b": 5
```

`skills/physics-student-focus/skill.yaml`

```yaml
routing:
  regex_keywords:
    "(某个学生|单个学生|该学生|同学.*(画像|诊断|表现))": 4
```

`skills/physics-homework-generator/skill.yaml`

```yaml
routing:
  regex_keywords:
    "作业\\s*id": 6
```

然后删除 `auto_route_rules.py` 里这三类对应 hardcode 之前先跑红测，确保 fixture 真依赖 manifest：

```python
if _CE_ID_RE.search(text):
    score += 5
```

```python
if _SINGLE_STUDENT_RE.search(text):
    score += 4
```

```python
("作业 id", 4)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_teacher_workflow_routing_regression.py tests/test_skill_auto_router.py
./.venv/bin/python scripts/eval_teacher_workflow_routing.py
```

Expected:
- FAIL，如果 YAML 还没补齐或 hardcode 删除过早。

**Step 3: Write minimal implementation**

- 在三个 skill YAML 中补 `regex_keywords`。
- 在 `services/api/skills/auto_route_rules.py` 只删除已经被 manifest 接管的稳定命中，保留组合型兜底逻辑，例如：
  - `lesson_capture_combo`
  - `student_focus_combo`
  - `assignment_intent` / `assignment_generation`
- 不动 `_TIE_BREAK_ORDER`，这一轮不引入 `priority_hint`，避免 DSL 膨胀。
- 让 `scripts/eval_teacher_workflow_routing.py` 输出一个简短统计，方便看这轮是否减少了 fallback 与 mismatch：

```python
print(
    f"cases={len(cases)} mismatches={len(mismatches)} fallbacks={fallback_total} low_confidence={low_confidence_total}"
)
```

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_teacher_workflow_routing_regression.py tests/test_skill_auto_router.py
./.venv/bin/python scripts/eval_teacher_workflow_routing.py
```

Expected:
- PASS；
- eval 输出 `mismatches=0`。

**Step 5: Commit**

```bash
git add skills/physics-core-examples/skill.yaml skills/physics-student-focus/skill.yaml skills/physics-homework-generator/skill.yaml services/api/skills/auto_route_rules.py tests/fixtures/teacher_workflow_routing_cases.json tests/test_teacher_workflow_routing_regression.py scripts/eval_teacher_workflow_routing.py
git commit -m "refactor(router): move stable regex routing truth into skill manifests"
```

---

### Task 4: Final regression and docs touch-up

**Files:**
- Modify: `docs/reference/agent-runtime-contract.md`
- Modify: `docs/architecture/module-boundaries.md`
- Reference: `services/api/skill_auto_router.py`
- Reference: `services/api/skills/spec.py`

**Step 1: Run backend regression**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_skill_auto_router.py tests/test_teacher_workflow_routing_regression.py tests/test_tool_dispatch_skill_policy.py tests/test_chat_job_processing_service.py tests/test_chat_runtime_service.py
```

Expected: PASS。

**Step 2: Run routing eval script**

Run:

```bash
./.venv/bin/python scripts/eval_teacher_workflow_routing.py
```

Expected:

```text
cases=<N> mismatches=0 fallbacks=<M> low_confidence=<K>
routing fixture evaluation passed
```

**Step 3: Update docs**

在 `docs/reference/agent-runtime-contract.md` 增补一句：
- teacher workflow auto-routing 的稳定关键词/regex 优先来自 skill manifest，而不是散落在运行时代码中的特例。

在 `docs/architecture/module-boundaries.md` 增补一句：
- `skill_auto_router.py` 负责组合评分与降级；manifest 是 routing truth 的优先来源；`auto_route_rules.py` 仅保留难以配置化的兜底启发式。

**Step 4: Run diff guard**

Run:

```bash
git diff --check
```

Expected: PASS。

**Step 5: Commit**

```bash
git add docs/reference/agent-runtime-contract.md docs/architecture/module-boundaries.md
git commit -m "docs(router): document manifest-first routing truth"
```
