# Change Management And Governance

Last updated: 2026-02-15

## 目标

建立统一的变更治理闭环，确保每次改动都满足：

1. 可审计（有记录）
2. 可验证（有证据）
3. 可回滚（有预案）

## 角色与职责

1. 变更负责人（Author）
   - 提交变更与验证证据；
   - 提供风险等级与回滚方案。
2. 模块 Owner（Reviewer）
   - 依据 `docs/architecture/ownership-map.md` 进行评审；
   - 对跨模块影响进行把关。
3. 发布值守（Operator）
   - 观察 CI 与关键指标；
   - 触发回滚或升级处置。

## 标准变更流程（默认）

1. 明确范围与风险等级（L/M/H）。
2. 实施改动并完成最小充分验证。
3. 提交 PR，按模板补齐证据。
4. 通过评审后合并，观察 CI 和运行指标。
5. 记录必要文档更新与风险登记。

## 紧急变更流程（生产风险优先）

触发条件：

1. 安全漏洞正在被利用或高概率可利用；
2. 服务不可用或核心教学流程阻断。

流程：

1. 先止损（降级/开关/回滚）；
2. 再补完整验证与文档；
3. 24 小时内补齐事后复盘（根因、影响、行动项）。

## 变更门禁清单

### 所有变更必须满足

1. 有清晰问题定义与影响面。
2. 有验证命令与结果摘要。
3. 变更可被追踪到单一 PR。

### M/H 变更额外要求

1. 更新风险登记或说明无新增风险原因；
2. 提供回滚路径；
3. 关键路径增加回归测试。

## 发布前门禁

发布前必须保留以下证据，且证据能关联到当前 PR / 变更单：

1. 后端质量预算通过：`python3 scripts/quality/check_backend_quality_budget.py`
2. 复杂度预算通过：`python3 scripts/quality/check_complexity_budget.py`
3. 关键回归通过：受影响测试、结构守卫、前端类型检查 / 构建
4. 运行时观测核验：查看 `/ops/metrics` 与 `/ops/slo`，确认无明显错误率或延迟异常

建议将 `scripts/quality/collect_backend_quality.sh` 的输出附到发布记录中，作为发布前门禁摘要。

对于 analysis runtime 的 M/H 变更，还应额外保留以下质量闭环证据：

1. 从 review queue 日志导出结构化 feedback dataset：`./.venv/bin/python scripts/export_review_feedback_dataset.py --input <review_queue.jsonl>`
2. 将 feedback dataset 或其 summary 输入离线评测：`./.venv/bin/python scripts/analysis_strategy_eval.py --fixtures tests/fixtures --review-feedback <dataset.json> --json --summary-only`
3. 记录 `by_domain` / `by_strategy` / `by_reason_code` 漂移，确认此次变更没有把错误从线上 review queue 悄悄转移到线下盲区。
4. 如需形成周报或灰度评估结论，可额外运行：`./.venv/bin/python scripts/build_review_drift_report.py --input <dataset.json>`。
5. 如需判断当前批次是否具备放量条件，可额外运行：`./.venv/bin/python scripts/build_analysis_release_readiness_report.py --contract-check <contract.json> --metrics <metrics.json> --drift-summary <drift.json> --shadow-compare <shadow.json>`。

## 回滚后核验

若发生回滚，值守人员必须在回滚完成后补充以下检查：

1. 再次查看 `/ops/metrics`，确认请求量、错误率、延迟恢复到可接受区间；
2. 查看 `/ops/slo`，确认当前 SLO 投影已恢复绿色或明确记录仍在观察；
3. 记录回滚原因、影响时间窗、后续补救任务与 owner。

## 文档治理约束

1. 设计过程文档放 `docs/plans/`，稳定结论迁移到 `docs/reference/` 或 `docs/explain/`。
2. 变更涉及运行流程时，优先更新 `docs/how-to/` 与 `docs/operations/`。
3. 主入口必须可发现：`README.md` 与 `docs/INDEX.md` 保持同步。

## 治理指标（建议季度复盘）

1. PR 首次通过率（含 CI）；
2. 紧急回滚次数；
3. 高风险变更占比；
4. 风险登记闭环率（到期复审是否完成）；
5. 文档滞后率（代码合并后未更新文档的比例）。

## Analysis Runtime Reviewer And Quality Gate Requirements

当变更触及 unified analysis runtime、job graph、strategy selector 或 review queue 时，除通用门禁外，还应补充以下证据：

1. 高风险域若启用 internal reviewer，必须明确 reviewer 仅作为内部 verify node，不得直接暴露为前台 agent；
2. 变更后需保留 `/teacher/analysis/metrics` 的 `specialist_quality` 快照，确认 timeout / invalid / budget / fallback 未越线；
3. 发布前需运行 `./.venv/bin/python scripts/build_analysis_release_readiness_report.py --contract-check <contract.json> --metrics <metrics.json> --drift-summary <drift.json> --shadow-compare <shadow.json>`，并把结果附到发布记录；
4. 若 release-readiness 因 `specialist_quality` 阻断，必须先修复或降级，不允许以“先上线再观察”替代门禁。

## Strategy-Specific Release Gates

当 analysis runtime 变更影响某个具体策略时，发布记录必须同时提供：

1. 全局 `specialist_quality`；
2. 对应策略的 `specialist_quality_by_strategy[strategy_id]`；
3. 所用滑窗参数（默认 `window_sec=3600`）；
4. 若 reviewer v2 参与高风险 verify，还需记录 `quality_score` 与主要 `issue_list` 分布是否异常。

若目标策略的 strategy-level gate 不通过，即使全局 gate 通过，也不应继续放量。

## Feedback-Loop Governance

当 release 或 rerun 周期依赖 review feedback 调优时，变更记录还应包含：

1. 最新 `tuning_recommendations` 列表；
2. `feedback_loop_summary.high_priority_count` 是否归零；
3. 对应 `strategy_id` 的修复动作是否已经在 fixture eval 中得到覆盖；
4. 若高优先级 recommendation 仍存在，说明变更尚未真正闭环，不应把 review queue 压力解释为“已解决”。

## Analysis Policy Change Governance

6. 如需形成一次性预发布结论，优先运行统一 gate：`./.venv/bin/python scripts/quality/check_analysis_preflight.py --fixtures tests/fixtures --review-feedback <dataset.jsonl> --metrics <metrics.json> --baseline-dir <baseline_dir> --candidate-dir <candidate_dir>`；仅当该 gate 通过，才进入放量。

5. policy 变更前需先运行：`./.venv/bin/python scripts/quality/check_analysis_policy.py --config <policy.json>`；若该步失败，不进入 release-readiness / drift / eval 阶段。
当变更只涉及 analysis 质量阈值、feedback tuning recommendation 规则或 strategy eval rollout 要求时，仍按受控变更处理，不视为“纯配置可忽略变更”。发布记录至少应包含：

1. `config/analysis_policy.json` 或临时 `--policy-config` 文件的 diff；
2. `./.venv/bin/python scripts/build_analysis_release_readiness_report.py ... --policy-config <policy.json>` 输出；
3. `./.venv/bin/python scripts/build_review_drift_report.py --input <dataset.json> --policy-config <policy.json>` 输出；
4. `./.venv/bin/python scripts/analysis_strategy_eval.py --fixtures tests/fixtures --review-feedback <dataset.json> --json --summary-only --policy-config <policy.json>` 输出。

若 policy 调整导致：

- 放宽 release gate；
- 降低 tuning recommendation priority；
- 减少 required edge-case coverage；

则默认按 M/H 变更处理，并要求说明为何这是风险可接受的显式决策，而不是为了让门禁“变绿”。

CI 现已在主流水线执行 `scripts/quality/check_analysis_policy.py` 与 `scripts/quality/check_analysis_preflight.py`，本地放量前应保持与 CI 相同输入口径。

CI 会上传 `analysis-rollout-artifacts`，其中至少包含 `analysis-policy.json` 与 `analysis-preflight.json`；GitHub job summary 则提供快速结论摘要。
