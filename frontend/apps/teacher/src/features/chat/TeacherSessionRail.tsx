import { useCallback, type ComponentProps } from 'react'
import SessionSidebar from './SessionSidebar'

type SessionSidebarProps = ComponentProps<typeof SessionSidebar>

type TeacherSessionRailProps = Omit<SessionSidebarProps, 'open' | 'onSelectSession'> & {
  sessionSidebarOpen: boolean
  skillsOpen: boolean
  setSessionSidebarOpen: (value: boolean) => void
  setSkillsOpen: (value: boolean) => void
  setActiveSessionId: (value: string) => void
  setSessionCursor: (value: number) => void
  setSessionHasMore: (value: boolean) => void
  setSessionError: (value: string) => void
  setOpenSessionMenuId: (value: string) => void
  closeSessionSidebarOnMobile: () => void
}

export default function TeacherSessionRail({
  sessionSidebarOpen,
  skillsOpen,
  setSessionSidebarOpen,
  setSkillsOpen,
  setActiveSessionId,
  setSessionCursor,
  setSessionHasMore,
  setSessionError,
  setOpenSessionMenuId,
  closeSessionSidebarOnMobile,
  ...sessionSidebarProps
}: TeacherSessionRailProps) {
  const handleSelectSession = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId)
    setSessionCursor(-1)
    setSessionHasMore(false)
    setSessionError('')
    setOpenSessionMenuId('')
    closeSessionSidebarOnMobile()
  }, [
    closeSessionSidebarOnMobile,
    setActiveSessionId,
    setOpenSessionMenuId,
    setSessionCursor,
    setSessionError,
    setSessionHasMore,
  ])

  return (
    <>
      <button
        type="button"
        className={`hidden max-[900px]:block max-[900px]:fixed max-[900px]:inset-0 max-[900px]:z-[15] max-[900px]:bg-black/[0.15] max-[900px]:transition-opacity max-[900px]:duration-200 max-[900px]:ease-in-out ${sessionSidebarOpen || skillsOpen ? 'max-[900px]:opacity-100 max-[900px]:pointer-events-auto' : 'max-[900px]:opacity-0 max-[900px]:pointer-events-none'}`}
        aria-label="关闭侧边栏"
        onClick={() => {
          setSessionSidebarOpen(false)
          setSkillsOpen(false)
        }}
      />
      <SessionSidebar
        {...sessionSidebarProps}
        open={sessionSidebarOpen}
        onSelectSession={handleSelectSession}
      />
    </>
  )
}
