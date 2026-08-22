# 上传与资源限额基线

- 适用角色：管理员、平台负责人、开发者
- 最后验证日期：2026-08-22
- 主要来源：`docs/plans/2026-02-13-code-audit-findings.md`、`docs/plans/2026-08-22-audit-remediation-design.md`

## 目标
防止上传链路成为资源耗尽入口（内存、磁盘、I/O）。

## 共享数字上限

实现：`services/api/upload_limits.py`（只共享数字上限与流式/防覆盖 helper；后缀与 MIME **按流保留**）。

| 常量 | 值 |
| --- | --- |
| `MAX_FILES` | 20 |
| `MAX_FILE_BYTES` | 20MB |
| `MAX_TOTAL_BYTES` | 80MB |

`exam_upload_start_service` 与 `assignment_upload_start_service` 导入同一组数字常量，不得各自另写一套。

## 按流后缀与 MIME

扩展名 + MIME 必须同时匹配。**冲突**的 MIME 与后缀 → **400**。空 `Content-Type` 或 `application/octet-stream` 视为未标注，回退到后缀白名单。不得用学生流的窄集合覆盖考试/作业流。学生 `/upload` 与 `/student/submit` 共用同一套后缀/MIME 常量（`student_ops_service.STUDENT_*`）。

### 学生 `POST /upload` 与 `POST /student/submit`

- 后缀：`.pdf` `.png` `.jpeg` `.jpg` `.webp` `.txt` `.md` `.csv`
- 对应 MIME（如 `.pdf`→`application/pdf`，`.png`→`image/png`；`.csv` 另含 `application/vnd.ms-excel`；`.md` 含 `text/x-markdown`）

### 考试试卷 / 作业源文件 / 作业 OCR

- 后缀：`.pdf` `.png` `.jpg` `.jpeg` `.bmp` `.webp` `.md` `.markdown` `.txt` `.tex`
- OCR（`assignment_questions_ocr_service`）与作业试卷对齐，**含** `.bmp` / `.tex` / `.markdown`，不得改用更窄的学生集

### 考试成绩

- 在试卷后缀之外另含：`.csv` `.xlsx` `.xls`

## 服务端基线规则
1. 限制上传文件数量（按场景区分；共享上限 20）。
2. 限制单文件大小（20MB）。
3. 限制单请求总上传体积（80MB）。
4. 扩展名 + MIME 双白名单校验；MIME 与后缀不一致拒绝。
5. 流式写入过程中实时校验，超限立即中断。禁止 `dest.write_bytes(await upload_file.read())`。有 `.file` 时在线程池中拷贝，避免堵事件循环。
6. 同名碰撞改名；以 `O_EXCL`/`"xb"` 创建并在 `FileExistsError` 时重试，不跟随悬空 symlink。
7. 请求失败时清理本次临时文件，避免垃圾落盘。

## 客户端协同规则
1. 上传前做数量/大小/类型预检。
2. 校验失败在前端直接提示并阻断请求。
3. 前后端限额配置需保持一致并可追踪。

## 回滚
可调大 `MAX_*`，不得删除检查，不得收缩考试/作业后缀集合。

## 审计与监控建议
- 记录上传拒绝原因（超限、类型不允许、总量超标、MIME 不一致）。
- 监控高失败率上传端点与磁盘增长速率。
- 将反复超限行为纳入安全告警。

## 相关文档
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/risk-register.md`
- `docs/plans/2026-02-13-code-audit-findings.md`
