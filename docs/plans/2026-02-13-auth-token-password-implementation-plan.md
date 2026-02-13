# 学生/教师 Token+密码认证实施计划

日期：2026-02-13  
状态：执行中

关联设计：`docs/plans/2026-02-13-auth-token-password-design.md`

## 1. 目标

在不修改 `chart.exec` 默认 `trusted` 行为前提下，交付以下认证链路：

1. 学生：`姓名 + 班级` identify 后，必须再用 `token 或密码` 登录。
2. 学生可用 token 设置密码，设置后 token/密码并行可用。
3. 教师：`姓名` identify；若重名则要求邮箱辅助，再用 `token 或密码` 登录。
4. token 自动生成、可重置、可导出（预生成分发模式）。
5. 登录成功后签发 Bearer token，前端后续请求统一携带。

## 2. 执行批次

### 批次 A：后端认证域与接口

1. 新增认证存储模块：`auth_registry.sqlite3`（学生、教师、审计日志）。
2. 新增认证服务：
   - identify（student/teacher）
   - login（token/password）
   - set-password
   - reset-token
   - export-tokens
3. 新增路由：`/auth/student/*`、`/auth/teacher/*`、`/auth/admin/*`。
4. 接入 Bearer 签发（复用现有 token 签名机制）并返回统一响应结构。

### 批次 B：前端接入

1. 学生端登录 UI 改两步：identify -> credential。
2. 学生端补“使用 token 设置密码”流程。
3. 教师端新增登录闸门：姓名 identify、必要时邮箱去歧义、再 credential 登录。
4. 学生/教师前端分别持久化 access token，并自动注入到后续 API 请求头。

### 批次 C：验证与兼容

1. 兼容保留旧 `/student/verify`（不立即移除）。
2. 增加后端单测（identify/login/set-password/歧义分支）。
3. 增加路由存在性断言。
4. 跑回归测试（至少 auth/student/teacher/chat 相关用例）。

## 3. 风险与对策

1. 教师目录历史数据不足（name/email 不完整）：
   - 对策：提供 admin 初始化/重置与导出能力，允许先以最小集运行。
2. 前端请求点分散导致漏加 Authorization：
   - 对策：封装统一 fetch 注入层，按应用（student/teacher）独立 token key。
3. 旧测试对无认证路径有依赖：
   - 对策：新链路增量接入，不破坏原 verify 接口；新增用例覆盖新接口。

## 4. 完成定义（DoD）

1. 学生端可完成 identify + token 登录，并可设置密码后用密码登录。
2. 教师端可完成 identify + token 登录；重名时可邮箱去歧义后登录。
3. 登录后 chat/history/persona 等主路径请求携带 Bearer token。
4. 新增测试通过，既有关键回归无失败。
