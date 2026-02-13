import { useCallback, useEffect, useMemo, useState } from 'react'
import type { TeacherPersona } from '../../appTypes'
import { toUserFacingErrorMessage } from '../../../../shared/errorMessage'
import {
  assignTeacherPersona,
  createTeacherPersona,
  fetchTeacherPersonas,
  setTeacherPersonaVisibility,
  uploadTeacherPersonaAvatar,
  updateTeacherPersona,
} from './personaApi'

type Props = {
  open: boolean
  onClose: () => void
  apiBase: string
}

const toLines = (value: string) =>
  value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 20)

const toErrorMessage = (error: unknown, fallback: string) => {
  return toUserFacingErrorMessage(error, fallback)
}

export default function TeacherPersonaManager({ open, onClose, apiBase }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [personas, setPersonas] = useState<TeacherPersona[]>([])
  const [selectedPersonaId, setSelectedPersonaId] = useState('')
  const [name, setName] = useState('')
  const [summary, setSummary] = useState('')
  const [styleRulesText, setStyleRulesText] = useState('先肯定后追问')
  const [examplesText, setExamplesText] = useState('你这一步很接近了，我们再看下一步。')
  const [assignStudentId, setAssignStudentId] = useState('')
  const [assignStatus, setAssignStatus] = useState<'active' | 'inactive'>('active')
  const [visibilityMode, setVisibilityMode] = useState<'assigned_only' | 'hidden_all'>('assigned_only')
  const [avatarFile, setAvatarFile] = useState<File | null>(null)

  const selectedPersona = useMemo(
    () => personas.find((item) => item.persona_id === selectedPersonaId) || null,
    [personas, selectedPersonaId],
  )

  const refresh = useCallback(async () => {
    if (!open) return
    setLoading(true)
    setError('')
    try {
      const data = await fetchTeacherPersonas(apiBase)
      setPersonas(Array.isArray(data.personas) ? data.personas : [])
      const firstId = String(data.personas?.[0]?.persona_id || '')
      setSelectedPersonaId((prev) => prev || firstId)
    } catch (err) {
      setError(toErrorMessage(err, '加载角色失败'))
    } finally {
      setLoading(false)
    }
  }, [apiBase, open])

  useEffect(() => {
    if (!open) return
    void refresh()
  }, [open, refresh])

  useEffect(() => {
    if (!selectedPersona) return
    setSummary(String(selectedPersona.summary || ''))
    const mode = String(selectedPersona.visibility_mode || 'assigned_only').toLowerCase()
    setVisibilityMode(mode === 'hidden_all' ? 'hidden_all' : 'assigned_only')
  }, [selectedPersona?.persona_id])

  const handleCreate = useCallback(async () => {
    const trimmedName = name.trim()
    if (!trimmedName) {
      setError('请先输入角色名称')
      return
    }
    const rules = toLines(styleRulesText)
    const examples = toLines(examplesText).slice(0, 5)
    if (!rules.length || !examples.length) {
      setError('请至少填写一条规则和一条例句')
      return
    }
    setLoading(true)
    setError('')
    setStatus('')
    try {
      await createTeacherPersona(apiBase, {
        name: trimmedName,
        summary: summary.trim(),
        style_rules: rules,
        few_shot_examples: examples,
        visibility_mode: visibilityMode,
      })
      setStatus('角色创建成功')
      setName('')
      await refresh()
    } catch (err) {
      setError(toErrorMessage(err, '创建角色失败'))
    } finally {
      setLoading(false)
    }
  }, [apiBase, examplesText, name, refresh, styleRulesText, summary, visibilityMode])

  const handleUpdateSummary = useCallback(async () => {
    if (!selectedPersonaId) return
    setLoading(true)
    setError('')
    setStatus('')
    try {
      await updateTeacherPersona(apiBase, selectedPersonaId, { summary: summary.trim() })
      setStatus('摘要已更新')
      await refresh()
    } catch (err) {
      setError(toErrorMessage(err, '更新摘要失败'))
    } finally {
      setLoading(false)
    }
  }, [apiBase, refresh, selectedPersonaId, summary])

  const handleAssign = useCallback(async () => {
    const sid = assignStudentId.trim()
    if (!selectedPersonaId || !sid) {
      setError('请先选择角色并填写 student_id')
      return
    }
    setLoading(true)
    setError('')
    setStatus('')
    try {
      await assignTeacherPersona(apiBase, selectedPersonaId, { student_id: sid, status: assignStatus })
      setStatus(`已为 ${sid} 设置指派状态：${assignStatus}`)
    } catch (err) {
      setError(toErrorMessage(err, '指派失败'))
    } finally {
      setLoading(false)
    }
  }, [apiBase, assignStatus, assignStudentId, selectedPersonaId])

  const handleVisibility = useCallback(async () => {
    if (!selectedPersonaId) {
      setError('请先选择角色')
      return
    }
    setLoading(true)
    setError('')
    setStatus('')
    try {
      await setTeacherPersonaVisibility(apiBase, selectedPersonaId, visibilityMode)
      setStatus(`可见性已更新为：${visibilityMode}`)
      await refresh()
    } catch (err) {
      setError(toErrorMessage(err, '更新可见性失败'))
    } finally {
      setLoading(false)
    }
  }, [apiBase, refresh, selectedPersonaId, visibilityMode])

  const handleAvatarUpload = useCallback(async () => {
    if (!selectedPersonaId || !avatarFile) {
      setError('请先选择角色并选择图片')
      return
    }
    setLoading(true)
    setError('')
    setStatus('')
    try {
      await uploadTeacherPersonaAvatar(apiBase, selectedPersonaId, avatarFile)
      setStatus('头像上传成功')
      setAvatarFile(null)
      await refresh()
    } catch (err) {
      setError(toErrorMessage(err, '头像上传失败'))
    } finally {
      setLoading(false)
    }
  }, [apiBase, avatarFile, refresh, selectedPersonaId])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-100 bg-black/50 backdrop-blur-sm flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-label="角色管理"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="bg-surface rounded-[12px] shadow-[0_16px_48px_rgba(0,0,0,0.16)] flex flex-col overflow-hidden w-[min(960px,94vw)] h-[min(720px,88vh)]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="m-0 text-base font-semibold">角色管理</h2>
          <button className="ghost" type="button" onClick={onClose}>关闭</button>
        </div>
        <div className="px-5 py-2 text-[12px] text-muted border-b border-border">
          角色只影响表达风格，不影响事实正确性与教学约束。
        </div>
        <div className="flex-1 min-h-0 grid grid-cols-[280px_minmax(0,1fr)] max-[900px]:grid-cols-1">
          <div className="border-r border-border overflow-auto p-3 max-[900px]:border-r-0 max-[900px]:border-b">
            <div className="text-[13px] font-semibold mb-2">角色列表</div>
            {loading ? <div className="text-[12px] text-muted">加载中...</div> : null}
            {!loading && !personas.length ? <div className="text-[12px] text-muted">暂无角色</div> : null}
            {personas.map((item) => (
              <button
                key={item.persona_id}
                type="button"
                className={`w-full text-left rounded-lg border px-2.5 py-2 mb-1 ${
                  item.persona_id === selectedPersonaId ? 'border-accent bg-[#f0f9ff]' : 'border-border bg-white hover:bg-surface-soft'
                }`}
                onClick={() => setSelectedPersonaId(item.persona_id)}
              >
                <div className="flex items-start gap-2">
                  {item.avatar_url ? (
                    <img
                      src={`${apiBase}${item.avatar_url}`}
                      alt={item.name || item.persona_id}
                      className="w-8 h-8 rounded-full object-cover border border-border shrink-0"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full border border-border bg-surface-soft shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold truncate">{item.name || item.persona_id}</div>
                    <div className="text-[12px] text-muted line-clamp-2">{item.summary || '未填写摘要'}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
          <div className="overflow-auto p-4">
            <div className="text-[13px] font-semibold mb-2">新建角色</div>
            <div className="grid gap-2 mb-4">
              <input className="rounded-lg border border-border px-3 py-2 text-[13px]" value={name} onChange={(e) => setName(e.target.value)} placeholder="角色名称" />
              <input className="rounded-lg border border-border px-3 py-2 text-[13px]" value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="角色摘要" />
              <textarea className="rounded-lg border border-border px-3 py-2 text-[13px] min-h-[72px]" value={styleRulesText} onChange={(e) => setStyleRulesText(e.target.value)} placeholder="风格规则（每行一条）" />
              <textarea className="rounded-lg border border-border px-3 py-2 text-[13px] min-h-[72px]" value={examplesText} onChange={(e) => setExamplesText(e.target.value)} placeholder="风格例句（每行一条）" />
              <select className="rounded-lg border border-border px-3 py-2 text-[13px]" value={visibilityMode} onChange={(e) => setVisibilityMode(e.target.value === 'hidden_all' ? 'hidden_all' : 'assigned_only')}>
                <option value="assigned_only">仅指派可见</option>
                <option value="hidden_all">全部隐藏</option>
              </select>
              <button className="ghost w-fit" type="button" onClick={() => void handleCreate()} disabled={loading}>创建角色</button>
            </div>

            <div className="text-[13px] font-semibold mb-2">编辑/指派（当前选中）</div>
            <div className="grid gap-2">
              <div className="text-[12px] text-muted">当前角色 ID：{selectedPersonaId || '未选择'}</div>
              {selectedPersona?.avatar_url ? (
                <img
                  src={`${apiBase}${selectedPersona.avatar_url}`}
                  alt={selectedPersona.name || selectedPersona.persona_id || 'avatar'}
                  className="w-14 h-14 rounded-full object-cover border border-border"
                />
              ) : null}
              <input className="rounded-lg border border-border px-3 py-2 text-[13px]" value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="更新摘要" />
              <button className="ghost w-fit" type="button" onClick={() => void handleUpdateSummary()} disabled={loading || !selectedPersonaId}>更新摘要</button>
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
                className="rounded-lg border border-border px-3 py-2 text-[13px]"
                onChange={(e) => {
                  const file = e.target.files?.[0] || null
                  setAvatarFile(file)
                }}
              />
              <button className="ghost w-fit" type="button" onClick={() => void handleAvatarUpload()} disabled={loading || !selectedPersonaId || !avatarFile}>上传头像</button>
              <div className="h-px bg-border my-1" />
              <input className="rounded-lg border border-border px-3 py-2 text-[13px]" value={assignStudentId} onChange={(e) => setAssignStudentId(e.target.value)} placeholder="student_id（精确指派）" />
              <select className="rounded-lg border border-border px-3 py-2 text-[13px]" value={assignStatus} onChange={(e) => setAssignStatus(e.target.value === 'inactive' ? 'inactive' : 'active')}>
                <option value="active">active</option>
                <option value="inactive">inactive</option>
              </select>
              <button className="ghost w-fit" type="button" onClick={() => void handleAssign()} disabled={loading || !selectedPersonaId}>提交指派</button>
              <div className="h-px bg-border my-1" />
              <select className="rounded-lg border border-border px-3 py-2 text-[13px]" value={visibilityMode} onChange={(e) => setVisibilityMode(e.target.value === 'hidden_all' ? 'hidden_all' : 'assigned_only')}>
                <option value="assigned_only">assigned_only</option>
                <option value="hidden_all">hidden_all</option>
              </select>
              <button className="ghost w-fit" type="button" onClick={() => void handleVisibility()} disabled={loading || !selectedPersonaId}>更新可见性</button>
              {error ? <div className="text-[12px] text-[#b91c1c]">{error}</div> : null}
              {status ? <div className="text-[12px] text-[#0f766e]">{status}</div> : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
