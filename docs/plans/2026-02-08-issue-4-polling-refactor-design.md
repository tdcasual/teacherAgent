# Issue 4 Polling Refactor Design

**Goal:** Refactor Teacher workbench polling to use the shared visibility-aware backoff poller without changing user-visible behavior.

**Scope (A):**
- Update `useAssignmentUploadStatusPolling.ts` and `useExamUploadStatusPolling.ts` to use `startVisibilityAwareBackoffPolling`.
- Preserve existing backoff, jitter, and “reset on status change” semantics.
- No new libraries and no changes to Student or Routing pages.

## Architecture

We will centralize timer/backoff orchestration in `startVisibilityAwareBackoffPolling`, keeping hook-specific logic limited to:
- issuing the API call
- computing a stable “status fingerprint”
- deciding whether polling should continue
- signaling delay reset when a state transition is detected

The poller will continue to manage:
- visibility-aware scheduling
- exponential backoff
- jitter
- cancellation on unmount

## Data Flow

1. Hook starts polling by calling `startVisibilityAwareBackoffPolling`.
2. `poll()` calls the existing status endpoint and derives a fingerprint (e.g., status + progress + timestamps).
3. If fingerprint changed since last poll:
   - return `{ action: 'continue', resetDelay: true }` to restart backoff from initial delay.
4. If status is terminal or polling should stop:
   - return `'stop'`.
5. Otherwise:
   - return `'continue'` to follow backoff progression.

## Error Handling

Errors are logged through the existing `onError` handler and do not stop polling. Backoff continues after failures.

## Testing Strategy (TDD)

- Add a targeted test that fails first:
  - When fingerprint changes, the next scheduled delay resets to the initial delay.
  - When fingerprint does not change, delay follows backoff growth.
- Run the test to verify RED, implement minimal changes, re-run to GREEN.
- Run existing hard verification gates:
  - `npm run typecheck`
  - `npm run e2e:teacher`
  - `npm run e2e:student`

## Out of Scope

- Refactoring `RoutingPage` auto-refresh.
- Any Student-side polling or debounce logic changes.
- Introducing React Query / SWR.
