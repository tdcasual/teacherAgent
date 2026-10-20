# 权限与认证参考

- 适用角色：管理员、开发者
- 最后验证日期：2026-09-06

## 角色
- `student`: 学生角色，受 `student_id` 作用域约束。
- `teacher`: 教师角色，受 `teacher_id` 作用域约束。
- `admin`: 管理员角色，可执行账号管理与跨作用域管理操作。
- `service`: 服务角色，用于运维指标与内部任务。

## 认证模式
1. 学生：identify + 密码登录，成功后获取 Bearer token。
2. 教师：identify + token/密码登录，成功后获取 Bearer token。
3. 管理员：
- 远程 API：`/auth/admin/login` 获取 Bearer token。
- 容器内：`admin_manager` trusted-local 模式直接管理（容器信任边界）。

## 关键安全机制
- token 与密码均以 hash 存储，不保存明文。
- 登录失败计数与锁定策略。
- token/password 重置后递增 `token_version`，旧 token 自动失效。
- 老师可按学生/班级/全量重置学生密码，明文默认密码仅在重置响应中返回一次。
- 管理员名册导入只写 `student_auth`；enroll 必须另带教师+学科+班级。
- 审计日志记录关键管理动作。
- LLM 工具面：绑定 actor 胜。`teacher.memory.*` 与 `teacher.workspace.init` 仅 `role=teacher`；模型传入的他人 `teacher_id` 为 `403 forbidden_teacher_scope`。缺绑定 `400 teacher_id_required`。
- `student.search` 按教师名册过滤；空名册返回 `{matches:[]}`。`student.profile.get/update` 在读盘前做 `bind_tool_student_id`；名册外 `403 forbidden_student_scope`。
- 学生 JWT/`actor_id` 只能操作自己的档案。admin/service 可对学生 search/get/update 使用显式 `student_id`，不可经工具冒充教师 MEMORY.md。
- `assignment.render` 显式 `--out` 必须落在 `DATA_DIR` 下；默认 PDF 路径仍为 `output/pdf/assignment_{id}.pdf`。
- `student.import` 工具恒 `410 gone`。
- 学生 `GET /assignment/{id}` 只返回题目 allowlist（`question_id` / `kp_id` / `stem_text` 等），不含 `answer_ref`、`stem_ref`、任意答案列，也不含 meta 的 `answer_files` / `expected_students` / `student_ids`。教师详情保持完整字段。
- 作业题干读取（catalog / context）将 `stem_ref` 限制在该作业目录或 `DATA_DIR/question_bank`（含 symlink resolve）。
- 生产环境 `AUTH_TOKEN_SECRET` 不得为空或为 `change_me`。

## 相关文档
- `docs/how-to/admin-manage-teachers-tui.md`
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/http_api.md`
