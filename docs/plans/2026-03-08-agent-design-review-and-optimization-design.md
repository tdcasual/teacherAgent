# Agent Design Review and Optimization Design

Date: 2026-03-08
Scope: `teacherAgent` 当前 agent / workflow / analysis runtime 设计评审与优化建议
Status: Drafted from validated architecture review

## 1. Executive Summary

当前项目的 agent 设计已经明显脱离“通用 Agent 平台”思路，而是收敛为一个面向教学 workflow 的受控执行系统。这个方向是正确的，也是项目最近一轮演进最有价值的部分。

核心判断如下：

- 产品定位清晰：系统明确服务于老师、学生、管理员三类角色的高频教学动作，而不是开放式插件市场或任意 agent 运行平台。
- 前台交互克制：`Coordinator` 仍然是唯一默认前台 agent，specialist agent 仅通过内部 handoff 执行，避免了用户心智和运维复杂度失控。
- 分析能力平台化方向正确：最近改动已经把 `survey` 的单域流程推进为统一 analysis plane，即 `target resolver -> artifact adapter -> strategy selector -> specialist runtime -> analysis report / review queue`。
- 系统可解释性增强：从 workflow 解析、review queue 降级，到统一 report plane，这套设计已经具备“为什么这样路由、为什么结果没直接给老师看、为什么要人工 review”的解释基础。

综合评分：**8.4 / 10**。

这不是一个“功能未成形”的 agent 设计，而是一个**方向正确、骨架已经搭起，但治理深度与运维闭环仍需继续补强**的系统。

## 2. Review Basis

本评审主要基于以下项目事实：

- 产品定位与运行时主链路定义：`README.md`
- 老师端总运行时契约：`docs/reference/agent-runtime-contract.md`
- 多域分析运行时契约：`docs/reference/analysis-runtime-contract.md`
- 最近优化计划与落地范围：`docs/plans/2026-03-07-agent-system-priority-optimization-plan.md`
- 最近上线说明与提交：`d727fcd`、`0b2e8e4`
- 关键后端实现：
  - `services/api/domains/manifest_registry.py`
  - `services/api/wiring/survey_wiring.py`
  - `services/api/specialist_agents/governor.py`
  - `services/api/analysis_target_resolution_service.py`
  - `services/api/analysis_report_service.py`
  - `services/api/review_queue_service.py`
- 关键前端接入：
  - `frontend/apps/teacher/src/features/workbench/hooks/useAnalysisReports.ts`

因此，本结论既不是抽象架构偏好，也不是只看文档不看代码的纸面判断，而是基于最近已实际落地的系统状态。

## 3. Overall Score

### 3.1 Score Breakdown

| Dimension | Score | Judgment |
| --- | --- | --- |
| 产品边界与定位 | 9.5 / 10 | 极清晰，且最近改动没有偏离产品主线 |
| 可扩展性 | 8.5 / 10 | 已具备多域扩展骨架，但装配仍有部分手工化 |
| 运行时治理 | 7.4 / 10 | 已有 governor / review queue / kill-switch 思路，但治理深度仍不足 |
| 产品落地度 | 8.8 / 10 | 后端统一平面已经真正接到老师工作台 |
| 可追溯性与可回放性 | 7.0 / 10 | 仍缺少版本戳与 replay 闭环 |
| 可观测性与运营化 | 7.2 / 10 | 已有 event 和日志入口，但尚未成为统一 operations surface |

### 3.2 Final Score

**综合评分：8.4 / 10**

建议将当前系统判断为：

> 一个已经完成第一阶段平台抽象的、面向教学 workflow 的受控 agent control plane，
> 目前最需要的不是“更多 agent”，而是“更强治理、更强追溯、更强运营闭环”。

## 4. What Is Already Strong

### 4.1 The project refuses the wrong abstraction

这是目前最重要的优点：项目没有把自己包装成开放式多 agent 平台，而是清楚地把 agent 能力限制在教学 workflow 产品之内。

其价值在于：

- 避免用户心智从“一个教学助手”裂变成“若干个会抢控制权的机器人”；
- 避免工程团队过早投资开放 agent marketplace、agent-to-agent conversation mesh 等高复杂度但低确定性方向；
- 让系统演进围绕“教学闭环的正确性、可解释性、可运维性”展开，而不是围绕炫技的 agent autonomy 展开。

这套选择在 `README.md` 和运行时契约中非常一致，没有出现文档说克制、代码却偷偷平台化的分裂。

### 4.2 Single front-facing coordinator is the correct product choice

`Coordinator` 仍然是唯一默认前台 agent，这是一个高质量的产品与架构决策。

优势包括：

- 老师端只有一个统一入口，避免角色错乱；
- specialist agent 成为内部认知执行单元，而不是用户直接操作对象；
- 降低 prompt 竞争、会话控制权切换、memory 污染和审计成本；
- 对新域扩展更友好，因为新增 domain 不需要改变前台交互模型。

这意味着项目当前的“多 agent”本质上是**受控 specialist runtime**，而不是开放协商式 agent society。这个边界应该继续保持。

### 4.3 Multi-domain analysis plane is the right evolution path

最近最大的进展，是从 survey-only 的特殊链路推进到了统一 analysis plane。

这条链路：

`target resolver -> artifact adapter -> strategy selector -> specialist runtime -> analysis report / review queue`

有三个关键价值：

1. 把“分析对象是什么”显式化，不再依赖“猜最近一个 report”；
2. 把输入归一化为 artifact，让不同 domain 复用同样的下游治理平面；
3. 把最终老师读取层统一为 report plane，而不是每个域一套私有读取模型。

这使得 `survey`、`class_report`、`video_homework` 之间出现了真正的平台共性，而不是复制三份近似但不兼容的流程。

### 4.4 Specialist output is intentionally constrained

specialist prompt 与代码实现都体现出较强的结构化输出约束：

- 只允许分析 artifact；
- 输出严格 JSON；
- 禁止学生级画像、自动动作脚本等越权结论；
- 必须给出证据引用、置信度与信息缺口；
- 有 fallback artifact 作为兜底。

这比“让模型自由回答，再从文本里摘结论”的设计可靠得多，也更适合教学场景的责任边界。

### 4.5 Report plane and review queue are no longer survey-only

统一 analysis report plane 和统一 review queue 的引入，说明系统已经开始具备“平台控制面”的形态，而不是把 survey 逻辑硬扩展到其它 domain。

尤其值得肯定的是：

- report plane 已经是老师端可见的统一读取面；
- review queue 不再只是 survey 的异常补丁，而成为跨域降级机制；
- rerun / review 这些动作开始具备可运营性。

这为后续的发布治理、人工复核、质量追踪提供了正确承载点。

## 5. Main Weaknesses and Risks

### 5.1 Manifest-driven metadata exists, but runtime assembly is not fully generalized

虽然已经引入 `DomainManifestRegistry`，方向正确，但当前更多还是“元数据集中定义”，尚未完全变成“装配方式也由统一机制驱动”。

目前的问题是：

- 各 domain 的 specialist registry / runtime 仍然需要在 `services/api/wiring/survey_wiring.py` 中分别手写；
- runner 的 constraint 解包逻辑仍然按域散落；
- 新增 domain 时，仍需复制一段 glue code，而不是主要填写 manifest 并挂载一个标准 runner factory。

风险在于：

- 随着 domain 增多，wiring 层再次膨胀；
- manifest 与 wiring 之间可能出现双重真相；
- 新域接入成本虽然下降，但还没有下降到“主要是声明式扩展”的水平。

### 5.2 Runtime governor is useful, but not yet a strong execution governor

当前 governor 已经能做预算校验、事件记录、异常净化和基本输出校验，这比直接裸跑 specialist 强很多。

但它仍有几个明显不足：

- timeout 目前是执行后比对 elapsed time，不是强约束；
- `max_steps` 仍停留在 contract 字段层，没有真实步骤级执行治理；
- `output_schema` 校验仍比较浅，只要结果是非空 dict 就可能通过；
- 没有把 domain / strategy / prompt version 等上下文注入到统一执行审计里。

这意味着当前 governor 更像“轻治理包装层”，还不是“强治理运行时”。

### 5.3 Analysis reports are unified, but still not version-traceable enough

统一 report plane 已经建立，但当前 report model 仍缺少对以下信息的稳定记录：

- `strategy_version`
- `prompt_version`
- `adapter_version`
- `runtime_version`

这会带来两个问题：

1. 当 prompt 或 strategy 升级后，历史报告的来源难以精确回溯；
2. 当老师感知结果退化时，团队难以复盘“到底是 artifact 变了、prompt 变了、strategy 变了，还是 runtime 变了”。

如果没有版本谱系，report plane 只是“统一读取面”，还不是“统一审计面”。

### 5.4 Review queue is a downgrade plane, but not yet a full operations surface

review queue 已经从 survey 专属能力提升成了统一降级平面，这非常好。但从运营角度看，还存在明显不足：

- reviewer 的处理结果还没有系统性回灌到 eval 与 tuning；
- 还缺少按 domain / strategy / reason_code 的聚合运营视图；
- 还没有形成“哪些域正在频繁 rerun / claim / reject / retry”的统一告警闭环。

换句话说，review queue 现在已经能接住失败，但还不能充分把失败变成后续优化输入。

### 5.5 New domain extension is easier, but still not cheap enough

当前扩新域已经不需要重造整条 survey stack，这是进步；但扩展成本仍然偏高，原因包括：

- 需要同时理解 manifest、artifact、strategy、runner、report provider、review queue provider；
- 各层虽然抽象存在，但 onboarding 模板还不够标准化；
- 跨层接入点仍较多，新人很容易遗漏 rollout flags、eval fixtures、report facade 等要素。

这意味着“架构可扩展”已经成立，但“团队扩展效率高”还没有完全成立。

## 6. Recommended Direction

推荐继续采用以下主方向：

> **受控平台化（Controlled Platformization）**

即：

- 保持 `Coordinator` 为唯一默认前台 agent；
- 把 specialist 继续留在内部 handoff / runtime 控制面；
- 不是增加 agent 自由度，而是增加控制面治理深度；
- 不是追求 agent 社会化，而是追求多域扩展、质量追溯、人工复核、运营治理的一致化。

这是当前最符合项目状态和产品目标的路线。

不推荐的方向包括：

- 过早开放 specialist 直接接管用户会话；
- 引入自由 agent-to-agent 对话网状运行时；
- 把“多域分析平台”误演进成“任意能力插件平台”；
- 为了平台化而削弱教学 workflow 的显式入口、解释性和降级路径。

## 7. Optimization Plan

### 7.1 P0: Must-do improvements

#### P0-1. Make manifest drive assembly, not only metadata

目标：把 manifest 从“说明书”推进成“装配真相的一部分”。

建议：

- 引入统一的 domain runtime builder；
- 让 manifest 能声明 runner binding key、artifact payload key、teacher context requirements 等核心装配元信息；
- 把 `survey_wiring.py` 中按域重复的 registry/runtime glue 尽量收敛成通用 builder；
- 新增 domain 时，尽量做到“填 manifest + 实现特定 runner / adapter”，而不是复制整段 wiring。

成功标准：

- 新增第 4 个 analysis domain 时，不再需要新增一组几乎同构的 build_*_specialist_registry 函数。

#### P0-2. Upgrade specialist output validation into true schema validation

目标：避免 specialist 仅凭“返回了一个非空 dict”就被当作有效结果。

建议：

- 为不同 `analysis_artifact` 类型建立更严格的 schema contract；
- governor 在 runtime 中依据 strategy / specialist 的 schema 做真实字段校验；
- 对关键字段（如 `executive_summary`、`teaching_recommendations`、`confidence_and_gaps`）进行最小完整性校验；
- schema 不满足时直接 downgrade 到 review queue 或标记 invalid_output，而不是继续交付为 final report。

成功标准：

- 输出契约真正体现 domain 质量要求，而不是只承担“防空值”作用。

#### P0-3. Add version lineage to analysis reports

目标：让 report plane 成为可追溯的审计面。

建议：

- 在统一 report model 中补充：
  - `strategy_version`
  - `prompt_version`
  - `adapter_version`
  - `runtime_version`
- 在 specialist runtime / planner / artifact adapter 层统一注入版本信息；
- rerun 时保留 previous lineage，支持最小差异比较。

成功标准：

- 任意一条分析报告都能回答“它是按哪个版本策略、哪个 prompt、哪个 adapter、哪个 runtime 生成的”。

### 7.2 P1: Operability upgrades

#### P1-1. Promote runtime events into operational metrics

目标：让 specialist event 不只是日志，而成为运营与告警信号。

建议：

- 按 `domain / strategy_id / specialist_agent / phase` 聚合 runtime 事件；
- 建立至少以下指标：
  - run_count
  - fail_count
  - timeout_count
  - review_downgrade_count
  - rerun_count
  - invalid_output_count
- 与 rollout checklist 对齐，为 domain enablement 提供持续观测证据。

成功标准：

- 发布与回滚决策不再只依赖人工抽样，而有清晰统计基线。

#### P1-2. Turn review queue into a true quality feedback loop

目标：把人工 review 从“兜底动作”升级为“质量学习闭环”。

建议：

- 将 claim / resolve / reject / dismiss / retry 的结果结构化沉淀；
- 汇总为按 domain / strategy / reason_code 的质量统计；
- 把 reviewer 的修正结论回灌到 offline eval fixtures 或 tuning dataset；
- 在 rollout 文档中加入“review feedback drift”监控要求。

成功标准：

- review queue 不再只是故障收容器，而成为质量提升输入源。

#### P1-3. Add controlled internal job graphs for high-risk domains

目标：在不引入自由 multi-agent mesh 的前提下，支持更复杂的内部协作流。

建议：

- 优先在 `video_homework` 试点小型固定图，如 `extract -> analyze -> verify -> merge`；
- 由同一 governed runtime 执行，而不是放任 agent 自由对话；
- 每个节点继续纳入 budget、timeout、event、fallback 约束；
- 明确说明这是 controlled orchestration，不是开放 agent network。

成功标准：

- 更复杂的高风险域可以拆步骤提质，同时不牺牲治理能力。

### 7.3 P2: Longer-term platform hardening

#### P2-1. Add replay / simulation harness

目标：让策略退化分析和版本回归比较可复现。

建议：

- 为报告保存足够的 artifact + strategy + version lineage；
- 提供 replay 脚本，可在不同 prompt / strategy 版本下重跑同一分析；
- 支持生成差异摘要，用于回归调试和灰度评估。

成功标准：

- 质量退化问题可以通过 replay 定位，而不只靠线上猜测。

#### P2-2. Build standard domain onboarding template

目标：降低扩域认知成本。

建议：

- 提供新 domain onboarding checklist/template；
- 明确要求域实现至少覆盖：manifest、artifact、strategy、specialist、report provider、review queue 接入、fixtures、rollout flags、docs；
- 让新域开发从“理解隐性规则”变成“完成显式模板”。

成功标准：

- 新域接入流程更接近工业化复制，而不是依赖核心作者经验。

## 8. Recommended Next Execution Order

推荐执行顺序如下：

1. `P0-1` manifest 驱动装配继续收敛
2. `P0-2` specialist schema 校验升级
3. `P0-3` report version lineage 落地
4. `P1-1` runtime metrics / operational dashboards
5. `P1-2` review queue feedback loop
6. `P1-3` controlled job graph 试点
7. `P2-1` replay / simulation harness
8. `P2-2` domain onboarding template

排序原则：

- 先补“平台真相来源”和“结果可追溯”；
- 再补“运营与质量闭环”；
- 最后再补“更复杂的内部编排能力”。

## 9. Final Recommendation

这套 agent 设计当前最应该坚持的战略，不是继续追求“更多 agent”，而是继续强化：

- 更清晰的控制面边界；
- 更强的 specialist runtime 治理；
- 更完善的 report lineage；
- 更闭环的 review / eval / rollout 运营体系。

如果沿着这条路线继续推进，项目会形成一个很有价值的形态：

> 一个不是通用 agent 平台、但拥有平台级治理能力的教学 workflow control plane。

这正是当前项目最有竞争力、也最不容易被轻易复制的方向。
