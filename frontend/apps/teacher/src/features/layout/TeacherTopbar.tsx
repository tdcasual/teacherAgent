import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { MutableRefObject } from 'react'

import { useDismissibleLayer } from '../../../../shared/useDismissibleLayer'
import {
  TEACHER_AUTH_EVENT,
  readTeacherAccessToken,
  readTeacherAuthSubject,
} from '../auth/teacherAuth'
import TeacherTopbarAdminMenu from './TeacherTopbarAdminMenu'
import TeacherTopbarOverflowMenu from './TeacherTopbarOverflowMenu'

type TeacherTopbarProps = {
  topbarRef: MutableRefObject<HTMLElement | null>
  sessionSidebarOpen: boolean
  skillsOpen: boolean
  compactMobile?: boolean
  onToggleSessionSidebar: () => void
  onOpenModelSettingsPanel: () => void
  onToggleSkillsWorkbench: () => void
  onToggleSettingsPanel: () => void
}

export default function TeacherTopbar({
  topbarRef,
  sessionSidebarOpen,
  skillsOpen,
  compactMobile = false,
  onToggleSessionSidebar,
  onOpenModelSettingsPanel,
  onToggleSkillsWorkbench,
  onToggleSettingsPanel,
}: TeacherTopbarProps) {
  const authButtonRef = useRef<HTMLButtonElement | null>(null)
  const authPanelRef = useRef<HTMLDivElement | null>(null)
  const [authOpen, setAuthOpen] = useState(false)
  const [authed, setAuthed] = useState(() => Boolean(readTeacherAccessToken()))
  const [authSubjectLabel, setAuthSubjectLabel] = useState(() => {
    const subject = readTeacherAuthSubject()
    return subject?.teacher_name || subject?.teacher_id || ''
  })
  const closeAuthPanel = useCallback(() => setAuthOpen(false), [])
  const toggleAuthPanel = useCallback(() => setAuthOpen((prev) => !prev), [])
  const authLayerRefs = useMemo(
    () => [authPanelRef, authButtonRef] as const,
    [],
  )

  useEffect(() => {
    const sync = () => {
      const hasToken = Boolean(readTeacherAccessToken())
      setAuthed(hasToken)
      const subject = readTeacherAuthSubject()
      setAuthSubjectLabel(subject?.teacher_name || subject?.teacher_id || '')
    }
    sync()
    window.addEventListener('storage', sync)
    window.addEventListener(TEACHER_AUTH_EVENT, sync as EventListener)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener(TEACHER_AUTH_EVENT, sync as EventListener)
    }
  }, [compactMobile])

  useDismissibleLayer({
    open: authOpen,
    onDismiss: closeAuthPanel,
    refs: authLayerRefs,
  })

  const authActionLabel = '管理'

  return (
    <header
      ref={topbarRef}
      className={`mobile-topbar flex justify-between items-center gap-[12px] px-4 py-[10px] bg-surface border-b border-border sticky top-0 z-[25] ${compactMobile ? 'mobile-topbar-compact max-[900px]:px-3 max-[900px]:py-2 max-[900px]:gap-2' : ''}`.trim()}
    >
      <div className={`flex items-center gap-[10px] flex-wrap ${compactMobile ? 'max-[900px]:gap-2 max-[900px]:flex-nowrap' : ''}`.trim()}>
        <div className="flex items-center gap-2 min-w-0">
          {!compactMobile ? (
            <img
              src="/ai-entry-logo.png"
              alt="AI入口图标"
              className="w-[30px] h-[30px] object-contain shrink-0 select-none"
              draggable={false}
            />
          ) : null}
          <div className={`mobile-topbar-title font-bold text-[16px] tracking-[0.2px] ${compactMobile ? 'max-[900px]:text-[14px] max-[900px]:truncate' : ''}`.trim()}>
            {compactMobile ? '教学助手' : '教学助手 · 老师端'}
          </div>
        </div>
        <button className="ghost" type="button" onClick={onToggleSessionSidebar}>
          {compactMobile ? (sessionSidebarOpen ? '会话开' : '会话') : sessionSidebarOpen ? '收起会话' : '展开会话'}
        </button>
      </div>
      <div className={`flex gap-[10px] items-center flex-wrap relative ${compactMobile ? 'max-[900px]:gap-2 max-[900px]:flex-nowrap' : ''}`.trim()}>
        <div className={`role-badge teacher ${compactMobile ? 'max-[900px]:hidden' : ''}`.trim()}>身份：老师</div>
        {authed ? <span className={`text-xs text-muted ${compactMobile ? 'max-[900px]:hidden' : ''}`.trim()}>已认证：{authSubjectLabel || '教师'}</span> : null}
        {!compactMobile ? (
          <button
            ref={authButtonRef}
            className="ghost"
            type="button"
            onClick={toggleAuthPanel}
            aria-haspopup="true"
            aria-expanded={authOpen}
          >
            {authActionLabel}
          </button>
        ) : null}
        {compactMobile ? (
          <TeacherTopbarOverflowMenu
            skillsOpen={skillsOpen}
            authOpen={authOpen}
            authButtonRef={authButtonRef}
            onToggleAuth={toggleAuthPanel}
            onToggleSkillsWorkbench={onToggleSkillsWorkbench}
            onToggleSettingsPanel={onToggleSettingsPanel}
          />
        ) : (
          <>
            <button className="ghost" type="button" onClick={onToggleSkillsWorkbench}>
              {skillsOpen ? '收起工作台' : '打开工作台'}
            </button>
            <button
              className="ghost border-none bg-transparent cursor-pointer min-h-[44px] min-w-[44px] p-2 rounded-lg text-muted transition-[background] duration-150 ease-in-out hover:bg-surface-soft [&_svg]:block"
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
          </>
        )}

        <TeacherTopbarAdminMenu
          open={authOpen}
          panelRef={authPanelRef}
          authed={authed}
          authSubjectLabel={authSubjectLabel}
          onOpenModelSettingsPanel={onOpenModelSettingsPanel}
          onClose={closeAuthPanel}
        />
      </div>
    </header>
  )
}
