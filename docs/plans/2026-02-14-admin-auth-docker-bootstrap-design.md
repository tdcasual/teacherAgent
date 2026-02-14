# 2026-02-14 管理员认证与 Docker 引导设计

## 背景
当前系统支持学生/教师 token+密码认证，也有基于 JWT `role=admin` 的管理接口，但缺少“可在部署时配置管理员账号密码并直接登录”的闭环。

本设计目标：在不改教师端前端的前提下，补齐管理员后端认证与教师账号管理能力。

## 目标范围
- 管理员账号来源：`docker-compose` 环境变量。
- 管理员登录：用户名+密码获取访问令牌。
- 教师账号管理（后端 API）：
  - 查看教师认证状态列表。
  - 启用/禁用教师账号。
  - 重置教师密码。
- 保留现有管理员能力：教师/学生 token 导出与重置。

## 非目标
- 本次不新增独立管理员前端页面。
- 不替换租户管理 `/admin/*` 的 `X-Admin-Key` 机制。

## 配置与引导
- 新增环境变量：
  - `ADMIN_USERNAME`：管理员用户名，默认 `admin`。
  - `ADMIN_PASSWORD`：可选，未配置时自动生成随机密码。
- 启动引导行为：
  - 在应用生命周期启动阶段执行管理员引导。
  - 若管理员记录不存在，则创建并写入密码哈希。
  - 当 `ADMIN_PASSWORD` 未配置时，生成随机密码并写入 `${DATA_DIR}/auth/admin_bootstrap.txt`（`0600` 权限）。
  - 已存在管理员记录时保持幂等，不覆盖历史密码。

## 数据模型
新增 `admin_auth` 表：
- `admin_username` (PK)
- `username_norm`（唯一）
- `password_hash`, `password_algo`, `password_set_at`
- `failed_count`, `locked_until`, `is_disabled`
- `updated_at`

说明：
- 复用现有密码哈希算法（PBKDF2-SHA256）与登录锁定策略。
- 管理员不会保存明文密码，仅首次自动生成时落盘到引导文件。

## API 设计
- `POST /auth/admin/login`
  - 入参：`username`, `password`
  - 成功：返回 `access_token`（`role=admin`）、`expires_in`。

- `GET /auth/admin/teacher/list`
  - 需 `admin` 鉴权。
  - 返回教师认证状态（`teacher_id/name/email/password_set/is_disabled/token_version`）。

- `POST /auth/admin/teacher/set-disabled`
  - 需 `admin` 鉴权。
  - 入参：`target_id`, `is_disabled`。
  - 行为：更新禁用状态并递增 `token_version`，使旧 token 失效。

- `POST /auth/admin/teacher/reset-password`
  - 需 `admin` 鉴权。
  - 入参：`target_id`, `new_password`（可选）。
  - 行为：
    - 提供 `new_password` 时按强度校验后重置。
    - 未提供时自动生成临时密码并返回给管理员。
    - 重置后递增 `token_version`，使旧访问 token 失效。

## 鉴权与兼容
- 将 `/auth/admin/login` 加入认证豁免路径（同学生/教师登录入口）。
- 保持现有 `require_principal(roles=("admin",))` 保护。

## 审计
管理员动作写入 `auth_audit_log`：
- `action=admin_login`（可选，失败不记录明文）
- `action=set_disabled`
- `action=reset_password`
- 保留 `reset_token/export_tokens` 现有审计。

## 测试策略
- 路由注册测试：新增 4 个管理员接口。
- 认证流程测试：
  - 自动生成管理员密码后可登录。
  - 管理员可列出教师状态。
  - 禁用教师后教师登录被拒。
  - 管理员重置教师密码后可用新密码登录。
