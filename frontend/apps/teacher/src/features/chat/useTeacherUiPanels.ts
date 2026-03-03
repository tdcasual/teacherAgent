import { useCallback } from 'react'

type UseTeacherUiPanelsParams = {
  skillsOpen: boolean
  setSkillsOpen: (value: boolean | ((prev: boolean) => boolean)) => void
  setSessionSidebarOpen: (value: boolean | ((prev: boolean) => boolean)) => void
  isMobileViewport: () => boolean
  settingsOpen: boolean
  setSettingsOpen: (value: boolean) => void
}

export function useTeacherUiPanels(params: UseTeacherUiPanelsParams) {
  const {
    skillsOpen,
    setSkillsOpen,
    setSessionSidebarOpen,
    isMobileViewport,
    settingsOpen,
    setSettingsOpen,
  } = params

  const toggleSkillsWorkbench = useCallback(() => {
    if (skillsOpen) {
      setSkillsOpen(false)
      return
    }
    setSkillsOpen(true)
    if (isMobileViewport()) setSessionSidebarOpen(false)
  }, [isMobileViewport, setSessionSidebarOpen, setSkillsOpen, skillsOpen])

  const requestCloseSettings = useCallback(() => {
    setSettingsOpen(false)
  }, [setSettingsOpen])

  const toggleSettingsPanel = useCallback(() => {
    if (settingsOpen) {
      requestCloseSettings()
      return
    }
    setSettingsOpen(true)
  }, [requestCloseSettings, setSettingsOpen, settingsOpen])

  const openModelSettingsPanel = useCallback(() => {
    setSettingsOpen(true)
  }, [setSettingsOpen])

  return {
    toggleSkillsWorkbench,
    requestCloseSettings,
    toggleSettingsPanel,
    openModelSettingsPanel,
  }
}
