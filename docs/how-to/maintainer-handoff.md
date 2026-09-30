# 维护者交接手册

- 适用角色：第二维护者、平台
- 最后验证日期：2026-09-06
- 验证：`bash scripts/maintainer_recovery_check.sh`

## AUTH_REQUIRED 三态

| 状态 | 行为 |
| --- | --- |
| 环境变量 **unset** 且进程在 pytest（`PYTEST_CURRENT_TEST`） | 鉴权自动关，便于 TestClient |
| `AUTH_REQUIRED=0` | **fail-closed**，不是 pytest 自动关；生产忽略此值 |
| `AUTH_REQUIRED=1` 或 `ENV=production` | 强制鉴权 |

测试里必须 `os.environ.pop("AUTH_REQUIRED", None)`，不要设成 `"0"`。

## 作业 sqlite 与身份库同文件

路径：`data/auth/auth_registry.sqlite3`。confirm 的 `BEGIN IMMEDIATE` 期间禁止再开第二个连接做 `CREATE TABLE`。名册快照在独占事务外计算。v2 之后盘上有 `meta.json`、表中无行 = crash **orphan**，教师 list 与学生 today 都不可见。

## CI

`pytest tests/ -x`：一次只暴露一个失败。覆盖率 `--cov-fail-under=85`。frontend `format:check` 扫 `apps/**/*.{ts,tsx,css}`。prettier printWidth 100 会增加物理行数，不要用涨预算代替抽取。

## 回滚

读路径 SQL-primary 失败：revert catalog/progress 提交。不要 `git filter-repo`。
