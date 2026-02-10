# Self-Improving Skill System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-improving skill system that observes skill usage, learns from failures, and hardens skills through testing.

**Architecture:** Three-layer observe/learn/improve cycle using personal skills (`~/.codex/skills/`) that shadow superpowers. Session hooks inject tracking. JSONL audit log accumulates data. Improvement skill proposes patches. Test harness validates changes.

**Tech Stack:** Bash (hooks), Markdown (skills), YAML (test scenarios), JSONL (audit log)

---

## Prerequisites

The personal skills directory (`~/.codex/skills/`) does not yet exist. All skills will be created there. The superpowers plugin (v4.2.0) is installed and active.

---

### Task 1: Create Personal Skills Directory Structure

**Files:**
- Create: `~/.codex/skills/` (directory)
- Create: `~/.codex/skills/skill-tracker/` (directory)
- Create: `~/.codex/skills/skill-improvement/` (directory)
- Create: `~/.codex/skills/test-skills/` (directory)
- Create: `~/.codex/skills/tests/` (directory)

**Step 1: Create all directories**

Run:
```bash
mkdir -p ~/.codex/skills/skill-tracker \
         ~/.codex/skills/skill-improvement \
         ~/.codex/skills/test-skills \
         ~/.codex/skills/tests
```

**Step 2: Initialize empty audit log**

Run:
```bash
touch ~/.codex/memory/skill-audit.jsonl
```

**Step 3: Verify structure**

Run:
```bash
find ~/.codex/skills -type d && ls ~/.codex/memory/skill-audit.jsonl
```
Expected: All 4 directories listed + audit file exists.

**Step 4: Commit**

```bash
# Nothing to commit - these are outside the repo
```

---

### Task 2: Create the Skill Tracker Skill (RED phase)

This skill instructs Claude to self-report skill usage during sessions.

**Files:**
- Create: `~/.codex/skills/skill-tracker/SKILL.md`

**Step 1: Run baseline scenario WITHOUT the skill**

Spawn a subagent with this prompt to see what Claude does naturally:

```
You are working on a physics education platform. The user asks:
"Fix the bug where student scores aren't saved after exam submission"

You have access to these superpowers skills: systematic-debugging,
test-driven-development, verification-before-completion.

Work through the task. At the end, report which skills you used,
which you skipped, and why.
```

Document: Does the agent naturally track and report skill usage? (Expected: No systematic tracking)

**Step 2: Write the skill-tracker SKILL.md**

Create `~/.codex/skills/skill-tracker/SKILL.md` with this content:

```markdown
---
name: skill-tracker
description: Use at the end of every task or before committing - records which skills were used, missed, or partially followed during this session for continuous improvement
---

# Skill Usage Tracker

## Overview

Track skill invocations during this session to build an audit trail for continuous improvement. This is the observability layer of the self-improving skill system.

**Announce at start:** "Recording skill usage for this session."

## When to Record

Record a skill usage entry at these natural breakpoints:
- Before each git commit
- After completing a major task
- When switching between different types of work
- At the end of a session

## What to Record

For each breakpoint, append a JSON line to `~/.codex/memory/skill-audit.jsonl`:

```json
{"timestamp":"ISO-8601","task":"brief description","events":[{"type":"skill_invoked|skill_missed|wrong_skill|skill_drift","skill":"name","details":"specifics"}],"summary":"one line"}
```

### Event Types

| Type | When | Details to capture |
|------|------|--------------------|
| `skill_invoked` | Skill was used correctly | trigger type, followed faithfully? |
| `skill_missed` | Should have used skill but didn't | evidence of what happened instead |
| `wrong_skill` | Used wrong skill for situation | which skill should have been used |
| `skill_drift` | Used skill but didn't follow it | which steps were skipped/modified |

## How to Record

Use the Bash tool to append to the audit log:

```bash
echo '{"timestamp":"2026-02-10T14:30:00Z","task":"fix score saving bug","events":[{"type":"skill_invoked","skill":"systematic-debugging","details":"followed all 4 phases"},{"type":"skill_missed","skill":"test-driven-development","details":"wrote fix before failing test"}],"summary":"1 correct, 1 missed"}' >> ~/.codex/memory/skill-audit.jsonl
```

## Self-Check Questions

Before recording, ask yourself:
1. Did I invoke every skill that applied? (Check the skill list)
2. For each skill I invoked, did I follow it completely?
3. Did I skip any steps or take shortcuts?
4. Was there a moment I rationalized not using a skill?

## Red Flags

- "I don't need to track this session" → Track it anyway
- "Nothing interesting happened" → Misses are interesting
- "I'll remember for next time" → Memory is unreliable. Log it.
- "This is overhead" → 30 seconds of logging saves hours of debugging skills
```

**Step 3: Run baseline scenario WITH the skill**

Spawn same subagent but include the skill-tracker content. Verify the agent now produces a structured audit entry at the end.

**Step 4: Refactor if needed**

If the agent doesn't produce a proper JSONL entry, strengthen the instructions. Common issues:
- Agent summarizes instead of writing JSONL → Add "MUST use exact JSON format"
- Agent forgets to append to file → Add "MUST use Bash tool to append"

---

### Task 3: Create Session Hook for Tracking Reminder

**Files:**
- Create: `~/.codex/hooks.json` (or update if exists)

**Step 1: Understand hook format**

The superpowers plugin uses `hooks.json` with this structure:
```json
{
  "hooks": {
    "SessionStart": [{ "matcher": "...", "hooks": [{ "type": "command", "command": "...", "async": true }] }]
  }
}
```

Personal hooks go in `~/.codex/hooks.json`.

**Step 2: Create the hooks file**

Create `~/.codex/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "if echo \"$TOOL_INPUT\" | grep -q 'git commit'; then echo '{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"REMINDER: Use skill-tracker to record skill usage before this commit. Append to ~/.codex/memory/skill-audit.jsonl\"}}'; fi",
            "async": true
          }
        ]
      }
    ]
  }
}
```

**Step 3: Verify hook triggers**

Run a test git commit in the worktree and verify the reminder appears.

**Step 4: Commit design docs**

```bash
cd "/Users/lvxiaoer/Documents/New project/.worktrees/self-improving-skills"
git add docs/plans/2026-02-10-self-improving-skill-system-design.md \
        docs/plans/2026-02-10-self-improving-skill-system-plan.md
git commit -m "docs: add self-improving skill system design and plan"
```

---

### Task 4: Create the Skill Improvement Skill (RED phase)

**Files:**
- Create: `~/.codex/skills/skill-improvement/SKILL.md`

**Step 1: Seed audit log with sample data**

Append 3-5 sample entries to `~/.codex/memory/skill-audit.jsonl` representing realistic sessions with various failure modes.

**Step 2: Run baseline scenario WITHOUT the skill**

Spawn a subagent:
```
Read ~/.codex/memory/skill-audit.jsonl. Analyze the skill usage patterns
and suggest improvements to the skill system.
```

Document: Does the agent produce actionable, structured recommendations? (Expected: vague, unstructured advice)

**Step 3: Write the skill-improvement SKILL.md**

Create `~/.codex/skills/skill-improvement/SKILL.md`:

```markdown
---
name: skill-improvement
description: Use periodically (weekly or biweekly) to analyze skill audit data and propose concrete improvements to skills that are failing, being skipped, or triggering incorrectly
---

# Skill Improvement

## Overview

Analyze accumulated skill audit data and propose concrete, testable improvements to underperforming skills. This is the feedback loop of the self-improving skill system.

**Announce at start:** "Analyzing skill audit data to propose improvements."

## Process

### Step 1: Read Audit Data

```bash
cat ~/.codex/memory/skill-audit.jsonl
```

### Step 2: Aggregate by Failure Mode

Count events across all sessions and categorize:

| Category | Meaning | Fix Type |
|----------|---------|----------|
| **Missed** (skill_missed) | Skill should have fired but didn't | Improve description/triggers |
| **Drift** (skill_drift) | Skill fired but wasn't followed | Strengthen enforcement language |
| **Wrong** (wrong_skill) | Wrong skill matched | Narrow description, add exclusions |
| **Low usage** | Skill rarely invoked | Check if description is discoverable |

### Step 3: Rank by Impact

Sort skills by total failure count. Focus on top 3-5.

### Step 4: Propose Patches

For each problem skill, output a concrete proposal:

```markdown
## Proposed Fix: [skill-name]

**Problem:** [category] - [count] occurrences in [N] sessions
**Pattern:** [what triggers the failure]
**Current description:** [quote current]
**Proposed description:** [new version]
**Additional changes:** [enforcement language, red flags, etc.]
**Test scenario:** [how to verify the fix works]
```

### Step 5: Create Shadow Skills

For approved proposals, create personal skill overrides:

```bash
mkdir -p ~/.codex/skills/[skill-name]
# Write patched SKILL.md that shadows the superpowers version
```

## Output Format

Always produce:
1. **Summary table** of all skills with failure counts
2. **Top 3-5 proposals** with concrete diffs
3. **Test scenarios** for each proposal
4. **Next review date** suggestion

## Red Flags

- "No issues found" → Review audit data more carefully. There are always patterns.
- "All skills are fine" → Check for missing data. Are sessions being tracked?
- "Too little data" → Suggest collecting more before next review.
```

**Step 4: Run scenario WITH the skill**

Spawn subagent with the skill content + sample audit data. Verify it produces structured proposals.

**Step 5: Refactor if needed**

Strengthen any weak areas based on test results.

---

### Task 5: Create Test Scenario Files

**Files:**
- Create: `~/.codex/skills/tests/tdd-scenarios.yaml`
- Create: `~/.codex/skills/tests/debugging-scenarios.yaml`
- Create: `~/.codex/skills/tests/brainstorming-scenarios.yaml`

**Step 1: Write TDD trigger scenarios**

Create `~/.codex/skills/tests/tdd-scenarios.yaml`:

```yaml
skill: test-driven-development
scenarios:
  - name: "feature request - should trigger"
    prompt: "Add a logout button to the student dashboard navbar"
    expected: skill_invoked

  - name: "bug fix - should trigger"
    prompt: "Fix the bug where exam scores show as NaN for some students"
    expected: skill_invoked

  - name: "refactor request - should trigger"
    prompt: "Refactor the exam upload service to use async/await"
    expected: skill_invoked

  - name: "research question - should NOT trigger"
    prompt: "How does the LLM routing system decide which model to use?"
    expected: skill_not_invoked

  - name: "config change - should NOT trigger"
    prompt: "Update the API timeout from 30s to 60s in the config"
    expected: skill_not_invoked
```

**Step 2: Write debugging trigger scenarios**

Create `~/.codex/skills/tests/debugging-scenarios.yaml`:

```yaml
skill: systematic-debugging
scenarios:
  - name: "error report - should trigger"
    prompt: "Students are getting 500 errors when submitting exams"
    expected: skill_invoked

  - name: "test failure - should trigger"
    prompt: "test_exam_upload_flow is failing with AssertionError"
    expected: skill_invoked

  - name: "new feature - should NOT trigger"
    prompt: "Add a progress bar to the exam upload page"
    expected: skill_not_invoked

  - name: "performance issue - should trigger"
    prompt: "The teacher dashboard takes 15 seconds to load"
    expected: skill_invoked
```

**Step 3: Write brainstorming trigger scenarios**

Create `~/.codex/skills/tests/brainstorming-scenarios.yaml`:

```yaml
skill: brainstorming
scenarios:
  - name: "vague idea - should trigger"
    prompt: "I want to add some kind of analytics to the platform"
    expected: skill_invoked

  - name: "clear spec - should NOT trigger"
    prompt: "Add a GET /api/scores endpoint that returns JSON array of {student_id, score, exam_id}"
    expected: skill_not_invoked

  - name: "exploration - should trigger"
    prompt: "How could we make the exam experience better for students?"
    expected: skill_invoked

  - name: "specific bug - should NOT trigger"
    prompt: "The login form crashes when email field is empty"
    expected: skill_not_invoked
```

---

### Task 6: Create the Test Skills Skill

**Files:**
- Create: `~/.codex/skills/test-skills/SKILL.md`

**Step 1: Run baseline - test without the skill**

Spawn a subagent:
```
Read the YAML files in ~/.codex/skills/tests/. Run each scenario
by spawning a subagent and checking if the expected skill was invoked.
Report results.
```

Document: Does the agent know how to structure the test run? (Expected: ad-hoc, inconsistent)

**Step 2: Write the test-skills SKILL.md**

Create `~/.codex/skills/test-skills/SKILL.md`:

```markdown
---
name: test-skills
description: Use after creating or modifying any skill to validate it triggers correctly and resists rationalization - runs scenario-based tests with subagents
---

# Test Skills

## Overview

Run scenario-based tests against skills using subagents. Each scenario checks whether a skill correctly triggers (or doesn't trigger) for a given prompt.

**Announce at start:** "Running skill test suite."

## Process

### Step 1: Load Scenarios

```bash
ls ~/.codex/skills/tests/*.yaml
```

Read each YAML file. Each contains a `skill` name and list of `scenarios`.

### Step 2: Run Each Scenario

For each scenario, spawn a Task subagent with this prompt template:

```
You have access to the superpowers skill system. The following skills
are available: [list all skill descriptions from system prompt].

A user sends you this message:
"[scenario prompt]"

Respond as you normally would. At the end of your response, add a
section called "## Skills Used" listing which skills you invoked
(if any) and why.
```

### Step 3: Score Results

For each scenario:
- If `expected: skill_invoked` → Check "Skills Used" section contains the target skill
- If `expected: skill_not_invoked` → Check "Skills Used" section does NOT contain the target skill

### Step 4: Report

Output a results table:

```markdown
## Test Results: [skill-name]

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| feature request | invoked | invoked | PASS |
| research question | not_invoked | invoked | FAIL |

**Pass rate:** 4/5 (80%)
**Failures:** [details of each failure]
**Recommendations:** [what to fix in the skill]
```

### Step 5: Save Results

Append results to `~/.codex/memory/skill-test-results.jsonl`:

```bash
echo '{"timestamp":"...","skill":"...","pass_rate":"4/5","failures":[...]}' >> ~/.codex/memory/skill-test-results.jsonl
```

## Red Flags

- "Tests all pass" on first run → Scenarios may be too easy. Add harder cases.
- "Can't test this skill" → Every skill can be tested. Adjust scenario format.
- "Testing is overkill for this change" → Small changes cause big regressions. Test anyway.
```

**Step 3: Run scenario WITH the skill**

Verify the agent follows the structured test process.

**Step 4: Refactor if needed**

---

### Task 7: End-to-End Validation

**Step 1: Verify skill-tracker works**

Start a new Claude session. Work on a small task. Verify that:
- The skill-tracker skill is discoverable
- It produces a valid JSONL entry when invoked
- The entry is appended to `~/.codex/memory/skill-audit.jsonl`

**Step 2: Verify skill-improvement works**

After accumulating 3+ audit entries, invoke the skill-improvement skill. Verify:
- It reads the audit log
- It produces structured proposals
- Proposals include concrete diffs and test scenarios

**Step 3: Verify test-skills works**

Invoke the test-skills skill. Verify:
- It finds and reads YAML scenario files
- It spawns subagents for each scenario
- It produces a pass/fail report
- Results are saved to `~/.codex/memory/skill-test-results.jsonl`

**Step 4: Commit all work**

```bash
cd "/Users/lvxiaoer/Documents/New project/.worktrees/self-improving-skills"
git add -A
git commit -m "feat: add self-improving skill system (Phase 1-3)"
```

---

## Summary of Deliverables

| File | Purpose |
|------|---------|
| `~/.codex/skills/skill-tracker/SKILL.md` | Observability - tracks skill usage per session |
| `~/.codex/skills/skill-improvement/SKILL.md` | Feedback loop - analyzes audit data, proposes fixes |
| `~/.codex/skills/test-skills/SKILL.md` | Test harness - validates skills with scenarios |
| `~/.codex/skills/tests/*.yaml` | Test scenarios for TDD, debugging, brainstorming |
| `~/.codex/hooks.json` | Hook to remind about tracking before commits |
| `~/.codex/memory/skill-audit.jsonl` | Persistent audit log |
| `docs/plans/2026-02-10-self-improving-skill-system-design.md` | Design document |
| `docs/plans/2026-02-10-self-improving-skill-system-plan.md` | This plan |
