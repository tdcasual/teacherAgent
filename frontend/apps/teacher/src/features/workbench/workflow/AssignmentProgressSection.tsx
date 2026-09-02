import type { Dispatch, FormEvent, SetStateAction } from 'react'
import type { AssignmentProgress, AssignmentProgressStudent } from '../../../appTypes'
import type { FormatProgressSummary } from '../../../types/workflow'
import LabeledField from './LabeledField'

export type TeacherGradePayload = {
  override_score?: number | null
  comment?: string
  adopted_coach_excerpts?: Array<{ text: string }>
}

type AssignmentProgressSectionProps = {
  progressPanelCollapsed: boolean
  setProgressPanelCollapsed: Dispatch<SetStateAction<boolean>>
  formatProgressSummary: FormatProgressSummary
  progressData: AssignmentProgress | null
  progressAssignmentId: string
  setProgressAssignmentId: (value: string) => void
  progressOnlyIncomplete: boolean
  setProgressOnlyIncomplete: (value: boolean) => void
  progressLoading: boolean
  fetchAssignmentProgress: (assignmentId?: string) => Promise<void>
  progressError: string
  archiveAssignment?: (assignmentId?: string) => Promise<void>
  unarchiveAssignment?: (assignmentId?: string) => Promise<void>
  saveStudentGrade?: (studentId: string, payload: TeacherGradePayload) => Promise<void>
}

const extractBestScore = (value: unknown): number | null => {
  if (!value || typeof value !== 'object') return null
  const candidate = value as { score_earned?: unknown }
  const score = Number(candidate.score_earned)
  return Number.isFinite(score) ? score : null
}

const processStatusLabel = (status?: string) => {
  if (status === 'pending') return '生成中'
  if (status === 'frozen') return '已冻结'
  if (status === 'partial') return '部分'
  return '无'
}

const officialScoreOf = (student: AssignmentProgressStudent): number | null => {
  if (typeof student.result?.official_score === 'number') return student.result.official_score
  if (typeof student.official_score === 'number') return student.official_score
  return extractBestScore(student.submission?.best)
}

const parseAdoptedExcerpts = (raw: string): Array<{ text: string }> => {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((text) => ({ text }))
}

const submitStudentGrade = (
  event: FormEvent<HTMLFormElement>,
  studentId: string,
  saveStudentGrade?: (studentId: string, payload: TeacherGradePayload) => Promise<void>,
) => {
  event.preventDefault()
  if (!saveStudentGrade) return
  const form = new FormData(event.currentTarget)
  const scoreRaw = String(form.get('override_score') || '').trim()
  const comment = String(form.get('comment') || '')
  const excerptsRaw = String(form.get('adopted_coach_excerpts') || '')
  const payload: TeacherGradePayload = {
    comment,
    adopted_coach_excerpts: parseAdoptedExcerpts(excerptsRaw),
  }
  if (scoreRaw) {
    const score = Number(scoreRaw)
    if (Number.isFinite(score)) payload.override_score = score
  }
  void saveStudentGrade(studentId, payload)
}

export default function AssignmentProgressSection(props: AssignmentProgressSectionProps) {
  const {
    progressPanelCollapsed, setProgressPanelCollapsed, formatProgressSummary,
    progressData, progressAssignmentId, setProgressAssignmentId,
    progressOnlyIncomplete, setProgressOnlyIncomplete,
    progressLoading, fetchAssignmentProgress, progressError,
    archiveAssignment, unarchiveAssignment, saveStudentGrade,
  } = props
  const visibilityStatus = String(progressData?.visibility_status || '').trim()

  return (
    	            <section id="workflow-progress-section" className={`mt-3 bg-surface border border-border rounded-[14px] shadow-sm ${progressPanelCollapsed ? 'py-[10px] px-3' : 'p-[10px]'}`}>
    	              <div className={`flex items-start gap-2 flex-wrap ${progressPanelCollapsed ? 'mb-0' : 'mb-2'}`}>
    	                <h3 className="m-0 whitespace-nowrap shrink-0">作业完成情况</h3>
    	                {progressPanelCollapsed ? (
    	                  <div
    	                    className="flex-1 min-w-0 text-muted text-[12px] whitespace-nowrap overflow-hidden text-ellipsis"
    	                    title={formatProgressSummary(progressData, progressAssignmentId)}
    	                  >
    	                    {formatProgressSummary(progressData, progressAssignmentId)}
    	                  </div>
    	                ) : null}
	    	                <button type="button" className="ghost" onClick={() => setProgressPanelCollapsed((v: boolean) => !v)}>
    	                  {progressPanelCollapsed ? '展开' : '收起'}
    	                </button>
    	              </div>
    	              {progressPanelCollapsed ? null : (
    	                <>
    	                  <div className="flex items-end justify-between gap-3 flex-wrap mb-[10px]">
    	                    <LabeledField label="作业编号" className="grid gap-1.5 min-w-[240px]">
    	                      <input
    	                        value={progressAssignmentId}
    	                        onChange={(e) => setProgressAssignmentId(e.target.value)}
    	                        placeholder="例如：A2403_2026-02-04"
    	                      />
    	                    </LabeledField>
    	                    <div className="flex items-center gap-3 flex-wrap">
    	                      <label className="toggle">
    	                        <input
    	                          type="checkbox"
    	                          checked={progressOnlyIncomplete}
    	                          onChange={(e) => setProgressOnlyIncomplete(e.target.checked)}
    	                        />
    	                        只看未完成
    	                      </label>
    	                      <button
    	                        type="button"
    	                        className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
    	                        disabled={progressLoading}
    	                        onClick={() => void fetchAssignmentProgress()}
    	                      >
    	                        {progressLoading ? '加载中…' : '刷新'}
    	                      </button>
                          {visibilityStatus === 'archived' ? (
                            <button
                              type="button"
                              className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                              disabled={progressLoading || !unarchiveAssignment}
                              onClick={() => void unarchiveAssignment?.()}
                            >
                              取消归档
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="border border-border rounded-xl py-[10px] px-[14px] bg-white text-ink cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                              disabled={progressLoading || !archiveAssignment}
                              onClick={() => void archiveAssignment?.()}
                            >
                              归档
                            </button>
                          )}
    	                    </div>
    	                  </div>

    	                  {progressError && <div className="mt-[10px] p-[10px_12px] rounded-xl text-[12px] whitespace-pre-wrap overflow-x-auto bg-danger-soft text-danger">{progressError}</div>}
    	                  {progressData && (
    	                    <div className="text-[13px] text-muted grid gap-1">
    	                      <div>作业编号：{progressData.assignment_id}</div>
    	                      <div>日期：{String(progressData.date || '') || '（未设置）'}</div>
    	                      <div>
    	                        应交：{progressData.counts?.expected ?? progressData.expected_count ?? 0} · 已提交：
    	                        {progressData.counts?.submitted ?? 0} · 完成：
    	                        {progressData.counts?.completed ?? 0}
    	                        {progressData.counts?.overdue ? ` · 逾期：${progressData.counts.overdue}` : ''}
    	                      </div>
    	                      <div>截止：{progressData.due_at ? progressData.due_at : '永不截止'}</div>
                            <div className="flex gap-6">
                              <span>结果</span>
                              <span>过程</span>
                            </div>
    	                    </div>
    	                  )}

    	                  {progressData?.students && progressData.students.length > 0 && (
    	                    <div className="mt-3 grid gap-2">
                          {(progressOnlyIncomplete
                            ? progressData.students.filter((s: AssignmentProgressStudent) => !s.complete)
                            : progressData.students
                          ).map((s: AssignmentProgressStudent) => {
    	                        const attempts = s.result?.attempts ?? s.submission?.attempts ?? 0
    	                        const official = officialScoreOf(s)
    	                        const overdue = Boolean(s.result?.overdue ?? s.overdue)
                            const processStatus = s.process?.status || 'none'
                            const liveStuck = String(s.process?.stuck_points?.[0]?.summary || '').trim()
                            const archiveStuck = (s.process_archive?.stuck_points || [])
                              .map((item) => String(item?.summary || '').trim())
                              .filter(Boolean)
                              .slice(0, 2)
                              .join('；')
                            const stuckNote = liveStuck || archiveStuck
                            const processNote = stuckNote ? ` · ${stuckNote}` : ''
    	                        const name = [s.class_name, s.student_name].filter(Boolean).join(' ')
    	                        const archiveStatus = String(s.process_archive_status || s.process_archive?.status || 'none')
    	                        const processLabel = archiveStatus === 'none' || !archiveStatus ? '无' : archiveStatus
    	                        const memory = s.has_memory_proposal ? ' · 有记忆提案' : ''
    	                        return (
    	                          <div
                                key={s.student_id}
                                data-testid={`progress-row-${s.student_id}`}
                                className={`progress-row border rounded-[14px] py-[10px] px-3 flex justify-between gap-3 items-start ${s.complete ? 'border-[color:var(--color-success)] bg-[color:var(--color-success-soft)]' : 'border-[color:var(--color-danger)] bg-[color:var(--color-danger-soft)]'}`}
                              >
    	                            <div className="text-[13px] min-w-0 flex-1">
    	                              <strong>{s.student_id}</strong>
    	                              {name ? <span className="text-muted text-[12px]"> {name}</span> : null}
                                  <div className="grid grid-cols-2 gap-2 mt-1 text-[12px] text-muted">
                                    <div>提交{attempts}次 · {official != null ? `官方分${official}` : '无官方分'}{overdue ? ' · 逾期' : ''}</div>
                                    <div>过程：{processStatusLabel(processStatus) || processLabel}{processNote}{memory}</div>
                                  </div>
                                  {saveStudentGrade ? (
                                    <form
                                      className="mt-2 grid gap-1.5"
                                      onSubmit={(event) => submitStudentGrade(event, s.student_id, saveStudentGrade)}
                                    >
                                      <LabeledField label="覆盖分数">
                                        <input
                                          name="override_score"
                                          type="number"
                                          step="any"
                                          defaultValue={s.teacher_grade?.override_score_earned ?? ''}
                                        />
                                      </LabeledField>
                                      <LabeledField label="评语">
                                        <textarea name="comment" defaultValue={s.teacher_grade?.comment || ''} rows={2} />
                                      </LabeledField>
                                      <LabeledField label="采纳陪练摘录">
                                        <textarea
                                          name="adopted_coach_excerpts"
                                          placeholder="每行一条；未采纳的陪练评语不会记入成绩"
                                          defaultValue={(s.teacher_grade?.adopted_coach_excerpts || [])
                                            .map((item) => item.text || '')
                                            .filter(Boolean)
                                            .join('\n')}
                                          rows={2}
                                        />
                                      </LabeledField>
                                      <div className="flex flex-wrap gap-2">
                                        <button
                                          type="submit"
                                          className="border border-border rounded-xl py-[8px] px-[12px] bg-white text-ink cursor-pointer disabled:opacity-60"
                                          disabled={progressLoading}
                                        >
                                          保存成绩
                                        </button>
                                        <button
                                          type="button"
                                          className="border border-border rounded-xl py-[8px] px-[12px] bg-white text-ink cursor-pointer disabled:opacity-60"
                                          disabled={progressLoading}
                                          onClick={() => void saveStudentGrade(s.student_id, { override_score: null })}
                                        >
                                          恢复自动分
                                        </button>
                                      </div>
                                    </form>
                                  ) : null}
    	                            </div>
    	                          </div>
    	                        )
    	                      })}
    	                    </div>
    	                  )}
    	                </>
    	              )}
    	            </section>
  )
}
