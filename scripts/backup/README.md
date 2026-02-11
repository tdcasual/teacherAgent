# Backup Scripts (A-tier)

本目录用于 A 档数据韧性方案的脚本化落地，支持：
- `S3/OSS` 可切换单写（单任务仅一个目标）
- 增量/全量备份
- 恢复校验
- 升级前强制快照

## 1. 依赖
- `bash`
- `python3`
- `tar`
- `aws`（若目标是 `s3`）
- `ossutil`（若目标是 `oss`）

## 2. 环境变量
### 通用
- `BACKUP_TARGET_DEFAULT=s3|oss`
- `BACKUP_NAMESPACE=prod`
- `BACKUP_HOT_DAYS=30`
- `BACKUP_COLD_DAYS=180`

### S3
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`
- `S3_BUCKET`

### OSS
- `OSS_ACCESS_KEY_ID`
- `OSS_ACCESS_KEY_SECRET`
- `OSS_ENDPOINT`
- `OSS_BUCKET`

## 3. 命令
### 增量备份（单写）
```bash
bash scripts/backup/run_backup.sh --snapshot-type incremental --target s3
```

### 全量备份（单写）
```bash
bash scripts/backup/run_backup.sh --snapshot-type full --target oss
```

### 干跑
```bash
bash scripts/backup/run_backup.sh --snapshot-type incremental --target s3 --dry-run
```

### 恢复校验
```bash
bash scripts/backup/verify_restore.sh --target s3
```

### 升级前快照
```bash
bash scripts/backup/pre_upgrade_snapshot.sh --target s3
```

## 4. 产物
- 运行中间产物：`output/backups/work/`
- 最新状态：`output/backups/state/latest_<target>.json`
- 恢复校验报告：`output/backups/restore-verify/<id>/verify_report.json`

## 5. 说明
- 当前为脚本骨架版本，优先用于联通验证与流程固化。
- 生命周期（热30/冷180）需在 S3/OSS 控制台配置对应规则。
- 生产启用前建议先在 staging 完成至少 1 次全链路恢复演练。

