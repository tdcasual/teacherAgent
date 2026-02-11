# A档数据韧性实施清单（可执行版）

## 1. 交付目标
- 目标：将《A档数据韧性与可重算设计》落地为可执行工程项。
- 边界：单机 `docker-compose`，`S3/OSS` 可切换单写，每次任务只写一个目标。
- 保护窗口：热备 30 天，冷备 180 天。

## 2. 本次新增文件
- `/Users/lvxiaoer/Documents/New project/docker-compose.backup.draft.yml`
- `/Users/lvxiaoer/Documents/New project/services/backup/Dockerfile`
- `/Users/lvxiaoer/Documents/New project/.env.backup.example`
- `/Users/lvxiaoer/Documents/New project/scripts/backup/common.sh`
- `/Users/lvxiaoer/Documents/New project/scripts/backup/run_backup.sh`
- `/Users/lvxiaoer/Documents/New project/scripts/backup/verify_restore.sh`
- `/Users/lvxiaoer/Documents/New project/scripts/backup/pre_upgrade_snapshot.sh`
- `/Users/lvxiaoer/Documents/New project/scripts/backup/README.md`

## 3. 分阶段执行清单

### 阶段 A：脚手架与参数基线
- [ ] 确认 `.env` 增加备份参数：`BACKUP_TARGET_DEFAULT`、`BACKUP_NAMESPACE`、`BACKUP_HOT_DAYS`、`BACKUP_COLD_DAYS`。
- [ ] 为目标云补齐参数：`S3_BUCKET` 或 `OSS_BUCKET`/`OSS_ENDPOINT`。
- [ ] 在执行机安装依赖：`bash`、`python3`、`tar`、`aws`（S3）或 `ossutil`（OSS）。

### 阶段 B：备份任务联通
- [ ] 本地执行增量备份（单写 S3）：
  - `bash scripts/backup/run_backup.sh --snapshot-type incremental --target s3`
- [ ] 本地执行全量备份（单写 OSS）：
  - `bash scripts/backup/run_backup.sh --snapshot-type full --target oss`
- [ ] 校验 `output/backups/state/latest_<target>.json` 已产出。

### 阶段 C：恢复校验联通
- [ ] 对最近一次备份执行恢复校验：
  - `bash scripts/backup/verify_restore.sh --target s3`
  - `bash scripts/backup/verify_restore.sh --target oss`
- [ ] 检查恢复目录 `output/backups/restore-verify/` 的校验结果。

### 阶段 D：升级前快照流程
- [ ] 执行升级前全量快照：
  - `bash scripts/backup/pre_upgrade_snapshot.sh --target s3`
- [ ] 记录输出的 `job_id`，写入发布工单。

### 阶段 E：编排接入（草案）
- [ ] 使用草案文件启动备份 profile：
  - `docker compose -f docker-compose.yml -f docker-compose.backup.draft.yml --profile backup up -d`
- [ ] 验证容器日志中周期任务有成功记录。

## 4. 文件级改造建议（下一步正式实现）
- `/Users/lvxiaoer/Documents/New project/docker-compose.yml`
  - 正式并入 `backup_scheduler`、`backup_daily_full`、`backup_verify_weekly` 服务。
- `/Users/lvxiaoer/Documents/New project/services/api/exam_upload_confirm_service.py`
  - `manifest` 增加 `schema_version` 与 `source_refs`。
- `/Users/lvxiaoer/Documents/New project/services/api/assignment_upload_confirm_service.py`
  - `meta` 增加 `schema_version`。
- `/Users/lvxiaoer/Documents/New project/skills/physics-student-coach/scripts/update_profile.py`
  - 画像写入补齐 `schema_version` 与迁移兼容入口。
- `/Users/lvxiaoer/Documents/New project/scripts/`（新增 `migrations/`）
  - 增加统一迁移执行器和版本迁移脚本。

## 5. 验收命令
- 语法校验：
  - `bash -n scripts/backup/common.sh scripts/backup/run_backup.sh scripts/backup/verify_restore.sh scripts/backup/pre_upgrade_snapshot.sh`
- 干跑校验：
  - `bash scripts/backup/run_backup.sh --snapshot-type incremental --target s3 --dry-run`
  - `bash scripts/backup/run_backup.sh --snapshot-type full --target oss --dry-run`

## 6. 发布门禁（建议）
- 最近 24 小时至少 1 次增量备份成功。
- 最近 7 天至少 1 次恢复校验成功。
- 升级前必须执行 `pre_upgrade_snapshot.sh` 并留档 `job_id`。
