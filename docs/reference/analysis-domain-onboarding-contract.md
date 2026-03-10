# Analysis Domain Onboarding Contract

用于把“新增 analysis domain 需要交付什么”从经验清单升级为显式契约。

## 1. Goal

每个新 domain 都必须能在统一 analysis plane 中完成：

- target resolver 识别目标；
- artifact adapter 产出稳定 artifact；
- strategy selector 选中可追溯 strategy；
- specialist runtime 在治理约束下执行；
- analysis report plane 与 review queue 暴露统一读路径；
- rollout / rollback / replay / eval 可被运维与评审复用。

## 2. Required Truth Sources

新增 domain 前，必须明确以下真相源：

- `domain_id` / `display_name` / `analysis_type`
- `target_type` / `target_scope`
- `artifact_type` / schema version / provenance
- `strategy_id` / `strategy_version` / review policy / budget
- `specialist_agent` / `task_kind` / output schema
- rollout stage / feature flags / rollback owner

缺任一项，都不应进入实现阶段。

## 3. Required Deliverables

每个 domain PR 至少应同时交付：

1. manifest entry：domain、artifact、strategy、specialist、binding、flags
2. artifact contract：稳定字段、缺口表达、来源说明
3. specialist contract：typed output、budget、timeout、fail-closed 规则
4. report binding：统一接入 `GET /teacher/analysis/reports` / detail / rerun
5. review queue integration：`domain / strategy_id / reason_code / disposition`
6. fixtures：happy path、low confidence、missing fields、provider noise、resource edge
7. offline eval：`scripts/analysis_strategy_eval.py` 或同等级验证入口
8. replay support：report detail 能重建 artifact payload 与 lineage
9. rollout docs：shadow / beta / release / rollback 入口
10. acceptance checklist：可被 reviewer 直接逐项核验

## 4. Runtime And Safety Requirements

实现必须遵守以下统一规则：

- 只通过 manifest / binding registry 接入，不新增中心化硬编码 lookup；
- specialist 不直接 takeover 老师会话，不直接写长期 memory；
- invalid output / timeout / budget exceeded 必须稳定降级到 review / failed；
- rerun 返回 `previous_lineage` 与 `current_lineage`；
- report detail 可用于 replay / compare / shadow validate。

## 5. Rollout And Rollback Requirements

上线前必须明确：

- feature flags 与默认值；
- shadow / beta / release 的 go / no-go 信号；
- review feedback / shadow compare / release-readiness 的检查路径；
- rollback 命令、责任人和验证动作；
- 是否需要 review-only 或 allowlist 阶段。

## 6. Canonical References

- Onboarding template：`docs/reference/analysis-domain-onboarding-template.md`
- Onboarding checklist：`docs/reference/analysis-domain-checklist.md`
- Capability matrix：`docs/reference/analysis-domain-capability-matrix.md`
- Extension plan template：`docs/plans/templates/analysis-domain-extension-template.md`
- Runtime contract：`docs/reference/analysis-runtime-contract.md`
