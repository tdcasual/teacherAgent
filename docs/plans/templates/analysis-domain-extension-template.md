# Analysis Domain Extension Plan Template

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 `<domain_id>` 接入统一 analysis plane，并满足 onboarding contract、replay、review、rollout 与 rollback 最低要求。

**Architecture:** 复用 manifest-driven assembly、统一 report plane、review queue、replay compare 与 capability matrix，不为单个 domain 新造私有读路径或私有治理面。

**Tech Stack:** Python 3.13、FastAPI、pytest、manifest/binding registry、analysis runtime contract、teacher workbench analysis plane。

---

## Contract Inputs

开始前先补齐并粘贴：

- Contract: `docs/reference/analysis-domain-onboarding-contract.md`
- Domain checklist: `docs/reference/analysis-domain-checklist.md`
- Capability matrix: `docs/reference/analysis-domain-capability-matrix.md`
- Rollout checklist: `docs/operations/multi-domain-analysis-rollout-checklist.md`

## Task 1: Register domain manifest and bindings

**Files:**
- Modify: `services/api/domains/manifest_registry.py`
- Modify: `services/api/domains/binding_registry.py`
- Test: `tests/test_analysis_domain_contract_checker.py`

**Steps:**
1. Write failing tests for manifest / binding / runtime / report registration.
2. Run the focused tests and confirm failure.
3. Add the minimal manifest and binding entries.
4. Re-run tests and confirm pass.

## Task 2: Implement artifact, strategy, and specialist contract

**Files:**
- Modify/Create: domain-specific adapter / strategy / specialist files
- Test: domain-specific targeted tests
- Doc: `docs/reference/analysis-runtime-contract.md`

**Steps:**
1. Write failing tests for artifact shape, strategy selection, and typed specialist output.
2. Run focused tests and confirm failure.
3. Implement minimal artifact / strategy / specialist code.
4. Re-run tests and confirm pass.

## Task 3: Connect report plane, review queue, and replay

**Files:**
- Modify: report provider / review queue integration files
- Test: `tests/test_analysis_report_service.py`
- Test: `tests/test_replay_analysis_run.py`

**Steps:**
1. Write failing tests for unified list/detail/rerun/replay support.
2. Run focused tests and confirm failure.
3. Implement report plane and replay support.
4. Re-run tests and confirm pass.

## Task 4: Add fixtures, eval, rollout docs, and final regression

**Files:**
- Modify/Create: `tests/fixtures/...`
- Modify: `docs/reference/analysis-domain-onboarding-template.md`
- Modify: `docs/reference/analysis-domain-checklist.md`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Steps:**
1. Add minimal happy path + edge fixtures.
2. Add or extend eval coverage.
3. Document rollout / rollback path.
4. Run contract check, replay compare, focused regression, and rollout doc guard tests.

## Acceptance Checklist

- [ ] onboarding contract 全项满足
- [ ] capability matrix 已更新
- [ ] replay / compare 可运行
- [ ] review queue reason code 完整
- [ ] rollout / rollback 路径已记录
