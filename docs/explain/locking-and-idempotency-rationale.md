# 锁与幂等处理策略说明

- 适用角色：开发者、平台负责人
- 最后验证日期：2026-08-26
- 主要来源：`docs/plans/2026-02-13-code-audit-findings.md`

## 问题背景
当任务处理时间超过锁 TTL 时，如果系统仅按时间戳回收锁，可能误删“仍由活跃进程持有”的锁，从而触发同一任务并发重复执行。

## 设计原则
1. 不能仅凭 TTL 判定锁失效。
2. 锁回收必须结合 owner 与进程存活状态。
3. 并发冲突场景优先保证“单任务单执行”。
4. 对重入路径必须有幂等保障。

## 推荐策略
1. 采用持有型锁（`flock/fcntl`）而非仅文件存在判断。
2. 锁记录 owner token；释放时校验 owner 一致性。
3. 若保留 TTL，配套心跳刷新机制与活跃持有探测。
4. 对 `processing` 状态任务避免无条件重入队。

## 幂等补偿
- 关键写路径加幂等键或状态机守卫。
- 重复执行时保证输出一致且无额外副作用。
- 异常恢复路径先做 owner 校验再回收资源。
- chat 幂等走文件系统（`request_map_dir` + `O_EXCL`），不是 Redis。

## Redis 作业与 lane key
RQ 与 `ChatRedisLaneStore` 共用同一 Redis 实例。该实例使用 `noeviction`：内存满时写入失败，而不是 LRU 静默丢 job 或 lane key。不要把 lane 迁到 LRU 实例，也不要按 DB index 隔离（`maxmemory-policy` 是实例级）。运维盯 Redis `OOM` 与 `INFO memory` 的 `used_memory` / `used_memory_rss`、API/worker 日志、chat job `error=enqueue_failed`（HTTP 仍 200、`status=failed`），以及 upload/exam enqueue 的 5xx。不要只告警 API 5xx，否则会漏掉 chat-lane OOM。256mb 不够则加大 `maxmemory`，不加回 LRU。

## 相关文档
- `docs/reference/risk-register.md`
- `docs/reference/upload-resource-guardrails.md`
- `docs/operations/slo-and-observability.md`
