import { useCallback, type Dispatch, type FormEvent } from 'react'
import type { VerifiedStudent, VerifyResponse } from '../appTypes'
import { toErrorMessage, type StudentAction, type StudentState } from './useStudentState'

type UseVerificationParams = {
  state: StudentState
  dispatch: Dispatch<StudentAction>
}

export function useVerification({ state, dispatch }: UseVerificationParams) {
  const { apiBase, nameInput, classInput } = state

  const handleVerify = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      const name = nameInput.trim()
      const className = classInput.trim()
      dispatch({ type: 'SET', field: 'verifyError', value: '' })
      if (!name) {
        dispatch({ type: 'SET', field: 'verifyError', value: '请先输入姓名。' })
        return
      }
      dispatch({ type: 'SET', field: 'verifying', value: true })
      try {
        const res = await fetch(`${apiBase}/student/verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, class_name: className || undefined }),
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as VerifyResponse
        if (data.ok && data.student) {
          dispatch({ type: 'BATCH', actions: [
            { type: 'SET', field: 'verifiedStudent', value: data.student as VerifiedStudent },
            { type: 'SET', field: 'verifyOpen', value: false },
            { type: 'SET', field: 'verifyError', value: '' },
          ]})
        } else if (data.error === 'multiple') {
          dispatch({ type: 'SET', field: 'verifyError', value: '同名学生，请补充班级。' })
        } else {
          dispatch({ type: 'SET', field: 'verifyError', value: data.message || '未找到该学生，请检查姓名或班级。' })
        }
      } catch (err: unknown) {
        dispatch({ type: 'SET', field: 'verifyError', value: toErrorMessage(err) })
      } finally {
        dispatch({ type: 'SET', field: 'verifying', value: false })
      }
    },
    [apiBase, nameInput, classInput, dispatch],
  )

  return { handleVerify }
}
