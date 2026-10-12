# 老师日常教学闭环

- 适用角色：老师
- 前置条件：老师端可访问，API 服务健康；已登录老师账号
- 最后验证日期：2026-10-12

## 目标
完成一次作业主线：**选 kind → 选 source → upload | bank | ai 进草稿 → 发布草稿 → 查看完成进度**。这不是考试分析流程，也不再走 2026-02-15 的「上传试卷生成讲评」路径。

- 作业类型 `assignment_kind`：做题 / 情景 / 科学史 / 实践。
- 草稿来源 `content_source`：上传文件 / 题库选题 / AI 起草。三者都是老师草稿，**confirm 才发布**；学生永远看不到 draft。
- **补练仅做题**。非做题没有补练入口；即使误开也会 409 `practice_not_applicable`。
- 「需要讨论」是陪练提示，**不是完成条件**。学生交了照片/产物后仍算完成，即使从没聊天。讨论不能替代提交（除非老师关掉「需要提交」，默认保持开）。

学生侧配套说明见 `docs/how-to/student-login-and-submit.md`（今日任务 + 按 kind 的提交按钮，对话不算提交；补练只在做题作业已交之后）。

## 步骤
1. 打开老师端 `http://localhost:3002` 并登录。
2. 打开工作台「工作流」。主线先出现「作业类型」和「草稿来源」选择器，不是直接上传，也不是考试上传。
3. **选 kind**：做题作业 / 情景作业 / 科学史作业 / 实践作业（默认做题）。
4. **选 source**：上传文件 / 题库选题 / AI 起草。题库在非做题时禁用，悬停文案是「题库仅用于做题作业」。换 kind/source 若已有草稿，确认后会清空，避免把题库稿改成情景。
5. **按来源生成草稿**（结果都进同一「解析结果（审核/修改）」）：
   - **上传**（`content_source=upload`）：填写作业编号、学科、范围（公共 / 班级 / 私人），选择作业文件（必填）和答案（可选），提交解析。班级作业的班级应来自 `GET /teacher/roster`，不要手填未任教班级。`POST /assignment/upload/start` 会带上 `assignment_kind`。等待后台解析完成。做题解析 0 题会失败；非做题允许 0 题，用材料填 brief。
   - **题库**（仅做题）：填知识点与题量（1–20，默认 5）→ `POST /assignment/draft/from-bank`。空库会看到「题库不足」（409 `question_bank_insufficient`），不会对学生编题。
   - **AI 起草**：做题填知识点（默认 `generate=true`）；非做题填主题/学段 + 可选 seed，**不是**先手打完整 brief。`POST /assignment/generate` 返回 draft；老师在草稿里改模型写的 brief / 讨论目标。
6. **审核草稿**：可先「保存草稿」。做题补全 8 点要求；非做题补全 `brief`（不要再凑 4 条易错），可选填「量规（每行一条）」`data-testid="draft-rubric"`（写入 `requirements.rubric` → `rubric.md`）。做题不展示量规框。完成条件勾选：
   - 需要提交（默认开）
   - **需要讨论（陪练提示，不作为完成条件）**
   - 允许补练（仅做题可开；关掉则学生不能点补练）
7. **发布草稿**：工作台主按钮就是「发布草稿」（`data-testid="assignment-confirm-button"`）。调用 `POST /assignment/upload/confirm`。有上传 `job_id` 走 job 路径；bank / AI 只有 `assignment_id` 时先保存再 confirm `{ assignment_id, ... }`，不要因为没有 job 就放弃。缺项时按钮不可用。
8. **进度**：发布成功后看「作业完成情况」（`GET /teacher/assignment/progress`）。跟进应交 / 完成 / 已评分 / 逾期。做题进度另有补练列；非做题显示「不适用」。学生正式提交走学生端提交按钮，不是聊天。进度行另有：
   - **考查纪要**（`progress-exam-notes-{sid}`）：展开 quotes / 陪练摘录。「采纳为评语」会 POST **合并后的完整** `adopted_coach_excerpts`（服务端整表替换）。无陪练 → 「无陪练纪要」。讨论仍不是完成条件。
   - **非做题量规**：assignment 级 `rubric.md` 检查单。无文件 → 「无量规，请老师覆盖」。有建议分才出现「按量规给分」；照片-only / `suggested_score=null` 隐藏该按钮，手填覆盖。做题不展示 assignment 量规。
   - **画像片段**（`progress-portrait-{sid}`）：薄弱 / 下一步 / 最近。读该生盘上完整 profile JSON，不是名册三字段 listing。
9. 需要下线时，在进度面板归档（`POST /assignment/{id}/archive`）；取消归档走 unarchive。

## 验证结果
- 能先选 kind 和 source，再看到对应的上传 / 题库 / AI 表单，最后出现可编辑草稿。
- 「发布草稿」成功后，`data/assignments/<assignment_id>/` 有作业，进度面板能刷出人数。
- 学生端「今日任务」能看到该作业（已发布且学生在名册内）；空态是「老师尚未布置」，没有生成按钮，也没有补练卡。
- 学生提交后，进度里的已评分/完成会更新；`submitted=false` 不会把首页标成已交。补练不改变 `counts.submitted` / 官方分。
- 非做题进度能看到量规 / 考查纪要 / 画像；空库时题库来源与补练仍 409，这是预期。

## 常见失败
- 上传失败：检查文件格式、大小与网络（见 `docs/reference/upload-resource-guardrails.md`）。
- 无法发布：做题 8 点未补全，或非做题缺 brief，或解析尚未 `done`。
- 进度空白：作业未发布，或当前账号不是该作业 `teacher_id`。
- 学生看不到作业：未发布、不在名册、或作业仍是 `orphan_draft`。孤儿作业需管理员 `POST /auth/admin/assignments/{id}/claim` 认领到合法老师和学科（禁止默认 id `teacher`）。
- 学科文案不对：pack 从 `packs/subjects/<id>/` 读取；未知学科回退 `generic`，不会回退物理。

## 空库 409 是预期（本波不填 CSV）
题库来源 `POST /assignment/draft/from-bank` 与学生补练在 `DATA_DIR/question_bank/questions.csv` 只有表头（0 行数据）时返回 409 `question_bank_insufficient`（文案「题库不足」）。这是正确失败，不是要修的洞；本波 **不** seed / 填写该 CSV。可选确认：

```bash
python3 - <<'PY'
from pathlib import Path
import os
p = Path(os.environ.get("DATA_DIR", "data")) / "question_bank" / "questions.csv"
lines = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
print(p, "data_rows", max(0, len(lines) - 1))
PY
```

`data_rows==0` → 补练 / from-bank 409 为预期。无题库仍可走上传 + AI 布置、学生提交、非做题量规、画像。`AUTH_TOKEN_SECRET` 轮换是 Owner 运维（见 `docs/how-to/auth-and-account-troubleshooting.md` 生产 bootstrap 勾选），不在本波 PR。

## 布置物理作业
物理是学科，不是单独产品。名册里该老师要有 `subject_id=physics` 的任教记录，布置时学科选「物理」，其余步骤与上面相同。

任教物理的老师登录后，能力列表会**额外**出现 pack 附属能力（课堂采集 / 核心例题 / 学生重点）。未任教物理的老师看不到它们。布置课后作业不依赖这些附属能力。

## 相关文档
- HTTP 作业接口：`docs/http_api.md`
- 学生登录与提交：`docs/how-to/student-login-and-submit.md`
- 孤儿认领与 pack 路径：`docs/http_api.md`（「孤儿作业认领」「学科 Pack」）
- 下一阶段设计：`docs/plans/2026-10-10-next-phase-gapfill-design.md`
- 无题库提分（考查清单 / 量规 / 画像 / 发布草稿）：`docs/plans/2026-10-12-score-up-without-bank-design.md`
