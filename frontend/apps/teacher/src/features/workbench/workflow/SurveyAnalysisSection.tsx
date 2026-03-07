import type { SurveyAnalysisSectionProps } from '../../../types/workflow'

const asStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value.map((item) => String(item || '').trim()).filter(Boolean)
}

export default function SurveyAnalysisSection(props: SurveyAnalysisSectionProps) {
  if (!props.surveyFeatureEnabled) return null

  const recommendationList = asStringArray(
    props.selectedSurveyReport?.analysis_artifact?.teaching_recommendations,
  )
  const keySignals = Array.isArray(props.selectedSurveyReport?.analysis_artifact?.key_signals)
    ? props.selectedSurveyReport?.analysis_artifact?.key_signals
    : []
  const confidenceAndGaps =
    (props.selectedSurveyReport?.analysis_artifact?.confidence_and_gaps as Record<string, unknown> | undefined) || {}
  const reviewSet = new Set(props.surveyReviewQueue.map((item) => item.report_id))

  return (
    <section
      id="workflow-survey-section"
      className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm grid gap-3"
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="m-0">问卷分析</h3>
          {props.surveyFeatureShadowMode ? (
            <span className="text-[11px] rounded-full px-2 py-0.5 bg-[#eef2ff] text-[#4338ca]">
              Shadow
            </span>
          ) : null}
        </div>
        <button type="button" className="ghost" onClick={() => void props.refreshSurveyReports()}>
          刷新
        </button>
      </div>

      {props.surveyReportsLoading ? (
        <div className="p-[10px_12px] rounded-xl text-[12px] bg-[#e8f7f2] text-[#0f766e]">问卷报告加载中…</div>
      ) : null}
      {props.surveyReportsError ? (
        <div className="p-[10px_12px] rounded-xl text-[12px] bg-danger-soft text-danger whitespace-pre-wrap">
          {props.surveyReportsError}
        </div>
      ) : null}
      {!props.surveyReportsLoading && !props.surveyReportsError && props.surveyReports.length === 0 ? (
        <div className="p-[10px_12px] rounded-xl text-[12px] bg-[#f8fafc] text-muted">暂无问卷分析报告</div>
      ) : null}

      {props.surveyReports.length > 0 ? (
        <div className="grid gap-2">
          {props.surveyReports.map((report) => {
            const reviewRequired = reviewSet.has(report.report_id) || report.status === 'review'
            const selected = report.report_id === props.selectedSurveyReportId
            return (
              <div
                key={report.report_id}
                className={`border rounded-[14px] p-3 grid gap-2 ${
                  selected ? 'border-[#6366f1] bg-[#f5f7ff]' : 'border-border bg-white'
                }`}
              >
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="grid gap-1">
                    <strong>{report.class_name || report.report_id}</strong>
                    <div className="text-[12px] text-muted">{report.summary || '暂无摘要'}</div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap text-[11px]">
                    <span className="rounded-full px-2 py-0.5 bg-[#f1f5f9] text-[#334155]">{report.status}</span>
                    {reviewRequired ? (
                      <span className="rounded-full px-2 py-0.5 bg-[#fff7ed] text-[#c2410c]">待复核</span>
                    ) : null}
                    {report.confidence != null ? (
                      <span className="rounded-full px-2 py-0.5 bg-[#ecfeff] text-[#155e75]">置信度 {report.confidence}</span>
                    ) : null}
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <button type="button" className="ghost" onClick={() => void props.selectSurveyReport(report.report_id)}>
                    查看详情
                  </button>
                  <button type="button" className="ghost" onClick={() => void props.rerunSurveyReport(report.report_id)}>
                    重新分析
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      ) : null}

      {props.selectedSurveyReport ? (
        <div className="border border-border rounded-[14px] bg-white p-3 grid gap-2">
          <div className="text-[13px] text-muted">详情：{props.selectedSurveyReport.report.report_id}</div>
          <div className="text-[14px] text-ink whitespace-pre-wrap">
            {String(props.selectedSurveyReport.analysis_artifact?.executive_summary || '暂无详细结论')}
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
