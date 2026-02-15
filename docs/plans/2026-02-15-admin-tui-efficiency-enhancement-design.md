# 2026-02-15 管理员 TUI 效率增强设计（实现版）

## 目标
在保持容器内 `admin_manager` 一键进入（trusted-local）体验不变的前提下，提升管理员批量运维效率与误操作防护。

## 设计范围
- 命令面板主循环（替代单次菜单执行后退出式交互）
- 过滤、排序、分页
- 选择器与批量操作
- 危险动作二次确认
- 会话级操作回放
- 向后兼容旧数字菜单（1-5）

## 交互模型
### 状态层
维护以下状态：
- 过滤条件：`query/disabled/password_set`
- 排序：字段 + 方向
- 分页：`page/page_size`
- 选择集合：`selected_ids`
- 操作历史：最近 `MAX_HISTORY` 条

### 命令层
将用户输入解析为命令动作，核心命令：
- `f`、`sort`、`page/size`、`sel`、`batch`
- `disable/enable/reset`
- `refresh`、`history`

### 渲染层
每轮输出统一视图：
- 摘要头（模式/总量/过滤后数量/页码/已选）
- 表格（含序号、选中标记）
- 提示行（快捷命令）

## 批量操作策略
- 目标集合来自 `selected_ids` 与当前数据交集。
- 批量动作：`batch disable|enable|reset auto|reset manual`
- “不中断”执行：单个失败不阻断整批，最终汇总成功/失败。
- 当影响人数 `>5` 时，强制确认词（如 `DISABLE 12` / `RESET 12`）。

## 兼容与安全
- trusted-local 与 API 登录双模式共存。
- trusted-local 仍写入审计日志（`actor_role=admin`）。
- 保留旧菜单入口：
  - `1` 刷新列表
  - `2/3` 单人禁用/启用
  - `4/5` 单人自动/手动重置密码

## 测试
- 新增 `tests/test_admin_auth_tui.py`：
  - 布尔过滤值解析
  - 选择器表达式解析
  - 过滤 + 排序行为
- 认证相关既有测试套件回归，确保接口行为无回归。
