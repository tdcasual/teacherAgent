# 后端质量加固演进说明

- 适用角色：开发者、平台负责人
- 最后验证日期：2026-02-15
- 主要来源：`docs/plans/2026-02-22-backend-quality-hardening-report.md`

## 为什么做这轮加固
目标是降低维护成本与线上不确定性：
1. 静态检查债务过高，影响 CI 稳定性。
2. 类型系统长期失真，改动时回归风险大。
3. `app_core.py` 体量过大，职责耦合严重。

## 结果概览（阶段性）
- Ruff 错误显著下降。
- mypy 从大量错误清零到可控基线。
- `services/api/app_core.py` 行数显著压缩并抽离部分职责。

## 核心策略
1. 用预算与守护测试约束质量退化。
2. 高风险模块优先做可回归的小步重构。
3. 将“历史兼容层”与“新服务层”逐步解耦。

## 当前仍需持续的工作
1. 继续收敛 `app_core` 的兼容导出与耦合面。
2. 保持 touched-file typing 与 lint 门禁。
3. 把阶段性改造成果沉淀为稳定 reference/explain 文档，而不仅是实施报告。

## 相关文档
- `docs/operations/slo-and-observability.md`
- `docs/architecture/module-boundaries.md`
- `docs/reference/permissions-and-security.md`
