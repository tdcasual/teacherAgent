# Backend 多角度评分设计（趋势型，按技术层模块）

Date: 2026-02-13
Status: Implemented (v1 script + config + tests)

## 1. 目标与范围

本设计用于后端治理与汇报，提供：

- 全局总分（100 分制）
- 模块分（按技术层：`routes / services / workers / runtime / wiring / skills`）
- 维度分（多角度雷达）
- 趋势判断（近 4 周改善或退化）

评分口径为“趋势分”：兼顾当前状态与近期变化，避免只看某一时点。

## 2. 评分框架

### 2.1 模块分

每个模块最终得分：

`module_score = clamp(0.7 * state_score + 0.3 * trend_score + bonus - penalty, 0, 100)`

其中：

- `state_score`：当前状态分
- `trend_score`：近 4 周趋势分
- `bonus`：持续改进奖励
- `penalty`：事故/安全/回归惩罚

### 2.2 全局总分

`global_score = Σ(module_score_m * risk_weight_m)`

`risk_weight` 按请求量、影响半径、变更频率计算，避免低风险模块拉高全局评价。

## 3. 多角度维度与权重

### 3.1 统一母体权重（全局口径）

- 正确性：25
- 可靠性：25
- 可维护性：20
- 安全性：15
- 交付效率：10
- 成本性能：5

### 3.2 技术层模块差异化权重（v1）

- `routes`：正确性 30 / 安全性 25 / 可靠性 20 / 可维护性 15 / 交付 5 / 成本 5
- `services`：正确性 30 / 可维护性 25 / 可靠性 20 / 安全性 15 / 交付 5 / 成本 5
- `workers`：可靠性 35 / 正确性 20 / 成本 15 / 可维护性 15 / 安全性 10 / 交付 5
- `runtime`：可靠性 40 / 安全性 25 / 可维护性 20 / 正确性 10 / 成本 5
- `wiring`：可维护性 35 / 正确性 25 / 可靠性 20 / 安全性 10 / 交付 10
- `skills`：正确性 30 / 安全性 25 / 可维护性 20 / 可靠性 15 / 交付 10

## 4. 计算方法（趋势 + 奖惩）

### 4.1 KPI 标准化

对每个 KPI 归一化到 0-100：

- 越高越好：`score = clamp(100 * actual / target, 0, 100)`
- 越低越好：`score = clamp(100 * target / actual, 0, 100)`

建议使用 7 天移动中位数平滑噪声。

### 4.2 当前状态分

`state_score = Σ(kpi_score_i * kpi_weight_i)`

### 4.3 趋势分（近 4 周）

建议：

`trend_score = clamp(50 + 30*improvement - 15*stability - 10*regression_events_norm, 0, 100)`

- `improvement`：相对 4 周前改善幅度（归一到 -1~1）
- `stability`：周波动系数（越高越差）
- `regression_events_norm`：关键回退事件归一值（如 SLO 破线、P1 回归）

### 4.4 奖惩策略

- 奖励（`+3~+8`）：连续 4 周无关键回归且核心指标持续改善
- 惩罚（`-5~-20`）：P0/P1 事故、鉴权缺口、高危漏洞未及时修复、SLO 连续破线

## 5. 数据流与治理闭环

### 5.1 数据流

1. 采集：CI 测试、静态检查、运行时指标、发布与缺陷记录
2. 标准化：统一为 `module + metric + timestamp + value + source`
3. 计算：产出 `module_score / global_score / top_risks / top_improvements`
4. 展示：管理层总分、TL 模块雷达、开发 KPI 明细

### 5.2 异常处理

- 缺失数据：标记 `insufficient_data`，不直接记 0 分
- 数据冲突：线上真实性优先（例如线上回归覆盖 CI 乐观结果）
- 刷分抑制：跨维度约束（测试分高但回归高则触发惩罚）

### 5.3 验证机制

- 单测：公式/边界/奖惩
- 回放：近 8-12 周历史数据回放
- 人工抽样：抽查高分/低分模块校准权重

## 6. 两周落地顺序（v1）

### Week 1

1. 锁定指标字典与模块映射（每个维度 2-4 个 KPI）
2. 建立评分配置文件（权重、阈值、奖惩规则）
3. 接入现有基线：
   - `config/backend_quality_budget.json`
   - `docs/operations/slo-and-observability.md`
4. 产出首次离线评分（近 4 周）

### Week 2

1. 接入自动化采集（每日）
2. 实现每周评分任务（周报）
3. 加入“异常数据与冲突告警”
4. 完成回放校准并冻结 v1 权重

## 7. 报表输出模板（v1）

### 7.1 总览

- Global Score: `82.4 / 100`（+3.1 WoW）
- 风险最高模块：`runtime`（可靠性退化）
- 改善最快模块：`services`（可维护性 + 正确性提升）

### 7.2 模块分

- routes: `79.2`
- services: `85.0`
- workers: `76.3`
- runtime: `72.8`
- wiring: `81.6`
- skills: `84.1`

### 7.3 行动项

1. runtime：收敛 p95 波动并修复连续告警根因
2. workers：降低队列堆积并控制失败重试风暴
3. routes：补齐鉴权与输入校验缺口

## 8. 非目标（v1）

- 不追求日内实时评分
- 不引入过多主观打分项
- 不把评分直接等同于团队绩效

## 9. 落地产物与用法（v1）

已落地文件：

- 评分配置：`config/backend_multi_angle_scoring.json`
- 评分脚本：`scripts/quality/backend_multi_angle_scoring.py`
- 示例输入：`data/staging/backend_multi_angle_scoring_sample.json`
- 单测：`tests/test_backend_multi_angle_scoring.py`

运行示例：

```bash
python3 scripts/quality/backend_multi_angle_scoring.py \
  --config config/backend_multi_angle_scoring.json \
  --input data/staging/backend_multi_angle_scoring_sample.json \
  --output output/backend_multi_angle_scoring_report.json
```

输出说明：

- `global_score`：全局风险加权分
- `module_scores`：每个技术层模块的 `state_score / trend_score / module_score`
- `insufficient_dimensions`：数据缺失维度列表（不直接按 0 分处理）
- `top_risks` / `top_improvements`：风险与改善优先级提示
