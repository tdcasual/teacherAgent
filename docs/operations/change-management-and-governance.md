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
