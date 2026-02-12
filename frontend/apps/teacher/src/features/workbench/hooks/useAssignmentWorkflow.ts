import { useCallback, useEffect, useMemo, useRef, type FormEvent } from 'react'
import { buildAssignmentWorkflowIndicator } from '../workflowIndicators'
import { formatMissingRequirements, parseLineList } from '../workbenchUtils'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../../utils/storage'
import type {
  AssignmentProgress,
  UploadDraft,
  UploadJobStatus,
  WorkflowIndicator,
  WorkflowStepState,
} from '../../../appTypes'

type UnknownRecord = Record<string, unknown>

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  if (error instanceof Error) {
    const message = error.message.trim()
    if (message) return message
  }
  const raw = String(error || '').trim()
  return raw || fallback
}

// ---------------------------------------------------------------------------
// Params type – the state / setters the hook needs from the parent component
// ---------------------------------------------------------------------------

export interface UseAssignmentWorkflowParams {
  apiBase: string

  // Upload card state
  uploadMode: string
  uploadAssignmentId: string
  uploadDate: string
  uploadScope: string
  uploadClassName: string
  uploadStudentIds: string
  uploadFiles: File[]
  uploadAnswerFiles: File[]
  uploading: boolean
  uploadStatus: string
  uploadError: string
  uploadCardCollapsed: boolean
  uploadJobId: string
  uploadJobInfo: UploadJobStatus | null
  uploadConfirming: boolean
  uploadStatusPollNonce: number
  uploadDraft: UploadDraft | null
  draftPanelCollapsed: boolean
  draftLoading: boolean
  draftError: string
  questionShowCount: number
  draftSaving: boolean
  draftActionStatus: string
  draftActionError: string
  misconceptionsText: string
  misconceptionsDirty: boolean

  // Progress state
  progressPanelCollapsed: boolean
  progressAssignmentId: string
  progressLoading: boolean
  progressError: string
  progressData: AssignmentProgress | null
  progressOnlyIncomplete: boolean

  // Exam poll nonce (needed by refreshWorkflowWorkbench)
  examStatusPollNonce: number

  // Setters
  setUploadError: (value: string) => void
  setUploadStatus: (value: string | ((prev: string) => string)) => void
  setUploadJobId: (value: string) => void
  setUploadJobInfo: (value: UploadJobStatus | null | ((prev: UploadJobStatus | null) => UploadJobStatus | null)) => void
  setUploadDraft: (value: UploadDraft | null | ((prev: UploadDraft | null) => UploadDraft | null)) => void
  setUploadFiles: (value: File[]) => void
  setUploadAnswerFiles: (value: File[]) => void
  setUploading: (value: boolean) => void
  setUploadCardCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void
  setUploadConfirming: (value: boolean) => void
  setUploadStatusPollNonce: (value: number | ((prev: number) => number)) => void
  setDraftPanelCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void
  setDraftLoading: (value: boolean) => void
  setDraftError: (value: string) => void
  setQuestionShowCount: (value: number | ((prev: number) => number)) => void
  setDraftSaving: (value: boolean) => void
  setDraftActionStatus: (value: string) => void
  setDraftActionError: (value: string) => void
  setMisconceptionsText: (value: string) => void
  setMisconceptionsDirty: (value: boolean) => void
  setProgressPanelCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void
  setProgressAssignmentId: (value: string) => void
  setProgressLoading: (value: boolean) => void
  setProgressError: (value: string) => void
  setProgressData: (value: AssignmentProgress | null) => void
  setExamStatusPollNonce: (value: number | ((prev: number) => number)) => void
}

// ---------------------------------------------------------------------------
// Return type
// ---------------------------------------------------------------------------

export interface UseAssignmentWorkflowReturn {
  handleUploadAssignment: (event: FormEvent) => Promise<void>
  saveDraft: (draft: UploadDraft) => Promise<void>
  handleConfirmUpload: () => Promise<void>
  fetchAssignmentProgress: (assignmentId?: string) => Promise<void>
  refreshWorkflowWorkbench: () => void
  scrollToWorkflowSection: (sectionId: string) => void
  assignmentWorkflowIndicator: WorkflowIndicator
  assignmentWorkflowAutoState: string
  computeLocalRequirementsMissing: (req: UnknownRecord) => string[]
  updateDraftRequirement: (key: string, value: unknown) => void
  updateDraftQuestion: (index: number, patch: UnknownRecord) => void
}

// ---------------------------------------------------------------------------
// Hook implementation
// ---------------------------------------------------------------------------

export function useAssignmentWorkflow(params: UseAssignmentWorkflowParams): UseAssignmentWorkflowReturn {
  const {
    apiBase,
    uploadMode,
    uploadAssignmentId,
    uploadDate,
    uploadScope,
    uploadClassName,
    uploadStudentIds,
    uploadFiles,
    uploadAnswerFiles,
    uploading,
    uploadError,
    uploadCardCollapsed,
    uploadJobId,
    uploadJobInfo,
    uploadConfirming,
    uploadDraft,
    draftPanelCollapsed,
    draftError,
    draftActionError,
    misconceptionsText,
    misconceptionsDirty,
    progressAssignmentId,
    setUploadError,
    setUploadStatus,
    setUploadJobId,
    setUploadJobInfo,
    setUploadDraft,
    setUploadFiles,
    setUploadAnswerFiles,
    setUploading,
    setUploadCardCollapsed,
    setUploadConfirming,
    setUploadStatusPollNonce,
    setDraftPanelCollapsed,
    setDraftLoading,
    setDraftError,
    setQuestionShowCount,
    setDraftSaving,
    setDraftActionStatus,
    setDraftActionError,
    setMisconceptionsText,
    setMisconceptionsDirty,
    setProgressPanelCollapsed,
    setProgressAssignmentId,
    setProgressLoading,
    setProgressError,
    setProgressData,
    setExamStatusPollNonce,
  } = params

  // ---- Workflow indicator (memoised) ----

  const assignmentWorkflowIndicator = useMemo<WorkflowIndicator>(() => {
    return buildAssignmentWorkflowIndicator({
      uploadJobId,
      uploadJobInfoStatus: uploadJobInfo?.status,
      uploading,
      uploadConfirming,
      uploadDraft,
      uploadError,
      draftError,
      draftActionError,
    })
  }, [draftActionError, draftError, uploadConfirming, uploadDraft, uploadError, uploadJobId, uploadJobInfo?.status, uploading])

  // ---- Workflow step reader ----

  const readWorkflowStepState = useCallback((indicator: WorkflowIndicator, stepKey: string): WorkflowStepState => {
    return indicator.steps.find((step) => step.key === stepKey)?.state || 'todo'
  }, [])

  // ---- Auto-state derived from indicator ----

  const assignmentWorkflowAutoState = useMemo(() => {
    const uploadStep = readWorkflowStepState(assignmentWorkflowIndicator, 'upload')
    const parseStep = readWorkflowStepState(assignmentWorkflowIndicator, 'parse')
    const reviewStep = readWorkflowStepState(assignmentWorkflowIndicator, 'review')
    const confirmStep = readWorkflowStepState(assignmentWorkflowIndicator, 'confirm')
    if (parseStep === 'error') return 'parse-error'
    if (reviewStep === 'error') return 'review-error'
    if (confirmStep === 'error') return 'confirm-error'
    if (confirmStep === 'done') return 'confirmed'
    if (confirmStep === 'active') return 'confirming'
    if (reviewStep === 'active') return 'review'
    if (parseStep === 'active') return 'parsing'
    if (uploadStep === 'active') return 'uploading'
    return 'idle'
  }, [assignmentWorkflowIndicator, readWorkflowStepState])

  // ---- Auto-collapse effect driven by workflow state ----

  const assignmentAutoStateRef = useRef('')

  useEffect(() => {
    if (uploadMode !== 'assignment') return
    if (assignmentAutoStateRef.current === assignmentWorkflowAutoState) return
    assignmentAutoStateRef.current = assignmentWorkflowAutoState
    switch (assignmentWorkflowAutoState) {
      case 'uploading':
      case 'parsing':
      case 'parse-error':
        setUploadCardCollapsed(false)
        break
      case 'review':
      case 'confirming':
        setUploadCardCollapsed(true)
        setDraftPanelCollapsed(false)
        break
      case 'review-error':
      case 'confirm-error':
        setDraftPanelCollapsed(false)
        break
      case 'confirmed':
        setUploadCardCollapsed(true)
        setDraftPanelCollapsed(true)
        if ((progressAssignmentId || uploadAssignmentId || uploadDraft?.assignment_id || '').trim()) {
          setProgressPanelCollapsed(false)
        }
        break
      default:
        break
    }
  }, [
    assignmentWorkflowAutoState,
    progressAssignmentId,
    setDraftPanelCollapsed,
    setProgressPanelCollapsed,
    setUploadCardCollapsed,
    uploadAssignmentId,
    uploadDraft?.assignment_id,
    uploadMode,
  ])

  // ---- Auto-expand upload card on error ----

  useEffect(() => {
    if (uploadError && uploadCardCollapsed) setUploadCardCollapsed(false)
  }, [setUploadCardCollapsed, uploadError, uploadCardCollapsed])

  // ---- Auto-expand draft panel on error ----

  useEffect(() => {
    if ((draftError || draftActionError) && draftPanelCollapsed) setDraftPanelCollapsed(false)
  }, [draftActionError, draftError, draftPanelCollapsed, setDraftPanelCollapsed])

  // ---- Load draft when job finishes parsing ----

  useEffect(() => {
    const uploadJobStatus = uploadJobInfo?.status
    if (!uploadJobId) return
    if (uploadJobStatus !== 'done' && uploadJobStatus !== 'confirmed') return
    let active = true
    const loadDraft = async () => {
      setDraftError('')
      setDraftLoading(true)
      try {
        const res = await fetch(`${apiBase}/assignment/upload/draft?job_id=${encodeURIComponent(uploadJobId)}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = await res.json()
        if (!active) return
        const draft = data?.draft as UploadDraft
        if (!draft || !draft.questions) throw new Error('draft 数据缺失')
        setUploadDraft(draft)
        setDraftPanelCollapsed(false)
        setQuestionShowCount(20)
      } catch (err: unknown) {
        if (!active) return
        setDraftError(toErrorMessage(err))
      } finally {
        if (!active) return
        setDraftLoading(false)
      }
    }
    loadDraft()
    return () => {
      active = false
    }
  }, [
    apiBase,
    setDraftError,
    setDraftLoading,
    setDraftPanelCollapsed,
    setQuestionShowCount,
    setUploadDraft,
    uploadJobId,
    uploadJobInfo?.status,
  ])

  // ---- Sync misconceptions text from draft ----

  useEffect(() => {
    if (!uploadDraft) return
    if (misconceptionsDirty) return
    const list = Array.isArray(uploadDraft.requirements?.misconceptions) ? uploadDraft.requirements.misconceptions : []
    setMisconceptionsText(list.join('\n'))
  }, [misconceptionsDirty, setMisconceptionsText, uploadDraft, uploadDraft?.draft_version, uploadDraft?.job_id])

  // ---- computeLocalRequirementsMissing ----

  const computeLocalRequirementsMissing = useCallback((req: UnknownRecord) => {
    const missing: string[] = []
    const subject = String(req?.subject || '').trim()
    const topic = String(req?.topic || '').trim()
    const grade = String(req?.grade_level || '').trim()
    const classLevel = String(req?.class_level || '').trim()
    const core = Array.isArray(req?.core_concepts) ? req.core_concepts : []
    const typical = String(req?.typical_problem || '').trim()
    const misconceptions = Array.isArray(req?.misconceptions) ? req.misconceptions : []
    const duration = Number(req?.duration_minutes || 0)
    const prefs = Array.isArray(req?.preferences) ? req.preferences : []

    if (!subject) missing.push('subject')
    if (!topic) missing.push('topic')
    if (!grade) missing.push('grade_level')
    if (!['偏弱', '中等', '较强', '混合'].includes(classLevel)) missing.push('class_level')
    if (core.filter(Boolean).length < 3) missing.push('core_concepts')
    if (!typical) missing.push('typical_problem')
    if (misconceptions.filter(Boolean).length < 4) missing.push('misconceptions')
    if (![20, 40, 60].includes(duration)) missing.push('duration_minutes')
    if (prefs.filter(Boolean).length < 1) missing.push('preferences')

    return missing
  }, [])

  // ---- updateDraftRequirement ----

  const updateDraftRequirement = useCallback(
    (key: string, value: unknown) => {
      setUploadDraft((prev) => {
        if (!prev) return prev
        const nextRequirements = {
          ...(prev.requirements || {}),
          [key]: value,
        }
        const nextMissing = computeLocalRequirementsMissing(nextRequirements)
        return {
          ...prev,
          requirements: nextRequirements,
          requirements_missing: nextMissing,
        }
      })
    },
    [computeLocalRequirementsMissing, setUploadDraft],
  )

  // ---- updateDraftQuestion ----

  const updateDraftQuestion = useCallback(
    (index: number, patch: UnknownRecord) => {
      setUploadDraft((prev) => {
        if (!prev) return prev
        const next = [...(prev.questions || [])]
        const cur = next[index] || {}
        next[index] = { ...cur, ...patch }
        return { ...prev, questions: next }
      })
    },
    [setUploadDraft],
  )

  // ---- fetchAssignmentProgress ----

  const fetchAssignmentProgress = useCallback(
    async (assignmentId?: string) => {
      const aid = (assignmentId || progressAssignmentId || '').trim()
      if (!aid) {
        setProgressError('请先填写作业编号')
        return
      }
      setProgressLoading(true)
      setProgressError('')
      try {
        const res = await fetch(
          `${apiBase}/teacher/assignment/progress?assignment_id=${encodeURIComponent(aid)}&include_students=true`,
        )
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as AssignmentProgress
        if (!data?.ok) {
          throw new Error('获取作业完成情况失败')
        }
        setProgressData(data)
        setProgressAssignmentId(data.assignment_id || aid)
      } catch (err: unknown) {
        setProgressError(toErrorMessage(err))
      } finally {
        setProgressLoading(false)
      }
    },
    [
      apiBase,
      progressAssignmentId,
      setProgressAssignmentId,
      setProgressData,
      setProgressError,
      setProgressLoading,
    ],
  )

  // ---- refreshWorkflowWorkbench ----

  const refreshWorkflowWorkbench = useCallback(() => {
    setUploadStatusPollNonce((n) => n + 1)
    setExamStatusPollNonce((n) => n + 1)
    const assignmentId = (progressAssignmentId || uploadAssignmentId || uploadDraft?.assignment_id || '').trim()
    if (assignmentId) {
      void fetchAssignmentProgress(assignmentId)
    }
  }, [
    fetchAssignmentProgress,
    progressAssignmentId,
    setExamStatusPollNonce,
    setUploadStatusPollNonce,
    uploadAssignmentId,
    uploadDraft?.assignment_id,
  ])

  // ---- scrollToWorkflowSection ----

  const scrollToWorkflowSection = useCallback((sectionId: string) => {
    if (typeof document === 'undefined') return
    const node = document.getElementById(sectionId)
    if (!node) return
    node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  // ---- saveDraft ----

  const saveDraft = useCallback(
    async (draft: UploadDraft) => {
      setDraftSaving(true)
      setUploadError('')
      setDraftActionError('')
      setDraftActionStatus('正在保存草稿…')
      try {
        const normalizedRequirements = {
          ...(draft.requirements || {}),
          misconceptions: parseLineList(misconceptionsText),
        }
        const res = await fetch(`${apiBase}/assignment/upload/draft/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_id: draft.job_id,
            requirements: normalizedRequirements,
            questions: draft.questions,
          }),
        })
        if (!res.ok) {
          const text = await res.text()
          let message = text || `状态码 ${res.status}`
          try {
            const parsed = JSON.parse(text)
            const detail = parsed?.detail || parsed
            if (typeof detail === 'string') message = detail
            if (detail?.message) message = detail.message
          } catch {
            // ignore
          }
          throw new Error(message)
        }
        const data = await res.json()
        if (data?.requirements_missing) {
          setUploadDraft((prev) =>
            prev
              ? {
                  ...prev,
                  requirements_missing: data.requirements_missing,
                  requirements: normalizedRequirements,
                  draft_saved: true,
                }
              : prev,
          )
        }
        const msg = data?.message || '草稿已保存。'
        setDraftActionStatus(msg)
        setUploadStatus((prev) => `${prev ? prev + '\n\n' : ''}${msg}`)
        setMisconceptionsDirty(false)
      } catch (err: unknown) {
        const message = toErrorMessage(err)
        setDraftActionError(message)
        throw err
      } finally {
        setDraftSaving(false)
      }
    },
    [
      apiBase,
      misconceptionsText,
      setDraftActionError,
      setDraftActionStatus,
      setDraftSaving,
      setMisconceptionsDirty,
      setUploadDraft,
      setUploadError,
      setUploadStatus,
    ],
  )

  // ---- handleUploadAssignment ----

  const handleUploadAssignment = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      setUploadError('')
      setUploadStatus('')
      setUploadJobId('')
      setUploadJobInfo(null)
      setUploadDraft(null)
      setDraftPanelCollapsed(false)
      setDraftError('')
      setDraftActionStatus('')
      setDraftActionError('')
      setUploadCardCollapsed(false)
      if (!uploadAssignmentId.trim()) {
        setUploadError('请填写作业编号')
        return
      }
      if (!uploadFiles.length) {
        setUploadError('请至少上传一份作业文件（文档或图片）')
        return
      }
      if (uploadScope === 'student' && !uploadStudentIds.trim()) {
        setUploadError('私人作业请填写学生编号')
        return
      }
      if (uploadScope === 'class' && !uploadClassName.trim()) {
        setUploadError('班级作业请填写班级')
        return
      }
      setUploading(true)
      try {
        const fd = new FormData()
        fd.append('assignment_id', uploadAssignmentId.trim())
        if (uploadDate.trim()) fd.append('date', uploadDate.trim())
        fd.append('scope', uploadScope)
        if (uploadClassName.trim()) fd.append('class_name', uploadClassName.trim())
        if (uploadStudentIds.trim()) fd.append('student_ids', uploadStudentIds.trim())
        uploadFiles.forEach((file) => fd.append('files', file))
        uploadAnswerFiles.forEach((file) => fd.append('answer_files', file))

        const res = await fetch(`${apiBase}/assignment/upload/start`, { method: 'POST', body: fd })
        if (!res.ok) {
          const text = await res.text()
          let message = text || `状态码 ${res.status}`
          try {
            const parsed = JSON.parse(text)
            const detail = parsed?.detail || parsed
            if (typeof detail === 'string') {
              message = detail
            } else if (detail?.message) {
              const hints = Array.isArray(detail.hints) ? detail.hints.join('；') : ''
              message = `${detail.message}${hints ? `（${hints}）` : ''}`
            }
          } catch (err) {
            // ignore JSON parse errors
          }
          throw new Error(message)
        }
        const data = await res.json()
        if (data && typeof data === 'object') {
          if (data.job_id) {
            const jid = String(data.job_id)
            setUploadJobId(jid)
            try {
              safeLocalStorageSetItem('teacherActiveUpload', JSON.stringify({ type: 'assignment', job_id: jid }))
            } catch {
              // ignore
            }
          }
          const message = data.message || '解析任务已创建，后台处理中。'
          setUploadStatus(message)
        } else {
          setUploadStatus(typeof data === 'string' ? data : JSON.stringify(data, null, 2))
        }
        setUploadFiles([])
        setUploadAnswerFiles([])
      } catch (err: unknown) {
        setUploadError(toErrorMessage(err))
      } finally {
        setUploading(false)
      }
    },
    [
      apiBase,
      setDraftActionError,
      setDraftActionStatus,
      setDraftError,
      setDraftPanelCollapsed,
      setUploadAnswerFiles,
      setUploadCardCollapsed,
      setUploadDraft,
      setUploadError,
      setUploadFiles,
      setUploadJobId,
      setUploadJobInfo,
      setUploadStatus,
      setUploading,
      uploadAnswerFiles,
      uploadAssignmentId,
      uploadClassName,
      uploadDate,
      uploadFiles,
      uploadScope,
      uploadStudentIds,
    ],
  )

  // ---- handleConfirmUpload ----

  const handleConfirmUpload = useCallback(
    async () => {
      const resolvedJobId = (() => {
        const jobId = String(uploadJobId || '').trim()
        if (jobId) return jobId
        try {
          const raw = safeLocalStorageGetItem('teacherActiveUpload')
          if (!raw) return ''
          const active = JSON.parse(raw)
          if (active?.type === 'assignment' && active?.job_id) return String(active.job_id).trim()
        } catch {
          // ignore
        }
        return ''
      })()
      if (!resolvedJobId) return
      if (!uploadJobId) setUploadJobId(resolvedJobId)
      const previousUploadJobInfo = uploadJobInfo ? { ...uploadJobInfo } : null
      setUploadError('')
      setDraftActionError('')
      setDraftActionStatus('正在创建作业…')
      setUploadConfirming(true)
      try {
        // If parsing is still running, don't attempt to confirm.
        if (uploadJobInfo && uploadJobInfo.status !== 'done' && uploadJobInfo.status !== 'confirmed' && uploadJobInfo.status !== 'created') {
          const message = '解析尚未完成，请等待解析完成后再创建作业。'
          setUploadError(message)
          setDraftActionError(message)
          setUploadStatusPollNonce((n) => n + 1)
          return
        }
        // Optimistic UI
        setUploadJobInfo((prev) =>
          prev
            ? {
                ...prev,
                status: prev.status === 'confirmed' || prev.status === 'created' ? 'confirmed' : 'confirming',
                step: 'confirming',
                progress: prev.progress ?? 0,
              }
            : {
                job_id: resolvedJobId,
                status: 'confirming',
                step: 'confirming',
                progress: 0,
              },
        )
        // Ensure latest edits are saved before confirm
        if (uploadDraft) {
          await saveDraft(uploadDraft)
        }
        const res = await fetch(`${apiBase}/assignment/upload/confirm`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: resolvedJobId, strict_requirements: true }),
        })
        if (!res.ok) {
          const text = await res.text()
          let message = text || `状态码 ${res.status}`
          try {
            const parsed = JSON.parse(text)
            const detail = parsed?.detail || parsed
            if (typeof detail === 'string') message = detail
            if (detail?.message) message = detail.message
            if (detail?.error === 'job_not_ready') {
              const progress = detail?.progress !== undefined ? `（进度 ${detail.progress}%）` : ''
              message = `${detail.message || '解析尚未完成'}${progress}`
              setUploadStatusPollNonce((n) => n + 1)
            }
            if (detail?.missing && Array.isArray(detail.missing)) {
              message = `${detail.message || '作业要求未补全'}：${formatMissingRequirements(detail.missing)}`
            }
          } catch {
            // ignore
          }
          throw new Error(message)
        }
        const data = await res.json()
        if (data && typeof data === 'object') {
          const lines: string[] = []
          lines.push(data.message || '作业已确认创建。')
          if (data.assignment_id) lines.push(`作业编号：${data.assignment_id}`)
          if (data.question_count !== undefined) lines.push(`题目数量：${data.question_count}`)
          if (Array.isArray(data.requirements_missing) && data.requirements_missing.length) {
            lines.push(`作业要求缺失项：${formatMissingRequirements(data.requirements_missing)}`)
          }
          if (Array.isArray(data.warnings) && data.warnings.length) {
            lines.push(`解析提示：${data.warnings.join('；')}`)
          }
          const msg = lines.join('\n')
          setDraftActionStatus(msg)
          setUploadStatus(msg)
          setUploadJobInfo((prev) =>
            prev ? { ...prev, status: 'confirmed' } : { job_id: resolvedJobId, status: 'confirmed' },
          )
          setDraftPanelCollapsed(true)
          try {
            const raw = safeLocalStorageGetItem('teacherActiveUpload')
            if (raw) {
              const active = JSON.parse(raw)
              if (active?.type === 'assignment' && active?.job_id === resolvedJobId) safeLocalStorageRemoveItem('teacherActiveUpload')
            }
          } catch {
            // ignore
          }
          if (data.assignment_id) {
            setProgressAssignmentId(data.assignment_id)
            setProgressPanelCollapsed(false)
            void fetchAssignmentProgress(data.assignment_id)
          }
        }
      } catch (err: unknown) {
        const message = toErrorMessage(err)
        setUploadError(message)
        setDraftActionError(message)
        setUploadJobInfo((prev) => {
          if (!prev || prev.status !== 'confirming') return prev
          if (previousUploadJobInfo) {
            return {
              ...prev,
              status: previousUploadJobInfo.status,
              step: previousUploadJobInfo.step ?? prev.step,
              progress: previousUploadJobInfo.progress ?? prev.progress,
            }
          }
          return { ...prev, status: 'done', step: 'parsed', progress: prev.progress ?? 100 }
        })
        setUploadStatusPollNonce((n) => n + 1)
      } finally {
        setUploadConfirming(false)
      }
    },
    [
      apiBase,
      fetchAssignmentProgress,
      saveDraft,
      setDraftActionError,
      setDraftActionStatus,
      setDraftPanelCollapsed,
      setProgressAssignmentId,
      setProgressPanelCollapsed,
      setUploadConfirming,
      setUploadError,
      setUploadJobId,
      setUploadJobInfo,
      setUploadStatus,
      setUploadStatusPollNonce,
      uploadDraft,
      uploadJobId,
      uploadJobInfo,
    ],
  )

  return {
    handleUploadAssignment,
    saveDraft,
    handleConfirmUpload,
    fetchAssignmentProgress,
    refreshWorkflowWorkbench,
    scrollToWorkflowSection,
    assignmentWorkflowIndicator,
    assignmentWorkflowAutoState,
    computeLocalRequirementsMissing,
    updateDraftRequirement,
    updateDraftQuestion,
  }
}
