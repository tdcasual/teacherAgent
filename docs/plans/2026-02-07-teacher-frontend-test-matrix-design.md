# 2026-02-07 Teacher Frontend Test Matrix Design

## Scope
- Product area: Teacher web app (`frontend/apps/teacher`)
- Focus: Chat interaction + workbench skills/workflow tabs
- Goal: Build a large idea matrix, then land a high-value executable subset

## Layered Strategy
- `L1` idea matrix: broad coverage (80+ cases), risk-first organization
- `L2` executable set: first 12 Playwright cases with highest regression value

## L2 First 12 (Executable)
| ID | Domain | Intent | Target Spec |
| --- | --- | --- | --- |
| TF-CHAT-INPUT-001 | Chat Input | IME composing Enter should not submit | `frontend/e2e/teacher-chat-chaos.spec.ts` |
| TF-CHAT-INPUT-004 | Chat Input | Multi-token cleanup keeps final effective @/$ | `frontend/e2e/teacher-chat-chaos.spec.ts` |
| TF-CHAT-ASYNC-002 | Chat Async | `/chat/status` transient error retries and recovers | `frontend/e2e/teacher-chat-chaos.spec.ts` |
| TF-CHAT-SESSION-003 | Session | Pending job remains bound to source session | `frontend/e2e/teacher-chat-chaos.spec.ts` |
| TF-CHAT-SESSION-006 | Session | Session menu closes on outside click/Escape | `frontend/e2e/teacher-chat-chaos.spec.ts` |
| TF-PERSIST-002 | Persistence | Corrupt `teacherSkillPinned` falls back safely | `frontend/e2e/teacher-chat-chaos.spec.ts` |
| TF-PERSIST-006 | Persistence | Resume pending chat from localStorage | `frontend/e2e/teacher-chat-chaos.spec.ts` |
| TF-WORKBENCH-SKILL-002 | Skill Workbench | Favorite+filter keeps correct insert target | `frontend/e2e/teacher-workbench-regression.spec.ts` |
| TF-WORKBENCH-WFLOW-004 | Workflow Workbench | Confirm enters confirming and blocks duplicates | `frontend/e2e/teacher-workbench-regression.spec.ts` |
| TF-WORKBENCH-WFLOW-009 | Workflow Workbench | Assignment/Exam mode state isolation | `frontend/e2e/teacher-workbench-regression.spec.ts` |
| TF-MOBILE-A11Y-003 | Mobile/A11y | Overlay closes both side panels on mobile | `frontend/e2e/teacher-workbench-regression.spec.ts` |
| TF-WORKBENCH-SKILL-007 | Skill Workbench | Template path can return to auto-route mode | `frontend/e2e/teacher-workbench-regression.spec.ts` |

## L1 Large Idea Matrix (96 Cases)

### Chat Input (12)
- TF-CHAT-INPUT-001: IME composing state with Enter should not submit request.
- TF-CHAT-INPUT-002: Shift+Enter inserts newline and does not submit.
- TF-CHAT-INPUT-003: Empty text with only spaces should not submit.
- TF-CHAT-INPUT-004: Multiple `@agent`/`$skill` tokens keep only cleaned user text.
- TF-CHAT-INPUT-005: Unknown `@agent` warning appears and request uses fallback agent.
- TF-CHAT-INPUT-006: Unknown `$skill` warning in auto-route mode uses normalized warning text.
- TF-CHAT-INPUT-007: Mention panel arrow key loops from bottom to top.
- TF-CHAT-INPUT-008: Mention panel Enter inserts highlighted item at cursor.
- TF-CHAT-INPUT-009: Cursor in middle insertion preserves surrounding text spacing.
- TF-CHAT-INPUT-010: Mixed Chinese/English tokens parse without corruption.
- TF-CHAT-INPUT-011: Invalid token id (`$bad!id`) does not crash parser.
- TF-CHAT-INPUT-012: Very long prompt with one invocation token still sends trimmed payload.

### Chat Async (12)
- TF-CHAT-ASYNC-001: `chat/start` success then immediate `done` status renders reply.
- TF-CHAT-ASYNC-002: First `chat/status` fails, retry succeeds, final reply shown.
- TF-CHAT-ASYNC-003: Long `processing` state keeps placeholder until completion.
- TF-CHAT-ASYNC-004: `failed` status updates placeholder with readable error.
- TF-CHAT-ASYNC-005: `cancelled` status updates placeholder and clears pending state.
- TF-CHAT-ASYNC-006: Queue hint shows lane position when `queued` with lane metrics.
- TF-CHAT-ASYNC-007: Queue hint switches to processing label once status changes.
- TF-CHAT-ASYNC-008: Visibilitychange to visible triggers immediate poll refresh.
- TF-CHAT-ASYNC-009: Network jitter message is replaced by final success reply.
- TF-CHAT-ASYNC-010: Rapid consecutive sends blocked while pending job exists.
- TF-CHAT-ASYNC-011: Sending state resets correctly after terminal failure.
- TF-CHAT-ASYNC-012: Request payload keeps max recent context window contract.

### Session Sidebar (12)
- TF-CHAT-SESSION-001: New session appears in sidebar immediately.
- TF-CHAT-SESSION-002: Rename operation updates title map and rendered title.
- TF-CHAT-SESSION-003: Pending job reply attaches only to originating session.
- TF-CHAT-SESSION-004: Switching sessions clears session-level error state.
- TF-CHAT-SESSION-005: Archived view toggle filters visible sessions correctly.
- TF-CHAT-SESSION-006: Session menu closes on outside click and Escape.
- TF-CHAT-SESSION-007: Dismissed archive confirm closes menu without action.
- TF-CHAT-SESSION-008: Session search matches id/title/preview fields.
- TF-CHAT-SESSION-009: Load-more sessions button disables when no next cursor.
- TF-CHAT-SESSION-010: Load older messages button handles no-more state gracefully.
- TF-CHAT-SESSION-011: Sidebar collapsed state prevents accidental menu interaction.
- TF-CHAT-SESSION-012: Mobile selecting session closes sidebar automatically.

### Scroll and Focus Routing (12)
- TF-CHAT-SCROLL-001: Desktop app/body overflow remains locked (`hidden`).
- TF-CHAT-SCROLL-002: Chat messages area scrolls independently from side panels.
- TF-CHAT-SCROLL-003: Default wheel route targets chat until side panel activation.
- TF-CHAT-SCROLL-004: Activated skill panel captures wheel without page scroll bleed.
- TF-CHAT-SCROLL-005: Clicking chat pane reclaims wheel routing from workbench.
- TF-CHAT-SCROLL-006: `scroll-to-bottom` button appears when reading history.
- TF-CHAT-SCROLL-007: `scroll-to-bottom` hides after returning near bottom threshold.
- TF-CHAT-SCROLL-008: Session panel overscroll behavior remains `contain`.
- TF-CHAT-SCROLL-009: Skill panel overscroll behavior remains `contain`.
- TF-CHAT-SCROLL-010: Routing page can scroll large channel list safely.
- TF-CHAT-SCROLL-011: Scroll anchor top positions remain stable during wheel bursts.
- TF-CHAT-SCROLL-012: Natural message overflow works without forced inline sizing.

### Skill Workbench (12)
- TF-WORKBENCH-SKILL-001: Skill search filters by id/title/description.
- TF-WORKBENCH-SKILL-002: Favorite+only-favorite filter keeps insertion target stable.
- TF-WORKBENCH-SKILL-003: Favorite toggles persist across reload via localStorage.
- TF-WORKBENCH-SKILL-004: `设为当前` pins skill and updates composer chip.
- TF-WORKBENCH-SKILL-005: `插入 $` inserts token and sends cleaned text payload.
- TF-WORKBENCH-SKILL-006: `使用模板` appends prompt at caret with focus retained.
- TF-WORKBENCH-SKILL-007: Switch back to auto route omits `skill_id` on request.
- TF-WORKBENCH-SKILL-008: Agent card `插入 @` updates active agent and token.
- TF-WORKBENCH-SKILL-009: Skills API failure falls back to bundled skill list.
- TF-WORKBENCH-SKILL-010: Skills refresh button shows loading and re-enables.
- TF-WORKBENCH-SKILL-011: Workbench collapse/expand preserves tab selection.
- TF-WORKBENCH-SKILL-012: Mixed use of `@` and `$` from cards yields coherent payload.

### Workflow Workbench (12)
- TF-WORKBENCH-WFLOW-001: Assignment upload validation blocks missing assignment id.
- TF-WORKBENCH-WFLOW-002: Assignment upload validation blocks missing files.
- TF-WORKBENCH-WFLOW-003: Class/student scope enforces required class/student fields.
- TF-WORKBENCH-WFLOW-004: Confirm button enters confirming and blocks duplicates.
- TF-WORKBENCH-WFLOW-005: Confirm button disabled before parse reaches `done`.
- TF-WORKBENCH-WFLOW-006: Requirements-missing disables confirm with tooltip reason.
- TF-WORKBENCH-WFLOW-007: Save draft updates status message and dirty flags.
- TF-WORKBENCH-WFLOW-008: Exam confirm path handles `job_not_ready` gracefully.
- TF-WORKBENCH-WFLOW-009: Assignment/Exam mode switch keeps form state isolated.
- TF-WORKBENCH-WFLOW-010: Workflow status chips reflect upload/parse/review/confirm transitions.
- TF-WORKBENCH-WFLOW-011: `teacherActiveUpload` recovery resumes polling on reload.
- TF-WORKBENCH-WFLOW-012: Collapsed panel summaries stay consistent with latest state.

### Persistence and Recovery (12)
- TF-PERSIST-001: Invalid JSON in favorites localStorage falls back to empty list.
- TF-PERSIST-002: Corrupt `teacherSkillPinned` value falls back to auto routing.
- TF-PERSIST-003: Missing `teacherActiveAgentId` falls back to `default`.
- TF-PERSIST-004: Invalid `teacherUploadMode` falls back to assignment.
- TF-PERSIST-005: Draft session ids survive reload before backend persistence.
- TF-PERSIST-006: Pending chat job recovers and finishes after refresh.
- TF-PERSIST-007: Pending chat from non-main session auto-activates source session.
- TF-PERSIST-008: Session view-state sync conflict keeps usable local state.
- TF-PERSIST-009: LocalStorage write failures do not crash app interactions.
- TF-PERSIST-010: Stale archived ids do not break session rendering.
- TF-PERSIST-011: Unknown workbench tab local value falls back to skills tab.
- TF-PERSIST-012: API base override persists and applies to new requests.

### Mobile and A11y (12)
- TF-MOBILE-A11Y-001: Mobile viewport keeps routing entry button visible.
- TF-MOBILE-A11Y-002: Mobile session toggle and workbench toggle are reachable.
- TF-MOBILE-A11Y-003: Overlay click closes both session and workbench panels.
- TF-MOBILE-A11Y-004: Session menu trigger exposes `aria-expanded` accurately.
- TF-MOBILE-A11Y-005: Keyboard-only open/close session menu works (Enter/Escape).
- TF-MOBILE-A11Y-006: Composer send button disabled while pending job exists.
- TF-MOBILE-A11Y-007: Disabled confirm controls expose expected title hints.
- TF-MOBILE-A11Y-008: Mention panel remains keyboard navigable on narrow screens.
- TF-MOBILE-A11Y-009: Focus returns to composer after mention insertion.
- TF-MOBILE-A11Y-010: Touch interactions do not trigger desktop-only wheel assumptions.
- TF-MOBILE-A11Y-011: Long content does not hide send button behind viewport.
- TF-MOBILE-A11Y-012: High-density session list remains scrollable on mobile.

## Prioritization Heuristic
- `P0`: Data loss, wrong request payload, stuck workflow, session-cross contamination.
- `P1`: Incorrect warning/disabled state, inconsistent panel behavior, recovery regressions.
- `P2`: UX polish and less frequent edge interactions.

## Notes for Next Expansion
- Keep adding executable cases by ID, not ad-hoc names.
- For timing-sensitive tests, prefer deterministic counters over long sleeps.
- When adding chaos tests, isolate them in dedicated spec files to avoid slowing baseline smoke paths.
