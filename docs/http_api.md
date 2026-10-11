# HTTP API

本文档描述项目提供的 HTTP 接口（FastAPI）。产品主线是**作业**（选 `assignment_kind` × `content_source` → upload / from-bank / generate 进草稿 → `POST /assignment/upload/confirm` **发布草稿** → 学生今日列表 → 显式提交 → progress；做题类才有题库补练），不是考试，也不是问卷/班级报告工作台。Exam HTTP 面已卸载：不要调用 `/exam/*`、`/exams` 或任何 exam 编排接口。Survey / class_report / analysis_report 路由同样不注册。

## 基础信息
- Base URL：`http://localhost:8000`
- Content-Type：`application/json`（除文件上传/表单接口）
- 老师端：`http://localhost:3002`
- 学生端：`http://localhost:3001`

## 实现说明（app.py 模块化）
`services/api/app.py` 作为组合根（composition root），统一通过
`services/api/app_routes.py` 注册各领域路由模块：
- `services/api/routes/chat_routes.py`
- `services/api/routes/student_routes.py`
- `services/api/routes/teacher_routes.py`
- `services/api/routes/skill_routes.py`
- `services/api/routes/assignment_routes.py`

身份与认领路由在 `services/api/routes/auth_routes.py`（含 `POST /auth/admin/assignments/{assignment_id}/claim`）。

## 架构边界约束（2026-02 更新）
- 模块边界规范：`docs/architecture/module-boundaries.md`
- Ownership 映射：`docs/architecture/ownership-map.md`

当前 API 目录遵循以下边界：
- `routes/*`：仅做 HTTP 协议转换，不做业务编排
- `assignment/application.py`：承载 context 用例编排
- `app.py` + `container.py`：组合根与依赖注入入口

学科 pack 不走 HTTP，见下文「学科 Pack」。

---

## Health
### GET `/health`
返回 `{ "status": "ok" }`

---

## 对话
### POST `/chat`
根据师生角色触发多技能 agent。老师默认走 assignment 工作流（上传/确认/进度），不要用对话去驱动 exam 工具。

**请求**
```json
{
  "role": "teacher",
  "messages": [
    { "role": "user", "content": "列出我布置的作业" },
    { "role": "assistant", "content": "已收到" }
  ]
}
```

**响应**
```json
{
  "reply": "……",
  "role": "teacher"
}
```

---

## 老师端模型配置与 Provider 管理

### GET `/teacher/model-config`
读取老师模型用途配置（`conversation`、`embedding`、`ocr`、`image_generation`）与可用目录。

### PUT `/teacher/model-config`
更新老师模型用途配置。

### GET `/teacher/provider-registry`
读取老师私有 Provider 列表（脱敏）及共享+私有合并目录。

### POST `/teacher/provider-registry/providers`
新增私有 Provider（OpenAI-Compatible，支持自定义 `base_url`）。
- 请求字段：
  - `teacher_id`（必填；未认证或空值返回 `teacher_id_required`）
  - `provider_id`（可选，未填自动生成；不可与共享 provider 同名）
  - `display_name`（可选）
  - `base_url`（必填，例如 `https://proxy.example.com/v1`）
  - `api_key`（必填，仅写入时可见，返回仅掩码）
  - `default_model`（可选）
  - `enabled`（可选，默认 `true`）
- 说明：可直接填写中转/代理地址；生产环境默认仅允许 `https://`。

### PATCH `/teacher/provider-registry/providers/{provider_id}`
更新私有 Provider（支持 key 轮换，不回显明文 key）。
- 可更新字段：`display_name`、`base_url`、`default_model`、`enabled`、`api_key`（轮换）。

### DELETE `/teacher/provider-registry/providers/{provider_id}`
禁用私有 Provider（软删除）。

### POST `/teacher/provider-registry/providers/{provider_id}/probe-models`
探测模型列表（依赖上游 `/models` 兼容性；失败不影响手填模型）。

### GET `/teacher/roster`
读取当前老师的任教名册（`teacher_id` + `subject_id` + `class_name`）。老师端上传作业时用它填充学科/班级，而不是硬编码物理。

---

## 技能与列表查询
### GET `/skills`
需要登录。返回当前身份可见的技能：全员作业三件套（`teacher-assignment-ops` / `homework-generator` / `student-coach`），加上该老师名册学科 pack 的 `skill_affiliates`。未任教物理的老师不会看到 `physics-*`。学生没有附属 skill。

### GET `/assignments`
返回当前老师可见的作业列表（分页：`limit`、`cursor`）

### GET `/lessons`
返回已有课程列表

---

## 作业上传（异步 Job）与草稿发布
老师日常主线：工作台先选 `assignment_kind`（`problem_set` / `scenario` / `science_history` / `practical`）再选 `content_source`（`upload` / `bank` / `ai`）。三条来源都进同一草稿区；**发布草稿**仍打本路径的 `POST /assignment/upload/confirm`（路径名是历史包袱，upload / bank / AI 草稿都走它）。发布后看 `GET /teacher/assignment/progress`。

管理员写作业（start / save / confirm / generate / from-bank）仍 403 `forbidden`。

### POST `/assignment/upload/start`
上传作业文件（必填）与答案（可选），创建后台解析任务。`teacher_id` 取自登录 principal，不要在表单里传默认 `teacher`。`content_source` 固定为 `upload`。

**multipart/form-data**
- `assignment_id`（必填）
- `subject_id`（必填；空值 → 400 `subject_id_required`。写入 `meta.json` 并决定 pack overlay）
- `assignment_kind`（可选；闭集 `problem_set` / `scenario` / `science_history` / `practical`。缺省 → `problem_set` 并打日志 `assignment.kind.defaulted`；非法值 → 400 `invalid_assignment_kind`）
- `date`（可选，`YYYY-MM-DD`）
- `due_at`（可选）
- `scope`（public/class/student）
- `class_name` / `student_ids`（按 scope 填写，可选）
- `files`（必填，PDF 或图片；可多文件）
- `answer_files`（可选，PDF 或图片；可多文件）
- `ocr_mode` / `language`（可选）

做题类解析 0 题仍失败。非做题允许 0 题：job 仍 `done`，confirm 时写表头-only `questions.csv`。

### GET `/assignment/upload/status?job_id=...`
查询解析进度与状态。

### GET `/assignment/upload/draft?job_id=...`
获取 **upload job** 草稿（题目列表 + kind-gated 要求）。bank / AI 草稿请用下面的 `GET /assignment/{assignment_id}/draft`。

### POST `/assignment/upload/draft/save`
保存草稿覆盖。Locator = `job_id` **或** `assignment_id`（folder draft，仅 `visibility_status=draft`）。两者都缺 → 400 `job_or_assignment_required`；两者都有时 `job_id` 赢（上传流）。无 `job_id` 时 handler 跳过 job saver，就地写 folder。已发布 → 409 `invalid_visibility_status`。

**JSON**
- `job_id`（可选）
- `assignment_id`（可选；无 job 时必填）
- `requirements` / `questions`（可选）

### POST `/assignment/upload/confirm`
**发布草稿**（写入 / 更新 `data/assignments/<assignment_id>/`，`visibility_status=published`）。Locator 同样是 `job_id` **或** `assignment_id`。

- 有 `job_id`：走上传 2PC 新建 published 目录（今日路径）。
- 仅有 `assignment_id`：handler **跳过** `load_upload_job` 与 job gate，调用 `_finalize_published_from_folder`（更新已有 draft；**不会** 409 `assignment already exists`）。owner 必须是当前老师；vis ≠ draft → 409 `invalid_visibility_status`。
- 两者都缺 → 400 `job_or_assignment_required`。

**JSON**
- `job_id`（可选）
- `assignment_id`（可选；folder 发布时用这个，无 job）
- `requirements_override`（可选）
- `completion_policy_override`（可选；可含 `requires_submission` / `requires_discussion` / `allow_practice`。`requires_discussion=true` 只是展示/陪练提示，**不是**完成门闩）
- `confirm`（默认 `true`）
- `strict_requirements`（默认 `true`）

Confirm 按 kind 校验要求：做题仍是 8 点；非做题必填 `requirements.brief`，不要 typical_problem / 4 条易错。做题 0 题 → 400 `questions_missing`。`content_source=bank` 且 kind ≠ `problem_set` → 400 `bank_requires_problem_set`。缺项 → 400 `requirements_missing`。`content_source=bank` 发布时把题干/答案字节快照进该作业目录，之后改题库不会改已布置作业的评分。

### GET `/assignment/{assignment_id}/draft`
重载 **folder draft**（bank / AI，或已落盘的 upload 草稿）。挂在 `assignment_upload_routes.py`，不要走 `GET /assignment/{assignment_id}`。owner + `visibility_status=draft` only；payload 与 upload draft 同形，`job_id` 省略，含 `assignment_kind` / `content_source`。非 owner → 403；vis ≠ draft → 409 `invalid_visibility_status`；缺目录 → 404。

---

## 作业进度、归档与今日列表

### GET `/teacher/assignment/progress?assignment_id=...`
单份作业完成情况（应交 / 完成 / 已评分 / 逾期）。老师端「作业完成情况」面板读这个接口。可选 `include_students`。每生可有 `practice: {assigned, submitted, open, bank_miss}`（盘上 `practice_*` + `bank_miss.json`）；**不**改变 `counts.submitted` / `official_score` / `overdue`。非做题补练列显示「不适用」。

### GET `/teacher/assignments/progress?date=YYYY-MM-DD`
当天（或指定日）该老师名下作业进度摘要。

### POST `/assignment/{assignment_id}/archive`
归档作业（老师或管理员；须拥有该作业）。

### POST `/assignment/{assignment_id}/unarchive`
取消归档。

### GET `/assignment/today?student_id=...`
学生「今日任务」。按学生已选科目/任课老师列出已布置作业。`auto_generate=true` 返回 **400** `auto_generate_disabled`——空态是「老师尚未布置」，不会自动生成作业。今日列表**不含**补练卡。

每条 `_today_item` 另含：
- `assignment_kind`（缺字段读作 `problem_set`）
- `allow_practice`（仅 `problem_set` 可为 true；非做题恒 false）

### GET `/assignment/{assignment_id}`
作业详情（受可见性/所有权约束）。

### GET `/assignment/{assignment_id}/download?file=...`
下载作业材料（需鉴权；学生只能拿自己可见的文件）。

### GET `/student/assignments/history`
学生「作业记录」（材料 / 官方分 / 未交补交）。与会话侧栏「历史任务」不是同一个入口。学生端画像卡只挂本页，读 `GET /student/profile/{self}` 的 `recent_weak_kp` / `next_focus` / `practice_history`（不要读 `weak_kp`）。

每条 `_history_item` 另含：
- `assignment_kind`
- `allow_practice`
- `practice`: `{assigned, open, submitted, bank_miss}`（非做题可全 0；SPA 不渲染补练入口）

---

## 孤儿作业认领

迁移后没有合法 `teacher_id` / `subject_id` 的作业会变成 `visibility_status=orphan_draft`，不进老师列表，也不进学生今日任务。只有管理员可以认领。

### GET `/auth/admin/assignments/orphans`
列出孤儿作业。需 admin Bearer。老师访问 **403**；无 token **401**（即使 `AUTH_REQUIRED=0` 也不走 `admin_local`）。

**响应**
```json
{
  "ok": true,
  "count": 1,
  "items": [
    {
      "assignment_id": "HW-orphan",
      "teacher_id": "",
      "subject_id": "",
      "visibility_status": "orphan_draft",
      "needs_subject_review": true,
      "needs_roster_review": false,
      "scope": "class"
    }
  ]
}
```

### POST `/auth/admin/assignments/{assignment_id}/claim`
把孤儿作业认领到指定老师 + 学科。需 admin Bearer。

**JSON**
- `teacher_id`（必填；禁止默认 id `teacher` → 400 `default_teacher_id_forbidden`）
- `subject_id`（必填；必须已在 identity graph 中 → 否则 400 `subject_not_found`）
- `visibility_status`（可选，`draft` 或 `published`，默认 `draft`）

认领前该老师在该学科必须已有名册，否则 400 `roster_required`。已认领过的作业再 claim → 409 `not_orphan`。老师自己 claim → 403。

成功时写入 `meta.json` 的 `teacher_id` / `subject_id` / `pack_id` / `visibility_status`，并按名册填充 `expected_students`。

**请求**
```json
{
  "teacher_id": "t_zhang",
  "subject_id": "physics",
  "visibility_status": "published"
}
```

**响应**
```json
{
  "ok": true,
  "assignment_id": "HW-orphan",
  "teacher_id": "t_zhang",
  "subject_id": "physics",
  "visibility_status": "published",
  "expected_students": ["S001"]
}
```

---

## 学科 Pack（文件系统，不是 HTTP）

作业的学科 overlay / 可选 grader 从 pack 目录读取，路径：

```
packs/subjects/<id>/
  pack.yaml
  prompts/student_overlay.md
  prompts/teacher_overlay.md
```

- 默认根目录：仓库 `packs/subjects/`，可用环境变量 `SUBJECT_PACKS_DIR` 覆盖。
- `<id>` 必须匹配 `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`。装载器只打开该根下的 `packs/subjects/<id>/pack.yaml`，拒绝路径逃逸。
- 内置示例：`packs/subjects/generic/`、`packs/subjects/physics/`。
- **找不到或损坏的 subject 一律回退 `generic`，永不回退物理。** `generic` pack 缺失则失败（`SubjectPackError`），没有第二默认学科。
- 作业 `meta.pack_id` 优先于 `meta.subject_id`。认领孤儿作业时 `pack_id` 取该学科在 identity graph 里登记的值，缺省则等于 `subject_id`。
- `pack.yaml` 的 `skill_affiliates` 只给任教该 `subject_id` 的老师并入 `GET /skills` 与聊天自动路由。布置作业不依赖附属 skill，只依赖 `subject_id` 与 overlay。
- 聊天 overlay 与提交评分读同一套 pack；不要在 HTTP 里再发明 `/packs` 接口。

装载实现：`services/api/subject_pack_service.py`。

---

## 学生画像
### GET `/student/profile/{student_id}`
读取学生画像 JSON。学生端「作业记录」页画像卡读 `recent_weak_kp` / `next_focus` / `practice_history`，不要读 `weak_kp`。授权仍走 `resolve_student_scope`。

### POST `/student/profile/update`
**表单字段**
- `student_id`（必填）
- `weak_kp` / `strong_kp` / `medium_kp`（可选）
- `next_focus` / `interaction_note`（可选）

---

## 学生导入
### POST `/auth/admin/students/import`
管理员导入名册 CSV，**只写 `student_auth`，不 enroll**。`multipart` 一个文件，上限 2000 行 / 256KB，UTF-8（允许 BOM）。

- 表头白名单：必填 `student_name,class_name`；可选 `student_id`；多余列 → 400 `unknown_column`
- 提供的 `student_id` 须 6–64 位字母数字、下划线或连字符（与 `safe_fs_id` 一致）；省略则生成 `s_` + sha1(normalize(class_name)+'|'+normalize(student_name))[:12]
- 重导默认不轮换密码；表单字段 `reset_passwords=true` 才会重置
- 学生端仍走 `POST /auth/student/identify`（姓名+班级）再密码登录；identify 读 `student_auth`，导入不必写 `student_profiles`
- 需要管理员 Bearer；`AUTH_REQUIRED=0` 且无 Bearer 仍 401
- 编班走已有 `POST /auth/admin/roster` 与 `POST /auth/admin/enrollments/enroll-class`

### POST `/student/import`
已停用（原 exam responses 导入）。一律 **410** `gone`。

---

## 作业生成、题库草稿与渲染
工作台三条草稿来源之一。AI / 题库结果都进同一 `AssignmentDraftSection`，**必须**再 `POST /assignment/upload/confirm`（或工具 `assignment.publish`，同一套 folder 发布校验）才对学生可见。学生永不调用这些接口。

### POST `/assignment/generate`
老师 AI 起草（`content_source` 本端点缺省 `ai`）。缺 `assignment_kind` → 默认 `problem_set` + 日志 `assignment.kind.defaulted`（不是 400）；非法 kind → 400 `invalid_assignment_kind`。传入 `content_source` 且不是 `ai` → 400 `generate_requires_content_source_ai`。无 teacher principal → 400 `teacher_id_required`。

**表单字段**
- `assignment_id`（必填）
- `subject_id`（必填；空值 → 400 `subject_id_required`）
- `assignment_kind`（可选；闭集同上。preflight / 旧客户端可省略）
- `content_source`（可选，缺省 `ai`）
- `seed`（可选短提示；非做题 AI 用它起草 brief，**不是**已完成 brief。Confirm 仍要 `requirements.brief`）
- `kp`（做题必填思路仍是知识点列表；非做题改为可选）
- `per_kp`（默认 5）
- `core_examples`（可选）
- `generate`（布尔；**HTTP Form 默认 `true`**。做题：默认走 LLM leftover / `make_generated`；显式 `false` = 只选题，不足 409 `question_bank_insufficient`，不编占位题。非做题：**忽略**该旗标，走 LLM brief，不 400）
- `date` / `due_at` / `class_name` / `student_ids`（可选）
- `requirements_json` / `question_ids` / `mode` / `source`（可选；`mode` 仍是内部 pick 算法 `kp|explicit|hybrid|auto`，不是产品轴 `content_source`）

做题：写 `questions.csv` + draft `meta.json`（`content_source=ai`、`visibility_status=draft`）。非做题：LLM 写 `brief` / `discussion_goals` / 可选 rubric，**不**伪造 `questions.csv` 数据行；LLM 失败或空 brief → 400 `generate_failed`。返回含 `draft` 对象（questions / requirements / missing / kind / source，`job_id` 省略）。

MCP **不**注册 `assignment.generate`。需要生成时走本接口或老师聊天。工具路径省略 `generate` 键时默认 **true**（`args.get("generate", True)`）。

### POST `/assignment/draft/from-bank`
老师从 `DATA_DIR/question_bank` 选题进 **draft**。服务端强制 `assignment_kind=problem_set`、`content_source=bank`。teacher/admin Bearer；admin 写作业仍 403（与 generate 相同）。学生不得调。空库或 0 命中 → 409 `question_bank_insufficient`，不写 draft，**永不** `make_generated`。已有 folder / SQL 行且不是当前老师自己的 draft → 409 `assignment already exists`。自己的 draft 允许覆盖选题。

**multipart/form-data**
- `assignment_id`（必填）
- `subject_id`（必填）
- `kp`（可选，逗号分隔）
- `count`（1–20，默认 5）
- `date` / `due_at` / `class_name` / `student_ids`（可选）

命中则写 `DATA_DIR/assignments/<id>/`：`questions.csv`、`meta.json`（`visibility_status=draft`）。返回与 upload draft 同形的 JSON（`job_id` 省略）。**发布**仍走 confirm + `assignment_id`；confirm 时快照 stem/answer 字节。`expected_students` 以 confirm 为准。

### POST `/assignment/render`
**表单字段**
- `assignment_id`（必填）

---

## 作业提交
### POST `/student/submit`
学生端提交面板调用此接口。聊天附件不会自动记为提交。**对话不是提交。** 本接口 **不** 自动选题库补练。

按钮文案随 `assignment_kind`：做题「提交作业」；情景/科学史「提交书面/照片」；实践「提交实践照片」。

**multipart/form-data**
- `student_id`（必填；受登录作用域约束）
- `files`（必填，支持多文件）
- `assignment_id`（必填）
- `auto_assignment`（若为 `true` → 400 `auto_assignment_disabled`）

成功时 HTTP 200。`submitted=false` 表示这次没有记为提交，不是传输失败。`reason=min_graded_total` 为有效评分不足；`reason=progress_unavailable` 为提交后未能读到 progress，不能当成评分不足。学生首页「已提交」只认 progress API，不看聊天完成。

`questions.csv` 无数据行（情景/实践常见）：跳过逐题 OCR，写 `received_without_items=true` 的报告，记为已交；`official_score` 仍 null 直到老师覆盖。做题 OCR 失败仍是 ungraded / `submitted=false`，不要套 received。提交成功后进程内派生画像（`recent_weak_kp` 等）；`POST /chat` 不再写 KP。

---

## 学生补练（仅做题）
路由：`services/api/routes/student_practice_routes.py`。body/query **不收** `student_id`，只信 principal。无 principal（含 `AUTH_REQUIRED=0`）→ 400 **`principal_required`**。`meta.student_id` ≠ actor → 403 `forbidden_student_scope`。补练不进 `GET /assignment/today`，也不写入 `student_submission_attempts`。

仅当 `assignment_kind=problem_set` 且 `allow_practice` 且该生该作业已有 qualifying homework submit（`valid_submission`）。否则：
- kind 非做题或 `allow_practice=false` → 409 `practice_not_applicable`
- 作业未交 → 409 `homework_not_submitted`
- 题库 0 命中 → 409 `question_bank_insufficient`（并写 `bank_miss.json`）

学生 SPA：补练按钮 **仅当** `problem_set && allow_practice && submitted` 才渲染（未交 / 非做题都没有入口，因此不需要 `homework_not_submitted` toast）。`ERROR_CODE_MESSAGES` 只把 `question_bank_insufficient` 映成「题库不足」。API 仍可能对未交作业返回 409 `homework_not_submitted`（防御码，不是 SPA 文案）。

### POST `/student/assignment/{assignment_id}/practice`
推荐一轮补练或返回已有 `open`。同一学生同一作业最多 1 个 open。成功 200，建 `practice_*`。无 body `student_id`。

### GET `/student/assignment/{assignment_id}/practice`
该生该作业补练列表（stem，无解答）+ `bank_miss`。kind 不适用时同样 409 `practice_not_applicable`。

### POST `/student/assignment/{assignment_id}/practice/{practice_id}/submit`
multipart，后缀同 `STUDENT_ALLOWED_SUFFIXES`。只打开 `student_submissions/<assignment_id>/<actor_id>/<practice_id>/`。缺目录或非 `practice_` 前缀 → 404。评分走 `grade_submission.py --attempt-dir`，**不**创建 `submission_*`；泄漏则删除并 500 `attempt_dir_leak`。响应含 `ok`、`submitted`（此字段=该次补练已交）、`official_score=null`、`practice_id`。补练不改作业官方分。

---

## 文件上传
### POST `/upload`
**multipart/form-data**
- `files`（必填，支持多文件）
