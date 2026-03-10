# Analysis Domain Checklist

用于评审新增 analysis domain 是否已经满足平台化接入要求。

## 1. Manifest 与装配

- [ ] 已在 manifest 中声明 `domain_id`、`display_name`、`rollout_stage`
- [ ] 已声明 artifact adapter / strategy / specialist / runtime binding / report binding
- [ ] 已确认 report provider 通过统一 analysis report plane 暴露，而不是私有 read path

## 2. Artifact / Strategy / Specialist

- [ ] artifact contract 已稳定，包含 `confidence`、`missing_fields`、`provenance`
- [ ] strategy 已声明 `strategy_id`、budget、review policy、delivery mode
- [ ] specialist 输出使用 typed schema，而不是宽泛 dict
- [ ] 如使用 controlled graph，节点类型、budget、失败降级策略已明确

## 3. Review Queue 与 Feedback Loop

- [ ] review queue 已保留 `domain`、`strategy_id`、`reason_code`、`disposition`、`operator_note`
- [ ] rerun / dismiss / reject / resolve / escalate 行为具备留痕
- [ ] review queue 日志可导出为 feedback dataset
- [ ] feedback dataset 可被 `scripts/analysis_strategy_eval.py` 消费

## 4. Replay / Compare / Audit

- [ ] report detail 可取回 replay 必需字段：artifact payload、artifact meta、analysis artifact、lineage
- [ ] `scripts/replay_analysis_run.py` 可对该域执行 replay request 重建
- [ ] `scripts/compare_analysis_runs.py` 可输出 compact diff summary

## 5. 测试与 Observability

- [ ] targeted tests 已覆盖正常路径、review 降级、invalid output、rerun
- [ ] fixtures 已覆盖最小样本与 edge cases
- [ ] `/ops/metrics.metrics.analysis_runtime` 可看到该域 counters 和 breakdowns
- [ ] `GET /teacher/analysis/metrics` 可见该域 runtime snapshot

## 6. Feature Flags 与文档

- 可执行 contract check：`./.venv/bin/python scripts/check_analysis_domain_contract.py --json`
- [ ] CI 已执行 `scripts/check_analysis_domain_contract.py --json` 并通过
- [ ] feature flags 已定义并写入 rollout 文档
- [ ] 已更新 `docs/reference/analysis-runtime-contract.md`
- [ ] 已更新 `docs/operations/multi-domain-analysis-rollout-checklist.md`
- [ ] 已更新 `docs/INDEX.md`
- [ ] 已对照 `docs/reference/analysis-domain-capability-matrix.md` 核对该域的 rollout / runtime / replay-compare 能力
- [ ] reviewer 可直接按本 checklist 完成验收
