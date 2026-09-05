# 管理员管理教师与学生名册

- 适用角色：管理员
- 前置条件：可进入教师 SPA 管理员登录，或进入 API 容器 shell
- 最后验证日期：2026-09-05

## 教师 SPA 学校管理
管理员用 `POST /auth/admin/login` 进入教师端后打开「学校管理」宽面板（不是 344px 教师抽屉）：

1. 创建教师，复制一次性临时密码发给老师。
2. 上传名册 CSV（`student_name,class_name`，可选 `student_id`）。这只创建/更新 `student_auth`，**不会自动 enroll**。
3. 选择教师 + 学科 + 班级，先「加任教」再「整班入学」（`POST /auth/admin/roster` 与 `enroll-class`）。
4. 如有孤儿作业，选同一教师/学科后认领。

CSV 上限 2000 行 / 256KB。多余列会失败。重导默认不改密码，除非勾选「重导时重置密码」。

## 进入 TUI（逃生舱）
```bash
docker compose exec api admin_manager
```

## 常用命令
- `h`：查看帮助
- `teacher add <teacher_name> [email] [teacher_id]`：创建教师
- `students import <csv_path> [--reset-passwords]`：导入名册（只写 `student_auth`）
- `roster add <teacher_id> <subject_id> <class_name>`
- `enroll-class <teacher_id> <subject_id> <class_name>`
- `f q 张老师`：按关键词过滤
- `batch disable`：批量禁用选中教师
- `batch reset auto`：批量重置密码并自动生成临时密码

## 单人操作
- `disable <teacher_id>`：禁用
- `enable <teacher_id>`：启用
- `reset <teacher_id> auto|manual`：重置密码

## 批量操作安全门
当批量影响人数 >5 时，系统要求输入确认词（例如 `DISABLE 12`），防止误操作。

## 验证结果
- 能看到教师列表。
- 导入 CSV 后学生能用临时密码登录，但 `student_enrollments` 仍为空，直到 enroll-class。
- 重置密码后，教师能使用新密码登录（或收到临时密码）。
