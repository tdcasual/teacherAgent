# Contributing Guide

本项目面向教学生产场景，提交标准以“可回滚、可审计、可验证”为核心。

## 分支与提交

1. 默认在短生命周期分支开发，合并到 `main` 前保持历史可读。
2. 提交信息建议使用 `<type>(<scope>): <summary>`：
   - `feat` 新功能
   - `fix` 缺陷修复
   - `refactor` 重构（不改行为）
   - `docs` 文档更新
   - `ci` 流水线与自动化
3. 一次提交只解决一个核心问题，避免“混合改动”导致回滚困难。

## 变更分级（治理门禁）

### 低风险变更（L）

- 文档、注释、样式、非行为重构。
- 要求：
  1. 本地最小验证（受影响测试或静态检查）；
  2. 更新相关文档入口（如 `README.md`、`docs/INDEX.md`）；
  3. PR 中说明“无行为变化”。

### 中风险变更（M）

- 单模块行为变化（接口兼容、性能、可观测性）。
- 要求：
  1. 先有失败测试再修复（TDD）；
  2. 提供回归测试证据与风险说明；
  3. 至少 1 名模块 Owner 评审（见 `docs/architecture/ownership-map.md`）。

### 高风险变更（H）

- 认证授权、数据持久化、并发模型、跨模块/跨端联动。
- 要求：
  1. 明确变更计划与回滚策略；
  2. 增加安全或一致性回归测试；
  3. 至少 2 名评审（含对应域 Owner）；
  4. 更新风险条目（`docs/reference/risk-register.md`）或说明为何不需要。

## PR 必填内容

1. 变更范围与目标（做了什么、为什么做）。
2. 风险等级（L/M/H）与影响面。
3. 验证证据（本地命令、核心输出、CI 结果）。
4. 文档影响（新增/更新/无需更新及理由）。
5. 回滚方案（尤其 M/H 变更）。

## 验证基线

提交前至少满足以下之一（按变更类型选最小充分集）：

1. 后端：`python3 -m pytest -q tests/...`（覆盖受影响模块）。
2. 前端：`npm run lint`、`npm run typecheck`、`npm run build:*`（覆盖受影响应用）。
3. 全量回归：`python3 -m pytest -q --maxfail=1`（高风险建议执行）。

不得在未验证的情况下宣称“已修复”。

## 文档治理规则

1. 涉及流程、权限、运维策略变更时，必须同步更新文档：
   - 权限/认证：`docs/reference/permissions-and-security.md`
   - 风险接受：`docs/reference/risk-register.md`
   - 责任边界：`docs/architecture/ownership-map.md`
2. 设计草案放在 `docs/plans/`，稳定结论沉淀到 `docs/reference/` 或 `docs/explain/`。
3. 文档应可执行：优先写清命令、路径、验证方式，而非抽象口号。

## 安全与事件

1. 发现安全问题请走 `SECURITY.md` 报告流程，不要在公开 issue 直接披露可利用细节。
2. 涉及凭据、权限、审计链路的改动，PR 必须标记为安全敏感。
