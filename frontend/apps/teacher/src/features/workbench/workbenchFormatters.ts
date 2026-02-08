import type {
  AssignmentProgress,
  ExamUploadDraft,
  ExamUploadJobStatus,
  UploadDraft,
  UploadJobStatus,
} from '../../appTypes'
import { formatMissingRequirements } from './workbenchUtils'

export const formatUploadJobStatus = (job: UploadJobStatus) => {
  const lines: string[] = []
  const statusMap: Record<string, string> = {
    queued: '排队中',
    processing: '解析中',
    done: '解析完成（待确认）',
    failed: '解析失败',
    confirmed: '已创建作业',
    created: '已创建作业',
    confirming: '确认中',
    cancelled: '已取消',
  }
  lines.push(`解析状态：${statusMap[job.status] || job.status}`)
  if (job.progress !== undefined) lines.push(`进度：${job.progress}%`)
  if (job.assignment_id) lines.push(`作业编号：${job.assignment_id}`)
  if (job.question_count !== undefined) lines.push(`题目数量：${job.question_count}`)
  if (job.delivery_mode) lines.push(`交付方式：${job.delivery_mode === 'pdf' ? '文档' : '图片'}`)
  if (job.error) lines.push(`错误：${job.error}`)

  // Backend may include extra fields for better UX.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const extra = job as any
  if (extra.error_detail) lines.push(`详情：${extra.error_detail}`)
  if (Array.isArray(extra.hints) && extra.hints.length) lines.push(`建议：${extra.hints.join('；')}`)
  if (job.warnings && job.warnings.length) lines.push(`解析提示：${job.warnings.join('；')}`)
  if (job.requirements_missing && job.requirements_missing.length) {
    const missingLabelMap: Record<string, string> = {
      // 8-point requirements
      subject: '学科',
      topic: '主题',
      grade_level: '年级',
      class_level: '班级水平',
      core_concepts: '核心概念',
      typical_problem: '典型题型/例题',
      misconceptions: '易错点/易混点',
      duration_minutes: '作业时间',
      preferences: '作业偏好',
      extra_constraints: '额外限制',
      // per-question fields
      stem: '题干',
      answer: '答案',
      kp: '知识点',
      difficulty: '难度',
      score: '分值',
      tags: '标签',
      type: '题型',
    }
    const missingCn = job.requirements_missing.map((key) => missingLabelMap[key] || key)
    lines.push(`作业要求缺失项：${missingCn.join('、')}`)
  }
  if (job.questions_preview && job.questions_preview.length) {
    const previews = job.questions_preview.map((q) => `Q${q.id}：${q.stem}`).join('\n')
    lines.push(`题目预览：\n${previews}`)
  }
  return lines.join('\n')
}

export const formatExamJobStatus = (job: ExamUploadJobStatus) => {
  const lines: string[] = []
  const statusMap: Record<string, string> = {
    queued: '排队中',
    processing: '解析中',
    done: '解析完成（待确认）',
    failed: '解析失败',
    confirmed: '已创建考试',
    confirming: '确认中',
    cancelled: '已取消',
  }
  lines.push(`解析状态：${statusMap[job.status] || job.status}`)
  if (job.progress !== undefined) lines.push(`进度：${job.progress}%`)
  if (job.exam_id) lines.push(`考试编号：${job.exam_id}`)
  if (job.counts?.students !== undefined) lines.push(`学生数：${job.counts.students}`)
  if (job.counts?.questions !== undefined) lines.push(`题目数：${job.counts.questions}`)
  if (job.scoring?.status) {
    const scoreMap: Record<string, string> = { scored: '已评分', partial: '部分已评分', unscored: '未评分' }
    const label = scoreMap[job.scoring.status] || job.scoring.status
    const sTotal = job.scoring.students_total ?? job.counts?.students
    const sScored = job.scoring.students_scored ?? job.counts_scored?.students
    if (sTotal !== undefined && sScored !== undefined) lines.push(`评分：${label}（已评分学生 ${sScored}/${sTotal}）`)
    else lines.push(`评分：${label}`)
    const defaults = Array.isArray(job.scoring.default_max_score_qids) ? job.scoring.default_max_score_qids.length : 0
    if (defaults) lines.push(`提示：有 ${defaults} 题缺少满分，系统已默认按 1 分/题 评分（建议在草稿里核对满分）。`)
  }
  if (job.error) lines.push(`错误：${job.error}`)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const extra = job as any
  if (extra.error_detail) lines.push(`详情：${extra.error_detail}`)
  if (Array.isArray(extra.hints) && extra.hints.length) lines.push(`建议：${extra.hints.join('；')}`)
  if (job.warnings && job.warnings.length) lines.push(`解析提示：${job.warnings.join('；')}`)
  return lines.join('\n')
}

export const formatExamJobSummary = (job: ExamUploadJobStatus | null, fallbackExamId?: string) => {
  if (!job) return `未开始解析${fallbackExamId ? ` · 考试编号：${fallbackExamId}` : ''}`
  const statusMap: Record<string, string> = {
    queued: '排队中',
    processing: '解析中',
    done: '解析完成（待确认）',
    failed: '解析失败',
    confirmed: '已创建',
    confirming: '确认中',
    cancelled: '已取消',
  }
  const parts: string[] = []
  parts.push(`状态：${statusMap[job.status] || job.status}`)
  if (job.progress !== undefined) parts.push(`${job.progress}%`)
  parts.push(`考试编号：${job.exam_id || fallbackExamId || job.job_id}`)
  if (job.counts?.students !== undefined) parts.push(`学生：${job.counts.students}`)
  if (job.counts?.questions !== undefined) parts.push(`题目：${job.counts.questions}`)
  if (job.scoring?.status) {
    const scoreMap: Record<string, string> = { scored: '已评分', partial: '部分已评分', unscored: '未评分' }
    parts.push(`评分：${scoreMap[job.scoring.status] || job.scoring.status}`)
  }
  if (job.status === 'failed' && job.error) parts.push(`错误：${job.error}`)
  return parts.join(' · ')
}

export const formatExamDraftSummary = (draft: ExamUploadDraft | null, jobInfo: ExamUploadJobStatus | null) => {
  if (!draft) return ''
  const parts: string[] = []
  parts.push(`考试编号：${draft.exam_id}`)
  if (draft.meta?.date) parts.push(String(draft.meta.date))
  if (draft.meta?.class_name) parts.push(String(draft.meta.class_name))
  if (draft.counts?.students !== undefined) parts.push(`学生：${draft.counts.students}`)
  if (draft.counts?.questions !== undefined) parts.push(`题目：${draft.counts.questions}`)
  if (jobInfo?.status === 'confirmed') parts.push('已创建')
  else if (jobInfo?.status === 'done') parts.push('待创建')
  return parts.join(' · ')
}

export const formatUploadJobSummary = (job: UploadJobStatus | null, fallbackAssignmentId?: string) => {
  if (!job) return `未开始解析${fallbackAssignmentId ? ` · 作业编号：${fallbackAssignmentId}` : ''}`
  const statusMap: Record<string, string> = {
    queued: '排队中',
    processing: '解析中',
    done: '解析完成（待确认）',
    failed: '解析失败',
    confirmed: '已创建',
    created: '已创建',
    confirming: '确认中',
    cancelled: '已取消',
  }
  const parts: string[] = []
  parts.push(`状态：${statusMap[job.status] || job.status}`)
  if (job.progress !== undefined) parts.push(`${job.progress}%`)
  parts.push(`作业编号：${job.assignment_id || fallbackAssignmentId || job.job_id}`)
  if (job.question_count !== undefined) parts.push(`题目：${job.question_count}`)
  if (job.requirements_missing && job.requirements_missing.length) parts.push(`缺失：${job.requirements_missing.length}项`)
  if (job.status === 'failed' && job.error) parts.push(`错误：${job.error}`)
  return parts.join(' · ')
}

export const formatDraftSummary = (draft: UploadDraft | null, jobInfo: UploadJobStatus | null) => {
  if (!draft) return ''
  const scopeLabel = draft.scope === 'public' ? '公共作业' : draft.scope === 'class' ? '班级作业' : '私人作业'
  const parts: string[] = []
  parts.push(`作业编号：${draft.assignment_id}`)
  if (draft.date) parts.push(draft.date)
  parts.push(scopeLabel)
  parts.push(`题目：${draft.questions?.length || 0}`)
  if (draft.requirements_missing && draft.requirements_missing.length) parts.push(`缺失：${draft.requirements_missing.length}项`)
  else parts.push('要求已补全')
  if (jobInfo?.status === 'confirmed' || jobInfo?.status === 'created') parts.push('已创建')
  else if (jobInfo?.status === 'done') parts.push('待创建')
  return parts.join(' · ')
}

export const formatProgressSummary = (p: AssignmentProgress | null, fallbackAssignmentId?: string) => {
  const aid = (p?.assignment_id || fallbackAssignmentId || '').trim()
  if (!aid) return '未加载作业完成情况'
  const expected = p?.counts?.expected ?? p?.expected_count ?? 0
  const completed = p?.counts?.completed ?? 0
  const overdue = p?.counts?.overdue ?? 0
  const parts: string[] = []
  parts.push(`作业编号：${aid}`)
  if (p?.date) parts.push(String(p.date))
  parts.push(`完成：${completed}/${expected}`)
  if (overdue) parts.push(`逾期：${overdue}`)
  return parts.join(' · ')
}

export const describeConfirmMissing = (missing: unknown) => {
  if (!Array.isArray(missing)) return ''
  const keys = missing.filter((item) => typeof item === 'string') as string[]
  if (!keys.length) return ''
  return formatMissingRequirements(keys)
}

