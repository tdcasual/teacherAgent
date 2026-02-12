import { useCallback } from 'react'
import type { ExamUploadDraft, UploadDraft } from '../../../appTypes'

export type UseDraftMutationsParams = {
  uploadDraft: UploadDraft | null
  setUploadDraft: React.Dispatch<React.SetStateAction<UploadDraft | null>>
  examDraft: ExamUploadDraft | null
  setExamDraft: React.Dispatch<React.SetStateAction<ExamUploadDraft | null>>
}

type UnknownRecord = Record<string, unknown>

export function useDraftMutations({
  setUploadDraft,
  setExamDraft,
}: UseDraftMutationsParams) {
  const computeLocalRequirementsMissing = useCallback(
    (req: UnknownRecord): string[] => {
      const missing: string[] = []
      const subject = String(req?.subject || '').trim()
      const topic = String(req?.topic || '').trim()
      const grade = String(req?.grade_level || '').trim()
      const classLevel = String(req?.class_level || '').trim()
      const core = Array.isArray(req?.core_concepts) ? req.core_concepts : []
      const typical = String(req?.typical_problem || '').trim()
      const misconceptions = Array.isArray(req?.misconceptions)
        ? req.misconceptions
        : []
      const duration = Number(req?.duration_minutes || 0)
      const prefs = Array.isArray(req?.preferences) ? req.preferences : []

      if (!subject) missing.push('subject')
      if (!topic) missing.push('topic')
      if (!grade) missing.push('grade_level')
      if (!['偏弱', '中等', '较强', '混合'].includes(classLevel))
        missing.push('class_level')
      if (core.filter(Boolean).length < 3) missing.push('core_concepts')
      if (!typical) missing.push('typical_problem')
      if (misconceptions.filter(Boolean).length < 4)
        missing.push('misconceptions')
      if (![20, 40, 60].includes(duration)) missing.push('duration_minutes')
      if (prefs.filter(Boolean).length < 1) missing.push('preferences')

      return missing
    },
    [],
  )

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
    [setUploadDraft, computeLocalRequirementsMissing],
  )

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

  const updateExamDraftMeta = useCallback(
    (key: string, value: unknown) => {
      setExamDraft((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          meta: {
            ...(prev.meta || {}),
            [key]: value,
          },
        }
      })
    },
    [setExamDraft],
  )

  const updateExamQuestionField = useCallback(
    (index: number, patch: UnknownRecord) => {
      setExamDraft((prev) => {
        if (!prev) return prev
        const next = [...(prev.questions || [])]
        const cur = next[index] || {}
        next[index] = { ...cur, ...patch }
        return { ...prev, questions: next }
      })
    },
    [setExamDraft],
  )

  const updateExamAnswerKeyText = useCallback(
    (value: string) => {
      setExamDraft((prev) => {
        if (!prev) return prev
        return { ...prev, answer_key_text: value }
      })
    },
    [setExamDraft],
  )

  const updateExamScoreSchemaSelectedCandidate = useCallback(
    (candidateId: string) => {
      const nextCandidateId = String(candidateId || '').trim()
      setExamDraft((prev) => {
        if (!prev) return prev
        const prevSchema = prev.score_schema || {}
        const prevSubject = prevSchema.subject || {}
        const selectedAvailable = nextCandidateId
          ? Array.isArray(prevSubject?.candidate_columns)
            ? prevSubject.candidate_columns.some(
                (candidate) =>
                  String(candidate?.candidate_id || '') === nextCandidateId,
              )
            : true
          : true
        const selectionError =
          nextCandidateId && !selectedAvailable
            ? 'selected_candidate_not_found'
            : ''
        const nextNeedsConfirm = !nextCandidateId || !selectedAvailable
        return {
          ...prev,
          needs_confirm: nextNeedsConfirm,
          score_schema: {
            ...prevSchema,
            confirm: Boolean(nextCandidateId && selectedAvailable),
            needs_confirm: nextNeedsConfirm,
            subject: {
              ...prevSubject,
              selected_candidate_id: nextCandidateId,
              selected_candidate_available: selectedAvailable,
              ...(selectionError
                ? { selection_error: selectionError }
                : { selection_error: '' }),
            },
          },
        }
      })
    },
    [setExamDraft],
  )

  return {
    computeLocalRequirementsMissing,
    updateDraftRequirement,
    updateDraftQuestion,
    updateExamDraftMeta,
    updateExamQuestionField,
    updateExamAnswerKeyText,
    updateExamScoreSchemaSelectedCandidate,
  }
}
