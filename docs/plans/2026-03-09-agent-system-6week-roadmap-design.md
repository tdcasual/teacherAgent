# Agent System 6-Week Governance-First Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 6 周内把当前 `teacherAgent` 的 agent / workflow / analysis runtime 收口为更稳定、可追溯、可回放、可观测、可扩域的受控控制平面，同时继续坚持“教学 workflow 产品”而不是开放式多 agent 平台的产品边界。

**Architecture:** 保持 `Coordinator` 为唯一默认前台 agent，继续沿用统一 analysis plane：`target resolver -> artifact adapter -> strategy selector -> specialist runtime -> analysis report / review queue`。执行顺序采用治理优先：`P0` 先补装配真相、版本 lineage、失败治理；`P1` 再把 review / replay / selector 变成质量闭环；`P2` 最后补运营化、发布门禁与新域接入工业化能力。

**Tech Stack:** Python 3.13、FastAPI、Pydantic v2、pytest、现有 `services/api` runtime / domain / review queue / metrics 结构、`docs/reference` 契约文档、`docs/operations` 运维文档、React teacher workbench。

---

## Validation Snapshot

本路线图基于 2026-03-09 的设计收敛结论：

- 路线尺度选择为“`6周演进版`”；
- 组织方式选择为“`治理优先型`”；
- 分阶段节奏确认为：`P0 收口 -> P1 闭环 -> P2 运营化`；
- 优先目标不是增加更多 agent，而是把现有 `Coordinator + specialist runtime + analysis plane` 做成真正稳定的受控系统。

这份文档是**经讨论确认后的路线图摘要**；更细的任务级实现清单可直接复用：

- `docs/plans/2026-03-08-agent-design-p0-p2-roadmap.md`
- `docs/plans/2026-03-07-agent-system-priority-optimization-plan.md`
- `docs/plans/2026-03-08-agent-design-review-and-optimization-design.md`

---

## Why This Route

选择治理优先，而不是扩域优先或平台化优先，原因如下：

1. 当前系统的核心价值已经不是“能不能做多 agent”，而是“是否能把教学分析能力稳定、安全、可解释地交付给老师”。
2. 项目已经具备统一 analysis plane、manifest-driven runtime builder、specialist governor、report plane 和 review queue 的基础骨架；此时继续扩域，容易把当前残留的手工 glue 与弱运营闭环一起复制出去。
3. 当前最需要补强的是：装配真相来源、lineage 稳定传播、fail-closed 行为、feedback 数据闭环、发布门禁，而不是更复杂的 agent autonomy。

因此，本路线图把“治理深度、追溯能力、运营纪律”放在“新增能力种类”之前。

---

## Non-Goals

以下内容明确不在本 6 周范围内：

- 不把系统演进成开放式 agent marketplace；
- 不引入自由 agent-to-agent mesh 或开放协商式多 agent 会话；
- 不以新增大量 domain 为主要成功指标；
- 不重写现有 teacher / student / admin 主链路；
- 不为了“平台漂亮”而重做整个运行时。

---

## Roadmap Overview

### P0 — 稳定化与收口（第 1-2 周）

**目标：** 把当前控制面从“方向正确、可运行”收敛成“新增 domain 成本更低、报告可追溯、失败路径可控”的状态。

**核心工作流：**

- 去手工化装配，继续让 manifest 成为 runtime / report 装配真相源；
- 把 lineage 从“字段存在”升级为“write/read/rerun/replay 强约束”；
- 统一 specialist failure reason code、review 降级和 fail-closed 语义。

**关键代码面：**

- `services/api/domains/manifest_registry.py`
- `services/api/domains/runtime_builder.py`
- `services/api/analysis_report_service.py`
- `services/api/strategies/planner.py`
- `services/api/specialist_agents/governor.py`
- `services/api/review_queue_service.py`

**阶段成功信号：**

- 新增一个 analysis domain 时，不再需要修改多处核心 lookup；
- report 的 `list/detail/rerun/replay` 都能稳定携带 lineage；
- `invalid_output`、`timeout`、`budget_exceeded`、`low_confidence_review` 都有稳定降级行为和审计事件。

### P1 — 质量闭环（第 3-4 周）

**目标：** 让系统不仅“能运行”，还能被比较、被验证、被纠偏。

**核心工作流：**

- 把 review queue 从人工兜底面升级为质量反馈数据入口；
- 把 replay / compare 接到真实 report lineage 上，形成回归验证通路；
- 让 selector 支持受控的 shadow compare、灰度阈值与 cohort 级实验。

**关键代码面：**

- `services/api/review_queue_service.py`
- `services/api/review_feedback_service.py`
- `services/api/analysis_report_service.py`
- `services/api/strategies/selector.py`
- `services/api/strategies/planner.py`
- `scripts/replay_analysis_run.py`

**阶段成功信号：**

- review 结果可沉淀为结构化 feedback dataset；
- 至少一个 domain 能跑通 replay compare / shadow validate；
- 每次 strategy / prompt / threshold 调整都能看到版本差异证据，而不是只靠主观样例判断。

### P2 — 运营化与扩域工业化（第 5-6 周）

**目标：** 把控制平面变成团队可持续上线、回滚和扩域的工程体系。

**核心工作流：**

- 把 runtime event、review downgrade、strategy hit、rerun 行为汇总成统一 operations surface；
- 固化发布门禁、lineage 核验、shadow 检查和回滚动作；
- 把 domain onboarding 的最低接入要求模板化。

**关键代码 / 文档面：**

- `services/api/analysis_metrics_service.py`
- `services/api/domains/runtime_builder.py`
- `services/api/specialist_agents/governor.py`
- `docs/operations/multi-domain-analysis-rollout-checklist.md`
- `docs/reference/analysis-domain-onboarding-template.md`
- `docs/reference/analysis-domain-checklist.md`

**阶段成功信号：**

- 关键 runtime 信号可统计、可导出、可告警；
- 每次 domain / strategy 上线都有标准门禁和回滚路径；
- 新域接入时可复用统一模板，而不是重新发明流程。

---

## Weekly Milestones

### Week 1

- 收敛 manifest / runtime / report 的装配边界；
- 识别并减少中央 lookup / glue 改动点；
- 为装配真相源和 fail-fast 行为补测试。

### Week 2

- 稳定 lineage 在 planner、report writer、report reader、rerun、replay 中的传播；
- 统一 failure code 与 review downgrade 行为；
- 完成 P0 验收。

### Week 3

- 把 review queue 的处理结果转成结构化反馈样本；
- 引入 domain / strategy / reason_code / confidence bucket 维度汇总；
- 建立质量观察基础报表。

### Week 4

- 打通至少一个 domain 的 replay compare / shadow validate；
- 为 selector 增加受控实验能力；
- 让策略变更具备基本版本对比证据。

### Week 5

- 汇总 specialist runtime、review queue、strategy selector 的关键运营指标；
- 补齐告警、降级开关和运行手册；
- 把发布前核验动作前置到 checklist。

### Week 6

- 固化 domain onboarding 模板与验收标准；
- 完成 release / rollback / replay / compare 文档联动；
- 形成下一轮扩域或提质工作的统一入口。

---

## Priority Order

建议严格按以下优先级执行，避免“看起来重要”的平台化工作挤占真正的风险收口项：

1. `P0-1` 去手工化 runtime / report 装配
2. `P0-2` 稳定 lineage 写入、读取、rerun、replay
3. `P0-3` 统一失败分类、降级治理与 fail-closed
4. `P1-1` review queue 反馈数据化
5. `P1-2` replay compare / shadow validate
6. `P1-3` selector 灰度阈值与策略实验
7. `P2-1` metrics / dashboard / alert 收口
8. `P2-2` 发布门禁与回滚流程固化
9. `P2-3` domain onboarding 模板化

---

## Success Metrics

6 周结束时，至少应满足以下结果：

- `新增 domain 变更面下降`：新增 domain 时，核心 wiring 改动文件数明显减少；
- `lineage 可追溯`：report list/detail/rerun/replay 均能读取稳定 lineage；
- `异常更可控`：specialist runtime 失败有统一 reason code、审计事件和降级策略；
- `质量可比较`：至少一个 domain 支持 replay compare / shadow validate；
- `发布更稳`：存在明确上线门禁、回滚路径与 release checklist；
- `接入更工业化`：新域接入拥有统一模板、fixture、验收清单。

---

## Risks And Mitigations

### 风险 1：过早把重点转向新增 domain

**影响：** 把当前半手工 glue 和弱治理路径复制到更多域中，后续收口成本更高。

**缓解：** 在 P0 完成前，不把“扩域数量”作为主要里程碑；所有新域需求默认走统一 plane 复用清单评审。

### 风险 2：lineage 字段“存在但不可信”

**影响：** replay / compare 失真，回归分析无法作为发布依据。

**缓解：** 对 lineage 缺失或不一致路径采用 fail-fast；把 lineage 校验写入 rerun / replay / rollout checklist。

### 风险 3：review queue 只停留在人工兜底

**影响：** 无法形成数据闭环，selector / prompt / strategy 调整仍然靠经验拍板。

**缓解：** 在 P1 明确把 review disposition、reason_code、operator note 转为结构化反馈样本。

### 风险 4：运营化只做“日志更多”而非“动作更稳”

**影响：** 指标增加但定位、回滚、发布门禁没有真正改善。

**缓解：** 所有新指标都要绑定一个操作动作：告警、降级、回滚、shadow 验证或放量门禁。

---

## Execution Notes

- 任务级实施应优先复用 `docs/plans/2026-03-08-agent-design-p0-p2-roadmap.md` 的详细分解；
- 若进入编码阶段，建议先用 worktree 隔离，再用 `executing-plans` 或 `subagent-driven-development` 按 task 执行；
- 本路线图的价值在于**统一顺序与成功标准**，避免团队在 P0 未收口前被新需求牵引到错误优先级。

