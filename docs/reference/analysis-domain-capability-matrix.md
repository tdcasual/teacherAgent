# Analysis Domain Capability Matrix

由 manifest / binding / contract checker 生成，用于快速查看当前 analysis domains 的平台能力面。

| domain_id | rollout_stage | strategy_ids | specialist_ids | runtime_binding | report_binding | replay_compare |
| --- | --- | --- | --- | --- | --- | --- |
| class_report | internal_only | class_signal.teacher.report | class_signal_analyst | yes | yes | yes |
| survey | shadow_or_beta | survey.chat.followup<br>survey.teacher.report | survey_analyst | yes | yes | yes |
| video_homework | controlled_beta | video_homework.teacher.report | video_homework_analyst | yes | yes | yes |

## Source

- `scripts/check_analysis_domain_contract.py --json`
- `services/api/domains/manifest_registry.py`
- `services/api/domains/binding_registry.py`
