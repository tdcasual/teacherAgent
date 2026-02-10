# 2026-02-10 Physics Subject Fallback Design

## 背景

当前考试上传解析对成绩表结构存在较强假设：优先识别“姓名 + 班级/准考证号 + 小题列（1/2/12(1)...）”。
在真实学校成绩单中，经常出现“多科汇总表”，只包含“总分 + 科目/分数（重复列）”，没有小题分。
该情况下旧流程可能直接退化到 `total`，导致考试分析只能输出总分层面，无法进行物理学科分析。

## 目标

1. 保持优先级：`question > subject(physics) > total`。
2. 当无小题分但存在物理科目分时，自动提取物理分并进入 `score_mode=subject`。
3. 支持多样表头（如“考生姓名/考号/科目/分数”）与“有/无单科排名”混杂格式。
4. 在混乱数据下避免误读：不能稳定识别时不要盲猜。

## 实施范围（本次实现）

### 1) xlsx 结构解析增强（规则优先）

文件：`skills/physics-teacher-ops/scripts/parse_scores.py`

- 放宽姓名列识别：支持 `姓名/考生姓名/学生姓名`。
- 支持学生标识列：`准考证号/考号/学号`。
- 兼容班级列别名：`班级/行政班/教学班/班别`。
- 新增 subject 模式提取：
  - 识别 `科目` 列并寻找相邻 `分数/成绩/得分` 列；
  - 在行内科目值为“物理”时抽取对应分数；
  - 排除排名型字段（如“班次/校次”“1/29”）。
- 过滤统计行（平均分、最高分、最低分等）。
- 若无小题且识别到物理分，写入：
  - `question_id = SUBJECT_PHYSICS`
  - `raw_label = 物理`（或原科目名）

### 2) score_mode 判定扩展

文件：`services/api/exam_upload_parse_service.py`

- 旧逻辑：仅区分 `total` 与 `question`。
- 新逻辑：
  - 仅 `TOTAL` -> `score_mode=total`
  - 全部为 `SUBJECT_` 前缀 -> `score_mode=subject`
  - 其他 -> `score_mode=question`

### 3) 低置信度确认门控（needs_confirm）

- `parse_scores.py` 支持输出结构化报告（`--report`）：
  - `mode` / `confidence` / `needs_confirm`
  - `subject.coverage` / `unresolved_students` / `candidate_columns`
- 上传解析阶段会把报告写入：
  - `parsed.json.score_schema`
  - `job.json.score_schema`
  - `parsed.json.needs_confirm` / `job.json.needs_confirm`
- 确认创建考试时新增门控：
  - 若 `needs_confirm=true` 且草稿 `score_schema.confirm != true`，则阻断确认并返回 `score_schema_confirm_required`
  - 老师在草稿保存 `score_schema.confirm=true` 后可继续 confirm

### 4) 候选映射 ID 与多文件聚合（本轮新增）

- 解析报告中的每个候选映射都带稳定 `candidate_id`（如 `pair:4:5` / `direct:12`）。
- 草稿确认建议使用 `score_schema.subject.selected_candidate_id`，而不是单纯布尔 `confirm`。
- 解析阶段支持读取已选 `selected_candidate_id` 回灌解析器，仅使用该候选映射重跑。
- 多成绩文件时不再简单覆盖：
  - `score_schema.sources` 保存每个文件的原始报告；
  - 聚合 `coverage/confidence/unresolved_students/candidate_columns` 生成全局决策；
  - `selected_candidate_id` 会写入聚合结果并触发确认通过。

## 测试策略与结果

### 新增/更新测试

1. `tests/test_exam_upload_flow.py`
   - 新增 `test_exam_upload_subject_score_sheet_extracts_physics`
   - 使用“考生姓名 + 考号 + 总分 + 科目/分数重复列”模拟真实成绩单
   - 断言：
     - 上传能完成；
     - 草稿 `meta.score_mode == subject`；
     - 题目为 `SUBJECT_PHYSICS`；
     - 落库分数正确抽取（42/35）。

2. `tests/test_exam_upload_parse_service.py`
   - 新增 `test_subject_question_ids_set_subject_score_mode`
   - 断言 `SUBJECT_` 题号会触发 `score_mode=subject`。

### 回归测试

执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_exam_upload_flow.py \
  tests/test_exam_upload_parse_service.py \
  tests/test_exam_upload_api_service.py \
  tests/test_exam_upload_confirm_service.py
```

结果：`17 passed`。

## 当前边界与下一步

本次实现优先解决“多科汇总表中的物理分提取”这一主路径问题，并确保不影响已有小题流程。
尚未在本次代码中完整落地的能力（后续可继续）：

1. 草稿页内更细粒度的“候选列点选 UI”与样本预览交互（后端已支持 `selected_candidate_id`）
2. `chaos_fallback`（极端混乱 Excel 的坐标文本化兜底抽取）
3. 覆盖率阈值（85%）与置信度阈值（0.82）的可配置化（当前为固定阈值）

这些能力建议作为下一阶段增量迭代，在现有 `subject` 主路径稳定后逐步接入。
