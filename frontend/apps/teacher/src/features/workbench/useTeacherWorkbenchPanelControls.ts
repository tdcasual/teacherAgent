import { useCallback, useEffect, useState, type MutableRefObject } from 'react'
import type { PanelImperativeHandle } from 'react-resizable-panels'

type UseTeacherWorkbenchPanelControlsParams = {
  workbenchPanelRef: MutableRefObject<PanelImperativeHandle | null>
  skillsOpen: boolean
  setSkillsOpen: (value: boolean | ((prev: boolean) => boolean)) => void
  isMobileLayout: boolean
  workbenchMaxWidth: number
  workbenchMinWidth: number
  defaultWorkbenchWidth: number
}

export function useTeacherWorkbenchPanelControls(params: UseTeacherWorkbenchPanelControlsParams) {
  const {
    workbenchPanelRef,
    skillsOpen,
    setSkillsOpen,
    isMobileLayout,
    workbenchMaxWidth,
    workbenchMinWidth,
    defaultWorkbenchWidth,
  } = params
  const [isWorkbenchResizing, setIsWorkbenchResizing] = useState(false)

  const startWorkbenchResize = useCallback(() => {
    setIsWorkbenchResizing(true)
  }, [])

  const handleWorkbenchResizeReset = useCallback(() => {
    const panel = workbenchPanelRef.current
    if (!panel) return
    panel.resize(defaultWorkbenchWidth)
    panel.expand()
    if (!skillsOpen) setSkillsOpen(true)
  }, [defaultWorkbenchWidth, skillsOpen, setSkillsOpen, workbenchPanelRef])

  useEffect(() => {
    const panel = workbenchPanelRef.current
    if (!panel) return
    if (isMobileLayout || !skillsOpen) {
      panel.collapse()
      return
    }
    panel.expand()
    const currentWidth = panel.getSize().inPixels
    if (!Number.isFinite(currentWidth)) return
    const clamped = Math.min(workbenchMaxWidth, Math.max(workbenchMinWidth, Math.round(currentWidth)))
    if (Math.abs(clamped - currentWidth) > 1) {
      panel.resize(clamped)
    }
  }, [isMobileLayout, skillsOpen, workbenchMaxWidth, workbenchMinWidth, workbenchPanelRef])

  useEffect(() => {
    if (!isWorkbenchResizing || typeof window === 'undefined') return
    const stop = () => setIsWorkbenchResizing(false)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
    return () => {
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
    }
  }, [isWorkbenchResizing])

  return {
    isWorkbenchResizing,
    startWorkbenchResize,
    handleWorkbenchResizeReset,
  }
}
