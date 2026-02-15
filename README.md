# Physics Teaching Helper Agent
[![Teacher E2E](https://github.com/tdcasual/teacherAgent/actions/workflows/teacher-e2e.yml/badge.svg?branch=main)](https://github.com/tdcasual/teacherAgent/actions/workflows/teacher-e2e.yml)

面向老师、学生与管理员的教学流程助手。
目标是把“上传材料、生成讲评、提交作业、账号管理”这些高频动作，变成可复用、可追踪、可运维的闭环。

## 30 秒定位
- 老师：看 `docs/how-to/teacher-daily-workflow.md`
- 学生：看 `docs/how-to/student-login-and-submit.md`
- 管理员：看 `docs/how-to/admin-manage-teachers-tui.md`
- 全局文档导航：`docs/INDEX.md`

## 5 分钟快速开始
```bash
cp .env.production.min.example .env
docker compose up -d
```

启动后访问：
- 老师端：`http://localhost:3002`
- 学生端：`http://localhost:3001`
- API：`http://localhost:8000`

管理员命令行入口：
```bash
docker compose exec api admin_manager
```

## 我现在要做什么
1. 老师完成一次教学闭环：`docs/how-to/teacher-daily-workflow.md`
2. 学生登录并提交作业：`docs/how-to/student-login-and-submit.md`
3. 管理员批量管理教师账号：`docs/how-to/admin-manage-teachers-tui.md`
4. 认证与账号故障排查：`docs/how-to/auth-and-account-troubleshooting.md`

## 角色入口
- 老师：`docs/how-to/teacher-daily-workflow.md`
- 学生：`docs/how-to/student-login-and-submit.md`
- 管理员：`docs/how-to/admin-manage-teachers-tui.md`

## 常见问题
1. `admin_manager` 找不到命令：
```bash
docker compose build api
docker compose up -d api
```
2. 学生或老师登录失败：看 `docs/how-to/auth-and-account-troubleshooting.md`
3. token 失效：通常是重置凭据后版本变化，重新登录即可。

## 进阶文档
- 快速开始扩展版：`docs/getting-started/quickstart.md`
- 操作手册总览：`docs/how-to/INDEX.md`
- 贡献与变更流程：`CONTRIBUTING.md`
- PR 变更模板：`.github/pull_request_template.md`
- 安全披露与处置：`SECURITY.md`
- HTTP API：`docs/http_api.md`
- MCP API：`docs/mcp_api.md`
- 权限与认证参考：`docs/reference/permissions-and-security.md`
- 认证与令牌模型：`docs/reference/auth-and-token-model.md`
- 风险与接受清单：`docs/reference/risk-register.md`
- 变更治理与发布门禁：`docs/operations/change-management-and-governance.md`
- 安全事件响应 runbook：`docs/operations/security-incident-response-runbook.md`
- 质量加固演进说明：`docs/explain/backend-quality-hardening-overview.md`
- 上传与资源限额基线：`docs/reference/upload-resource-guardrails.md`
- 锁与幂等处理说明：`docs/explain/locking-and-idempotency-rationale.md`
- 架构边界：`docs/architecture/module-boundaries.md`
- 运维可观测：`docs/operations/slo-and-observability.md`
- 设计与演进历史：`docs/plans/`

## 本地开发（可选）
```bash
# API
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt
uvicorn services.api.app:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev:teacher
```
