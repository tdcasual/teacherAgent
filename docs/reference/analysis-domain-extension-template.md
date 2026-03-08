# Analysis Domain Extension Template

用于新增第 4 个及之后的 analysis domain。

## 必备项

- manifest entry：`domain_id`、artifact adapters、strategies、specialists、feature flags、runtime binding
- artifact contract：稳定 `artifact_type`，并明确 `confidence`、`missing_fields`、`provenance`
- strategy contract：`strategy_id`、`strategy_version`、`delivery_mode`、`review_policy`
- specialist contract：typed `output_schema`，不得直接 takeover 老师会话
- report plane：统一挂到 `analysis report plane`
- review queue：统一接入 domain / reason / operation
- fixtures：至少补 domain 最小 fixture 集和 edge cases
- rollout：补 feature flags、checklist、release notes

## 建议流程

1. 在 `services/api/domains/manifest_registry.py` 增加 manifest
2. 实现 artifact adapter 或复用已有 adapter
3. 实现 specialist runner 与 typed output schema
4. 接入统一 report / review queue
5. 补 targeted tests、eval fixtures、rollout docs
6. 确认 teacher workbench 只消费统一 plane，而不是新造私有 read path
