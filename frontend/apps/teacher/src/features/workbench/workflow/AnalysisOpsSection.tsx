import type {
  AnalysisOpsRecommendation,
  AnalysisOpsSectionProps,
  AnalysisReportSummary,
  AnalysisReportsDomainSummary,
} from '../../../types/workflow'

const buildDomain = (report: Pick<AnalysisReportSummary, 'domain' | 'analysis_type'>) => {
  return String(report.domain || report.analysis_type || '').trim() || 'unknown'
}

const buildFallbackDomainSummaries = (reports: AnalysisReportSummary[]): AnalysisReportsDomainSummary[] => {
  const domains = new Map<string, AnalysisReportsDomainSummary>()
  for (const report of reports) {
    const domain = buildDomain(report)
    const current = domains.get(domain) ?? {
      domain,
      total_reports: 0,
      review_required_reports: 0,
      queued_review_items: 0,
      status_counts: {},
    }
    current.total_reports += 1
    if (report.review_required) current.review_required_reports += 1
    current.status_counts = {
      ...(current.status_counts || {}),
      [report.status]: ((current.status_counts || {})[report.status] || 0) + 1,
    }
    domains.set(domain, current)
  }
  return Array.from(domains.values())
}

const pickTopRecommendation = (value: unknown): AnalysisOpsRecommendation | null => {
  if (!Array.isArray(value) || value.length === 0) return null
  const first = value[0]
  return first && typeof first === 'object' ? (first as AnalysisOpsRecommendation) : null
}

export default function AnalysisOpsSection(props: AnalysisOpsSectionProps) {
  const summary = props.analysisReportsSummary
  const domainSummaries = summary?.domains?.length ? summary.domains : buildFallbackDomainSummaries(props.analysisReports)
  const totalReports = summary?.total_reports ?? props.analysisReports.length
  const reviewRequiredReports = summary?.review_required_reports ?? props.analysisReports.filter((item) => item.review_required).length
  const unresolvedReviewItems = props.analysisReviewSummary?.unresolved_items ?? 0
  const currentReportIds = props.analysisReports.map((item) => String(item.report_id || '').trim()).filter(Boolean)
  const opsSummary = props.analysisOpsSnapshot?.ops_summary
  const topRecommendation = pickTopRecommendation(props.analysisOpsSnapshot?.review_feedback?.recommendations)
  const runtimeRisk = String(opsSummary?.top_failure_reason || '').trim() || '暂无'
  const reviewReason = String(opsSummary?.top_review_reason || '').trim() || '暂无'
  const recommendationAction = String(topRecommendation?.recommended_action || '').trim() || '暂无建议'
  const recommendationType = String(topRecommendation?.action_type || '').trim() || '无'

  return (
    <div className="grid gap-3 border border-[#e2e8f0] rounded-[14px] bg-[#f8fafc] p-3">
      <div className="grid gap-2 md:grid-cols-3">
        <div className="rounded-[12px] bg-white border border-border p-3 grid gap-1">
          <span className="text-[12px] text-muted">总报告数</span>
          <strong className="text-[18px] text-ink">{totalReports}</strong>
        </div>
        <div className="rounded-[12px] bg-white border border-border p-3 grid gap-1">
          <span className="text-[12px] text-muted">待复核报告</span>
          <strong className="text-[18px] text-ink">{reviewRequiredReports}</strong>
        </div>
        <div className="rounded-[12px] bg-white border border-border p-3 grid gap-1">
          <span className="text-[12px] text-muted">待处理复核</span>
          <strong className="text-[18px] text-ink">{unresolvedReviewItems}</strong>
        </div>
      </div>

      {props.analysisOpsSnapshot ? (
        <div className="grid gap-2 md:grid-cols-3">
          <div className="rounded-[12px] bg-white border border-border p-3 grid gap-1">
            <span className="text-[12px] text-muted">运行风险</span>
            <strong className={`text-[16px] ${opsSummary?.needs_attention ? 'text-[#b91c1c]' : 'text-ink'}`.trim()}>{runtimeRisk}</strong>
            <div className="text-[12px] text-muted">{opsSummary?.needs_attention ? '当前有需要关注的运行风险。' : '当前未发现显著运行风险。'}</div>
          </div>
          <div className="rounded-[12px] bg-white border border-border p-3 grid gap-1">
            <span className="text-[12px] text-muted">复核热点</span>
            <strong className="text-[16px] text-ink">{reviewReason}</strong>
            <div className="text-[12px] text-muted">优先处理最常见的人工复核原因。</div>
          </div>
          <div className="rounded-[12px] bg-white border border-border p-3 grid gap-1">
            <span className="text-[12px] text-muted">优先建议</span>
            <strong className="text-[16px] text-ink">{recommendationType}</strong>
            <div className="text-[12px] text-muted whitespace-pre-wrap">{recommendationAction}</div>
          </div>
        </div>
      ) : null}

      {domainSummaries.length > 0 ? (
        <div className="flex gap-2 flex-wrap">
          {domainSummaries.map((item) => (
            <button
              key={item.domain}
              type="button"
              className={`ghost text-[12px] ${props.analysisDomainFilter === item.domain ? 'border-[#6366f1] text-[#4338ca]' : ''}`.trim()}
              onClick={() => props.setAnalysisDomainFilter(item.domain)}
            >
              {item.domain} · {item.total_reports} 份 · 待复核 {item.review_required_reports}
            </button>
          ))}
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="text-[12px] text-muted whitespace-pre-wrap">
          当前筛选：{currentReportIds.length} 份报告
          {domainSummaries.length > 0 ? ' · 可点击域卡片快速切换筛选' : ''}
        </div>
        <button
          type="button"
          className="ghost"
          disabled={currentReportIds.length === 0}
          onClick={() => void props.rerunAnalysisReportsBulk(currentReportIds)}
        >
          批量重跑当前筛选（{currentReportIds.length}）
        </button>
      </div>
    </div>
  )
}
