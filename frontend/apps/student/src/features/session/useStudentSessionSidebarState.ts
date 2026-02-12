import { useCallback, useEffect, useRef, type Dispatch, type KeyboardEvent } from 'react'
import { getNextMenuIndex } from '../../../../shared/sessionMenuNavigation'
import type { StudentAction } from '../../hooks/useStudentState'

type UseStudentSessionSidebarStateParams = {
  sidebarOpen: boolean
  openSessionMenuId: string
  dispatch: Dispatch<StudentAction>
}

export function useStudentSessionSidebarState({ sidebarOpen, openSessionMenuId, dispatch }: UseStudentSessionSidebarStateParams) {
  const sessionMenuRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const sessionMenuTriggerRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  const toggleSessionMenu = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    dispatch({ type: 'SET', field: 'openSessionMenuId', value: openSessionMenuId === sid ? '' : sid })
  }, [openSessionMenuId, dispatch])

  const setSessionMenuRef = useCallback((sessionId: string, node: HTMLDivElement | null) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    if (node) { sessionMenuRefs.current[sid] = node; return }
    delete sessionMenuRefs.current[sid]
  }, [])

  const setSessionMenuTriggerRef = useCallback((sessionId: string, node: HTMLButtonElement | null) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    if (node) { sessionMenuTriggerRefs.current[sid] = node; return }
    delete sessionMenuTriggerRefs.current[sid]
  }, [])

  const focusSessionMenuItem = useCallback((sessionId: string, target: 'first' | 'last') => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    const menu = sessionMenuRefs.current[sid]
    if (!menu) return
    const items = Array.from(menu.querySelectorAll<HTMLButtonElement>('.session-menu-item:not([disabled])'))
    if (!items.length) return
    const index = target === 'last' ? items.length - 1 : 0
    items[index]?.focus()
  }, [])

  const handleSessionMenuTriggerKeyDown = useCallback(
    (sessionId: string, isMenuOpen: boolean, event: KeyboardEvent<HTMLButtonElement>) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        event.stopPropagation()
        if (!isMenuOpen) toggleSessionMenu(sid)
        const target: 'first' | 'last' = event.key === 'ArrowUp' ? 'last' : 'first'
        window.setTimeout(() => focusSessionMenuItem(sid, target), 0)
        return
      }
      if (event.key === 'Escape' && isMenuOpen) {
        event.preventDefault()
        toggleSessionMenu(sid)
      }
    },
    [focusSessionMenuItem, toggleSessionMenu],
  )

  const handleSessionMenuKeyDown = useCallback(
    (sessionId: string, event: KeyboardEvent<HTMLDivElement>) => {
      const sid = String(sessionId || '').trim()
      if (!sid || openSessionMenuId !== sid) return
      const menu = sessionMenuRefs.current[sid]
      if (!menu) return
      const items = Array.from(menu.querySelectorAll<HTMLButtonElement>('.session-menu-item:not([disabled])'))
      if (!items.length) return

      if (event.key === 'Escape') {
        event.preventDefault()
        toggleSessionMenu(sid)
        sessionMenuTriggerRefs.current[sid]?.focus()
        return
      }
      if (event.key === 'Tab') { toggleSessionMenu(sid); return }

      let direction: 'next' | 'prev' | 'first' | 'last' | null = null
      if (event.key === 'ArrowDown') direction = 'next'
      else if (event.key === 'ArrowUp') direction = 'prev'
      else if (event.key === 'Home') direction = 'first'
      else if (event.key === 'End') direction = 'last'
      if (!direction) return

      event.preventDefault()
      const activeIndex = items.findIndex((item) => item === document.activeElement)
      const nextIndex = getNextMenuIndex(activeIndex, items.length, direction)
      if (nextIndex >= 0) items[nextIndex]?.focus()
    },
    [openSessionMenuId, toggleSessionMenu],
  )

  // Close menu on outside click
  useEffect(() => {
    if (!openSessionMenuId) return
    const sid = openSessionMenuId
    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('.session-menu-wrap')) return
      dispatch({ type: 'SET', field: 'openSessionMenuId', value: '' })
    }
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        sessionMenuTriggerRefs.current[sid]?.focus()
        dispatch({ type: 'SET', field: 'openSessionMenuId', value: '' })
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('touchstart', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('touchstart', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [openSessionMenuId, dispatch])

  // Close menu when sidebar closes
  useEffect(() => {
    if (!sidebarOpen) dispatch({ type: 'SET', field: 'openSessionMenuId', value: '' })
  }, [sidebarOpen, dispatch])

  return {
    toggleSessionMenu,
    setSessionMenuRef,
    setSessionMenuTriggerRef,
    handleSessionMenuTriggerKeyDown,
    handleSessionMenuKeyDown,
  }
}
