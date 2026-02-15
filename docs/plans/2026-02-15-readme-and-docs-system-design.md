# 2026-02-15 README 与文档体系重构设计

## 背景
当前仓库已有大量设计/实现文档，但入口偏技术与历史沉淀导向。对于教学业务用户（老师、学生、管理员）而言，无法快速定位“现在要做什么、该看哪篇文档、怎么验证结果”。

## 目标
1. README 从“项目介绍”升级为“任务分发台”。
2. 文档体系按使用目的分层：上手、操作、参考、解释。
3. 优先覆盖高频业务任务：老师日常流程、学生登录提交、管理员教师账号管理、账号故障排查。
4. 保留现有 `docs/plans/` 作为历史与设计档，不强制迁移。

## 信息架构
- `docs/getting-started/`: 首次接触者的最短路径。
- `docs/how-to/`: 任务驱动操作手册（主路径）。
- `docs/reference/`: 稳定事实与契约（API、权限、配置、目录）。
- `docs/explain/`: 设计理念与架构解释。

新增导航页：
- `docs/INDEX.md`: 全局入口（任务 + 角色）。
- `docs/how-to/INDEX.md`: 操作手册总览。

## README 策略
README 顶层结构：
1. 30 秒定位。
2. 5 分钟快速开始。
3. 我现在要做什么（任务卡）。
4. 角色入口（老师/学生/管理员）。
5. 常见问题。
6. 进阶链接（API/架构/运维/开发）。

## 首批落地文档
- `docs/getting-started/quickstart.md`
- `docs/how-to/teacher-daily-workflow.md`
- `docs/how-to/student-login-and-submit.md`
- `docs/how-to/admin-manage-teachers-tui.md`
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/permissions-and-security.md`

## 治理规则
1. 每次功能上线至少同步 1 篇 `how-to` 或 `reference`。
2. 文档头部固定：适用角色、前置条件、最后验证日期。
3. `docs/plans/` 中文档可标注 `draft / active / superseded` 状态，不强制删除历史。

## 验收标准
1. 新用户 10 分钟内可定位并完成“老师一次教学闭环”或“管理员一次教师账号管理”。
2. README 中所有主链接可达。
3. 管理员 TUI、学生认证、老师日常操作均有独立 how-to。
