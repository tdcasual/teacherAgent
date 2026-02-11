import { useCallback, useEffect, useRef, type FormEvent } from 'react'
import { safeLocalStorageSetItem, safeLocalStorageGetItem, safeLocalStorageRemoveItem } from '../../../utils/storage'
import type {
  ExamUploadDraft,
  ExamUploadJobStatus,
} from '../../../appTypes'

export type UseExamWorkflowParams = {
  apiBase: string
  examId: string
  examDate: string
  examClassName: string
  examPaperFiles: File[]
  examScoreFiles: File[]
  examAnswerFiles: File[]
  examUploading: boolean
  examUploadError: string
  examJobId: string
  examJobInfo: ExamUploadJobStatus | null
  examDraft: ExamUploadDraft | null
  examDraftPanelCollapsed: boolean
  examDraftError: string
  examDraftActionError: string
  examDraftSaving: boolean
  examConfirming: boolean
  examStatusPollNonce: number
  uploadCardCollapsed: boolean
  uploadMode: string
  examWorkflowAutoState: string
  setExamUploadError: (v: string) => void
  setExamUploadStatus: (v: string | ((prev: string) => string)) => void
  setExamJobId: (v: string) => void
  setExamJobInfo: (v: ExamUploadJobStatus | null | ((prev: ExamUploadJobStatus | null) => ExamUploadJobStatus | null)) => void
  setExamDraft: (v: ExamUploadDraft | null | ((prev: ExamUploadDraft | null) => ExamUploadDraft | null)) => void
  setExamDraftPanelCollapsed: (v: boolean | ((prev: boolean) => boolean)) => void
  setExamDraftLoading: (v: boolean) => void
  setExamDraftError: (v: string) => void
  setExamDraftSaving: (v: boolean) => void
  setExamDraftActionStatus: (v: string) => void
  setExamDraftActionError: (v: string) => void
  setExamUploading: (v: boolean) => void
  setExamConfirming: (v: boolean) => void
  setExamPaperFiles: (v: File[]) => void
  setExamScoreFiles: (v: File[]) => void
  setExamAnswerFiles: (v: File[]) => void
  setUploadCardCollapsed: (v: boolean | ((prev: boolean) => boolean)) => void
  setExamStatusPollNonce: (v: number | ((prev: number) => number)) => void
}

export function useExamWorkflow(params: UseExamWorkflowParams) {
  const {
    apiBase,
    examId, examDate, examClassName,
    examPaperFiles, examScoreFiles, examAnswerFiles,
    examJobId, examJobInfo, examDraft,
    examDraftPanelCollapsed, examDraftError, examDraftActionError,
    examUploadError, uploadCardCollapsed, uploadMode,
    examWorkflowAutoState,
    setExamUploadError, setExamUploadStatus,
    setExamJobId, setExamJobInfo,
    setExamDraft, setExamDraftPanelCollapsed,
    setExamDraftLoading, setExamDraftError,
    setExamDraftSaving, setExamDraftActionStatus, setExamDraftActionError,
    setExamUploading, setExamConfirming,
    setExamPaperFiles, setExamScoreFiles, setExamAnswerFiles,
    setUploadCardCollapsed, setExamStatusPollNonce,
  } = params

  // --- Exam-specific effects ---

  // Auto-expand upload card on exam upload error
  useEffect(() => {
    if (examUploadError && uploadCardCollapsed) setUploadCardCollapsed(false)
  }, [examUploadError, uploadCardCollapsed])

  // Auto-expand exam draft panel on draft errors
  useEffect(() => {
    if ((examDraftError || examDraftActionError) && examDraftPanelCollapsed) {
      setExamDraftPanelCollapsed(false)
    }
  }, [examDraftError, examDraftActionError, examDraftPanelCollapsed])

  // Exam workflow auto-state panel management
  const examAutoStateRef = useRef('')

  useEffect(() => {
    if (uploadMode !== 'exam') return
    if (examAutoStateRef.current === examWorkflowAutoState) return
    examAutoStateRef.current = examWorkflowAutoState
    switch (examWorkflowAutoState) {
      case 'uploading':
      case 'parsing':
      case 'parse-error':
        setUploadCardCollapsed(false)
        break
      case 'review':
      case 'confirming':
        setUploadCardCollapsed(true)
        setExamDraftPanelCollapsed(false)
        break
      case 'review-error':
      case 'confirm-error':
        setExamDraftPanelCollapsed(false)
        break
      case 'confirmed':
        setUploadCardCollapsed(true)
        setExamDraftPanelCollapsed(true)
        break
      default:
        break
    }
  }, [examWorkflowAutoState, uploadMode])

  // Load exam draft when job is done
  useEffect(() => {
    if (!examJobId) return
    if (!examJobInfo) return
    if (examJobInfo.status !== 'done' && examJobInfo.status !== 'confirmed') return
    let active = true
    const loadDraft = async () => {
      setExamDraftError('')
      setExamDraftLoading(true)
      try {
        const res = await fetch(`${apiBase}/exam/upload/draft?job_id=${encodeURIComponent(examJobId)}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = await res.json()
        if (!active) return
        let draft = data?.draft as ExamUploadDraft
        if (!draft || !draft.questions) throw new Error('draft 数据缺失')

        const scoreSchema = draft.score_schema || {}
        const subjectSchema = scoreSchema.subject || {}
        const selectedCandidateId = String(subjectSchema.selected_candidate_id || '').trim()
        const suggestedCandidateId = String(
          subjectSchema.suggested_selected_candidate_id || subjectSchema.recommended_candidate_id || '',
        ).trim()
        const candidateColumns = Array.isArray(subjectSchema.candidate_columns) ? subjectSchema.candidate_columns : []
        const suggestedAvailable = Boolean(
          suggestedCandidateId && candidateColumns.some((candidate: any) => String(candidate?.candidate_id || '') === suggestedCandidateId),
        )
        if (!selectedCandidateId && suggestedAvailable) {
          draft = {
            ...draft,
            needs_confirm: true,
            score_schema: {
              ...scoreSchema,
              confirm: false,
              needs_confirm: true,
              subject: {
                ...subjectSchema,
                selected_candidate_id: suggestedCandidateId,
                selected_candidate_available: true,
                selection_error: '',
              },
            },
          }
        }

        setExamDraft(draft)
        setExamDraftPanelCollapsed(false)
      } catch (err: any) {
        if (!active) return
        setExamDraftError(err.message || String(err))
      } finally {
        if (!active) return
        setExamDraftLoading(false)
      }
    }
    loadDraft()
    return () => {
      active = false
    }
  }, [examJobId, examJobInfo?.status, apiBase])

  // --- Exam workflow handlers ---

  const handleUploadExam = useCallback(async (event: FormEvent) => {
    event.preventDefault()
    setExamUploadError('')
    setExamUploadStatus('')
    setExamJobId('')
    setExamJobInfo(null)
    setExamDraft(null)
    setExamDraftPanelCollapsed(false)
    setExamDraftError('')
    setExamDraftActionStatus('')
    setExamDraftActionError('')
    setUploadCardCollapsed(false)
    if (!examPaperFiles.length) {
      setExamUploadError('请至少上传一份试卷文件（文档或图片）')
      return
    }
    if (!examScoreFiles.length) {
      setExamUploadError('请至少上传一份成绩文件（表格文件或文档/图片）')
      return
    }
    setExamUploading(true)
    try {
      const fd = new FormData()
      if (examId.trim()) fd.append('exam_id', examId.trim())
      if (examDate.trim()) fd.append('date', examDate.trim())
      if (examClassName.trim()) fd.append('class_name', examClassName.trim())
      examPaperFiles.forEach((file) => fd.append('paper_files', file))
      examScoreFiles.forEach((file) => fd.append('score_files', file))
      examAnswerFiles.forEach((file) => fd.append('answer_files', file))

      const res = await fetch(`${apiBase}/exam/upload/start`, { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = await res.json()
      if (data && typeof data === 'object') {
        if (data.job_id) {
          const jid = String(data.job_id)
          setExamJobId(jid)
          try {
            safeLocalStorageSetItem('teacherActiveUpload', JSON.stringify({ type: 'exam', job_id: jid }))
          } catch {
            // ignore
          }
        }
        const message = data.message || '考试解析任务已创建，后台处理中。'
        setExamUploadStatus(message)
      } else {
        setExamUploadStatus(typeof data === 'string' ? data : JSON.stringify(data, null, 2))
      }
      setExamPaperFiles([])
      setExamScoreFiles([])
      setExamAnswerFiles([])
    } catch (err: any) {
      setExamUploadError(err.message || String(err))
    } finally {
      setExamUploading(false)
    }
  }, [
    apiBase, examId, examDate, examClassName,
    examPaperFiles, examScoreFiles, examAnswerFiles,
  ])

  const saveExamDraft = useCallback(async (draft: ExamUploadDraft) => {
    const selectedCandidateId = String((draft.score_schema?.subject?.selected_candidate_id || '').trim())
    const previousCandidateId = String((examJobInfo?.score_schema?.subject?.selected_candidate_id || '').trim())
    const shouldReparse = Boolean(selectedCandidateId && selectedCandidateId !== previousCandidateId)
    setExamDraftSaving(true)
    setExamUploadError('')
    setExamDraftActionError('')
    setExamDraftActionStatus('正在保存考试草稿…')
    try {
      const res = await fetch(`${apiBase}/exam/upload/draft/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: draft.job_id,
          meta: draft.meta,
          questions: draft.questions,
          score_schema: draft.score_schema || {},
          answer_key_text: draft.answer_key_text ?? '',
          reparse: shouldReparse,
        }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = await res.json()
      const msg = data?.message || '考试草稿已保存。'
      setExamDraftActionStatus(msg)
      setExamUploadStatus((prev: string) => `${prev ? prev + '\n\n' : ''}${msg}`)
      const reparseExpected = shouldReparse
      setExamDraft((prev: ExamUploadDraft | null) =>
        prev
          ? {
              ...prev,
              draft_saved: true,
              draft_version: data?.draft_version ?? prev.draft_version,
              ...(reparseExpected ? { needs_confirm: true } : {}),
            }
          : prev
      )
      if (reparseExpected) {
        setExamDraftActionStatus('已保存映射选择，正在按新映射重新解析成绩…')
        setExamUploadStatus((prev: string) => `${prev ? prev + '\n\n' : ''}已保存映射选择，正在重新解析成绩…`)
        setExamStatusPollNonce((n: number) => n + 1)
      }
      return data
    } catch (err: any) {
      const message = err?.message || String(err)
      setExamDraftActionError(message)
      throw err
    } finally {
      setExamDraftSaving(false)
    }
  }, [apiBase, examJobInfo?.score_schema?.subject?.selected_candidate_id])

  const handleConfirmExamUpload = useCallback(async () => {
    if (!examJobId) return
    setExamUploadError('')
    setExamDraftActionError('')
    setExamDraftActionStatus('正在创建考试…')
    setExamConfirming(true)
    try {
      if (examJobInfo && examJobInfo.status !== 'done' && examJobInfo.status !== 'confirmed') {
        const message = '解析尚未完成，请等待解析完成后再创建考试。'
        setExamUploadError(message)
        setExamDraftActionError(message)
        setExamStatusPollNonce((n: number) => n + 1)
        return
      }
      setExamJobInfo((prev: ExamUploadJobStatus | null) =>
        prev
          ? {
              ...prev,
              status: prev.status === 'confirmed' ? 'confirmed' : 'confirming',
              step: 'confirming',
              progress: prev.progress ?? 0,
            }
          : prev
      )
      if (examDraft) {
        await saveExamDraft(examDraft)
      }
      const res = await fetch(`${apiBase}/exam/upload/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: examJobId }),
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
            setExamStatusPollNonce((n: number) => n + 1)
          }
          if (detail?.error === 'score_schema_confirm_required') {
            message = detail?.message || '成绩映射置信度不足，请先在草稿中选择并保存物理分映射列。'
            setExamDraftPanelCollapsed(false)
            setExamStatusPollNonce((n: number) => n + 1)
          }
        } catch {
          // ignore
        }
        throw new Error(message)
      }
      const data = await res.json()
      if (data && typeof data === 'object') {
        const lines: string[] = []
        lines.push(data.message || '考试已确认创建。')
        if (data.exam_id) lines.push(`考试编号：${data.exam_id}`)
        const msg = lines.join('\n')
        setExamDraftActionStatus(msg)
        setExamUploadStatus(msg)
        setExamJobInfo((prev: ExamUploadJobStatus | null) => (prev ? { ...prev, status: 'confirmed' } : prev))
        setExamDraftPanelCollapsed(true)
        try {
          const raw = safeLocalStorageGetItem('teacherActiveUpload')
          if (raw) {
            const active = JSON.parse(raw)
            if (active?.type === 'exam' && active?.job_id === examJobId) safeLocalStorageRemoveItem('teacherActiveUpload')
          }
        } catch {
          // ignore
        }
      }
    } catch (err: any) {
      const message = err?.message || String(err)
      setExamUploadError(message)
      setExamDraftActionError(message)
    } finally {
      setExamConfirming(false)
    }
  }, [apiBase, examJobId, examJobInfo, examDraft, saveExamDraft])

  return {
    handleUploadExam,
    saveExamDraft,
    handleConfirmExamUpload,
  }
}
