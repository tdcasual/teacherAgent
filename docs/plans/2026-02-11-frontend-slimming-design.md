# Frontend File Slimming Design

Date: 2026-02-11

## Goal

Reduce three oversized frontend files to manageable sizes:
- `App.tsx` 2612 → ~350 lines
- `TeacherWorkbench.tsx` 1891 → ~150 lines
- `styles.css` 2953 → deleted (replaced by Tailwind CSS)

## Phase 1: App.tsx Decomposition

### 1.1 TeacherAppContext

Create `features/state/TeacherAppContext.tsx` to eliminate the 120-prop drilling chain from App → TeacherWorkbench.

Context provides: `apiBase`, current session state, workbench state, all action callbacks from extracted hooks.

### 1.2 Extracted Hooks

| Hook | File | Responsibility | ~Lines |
|------|------|---------------|--------|
| `useTeacherChatApi` | `features/chat/useTeacherChatApi.ts` | Session list refresh, message loading, message sending, chat job polling | 250 |
| `useAssignmentWorkflow` | `features/workbench/hooks/useAssignmentWorkflow.ts` | Assignment upload, save draft, confirm upload, progress query | 200 |
| `useExamWorkflow` | `features/workbench/hooks/useExamWorkflow.ts` | Exam upload, save draft, confirm upload | 180 |
| `useDraftMutations` | `features/workbench/hooks/useDraftMutations.ts` | Draft field updates (requirements, questions, exam metadata, score schema) | 120 |
| `useSkillManager` | `features/workbench/hooks/useSkillManager.ts` | Skill list fetch, filter, favorites, selection, insertion | 150 |
| `useSessionActions` | `features/chat/useSessionActions.ts` | New/rename/archive session, dialog management | 130 |
| `useLocalStorageSync` | `features/state/useLocalStorageSync.ts` | ~20 localStorage persistence effects consolidated | 100 |
| `useWheelScrollZone` | `features/chat/useWheelScrollZone.ts` | Wheel scroll zone management | 80 |

### 1.3 Final App.tsx Structure

```
App.tsx (~350 lines):
  - Imports + constants
  - Compose all hooks
  - Provide TeacherAppContext
  - Render layout skeleton: Topbar, SettingsModal, SessionSidebar, ChatPanel, WorkbenchPanel
  - Render dialogs (rename, archive)
```

## Phase 2: TeacherWorkbench.tsx Decomposition

### 2.1 Tab Components

| Component | File | ~Lines |
|-----------|------|--------|
| `SkillsTab` | `features/workbench/tabs/SkillsTab.tsx` | 200 |
| `WorkflowTab` | `features/workbench/tabs/WorkflowTab.tsx` | 100 |
| `MemoryTab` | `features/workbench/tabs/MemoryTab.tsx` | 120 |

### 2.2 WorkflowTab Sub-components

| Component | File | ~Lines |
|-----------|------|--------|
| `WorkflowSummaryCard` | `features/workbench/workflow/WorkflowSummaryCard.tsx` | 80 |
| `UploadSection` | `features/workbench/workflow/UploadSection.tsx` | 180 |
| `AssignmentProgressSection` | `features/workbench/workflow/AssignmentProgressSection.tsx` | 100 |
| `AssignmentDraftSection` | `features/workbench/workflow/AssignmentDraftSection.tsx` | 250 |
| `ExamDraftSection` | `features/workbench/workflow/ExamDraftSection.tsx` | 200 |
| `ExamCandidateMappingCard` | `features/workbench/workflow/ExamCandidateMappingCard.tsx` | 250 |

### 2.3 SkillsTab Sub-components

| Component | File | ~Lines |
|-----------|------|--------|
| `SkillCard` | `features/workbench/skills/SkillCard.tsx` | 100 |
| `SkillCreateForm` | `features/workbench/skills/SkillCreateForm.tsx` | 60 |
| `SkillImportDialog` | `features/workbench/skills/SkillImportDialog.tsx` | 60 |

### 2.4 Pure Logic Extraction

- `examCandidateAnalysis.ts` — sorting, recommendation, conflict detection (~120 lines)

### 2.5 Final TeacherWorkbench.tsx Structure

```
TeacherWorkbench.tsx (~150 lines):
  - Consume TeacherAppContext
  - Workbench header (refresh, collapse buttons)
  - Tab switcher
  - Render active tab component
```

## Phase 3: styles.css → Tailwind CSS Migration

### 3.1 Installation & Configuration

- Install: `tailwindcss`, `@tailwindcss/vite`, `@tailwindcss/typography`
- Add Tailwind Vite plugin to both `vite.teacher.config.ts` and `vite.student.config.ts`
- Create `tailwind.css` entry with `@import "tailwindcss"` and `@theme` block mapping existing CSS variables
- `@tailwindcss/typography` replaces `.text` markdown prose styles

### 3.2 Theme Mapping (from `:root` variables)

Map existing CSS custom properties to Tailwind theme extensions:
- Colors: `--accent`, `--bg`, `--surface`, `--border`, `--text-*` → `theme.colors.*`
- Shadows, border-radius, spacing → `theme.extend.*`

### 3.3 Migration Order (aligned with component extraction)

1. Install Tailwind + configure theme
2. Global reset + layout (App.tsx skeleton) — replace topbar, layout grid, overlay
3. SessionSidebar — replace `.session-*`, `.history-*` classes
4. ChatMessages + ChatComposer + MentionPanel — replace `.chat-*`, `.composer-*`, `.mention-*`
5. SkillsTab + sub-components — replace `.skills-*`, `.skill-*`
6. WorkflowTab + sub-components — replace `.workflow-*`, `.upload-*`, `.draft-*`, `.exam-*`, `.progress-*`
7. MemoryTab — replace `.memory-*`, `.proposal-*`
8. RoutingPage + ModelCombobox — replace `.routing-*`, `.provider-*`, `.model-combobox-*`
9. SettingsModal — replace `.settings-*`
10. Mobile responsive — convert `@media` queries to Tailwind responsive prefixes (`md:`, `lg:`)
11. Delete `styles.css`

### 3.4 Retained Global Styles

- `tailwind.css`: `@theme` block with design tokens
- Tailwind preflight replaces manual CSS reset
- `@tailwindcss/typography` `.prose` replaces `.text` markdown styles

## Execution Order

The three phases have dependencies:

```
Phase 1 (App.tsx hooks + Context)
  ↓
Phase 2 (TeacherWorkbench component split) — depends on Context from Phase 1
  ↓
Phase 3 (Tailwind migration) — done per-component as Phases 1-2 create new files
```

Recommended: interleave Phase 3 with Phases 1-2. As each component is extracted, immediately convert its styles to Tailwind. This avoids a separate full-pass CSS migration.

## File Count Summary

| Category | New Files | Deleted Files |
|----------|-----------|---------------|
| Hooks | 8 | 0 |
| Context | 1 | 0 |
| Tab components | 3 | 0 |
| Workflow sub-components | 6 | 0 |
| Skills sub-components | 3 | 0 |
| Pure logic | 1 | 0 |
| CSS | 1 (tailwind.css) | 1 (styles.css) |
| **Total** | **23 new** | **1 deleted** |

Net result: 3 oversized files → 23 focused files, each under 300 lines.
