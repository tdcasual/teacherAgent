import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Dispatch } from 'react'
import type { StudentPersonaCard, VerifiedStudent } from '../../appTypes'
import type { StudentAction } from '../../hooks/useStudentState'
import { validateAvatarFileBeforeUpload } from '../../../../shared/uploadValidation'
import { useDismissibleLayer } from '../../../../shared/useDismissibleLayer'

type Props = {
  apiBase: string
  verifiedStudent: VerifiedStudent | null
  sidebarOpen: boolean
  compactMobile?: boolean
  dispatch: Dispatch<StudentAction>
  startNewStudentSession: () => void
  personaEnabled: boolean
  personaPickerOpen: boolean
  personaCards: StudentPersonaCard[]
  activePersonaId: string
  personaLoading: boolean
  personaError: string
  onTogglePersonaEnabled: (next: boolean) => void
  onTogglePersonaPicker: () => void
  onSelectPersona: (personaId: string) => void
  onCreateCustomPersona: (payload: { name: string; summary: string; styleRules: string[]; examples: string[] }) => Promise<void>
  onUpdateCustomPersona: (personaId: string, payload: { name: string; summary: string; styleRules: string[]; examples: string[] }) => Promise<void>
  onUploadCustomPersonaAvatar: (personaId: string, file: File) => Promise<void>
}

export default function StudentTopbar({
  apiBase,
  verifiedStudent,
  sidebarOpen,
  compactMobile = false,
  dispatch,
  startNewStudentSession,
  personaEnabled,
  personaPickerOpen,
  personaCards,
  activePersonaId,
  personaLoading,
  personaError,
  onTogglePersonaEnabled,
  onTogglePersonaPicker,
  onSelectPersona,
  onCreateCustomPersona,
  onUpdateCustomPersona,
  onUploadCustomPersonaAvatar,
}: Props) {
  const pickerButtonRef = useRef<HTMLButtonElement | null>(null)
  const pickerPanelRef = useRef<HTMLDivElement | null>(null)
  const quickActionsButtonRef = useRef<HTMLButtonElement | null>(null)
  const quickActionsPanelRef = useRef<HTMLDivElement | null>(null)
  const activePersonaName = personaCards.find((item) => item.persona_id === activePersonaId)?.name || '未选择'
  const customPersonas = useMemo(
    () => personaCards.filter((item) => String(item.source || '') === 'student_custom'),
    [personaCards],
  )
  const [customName, setCustomName] = useState('')
  const [customSummary, setCustomSummary] = useState('')
  const [customRules, setCustomRules] = useState('先肯定后追问')
  const [customExamples, setCustomExamples] = useState('你这步很接近，我们再推进一步。')
  const [customEditId, setCustomEditId] = useState('')
  const [customLoading, setCustomLoading] = useState(false)
  const [customMsg, setCustomMsg] = useState('')
  const [quickActionsOpen, setQuickActionsOpen] = useState(false)
  const closePicker = useCallback(() => {
    dispatch({ type: 'SET', field: 'personaPickerOpen', value: false })
  }, [dispatch])
  const closeQuickActions = useCallback(() => {
    setQuickActionsOpen(false)
  }, [])
  const pickerLayerRefs = useMemo(
    () => [pickerPanelRef, pickerButtonRef] as const,
    [],
  )
  const quickActionsLayerRefs = useMemo(
    () => [quickActionsPanelRef, quickActionsButtonRef] as const,
    [],
  )

  const customTarget = customPersonas.find((item) => item.persona_id === customEditId) || null
  const parseLines = (value: string) =>
    value.split('\n').map((item) => item.trim()).filter(Boolean).slice(0, 20)

  useDismissibleLayer({
    open: personaPickerOpen,
    onDismiss: closePicker,
    refs: pickerLayerRefs,
  })

  useDismissibleLayer({
    open: quickActionsOpen,
    onDismiss: closeQuickActions,
    refs: quickActionsLayerRefs,
  })

  useEffect(() => {
    if (!compactMobile && quickActionsOpen) setQuickActionsOpen(false)
  }, [compactMobile, quickActionsOpen])

  useEffect(() => {
    if (personaPickerOpen && quickActionsOpen) setQuickActionsOpen(false)
  }, [personaPickerOpen, quickActionsOpen])

  const titleText = compactMobile ? '物理学习助手' : '物理学习助手 · 学生端'
  const sidebarLabel = compactMobile ? (sidebarOpen ? '会话开' : '会话') : (sidebarOpen ? '收起会话' : '展开会话')
  const newSessionLabel = compactMobile ? '新建' : '新会话'
  const personaEnabledLabel = compactMobile ? `角色${personaEnabled ? '开' : '关'}` : `角色卡：${personaEnabled ? '开' : '关'}`
  const personaPickerLabel = compactMobile ? (activePersonaId ? `角色：${activePersonaName}` : '角色') : (activePersonaId ? `已选：${activePersonaName}` : '选择角色卡')
  const personaEnabledMenuLabel = `角色卡：${personaEnabled ? '开' : '关'}`
  const personaPickerMenuLabel = activePersonaId ? `已选：${activePersonaName}` : '选择角色卡'

  return (
    <header className={`relative flex justify-between items-center gap-3 px-4 py-2.5 bg-white/94 border-b border-border backdrop-blur-[8px] backdrop-saturate-[180%] sticky top-0 z-25 max-[900px]:items-start max-[900px]:flex-wrap ${compactMobile ? 'max-[900px]:px-3 max-[900px]:py-2 max-[900px]:gap-2' : ''}`.trim()}>
      <div className={`flex items-center gap-2 flex-wrap max-[900px]:w-full max-[900px]:justify-between ${compactMobile ? 'max-[900px]:gap-1.5 max-[900px]:flex-nowrap' : ''}`.trim()}>
        <div className="flex items-center gap-2 min-w-0">
          {!compactMobile ? (
            <img
              src="/ai-entry-logo.png"
              alt="AI入口图标"
              className="w-[30px] h-[30px] object-contain shrink-0 select-none"
              draggable={false}
            />
          ) : null}
          <div className={`font-bold text-base tracking-[0.2px] max-[900px]:text-sm ${compactMobile ? 'max-[900px]:truncate' : ''}`.trim()}>{titleText}</div>
        </div>
        <button
          className="ghost"
          type="button"
          aria-expanded={sidebarOpen}
          aria-controls="student-session-sidebar"
          onClick={() => dispatch({ type: 'SET', field: 'sidebarOpen', value: !sidebarOpen })}
        >
          {sidebarLabel}
        </button>
        <button className="ghost" onClick={startNewStudentSession}>
          {newSessionLabel}
        </button>
        {compactMobile ? (
          <button
            ref={quickActionsButtonRef}
            className="ghost"
            type="button"
            aria-haspopup="menu"
            aria-expanded={quickActionsOpen}
            onClick={() => setQuickActionsOpen((prev) => !prev)}
          >
            更多
          </button>
        ) : null}
      </div>
      {!compactMobile ? (
        <div className="flex items-center gap-2 max-[900px]:w-full max-[900px]:justify-between relative">
          <button
            type="button"
            className="ghost"
            onClick={() => onTogglePersonaEnabled(!personaEnabled)}
            disabled={!verifiedStudent || personaLoading}
            aria-pressed={personaEnabled}
          >
            {personaEnabledLabel}
          </button>
          <button
            ref={pickerButtonRef}
            type="button"
            className="ghost"
            onClick={onTogglePersonaPicker}
            aria-haspopup="dialog"
            aria-expanded={personaPickerOpen}
            disabled={!verifiedStudent || !personaEnabled || personaLoading}
          >
            {personaPickerLabel}
          </button>
          <div className="role-badge student">身份：学生</div>
          {verifiedStudent?.student_id ? (
            <span className="muted">
              当前学生：{verifiedStudent.student_id}
            </span>
          ) : null}
        </div>
      ) : null}
      {compactMobile && quickActionsOpen ? (
        <div
          ref={quickActionsPanelRef}
          className="absolute right-0 top-[calc(100%+8px)] z-40 min-w-[188px] rounded-xl border border-border bg-white p-2 shadow-[0_12px_28px_rgba(15,23,42,0.14)] grid gap-1"
          role="menu"
          aria-label="移动端更多操作"
        >
          <button
            type="button"
            className="ghost justify-start"
            onClick={() => {
              onTogglePersonaEnabled(!personaEnabled)
              setQuickActionsOpen(false)
            }}
            disabled={!verifiedStudent || personaLoading}
            aria-pressed={personaEnabled}
          >
            {personaEnabledMenuLabel}
          </button>
          <button
            ref={pickerButtonRef}
            type="button"
            className="ghost justify-start"
            onClick={() => {
              onTogglePersonaPicker()
              setQuickActionsOpen(false)
            }}
            aria-haspopup="dialog"
            aria-expanded={personaPickerOpen}
            disabled={!verifiedStudent || !personaEnabled || personaLoading}
          >
            {personaPickerMenuLabel}
          </button>
          {verifiedStudent?.student_id ? (
            <div className="text-[12px] text-muted px-1 py-0.5">当前学生：{verifiedStudent.student_id}</div>
          ) : null}
        </div>
      ) : null}
      {personaPickerOpen ? (
        <div
          ref={pickerPanelRef}
          className="absolute right-0 top-[calc(100%+8px)] w-[300px] max-h-[320px] overflow-auto rounded-xl border border-border bg-white shadow-[0_12px_28px_rgba(15,23,42,0.14)] p-2 z-40"
          role="dialog"
          aria-label="角色卡选择"
        >
            {personaError ? <div className="text-[12px] text-[#b91c1c] px-2 py-1">{personaError}</div> : null}
            {!personaCards.length ? <div className="text-[12px] text-muted px-2 py-2">暂无可用角色卡</div> : null}
            {personaCards.map((item) => (
              <button
                key={item.persona_id}
                type="button"
                className={`w-full text-left rounded-lg border px-2.5 py-2 mb-1 transition-colors ${
                  item.persona_id === activePersonaId ? 'border-accent bg-[#f0f9ff]' : 'border-border bg-white hover:bg-[#f8fafc]'
                }`}
                onClick={() => onSelectPersona(item.persona_id)}
              >
                <div className="flex items-start gap-2">
                  {item.avatar_url ? (
                    <img
                      src={item.avatar_url.startsWith('http') ? item.avatar_url : `${apiBase}${item.avatar_url}`}
                      alt={item.name || item.persona_id}
                      className="w-8 h-8 rounded-full object-cover border border-border shrink-0"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full border border-border bg-surface-soft shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold leading-tight truncate">{item.name || item.persona_id}</div>
                    <div className="text-[12px] text-muted mt-0.5 leading-tight">{item.summary || '风格卡'}</div>
                  </div>
                </div>
              </button>
            ))}
            <div className="h-px bg-border my-2" />
            <div className="text-[12px] font-semibold text-[#334155] px-1 pb-1">自定义角色</div>
            <input
              className="w-full rounded-lg border border-border px-2.5 py-2 text-[12px] mb-1"
              placeholder="角色名称"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
            />
            <input
              className="w-full rounded-lg border border-border px-2.5 py-2 text-[12px] mb-1"
              placeholder="角色摘要"
              value={customSummary}
              onChange={(e) => setCustomSummary(e.target.value)}
            />
            <textarea
              className="w-full rounded-lg border border-border px-2.5 py-2 text-[12px] min-h-[56px] mb-1"
              placeholder="风格规则（每行一条）"
              value={customRules}
              onChange={(e) => setCustomRules(e.target.value)}
            />
            <textarea
              className="w-full rounded-lg border border-border px-2.5 py-2 text-[12px] min-h-[56px] mb-1"
              placeholder="示例（每行一条）"
              value={customExamples}
              onChange={(e) => setCustomExamples(e.target.value)}
            />
            <button
              type="button"
              className="w-full rounded-lg border border-border bg-white px-2.5 py-2 text-[12px] hover:bg-surface-soft disabled:opacity-60"
              disabled={customLoading}
              onClick={async () => {
                const name = customName.trim()
                const styleRules = parseLines(customRules)
                const examples = parseLines(customExamples).slice(0, 5)
                if (!name || !styleRules.length || !examples.length) {
                  setCustomMsg('请完整填写名称/规则/示例')
                  return
                }
                setCustomLoading(true)
                setCustomMsg('')
                try {
                  await onCreateCustomPersona({ name, summary: customSummary.trim(), styleRules, examples })
                  setCustomMsg('创建成功')
                  setCustomName('')
                } catch (err) {
                  setCustomMsg(String((err as Error)?.message || err || '创建失败'))
                } finally {
                  setCustomLoading(false)
                }
              }}
            >
              创建自定义角色
            </button>
            <select
              className="w-full rounded-lg border border-border px-2.5 py-2 text-[12px] my-1"
              value={customEditId}
              onChange={(e) => {
                const nextId = e.target.value
                setCustomEditId(nextId)
                const next = customPersonas.find((item) => item.persona_id === nextId)
                if (!next) return
                setCustomName(String(next.name || ''))
                setCustomSummary(String(next.summary || ''))
                setCustomRules(Array.isArray(next.style_rules) ? next.style_rules.join('\n') : '')
                setCustomExamples(Array.isArray(next.few_shot_examples) ? next.few_shot_examples.join('\n') : '')
              }}
            >
              <option value="">选择要编辑的自定义角色</option>
              {customPersonas.map((item) => (
                <option key={item.persona_id} value={item.persona_id}>
                  {item.name || item.persona_id}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="w-full rounded-lg border border-border bg-white px-2.5 py-2 text-[12px] hover:bg-surface-soft disabled:opacity-60"
              disabled={customLoading || !customEditId}
              onClick={async () => {
                if (!customEditId) return
                const name = customName.trim()
                const styleRules = parseLines(customRules)
                const examples = parseLines(customExamples).slice(0, 5)
                if (!name || !styleRules.length || !examples.length) {
                  setCustomMsg('请完整填写名称/规则/示例')
                  return
                }
                setCustomLoading(true)
                setCustomMsg('')
                try {
                  await onUpdateCustomPersona(customEditId, { name, summary: customSummary.trim(), styleRules, examples })
                  setCustomMsg('更新成功')
                } catch (err) {
                  setCustomMsg(String((err as Error)?.message || err || '更新失败'))
                } finally {
                  setCustomLoading(false)
                }
              }}
            >
              更新自定义角色
            </button>
            <input
              type="file"
              accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
              className="w-full rounded-lg border border-border px-2.5 py-2 text-[12px] mt-1"
              disabled={!customEditId || customLoading}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (!file || !customEditId) return
                const avatarError = validateAvatarFileBeforeUpload(file)
                if (avatarError) {
                  setCustomMsg(avatarError)
                  e.currentTarget.value = ''
                  return
                }
                setCustomLoading(true)
                setCustomMsg('')
                void onUploadCustomPersonaAvatar(customEditId, file)
                  .then(() => setCustomMsg('头像上传成功'))
                  .catch((err) => setCustomMsg(String((err as Error)?.message || err || '头像上传失败')))
                  .finally(() => setCustomLoading(false))
              }}
            />
            {customTarget?.avatar_url ? (
              <img
                src={customTarget.avatar_url.startsWith('http') ? customTarget.avatar_url : `${apiBase}${customTarget.avatar_url}`}
                alt={customTarget.name || customTarget.persona_id}
                className="w-10 h-10 rounded-full object-cover border border-border mt-1"
              />
            ) : null}
            {customMsg ? <div className="text-[12px] text-muted mt-1">{customMsg}</div> : null}
        </div>
      ) : null}
    </header>
  )
}
