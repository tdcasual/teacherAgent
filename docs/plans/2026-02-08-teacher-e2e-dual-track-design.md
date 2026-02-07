# 2026-02-08 Teacher E2E Dual-Track Design

## Scope
- Product: Teacher web app + upload workflow backend
- Priority strategy: frontend-first 70% + system-real 30%
- This document focuses on executable deep-chain cases for both tracks:
  - Assignment deep chain: A001-A024
  - Exam deep chain: E001-E024
- Total in this design: 48 executable E2E cases

## Objectives
- Keep PR feedback fast while retaining real integration confidence.
- Validate the end-to-end state machine from UI actions to backend status transitions.
- Validate persistence/restore behavior (`teacherActiveUpload`, refresh recovery, terminal cleanup).
- Ensure key data outputs are durable and semantically consistent for downstream analytics.

## Test Architecture
- Lane 1 (`PR-SMOKE`): stable UI+contract cases, deterministic mocks, short runtime.
- Lane 2 (`NIGHTLY-SYSTEM`): real API + file upload + filesystem assertions.
- Suite boundaries:
  - UI/contract regression (Playwright + route mocks)
  - Workflow deep chain (Playwright + status orchestration)
  - System persistence checks (Playwright + API + file assertions)
- Flake-control rules:
  - Prefer deterministic counters and fixed status progression over arbitrary sleeps.
  - Use narrow selectors tied to semantic labels/titles, avoid fragile text duplication.
  - Isolate heavy/slow cases in dedicated specs.

## Data Flow Under Test
1. Teacher action in workflow UI (`upload -> parse -> draft -> confirm`).
2. Frontend triggers `/assignment/upload/*` or `/exam/upload/*` endpoints.
3. Poll status drives UI state chips/buttons/messages.
4. Draft load/save round-trip preserves user edits.
5. Confirm writes durable artifacts under `data/` and clears active-recovery markers.
6. Subsequent reads (`overview`, `analysis`, progress panels) remain consistent.

## Error Handling Under Test
- Input validation errors before request dispatch.
- Asynchronous status failures and retry behavior.
- Confirm precondition failures (`job_not_ready`, missing requirements).
- Terminal states (`failed`, `confirmed`) and local marker cleanup.
- Refresh/reopen recovery with active job context.

## Assignment Deep Chain (A001-A024)
| ID | Scenario | Trigger | Core Assertions |
| --- | --- | --- | --- |
| A001 | Missing assignment id blocked | submit upload form without id | UI shows validation error; no `/assignment/upload/start` |
| A002 | Missing assignment file blocked | id exists, no files | UI error; no request sent |
| A003 | Class scope missing class name | scope=class with file | UI error; no request sent |
| A004 | Student scope missing student ids | scope=student with file | UI error; no request sent |
| A005 | Upload success stores active marker | valid form submit | `teacherActiveUpload={type:assignment,job_id}` |
| A006 | Status queued->processing visible | polling status progression | workflow chip/status text updates correctly |
| A007 | Transient status error recovers | first status fails then success | UI remains interactive; polling resumes |
| A008 | Done triggers draft fetch | status reaches done | `/assignment/upload/draft` called; draft panel visible |
| A009 | Draft load failure surfaced | draft API error | visible draft error block, no crash |
| A010 | Draft save success round-trip | click 保存草稿 | success message and updated draft marker |
| A011 | Draft save failure surfaced | save returns error | error shown; state not falsely advanced |
| A012 | Missing requirements disables confirm | draft has requirements_missing | 创建作业 disabled + reason tooltip |
| A013 | Confirm gate requires done | status != done | confirm remains disabled |
| A014 | Confirm in-flight prevents duplicate | rapid repeated clicks | exactly one confirm request |
| A015 | Confirm success terminal state | confirm success response | button -> 已创建; terminal workflow chip |
| A016 | Confirm failure retryable | confirm returns error | error shown; user can retry |
| A017 | Refresh recovers active assignment job | reload page with marker | app restores workflow/job and continues polling |
| A018 | Tab switches keep workflow state | switch chat/routing/workflow | upload/draft state preserved |
| A019 | Collapsed panel summary coherence | collapse/expand cards | summary reflects latest state |
| A020 | Progress refresh action integrity | click 刷新完成率 | loading/disabled toggles + result binds |
| A021 | Incomplete filter correctness | toggle 只看未完成 | visible rows match filter rule |
| A022 | Session switching isolation | change chat session during workflow | workflow state unaffected |
| A023 | API base override effective | change settings base URL | subsequent upload/status requests use new base |
| A024 | Filesystem artifact consistency | real confirm run | assignment files exist and required fields valid |

## Exam Deep Chain (E001-E024)
| ID | Scenario | Trigger | Core Assertions |
| --- | --- | --- | --- |
| E001 | Missing paper file blocked | submit exam form without paper | UI error; no `/exam/upload/start` |
| E002 | Missing score file blocked | paper present, no score | UI error; no request |
| E003 | Upload success stores active marker | valid exam upload | `teacherActiveUpload={type:exam,job_id}` |
| E004 | Queued->processing visible | polling progression | exam workflow chip/status updates |
| E005 | Status failure then recovery | transient status error | retry path works, no stuck UI |
| E006 | Done triggers exam draft fetch | status done | exam draft panel visible |
| E007 | Max-score edits persist | edit question max_score + save | saved draft reflects new scores |
| E008 | Meta edits persist | edit date/class + save | draft reload returns edited meta |
| E009 | Answer key text persists | edit answer_key_text + save | value preserved across reload |
| E010 | Confirm gate requires done | status != done | 创建考试 disabled |
| E011 | Confirm in-flight dedupe | rapid clicks on 创建考试 | single confirm request |
| E012 | Confirmed terminal lock | status confirmed | button state prevents repeat confirm |
| E013 | job_not_ready error path | confirm before ready | precise error feedback + polling resume |
| E014 | Failed state clears active marker | status failed | local active marker removed |
| E015 | Confirmed state clears active marker | status confirmed | local active marker removed |
| E016 | Scoring status visibility | partial/scored cases | correct scoring labels and counts |
| E017 | Default max-score warning visible | default_max_score_qids present | warning shown in draft meta |
| E018 | Refresh recovers active exam job | reload with marker | exam mode restored and polling resumed |
| E019 | Mode switch isolation | assignment<->exam switch | no cross-mode field leakage |
| E020 | Collapse summary coherence | collapse/expand exam draft | summary equals current state |
| E021 | Mobile action reachability | small viewport | critical exam actions visible/clickable |
| E022 | Network jitter resilience | intermittent status issues | UI avoids blank/broken state |
| E023 | Analysis read path available | confirm then open analysis route | downstream analysis endpoints readable |
| E024 | Filesystem artifact consistency | real exam confirm run | `data/exams` and `data/analysis` aligned |

## Playwright File Allocation
| File | Primary IDs | Notes |
| --- | --- | --- |
| `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-workflow-validation.spec.ts` | A001-A004, E001-E002, A012-A013 | Keep fast deterministic validation coverage |
| `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-upload-lifecycle.spec.ts` | A005-A011, A014-A019, E003-E006, E010-E015, E018-E020 | Deep workflow state-machine with controlled status progressions |
| `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-workbench-regression.spec.ts` | A022, E019, E021 | Existing UI stability coverage reused |
| `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-system-assignment.spec.ts` (new) | A020-A021, A023-A024 | Real backend + filesystem assertions |
| `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-system-exam.spec.ts` (new) | E007-E009, E016-E017, E022-E024 | Real backend + analysis/draft consistency assertions |

## Execution Plan
1. Extend existing specs first (A001-A019, E001-E020).
2. Add two system-real specs for filesystem-level assertions.
3. Gate PR with stable subset; schedule heavy real cases nightly.

## Proposed CI Split
- `teacher-e2e-smoke`:
  - deterministic, mock-heavy, under ~6 minutes
  - includes A001-A019, E001-E020 stable subset
- `teacher-e2e-system`:
  - real upload/confirm filesystem checks
  - includes A020-A024, E021-E024

## Acceptance Criteria
- Each ID maps to exactly one primary spec test name.
- No duplicate assertion ownership across files.
- Terminal states always verify marker cleanup.
- System cases verify durable artifacts, not only UI text.

## Next Step
- Convert this design to implementation checklist and add missing spec files:
  - `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-system-assignment.spec.ts`
  - `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-system-exam.spec.ts`
