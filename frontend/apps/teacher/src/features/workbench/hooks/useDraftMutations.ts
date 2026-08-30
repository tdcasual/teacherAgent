import { useCallback } from 'react'
import type { UploadDraft } from '../../../appTypes'

type UseDraftMutationsParams = {
  uploadDraft: UploadDraft | null
  setUploadDraft: React.Dispatch<React.SetStateAction<UploadDraft | null>>
}

type UnknownRecord = Record<string, unknown>

export function useDraftMutations({
  setUploadDraft,
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

  return {
    computeLocalRequirementsMissing,
    updateDraftRequirement,
    updateDraftQuestion,
  }
}
