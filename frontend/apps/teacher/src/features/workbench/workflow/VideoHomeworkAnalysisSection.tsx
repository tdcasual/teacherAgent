import type { VideoHomeworkAnalysisSectionProps } from '../../../types/workflow'

const asStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value.map((item) => String(item || '').trim()).filter(Boolean)
}

const asRecord = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return value as Record<string, unknown>
}

export default function VideoHomeworkAnalysisSection(props: VideoHomeworkAnalysisSectionProps) {
  if (!props.videoHomeworkFeatureEnabled || !props.selectedAnalysisReport) return null

  const report = props.selectedAnalysisReport.report
  const domain = String(report.domain || report.analysis_type || '').trim()
  if (domain !== 'video_homework') return null

  const artifact = props.selectedAnalysisReport.analysis_artifact
  const artifactMeta = props.selectedAnalysisReport.artifact_meta
  const completionOverview = asRecord(artifact.completion_overview)
  const confidenceAndGaps = asRecord(artifact.confidence_and_gaps)
  const expressionSignals = Array.isArray(artifact.expression_signals) ? artifact.expression_signals : []
  const evidenceClips = Array.isArray(artifact.evidence_clips) ? artifact.evidence_clips : []
  const recommendations = asStringArray(artifact.teaching_recommendations)
  const availableCount = props.analysisReports.filter(
    (item) => String(item.domain || item.analysis_type || '').trim() === 'video_homework',
  ).length

  return (
    <section className="mt-3 bg-surface border border-border rounded-[14px] p-[10px] shadow-sm grid gap-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="grid gap-1">
          <h3>视频作业分析</h3>
          <div className="text-[12px] text-muted">当前对象：{report.target_id} · 已收录 {availableCount} 份视频分析报告</div>
        </div>
        <div className="text-[11px] text-muted">
          提交人：{String(artifactMeta.student_id || '未知')} · 作业：{String(artifactMeta.assignment_id || '未关联')}
        </div>
      </div>

      <div className="text-[14px] text-ink whitespace-pre-wrap">
        {String(artifact.executive_summary || '暂无视频作业分析结论')}
      </div>

      <div className="grid gap-1 rounded-xl bg-[#f8fafc] p-[10px_12px] text-[12px] text-muted">
        <strong className="text-[13px] text-ink">完成度概览</strong>
        <div>
          状态：{String(completionOverview.status || 'unknown')} · 时长：{String(completionOverview.duration_sec ?? '未知')} 秒
        </div>
        <div className="whitespace-pre-wrap">{String(completionOverview.summary || '暂无完成度说明')}</div>
      </div>

      {expressionSignals.length > 0 ? (
        <div className="grid gap-1">
          <strong className="text-[13px]">表达 / 展示信号</strong>
          {expressionSignals.map((item, index) => {
            const entry = asRecord(item)
            return (
              <div key={index} className="text-[12px] text-muted">
                {String(entry.title || `信号 ${index + 1}`)}：{String(entry.detail || entry.summary || '')}
              </div>
            )
          })}
        </div>
      ) : null}

      {evidenceClips.length > 0 ? (
        <div className="grid gap-1">
          <strong className="text-[13px]">证据片段</strong>
          {evidenceClips.map((item, index) => {
            const entry = asRecord(item)
            return (
              <div key={index} className="text-[12px] text-muted whitespace-pre-wrap">
                {String(entry.label || `片段 ${index + 1}`)}（{String(entry.start_sec ?? '?')}s - {String(entry.end_sec ?? '?')}s）：
                {String(entry.excerpt || '暂无摘录')}
              </div>
            )
          })}
        </div>
      ) : null}

      {recommendations.length > 0 ? (
        <div className="grid gap-1">
          <strong className="text-[13px]">教学建议</strong>
          {recommendations.map((item) => (
            <div key={item} className="text-[12px] text-muted">- {item}</div>
          ))}
        </div>
      ) : null}

      <div className="text-[12px] text-muted">
        置信度：{String(confidenceAndGaps.confidence ?? artifactMeta.parse_confidence ?? '未知')} · 缺口：
        {asStringArray(confidenceAndGaps.gaps).join('、') || '无'}
      </div>
    </section>
  )
}
