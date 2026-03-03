import { useCallback, useMemo, useRef, useState } from 'react'
import type { Dispatch } from 'react'
import type { VerifiedStudent } from '../../appTypes'
import type { StudentAction } from '../../hooks/useStudentState'
import { useDismissibleLayer } from '../../../../shared/useDismissibleLayer'

type Props = {
  verifiedStudent: VerifiedStudent | null
  sidebarOpen: boolean
  compactMobile?: boolean
  dispatch: Dispatch<StudentAction>
  startNewStudentSession: () => void
}

export default function StudentTopbar({
  verifiedStudent,
  sidebarOpen,
  compactMobile = false,
  dispatch,
  startNewStudentSession,
}: Props) {
  const quickActionsButtonRef = useRef<HTMLButtonElement | null>(null)
  const quickActionsPanelRef = useRef<HTMLDivElement | null>(null)
  const [quickActionsOpen, setQuickActionsOpen] = useState(false)
  const closeQuickActions = useCallback(() => {
    setQuickActionsOpen(false)
  }, [])
  const quickActionsLayerRefs = useMemo(
    () => [quickActionsPanelRef, quickActionsButtonRef] as const,
    [],
  )

  useDismissibleLayer({
    open: quickActionsOpen,
    onDismiss: closeQuickActions,
    refs: quickActionsLayerRefs,
  })

  const titleText = compactMobile ? '物理学习助手' : '物理学习助手 · 学生端'
  const sidebarLabel = compactMobile ? (sidebarOpen ? '会话开' : '会话') : (sidebarOpen ? '收起会话' : '展开会话')
  const newSessionLabel = compactMobile ? '新建' : '新会话'

  return (
    <header className={`mobile-topbar relative flex justify-between items-center gap-3 px-4 py-2.5 bg-white/94 border-b border-border backdrop-blur-[8px] backdrop-saturate-[180%] sticky top-0 z-25 max-[900px]:items-start max-[900px]:flex-wrap ${compactMobile ? 'mobile-topbar-compact max-[900px]:px-3 max-[900px]:py-2 max-[900px]:gap-2' : ''}`.trim()}>
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
          <div className={`mobile-topbar-title font-bold text-base tracking-[0.2px] max-[900px]:text-sm ${compactMobile ? 'max-[900px]:truncate' : ''}`.trim()}>{titleText}</div>
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
          {verifiedStudent?.student_id ? (
            <div className="text-[12px] text-muted px-1 py-0.5">当前学生：{verifiedStudent.student_id}</div>
          ) : (
            <div className="text-[12px] text-muted px-1 py-0.5">未验证学生身份</div>
          )}
        </div>
      ) : null}
    </header>
  )
}
