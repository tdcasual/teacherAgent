# Physics Teaching Helper Agent

本项目是一套面向物理教学的多技能 agent 系统，覆盖考试分析、课堂内容采集、课后诊断、学生个性化辅导、题库与核心例题管理等完整流程。

## 核心能力
- 解析考试成绩（xls/xlsx）、试卷、参考答案，生成考试分析与讨论稿
- 课堂内容采集（PDF/Word/图片 OCR）并结构化保存
- 课前检测清单、课后诊断与个性化作业生成
- 学生对话诊断、学习讨论（Socratic）、费曼反思、作业发放
- 学生作业拍照 OCR 评分与画像自动更新
- 核心例题库：标准解法、核心模型、变式模板

## 技能列表与职责边界
### 1) `physics-teacher-ops`
老师侧：考试分析、知识点管理、备课与课堂讨论、课前/课后材料输出。

### 2) `physics-homework-generator`
老师侧：基于课堂讨论/教案/学案批量生成课后诊断与作业。

### 3) `physics-lesson-capture`
课堂内容采集：OCR、例题抽取、课堂总结、讨论模板输出。

### 4) `physics-student-coach`
学生侧：身份验证、诊断 → 讨论 → 费曼反思 → 作业 → OCR 评价 → 画像更新。

### 5) `physics-student-focus`
老师侧：针对某个学生进行重点分析（答题卡/讨论）并更新画像。

### 6) `physics-core-examples`
核心例题库：登记核心例题、标准解法、核心模型、变式模板，支持图文题。

## 目录结构（核心）
```
skills/
  physics-teacher-ops/
  physics-homework-generator/
  physics-lesson-capture/
  physics-student-coach/
  physics-student-focus/
  physics-core-examples/

scripts/
  grade_submission.py
  render_assignment_pdf.py
  student_session_finalize.py
  profile_to_mem0.py
  check_profile_changes.py

data/
  question_bank/
  core_examples/
  lessons/
  assignments/
  student_profiles/
  student_submissions/

frontend/
  apps/
    teacher/
    student/
  vite.teacher.config.ts
  vite.student.config.ts
```

## 常见工作流
### A. 考试上传与分析（老师端）
1. 打开老师端：`http://localhost:3002`
2. 在「上传文件」卡片切换到「考试」
3. 上传 **试卷**（PDF/图片）+ **成绩表**（推荐 xlsx；也支持 xls/PDF/图片）
4. 等待后台解析完成 → 打开草稿 →（可选）修改题目满分/日期/班级 → 保存草稿
5. 点击「创建考试」确认写入：
   - `data/exams/<exam_id>/manifest.json`
   - `data/exams/<exam_id>/derived/*.csv`
   - `data/analysis/<exam_id>/draft.json`（分析草稿）
6. 在对话框可直接输入：
   - `列出考试`
   - `查看考试 EX_... 概览`
   - `分析考试 EX_...`
   - `查看 EX_... 学生列表`
   - `查看 EX_... 学生 高二2403班_武熙语`
   - `查看 EX_... 第3题`（或 `question_id=Q3`）

### B. 课堂采集 → 课后诊断
1. `physics-lesson-capture` 进行 OCR + 例题抽取
2. `physics-homework-generator` 根据课堂讨论生成课后诊断与作业

### C. 学生侧闭环
1. `physics-student-coach` 对话诊断
2. 讨论与反思 → 作业生成
3. 学生拍照提交 → OCR → 画像自动更新

### D. 核心例题
1. 添加核心例题 + 图
2. 记录标准方法与核心模型
3. 生成变式题用于作业

## 重要原则
- 画像是事实源：`data/student_profiles/*.json`
- mem0 是摘要记忆层：只写确认后的短摘要
- 题库优先，自动生成补足
- 不保存原始分数，只保存派生字段

## 快速开始（示例）
### 生成作业并输出 PDF
```bash
python3 skills/physics-student-coach/scripts/select_practice.py \
  --assignment-id A2403_2026-02-04 \
  --kp KP-M01,KP-E04 \
  --per-kp 5 \
  --avoid-days 14 \
  --generate

python3 scripts/render_assignment_pdf.py \
  --assignment-id A2403_2026-02-04
```

### 学生作业提交评分
```bash
python3 scripts/grade_submission.py \
  --student-id 高二2403班_武熙语 \
  --auto-assignment \
  --files /path/to/photo1.jpg
```

### 课堂材料采集
```bash
python3 skills/physics-lesson-capture/scripts/lesson_capture.py \
  --lesson-id L2403_2026-02-04 \
  --topic "静电场综合" \
  --sources /path/to/lesson.pdf
```

### 核心例题（含图片）
```bash
python3 skills/physics-core-examples/scripts/register_core_example.py \
  --example-id CE001 \
  --kp-id KP-M01 \
  --core-model "匀强电场中类抛体运动模型" \
  --stem-file /path/to/stem.md \
  --solution-file /path/to/solution.md \
  --model-file /path/to/model.md \
  --figure-file /path/to/figure.png
```

## 部署（Docker + Coolify + GHCR）
### 1) docker-compose
默认使用本地内嵌 Qdrant（持久化到 `.qdrant/`）。如需独立 Qdrant，可启用 profile。

```bash
docker compose up -d
# 可选启用独立 Qdrant
docker compose --profile qdrant up -d
```

### 2) 端口
- API: `8000`
- MCP: `9000`
- 学生端 Frontend: `3001`
- 老师端 Frontend: `3002`

### 3) 持久化目录
- `data/` 教学与诊断数据
- `.qdrant/` 向量库
- `.mem0/` mem0 缓存
- `uploads/` 上传文件

### 4) GitHub Actions → GHCR
已内置 workflow：`.github/workflows/docker.yml`  
推送 `main` 自动构建并推送：
- `ghcr.io/<owner>/<repo>/api`
- `ghcr.io/<owner>/<repo>/mcp`
- `ghcr.io/<owner>/<repo>/frontend`

### 5) Frontend（Vite + PWA）
前端已内置 PWA 支持，可直接“添加到主屏”。  
可通过构建变量设置 API 地址：
- `VITE_API_URL`
- `VITE_MCP_URL`

---

## 本地开发（推荐）
### 1) 启动 API（FastAPI）
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt
uvicorn services.api.app:app --reload --port 8000
```

### 2) 启动 MCP（可选）
```bash
pip install -r services/mcp/requirements.txt
uvicorn services.mcp.app:app --reload --port 9000
```

### 3) 启动前端（学生端/老师端分离）
```bash
cd frontend
npm install
npm run dev:teacher
npm run dev:student
```

默认访问：
- 学生端：`http://localhost:3001`
- 老师端：`http://localhost:3002`

---

## 前端使用说明（师生分端）
- **老师端**：支持 `@技能` 提示与快捷插入，技能栏可折叠与滚动，支持富文本与 LaTeX。  
- **学生端**：仅支持提问学科问题与提交作业，支持富文本与 LaTeX。  

---

## 模型切换与 .env 配置
项目已内置统一的模型切换网关，配置文件位于 `config/model_registry.yaml`，默认会读取 `.env` 环境变量。

### 配置优先级
1) `LLM_*` 显式配置  
2) 各厂商的专用环境变量（如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`）  
3) `config/model_registry.yaml` 的默认值

### 通用变量（模型网关）
- `MODEL_REGISTRY_PATH`：自定义 registry 路径（默认 `config/model_registry.yaml`）
- `LLM_PROVIDER`：目标厂商（如 `openai` / `deepseek` / `kimi` / `gemini` / `siliconflow`）
- `LLM_MODE`：调用模式（`openai-response` / `openai-chat` / `openai-complete` / `gemini-native` / `gemini-openai`）
- `LLM_MODEL`：目标模型名称
- `LLM_API_KEY`：统一 API Key（若设置，会覆盖厂商专用 key）
- `LLM_TIMEOUT_SEC`：超时时间（秒）
- `LLM_RETRY`：失败重试次数
- `LLM_MAX_CONCURRENCY`：单个 API 进程内允许的最大 LLM 并发（默认 `8`）
- `OCR_MAX_CONCURRENCY`：单个 API 进程内允许的最大 OCR 并发（默认 `4`）
- `OCR_TIMEOUT_SEC`：OCR 超时时间（秒；`0/none` 表示不限制）

---

## 提示词版本与配置
System Prompt 采用“分层、模块化、可版本化”组织方式，位于 `prompts/<version>/`。

### 环境变量
- `PROMPT_VERSION`：提示词版本（默认 `v1`）
- `PROMPTS_DIR`：提示词目录（默认 `./prompts`）
- `PROMPT_DEBUG`：设为 `1` 时在编译后的 prompt 中加入模块标记（仅调试用）

### OpenAI（含 Responses / Chat / Completions）
- `OPENAI_API_KEY`
- `OPENAI_RESPONSE_MODEL`
- `OPENAI_CHAT_MODEL`
- `OPENAI_COMPLETION_MODEL`

### SiliconFlow（默认兼容入口）
- `SILICONFLOW_API_KEY`
- `SILICONFLOW_BASE_URL`
- `SILICONFLOW_LLM_MODEL`

### DeepSeek（OpenAI 兼容）
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`

### Kimi（Moonshot，OpenAI 兼容）
- `MOONSHOT_API_KEY`
- `KIMI_BASE_URL`
- `KIMI_MODEL`

### Gemini（原生 / OpenAI 兼容）
- `GEMINI_API_KEY`
- `GEMINI_BASE_URL`
- `GEMINI_OPENAI_BASE_URL`
- `GEMINI_MODEL`

### 示例：OpenAI Responses
```bash
LLM_PROVIDER=openai
LLM_MODE=openai-response
OPENAI_API_KEY=sk-xxx
OPENAI_RESPONSE_MODEL=gpt-4.1-mini
```

### 示例：DeepSeek（OpenAI 兼容）
```bash
LLM_PROVIDER=deepseek
LLM_MODE=openai-chat
DEEPSEEK_API_KEY=xxx
DEEPSEEK_MODEL=deepseek-chat
```

### 示例：Gemini 原生
```bash
LLM_PROVIDER=gemini
LLM_MODE=gemini-native
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-1.5-flash
```

---

## 接口文档
- HTTP API：`docs/http_api.md`
- MCP 协议：`docs/mcp_api.md`

---

## 安全与提示词测试
- 提示词注入测试样例：`tests/prompt_injection_cases.jsonl`
- 说明文档：`tests/prompt_injection_README.md`

---
如需扩展或调整流程，请在各技能的 `SKILL.md` 中查看详细说明。
