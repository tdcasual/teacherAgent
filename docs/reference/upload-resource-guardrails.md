# 上传与资源限额基线

- 适用角色：管理员、平台负责人、开发者
- 最后验证日期：2026-08-26
- 主要来源：`docs/plans/2026-08-26-audit-remediation-design.md`（F4 / F22，W0-P4）

## 目标
防止上传链路成为资源耗尽入口（内存、磁盘、I/O）。

## 共享数字上限

`services/api/upload_limits.py` **只放共享数字**，写盘复用现有 `save_upload_file`：

| 项 | 值 |
| --- | --- |
| 单请求文件数 | 20 |
| 单文件 | 20MB |
| 单请求总大小 | 80MB |

exam / assignment *start* 只 import 这些数字，不收缩各自后缀集。

## 后缀是唯一录取门

- 后缀必须落在该流 allow-set，否则 HTTP **400** `invalid_suffix`（无后缀、`.exe`、`.bin` 一律拒）。
- MIME **不是**第二道门，也 **不能**单凭 MIME 放行未知后缀。
- MIME 为空、`application/octet-stream`、或浏览器乱报的 Excel / TeX 类型 → **不**因此拒绝合法后缀。
- 禁止「已知 MIME + 未知后缀 → 200」。例如 `Content-Type: application/pdf` 配 `.exe` 必须 400 `invalid_suffix`。
- 禁止「MIME 与后缀不一致 → 400」——那会打掉合法 `.xlsx` + `octet-stream`。

超限 HTTP **400**；中文错误风格保持，机器可读 `error`：`too_many_files` / `file_too_large` / `invalid_suffix`。

## 按流规则

| 流 | 角色 | 后缀集 | 碰撞 |
| --- | --- | --- | --- |
| `POST /upload` | `require_principal()`（无 roles = 任一已认证角色）。`AUTH_REQUIRED=0` 时该调用 no-op，但大小/后缀帽仍生效 | `.pdf .png .jpg .jpeg .webp .txt .md .csv` | **禁止覆盖**：同名加 `-2` 或 `-<8hex>` |
| `POST /student/submit` | 保持 `resolve_student_scope` | 同上学生流 | 同上；走 `save_upload_file`，禁止全量 `read()` |
| assignment OCR | 保持 assignment 调用方鉴权 | 与 assignment paper 对齐（含 `.bmp .tex .markdown`） | 同上；禁止全量 `read()` |
| exam start | 不变 | 现有 paper/score/answer 集（含 `.xlsx .xls .bmp`） | 现有行为 + 同一数字常量 |
| assignment start | 不变 | 现有集（含 `.tex .bmp .markdown`） | 同上 |

## 服务端基线规则
1. 限制上传文件数量（共享 20，exam/assignment start 按字段）。
2. 限制单文件大小（20MB）。
3. 限制单请求总上传体积（80MB）。
4. **只按后缀录取**；不把 MIME 当白名单或否决项。
5. 流式写入复用 `save_upload_file`；超限后删除当次超限文件。
6. `/upload`、submit、OCR 同名不覆盖。

## 客户端协同规则
1. 上传前做数量/大小/类型预检。
2. 校验失败在前端直接提示并阻断请求。
3. 前后端限额配置需保持一致并可追踪。

## 审计与监控建议
- 记录上传拒绝原因（`too_many_files` / `file_too_large` / `invalid_suffix`）。
- 监控高失败率上传端点与磁盘增长速率。
- 将反复超限行为纳入安全告警。

## 回滚
可调大 `MAX_*`，不得删检查，不得收缩 exam/assignment 类型，不得去掉 `/upload` 角色门。

## 相关文档
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/risk-register.md`
- `docs/plans/2026-08-26-audit-remediation-design.md`
