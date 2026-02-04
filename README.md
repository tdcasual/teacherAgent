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
```

## 常见工作流
### A. 考试分析
1. 解析成绩 → 生成草案 → 讨论确认 → 写入分析版本
2. 生成课前检测与课后诊断

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
- Frontend: `3000`

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
如需扩展或调整流程，请在各技能的 `SKILL.md` 中查看详细说明。
