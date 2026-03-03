# Multi-Angle Audit Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve the highest-risk findings from the 2026-03-03 code audit while improving maintainability, security governance, and quality headroom.

**Architecture:** Use a risk-first sequence: reduce complexity in high-traffic backend paths, then reduce exception-policy debt, then harden dependency audit gates, and finally recover `app_core.py` budget headroom. Every task is TDD-first with small commits so regressions are isolated and reversible.

**Tech Stack:** Python 3.13, FastAPI, pytest, Ruff, mypy, Node 24, Vitest, GitHub Actions

---

## Execution Rules

- Work in isolated worktree and branch (example: `codex/audit-remediation-20260303`).
- Required skills during implementation: `@test-driven-development`, `@systematic-debugging`, `@verification-before-completion`, `@requesting-code-review`.
- DRY + YAGNI: only extract code needed to remove current risk; do not redesign unrelated modules.
- One commit per task.

### Task 1: Route Complexity Reduction (Auth + Chat)

**Files:**
- Create: `services/api/routes/auth_route_handlers.py`
- Create: `services/api/routes/chat_route_handlers.py`
- Modify: `services/api/routes/auth_routes.py`
- Modify: `services/api/routes/chat_routes.py`
- Test: `tests/test_route_complexity_hotspots.py`

**Step 1: Write the failing test**

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _ruff_c901(path: str) -> list[dict]:
    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        path,
        "--select",
        "C901",
        "--config",
        "lint.mccabe.max-complexity=14",
        "--output-format",
        "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = proc.stdout.strip()
    return json.loads(out) if out else []


def test_auth_and_chat_routes_have_no_c901_over_14() -> None:
    targets = [
        "services/api/routes/auth_routes.py",
        "services/api/routes/chat_routes.py",
    ]
    issues: list[dict] = []
    for target in targets:
        issues.extend(_ruff_c901(target))
    assert not issues, f"C901 issues still present: {issues}"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_route_complexity_hotspots.py::test_auth_and_chat_routes_have_no_c901_over_14`  
Expected: FAIL with C901 items from `register_auth_routes` and `_register_chat_routes`/`chat_stream`.

**Step 3: Write minimal implementation**

```python
# services/api/routes/auth_route_handlers.py
from __future__ import annotations

from typing import Any, Callable


def build_auth_handlers(core: Any) -> dict[str, Callable[..., Any]]:
    return {
        "login": core.login_handler,
        "refresh": core.refresh_handler,
        "logout": core.logout_handler,
    }
```

```python
# services/api/routes/auth_routes.py (shape)
from .auth_route_handlers import build_auth_handlers

def register_auth_routes(router, core):
    handlers = build_auth_handlers(core)
    router.post("/auth/login")(handlers["login"])
    router.post("/auth/refresh")(handlers["refresh"])
    router.post("/auth/logout")(handlers["logout"])
```

```python
# services/api/routes/chat_route_handlers.py (shape)
from __future__ import annotations

from typing import Any, Callable


def build_chat_handlers(core: Any) -> dict[str, Callable[..., Any]]:
    return {
        "start": core.chat_start_handler,
        "status": core.chat_status_handler,
        "stream": core.chat_stream_handler,
    }
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_route_complexity_hotspots.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/routes/auth_route_handlers.py services/api/routes/chat_route_handlers.py \
  services/api/routes/auth_routes.py services/api/routes/chat_routes.py \
  tests/test_route_complexity_hotspots.py
git commit -m "refactor: split auth/chat route handlers to remove C901 hotspots"
```

### Task 2: Service Complexity Reduction (Exam Range + Skills Loader)

**Files:**
- Create: `services/api/exam_range_query_helpers.py`
- Create: `services/api/skills/loader_parse_helpers.py`
- Modify: `services/api/exam_range_service.py`
- Modify: `services/api/skills/loader.py`
- Test: `tests/test_service_complexity_hotspots.py`

**Step 1: Write the failing test**

```python
from __future__ import annotations

import json
import subprocess
import sys


def _issues(path: str) -> list[dict]:
    cmd = [
        sys.executable, "-m", "ruff", "check", path,
        "--select", "C901",
        "--config", "lint.mccabe.max-complexity=14",
        "--output-format", "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return json.loads(proc.stdout or "[]")


def test_exam_range_and_skill_loader_hotspots_removed() -> None:
    targets = [
        "services/api/exam_range_service.py",
        "services/api/skills/loader.py",
    ]
    issues = [item for t in targets for item in _issues(t)]
    assert not issues, f"C901 issues still present: {issues}"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_service_complexity_hotspots.py::test_exam_range_and_skill_loader_hotspots_removed`  
Expected: FAIL with C901 on `exam_range_top_students` and `_load_skill_spec_from_folder`.

**Step 3: Write minimal implementation**

```python
# services/api/exam_range_query_helpers.py (shape)
from __future__ import annotations

from typing import Any, Dict


def normalize_range_args(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "start_question_no": args.get("start_question_no"),
        "end_question_no": args.get("end_question_no"),
        "top_n": int(args.get("top_n", 10) or 10),
    }
```

```python
# services/api/skills/loader_parse_helpers.py (shape)
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def read_skill_files(folder: Path) -> Dict[str, Any]:
    return {
        "skill_md": (folder / "SKILL.md").read_text(encoding="utf-8"),
        "skill_yaml": (folder / "skill.yaml").read_text(encoding="utf-8"),
    }
```

Refactor callers to delegate branching/parsing to helpers and keep each public function linear.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_service_complexity_hotspots.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/exam_range_query_helpers.py services/api/skills/loader_parse_helpers.py \
  services/api/exam_range_service.py services/api/skills/loader.py \
  tests/test_service_complexity_hotspots.py
git commit -m "refactor: extract exam range and skill loader logic to reduce C901"
```

### Task 3: Exception Policy Debt Burn-Down (Chat Lock First)

**Files:**
- Modify: `services/api/chat_lock_service.py`
- Modify: `config/exception_policy_allowlist.txt`
- Create: `tests/test_exception_policy_budget_targets.py`

**Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path


def _entries() -> list[str]:
    path = Path("config/exception_policy_allowlist.txt")
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_chat_lock_allowlist_entries_reduced_to_budget() -> None:
    rows = _entries()
    chat_lock_rows = [r for r in rows if r.startswith("services/api/chat_lock_service.py:")]
    assert len(chat_lock_rows) <= 10, f"chat_lock allowlist too high: {len(chat_lock_rows)}"


def test_global_allowlist_entries_reduced_to_budget() -> None:
    rows = _entries()
    assert len(rows) <= 340, f"allowlist still too high: {len(rows)}"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_exception_policy_budget_targets.py`  
Expected: FAIL because current counts are above target (`chat_lock` and global entries).

**Step 3: Write minimal implementation**

```python
# services/api/chat_lock_service.py (shape)
from json import JSONDecodeError
from pathlib import Path


def _read_lock_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except JSONDecodeError:
        return {}
```

Replace broad `except Exception` with explicit exceptions (`FileNotFoundError`, `PermissionError`, `JSONDecodeError`, `OSError`) and add policy marker comments only where broad catch is still required by design.  
Then remove stale/deleted entries from `config/exception_policy_allowlist.txt`.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_exception_policy_budget_targets.py && python3 scripts/quality/check_exception_policy.py`  
Expected: PASS, and check script reports reduced tracked violations.

**Step 5: Commit**

```bash
git add services/api/chat_lock_service.py config/exception_policy_allowlist.txt \
  tests/test_exception_policy_budget_targets.py
git commit -m "chore: reduce exception policy debt in chat lock flow"
```

### Task 4: Dependency Audit Governance in CI

**Files:**
- Create: `scripts/quality/check_frontend_prod_audit.sh`
- Create: `scripts/quality/check_backend_dep_audit.sh`
- Modify: `.github/workflows/ci.yml`
- Create: `tests/test_dependency_audit_ci_contract.py`

**Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path


def test_ci_contains_dependency_audit_steps() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "scripts/quality/check_frontend_prod_audit.sh" in text
    assert "scripts/quality/check_backend_dep_audit.sh" in text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_dependency_audit_ci_contract.py`  
Expected: FAIL because CI currently lacks these commands.

**Step 3: Write minimal implementation**

```bash
# scripts/quality/check_frontend_prod_audit.sh
#!/usr/bin/env bash
set -euo pipefail
cd frontend
npm audit --omit=dev --audit-level=high
```

```bash
# scripts/quality/check_backend_dep_audit.sh
#!/usr/bin/env bash
set -euo pipefail
docker run --rm -v "$PWD:/workspace" -w /workspace python:3.13-slim \
  bash -lc "pip install -q pip-audit && pip-audit -r services/api/requirements.txt"
```

Add corresponding CI steps in `.github/workflows/ci.yml` (backend-quality job).

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_dependency_audit_ci_contract.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/quality/check_frontend_prod_audit.sh scripts/quality/check_backend_dep_audit.sh \
  .github/workflows/ci.yml tests/test_dependency_audit_ci_contract.py
git commit -m "ci: add production dependency audit gates for frontend and backend"
```

### Task 5: Recover `app_core.py` Budget Headroom

**Files:**
- Create: `services/api/app_core_init.py`
- Modify: `services/api/app_core.py`
- Modify: `config/backend_quality_budget.json`
- Create: `tests/test_app_core_headroom_budget.py`

**Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path


def test_app_core_line_budget_has_headroom() -> None:
    lines = len(Path("services/api/app_core.py").read_text(encoding="utf-8").splitlines())
    assert lines <= 260, f"app_core.py still too large: {lines}"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_app_core_headroom_budget.py`  
Expected: FAIL (`app_core.py` is currently 276 lines).

**Step 3: Write minimal implementation**

```python
# services/api/app_core_init.py (shape)
from __future__ import annotations

from typing import Any


def init_runtime_dependencies(core: Any) -> None:
    core._init_paths()
    core._init_limits()
    core._init_services()
```

Move non-public initialization blocks from `app_core.py` into `app_core_init.py` without changing runtime behavior.  
Update `config/backend_quality_budget.json`:

```json
{
  "ruff_max": 1,
  "mypy_max": 1,
  "app_core_max_lines": 260
}
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_app_core_headroom_budget.py && python3 scripts/quality/check_backend_quality_budget.py --print-only`  
Expected: PASS and reported `app_core_lines <= 260`.

**Step 5: Commit**

```bash
git add services/api/app_core_init.py services/api/app_core.py \
  config/backend_quality_budget.json tests/test_app_core_headroom_budget.py
git commit -m "refactor: extract app core initialization and restore budget headroom"
```

## Final Verification (No Skip)

Run in order:

```bash
python3 -m pytest -q tests/test_route_complexity_hotspots.py tests/test_service_complexity_hotspots.py
python3 -m pytest -q tests/test_exception_policy_budget_targets.py tests/test_dependency_audit_ci_contract.py tests/test_app_core_headroom_budget.py
python3 scripts/quality/check_complexity_budget.py
python3 scripts/quality/check_exception_policy.py
python3 scripts/quality/check_backend_quality_budget.py
python3 -m pytest tests/ -x -q -m "not stress"
```

Expected:
- zero new C901 regressions in targeted hotspots
- exception allowlist count reduced and policy check green
- dependency audit CI contract test green
- `app_core.py` below new budget
- full test suite passes

## Documentation Update

- Modify: `docs/operations/rewrite-baseline-metrics-2026-03-02.md` (append remediation delta)
- Create: `docs/plans/2026-03-03-multi-angle-audit-remediation-report.md` (before/after metrics, risk closure, residual debt)

Recommended final commit:

```bash
git add docs/operations/rewrite-baseline-metrics-2026-03-02.md \
  docs/plans/2026-03-03-multi-angle-audit-remediation-report.md
git commit -m "docs: record audit remediation outcomes and residual risks"
```
