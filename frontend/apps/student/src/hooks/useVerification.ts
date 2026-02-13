import { useCallback, type Dispatch, type FormEvent } from 'react'
import type {
  StudentIdentifyResponse,
  StudentLoginResponse,
  StudentSetPasswordResponse,
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

const buildCandidateHint = (data: StudentIdentifyResponse): string => {
  const classes = Array.isArray(data.candidates)
    ? data.candidates
      .map((item) => String(item?.student?.class_name || '').trim())
      .filter(Boolean)
    : []
  if (!classes.length) return ''
  const unique = Array.from(new Set(classes)).slice(0, 6)
  return `候选班级：${unique.join('、')}${classes.length > unique.length ? ' 等' : ''}。`
}

export function useVerification({ state, dispatch }: UseVerificationParams) {
  const { apiBase, nameInput, classInput, credentialInput, credentialType, newPasswordInput } = state

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
        dispatch({
          type: 'SET',
          field: 'verifyError',
          value: credentialType === 'token' ? '请输入 token。' : '请输入密码。',
        })
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
            credential_type: credentialType,
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
          let message = loginData.message || '认证失败，请检查 token 或密码。'
          if (reason === 'password_not_set') {
            message = '当前账号尚未设置密码，请先使用 token 登录后设置密码。'
          } else if (reason === 'invalid_credential') {
            message = credentialType === 'token' ? 'token 不正确，请重新输入。' : '密码不正确，请重新输入。'
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
    [apiBase, nameInput, classInput, credentialInput, credentialType, dispatch],
  )

  const handleSetPassword = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      const name = nameInput.trim()
      const className = classInput.trim()
      const credential = credentialInput.trim()
      const newPassword = newPasswordInput.trim()
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
        dispatch({ type: 'SET', field: 'verifyError', value: '请先输入用于校验的 token 或当前密码。' })
        return
      }
      if (!newPassword) {
        dispatch({ type: 'SET', field: 'verifyError', value: '请输入新密码。' })
        return
      }

      dispatch({ type: 'SET', field: 'settingPassword', value: true })
      try {
        const identifyData = await identifyStudent(apiBase, name, className)
        if (!identifyData.ok || !identifyData.candidate_id) {
          const hint = identifyData.error === 'multiple' ? buildCandidateHint(identifyData) : ''
          dispatch({
            type: 'SET',
            field: 'verifyError',
            value: hint
              ? `同名学生，请补充班级。${hint}`
              : identifyData.message || '无法定位学生，请确认姓名和班级。',
          })
          return
        }

        const res = await fetch(`${apiBase}/auth/student/set-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            candidate_id: identifyData.candidate_id,
            credential_type: credentialType,
            credential,
            new_password: newPassword,
          }),
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as StudentSetPasswordResponse
        if (!data.ok) {
          const reason = String(data.error || '').trim()
          let message = data.message || '设置密码失败。'
          if (reason === 'weak_password') {
            message = '密码至少 8 位，且需同时包含字母与数字。'
          } else if (reason === 'invalid_credential') {
            message = '当前 token/密码校验失败，请重试。'
          }
          dispatch({ type: 'SET', field: 'verifyError', value: message })
          return
        }

        dispatch({
          type: 'BATCH',
          actions: [
            { type: 'SET', field: 'verifyInfo', value: '密码设置成功。后续可使用 token 或密码登录。' },
            { type: 'SET', field: 'newPasswordInput', value: '' },
            { type: 'SET', field: 'credentialType', value: 'password' },
          ],
        })
      } catch (err: unknown) {
        dispatch({ type: 'SET', field: 'verifyError', value: toErrorMessage(err) })
      } finally {
        dispatch({ type: 'SET', field: 'settingPassword', value: false })
      }
    },
    [apiBase, nameInput, classInput, credentialInput, credentialType, newPasswordInput, dispatch],
  )

  return { handleVerify, handleSetPassword }
}
