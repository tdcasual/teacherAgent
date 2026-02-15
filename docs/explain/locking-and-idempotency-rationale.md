# 锁与幂等处理策略说明

- 适用角色：开发者、平台负责人
- 最后验证日期：2026-02-15
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

## 相关文档
- `docs/reference/risk-register.md`
- `docs/reference/upload-resource-guardrails.md`
- `docs/operations/slo-and-observability.md`
