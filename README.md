# Teaching Workflow Product
[![Teacher E2E](https://github.com/tdcasual/teacherAgent/actions/workflows/teacher-e2e.yml/badge.svg?branch=main)](https://github.com/tdcasual/teacherAgent/actions/workflows/teacher-e2e.yml)

面向老师、学生与管理员的单校作业产品。
目标是把“布置作业、今日任务、显式提交、进度与账号管理”收敛成可解释、可回归、可运维的闭环，而不是考试分析平台或通用 agent 平台。

## 产品真相
- 产品定位：单校作业产品，不是插件市场、考试分析或通用 agent 平台
- 老师主线：上传材料 → 审核草稿并创建 → 查看完成进度
- 学生主线：今日任务 → 陪练（侧信道）→ 显式提交
- 老师端默认能力：`teacher-assignment-ops`；全员产品面是作业三件套（作业运营 / 作业生成 / 学生教练）。任教某学科的老师额外看到该 pack 的 `skill_affiliates`（如物理老师的课堂采集）
- 运行时契约：`docs/reference/agent-runtime-contract.md`

## 30 秒定位
- 老师：看 `docs/how-to/teacher-daily-workflow.md`
- 学生：看 `docs/how-to/student-login-and-submit.md`
- 管理员：看 `docs/how-to/admin-manage-teachers-tui.md`
- 全局文档导航：`docs/INDEX.md`

## 5 分钟快速开始
```bash
cp .env.production.min.example .env
# 填必填密钥：把 REDIS_PASSWORD / MCP_API_KEY / AUTH_TOKEN_SECRET / MASTER_KEY 的 change_me 换成真实值
docker compose up -d
```

复制 example **不会**直接启动。`change_me` 不是密钥。compose 对空的 `REDIS_PASSWORD`、`MCP_API_KEY` 与 `MASTER_KEY` 使用 `${VAR:?}`，缺值会立刻失败；`AUTH_TOKEN_SECRET` 同样必须换成部署密钥后再 `docker compose up`。四项都空着时栈起不来。MCP 仅绑定 `127.0.0.1:9000`。

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

## 关键参考
- 运行时契约：`docs/reference/agent-runtime-contract.md`
- 模型策略：`docs/reference/model-policy.md`
- 架构边界：`docs/architecture/module-boundaries.md`

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
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt
uvicorn services.api.app:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev:teacher
```

说明：非 Docker 方式本地启动后端时，请使用 Python `3.13`，以与 `pyproject.toml` 和 CI 保持一致。
