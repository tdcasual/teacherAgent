# Physics Teaching Helper Agent
[![Teacher E2E](https://github.com/tdcasual/teacherAgent/actions/workflows/teacher-e2e.yml/badge.svg?branch=main)](https://github.com/tdcasual/teacherAgent/actions/workflows/teacher-e2e.yml)

欢迎来到这套面向老师的物理教学助手 👋  
你可以把它理解成一个“教学流程搭子”：课前能备、课堂能记、课后能跟、复盘能看。

> 默认使用者身份：老师（Teacher）

## 这个项目是做什么的？
- 帮老师做考试与作业相关的分析与生成
- 把课堂材料（文档/图片）转成可复用的结构化内容
- 支持学生学习诊断与个性化辅导闭环
- 提供题库与核心例题沉淀，便于长期复用

一句话：**把教学中的重复劳动，变成可复用、可追踪、可沉淀的流程。**

## 3 分钟快速体验（推荐）
```bash
cp .env.production.min.example .env
docker compose up -d
```

启动后默认访问：
- 老师端：`http://localhost:3002`
- 学生端：`http://localhost:3001`
- API：`http://localhost:8000`

如果你只想先体验老师侧功能，打开老师端就可以开始。

## 项目结构（先有方向感）
- `frontend/`：师生双端前端（老师端 / 学生端）
- `services/api/`：后端 API 聚合与业务服务
- `services/mcp/`：MCP 服务
- `skills/`：教学相关技能与流程编排
- `data/`：教学数据（题库、作业、画像、课堂内容等）

## 推荐使用路径（老师视角）
1. 进入老师端，上传教学或考试相关材料
2. 生成分析草稿 / 课堂讨论稿 / 作业建议
3. 在课后查看诊断结果并迭代下一轮教学安排

不用一次学会所有功能，先跑通一个完整小闭环就会非常顺手。

## 详细文档入口（操作细节请看这里）
README 保持“轻量介绍”，具体配置与接口文档请查阅：

- HTTP API：`docs/http_api.md`
- MCP API：`docs/mcp_api.md`
- 设计与演进文档：`docs/plans/`
- 提示词与安全测试说明：`tests/prompt_injection_README.md`

## 本地开发（可选）
如果你不走 Docker，也可以本地启动：

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

## 代码质量检查（推荐）
提交前建议先执行一轮质量检查，减少 CI 返工：

```bash
# 后端
python3 -m ruff check services/api/settings.py services/api/runtime/runtime_manager.py tests/test_ci_workflow_quality.py
python3 -m black --check services/api/settings.py services/api/runtime/runtime_manager.py tests/test_ci_workflow_quality.py
python3 -m mypy --follow-imports=skip services/api/settings.py services/api/runtime/runtime_manager.py

# 前端
cd frontend
npm run typecheck
```

---

如果你准备把它用于日常教学，建议下一步先看 `docs/http_api.md`，再按你的教学场景逐步开启对应模块。
