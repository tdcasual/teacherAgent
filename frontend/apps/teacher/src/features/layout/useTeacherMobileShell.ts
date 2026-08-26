import { useCallback, useEffect, useMemo, useState } from 'react'
import { readFeatureFlag } from '../../../../shared/featureFlags'
import { DESKTOP_BREAKPOINT, workbenchMaxWidthForViewport } from '../../teacherAppChrome'
import { isTeacherMobileTab, teacherMobilePanelsFromTab, type TeacherMobileTab } from './mobileShellState'

type BooleanSetter = (value: boolean | ((prev: boolean) => boolean)) => void

type UseTeacherMobileShellParams = {
  sessionSidebarOpen: boolean
  skillsOpen: boolean
  setSessionSidebarOpen: BooleanSetter
  setSkillsOpen: BooleanSetter
  setActiveSessionId: (value: string | ((prev: string) => string)) => void
  setSessionCursor: (value: number) => void
  setSessionHasMore: (value: boolean) => void
  setSessionError: (value: string) => void
  setOpenSessionMenuId: (value: string | ((prev: string) => string)) => void
}

export function useTeacherMobileShell(params: UseTeacherMobileShellParams) {
  const {
    sessionSidebarOpen,
    skillsOpen,
    setSessionSidebarOpen,
    setSkillsOpen,
    setActiveSessionId,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
  } = params
  const [viewportWidth, setViewportWidth] = useState(() => (typeof window !== 'undefined' ? window.innerWidth : 1280))
  const isMobileLayout = viewportWidth <= DESKTOP_BREAKPOINT
  const workbenchMaxWidth = workbenchMaxWidthForViewport(viewportWidth)
  const mobileShellV2Enabled = useMemo(() => {
    const source: Record<string, string | undefined> = {
      mobileShellV2: import.meta.env.VITE_MOBILE_SHELL_V2_TEACHER,
    }
    if (typeof window !== 'undefined') {
      try {
        const localOverride = window.localStorage.getItem('teacherMobileShellV2')
        if (localOverride != null) source.mobileShellV2 = localOverride
      } catch {
        // ignore localStorage read failures
      }
    }
    return readFeatureFlag('mobileShellV2', true, source)
  }, [])
  const teacherUseMobileShellV2 = mobileShellV2Enabled && isMobileLayout
  const [mobileTab, setMobileTab] = useState<TeacherMobileTab>('chat')

  const isMobileViewport = useCallback(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(max-width: 900px)').matches
  }, [])

  useEffect(() => {
    if (!teacherUseMobileShellV2) return
    const nextPanels = teacherMobilePanelsFromTab(mobileTab)
    if (sessionSidebarOpen !== nextPanels.sessionSidebarOpen) setSessionSidebarOpen(nextPanels.sessionSidebarOpen)
    if (skillsOpen !== nextPanels.skillsOpen) setSkillsOpen(nextPanels.skillsOpen)
  }, [teacherUseMobileShellV2, mobileTab, sessionSidebarOpen, skillsOpen, setSessionSidebarOpen, setSkillsOpen])

  const handleTeacherMobileTabChange = useCallback((tabId: string) => {
    if (!isTeacherMobileTab(tabId)) return
    setMobileTab(tabId)
  }, [])

  const handleSelectSessionFromSheet = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    setActiveSessionId(sid)
    setSessionCursor(-1)
    setSessionHasMore(false)
    setSessionError('')
    setOpenSessionMenuId('')
    setMobileTab('chat')
  }, [
    setActiveSessionId,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
  ])

  const handleTopbarSessionToggle = useCallback(() => {
    if (!teacherUseMobileShellV2) {
      setSessionSidebarOpen((prev) => {
        const next = !prev
        if (next && isMobileViewport()) setSkillsOpen(false)
        return next
      })
      return
    }
    setMobileTab((prev) => (prev === 'sessions' ? 'chat' : 'sessions'))
  }, [teacherUseMobileShellV2, isMobileViewport, setSessionSidebarOpen, setSkillsOpen])

  const handleTopbarWorkbenchToggle = useCallback(() => {
    if (!teacherUseMobileShellV2) {
      if (skillsOpen) {
        setSkillsOpen(false)
        return
      }
      setSkillsOpen(true)
      if (isMobileViewport()) setSessionSidebarOpen(false)
      return
    }
    setMobileTab((prev) => (prev === 'workbench' ? 'chat' : 'workbench'))
  }, [teacherUseMobileShellV2, skillsOpen, isMobileViewport, setSkillsOpen, setSessionSidebarOpen])

  return {
    viewportWidth,
    setViewportWidth,
    isMobileLayout,
    workbenchMaxWidth,
    mobileShellV2Enabled,
    teacherUseMobileShellV2,
    mobileTab,
    setMobileTab,
    isMobileViewport,
    handleTeacherMobileTabChange,
    handleSelectSessionFromSheet,
    handleTopbarSessionToggle,
    handleTopbarWorkbenchToggle,
  }
}
