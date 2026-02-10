# Self-Improving Skill System Design

**Date:** 2026-02-10
**Status:** Approved
**Approach:** Observability + Feedback Loop (primary) + Test-Driven Hardening (secondary)

## Problem

The superpowers skill system (v4.2.0) suffers from unreliable triggering:
- Skills are skipped when they should fire
- Skills are invoked but not followed faithfully
- Wrong skills fire for the situation
- Behavior is inconsistent and unpredictable

## Architecture

Three layers forming a continuous improvement cycle:

```
┌─────────────────────────────────────────────┐
│           OBSERVE (Session Hooks)            │
│  session-start hook → skill tracker prompt → │
│  Claude self-reports skill usage to memory   │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│           LEARN (Skill Audit Memory)         │
│  ~/.claude/memory/skill-audit.jsonl          │
│  Accumulates patterns across sessions        │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│           IMPROVE (Two Mechanisms)           │
│  1. skill-improvement skill (manual review)  │
│  2. test harness (automated hardening)       │
│  → Outputs: patched skills in ~/.claude/skills/
└─────────────────────────────────────────────┘
```

**Key design decisions:**
- Personal skills directory (`~/.claude/skills/`) is the output target. Never modify superpowers directly - shadow with improved versions.
- JSONL audit log - machine-readable, appendable, easy to query.
- Human-in-the-loop - system proposes changes, user approves. No auto-patching.
- Hooks do the heavy lifting - session-start hook injects tracking prompt automatically.

## Layer 1: Observability

The session-start hook injects a skill tracker prompt that instructs Claude to self-report skill usage at natural breakpoints.

**Audit log format** (`~/.claude/memory/skill-audit.jsonl`):

```jsonl
{
  "session_id": "abc123",
  "timestamp": "2026-02-10T14:30:00Z",
  "events": [
    {
      "type": "skill_invoked",
      "skill": "systematic-debugging",
      "trigger": "auto_matched",
      "followed": true,
      "drift_notes": null
    },
    {
      "type": "skill_missed",
      "skill": "test-driven-development",
      "evidence": "wrote production code without failing test first",
      "user_context": "implement feature X"
    },
    {
      "type": "wrong_skill",
      "skill_used": "brainstorming",
      "skill_expected": "writing-plans",
      "reason": "user already had a spec, didn't need ideation"
    }
  ],
  "summary": "2 skills invoked correctly, 1 missed (TDD), 1 wrong match"
}
```

## Layer 2: Feedback Loop

A `skill-improvement` personal skill, invoked periodically (e.g., weekly via `/skill-improvement`).

**Process:**
1. Reads `~/.claude/memory/skill-audit.jsonl` and aggregates patterns
2. Identifies top failure modes per skill:
   - Missed most often → trigger/description problem
   - Invoked but not followed → compliance/enforcement problem
   - False triggers → specificity problem
3. Proposes concrete patches as personal skill overrides (diffs)
4. User reviews and approves before deployment

**Output target:** Patched skills in `~/.claude/skills/<skill-name>/SKILL.md` which automatically shadow superpowers versions via skills-core.js.

## Layer 3: Test-Driven Hardening

Scenario-based testing using subagents, driven by audit data.

**Test format** (`~/.claude/skills/tests/<skill>-scenarios.yaml`):

```yaml
skill: test-driven-development
scenarios:
  - name: "simple feature request"
    prompt: "Add a logout button to the navbar"
    expected: skill_invoked
  - name: "pure research question"
    prompt: "How does the auth middleware work?"
    expected: skill_not_invoked
```

**Process:**
1. `test-skills` skill spawns a subagent per scenario
2. Each subagent receives the prompt + full skill system context
3. Response scored: correct skill invoked? Process followed?
4. Results aggregated into pass/fail report

**When to run:** After modifying skills, after improvement proposals, periodically as regression.

## Implementation Phases

### Phase 1: Observability Foundation
- Create `~/.claude/skills/skill-tracker/SKILL.md`
- Add session-start hook snippet for tracking injection
- Create `~/.claude/memory/skill-audit.jsonl`
- **Goal:** Real data after 5-10 sessions

### Phase 2: Skill Improvement Skill
- Create `~/.claude/skills/skill-improvement/SKILL.md`
- Reads audit JSONL, aggregates, proposes patches
- **Goal:** Actionable recommendations on demand

### Phase 3: Test Harness
- Create `~/.claude/skills/tests/` with YAML scenarios
- Create `~/.claude/skills/test-skills/SKILL.md`
- Seed scenarios from Phase 1 audit data
- **Goal:** Validate skill changes before deploying

### Phase 4: Initial Hardening
- Use Phase 1 data + Phase 3 tests to create overrides
- Shadow top 3-5 problem skills with hardened versions
- **Goal:** Measurably improved reliability

### Phase 5: Continuous Loop (ongoing)
- Periodic audit reviews
- Test suite grows with each new failure mode
- Personal skills evolve based on data
