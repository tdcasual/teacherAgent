# A档数据韧性与可重算设计（单机 `docker-compose`）

## 0. 设计状态
- 日期：2026-02-11
- 状态：已与需求方逐段确认
- 部署形态：单台云主机 + `docker-compose`
- 备份目标：支持 `S3` 与 `OSS`，且**每次任务仅单写一个目标**（可切换）
- 保留策略：热备 30 天 + 冷备 180 天
- 恢复目标：`RPO <= 5 分钟`，`RTO <= 30 分钟`

## 1. 背景与目标
当前系统把教学数据（考试、作业、学生画像、教师工作区等）作为核心资产。现状已有本地挂载持久化能力，但缺乏“可证明可恢复”的制度化机制：备份策略、恢复演练、版本迁移与重算通道尚未形成统一闭环。业务上要求两件事：第一，升级后数据不丢；第二，功能大改后仍能使用原始数据做二次分析。基于这些约束，本设计定义 A 档目标：在单机架构内实现稳健级数据保护，而不是追求跨地域双活。设计强调三条主线：一是将数据分为可追溯原始层、可重建派生层、在线服务层，降低耦合；二是建立“备份成功 ≠ 可恢复成功”的治理体系，强制演练与门禁；三是建立结构化迁移机制（`schema_version + migrations`），避免大版本升级依赖临时兼容代码。最终验收标准不是“看起来有备份”，而是：指定时间窗口内能按脚本恢复、能重放历史数据、能通过升级回滚演练。

## 2. 数据分层模型（Raw / Derived / Serving）
为保障“升级可变、数据不变”，将现有数据域归入三层。

1) `raw`（不可变原始层）：原始上传文件、OCR 原文、解析前文本、原始成绩文件、原始答题图像等。原则是只追加不覆盖，保留来源与时间戳。  
2) `derived`（可重算派生层）：例如 `responses_scored.csv`、分析草稿、题目结构化结果、画像建议稿等。该层允许按新算法重建，且应记录 `analyzer_version`。  
3) `serving`（在线服务层）：画像文件、工作区配置、会话索引、任务状态、租户配置等在线读写对象。

建议在逻辑上引入统一元数据字段：`data_domain`、`schema_version`、`generated_by`、`generated_at`、`source_refs`。对现有目录不做一次性破坏迁移，而采用“渐进落标”：新写入对象优先带齐元数据，旧对象通过迁移器补全。该模型的关键价值是把“业务功能变化”与“原始事实存续”解耦。即使未来分析模型、评分逻辑、画像策略大幅变更，也可固定从 `raw` 回放，重新产出 `derived`，并把旧结果作为历史版本保留，避免数据资产被功能迭代吞掉。

## 3. 备份架构（可切换单写）
采用三组件编排：`backup_scheduler`（定时触发）、`backup_runner`（打包与上传）、`backup_verify`（恢复抽检）。

- `backup_scheduler` 负责按策略触发任务，并为每次任务显式注入 `target=s3|oss`。
- `backup_runner` 仅初始化目标云对应客户端，执行单目标写入；若目标不可用则任务失败并告警，**不自动切换**到另一云，避免“静默漂移”。
- `backup_verify` 周期性执行抽样恢复，验证 manifest 与数据可读性。

每次任务产出 `backup_manifest.json`（建议对象路径前缀：`backups/{env}/{date}/{job_id}/`），包含：
- `job_id`、`target_provider`、`started_at`、`finished_at`
- `snapshot_type`（incremental/full）
- `object_list`（路径、大小、哈希、domain）
- `schema_versions`
- `restore_entrypoint`
- `tool_versions`

该模式满足“系统支持两家，但每次任务只选一家写入”的要求，且运维行为可追踪。切换云提供方仅通过任务参数或环境变量调整，不需要修改业务容器。

## 4. 备份策略与保留策略
### 4.1 任务节奏
- 增量快照：每 5 分钟一次（对齐 RPO 目标）
- 全量快照：每日低峰（建议 02:00）
- 恢复校验：每周固定窗口（建议周日凌晨）

### 4.2 数据域优先级
- P0：`raw`、`student_profiles`、`teacher_workspaces`、任务状态与迁移日志
- P1：`derived` 分析结果
- P2：可再生缓存

### 4.3 生命周期
按你的最新确认：
- 热备：30 天（可快速恢复）
- 冷备：180 天（合规追溯）

生命周期由目标存储端策略执行（S3 Lifecycle / OSS Lifecycle），系统侧只负责写入统一标签（如 `tier=hot`、`expire_after_days`），避免手工清理误删。

## 5. 恢复分级与演练制度
定义三级恢复，匹配 A 档目标：

- L1（对象级）：恢复单考试、单作业、单画像文件；目标 5-10 分钟。
- L2（窗口级）：按时间窗口恢复增量快照；目标 30 分钟内。
- L3（系统级）：新机全量恢复并启动服务；目标 30 分钟级别（核心服务先恢复）。

演练制度：
- 每周至少 1 次 L1 抽检恢复；
- 每月至少 1 次 L3 全链路演练；
- 演练结果写入 `restore_audit`，指标含 `actual_rpo`、`actual_rto`、失败原因、修复动作。

发布门禁：若最近 7 天无成功恢复演练，或最近 24 小时备份健康检查失败，则禁止执行生产升级。该门禁将“数据可靠性”前置到发布流程，而不是事后补救。

## 6. Schema 版本化与迁移框架
对核心对象引入 `schema_version`：
- 考试 `manifest`
- 作业 `meta/requirements`
- 学生画像 `student_profiles`
- 教师工作区关键配置

新增统一迁移器：`migrations/registry.py` + `migrations/vX_to_vY.py`。

规则：
1. 迁移前强制做升级快照；
2. 迁移脚本必须幂等（重复执行不破坏数据）；
3. 迁移失败可回滚到快照；
4. 每次迁移写审计日志（输入版本、输出版本、对象数量、失败对象）。

读路径采用短期兼容：读取层允许处理 `N-1` 版本，写入统一落新版本。这样可支持滚动升级，也让功能大改时仍可解析旧数据并纳入新分析链路。

## 7. 原始数据二次分析（重放通道）
为保证“功能大改仍可复算”，定义重放接口：
- `rebuild_derived --scope exam --exam-id <id> --analyzer-version <v>`
- `rebuild_profile_features --student-id <id> --feature-version <v>`

重放原则：
1. 输入只读取 `raw` 与必要字典；
2. 输出写入版本化 `derived` 路径（如 `v1/`, `v2/`）；
3. 不覆盖历史结果，支持并行对比；
4. 记录 `analyzer_version` 与配置快照。

这样在算法升级（评分策略、知识点归因、画像规则）后，可对历史全量数据做一致性重算，形成纵向对比，支撑教研复盘与模型迭代验证。

## 8. `docker-compose` 落地项
在现有编排上新增服务（可使用同一工具镜像）：
- `backup-scheduler`
- `backup-runner`
- `backup-verify`

关键环境变量：
- 通用：`BACKUP_TARGET_DEFAULT`、`BACKUP_SINGLE_TARGET_ENFORCED=1`、`BACKUP_HOT_DAYS=30`、`BACKUP_COLD_DAYS=180`
- S3：`S3_BUCKET`、`S3_REGION`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`
- OSS：`OSS_BUCKET`、`OSS_ENDPOINT`、`OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`

建议新增运维脚本：
- `scripts/backup/run_backup.sh`
- `scripts/backup/verify_restore.sh`
- `scripts/backup/pre_upgrade_snapshot.sh`

并将升级流程固定为：`升级前快照 -> 升级 -> L1 恢复验证 -> 放行`。

## 9. 告警与可观测性
告警阈值建议：
- 连续 2 次增量失败
- 最近 10 分钟无成功增量
- 每周恢复校验失败
- 生命周期策略未生效（对象超期未转层）

指标看板：
- 备份成功率、备份延迟、恢复成功率、`actual_rpo`、`actual_rto`
- 各数据域对象数与容量增长
- 迁移成功/失败计数

## 10. 实施节奏（4 周）
第 1 周：数据分层标识、单任务单写框架、S3/OSS Provider 抽象。  
第 2 周：增量/全量备份任务、manifest/hash、热30冷180生命周期。  
第 3 周：L1/L2/L3 恢复工具与周度演练自动化。  
第 4 周：`schema_version` 与迁移框架、发布门禁、上线演练。

## 11. 验收标准
1. 任意一天内，增量备份任务成功率 >= 99%。
2. 周度 L1 恢复演练成功率 100%。
3. 月度 L3 演练满足 `RPO<=5m` 与 `RTO<=30m`。
4. 核心对象全部带 `schema_version`，迁移测试覆盖 100%。
5. 抽取历史考试样本，使用新 `analyzer_version` 重放成功并产出新旧对比结果。

---

该设计为 A 档（稳健）方案；若未来目标升级到跨地域容灾，可在此基础上扩展双活与自动故障切换。
