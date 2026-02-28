import { useCallback, type Dispatch, type FormEvent } from 'react'
import type {
  StudentIdentifyResponse,
  StudentLoginResponse,
  StudentVerifyCandidate,
  VerifiedStudent,
} from '../appTypes'
import { writeStudentAccessToken } from '../features/auth/studentAuth'
import { toErrorMessage, type StudentAction, type StudentState } from './useStudentState'

type UseVerificationParams = {
  state: StudentState
  dispatch: Dispatch<StudentAction>
}

const identifyStudent = async (apiBase: string, name: string, className: string) => {
  const res = await fetch(`${apiBase}/auth/student/identify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, class_name: className || undefined }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `状态码 ${res.status}`)
  }
  return (await res.json()) as StudentIdentifyResponse
}

const collectCandidateClasses = (candidates: StudentVerifyCandidate[]): string[] => {
  return candidates.map((item) => String(item?.student?.class_name || '').trim()).filter(Boolean)
}

const buildCandidateHint = (data: StudentIdentifyResponse): string => {
  const classes = Array.isArray(data.candidates)
    ? collectCandidateClasses(data.candidates)
    : []
  if (!classes.length) return ''
  const unique = Array.from(new Set(classes)).slice(0, 6)
  return `候选班级：${unique.join('、')}${classes.length > unique.length ? ' 等' : ''}。`
}

export function useVerification({ state, dispatch }: UseVerificationParams) {
  const { apiBase, nameInput, classInput, credentialInput } = state

  const handleVerify = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      const name = nameInput.trim()
      const className = classInput.trim()
      const credential = credentialInput.trim()
      dispatch({
        type: 'BATCH',
        actions: [
          { type: 'SET', field: 'verifyError', value: '' },
          { type: 'SET', field: 'verifyInfo', value: '' },
        ],
      })
      if (!name) {
        dispatch({ type: 'SET', field: 'verifyError', value: '请先输入姓名。' })
        return
      }
      if (!credential) {
        dispatch({ type: 'SET', field: 'verifyError', value: '请输入密码。' })
        return
      }

      dispatch({ type: 'SET', field: 'verifying', value: true })
      try {
        const identifyData = await identifyStudent(apiBase, name, className)
        if (!identifyData.ok || !identifyData.candidate_id) {
          if (identifyData.error === 'multiple') {
            const hint = buildCandidateHint(identifyData)
            dispatch({
              type: 'SET',
              field: 'verifyError',
              value: hint ? `同名学生，请补充班级。${hint}` : '同名学生，请补充班级。',
            })
          } else {
            dispatch({
              type: 'SET',
              field: 'verifyError',
              value: identifyData.message || '未找到该学生，请检查姓名或班级。',
            })
          }
          return
        }

        const loginRes = await fetch(`${apiBase}/auth/student/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            candidate_id: identifyData.candidate_id,
            credential_type: 'password',
            credential,
          }),
        })
        if (!loginRes.ok) {
          const text = await loginRes.text()
          throw new Error(text || `状态码 ${loginRes.status}`)
        }
        const loginData = (await loginRes.json()) as StudentLoginResponse
        if (!loginData.ok || !loginData.access_token || !loginData.student) {
          const reason = String(loginData.error || '').trim()
          let message = loginData.message || '认证失败，请检查密码。'
          if (reason === 'password_not_set') {
            message = '该账号尚未设置密码，请联系老师重置默认密码。'
          } else if (reason === 'invalid_credential') {
            message = '密码不正确，请重新输入。'
          } else if (reason === 'locked') {
            message = '登录尝试过多，请稍后再试。'
          }
          dispatch({ type: 'SET', field: 'verifyError', value: message })
          return
        }

        writeStudentAccessToken(loginData.access_token)
        dispatch({
          type: 'BATCH',
          actions: [
            { type: 'SET', field: 'verifiedStudent', value: loginData.student as VerifiedStudent },
            { type: 'SET', field: 'verifyOpen', value: false },
            { type: 'SET', field: 'verifyError', value: '' },
            { type: 'SET', field: 'verifyInfo', value: '认证成功，已启用会话。' },
          ],
        })
      } catch (err: unknown) {
        dispatch({ type: 'SET', field: 'verifyError', value: toErrorMessage(err) })
      } finally {
        dispatch({ type: 'SET', field: 'verifying', value: false })
      }
    },
    [apiBase, nameInput, classInput, credentialInput, dispatch],
  )

  return { handleVerify }
}
