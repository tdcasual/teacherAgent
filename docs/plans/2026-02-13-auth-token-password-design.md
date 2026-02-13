# 学生/教师 Token + 密码认证改造设计

日期：2026-02-13  
状态：已评审确认（设计阶段）  
关联约束：`chart.exec` 默认 `trusted` 不改动（本方案不触碰该链路）

## 1. 背景与目标

当前学生端主要通过姓名/班级识别身份，教师端通过本地 teacher_id 相关配置参与请求。该方式在“重名”“弱鉴别”“凭据可撤销性”方面不足，且无法形成统一的密码与 token 并存认证体系。

本次目标是引入统一认证闭环：

- 学生端：`姓名 + 班级` 仅用于定位账号；认证必须再提供 `token 或密码`。
- 学生可使用 token 设置密码；设置后仍可使用 token 或密码认证。
- 教师端：`姓名 + token/密码` 认证；若仅姓名无法唯一定位，要求邮箱辅助去歧义。
- token 自动生成，可由教师端查看/重置/导出分发。
- 登录成功后统一签发 Bearer token，后续接口使用同一鉴权方式。

非目标：

- 不改 `chart.exec` 的默认执行策略。
- 不在本次引入外部 IAM/OIDC。
- 不重构全部业务域模型，仅新增认证域并平滑接入。

## 2. 范围与需求

### 2.1 学生认证需求

1. 先 identify（姓名+班级）再 authenticate（token/密码），不允许仅 identify 直接进入已认证态。
2. 若学生未设密码，可用 token 登录后设置密码。
3. 设置密码后保留 token 登录能力（双通路）。
4. 对重名场景返回候选并要求补班级。

### 2.2 教师认证需求

1. 教师先用姓名 identify。
2. 若姓名不唯一，接口返回“需邮箱去歧义”并由前端补邮箱后再 identify。
3. identify 唯一后使用 token 或密码认证。

### 2.3 管理与运维需求

1. token 自动生成，后端仅存 hash。
2. 支持重置 token（旧 token 立即失效）。
3. 支持批量导出 token（CSV）用于线下分发。
4. 全链路具备审计日志（谁在何时为谁重置/导出）。

## 3. 架构方案

采用“认证域独立存储”方案（推荐）：

- 新增认证存储：`data/auth/auth_registry.sqlite3`
- 业务 profile 继续留在原有 `student_profiles`/teacher 相关域，不混存凭据。
- 新增 `auth_registry_service`（读写认证记录、哈希校验、锁定策略）
- 新增 `auth_login_service`（identify/login/set-password/reset-token）
- 新增 `auth_admin_service`（批量导出、审计）

优势：

- 安全边界清晰，避免凭据散落在 JSON 文件。
- SQLite 可用索引/唯一约束表达歧义分支与去歧义查询。
- 易做原子更新、版本化失效与审计。

## 4. 数据模型设计

建议两张主表：

### 4.1 `student_auth`

- `student_id TEXT PRIMARY KEY`
- `name_norm TEXT NOT NULL`
- `class_norm TEXT NOT NULL`
- `token_hash TEXT NOT NULL`
- `token_hint TEXT`（仅提示，如末 4 位）
- `password_hash TEXT`（未设置为空）
- `password_algo TEXT`（如 argon2id）
- `password_set_at TEXT`
- `token_version INTEGER NOT NULL DEFAULT 1`
- `token_rotated_at TEXT`
- `failed_count INTEGER NOT NULL DEFAULT 0`
- `locked_until TEXT`
- `is_disabled INTEGER NOT NULL DEFAULT 0`
- `updated_at TEXT NOT NULL`

索引：

- `idx_student_name_class(name_norm, class_norm)`

### 4.2 `teacher_auth`

- `teacher_id TEXT PRIMARY KEY`
- `name_norm TEXT NOT NULL`
- `email_norm TEXT`
- 其余字段同 `student_auth`

索引：

- `idx_teacher_name(name_norm)`
- `idx_teacher_name_email(name_norm, email_norm)`

### 4.3 审计表 `auth_audit_log`

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `actor_id TEXT`
- `actor_role TEXT`
- `action TEXT`（reset_token / export_tokens / set_password / login_failed 等）
- `target_id TEXT`
- `target_role TEXT`
- `detail_json TEXT`
- `created_at TEXT`

## 5. 接口契约（草案）

### 5.1 学生

- `POST /auth/student/identify`
  - 入参：`name`, `class_name`
  - 出参：
    - 唯一：`{ ok: true, candidate_id, student: {...} }`
    - 多条：`{ ok: false, error: "multiple", candidates: [...] }`
    - 无结果：`{ ok: false, error: "not_found" }`

- `POST /auth/student/login`
  - 入参：`candidate_id`, `credential_type: "token"|"password"`, `credential`
  - 出参：`{ ok: true, access_token, expires_in, role: "student", subject_id }`

- `POST /auth/student/set-password`
  - 入参：`candidate_id`, `credential_type`, `credential`, `new_password`
  - 要求：先通过 token 或旧密码验证，后设置新密码

### 5.2 教师

- `POST /auth/teacher/identify`
  - 入参：`name`, `email?`
  - 出参：
    - 唯一：`{ ok: true, candidate_id, teacher: {...} }`
    - 歧义：`{ ok: false, error: "multiple", need_email_disambiguation: true }`

- `POST /auth/teacher/login`
  - 入参：`candidate_id`, `credential_type`, `credential`
  - 出参同学生登录

### 5.3 管理

- `POST /auth/admin/student/reset-token`
- `POST /auth/admin/teacher/reset-token`
- `POST /auth/admin/student/export-tokens`（CSV）
- `POST /auth/admin/teacher/export-tokens`（CSV）

## 6. 认证与安全策略

1. **Token 生成与存储**
   - 使用高熵随机值（至少 32 字节随机源）。
   - 库内仅保存 hash（推荐 HMAC-SHA256 + server pepper）。
   - 明文 token 仅在生成/重置返回一次。

2. **密码策略**
   - `argon2id`（优先）或 `bcrypt`。
   - 强制最小长度与基本复杂度策略（可配置）。
   - 常量时间比较，避免时序侧信道。

3. **失败与锁定**
   - 失败计数阈值（例如 5 次）后短时锁定（如 15 分钟）。
   - IP + principal 双维度限流。

4. **token 轮换失效**
   - 通过 `token_version` / `token_rotated_at` 让旧 token 立即失效。
   - Bearer token 验证时增加版本校验（或等效时间戳比较）。

5. **错误信息最小化**
   - 未认证端返回统一错误语义，不泄露“账号是否存在”的过细信息。

## 7. 前端改造设计

### 7.1 学生端

登录 UI 改为两步：

1. Identify：输入姓名、班级，调用 `/auth/student/identify`。
2. Authenticate：输入 token 或密码，调用 `/auth/student/login`。

首次设密：

- 若后端返回 `password_not_set=true`，展示“设置密码”入口。
- 通过 `/auth/student/set-password` 完成设置。

状态管理：

- 新增 `authState: unauthenticated | identifying | credential_required | authenticated`
- 认证成功后将 access token 注入后续 API 请求头。

### 7.2 教师端

登录 UI：

1. 输入姓名 identify；
2. 若 `need_email_disambiguation=true`，显示邮箱输入并再次 identify；
3. 唯一后输入 token 或密码登录。

兼容本地 `teacherRoutingTeacherId`：

- 登录成功后以服务端 subject_id 为准同步覆盖旧本地值，避免漂移。

## 8. 回滚与发布策略

阶段化发布：

1. 新接口上线，不强制旧流量切换。
2. 学生/教师前端切新登录页，灰度开关控制。
3. 灰度稳定后，对核心业务接口开启“必须 Bearer token”。
4. 保留兼容窗口后下线旧 verify-only 入口。

回滚：

- 保留旧登录入口与旧前端开关；新认证异常时可快速切回。
- 新增认证库为旁路，不影响原 profile 数据。

## 9. 测试计划

### 9.1 后端

- identify：唯一/多条/无结果分支
- login：token 成功/失败、密码成功/失败、锁定策略
- set-password：首次设置、旧密码更新、弱密码拒绝
- reset/export：权限校验、审计日志落盘、旧 token 失效
- Bearer token：版本轮换后失效验证

### 9.2 前端

- 学生：两步登录、首次设密、token/密码双通路
- 教师：姓名歧义 + 邮箱去歧义流程
- 登录后关键页面请求均带 `Authorization`
- 失败提示为用户友好文案，不透出内部细节

### 9.3 E2E

- 重名学生 + 同班去歧义
- 重名教师 + 邮箱辅助
- token 重置后旧 token 立即不可用

## 10. 风险与待确认

1. token 批量导出的权限边界（仅 admin，还是 teacher 可导出其班级/名下）
2. teacher_id 与姓名/邮箱的历史数据完整性（需一次数据体检）
3. 是否要求定期轮换 token（如每学期）
4. 密码复杂度策略与遗忘密码流程（后续可补）

---

如果需要进入实施阶段，下一步将基于本设计产出执行计划文档，并拆分为后端、前端、迁移、测试四个可并行任务包。
