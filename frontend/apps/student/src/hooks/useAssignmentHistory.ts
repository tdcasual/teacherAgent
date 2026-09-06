import { useCallback, useEffect, useState } from 'react'
import type { StudentAssignmentHistoryItem } from '../appTypes'
import { isAbortError, toErrorMessage } from './useStudentState'

type UseAssignmentHistoryParams = {
  apiBase: string
  studentId: string
  enabled: boolean
}

const toHistoryItems = (payload: unknown): StudentAssignmentHistoryItem[] => {
  if (!payload || typeof payload !== 'object') return []
  const raw = (payload as { assignments?: unknown }).assignments
  if (!Array.isArray(raw)) return []
  const items: StudentAssignmentHistoryItem[] = []
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object') continue
    const item = entry as Record<string, unknown>
    const assignmentId = String(item.assignment_id || '').trim()
    if (!assignmentId) continue
    items.push({
      assignment_id: assignmentId,
      teacher_id: String(item.teacher_id || '').trim(),
      subject_id: String(item.subject_id || '').trim(),
      title: String(item.title || assignmentId).trim() || assignmentId,
      due_at: item.due_at ? String(item.due_at) : '',
      visibility_status: String(item.visibility_status || '').trim(),
      submitted: Boolean(item.submitted),
      official_score: typeof item.official_score === 'number' ? item.official_score : null,
      archived_at: item.archived_at ? String(item.archived_at) : null,
    })
  }
  return items
}

export function useAssignmentHistory({ apiBase, studentId, enabled }: UseAssignmentHistoryParams) {
  const [items, setItems] = useState<StudentAssignmentHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const reload = useCallback(async () => {
    const sid = studentId.trim()
    if (!sid || !enabled) {
      setItems([])
      setError('')
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      const url = new URL(`${apiBase}/student/assignments/history`)
      url.searchParams.set('student_id', sid)
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = await res.json()
      setItems(toHistoryItems(data))
    } catch (err: unknown) {
      if (isAbortError(err)) return
      setError(toErrorMessage(err, '无法获取作业记录'))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [apiBase, enabled, studentId])

  useEffect(() => {
    void reload()
  }, [reload])

  return { items, loading, error, reload }
}
