import { useCallback, useEffect, useRef } from 'react'
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

const isMobileViewport = () => {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(max-width: 900px)').matches
}

export function useWheelScrollZone({
  appRef,
  sessionSidebarOpen,
  skillsOpen,
  inlineRoutingOpen,
}: UseWheelScrollZoneOptions): UseWheelScrollZoneReturn {
  const wheelScrollZoneRef = useRef<WheelScrollZone>('chat')

  const setWheelScrollZone = useCallback((zone: WheelScrollZone) => {
    wheelScrollZoneRef.current = zone
  }, [])

  const resolveWheelScrollTarget = useCallback(
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
    [inlineRoutingOpen, sessionSidebarOpen, skillsOpen],
  )

  // Reset zone to 'chat' when sidebar/workbench closes
  useEffect(() => {
    if (wheelScrollZoneRef.current === 'session' && !sessionSidebarOpen) {
      setWheelScrollZone('chat')
    }
    if (wheelScrollZoneRef.current === 'workbench' && !skillsOpen) {
      setWheelScrollZone('chat')
    }
  }, [sessionSidebarOpen, setWheelScrollZone, skillsOpen])

  // Pointer-down zone detection
  useEffect(() => {
    if (typeof document === 'undefined') return
    const enabled = !isMobileViewport()
    if (!enabled) {
      setWheelScrollZone('chat')
      return
    }
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null
      if (!target) return
      const root = appRef.current
      if (!root || !root.contains(target)) return
      if (sessionSidebarOpen && target.closest('.session-sidebar')) {
        setWheelScrollZone('session')
        return
      }
      if (skillsOpen && target.closest('.skills-panel')) {
        setWheelScrollZone('workbench')
        return
      }
      if (target.closest('.chat-shell')) {
        setWheelScrollZone('chat')
      }
    }
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') setWheelScrollZone('chat')
    }
    document.addEventListener('pointerdown', onPointerDown, true)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown, true)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [isMobileViewport, sessionSidebarOpen, setWheelScrollZone, skillsOpen])

  // Wheel event redirection
  useEffect(() => {
    if (typeof document === 'undefined') return
    const enabled = !isMobileViewport()
    if (!enabled) return

    const onWheel = (event: WheelEvent) => {
      if (event.defaultPrevented || event.ctrlKey) return
      const target = event.target as HTMLElement | null
      if (!target) return
      const root = appRef.current
      if (!root || !root.contains(target)) return
      if (target.closest('textarea, input, select, [contenteditable="true"]')) return

      const tryScroll = (el: HTMLElement | null) => {
        if (!el) return false
        const beforeTop = el.scrollTop
        const beforeLeft = el.scrollLeft
        if (event.deltaY) el.scrollTop += event.deltaY
        if (event.deltaX) el.scrollLeft += event.deltaX
        return el.scrollTop !== beforeTop || el.scrollLeft !== beforeLeft
      }

      let zone = wheelScrollZoneRef.current
      if (zone === 'session' && !sessionSidebarOpen) zone = 'chat'
      if (zone === 'workbench' && !skillsOpen) zone = 'chat'

      // Important: always consume the wheel event while the app is in desktop chat mode.
      // This prevents native scrolling of whichever panel happens to be under the cursor
      // until the user explicitly activates a panel via pointer interaction.
      event.preventDefault()

      const destination = resolveWheelScrollTarget(zone)
      tryScroll(destination)
    }

    document.addEventListener('wheel', onWheel, { passive: false, capture: true })
    return () => {
      document.removeEventListener('wheel', onWheel, true)
    }
  }, [isMobileViewport, resolveWheelScrollTarget, sessionSidebarOpen, skillsOpen])

  return { wheelScrollZoneRef, setWheelScrollZone, resolveWheelScrollTarget }
}