import type { Dispatch } from 'react'
import type { StudentPersonaCard, VerifiedStudent } from '../../appTypes'
import type { StudentAction } from '../../hooks/useStudentState'

type Props = {
  verifiedStudent: VerifiedStudent | null
  sidebarOpen: boolean
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
}

export default function StudentTopbar({
  verifiedStudent,
  sidebarOpen,
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
}: Props) {
  const activePersonaName = personaCards.find((item) => item.persona_id === activePersonaId)?.name || '未选择'

  return (
    <header className="relative flex justify-between items-center gap-3 px-4 py-2.5 bg-white/94 border-b border-border backdrop-blur-[8px] backdrop-saturate-[180%] sticky top-0 z-25 max-[900px]:items-start max-[900px]:flex-wrap">
      <div className="flex items-center gap-2 flex-wrap max-[900px]:w-full max-[900px]:justify-between">
        <div className="font-bold text-base tracking-[0.2px] max-[900px]:text-sm">物理学习助手 · 学生端</div>
        <button
          className="ghost"
          type="button"
          aria-expanded={sidebarOpen}
          aria-controls="student-session-sidebar"
          onClick={() => dispatch({ type: 'SET', field: 'sidebarOpen', value: !sidebarOpen })}
        >
          {sidebarOpen ? '收起会话' : '展开会话'}
        </button>
        <button className="ghost" onClick={startNewStudentSession}>
          新会话
        </button>
      </div>
      <div className="flex items-center gap-2 max-[900px]:w-full max-[900px]:justify-between relative">
        <button
          type="button"
          className="ghost"
          onClick={() => onTogglePersonaEnabled(!personaEnabled)}
          disabled={!verifiedStudent || personaLoading}
          aria-pressed={personaEnabled}
        >
          角色卡：{personaEnabled ? '开' : '关'}
        </button>
        <button
          type="button"
          className="ghost"
          onClick={onTogglePersonaPicker}
          disabled={!verifiedStudent || !personaEnabled || personaLoading}
        >
          {activePersonaId ? `已选：${activePersonaName}` : '选择角色卡'}
        </button>
        <div className="role-badge student">身份：学生</div>
        {verifiedStudent?.student_id ? (
          <span className="muted">
            当前学生：{verifiedStudent.student_id}
          </span>
        ) : null}
        {personaPickerOpen ? (
          <div className="absolute right-0 top-[calc(100%+8px)] w-[300px] max-h-[320px] overflow-auto rounded-xl border border-border bg-white shadow-[0_12px_28px_rgba(15,23,42,0.14)] p-2 z-40">
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
                <div className="text-[13px] font-semibold leading-tight">{item.name || item.persona_id}</div>
                <div className="text-[12px] text-muted mt-0.5 leading-tight">{item.summary || '风格卡'}</div>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </header>
  )
}
