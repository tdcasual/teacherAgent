# Dynamic Skill Tools Design (Claude-like Compatibility Layer)

Date: 2026-02-12
Status: Approved
Owner: Backend Skills Platform

## 1. Goal and Scope

We will strengthen the lightweight `SKILL.md` mechanism so that one skill can:

1. Register its own dynamic tools.
2. Use existing built-in static tools in the same request.
3. Stay compatible with Claude-style skill repositories using minimal adaptation.

This design must preserve current skill precedence and source ordering behavior. The existing load order remains unchanged:
`teacher_skills` (lowest) -> project `skills` -> `~/.claude/skills` (higher overrides).

Chosen constraints from product decisions:

- Compatibility mode: High-compatibility with light adaptation (`tool-manifest.yaml`).
- Executors in phase 1: `script + http`.
- Security profile: permissive (wide open), but still with stability safeguards.
- Runtime scope: production, teacher role only.
- Registration mode: import-time precompile + request-time hot reload by file hash/mtime.
- Failure policy: retry, then degrade to static-tools-only flow.
- Tool boundary policy: dynamic tools are not intersected with static role-allowlist.

## 2. Non-Goals

- We do not redesign skill selection logic (`resolve_effective_skill` remains as-is).
- We do not replace static tool registry or static tool dispatch implementation.
- We do not change role-default skills or fallback behavior.
- We do not require external skill authors to adopt a full MCP server.

## 3. Compatibility Contract

### 3.1 Skill Package Layout

For imported teacher skills, compatible package layout is:

- `SKILL.md` (required)
- `tool-manifest.yaml` (recommended for dynamic tools)
- `scripts/` and optional `references/` (optional)

### 3.2 Manifest Shape

`tool-manifest.yaml` introduces dynamic tools with normalized fields:

- `version`
- `runtime.default_timeout_sec`
- `runtime.default_retry.{max_attempts, backoff_ms}`
- `tools[]`
  - `name`
  - `description`
  - `input_schema` (JSON schema object)
  - `executor`
    - `type`: `script` or `http`
    - script: `entry`, `args_template`
    - http: `method`, `url`, `headers_template`, `body_template`

Alias compatibility for external repos:

- `parameters` -> `input_schema`
- `script` -> `entry`
- `endpoint` -> `url`

### 3.3 Coexistence Rule with Static Tools

At request time:

- visible tools = static allowed tools + dynamic tools for current skill
- static tool names always win on name conflict
- dynamic conflicting tools are marked `shadowed` in compile report

## 4. Architecture

Add a dynamic tool extension layer without changing static core:

1. `dynamic_tool_manifest_service.py`
- Parse and normalize manifest.
- Validate schema, executor type, duplicate names.
- Emit compile report.

2. `dynamic_tool_registry.py`
- Build request-scoped merged registry:
  - static `DEFAULT_TOOL_REGISTRY`
  - dynamic entries from selected skill
- Provide OpenAI-compatible tool schemas for dynamic tools.

3. `dynamic_tool_dispatcher.py`
- Dispatch dynamic tool calls.
- Route by executor type:
  - `ScriptRunner`
  - `HttpRunner`

4. `dynamic_tool_runtime_cache.py`
- Cache compiled dynamic tools by `skill_id`.
- Hot reload when source hash/mtime changes.

No changes to skill precedence. Dynamic tooling only activates after a skill is selected by existing routing.

## 5. Data Flow

### 5.1 Import-time Precompile

On `/teacher/skills/import` success:

1. Download/import skill files as today.
2. If `tool-manifest.yaml` exists, compile it.
3. Write artifacts into skill directory:
  - `dynamic_tools.json` (normalized runtime spec)
  - `dynamic_tools.lock.json` (source files + hash + compile metadata)
  - `dynamic_tools.report.json` (valid/invalid/shadowed details)
4. Continue import even if some tools fail compile.

### 5.2 Request-time Hot Reload

On chat request after skill resolution:

1. Load selected skill.
2. Compare lock hash against manifest/source files.
3. If changed, recompile and refresh cache.
4. Build request-scoped merged registry.
5. Expose merged tool schemas to LLM.

### 5.3 Tool Invocation

During tool call loop:

1. Try static dispatch first (current behavior).
2. If not static, try dynamic dispatcher.
3. For dynamic execution:
  - validate args against dynamic `input_schema`
  - execute with timeout + retry policy
4. On repeated failure:
  - emit `dynamic_tool.degraded`
  - return structured error
  - continue workflow with static tools path

## 6. Execution Model

### 6.1 Script Runner

- Execute within skill directory as cwd.
- Command built from `entry` + rendered `args_template`.
- Input/Output contract:
  - stdin optional JSON payload
  - stdout preferred JSON `{ok,data,error}`
- Captured output is size-limited and normalized.

### 6.2 HTTP Runner

- Render URL/headers/body from templates.
- Send request with timeout/retry.
- Parse response JSON/text into normalized tool result.

### 6.3 Retry and Degrade

Retry policy source:

1. Tool-level override in manifest.
2. Runtime default in manifest.
3. System fallback default.

Failure after max attempts triggers degrade path for this tool call only (chat flow remains alive).

## 7. Safety and Governance

The selected profile is permissive, but minimum guardrails still apply for platform stability:

- argument schema validation before execution
- max timeout per call
- output truncation limits
- structured error envelopes
- no static-tool override by dynamic definitions
- dynamic tools only enabled for teacher role in production

Note: this profile intentionally accepts higher operational and security risk to maximize compatibility with code-driven skills.

## 8. Observability

Add diagnostics events:

- `dynamic_tool.compile`
- `dynamic_tool.reload`
- `dynamic_tool.call`
- `dynamic_tool.retry`
- `dynamic_tool.failed`
- `dynamic_tool.degraded`

Common fields:

- `skill_id`, `tool_name`, `executor`, `attempt`, `latency_ms`, `status`, `error_code`

Import API should return compile summary counts:

- `compiled_ok`
- `invalid_tools`
- `shadowed_tools`

## 9. Testing Strategy

### 9.1 Unit

- manifest parser normalization + alias fields
- schema validation pass/fail
- conflict resolution (static wins)
- retry/backoff calculator

### 9.2 Integration

- import + compile artifacts persisted
- request hot reload on manifest change
- merged registry visible to LLM tool schema
- dynamic dispatch success for script/http

### 9.3 E2E

- teacher session with imported dynamic skill:
  - dynamic script tool called successfully
  - dynamic http tool called successfully
  - forced failure retries then degrades to static path

## 10. Rollout Plan

Phase 1 (feature flagged):

1. Implement parser + runtime artifacts.
2. Implement merged registry (teacher-only).
3. Implement dynamic dispatcher (script/http).
4. Add diagnostics and failure degrade behavior.
5. Ship behind `DYNAMIC_SKILL_TOOLS_ENABLED`.

Phase 2:

1. Harden template engine and better error taxonomy.
2. Add optional policy modes (strict/balanced).
3. Evaluate MCP executor as phase-2 extension.

## 11. Definition of Done

- A teacher-imported skill with `tool-manifest.yaml` can register dynamic tools.
- Dynamic and static tools can be used in one session.
- Existing skill precedence and fallback behavior remain unchanged.
- Retry then degrade behavior is observable and deterministic.
- Test suite covers parser, dispatch, and end-to-end dynamic call flow.
