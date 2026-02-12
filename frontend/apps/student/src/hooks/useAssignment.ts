import { useEffect, type Dispatch } from 'react'
import { isAbortError, toErrorMessage, todayDate, type StudentAction, type StudentState } from './useStudentState'

type UseAssignmentParams = {
  state: StudentState
  dispatch: Dispatch<StudentAction>
}

export function useAssignment({ state, dispatch }: UseAssignmentParams) {
  const { apiBase, verifiedStudent } = state

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) {
      dispatch({ type: 'BATCH', actions: [
        { type: 'SET', field: 'todayAssignment', value: null },
        { type: 'SET', field: 'assignmentError', value: '' },
        { type: 'SET', field: 'assignmentLoading', value: false },
      ]})
      return
    }
    const controller = new AbortController()
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'assignmentLoading', value: true },
      { type: 'SET', field: 'assignmentError', value: '' },
    ]})
    const timer = setTimeout(async () => {
      try {
        const date = todayDate()
        const url = new URL(`${apiBase}/assignment/today`)
        url.searchParams.set('student_id', sid)
        url.searchParams.set('date', date)
        url.searchParams.set('auto_generate', 'true')
        url.searchParams.set('generate', 'true')
        const res = await fetch(url.toString(), { signal: controller.signal })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = await res.json()
        dispatch({ type: 'SET', field: 'todayAssignment', value: data.assignment || null })
      } catch (err: unknown) {
        if (isAbortError(err)) return
        dispatch({ type: 'BATCH', actions: [
          { type: 'SET', field: 'assignmentError', value: toErrorMessage(err, '无法获取今日作业') },
          { type: 'SET', field: 'todayAssignment', value: null },
        ]})
      } finally {
        dispatch({ type: 'SET', field: 'assignmentLoading', value: false })
      }
    }, 300)
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [verifiedStudent, apiBase, dispatch])
}
