import { useCallback, useEffect, useId, useState, type FormEvent } from 'react'

import { resolveRuntimeApiBase } from '../../../../shared/apiBase'
import { readTeacherAccessToken } from '../auth/teacherAuth'
import { safeLocalStorageGetItem } from '../../utils/storage'

type TeacherAuthItem = {
  teacher_id?: string
  teacher_name?: string
  email?: string
  is_disabled?: boolean
}

type CreateTeacherResponse = {
  ok?: boolean
  error?: string
  message?: string
  teacher_id?: string
  temp_password?: string
}

type ResetPasswordResponse = {
  ok?: boolean
  error?: string
  message?: string
  temp_password?: string
}

const toText = (value: unknown): string => String(value ?? '').trim()

function TempPasswordOnce({ password, onCopied }: { password: string; onCopied?: () => void }) {
  const [copied, setCopied] = useState(false)
  if (!password) return null
  return (
    <div className="grid gap-1.5 rounded-lg border border-border bg-white p-3">
      <div className="text-xs text-muted">一次性临时密码，请立即复制发给教师。</div>
      <div className="font-mono text-sm break-all">{password}</div>
      {copied ? (
        <div className="text-xs text-muted">已复制</div>
      ) : (
        <button
          type="button"
          className="ghost justify-start w-fit"
          onClick={() => {
            void navigator.clipboard.writeText(password).then(() => {
              setCopied(true)
              onCopied?.()
            })
          }}
        >
          复制一次
        </button>
      )}
    </div>
  )
}

export default function AdminSchoolPanel() {
  const formId = useId()
  const nameId = `${formId}-name`
  const emailId = `${formId}-email`
  const teacherIdField = `${formId}-teacher-id`
  const [nameInput, setNameInput] = useState('')
  const [emailInput, setEmailInput] = useState('')
  const [teacherIdInput, setTeacherIdInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [tempPassword, setTempPassword] = useState('')
  const [items, setItems] = useState<TeacherAuthItem[]>([])
  const [loadingList, setLoadingList] = useState(false)

  const apiBase = resolveRuntimeApiBase(safeLocalStorageGetItem('apiBaseTeacher'))

  const authHeaders = useCallback((): HeadersInit => {
    const token = readTeacherAccessToken()
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }
  }, [])

  const refreshList = useCallback(async () => {
    setLoadingList(true)
    try {
      const res = await fetch(`${apiBase}/auth/admin/teacher/list`, { headers: authHeaders() })
      const data = (await res.json()) as { ok?: boolean; items?: TeacherAuthItem[]; detail?: string }
      if (!res.ok) {
        setError(toText(data.detail) || `状态码 ${res.status}`)
        return
      }
      setItems(Array.isArray(data.items) ? data.items : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载教师列表失败')
    } finally {
      setLoadingList(false)
    }
  }, [apiBase, authHeaders])

  useEffect(() => {
    void refreshList()
  }, [refreshList])

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault()
    const teacherName = nameInput.trim()
    if (!teacherName) {
      setError('请填写教师姓名。')
      return
    }
    setError('')
    setInfo('')
    setTempPassword('')
    setSubmitting(true)
    try {
      const payload: Record<string, string> = { teacher_name: teacherName }
      const email = emailInput.trim()
      const teacherId = teacherIdInput.trim()
      if (email) payload.email = email
      if (teacherId) payload.teacher_id = teacherId
      const res = await fetch(`${apiBase}/auth/admin/teacher/create`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      })
      const data = (await res.json()) as CreateTeacherResponse & { detail?: string }
      if (!res.ok || !data.ok) {
        const code = toText(data.detail || data.error)
        const messages: Record<string, string> = {
          teacher_id_taken: '教师 ID 已被占用。',
          email_taken: '该邮箱已被占用。',
          invalid_teacher_id: '教师 ID 不合法，且不能为 teacher。',
          missing_teacher_name: '请填写教师姓名。',
        }
        setError(messages[code] || data.message || code || '创建教师失败。')
        return
      }
      setTempPassword(toText(data.temp_password))
      setInfo(`已创建教师 ${toText(data.teacher_id)}。`)
      setNameInput('')
      setEmailInput('')
      setTeacherIdInput('')
      await refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建教师失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDisable = async (teacherId: string, isDisabled: boolean) => {
    setError('')
    setInfo('')
    const res = await fetch(`${apiBase}/auth/admin/teacher/set-disabled`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ target_id: teacherId, is_disabled: isDisabled }),
    })
    const data = (await res.json()) as { ok?: boolean; detail?: string }
    if (!res.ok || !data.ok) {
      setError(toText(data.detail) || '更新教师状态失败。')
      return
    }
    setInfo(isDisabled ? `已禁用 ${teacherId}` : `已启用 ${teacherId}`)
    await refreshList()
  }

  const handleReset = async (teacherId: string) => {
    setError('')
    setInfo('')
    setTempPassword('')
    const res = await fetch(`${apiBase}/auth/admin/teacher/reset-password`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ target_id: teacherId }),
    })
    const data = (await res.json()) as ResetPasswordResponse & { detail?: string }
    if (!res.ok || !data.ok) {
      setError(toText(data.detail || data.error) || '重置密码失败。')
      return
    }
    setTempPassword(toText(data.temp_password))
    setInfo(`已重置 ${teacherId} 的密码。`)
  }

  return (
    <section
      className="h-full min-h-0 w-full min-w-[720px] overflow-auto bg-surface p-6"
      role="region"
      aria-label="学校管理"
    >
      <div className="grid gap-6 max-w-[960px]">
        <div className="grid gap-1">
          <div className="text-lg font-semibold">学校管理</div>
          <div className="text-sm text-muted">创建、列出、禁用教师，并重置临时密码。作业上传仍由教师账号完成。</div>
        </div>

        <form className="grid gap-3 rounded-2xl border border-border p-4" onSubmit={handleCreate}>
          <div className="text-sm font-semibold">创建教师</div>
          <div className="grid gap-1">
            <label className="text-xs text-muted" htmlFor={nameId}>教师姓名</label>
            <input id={nameId} value={nameInput} onChange={(event) => setNameInput(event.target.value)} autoComplete="name" />
          </div>
          <div className="grid gap-1">
            <label className="text-xs text-muted" htmlFor={emailId}>邮箱（可选）</label>
            <input id={emailId} value={emailInput} onChange={(event) => setEmailInput(event.target.value)} autoComplete="email" />
          </div>
          <div className="grid gap-1">
            <label className="text-xs text-muted" htmlFor={teacherIdField}>教师 ID（可选）</label>
            <input
              id={teacherIdField}
              value={teacherIdInput}
              onChange={(event) => setTeacherIdInput(event.target.value)}
              placeholder="省略则自动生成"
              autoComplete="off"
            />
          </div>
          <button type="submit" className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer w-fit" disabled={submitting}>
            {submitting ? '创建中…' : '创建教师'}
          </button>
        </form>

        {tempPassword ? <TempPasswordOnce password={tempPassword} /> : null}
        {error ? <div className="status err">{error}</div> : null}
        {info ? <div className="status ok">{info}</div> : null}

        <div className="grid gap-3 rounded-2xl border border-border p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold">教师列表</div>
            <button type="button" className="ghost" onClick={() => void refreshList()} disabled={loadingList}>
              {loadingList ? '刷新中…' : '刷新'}
            </button>
          </div>
          {items.length ? (
            <div className="grid gap-2">
              {items.map((item) => {
                const teacherId = toText(item.teacher_id)
                const disabled = Boolean(item.is_disabled)
                return (
                  <div key={teacherId} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                    <div className="grid gap-0.5 min-w-0">
                      <div className="text-sm font-medium">{toText(item.teacher_name) || teacherId}</div>
                      <div className="text-xs text-muted font-mono break-all">
                        {teacherId}
                        {item.email ? ` · ${toText(item.email)}` : ''}
                        {disabled ? ' · 已禁用' : ''}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button type="button" className="ghost" onClick={() => void handleDisable(teacherId, !disabled)}>
                        {disabled ? '启用' : '禁用'}
                      </button>
                      <button type="button" className="ghost" onClick={() => void handleReset(teacherId)}>
                        重置密码
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-xs text-muted">{loadingList ? '加载中…' : '暂无教师。'}</div>
          )}
        </div>
      </div>
    </section>
  )
}
