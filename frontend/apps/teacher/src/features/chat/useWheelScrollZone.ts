import { useCallback, useRef } from 'react'
import type { WheelScrollZone } from '../../appTypes'

export interface UseWheelScrollZoneOptions {
  appRef: React.RefObject<HTMLDivElement | null>
  sessionSidebarOpen: boolean
  skillsOpen: boolean
  inlineRoutingOpen: boolean
}

export interface UseWheelScrollZoneReturn {
  wheelScrollZoneRef: React.RefObject<WheelScrollZone>
  setWheelScrollZone: (zone: WheelScrollZone) => void
  resolveWheelScrollTarget: (zone: WheelScrollZone) => HTMLElement | null
}

export function useWheelScrollZone({
  appRef,
  sessionSidebarOpen,
  skillsOpen,
  inlineRoutingOpen,
}: UseWheelScrollZoneOptions): UseWheelScrollZoneReturn {
  const wheelScrollZoneRef = useRef<WheelScrollZone>('chat')

  const resolveTarget = useCallback(
    (zone: WheelScrollZone) => {
      const root = appRef.current
      if (!root) return null
      if (zone === 'session') {
        if (!sessionSidebarOpen) return null
        return root.querySelector('.session-groups') as HTMLElement | null
      }
      if (zone === 'workbench') {
        if (!skillsOpen) return null
        return (
          (root.querySelector('.skills-panel.open .skills-body') as HTMLElement | null) ||
          (root.querySelector('.skills-panel.open .workbench-memory') as HTMLElement | null)
        )
      }
      if (inlineRoutingOpen) {
        return root.querySelector('.chat-shell') as HTMLElement | null
      }
      return root.querySelector('.messages') as HTMLElement | null
    },
    [appRef, inlineRoutingOpen, sessionSidebarOpen, skillsOpen],
  )

  const setWheelScrollZone = useCallback((zone: WheelScrollZone) => {
    wheelScrollZoneRef.current = zone
  }, [])

  return {
    wheelScrollZoneRef,
    setWheelScrollZone,
    resolveWheelScrollTarget: resolveTarget,
  }
}
