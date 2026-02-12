import { useEffect, type RefObject } from 'react'
import { safeLocalStorageSetItem, safeLocalStorageRemoveItem } from '../../utils/storage'
import { TEACHER_LOCAL_DRAFT_SESSIONS_KEY } from '../chat/viewState'
import type { PendingChatJob, WorkbenchTab } from '../../appTypes'
import type { RoutingSection } from '../routing/RoutingPage'

// ---------------------------------------------------------------------------
// Params
// ---------------------------------------------------------------------------

export type UseLocalStorageSyncParams = {
  // localStorage-synced state
  apiBase: string
  favorites: string[]
  skillsOpen: boolean
  workbenchTab: WorkbenchTab
  sessionSidebarOpen: boolean
  settingsSection: RoutingSection
  activeSkillId: string
  skillPinned: boolean
  localDraftSessionIds: string[]
  activeSessionId: string
  uploadMode: string
  pendingChatJob: PendingChatJob | null
  pendingChatKey: string

  // Refs to keep in sync with state
  activeSessionRef: RefObject<string>
  historyCursorRef: RefObject<number>
  historyHasMoreRef: RefObject<boolean>
  localDraftSessionIdsRef: RefObject<string[]>
  pendingChatJobRef: RefObject<PendingChatJob | null>
  historyCursor: number
  historyHasMore: boolean

  // Topbar / viewport
  topbarRef: RefObject<HTMLElement | null>
  setTopbarHeight: (h: number) => void
  setViewportWidth: (w: number) => void

  // Session menu close-on-outside-click
  openSessionMenuId: string
  setOpenSessionMenuId: (id: string) => void

  // Input textarea auto-resize
  inputRef: RefObject<HTMLTextAreaElement | null>
  input: string

  // Composer warning clear
  composerWarning: string
  setComposerWarning: (w: string) => void

  // Upload/draft error auto-expand
  uploadError: string
  uploadCardCollapsed: boolean
  setUploadCardCollapsed: (v: boolean) => void
  examUploadError: string
  draftError: string
  draftActionError: string
  draftPanelCollapsed: boolean
  setDraftPanelCollapsed: (v: boolean) => void
  examDraftError: string
  examDraftActionError: string
  examDraftPanelCollapsed: boolean
  setExamDraftPanelCollapsed: (v: boolean) => void

  // Markdown cache ref (cleared on apiBase change)
  markdownCacheRef: RefObject<Map<string, { content: string; html: string; apiBase: string }>>
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useLocalStorageSync(params: UseLocalStorageSyncParams): void {
  const {
    apiBase,
    favorites,
    skillsOpen,
    workbenchTab,
    sessionSidebarOpen,
    settingsSection,
    activeSkillId,
    skillPinned,
    localDraftSessionIds,
    activeSessionId,
    uploadMode,
    pendingChatJob,
    pendingChatKey,
    activeSessionRef,
    historyCursorRef,
    historyHasMoreRef,
    localDraftSessionIdsRef,
    pendingChatJobRef,
    historyCursor,
    historyHasMore,
    topbarRef,
    setTopbarHeight,
    setViewportWidth,
    openSessionMenuId,
    setOpenSessionMenuId,
    inputRef,
    input,
    composerWarning,
    setComposerWarning,
    uploadError,
    uploadCardCollapsed,
    setUploadCardCollapsed,
    examUploadError,
    draftError,
    draftActionError,
    draftPanelCollapsed,
    setDraftPanelCollapsed,
    examDraftError,
    examDraftActionError,
    examDraftPanelCollapsed,
    setExamDraftPanelCollapsed,
    markdownCacheRef,
  } = params

  // --- localStorage sync effects ---

  useEffect(() => {
    safeLocalStorageSetItem('apiBaseTeacher', apiBase)
    markdownCacheRef.current.clear()
  }, [apiBase, markdownCacheRef])

  useEffect(() => {
    safeLocalStorageSetItem('teacherSkillFavorites', JSON.stringify(favorites))
  }, [favorites])

  useEffect(() => {
    safeLocalStorageSetItem('teacherSkillsOpen', String(skillsOpen))
  }, [skillsOpen])

  useEffect(() => {
    safeLocalStorageSetItem('teacherWorkbenchTab', workbenchTab)
  }, [workbenchTab])

  useEffect(() => {
    safeLocalStorageSetItem('teacherSessionSidebarOpen', String(sessionSidebarOpen))
  }, [sessionSidebarOpen])

  useEffect(() => {
    safeLocalStorageSetItem('teacherSettingsSection', settingsSection)
  }, [settingsSection])

  useEffect(() => {
    if (activeSkillId) safeLocalStorageSetItem('teacherActiveSkillId', activeSkillId)
    else safeLocalStorageRemoveItem('teacherActiveSkillId')
  }, [activeSkillId])

  useEffect(() => {
    safeLocalStorageSetItem('teacherSkillPinned', String(skillPinned))
  }, [skillPinned])

  useEffect(() => {
    try {
      safeLocalStorageSetItem(TEACHER_LOCAL_DRAFT_SESSIONS_KEY, JSON.stringify(localDraftSessionIds))
    } catch {
      // ignore localStorage write errors
    }
  }, [localDraftSessionIds])

  useEffect(() => {
    if (activeSessionId) safeLocalStorageSetItem('teacherActiveSessionId', activeSessionId)
    else safeLocalStorageRemoveItem('teacherActiveSessionId')
  }, [activeSessionId])

  useEffect(() => {
    safeLocalStorageSetItem('teacherUploadMode', uploadMode)
  }, [uploadMode])

  useEffect(() => {
    if (pendingChatJob) safeLocalStorageSetItem(pendingChatKey, JSON.stringify(pendingChatJob))
    else safeLocalStorageRemoveItem(pendingChatKey)
  }, [pendingChatJob, pendingChatKey])

  // --- Ref-sync effects ---

  useEffect(() => {
    activeSessionRef.current = activeSessionId
  }, [activeSessionId, activeSessionRef])

  useEffect(() => {
    historyCursorRef.current = historyCursor
  }, [historyCursor, historyCursorRef])

  useEffect(() => {
    historyHasMoreRef.current = historyHasMore
  }, [historyHasMore, historyHasMoreRef])

  useEffect(() => {
    localDraftSessionIdsRef.current = localDraftSessionIds
  }, [localDraftSessionIds, localDraftSessionIdsRef])

  useEffect(() => {
    pendingChatJobRef.current = pendingChatJob
  }, [pendingChatJob, pendingChatJobRef])

  // --- Topbar height / viewport resize observer ---

  useEffect(() => {
    if (typeof window === 'undefined') return
    const el = topbarRef.current
    if (!el) return
    const updateHeight = () => {
      setTopbarHeight(Math.max(56, Math.round(el.getBoundingClientRect().height)))
      setViewportWidth(window.innerWidth)
    }
    updateHeight()
    let observer: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(updateHeight)
      observer.observe(el)
    }
    window.addEventListener('resize', updateHeight)
    return () => {
      window.removeEventListener('resize', updateHeight)
      observer?.disconnect()
    }
  }, [setTopbarHeight, setViewportWidth, topbarRef])

  // --- Session menu close-on-outside-click ---

  useEffect(() => {
    if (!openSessionMenuId) return
    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('.session-menu-wrap')) return
      setOpenSessionMenuId('')
    }
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpenSessionMenuId('')
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
  }, [openSessionMenuId, setOpenSessionMenuId])

  useEffect(() => {
    if (!sessionSidebarOpen) {
      setOpenSessionMenuId('')
    }
  }, [sessionSidebarOpen, setOpenSessionMenuId])

  // --- Input textarea auto-resize ---

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = '0px'
    const next = Math.min(220, Math.max(56, el.scrollHeight))
    el.style.height = `${next}px`
  }, [input, inputRef, pendingChatJob?.job_id])

  // --- Composer warning clear ---

  useEffect(() => {
    if (!composerWarning) return
    if (!input.trim()) return
    setComposerWarning('')
  }, [composerWarning, input, setComposerWarning])

  // --- Upload/draft error auto-expand ---

  useEffect(() => {
    if (uploadError && uploadCardCollapsed) setUploadCardCollapsed(false)
  }, [uploadError, uploadCardCollapsed, setUploadCardCollapsed])

  useEffect(() => {
    if (examUploadError && uploadCardCollapsed) setUploadCardCollapsed(false)
  }, [examUploadError, uploadCardCollapsed, setUploadCardCollapsed])

  useEffect(() => {
    if ((draftError || draftActionError) && draftPanelCollapsed) setDraftPanelCollapsed(false)
  }, [draftError, draftActionError, draftPanelCollapsed, setDraftPanelCollapsed])

  useEffect(() => {
    if ((examDraftError || examDraftActionError) && examDraftPanelCollapsed) setExamDraftPanelCollapsed(false)
  }, [examDraftError, examDraftActionError, examDraftPanelCollapsed, setExamDraftPanelCollapsed])
}
