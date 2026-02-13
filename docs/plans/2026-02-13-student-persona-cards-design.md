# Student Persona Cards Design

Date: 2026-02-13  
Scope: Student-side persona cards (style-guided replies) with teacher-managed preset personas, strong safety review, and per-student visibility assignment.

## 1. Confirmed Product Decisions

This design is based on validated decisions:

1. Persona effect level: `B` (influence wording + teaching rhythm), with mild role-play only.
2. Persona authoring: `C` (rules + few-shot examples).
3. Custom-card safety: `A` (strong review before usable).
4. Transparency: first activation shows one-time virtual-style notice (`B`).
5. Student-side picker behavior:
   - Default disabled.
   - User manually opens switch to choose.
   - Picker closes automatically after selection.
6. Preset persona governance:
   - Managed by teacher-side (teacher treated as admin of own persona domain).
   - Teacher decides visibility by student assignment.
   - Student sees all personas assigned to that student.
7. Assignment granularity first release: `A` (precise `student_id` assignment only).

## 2. Goals And Non-Goals

Goals:
1. Provide controllable style personalization without reducing subject correctness.
2. Keep student tutoring constraints dominant over persona behavior.
3. Support mixed persona sources: teacher-assigned preset + student custom (max 5 approved).
4. Deliver auditable, permission-safe runtime behavior.

Non-goals (Phase 1):
1. No broad role simulation or identity substitution.
2. No class-wide or school-wide persona rollout in first iteration.
3. No replacement of current prompt framework; persona remains an additive layer.

## 3. Architecture Overview

Use a "persona style layer" injected through the existing chat extra system path:

1. Frontend sends `persona_id` on `/chat/start`.
2. Backend validates whether current student can use this persona.
3. Persona is transformed into bounded style instructions.
4. Style instructions are appended into `extra_system`.
5. Agent runtime consumes `system prompt + skill prompt + extra_system + messages`.

Priority order is strict and explicit:

1. Safety and platform guardrails.
2. Subject correctness and anti-hallucination constraints.
3. Existing tutoring strategy (progressive guidance).
4. Persona style (wording/rhythm only).

This keeps persona from overriding teaching quality.

## 4. Data Model

### 4.1 Teacher preset personas

New storage (file-backed, consistent with current architecture):

1. `data/teacher_personas/<teacher_id>/personas.json`
2. `data/teacher_personas/<teacher_id>/assets/<persona_id>.<ext>` (avatar)

Persona object:
1. `persona_id`
2. `teacher_id`
3. `name`
4. `summary`
5. `style_rules` (tone/sentence cadence/forbidden style patterns)
6. `few_shot_examples` (3-5 examples)
7. `intensity_cap` (e.g. `low|medium`)
8. `lifecycle_status` (`draft|active|archived`)
9. `visibility_mode` (`assigned_only|hidden_all`)
10. `avatar_url`
11. audit fields (`created_at`, `updated_at`, `updated_by`)

### 4.2 Persona assignment index

To support efficient student-side lookup:

1. `data/persona_assignments/by_student/<student_id>.json`

Assignment record:
1. `assignment_id`
2. `student_id`
3. `teacher_id`
4. `persona_id`
5. `status` (`active|inactive`)
6. `assigned_at`
7. `assigned_by`

### 4.3 Student custom personas

Extend `data/student_profiles/<student_id>.json`:

1. `personas.custom[]`
2. `personas.active_persona_id`
3. `personas.first_activation_notified_ids[]`

Custom persona fields:
1. `persona_id`
2. `name`
3. `style_rules`
4. `few_shot_examples`
5. `avatar_url` (optional)
6. `review_status` (`pending|approved|rejected`)
7. `review_reason`
8. timestamps

Hard server rule: approved custom persona count per student `<= 5`.

## 5. API Design

### 5.1 Student APIs

1. `GET /student/personas`
   - Return: assigned teacher personas + approved custom personas + active persona + switch state hints.
2. `POST /student/personas/custom`
   - Create custom persona in `pending`.
3. `DELETE /student/personas/custom/{persona_id}`
   - Soft delete or hard delete student-owned persona.
4. `POST /student/personas/activate`
   - Set active persona by `persona_id` or clear to none.
5. `POST /student/personas/avatar/upload`
   - Upload image and return safe URL.

### 5.2 Teacher APIs

1. `GET /teacher/personas`
2. `POST /teacher/personas`
3. `PATCH /teacher/personas/{persona_id}`
4. `POST /teacher/personas/{persona_id}/assign`
   - payload includes `student_id`, `status`.
5. `POST /teacher/personas/{persona_id}/visibility`
   - switch between `assigned_only` and `hidden_all`.
6. `POST /teacher/personas/{persona_id}/avatar/upload`

### 5.3 Chat payload extension

Add `persona_id` to `ChatRequest` and `ChatStartRequest`.  
Persist into chat job request payload.

## 6. Runtime Composition Rules

### 6.1 Persona-to-prompt template

Construct bounded persona prompt block:

1. Declare virtual-style scope explicitly.
2. Permit only wording/rhythm expression.
3. Forbid identity claims and factual overrides.
4. Enforce response style cap:
   - max one role-flavored expression per reply.
5. In assignment diagnosis mode:
   - auto downgrade to weak style.

### 6.2 One-time first-use notice

When a student activates a persona first time:
1. include one short notice in assistant response metadata or initial prefix.
2. store persona id in `first_activation_notified_ids`.
3. do not repeat for same student-persona pair.

### 6.3 Deduplication fix

Current chat dedup fingerprint must include `persona_id`, otherwise same user input with different persona can be wrongly debounced.

## 7. Strong Review Pipeline

Custom persona cannot be activated until approved.

Review checks:
1. Content safety (abuse, hate, sexual, self-harm escalation).
2. Prompt-injection patterns (ignore system, reveal prompt, privilege escalation).
3. Identity overreach ("I am the real historical person").
4. Teaching conflict (encouraging direct answer dump when policy requires guided tutoring).
5. Role-play intensity breach (exceeds mild bound).

Review outcome:
1. `approved`: usable.
2. `rejected`: unusable, with `review_reason`.

Teacher-created preset personas should pass the same validator before `active`.

## 8. Frontend UX Design (Student)

Entry point: student topbar persona button.

State model:
1. `personaEnabled` (default false).
2. `activePersonaId`.
3. `personaPickerOpen`.

Interaction:
1. Default no persona.
2. User turns on switch -> picker opens.
3. User selects card -> `activePersonaId` set -> picker closes automatically.
4. Persona remains active until user manually disables.
5. If backend reports persona revoked/not visible:
   - clear active persona.
   - show lightweight toast once.

Card visuals:
1. Avatar image (preset or uploaded custom image).
2. Name and short style summary.
3. Tags (e.g. "清晰", "温和", "启发式").

Image constraints:
1. allow `jpg/png/webp`.
2. reject `svg`.
3. max size 2MB.
4. normalize/resize server-side before persisting.

## 9. Permission And Security

1. Teacher scope isolation:
   - teacher may manage only personas with same `teacher_id`.
2. Student scope isolation:
   - student may activate only assigned teacher personas or own approved customs.
3. Runtime second-check:
   - even if client tampers with `persona_id`, backend revalidates before composing prompt.
4. Visibility kill-switch:
   - `hidden_all` immediately disables exposure and runtime usage.

## 10. Error Handling And Degradation

1. Persona not found / unauthorized:
   - ignore persona and continue chat without style layer, return non-fatal warning code.
2. Persona asset load failure:
   - fallback avatar.
3. Review service temporary failure:
   - keep persona `pending`; do not auto-approve.
4. Assignment revoked during session:
   - next request auto-clears active persona and returns one-time notice.

No persona-related failure should block normal student chat completion.

## 11. Testing And Acceptance

Backend tests:
1. student visibility authorization.
2. custom persona cap (`<=5`) enforcement.
3. review state transition correctness.
4. dedup fingerprint includes `persona_id`.
5. runtime downgrade in diagnosis mode.
6. first-use notice one-time behavior.

Frontend E2E:
1. default disabled state.
2. manual toggle + selection + auto-close picker.
3. active persona persists across reload/session restore.
4. revoked persona auto-clears with user hint.
5. avatar upload success/failure fallback.

Release acceptance:
1. measurable style differentiation with no subject-quality regression.
2. no increase in student chat failure rate.
3. no cross-student or cross-teacher persona leakage.

## 12. Implementation Slices (Recommended)

1. Slice 1: Data models + read APIs + frontend read-only picker.
2. Slice 2: Activation + chat payload + runtime prompt injection + dedup fix.
3. Slice 3: custom persona creation + strong review + cap enforcement.
4. Slice 4: teacher persona CRUD + precise student assignment.
5. Slice 5: avatar upload + image pipeline + full E2E hardening.

This phased delivery keeps risk low and validates core behavior early.
