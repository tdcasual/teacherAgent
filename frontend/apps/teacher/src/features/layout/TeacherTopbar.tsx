import { useEffect, useState, type FormEvent, type MutableRefObject } from 'react'

import { safeLocalStorageGetItem } from '../../utils/storage'
import {
  TEACHER_AUTH_EVENT,
  clearTeacherAuthSession,
  readTeacherAccessToken,
  readTeacherAuthSubject,
  writeTeacherAuthSession,
} from '../auth/teacherAuth'

type TeacherTopbarProps = {
  topbarRef: MutableRefObject<HTMLElement | null>
  sessionSidebarOpen: boolean
  skillsOpen: boolean
  onToggleSessionSidebar: () => void
  onOpenRoutingSettingsPanel: () => void
  onOpenPersonaManager: () => void
  onToggleSkillsWorkbench: () => void
  onToggleSettingsPanel: () => void
}

type TeacherIdentifyResponse = {
  ok: boolean
  error?: string
  message?: string
  candidate_id?: string
  need_email_disambiguation?: boolean
}

type TeacherLoginResponse = {
  ok: boolean
  error?: string
  message?: string
  access_token?: string
  subject_id?: string
  teacher?: {
    teacher_id?: string
    teacher_name?: string
    email?: string
  }
}

type TeacherSetPasswordResponse = {
  ok: boolean
  error?: string
  message?: string
}

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function TeacherTopbar({
  topbarRef,
  sessionSidebarOpen,
  skillsOpen,
  onToggleSessionSidebar,
  onOpenRoutingSettingsPanel,
  onOpenPersonaManager,
  onToggleSkillsWorkbench,
  onToggleSettingsPanel,
}: TeacherTopbarProps) {
  const [authOpen, setAuthOpen] = useState(() => !readTeacherAccessToken())
  const [authed, setAuthed] = useState(() => Boolean(readTeacherAccessToken()))
  const [authSubjectLabel, setAuthSubjectLabel] = useState(() => {
    const subject = readTeacherAuthSubject()
    return subject?.teacher_name || subject?.teacher_id || ''
  })

  const [nameInput, setNameInput] = useState('')
  const [emailInput, setEmailInput] = useState('')
  const [credentialInput, setCredentialInput] = useState('')
  const [credentialType, setCredentialType] = useState<'token' | 'password'>('token')
  const [newPasswordInput, setNewPasswordInput] = useState('')
  const [needEmail, setNeedEmail] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [settingPassword, setSettingPassword] = useState(false)
  const [authError, setAuthError] = useState('')
  const [authInfo, setAuthInfo] = useState('')

  useEffect(() => {
    const sync = () => {
      const hasToken = Boolean(readTeacherAccessToken())
      setAuthed(hasToken)
      const subject = readTeacherAuthSubject()
      setAuthSubjectLabel(subject?.teacher_name || subject?.teacher_id || '')
      if (!hasToken) {
        setAuthOpen(true)
      }
    }
    sync()
    window.addEventListener('storage', sync)
    window.addEventListener(TEACHER_AUTH_EVENT, sync as EventListener)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener(TEACHER_AUTH_EVENT, sync as EventListener)
    }
  }, [])

  const handleAuthSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const apiBase = safeLocalStorageGetItem('apiBaseTeacher') || DEFAULT_API_URL
    const name = nameInput.trim()
    const email = emailInput.trim()
    const credential = credentialInput.trim()

    setAuthError('')
    setAuthInfo('')

    if (!name) {
      setAuthError('请输入教师姓名。')
      return
    }
    if (!credential) {
      setAuthError(credentialType === 'token' ? '请输入 token。' : '请输入密码。')
      return
    }

    setSubmitting(true)
    try {
      const identifyRes = await fetch(`${apiBase}/auth/teacher/identify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email: email || undefined }),
      })
      if (!identifyRes.ok) {
        const text = await identifyRes.text()
        throw new Error(text || `状态码 ${identifyRes.status}`)
      }
      const identifyData = (await identifyRes.json()) as TeacherIdentifyResponse
      if (!identifyData.ok || !identifyData.candidate_id) {
        const needEmailFlag = Boolean(identifyData.need_email_disambiguation)
        setNeedEmail(needEmailFlag)
        setAuthError(identifyData.message || (needEmailFlag ? '该姓名存在多个教师，请补充邮箱。' : '未找到该教师。'))
        return
      }

      const loginRes = await fetch(`${apiBase}/auth/teacher/login`, {
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
      const loginData = (await loginRes.json()) as TeacherLoginResponse
      if (!loginData.ok || !loginData.access_token) {
        const reason = String(loginData.error || '').trim()
        let message = loginData.message || '教师认证失败。'
        if (reason === 'invalid_credential') {
          message = credentialType === 'token' ? 'token 不正确，请重试。' : '密码不正确，请重试。'
        } else if (reason === 'password_not_set') {
          message = '当前教师账号尚未设置密码，请先使用 token 登录。'
        } else if (reason === 'locked') {
          message = '尝试次数过多，请稍后再试。'
        }
        setAuthError(message)
        return
      }

      const teacher = loginData.teacher || {}
      const teacherId = String(loginData.subject_id || teacher.teacher_id || identifyData.candidate_id || '').trim()
      const teacherName = String(teacher.teacher_name || name || teacherId).trim()
      const teacherEmail = String(teacher.email || email || '').trim()
      writeTeacherAuthSession({
        accessToken: loginData.access_token,
        teacherId,
        teacherName,
        ...(teacherEmail ? { email: teacherEmail } : {}),
      })

      setNeedEmail(false)
      setCredentialInput('')
      setAuthInfo('认证成功。')
      setAuthOpen(false)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '认证失败')
      setAuthError(message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleSetPassword = async (event: FormEvent) => {
    event.preventDefault()
    const apiBase = safeLocalStorageGetItem('apiBaseTeacher') || DEFAULT_API_URL
    const name = nameInput.trim()
    const email = emailInput.trim()
    const credential = credentialInput.trim()
    const newPassword = newPasswordInput.trim()

    setAuthError('')
    setAuthInfo('')

    if (!name) {
      setAuthError('请输入教师姓名。')
      return
    }
    if (!credential) {
      setAuthError('请先输入用于校验的 token 或当前密码。')
      return
    }
    if (!newPassword) {
      setAuthError('请输入新密码。')
      return
    }

    setSettingPassword(true)
    try {
      const identifyRes = await fetch(`${apiBase}/auth/teacher/identify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email: email || undefined }),
      })
      if (!identifyRes.ok) {
        const text = await identifyRes.text()
        throw new Error(text || `状态码 ${identifyRes.status}`)
      }
      const identifyData = (await identifyRes.json()) as TeacherIdentifyResponse
      if (!identifyData.ok || !identifyData.candidate_id) {
        const needEmailFlag = Boolean(identifyData.need_email_disambiguation)
        setNeedEmail(needEmailFlag)
        setAuthError(identifyData.message || (needEmailFlag ? '该姓名存在多个教师，请补充邮箱。' : '未找到该教师。'))
        return
      }

      const setPasswordRes = await fetch(`${apiBase}/auth/teacher/set-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_id: identifyData.candidate_id,
          credential_type: credentialType,
          credential,
          new_password: newPassword,
        }),
      })
      if (!setPasswordRes.ok) {
        const text = await setPasswordRes.text()
        throw new Error(text || `状态码 ${setPasswordRes.status}`)
      }
      const setPasswordData = (await setPasswordRes.json()) as TeacherSetPasswordResponse
      if (!setPasswordData.ok) {
        const reason = String(setPasswordData.error || '').trim()
        let message = setPasswordData.message || '设置密码失败。'
        if (reason === 'weak_password') {
          message = '密码至少 8 位，且需同时包含字母和数字。'
        } else if (reason === 'invalid_credential') {
          message = '当前 token/密码校验失败，请重试。'
        }
        setAuthError(message)
        return
      }

      setCredentialType('password')
      setNewPasswordInput('')
      setAuthInfo('密码设置成功，后续可使用密码登录（token 仍可用）。')
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || '设置密码失败')
      setAuthError(message)
    } finally {
      setSettingPassword(false)
    }
  }

  return (
    <header
      ref={topbarRef}
      className="flex justify-between items-center gap-[12px] px-4 py-[10px] bg-white/[0.94] border-b border-border sticky top-0 z-[25]"
      style={{ backdropFilter: 'saturate(180%) blur(8px)' }}
    >
      <div className="flex items-center gap-[10px] flex-wrap">
        <div className="font-bold text-[16px] tracking-[0.2px]">物理教学助手 · 老师端</div>
        <button className="ghost" type="button" onClick={onToggleSessionSidebar}>
          {sessionSidebarOpen ? '收起会话' : '展开会话'}
        </button>
      </div>
      <div className="flex gap-[10px] items-center flex-wrap relative">
        <div className="role-badge teacher">身份：老师</div>
        {authed ? <span className="text-xs text-muted">已认证：{authSubjectLabel || '教师'}</span> : null}
        <button className="ghost" type="button" onClick={() => setAuthOpen((prev) => !prev)}>
          {authed ? '认证信息' : '教师认证'}
        </button>
        <button className="ghost" type="button" onClick={onOpenRoutingSettingsPanel}>
          模型路由
        </button>
        <button className="ghost" type="button" onClick={onOpenPersonaManager}>
          角色管理
        </button>
        <button className="ghost" type="button" onClick={onToggleSkillsWorkbench}>
          {skillsOpen ? '收起工作台' : '打开工作台'}
        </button>
        <button
          className="ghost border-none bg-transparent cursor-pointer p-[6px] rounded-lg text-[#6b7280] transition-[background] duration-150 ease-in-out hover:bg-surface-soft [&_svg]:block"
          onClick={onToggleSettingsPanel}
          aria-label="设置"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>

        {authOpen ? (
          <div className="absolute right-0 top-[calc(100%+8px)] w-[320px] rounded-xl border border-border bg-white shadow-[0_12px_28px_rgba(15,23,42,0.14)] p-3 z-40 grid gap-2.5">
            <div className="text-sm font-semibold">教师认证</div>
            <form className="grid gap-2" onSubmit={handleAuthSubmit}>
              <div className="grid gap-1">
                <label className="text-xs text-muted">姓名</label>
                <input
                  value={nameInput}
                  onChange={(event) => setNameInput(event.target.value)}
                  placeholder="例如：张老师"
                  autoComplete="name"
                />
              </div>
              <div className="grid gap-1">
                <label className="text-xs text-muted">邮箱（同名时必填）</label>
                <input
                  value={emailInput}
                  onChange={(event) => setEmailInput(event.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                />
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className={`ghost ${credentialType === 'token' ? 'font-semibold' : ''}`}
                  onClick={() => setCredentialType('token')}
                >
                  token
                </button>
                <button
                  type="button"
                  className={`ghost ${credentialType === 'password' ? 'font-semibold' : ''}`}
                  onClick={() => setCredentialType('password')}
                >
                  密码
                </button>
              </div>
              <div className="grid gap-1">
                <label className="text-xs text-muted">{credentialType === 'token' ? 'token' : '密码'}</label>
                <input
                  type={credentialType === 'token' ? 'text' : 'password'}
                  value={credentialInput}
                  onChange={(event) => setCredentialInput(event.target.value)}
                  placeholder={credentialType === 'token' ? '输入分发 token' : '输入已设置密码'}
                  autoComplete={credentialType === 'token' ? 'off' : 'current-password'}
                />
              </div>
              <button
                type="submit"
                className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer"
                disabled={submitting}
              >
                {submitting ? '认证中…' : '确认认证'}
              </button>
            </form>
            <form className="grid gap-2 border border-border rounded-[10px] p-2.5 bg-surface-soft" onSubmit={handleSetPassword}>
              <div className="text-xs text-muted">使用当前 token 或密码设置新密码（设置后 token 仍可登录）</div>
              <div className="grid gap-1">
                <label className="text-xs text-muted">新密码</label>
                <input
                  type="password"
                  value={newPasswordInput}
                  onChange={(event) => setNewPasswordInput(event.target.value)}
                  placeholder="至少 8 位，含字母和数字"
                  autoComplete="new-password"
                />
              </div>
              <button
                type="submit"
                className="border-none rounded-[10px] px-3 py-[9px] bg-[#0f766e] text-white cursor-pointer"
                disabled={settingPassword}
              >
                {settingPassword ? '设置中…' : '设置密码'}
              </button>
            </form>
            {needEmail ? <div className="text-xs text-muted">检测到同名教师，请补充邮箱后重试。</div> : null}
            {authError ? <div className="status err">{authError}</div> : null}
            {authInfo ? <div className="status ok">{authInfo}</div> : null}
            {authed ? (
              <button
                type="button"
                className="ghost justify-start"
                onClick={() => {
                  clearTeacherAuthSession()
                  setAuthInfo('')
                  setAuthError('')
                }}
              >
                退出认证
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </header>
  )
}
