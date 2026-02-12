import { useCallback } from 'react'
import { useWheelScrollZone as useSharedWheelScrollZone } from '../../../../shared/useWheelScrollZone'
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
  const resolveTarget = useCallback(
    (zone: string) => {
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

  const { zoneRef, setZone } = useSharedWheelScrollZone({
    appRef,
    defaultZone: 'chat' as const,
    resolveTarget,
    detectors: [
      { zone: 'session' as const, selector: '.session-sidebar', when: () => sessionSidebarOpen },
      { zone: 'workbench' as const, selector: '.skills-panel', when: () => skillsOpen },
      { zone: 'chat' as const, selector: '.chat-shell' },
    ],
    resetWhen: [
      { zone: 'session' as const, condition: !sessionSidebarOpen },
      { zone: 'workbench' as const, condition: !skillsOpen },
    ],
  })

  return {
    wheelScrollZoneRef: zoneRef,
    setWheelScrollZone: setZone,
    resolveWheelScrollTarget: resolveTarget as (zone: WheelScrollZone) => HTMLElement | null,
  }
}
