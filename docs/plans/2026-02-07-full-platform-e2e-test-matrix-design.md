# 2026-02-07 Full Platform E2E Test Matrix Design

## 1) 功能分析（全量）

本项目可分为 10 个端到端测试域：

1. 老师端聊天与召唤链路（`@agent`、`$skill`、异步轮询、队列状态、错误恢复）。
2. 老师端会话系统（新建/切换/归档/检索/历史分页/跨会话隔离）。
3. 老师端技能工作台（技能筛选、收藏、模板、手动固定与自动路由切换）。
4. 老师端作业上传全流程（start/status/draft/save/confirm）。
5. 老师端考试上传全流程（试卷+成绩、多阶段审核、confirm 落地）。
6. 老师端模型路由与 Provider 管理（simulate/proposal/review/rollback/probe-models）。
7. 本地状态持久化恢复（localStorage/sessionStorage 损坏、刷新恢复、冲突兜底）。
8. 移动端与可访问性（overlay、键盘导航、ARIA、窄屏可操作性）。
9. 学生端学习闭环（诊断、练习生成、作业提交、OCR、画像更新）。
10. 跨系统一致性与安全（并发、幂等、原子写入、输入安全、重启恢复）。

目标是建立统一的“高风险优先”矩阵：

- `P0`: 数据错写、状态串线、流程卡死、重复提交。
- `P1`: 降级策略、异常可恢复、提示准确性。
- `P2`: 体验稳定性、可访问性和边缘交互。

---

## 2) 执行规范（统一模板）

每条 E2E 用例按 `Given / When / Then` 编写，建议映射到 Playwright 用例如下：

- `Given`: 固定 localStorage 初始状态 + API route mock。
- `When`: 用户交互（click/type/upload/switch/reload）。
- `Then`: 断言 UI 状态 + 请求 payload + 本地状态变化。

统一断言维度：

1. UI：按钮禁用态、状态 chip、提示文本、可见性。
2. 请求：路径、方法、次数、关键字段（如 `skill_id`、`session_id`）。
3. 状态：`teacherActiveUpload`、`teacherPendingChatJob`、view state。
4. 结果：最终消息、任务状态、数据落地标识。

---

## 3) 全量 E2E 用例（120）

### A. 聊天与召唤链路（16）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| A001 | P0 | 输入框存在中文 IME 组合态 | 按 Enter | 不触发 `/chat/start` |
| A002 | P0 | `/chat/start` 返回 500 | 点击发送 | 显示错误，输入恢复可编辑 |
| A003 | P0 | `/chat/status` 先 processing 后 done | 发送消息 | 占位消息被最终回复替换 |
| A004 | P0 | `/chat/status` 返回 failed+detail | 发送消息 | 错误可读，pending 被清理 |
| A005 | P0 | `/chat/status` 返回 cancelled | 发送消息 | 状态转取消，允许再次发送 |
| A006 | P1 | start 返回 queued 位置信息 | 发送消息 | 队列文案显示 position/size |
| A007 | P1 | 页面后台后恢复前台 | 触发 visibilitychange | 立即补轮询并刷新状态 |
| A008 | P0 | 已存在 pending 任务 | 连续点击发送 | 只产生一次 start 请求 |
| A009 | P1 | 超长消息历史存在 | 发送新消息 | payload 满足上下文窗口约束 |
| A010 | P1 | 文本中多个 `@/$` token | 点击发送 | 最后合法 token 生效 |
| A011 | P1 | 光标在中间位置 | 选择 mention 插入 | 前后文本和空格保持正确 |
| A012 | P2 | 中英混合与特殊标点 | 发送 | 正文无乱码且不截断 |
| A013 | P1 | 输入仅 token 无正文 | 点击发送 | 拦截发送并保留输入 |
| A014 | P1 | 多行编辑场景 | Shift+Enter 再 Enter | 前者换行后者发送 |
| A015 | P0 | start 响应延迟 | 发送后立即切会话 | 源会话消息/占位不丢失 |
| A016 | P1 | status 返回未知终态 | 发送消息 | 进入兜底错误态而非卡死 |

### B. 会话与历史侧栏（12）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| B001 | P0 | 侧栏已展开 | 点击“新建” | 出现 `session_*` 且 active |
| B002 | P1 | 会话支持重命名 | 修改标题 | 列表/检索/view-state 同步 |
| B003 | P0 | 目标会话可归档 | 确认归档 | 活跃列表移除，归档可见 |
| B004 | P1 | 归档确认弹窗 | 点击取消 | 菜单关闭且不变更状态 |
| B005 | P1 | 多会话含不同 preview | 搜索关键词 | 按 id/title/preview 过滤 |
| B006 | P1 | 菜单已打开 | 外部点击/Escape | 菜单关闭，`aria-expanded=false` |
| B007 | P0 | main/s2 双会话存在 | main 发消息后切 s2 | 回复仅写回 main |
| B008 | P1 | 会话 A 显示错误 | 切换到会话 B | A 的瞬时错误不泄漏到 B |
| B009 | P1 | 会话分页到末尾 | 查看“加载更多” | 按钮禁用并显示末页文案 |
| B010 | P1 | 历史分页到末尾 | 查看“更早消息” | 按钮禁用并显示无更多 |
| B011 | P0 | 新建草稿会话未落库 | 刷新页面 | 草稿会话仍保留可见 |
| B012 | P2 | 会话列表很长 | 连续滚动 | 无页面滚动穿透 |

### C. 技能工作台（12）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| C001 | P1 | 技能列表已加载 | 输入搜索词 | 按 id/title/desc 过滤 |
| C002 | P1 | 至少一项技能已收藏 | 开启“只看收藏”并插入 | 插入目标正确且稳定 |
| C003 | P1 | 收藏状态已变更 | 刷新页面 | 收藏状态持久化恢复 |
| C004 | P0 | 技能卡可“设为当前” | 点击后发送 | payload 带对应 `skill_id` |
| C005 | P0 | 当前为固定技能 | 切“自动路由”后发送 | payload 不含 `skill_id` |
| C006 | P1 | 光标置于中间 | 点击“插入 $” | token 在光标处插入 |
| C007 | P1 | 技能含模板 | 点击“使用模板” | 模板插入且可继续编辑 |
| C008 | P1 | `/skills` 返回失败 | 打开页面 | 使用内置 fallback 列表 |
| C009 | P1 | 可手动刷新技能 | 点击刷新 | loading/disabled/恢复正确 |
| C010 | P2 | 当前 tab=workflow | 收起再展开工作台 | tab 保持不变 |
| C011 | P1 | agent 卡片可插入 `@` | 插入后发送 | `agent_id` 与 UI 一致 |
| C012 | P1 | 卡片插入+手输混用 | 发送 | 最终 payload 一致且可预测 |

### D. 作业上传全流程（14）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| D001 | P0 | workflow=assignment | 缺 assignment_id 提交 | 前端拦截，无 start 请求 |
| D002 | P0 | assignment_id 已填 | 缺 files 提交 | 前端拦截并提示 |
| D003 | P0 | scope=class | 无 class_name 提交 | 前端拦截并提示 |
| D004 | P0 | scope=student | 无 student_ids 提交 | 前端拦截并提示 |
| D005 | P1 | start 返回 job_id | 成功上传 | 写入 `teacherActiveUpload` |
| D006 | P1 | status: queued->processing->done | 自动轮询 | 状态 chip 逐步更新 |
| D007 | P0 | status=failed | 轮询结束 | 展示失败并清空 activeUpload |
| D008 | P0 | draft 可编辑 | 点击保存 | dirty 清除，提示成功 |
| D009 | P0 | `requirements_missing` 非空 | 观察 confirm 按钮 | disabled 且含原因 title |
| D010 | P0 | confirm 可点击 | 快速重复点击 | 仅一次 confirm 请求 |
| D011 | P0 | confirm 成功 | 返回 `ok=true` | 状态“已创建”并清理 job |
| D012 | P1 | confirm 返回 `job_not_ready` | 点击 confirm | 不丢草稿，提示稍后重试 |
| D013 | P1 | local 有 activeUpload | 刷新页面 | 自动恢复轮询与表单态 |
| D014 | P1 | files+answer_files 混合上传 | 提交 | 请求体字段和顺序正确 |

### E. 考试上传全流程（14）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| E001 | P0 | workflow=exam | 无试卷文件提交 | 前端拦截 |
| E002 | P0 | 已有试卷文件 | 无成绩文件提交 | 前端拦截 |
| E003 | P1 | `/exam/upload/start` 成功 | 提交 | 写入 `teacherActiveUpload` |
| E004 | P1 | status 含 progress | 连续轮询 | 进度显示合法且不倒退 |
| E005 | P0 | draft 可改日期/班级/满分 | save 后 reload draft | 修改值一致 |
| E006 | P0 | confirm 成功 | 点击 confirm | 显示 exam_id 与题量摘要 |
| E007 | P0 | status=confirmed | 轮询到终态 | 清空 activeUpload |
| E008 | P0 | status=failed | 轮询到终态 | 显示错误且可重新操作 |
| E009 | P1 | 不填 exam_id | 发起上传 | UI 显示后端自动生成 ID |
| E010 | P1 | 成绩文件为 xlsx+图片组合 | 上传 | 任务能创建并进入解析 |
| E011 | P1 | parse 未 done | 查看 confirm | confirm 维持 disabled |
| E012 | P1 | confirm 返回 not ready | 点击 confirm | 状态可恢复并继续轮询 |
| E013 | P1 | assignment 与 exam 来回切换 | 输入各自表单 | 字段互不污染 |
| E014 | P2 | 上传区折叠显示摘要 | 切换 job | 摘要总是当前 job 数据 |

### F. 模型路由与 Provider（14）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| F001 | P0 | routing/provider 接口均成功 | 打开路由页 | 页面完整可操作 |
| F002 | P1 | routing 成功 provider 失败 | 打开路由页 | provider 区降级可读 |
| F003 | P1 | provider 成功 routing 失败 | 打开路由页 | 显示错误且可刷新 |
| F004 | P0 | simulate 接口可用 | 发起模拟 | 返回命中规则与 channel |
| F005 | P0 | proposals 接口可用 | 创建提案 | 列表出现新提案 |
| F006 | P0 | 提案处于待审核 | 审核“生效” | routing version 递增 |
| F007 | P1 | 提案处于待审核 | 审核“拒绝” | 状态和意见正确记录 |
| F008 | P0 | history 有旧版本 | 执行 rollback | 当前配置切到目标版本 |
| F009 | P0 | provider 输入合法 https | 新增 provider | 成功创建并脱敏显示 key |
| F010 | P0 | provider_id 冲突共享目录 | 提交新增 | 返回冲突错误 |
| F011 | P1 | provider 已存在 | PATCH 轮换 api_key | 成功且不回显明文 key |
| F012 | P1 | provider 已存在 | DELETE | 软删除后目录不可选 |
| F013 | P1 | 上游 `/models` 可达 | probe-models | 模型列表写入可选 |
| F014 | P1 | 上游 `/models` 超时 | probe-models | 失败提示但不阻断手填 |

### G. 持久化与恢复（10）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| G001 | P0 | `teacherSkillPinned=INVALID` | 启动应用 | 回退自动路由 |
| G002 | P0 | `teacherActiveAgentId` 缺失 | 启动应用 | 回退 `default` |
| G003 | P1 | `teacherWorkbenchTab` 非法值 | 启动应用 | 回退默认 tab |
| G004 | P0 | `teacherPendingChatJob` 存在 | 刷新 | 自动补轮询直至终态 |
| G005 | P1 | `teacherActiveUpload` 存在 | 刷新 | workflow 自动恢复 |
| G006 | P1 | 本地 view-state 与远端冲突 | 启动同步 | 保持可用且无崩溃 |
| G007 | P1 | local JSON 损坏 | 启动应用 | 自动兜底且可继续聊天 |
| G008 | P1 | localStorage 写入失败 | 执行关键操作 | 主流程不中断 |
| G009 | P1 | 自定义 `apiBaseTeacher` | 刷新再发请求 | 请求命中新 base URL |
| G010 | P0 | confirm 中途刷新 | 等待终态 | 不重复 confirm，状态一致 |

### H. 移动端与可访问性（8）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| H001 | P0 | mobile 且双侧栏打开 | 点击 overlay | 两侧栏同时关闭 |
| H002 | P1 | 会话菜单触发器存在 | 打开/关闭菜单 | `aria-expanded` 准确 |
| H003 | P1 | 键盘操作场景 | Enter 打开，Escape 关闭 | 无鼠标完成菜单操作 |
| H004 | P1 | 窄屏 mention panel 展开 | 键盘上下+Enter | 正确插入 token |
| H005 | P1 | 有 pending 任务 | 查看发送按钮 | disabled 且状态可见 |
| H006 | P2 | 浏览器缩放 200% | 操作输入发送 | 输入区与按钮可见可点 |
| H007 | P2 | 手机横屏 | 打开页面 | 关键按钮仍可触达 |
| H008 | P2 | 触摸滚动长列表 | 连续滚动 | 不触发桌面 wheel 假设 |

### I. 学生端闭环（12）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| I001 | P0 | 学生身份登录 | 查看可见作业 | 仅显示可访问范围 |
| I002 | P0 | 完成诊断对话 | 触发练习生成 | 生成个性化练习 |
| I003 | P1 | 费曼反思流程开启 | 提交反思内容 | 可保存并进入下一步 |
| I004 | P0 | `/student/submit` 可用 | 上传多张作业图片 | 返回评分摘要 |
| I005 | P0 | `auto_assignment=true` | 提交作业 | 自动匹配最近作业 |
| I006 | P1 | 一张无效格式一张有效图片 | 提交 | 返回部分失败可读结果 |
| I007 | P1 | OCR 部分页失败 | 提交 | 保留成功页结果 |
| I008 | P0 | 提交前后可读 profile | 提交成功后读取 profile | weak/strong KP 预期更新 |
| I009 | P1 | 同作业连续两次提交 | 查看历史 | 顺序和时间戳正确 |
| I010 | P1 | 作业范围策略变化 | 刷新列表 | 可见清单即时更新 |
| I011 | P1 | 网络抖动可重试 | 触发重试 | 不产生重复提交记录 |
| I012 | P2 | 长会话学习场景 | 滚动+输入交替 | 输入区定位稳定 |

### J. 跨系统一致性与安全（8）

| ID | Priority | Given | When | Then |
| --- | --- | --- | --- | --- |
| J001 | P0 | 并发两个上传任务 | 同时轮询 | job 状态互不串线 |
| J002 | P0 | confirm 写盘中断异常 | 执行 confirm | 无半成品目录残留 |
| J003 | P0 | 上传文件名含路径穿越字符 | 提交 | 服务端拒绝并记录错误 |
| J004 | P0 | 超过文件大小限制 | 提交 | 返回明确限制错误 |
| J005 | P1 | MIME 与扩展名冲突 | 提交 | 触发安全校验策略 |
| J006 | P1 | 服务重启后 | 查询进行中 job | 可恢复可追踪状态 |
| J007 | P1 | 请求含 request_id | 贯穿 start/status/confirm | 链路可追踪 |
| J008 | P1 | failed/cancelled 多次出现 | 检查 local 状态 | 无脏键残留影响新流程 |

---

## 4) 实施建议（从“全量”到“可执行”）

建议分 4 批落地：

1. **批次 1（P0 核心 36 条）**：A/B/D/E/F/G/J 中所有 P0，先做防回归护城河。
2. **批次 2（P1 主流程 46 条）**：补齐异常恢复和降级体验。
3. **批次 3（移动端/可访问性 8 条）**：修正跨设备和键盘路径。
4. **批次 4（学生端闭环 12 条 + 体验类 P2）**：完成平台端到端闭环覆盖。

如果直接转 Playwright，可按文件切分：

- `teacher-chat-critical.spec.ts`（A+B）
- `teacher-workbench-flow.spec.ts`（C+D+E）
- `teacher-routing-provider.spec.ts`（F）
- `teacher-recovery-state.spec.ts`（G+H）
- `student-learning-loop.spec.ts`（I）
- `platform-consistency-security.spec.ts`（J）

