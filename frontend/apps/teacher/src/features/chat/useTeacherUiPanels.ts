import { useCallback } from 'react'
import type { RoutingSection } from '../routing/RoutingPage'

type UseTeacherUiPanelsParams = {
  skillsOpen: boolean
  setSkillsOpen: (value: boolean | ((prev: boolean) => boolean)) => void
  setSessionSidebarOpen: (value: boolean | ((prev: boolean) => boolean)) => void
  isMobileViewport: () => boolean
  settingsHasUnsavedDraft: boolean
  settingsOpen: boolean
  setSettingsOpen: (value: boolean) => void
  setSettingsLegacyFlat: (value: boolean) => void
  setSettingsHasUnsavedDraft: (value: boolean) => void
  setInlineRoutingOpen: (value: boolean) => void
  setSettingsSection: (value: RoutingSection) => void
}

export function useTeacherUiPanels(params: UseTeacherUiPanelsParams) {
  const {
    skillsOpen,
    setSkillsOpen,
    setSessionSidebarOpen,
    isMobileViewport,
    settingsHasUnsavedDraft,
    settingsOpen,
    setSettingsOpen,
    setSettingsLegacyFlat,
    setSettingsHasUnsavedDraft,
    setInlineRoutingOpen,
    setSettingsSection,
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
    if (settingsHasUnsavedDraft && typeof window !== 'undefined') {
      const confirmed = window.confirm('当前有未提交的路由草稿，确认关闭并丢弃吗？')
      if (!confirmed) return
    }
    setSettingsOpen(false)
    setSettingsLegacyFlat(false)
    setSettingsHasUnsavedDraft(false)
  }, [setSettingsHasUnsavedDraft, setSettingsLegacyFlat, setSettingsOpen, settingsHasUnsavedDraft])

  const toggleSettingsPanel = useCallback(() => {
    if (settingsOpen) {
      requestCloseSettings()
      return
    }
    setInlineRoutingOpen(false)
    setSettingsLegacyFlat(false)
    setSettingsOpen(true)
  }, [requestCloseSettings, setInlineRoutingOpen, setSettingsLegacyFlat, setSettingsOpen, settingsOpen])

  const openRoutingSettingsPanel = useCallback(() => {
    setInlineRoutingOpen(true)
    setSettingsSection('general')
    setSettingsLegacyFlat(false)
    if (settingsOpen) setSettingsOpen(false)
  }, [setInlineRoutingOpen, setSettingsLegacyFlat, setSettingsOpen, setSettingsSection, settingsOpen])

  return {
    toggleSkillsWorkbench,
    requestCloseSettings,
    toggleSettingsPanel,
    openRoutingSettingsPanel,
  }
}
