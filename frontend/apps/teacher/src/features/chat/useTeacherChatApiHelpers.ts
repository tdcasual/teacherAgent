import type { ExecutionTimelineEntry, Skill } from '../../appTypes'
import type { AnalysisReportSummary } from '../../types/workflow'

export const buildAnalysisTargetContract = (
  target: AnalysisReportSummary | null | undefined,
): Record<string, string> | null => {
  if (!target) return null
  const reportId = String(target.report_id || '').trim()
  const targetId = String(target.target_id || reportId).trim()
  if (!targetId) return null
  const domain = String(target.domain || target.analysis_type || '').trim()
  const targetType = String(target.target_type || '').trim() || 'report'
  const strategyId = String(target.strategy_id || '').trim()
  const analysisTarget: Record<string, string> = {
    target_type: targetType,
    target_id: targetId,
  }
  if (domain) analysisTarget.source_domain = domain
  if (targetType === 'report' && reportId) analysisTarget.report_id = reportId
  if (strategyId) analysisTarget.strategy_id = strategyId
  return analysisTarget
}

export const buildAnalysisTargetContextMessage = (target: AnalysisReportSummary | null | undefined): string => {
  if (!target) return ''
  const reportId = String(target.report_id || '').trim()
  const targetId = String(target.target_id || reportId).trim()
  if (!targetId) return ''
  const domain = String(target.domain || target.analysis_type || '').trim()
  const targetType = String(target.target_type || '').trim()
  const strategyId = String(target.strategy_id || '').trim()
  const parts = ['[analysis_target]']
  if (domain) parts.push(`domain=${domain}`)
  if (targetType) parts.push(`target_type=${targetType}`)
  parts.push(`target_id=${targetId}`)
  if (reportId) parts.push(`report_id=${reportId}`)
  if (strategyId) parts.push(`strategy_id=${strategyId}`)
  return parts.join(' ')
}

export const appendExecutionTimelineEntry = (
  setExecutionTimeline: React.Dispatch<React.SetStateAction<ExecutionTimelineEntry[]>>,
  entry: ExecutionTimelineEntry | null,
) => {
  if (!entry) return
  setExecutionTimeline((prev) => [...prev, entry].slice(-12))
}

export const buildExecutionTimelineEntry = (
  eventType: string,
  payload: Record<string, unknown>,
  skillList: Skill[],
): ExecutionTimelineEntry | null => {
  if (eventType === 'assistant.delta') return null
  if (eventType === 'job.queued') {
    const lanePos = Number(payload.lane_queue_position || 0)
    return {
      type: eventType,
      summary: lanePos > 0 ? `排队中（前方 ${lanePos}）` : '排队中',
      meta: payload,
    }
  }
  if (eventType === 'job.processing') return { type: eventType, summary: '处理中', meta: payload }
  if (eventType === 'workflow.resolved') {
    const skillId = String(
      payload.requested_skill_id || payload.skill_id_requested || payload.effective_skill_id || payload.skill_id_effective || '',
    ).trim()
    const effective = String(payload.effective_skill_id || payload.skill_id_effective || '').trim()
    const title = skillList.find((item) => item.id === effective)?.title || effective || skillId || 'workflow'
    return { type: eventType, summary: `工作流已解析：${title}`, meta: payload }
  }
  if (eventType === 'tool.start') {
    const toolName = String(payload.tool_name || '').trim() || 'tool'
    return { type: eventType, summary: `调用工具：${toolName}`, meta: payload }
  }
  if (eventType === 'tool.finish') {
    const toolName = String(payload.tool_name || '').trim() || 'tool'
    const ok = Boolean(payload.ok)
    return { type: eventType, summary: ok ? `工具完成：${toolName}` : `工具失败：${toolName}`, meta: payload }
  }
  if (eventType === 'assistant.done') return { type: eventType, summary: '已生成回复', meta: payload }
  if (eventType === 'job.done') return { type: eventType, summary: '任务完成', meta: payload }
  if (eventType === 'job.failed') return { type: eventType, summary: '任务失败', meta: payload }
  if (eventType === 'job.cancelled') return { type: eventType, summary: '任务已取消', meta: payload }
  return null
}

export const resolveWorkflowHint = (
  payload: {
    requested_skill_id?: string
    effective_skill_id?: string
    reason?: string
    skill_id_requested?: string
    skill_id_effective?: string
    skill_reason?: string
    confidence?: number
    skill_confidence?: number
  },
  skillList: Skill[],
): string => {
  const reason = String(payload.reason || payload.skill_reason || '').trim()
  const requested = String(payload.requested_skill_id || payload.skill_id_requested || '').trim()
  const effective = String(payload.effective_skill_id || payload.skill_id_effective || '').trim()
  const confidenceRaw = Number(payload.confidence ?? payload.skill_confidence ?? Number.NaN)
  const confidence = Number.isFinite(confidenceRaw) ? confidenceRaw : undefined
  if (!effective || reason === 'explicit') return ''
  const title = skillList.find((item) => item.id === effective)?.title || effective
  if (requested && requested === effective) return ''
  if (reason.includes('default')) return `当前未明确指定，先按「${title}」工作流继续。`
  if (confidence !== undefined && confidence < 0.56) return `已优先按「${title}」工作流处理；如需切换，可显式选择能力。`
  return `已按「${title}」工作流处理。`
}
