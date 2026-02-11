# 2026-02-11 E2E 补测可执行清单（Gap Closure）

## 0) 背景与目标

- 当前前端 E2E 已形成大规模覆盖（Teacher + Student 体系），并且与全平台矩阵（A-J）基本对齐。
- 当前主要缺口不在“矩阵 case 数量”，而在以下三类：
  1) **真实后端链路覆盖不足**（多数是 route mock）
  2) **部分 API 能力面缺少端到端回归**（尤其 student/import/generate/render）
  3) **CI 门禁分层不完整**（student 全量/跨浏览器/a11y 仍可加强）

本清单目标：在不打断现有稳定回归的前提下，按优先级补齐高风险链路。

---

## 1) 执行原则

- 先补 P0（数据一致性、重复提交、流程可恢复）。
- 保持“PR 快速反馈 + Nightly 深链路”双轨：
  - PR：mock/contract + 少量系统关键链路
  - Nightly：真实 API + 落盘 + 重启恢复
- 每条用例必须包含 `Given / When / Then`，并附目标 spec 文件。

---

## 2) P0（本周必须补齐）

### P0-1 老师端真实后端深链路（作业）

- [x] **ID：P0-T-REAL-ASSIGN-001**
  - Given：真实后端可用，作业上传所需文件齐全
  - When：老师端执行 `start -> status -> draft/save -> confirm`
  - Then：
    - UI 状态流完整且可恢复
    - `teacherActiveUpload` 终态清理
    - `data/assignments/<assignment_id>/` 核心文件可读且字段一致
  - 目标文件：`frontend/e2e/teacher-system-real-assignment.spec.ts`（新建）

- [x] **ID：P0-T-REAL-ASSIGN-002**
  - Given：confirm 接口超时/500
  - When：重复点击“创建作业”
  - Then：仅一次有效 confirm；失败可重试；无半成品目录
  - 目标文件：`frontend/e2e/teacher-system-real-assignment.spec.ts`

### P0-2 老师端真实后端深链路（考试）

- [x] **ID：P0-T-REAL-EXAM-001**
  - Given：真实后端可用，试卷 + 成绩文件齐全
  - When：执行 `start -> status -> draft/save -> confirm`
  - Then：
    - `data/exams/<exam_id>/` 与 `data/analysis/<exam_id>/` 同步落地
    - scoring 状态与 UI 标签一致
    - 活跃上传标记终态清理
  - 目标文件：`frontend/e2e/teacher-system-real-exam.spec.ts`（新建）

- [x] **ID：P0-T-REAL-EXAM-002**
  - Given：解析已 done，confirm 前页面刷新
  - When：恢复后继续 confirm
  - Then：不重复写盘；终态一致；可继续后续分析读取
  - 目标文件：`frontend/e2e/teacher-system-real-exam.spec.ts`

### P0-3 学生端真实提交链路

- [ ] **ID：P0-S-REAL-SUBMIT-001**
  - Given：真实后端可用，学生带多图提交
  - When：调用 `/student/submit` 后读取 profile
  - Then：提交记录、评分摘要、画像变化三者一致
  - 目标文件：`frontend/e2e/student-system-real-submit.spec.ts`（新建）

- [ ] **ID：P0-S-REAL-SUBMIT-002**
  - Given：网络抖动 + 重试
  - When：学生重复触发提交
  - Then：后端仅一条有效提交记录（幂等/去重成立）
  - 目标文件：`frontend/e2e/student-system-real-submit.spec.ts`

### P0-4 老师端跨 Tab 并发与恢复

- [ ] **ID：P0-T-CROSSTAB-001**
  - Given：同一 teacher_id 打开两个标签页
  - When：近同时发送聊天消息
  - Then：只创建一个 pending job；无重复 user bubble
  - 目标文件：`frontend/e2e/teacher-high-risk-resilience.spec.ts`（新建）

- [ ] **ID：P0-T-CROSSTAB-002**
  - Given：Tab A 持有 pending upload/chat
  - When：Tab B 清理本地状态或切换会话
  - Then：Tab A 主流程不中断；Tab B 正确 re-verify
  - 目标文件：`frontend/e2e/teacher-high-risk-resilience.spec.ts`

### P0-5 服务重启恢复（真实链路）

- [ ] **ID：P0-SYSTEM-RESTART-001**
  - Given：存在 in-flight chat/upload job
  - When：API 服务重启后继续查询 status
  - Then：job 可恢复追踪，前端不卡死、不误终态
  - 目标文件：`frontend/e2e/platform-system-restart.spec.ts`（新建）

---

## 3) P1（下周补齐）

### P1-1 API 能力面 E2E

- [ ] **ID：P1-API-STUDENT-PROFILE-001**
  - Given：已有学生画像
  - When：调用 `/student/profile/update`
  - Then：`GET /student/profile/{id}` 读取到一致更新
  - 目标文件：`frontend/e2e/api-surface-regression.spec.ts`（新建）

- [ ] **ID：P1-API-STUDENT-IMPORT-001**
  - Given：导入文件格式合法/非法两组输入
  - When：调用 `/student/import`
  - Then：成功路径写入可见；失败路径错误可读且不中断系统
  - 目标文件：`frontend/e2e/api-surface-regression.spec.ts`

- [ ] **ID：P1-API-ASSIGNMENT-GEN-001**
  - Given：有效生成参数
  - When：`/assignment/generate -> /assignment/render`
  - Then：生成内容与渲染结果一致且可下载/可展示
  - 目标文件：`frontend/e2e/api-surface-regression.spec.ts`

- [ ] **ID：P1-API-LIST-READ-001**
  - Given：已有考试/作业/课次数据
  - When：读取 `/exams` `/assignments` `/lessons`
  - Then：列表项字段完整，前端关键入口可消费
  - 目标文件：`frontend/e2e/api-surface-regression.spec.ts`

### P1-2 CI 门禁补强

- [ ] 新增 `student-e2e.yml`：PR 必跑学生端核心链路。
- [ ] `teacher-e2e.yml` 保持快速稳定，重链路迁移到 nightly。
- [ ] 新增 nightly workflow：执行真实后端链路（P0 Real + Restart）。

---

## 4) P2（体验与平台一致性）

- [ ] **ID：P2-BROWSER-SMOKE-001**
  - 在 Firefox/WebKit 跑最小 smoke（发送、会话切换、上传入口可达）。
  - 目标文件：`frontend/e2e/cross-browser-smoke.spec.ts`（新建）

- [ ] **ID：P2-A11Y-SMOKE-001**
  - 关键页面接入 a11y 快速扫描（菜单、表单、按钮可访问性）。
  - 目标文件：`frontend/e2e/a11y-smoke.spec.ts`（新建）

---

## 5) 建议的文件与命令落位

### 推荐新增 spec

- `frontend/e2e/teacher-system-real-assignment.spec.ts`
- `frontend/e2e/teacher-system-real-exam.spec.ts`
- `frontend/e2e/student-system-real-submit.spec.ts`
- `frontend/e2e/teacher-high-risk-resilience.spec.ts`
- `frontend/e2e/platform-system-restart.spec.ts`
- `frontend/e2e/api-surface-regression.spec.ts`
- `frontend/e2e/cross-browser-smoke.spec.ts`
- `frontend/e2e/a11y-smoke.spec.ts`

### 推荐脚本（package.json）

- `e2e:teacher:real`
- `e2e:student:real`
- `e2e:nightly`
- `e2e:cross-browser-smoke`
- `e2e:a11y`

---

## 6) 验收标准（DoD）

- P0 清单项全部可在 CI 或 nightly 稳定运行（连续 3 次无随机失败）。
- 真实后端链路覆盖作业、考试、学生提交三条主流程。
- 服务重启恢复与跨 Tab 并发用例纳入固定回归。
- API 能力面缺口（profile update/import/generate/render/list）至少具备 1 条端到端正向 + 1 条异常路径。
- 补测后更新一份覆盖映射表（case id -> spec -> workflow）。

---

## 7) 建议执行顺序（最短收益路径）

1. 先落 `P0-T-REAL-ASSIGN` + `P0-T-REAL-EXAM`。
2. 再落 `P0-T-CROSSTAB` + `P0-SYSTEM-RESTART`。
3. 接着补 `P0-S-REAL-SUBMIT`。
4. 最后补齐 P1 API 能力面和 P2 兼容性。

按上述顺序，通常可以在第 1~2 步就显著提升“高风险回归防护力”。
