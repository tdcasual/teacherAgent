# Physics Teaching Helper Agent
[![Teacher E2E](https://github.com/tdcasual/teacherAgent/actions/workflows/teacher-e2e.yml/badge.svg?branch=main)](https://github.com/tdcasual/teacherAgent/actions/workflows/teacher-e2e.yml)

本项目是一套面向物理教学的多技能 agent 系统，覆盖考试分析、课堂内容采集、课后诊断、学生个性化辅导、题库与核心例题管理等完整流程。

## 核心能力
- 解析考试成绩（xls/xlsx）、试卷、参考答案，生成考试分析与讨论稿
- 课堂内容采集（PDF/Word/图片 OCR）并结构化保存
- 课前检测清单、课后诊断与个性化作业生成
- 学生对话诊断、学习讨论（Socratic）、费曼反思、作业发放
- 学生作业拍照 OCR 评分与画像自动更新
- 核心例题库：标准解法、核心模型、变式模板
- 老师端高权限图表执行：可通过 `chart.exec` 运行 Python 代码并返回 Markdown 图片
- 图表智能体支持 `opencode` 链路：`chart.agent.run` 默认走 `engine=opencode`（可切换 `auto|llm`），并可按需覆盖 opencode 的 model/agent/attach 参数

## API 模块化（app.py）
`services/api/app.py` 当前作为 FastAPI 组合层，核心路由编排按领域拆分到独立服务：
- `exam_api_service.py`
- `assignment_api_service.py`
- `student_profile_api_service.py`
- `teacher_routing_api_service.py`
- `chart_api_service.py`
- `chat_api_service.py`
- `teacher_memory_api_service.py`
- `upload_io_service.py`
- `llm_agent_tooling_service.py`

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

### 7) `physics-llm-routing`
老师侧模型路由管理：按任务类型配置多渠道模型，支持仿真、提案生效与回滚。

## 目录结构（核心）
```
skills/
  physics-teacher-ops/
  physics-homework-generator/
  physics-lesson-capture/
  physics-student-coach/
  physics-student-focus/
  physics-core-examples/
  physics-llm-routing/

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
- mem0 是摘要记忆层：老师端记忆写入后自动做语义索引（受开关控制）
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

另有老师端回归工作流：`.github/workflows/teacher-e2e.yml`  
在 `pull_request` 与 `push(main)` 上运行 `npm run e2e:teacher`，并上传 `playwright-report` 与 `test-results` 作为构建产物。

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

### 4) 运行老师端 E2E 回归（Playwright）
```bash
cd frontend
npx playwright install --with-deps chromium
npm run e2e:teacher
```

默认访问：
- 学生端：`http://localhost:3001`
- 老师端：`http://localhost:3002`

---

## 前端使用说明（师生分端）
- **老师端**：支持 `@agent` 与 `$skill` 召唤提示与快捷插入，技能栏可折叠与滚动，支持富文本与 LaTeX。  
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
- `LLM_MAX_CONCURRENCY_STUDENT`：学生端/学生请求的最大 LLM 并发（默认继承 `LLM_MAX_CONCURRENCY`）
- `LLM_MAX_CONCURRENCY_TEACHER`：老师端/老师请求的最大 LLM 并发（默认继承 `LLM_MAX_CONCURRENCY`）
- `OCR_MAX_CONCURRENCY`：单个 API 进程内允许的最大 OCR 并发（默认 `4`）
- `OCR_TIMEOUT_SEC`：OCR 超时时间（秒；`0/none` 表示不限制）
- `CHAT_MAX_MESSAGES`：聊天上下文保留的最大消息数（默认 `14`）
- `CHAT_MAX_MESSAGES_STUDENT`：学生端聊天上下文保留的最大消息数（默认 `40`，若未设置则按 `CHAT_MAX_MESSAGES` 推导）
- `CHAT_MAX_MESSAGES_TEACHER`：老师端聊天上下文保留的最大消息数（默认 `40`，若未设置则按 `CHAT_MAX_MESSAGES` 推导）
- `CHAT_MAX_MESSAGE_CHARS`：单条消息最大长度（默认 `2000`）
- `CHAT_EXTRA_SYSTEM_MAX_CHARS`：学生端追加系统信息最大长度（默认 `6000`）
- `CHAT_STUDENT_INFLIGHT_LIMIT`：同一学生允许的并发生成请求数（默认 `1`）
- `CHAT_WORKER_POOL_SIZE`：聊天异步 worker 数量（lane-aware 队列消费线程数，默认 `4`）
- `CHAT_LANE_MAX_QUEUE`：单个会话 lane 允许的最大排队量（排队+执行中，默认 `6`）
- `CHAT_LANE_DEBOUNCE_MS`：同一 lane 相同输入的去抖时间窗（毫秒，默认 `500`）
- `CHAT_JOB_CLAIM_TTL_SEC`：聊天任务 claim.lock 的过期时间（秒；用于多进程防重复处理，默认 `600`）
- `OPENCODE_BRIDGE_ENABLED`：是否启用 opencode 图表桥接（默认由 `config/opencode_bridge.yaml` 决定）
- `OPENCODE_BRIDGE_FILE`：opencode 桥接配置文件路径（默认 `config/opencode_bridge.yaml`）
- `OPENCODE_BRIDGE_BIN`：opencode 可执行文件（默认 `opencode`）
- `OPENCODE_BRIDGE_MODE`：`run` 或 `attach`
- `OPENCODE_BRIDGE_ATTACH_URL`：attach 模式地址（如 `http://127.0.0.1:4096`）
- `OPENCODE_BRIDGE_AGENT` / `OPENCODE_BRIDGE_MODEL`：默认 agent 与模型
- `OPENCODE_BRIDGE_TIMEOUT_SEC` / `OPENCODE_BRIDGE_MAX_RETRIES`：opencode 代码生成阶段超时与重试
- `PROFILE_CACHE_TTL_SEC`：学生画像读取缓存 TTL（秒，默认 `10`）
- `ASSIGNMENT_DETAIL_CACHE_TTL_SEC`：作业详情读取缓存 TTL（秒，默认 `10`）
- `PROFILE_UPDATE_ASYNC`：学生端聊天后画像更新是否走异步队列（默认 `1`）
- `PROFILE_UPDATE_QUEUE_MAX`：画像更新队列最大长度（默认 `500`）
- `DEFAULT_TEACHER_ID`：老师端工作区/记忆的默认标识（默认 `teacher`）
- `TEACHER_SESSION_COMPACT_ENABLED`：老师会话是否启用自动压缩（默认 `1`）
- `TEACHER_SESSION_COMPACT_MAIN_ONLY`：是否仅压缩老师 `main` 会话（默认 `1`）
- `TEACHER_SESSION_COMPACT_MAX_MESSAGES`：触发压缩的消息阈值（默认 `160`）
- `TEACHER_SESSION_COMPACT_KEEP_TAIL`：压缩后保留的最近消息数（默认 `40`）
- `TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC`：同一会话两次压缩的最小间隔秒数（默认 `60`）
- `TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS`：用于生成压缩摘要的最大文本长度（默认 `12000`）
- `TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY`：老师端是否将会话压缩摘要注入系统上下文（默认 `1`）
- `TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS`：注入的会话摘要最大长度（字符；默认 `1500`）
- `TEACHER_MEMORY_AUTO_ENABLED`：是否启用老师端自动记忆（默认 `1`）
- `TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS`：自动记忆最小有效内容长度（默认 `12`）
- `TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY`：单老师每天最多自动写入数量（默认 `8`）
- `TEACHER_MEMORY_AUTO_APPLY_ENABLED`：是否启用提案创建后自动应用（默认 `1`）
- `TEACHER_MEMORY_AUTO_APPLY_TARGETS`：允许自动应用的 target 列表（默认 `DAILY,MEMORY`）
- `TEACHER_MEMORY_AUTO_APPLY_STRICT`：自动应用严格模式（敏感信息拦截、冲突替换等，默认 `1`）
- `TEACHER_MEMORY_AUTO_INFER_ENABLED`：是否启用“无记住口令”的重复偏好自动推断（默认 `1`）
- `TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS`：触发自动推断所需的近似重复次数（默认 `2`，含当前轮）
- `TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS`：自动推断回看最近老师发言轮数（默认 `24`）
- `TEACHER_MEMORY_AUTO_INFER_MIN_CHARS`：自动推断最小有效内容长度（默认 `16`）
- `TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY`：自动推断提案最低优先级（0-100，默认 `58`；低于阈值只记录跳过事件不落盘）
- `TEACHER_MEMORY_DECAY_ENABLED`：是否启用记忆衰减与过期过滤（默认 `1`）
- `TEACHER_MEMORY_TTL_DAYS_MEMORY`：长期记忆默认 TTL 天数（默认 `180`，`0` 表示不过期）
- `TEACHER_MEMORY_TTL_DAYS_DAILY`：每日记忆默认 TTL 天数（默认 `14`，`0` 表示不过期）
- `TEACHER_MEMORY_CONTEXT_MAX_ENTRIES`：老师上下文注入时保留的活跃记忆条数上限（默认 `18`）
- `TEACHER_MEMORY_SEARCH_FILTER_EXPIRED`：检索结果是否过滤过期记忆（默认 `1`）
- `TEACHER_MEMORY_FLUSH_ENABLED`：是否启用“接近压缩阈值”自动 flush（默认 `1`）
- `TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES`：距离压缩阈值多少条消息时触发 flush（默认 `24`）
- `TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS`：flush 可写入的近期对话摘录上限（默认 `2400`）
- `TEACHER_MEM0_ENABLED`：老师端是否启用 mem0 语义检索（默认 `0`）
- `TEACHER_MEM0_WRITE_ENABLED`：老师端在 `teacher.memory.apply` 时是否写入 mem0（默认 `1`，但需先启用 `TEACHER_MEM0_ENABLED`）
- `TEACHER_MEM0_INDEX_DAILY`：是否将 `target=DAILY` 的每日记录也写入 mem0（默认 `0`）
- `TEACHER_MEM0_TOPK`：mem0 搜索返回条数（默认 `5`）
- `TEACHER_MEM0_THRESHOLD`：mem0 最低相似度阈值（默认 `0.0`）
- `TEACHER_MEM0_CHUNK_CHARS`：写入 mem0 的分块大小（字符；默认 `900`）
- `TEACHER_MEM0_CHUNK_OVERLAP_CHARS`：写入 mem0 的分块重叠（字符；默认 `100`）

### 老师端默认记忆规则
- 出现明确长期信号（如“以后/默认/统一/固定”）时，优先写入 `MEMORY.md`。
- 未出现“记住”口令时，若在最近对话中重复出现同类稳定偏好（输出结构/格式/讲解风格/作业参数），会自动推断并写入 `MEMORY.md`。
- 含明显时效词（如“今天/本周/这次/临时/暂时”）的内容优先写入 `memory/YYYY-MM-DD.md`。
- 命中敏感模式（key/token/password 等）会被自动拦截，不会写入工作区。
- 每条记忆会计算 `priority_score` 并带有 TTL；检索与上下文注入默认只使用“未过期、未被替代”的活跃记忆。

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
