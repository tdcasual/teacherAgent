import type {
  AnalysisReportSectionProps,
  AnalysisReportSummary,
} from '../../../types/workflow'

import AnalysisOpsSection from './AnalysisOpsSection'

const asStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value.map((item) => String(item || '').trim()).filter(Boolean)
}

const uniqueValues = (values: string[]) => Array.from(new Set(values.map((item) => String(item || '').trim()).filter(Boolean)))

const buildDomain = (report: Pick<AnalysisReportSummary, 'domain' | 'analysis_type'>) => {
  return String(report.domain || report.analysis_type || '').trim()
}

export default function AnalysisReportSection(props: AnalysisReportSectionProps) {
  if (!props.analysisFeatureEnabled) return null

  const recommendationList = asStringArray(
    props.selectedAnalysisReport?.analysis_artifact?.teaching_recommendations,
  )
  const keySignals = Array.isArray(props.selectedAnalysisReport?.analysis_artifact?.key_signals)
    ? props.selectedAnalysisReport?.analysis_artifact?.key_signals
    : []
  const confidenceAndGaps =
    (props.selectedAnalysisReport?.analysis_artifact?.confidence_and_gaps as Record<string, unknown> | undefined) || {}
  const reviewSet = new Set(props.analysisReviewQueue.map((item) => item.report_id))
  const domainOptions = uniqueValues(props.analysisReports.map((item) => buildDomain(item)))
  const strategyOptions = uniqueValues(props.analysisReports.map((item) => item.strategy_id))
  const targetTypeOptions = uniqueValues(props.analysisReports.map((item) => item.target_type))
  const statusOptions = uniqueValues(props.analysisReports.map((item) => item.status))
  const selectedReportSummary = props.analysisReports.find((item) => item.report_id === props.selectedAnalysisReportId)
  const selectedDomain = selectedReportSummary ? buildDomain(selectedReportSummary) : ''

  return (
    <section
      id="workflow-analysis-section"
      className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm grid gap-3"
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="m-0">统一分析报告</h3>
          {props.analysisFeatureShadowMode ? (
            <span className="text-[11px] rounded-full px-2 py-0.5 bg-[#eef2ff] text-[#4338ca]">
              Shadow
            </span>
          ) : null}
        </div>
        <button type="button" className="ghost" onClick={() => void props.refreshAnalysisReports()}>
          刷新
        </button>
      </div>

      <AnalysisOpsSection
        analysisReports={props.analysisReports}
        analysisReportsSummary={props.analysisReportsSummary}
        analysisReviewSummary={props.analysisReviewSummary}
        analysisDomainFilter={props.analysisDomainFilter}
        setAnalysisDomainFilter={props.setAnalysisDomainFilter}
        rerunAnalysisReportsBulk={props.rerunAnalysisReportsBulk}
      />

      <div className="grid gap-2 md:grid-cols-4">
        <label className="grid gap-1 text-[12px] text-muted">
          <span>分析域</span>
          <select
            aria-label="分析域"
            value={props.analysisDomainFilter}
            onChange={(event) => props.setAnalysisDomainFilter(event.target.value)}
          >
            <option value="">全部域</option>
            {domainOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-[12px] text-muted">
          <span>状态</span>
          <select
            aria-label="状态"
            value={props.analysisStatusFilter}
            onChange={(event) => props.setAnalysisStatusFilter(event.target.value)}
          >
            <option value="">全部状态</option>
            {statusOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-[12px] text-muted">
          <span>策略</span>
          <select
            aria-label="策略"
            value={props.analysisStrategyFilter}
            onChange={(event) => props.setAnalysisStrategyFilter(event.target.value)}
          >
            <option value="">全部策略</option>
            {strategyOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-[12px] text-muted">
          <span>对象类型</span>
          <select
            aria-label="对象类型"
            value={props.analysisTargetTypeFilter}
            onChange={(event) => props.setAnalysisTargetTypeFilter(event.target.value)}
          >
            <option value="">全部对象</option>
            {targetTypeOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </label>
      </div>

      {props.selectedAnalysisReportId ? (
        <div className="border border-[#c7d2fe] rounded-[14px] bg-[#eef2ff] p-3 grid gap-2">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="grid gap-1">
              <strong>当前对话对象</strong>
              <div className="text-[12px] text-[#4338ca] whitespace-pre-wrap">
                {props.selectedAnalysisReport?.report.target_id || props.selectedAnalysisReportId}
                {selectedDomain ? ` · ${selectedDomain}` : ''}
                {props.selectedAnalysisReport?.report.strategy_id ? ` · ${props.selectedAnalysisReport.report.strategy_id}` : ''}
              </div>
              <div className="text-[12px] text-muted">后续 chat follow-up 将优先基于这个对象继续分析。</div>
            </div>
            <button
              type="button"
              className="ghost"
              onClick={() => void props.selectAnalysisReport('', '')}
            >
              清除当前对象
            </button>
          </div>
        </div>
      ) : null}

      {props.analysisReportsLoading ? (
        <div className="p-[10px_12px] rounded-xl text-[12px] bg-[#e8f7f2] text-[#0f766e]">分析报告加载中…</div>
      ) : null}
      {props.analysisReportsError ? (
        <div className="p-[10px_12px] rounded-xl text-[12px] bg-danger-soft text-danger whitespace-pre-wrap">
          {props.analysisReportsError}
        </div>
      ) : null}
      {!props.analysisReportsLoading && !props.analysisReportsError && props.analysisReports.length === 0 ? (
        <div className="p-[10px_12px] rounded-xl text-[12px] bg-[#f8fafc] text-muted">暂无分析报告</div>
      ) : null}

      {props.analysisReports.length > 0 ? (
        <div className="grid gap-2">
          {props.analysisReports.map((report) => {
            const domain = buildDomain(report)
            const reviewRequired = reviewSet.has(report.report_id) || report.review_required || report.status === 'review'
            const selected = report.report_id === props.selectedAnalysisReportId
            return (
              <div
                key={report.report_id}
                className={`border rounded-[14px] p-3 grid gap-2 ${
                  selected ? 'border-[#6366f1] bg-[#f5f7ff]' : 'border-border bg-white'
                }`}
              >
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="grid gap-1">
                    <strong>{report.summary || report.target_id || report.report_id}</strong>
                    <div className="text-[12px] text-muted">{report.report_id}</div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap text-[11px]">
                    {domain ? (
                      <span className="rounded-full px-2 py-0.5 bg-[#eef2ff] text-[#4338ca]">{domain}</span>
                    ) : null}
                    <span className="rounded-full px-2 py-0.5 bg-[#f1f5f9] text-[#334155]">{report.status}</span>
                    <span className="rounded-full px-2 py-0.5 bg-[#f8fafc] text-muted">{report.strategy_id}</span>
                    {reviewRequired ? (
                      <span className="rounded-full px-2 py-0.5 bg-[#fff7ed] text-[#c2410c]">待复核</span>
                    ) : null}
                    {report.confidence != null ? (
                      <span className="rounded-full px-2 py-0.5 bg-[#ecfeff] text-[#155e75]">置信度 {report.confidence}</span>
                    ) : null}
                  </div>
                </div>
                <div className="text-[12px] text-muted whitespace-pre-wrap">
                  对象：{report.target_type} · {report.target_id}
                </div>
                <div className="flex gap-2 flex-wrap">
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => void props.selectAnalysisReport(report.report_id, domain)}
                  >
                    选择对象
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => void props.rerunAnalysisReport(report.report_id, domain)}
                  >
                    重新分析
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      ) : null}

      {props.selectedAnalysisReport ? (
        <div className="border border-border rounded-[14px] bg-white p-3 grid gap-2">
          <div className="text-[13px] text-muted">
            详情：{props.selectedAnalysisReport.report.target_id} · {props.selectedAnalysisReport.report.strategy_id}
          </div>
          <div className="text-[14px] text-ink whitespace-pre-wrap">
            {String(props.selectedAnalysisReport.analysis_artifact?.executive_summary || '暂无详细结论')}
          </div>
          {keySignals.length > 0 ? (
            <div className="grid gap-1">
              <strong className="text-[13px]">关键信号</strong>
              {keySignals.map((item, index) => {
                const entry = item as Record<string, unknown>
                return (
                  <div key={index} className="text-[12px] text-muted">
                    {String(entry.title || entry.signal || '关键信号')}：{String(entry.detail || entry.summary || '')}
                  </div>
                )
              })}
            </div>
          ) : null}
          {recommendationList.length > 0 ? (
            <div className="grid gap-1">
              <strong className="text-[13px]">教学建议</strong>
              {recommendationList.map((item) => (
                <div key={item} className="text-[12px] text-muted">- {item}</div>
              ))}
            </div>
          ) : null}
          <div className="text-[12px] text-muted">
            置信度：{String(confidenceAndGaps.confidence ?? '未知')} · 缺口：
            {asStringArray(confidenceAndGaps.gaps).join('、') || '无'}
          </div>
        </div>
      ) : null}
    </section>
  )
}
