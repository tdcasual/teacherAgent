import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { renderMarkdown, absolutizeChartImageUrls, renderStreamingPlainText } from '../../shared/markdown'
import { useSmartAutoScroll, useScrollPositionLock, evictOldestEntries } from '../../shared/useSmartAutoScroll'
import type { Message, RenderedMessage } from './appTypes'
import { useStudentState, PENDING_CHAT_KEY_PREFIX, todayDate } from './hooks/useStudentState'
import type { PendingChatJob } from './appTypes'
import { useVerification } from './hooks/useVerification'
import { useSessionManager } from './hooks/useSessionManager'
import { useChatPolling } from './hooks/useChatPolling'
import { useAssignment } from './hooks/useAssignment'
import { useStudentSendFlow } from './features/chat/useStudentSendFlow'
import { selectComposerHint } from './features/chat/studentUiSelectors'
import StudentTodayHome from './features/home/StudentTodayHome'
import { buildStudentTodayHomeViewModel } from './features/home/studentTodayHomeState'
import { useStudentSessionSidebarState } from './features/session/useStudentSessionSidebarState'
import { useStudentSessionViewStateSync } from './features/session/useStudentSessionViewStateSync'
import {
  isStudentMobileTab,
  studentMobilePanelsFromTab,
  studentMobileTabFromPanels,
} from './features/layout/mobileShellState'
import { useChatAttachments } from '../../shared/useChatAttachments'
import { readFeatureFlag } from '../../shared/featureFlags'
import { MobileTabBar, type MobileTabItem } from '../../shared/mobile/MobileTabBar'
import {
  MobileTabChatIcon,
  MobileTabLearningIcon,
  MobileTabSessionIcon,
} from '../../shared/mobile/tabIcons'
import StudentTopbar from './features/layout/StudentTopbar'
import StudentLayout from './features/layout/StudentLayout'
import ChatPanel from './features/chat/ChatPanel'
import SessionSidebar from './features/chat/SessionSidebar'
import 'katex/dist/katex.min.css'

const DESKTOP_BREAKPOINT = 900

export default function App() {
  const { state, dispatch, refs, setActiveSession } = useStudentState()
  const appRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const [viewportWidth, setViewportWidth] = useState(() => (typeof window !== 'undefined' ? window.innerWidth : 1280))
  const [homeOpen, setHomeOpen] = useState(true)
  const [mobileTab, setMobileTab] = useState<'chat' | 'sessions' | 'learning'>('learning')
  const { messagesRef, endRef, isNearBottom, scrollToBottom, autoScroll } = useSmartAutoScroll()
  const { saveScrollHeight, restoreScrollPosition } = useScrollPositionLock(messagesRef)
  const isMobileLayout = viewportWidth <= DESKTOP_BREAKPOINT
  const mobileShellV2Enabled = useMemo(() => {
    const source: Record<string, string | undefined> = {
      mobileShellV2: import.meta.env.VITE_MOBILE_SHELL_V2_STUDENT,
    }
    if (typeof window !== 'undefined') {
      try {
        const localOverride = window.localStorage.getItem('studentMobileShellV2')
        if (localOverride != null) source.mobileShellV2 = localOverride
      } catch {
        // ignore localStorage read failures
      }
    }
    return readFeatureFlag('mobileShellV2', true, source)
  }, [])
  const studentUseMobileShellV2 = mobileShellV2Enabled && isMobileLayout
  const mobileTabItems = useMemo<MobileTabItem[]>(
    () => [
      { id: 'chat', label: '聊天', icon: <MobileTabChatIcon /> },
      { id: 'sessions', label: '会话', icon: <MobileTabSessionIcon /> },
      { id: 'learning', label: '学习', icon: <MobileTabLearningIcon /> },
    ],
    [],
  )

  useEffect(() => {
    if (typeof window === 'undefined') return
    const onResize = () => setViewportWidth(window.innerWidth)
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // ── Hooks ──
  const { viewStateSyncReady } = useStudentSessionViewStateSync({ state, dispatch, setActiveSession })
  const { handleVerify } = useVerification({ state, dispatch })
  useAssignment({ state, dispatch })

  const sessionManager = useSessionManager({
    state, dispatch, refs, setActiveSession, saveScrollHeight, restoreScrollPosition,
  })

  useChatPolling({
    state, dispatch, refs, setActiveSession,
    refreshSessions: sessionManager.refreshSessions,
  })

  const {
    toggleSessionMenu, setSessionMenuRef, setSessionMenuTriggerRef,
    handleSessionMenuTriggerKeyDown, handleSessionMenuKeyDown,
  } = useStudentSessionSidebarState({
    sidebarOpen: state.sidebarOpen,
    openSessionMenuId: state.openSessionMenuId,
    dispatch,
  })

  // ── Rendered messages (markdown cache) ──
  const renderedMessages = useMemo(() => {
    const cache = refs.markdownCacheRef.current
    evictOldestEntries(cache)
    const pendingPlaceholderId = state.pendingChatJob?.job_id
      ? String(state.pendingChatJob.placeholder_id || '').trim()
      : ''
    return state.messages.map((msg): RenderedMessage => {
      if (pendingPlaceholderId && msg.id === pendingPlaceholderId) {
        return { ...msg, html: renderStreamingPlainText(msg.content) }
      }
      const cached = cache.get(msg.id)
      if (cached && cached.content === msg.content && cached.apiBase === state.apiBase) return { ...msg, html: cached.html }
      const html = absolutizeChartImageUrls(renderMarkdown(msg.content), state.apiBase)
      cache.set(msg.id, { content: msg.content, html, apiBase: state.apiBase })
      return { ...msg, html }
    })
  }, [state.messages, state.apiBase, state.pendingChatJob?.job_id, state.pendingChatJob?.placeholder_id, refs.markdownCacheRef])

  // ── Auto-scroll on new messages ──
  useEffect(() => { autoScroll() }, [state.messages, state.sending, autoScroll])

  // ── Textarea auto-resize ──
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = '0px'
    const next = Math.min(220, Math.max(56, el.scrollHeight))
    el.style.height = `${next}px`
  }, [state.input, state.verifiedStudent, state.pendingChatJob?.job_id])

  // ── Default session selection ──
  useEffect(() => {
    if (!state.verifiedStudent?.student_id) return
    if (!viewStateSyncReady) return
    if (state.pendingChatJob?.job_id) return
    if (state.activeSessionId) return
    const next = state.todayAssignment?.assignment_id || `general_${todayDate()}`
    setActiveSession(next)
  }, [state.verifiedStudent?.student_id, state.todayAssignment?.assignment_id, state.pendingChatJob?.job_id, state.activeSessionId, viewStateSyncReady, setActiveSession])

  // ── Auto-load session messages ──
  useEffect(() => {
    if (!state.verifiedStudent?.student_id) return
    if (!state.activeSessionId) return
    const forceTriggeredBySessionSelect = state.forceSessionLoadToken !== refs.lastHandledForceSessionLoadTokenRef.current
    if (forceTriggeredBySessionSelect) refs.lastHandledForceSessionLoadTokenRef.current = state.forceSessionLoadToken
    if (refs.skipAutoSessionLoadIdRef.current) {
      const skippedSessionId = refs.skipAutoSessionLoadIdRef.current
      refs.skipAutoSessionLoadIdRef.current = ''
      if (skippedSessionId === state.activeSessionId) return
    }
    if (state.pendingChatJob?.job_id) {
      const pendingMatchesActiveSession = state.pendingChatJob.session_id === state.activeSessionId
      const hasLoadedActiveSessionHistory = state.sessionCursor !== 0
      if (pendingMatchesActiveSession && !forceTriggeredBySessionSelect && hasLoadedActiveSessionHistory) return
      void sessionManager.loadSessionMessages(state.activeSessionId, -1, false)
      return
    }
    if (state.sending) return
    void sessionManager.loadSessionMessages(state.activeSessionId, -1, false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.activeSessionId, state.verifiedStudent?.student_id, state.apiBase, state.pendingChatJob?.job_id, state.pendingChatJob?.session_id, state.forceSessionLoadToken, state.sessionCursor])

  // ── Sync activeSessionRef ──
  useEffect(() => { refs.activeSessionRef.current = state.activeSessionId }, [state.activeSessionId, refs.activeSessionRef])

  // ── Send flow (wrapper setters for compatibility) ──
  const setSending = useCallback((v: boolean) => dispatch({ type: 'SET', field: 'sending', value: v }), [dispatch])
  const setInput = useCallback((v: string) => dispatch({ type: 'SET', field: 'input', value: v }), [dispatch])
  const setPendingChatJob = useCallback((v: PendingChatJob | null) => dispatch({ type: 'SET', field: 'pendingChatJob', value: v }), [dispatch])
  const setVerifyError = useCallback((v: string) => dispatch({ type: 'SET', field: 'verifyError', value: v }), [dispatch])
  const setVerifyOpen = useCallback((v: boolean) => dispatch({ type: 'SET', field: 'verifyOpen', value: v }), [dispatch])
  const setMessages = useCallback((v: Message[] | ((prev: Message[]) => Message[])) => {
    if (typeof v === 'function') dispatch({ type: 'UPDATE_MESSAGES', updater: v })
    else dispatch({ type: 'SET', field: 'messages', value: v })
  }, [dispatch])
  const updateMessage = useCallback((id: string, patch: Partial<Message>) => {
    dispatch({ type: 'UPDATE_MESSAGES', updater: (prev) => prev.map((m) => m.id === id ? { ...m, ...patch } : m) })
  }, [dispatch])

  const attachmentSessionId = state.activeSessionId || state.todayAssignment?.assignment_id || `general_${todayDate()}`
  const {
    attachments,
    addFiles,
    removeAttachment,
    readyAttachmentRefs,
    hasSendableAttachments,
    uploading: uploadingAttachments,
  } = useChatAttachments({
    apiBase: state.apiBase,
    role: 'student',
    sessionId: attachmentSessionId,
    studentId: state.verifiedStudent?.student_id || '',
    persistenceKey: state.verifiedStudent?.student_id
      ? `student:${state.verifiedStudent.student_id}:${attachmentSessionId}`
      : '',
  })
  const keepReadyAttachmentsOnSend = useCallback(() => {}, [])

  const { handleSend } = useStudentSendFlow({
    apiBase: state.apiBase,
    input: state.input,
    messages: state.messages,
    activeSessionId: state.activeSessionId,
    todayAssignment: state.todayAssignment,
    verifiedStudent: state.verifiedStudent,
    pendingChatJob: state.pendingChatJob,
    attachments: readyAttachmentRefs,
    pendingChatKeyPrefix: PENDING_CHAT_KEY_PREFIX,
    todayDate,
    onSendSuccess: keepReadyAttachmentsOnSend,
    setVerifyError,
    setVerifyOpen,
    setSending,
    setInput,
    setActiveSession,
    setPendingChatJob,
    setMessages,
    updateMessage,
    pendingRecoveredFromStorageRef: refs.pendingRecoveredFromStorageRef,
    skipAutoSessionLoadIdRef: refs.skipAutoSessionLoadIdRef,
  })

  // ── Composer hint + keyboard ──
  const composerHint = useMemo(() => selectComposerHint({
    verifiedStudent: state.verifiedStudent,
    pendingChatJobId: state.pendingChatJob?.job_id || '',
    sending: state.sending,
  }), [state.pendingChatJob?.job_id, state.sending, state.verifiedStudent])

  const todayHomeViewModel = useMemo(() => buildStudentTodayHomeViewModel({
    verifiedStudent: state.verifiedStudent,
    assignmentLoading: state.assignmentLoading,
    assignmentError: state.assignmentError,
    todayAssignment: state.todayAssignment,
    activeSessionId: state.activeSessionId,
    messages: state.messages,
    pendingChatJob: state.pendingChatJob,
    recentCompletedReplies: state.recentCompletedReplies,
  }), [
    state.activeSessionId,
    state.assignmentError,
    state.assignmentLoading,
    state.messages,
    state.pendingChatJob,
    state.recentCompletedReplies,
    state.todayAssignment,
    state.verifiedStudent,
  ])

  const handleInputKeyDown = useCallback((event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter') return
    if (event.shiftKey) return
    if (event.nativeEvent.isComposing) return
    event.preventDefault()
    if (!state.verifiedStudent) return
    if (state.sending || state.pendingChatJob?.job_id) return
    if (!state.input.trim() && !hasSendableAttachments) return
    event.currentTarget.form?.requestSubmit()
  }, [state.verifiedStudent, state.sending, state.pendingChatJob?.job_id, state.input, hasSendableAttachments])

  useEffect(() => {
    if (!studentUseMobileShellV2) return
    const nextTab = studentMobileTabFromPanels({
      sidebarOpen: state.sidebarOpen,
      verifyOpen: state.verifyOpen,
      homeOpen,
    })
    if (mobileTab !== nextTab) setMobileTab(nextTab)
  }, [studentUseMobileShellV2, state.sidebarOpen, state.verifyOpen, homeOpen, mobileTab])

  useEffect(() => {
    if (state.verifiedStudent?.student_id) return
    setHomeOpen(true)
  }, [state.verifiedStudent?.student_id])

  const handleMobileTabChange = useCallback((tabId: string) => {
    if (!isStudentMobileTab(tabId)) return
    setMobileTab(tabId)
    if (!studentUseMobileShellV2) return
    const nextPanels = studentMobilePanelsFromTab(tabId)
    setHomeOpen(nextPanels.homeOpen)
    if (state.sidebarOpen !== nextPanels.sidebarOpen) {
      dispatch({ type: 'SET', field: 'sidebarOpen', value: nextPanels.sidebarOpen })
    }
    if (state.verifyOpen !== nextPanels.verifyOpen) {
      dispatch({ type: 'SET', field: 'verifyOpen', value: nextPanels.verifyOpen })
    }
  }, [studentUseMobileShellV2, state.sidebarOpen, state.verifyOpen, dispatch])

  const openTodayHome = useCallback(() => {
    setHomeOpen(true)
    if (!studentUseMobileShellV2) return
    setMobileTab('learning')
    if (state.sidebarOpen) {
      dispatch({ type: 'SET', field: 'sidebarOpen', value: false })
    }
  }, [dispatch, state.sidebarOpen, studentUseMobileShellV2])

  const openExecutionState = useCallback(() => {
    setHomeOpen(false)
    if (!studentUseMobileShellV2) return
    setMobileTab('chat')
    if (state.sidebarOpen) {
      dispatch({ type: 'SET', field: 'sidebarOpen', value: false })
    }
  }, [dispatch, state.sidebarOpen, studentUseMobileShellV2])

  const handlePrimaryHomeAction = useCallback(() => {
    if (!state.verifiedStudent) {
      dispatch({ type: 'SET', field: 'verifyOpen', value: true })
      return
    }
    if (todayHomeViewModel.status === 'pending_generation') {
      dispatch({ type: 'SET', field: 'assignmentRefreshNonce', value: state.assignmentRefreshNonce + 1 })
      return
    }
    if (todayHomeViewModel.status === 'generating') return
    openExecutionState()
  }, [dispatch, openExecutionState, state.assignmentRefreshNonce, state.verifiedStudent, todayHomeViewModel.status])

  const handleOpenHistory = useCallback(() => {
    setHomeOpen(false)
    dispatch({ type: 'SET', field: 'sidebarOpen', value: true })
    if (studentUseMobileShellV2) setMobileTab('sessions')
  }, [dispatch, studentUseMobileShellV2])

  const handleOpenFreeChat = useCallback(() => {
    openExecutionState()
  }, [openExecutionState])

  const handleStartNewStudentSession = useCallback(() => {
    openExecutionState()
    sessionManager.startNewStudentSession()
  }, [openExecutionState, sessionManager])

  useEffect(() => {
    if (!studentUseMobileShellV2) return
    if (!homeOpen) return
    if (!state.sidebarOpen) return
    dispatch({ type: 'SET', field: 'sidebarOpen', value: false })
  }, [dispatch, homeOpen, state.sidebarOpen, studentUseMobileShellV2])

  const heroDateLabel = useMemo(() => {
    const now = new Date()
    return now.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })
  }, [])

  // ── Render ──
  return (
    <div
      className={`app flex h-dvh flex-col bg-bg overflow-hidden ${studentUseMobileShellV2 ? 'student-mobile-shell-v2' : ''}`.trim()}
      ref={appRef}
      data-mobile-shell-v2={mobileShellV2Enabled ? '1' : '0'}
    >
      <StudentTopbar
        verifiedStudent={state.verifiedStudent}
        sidebarOpen={state.sidebarOpen}
        homeActive={homeOpen}
        compactMobile={studentUseMobileShellV2}
        dispatch={dispatch}
        openTodayHome={openTodayHome}
        startNewStudentSession={handleStartNewStudentSession}
      />
      <StudentLayout
        sidebarOpen={state.sidebarOpen}
        sidebar={
          <SessionSidebar
            apiBase={state.apiBase}
            sidebarOpen={state.sidebarOpen}
            showHistorySection={!studentUseMobileShellV2 || mobileTab === 'sessions'}
            dispatch={dispatch}
            verifiedStudent={state.verifiedStudent}
            historyLoading={state.historyLoading}
            historyError={state.historyError}
            historyHasMore={state.historyHasMore}
            refreshSessions={sessionManager.refreshSessions}
            showArchivedSessions={state.showArchivedSessions}
            historyQuery={state.historyQuery}
            visibleSessionCount={sessionManager.visibleSessions.length}
            groupedSessions={sessionManager.groupedSessions}
            deletedSessionIds={state.deletedSessionIds}
            activeSessionId={state.activeSessionId}
            onSelectSession={(sessionId) => {
              setHomeOpen(false)
              if (studentUseMobileShellV2) setMobileTab('sessions')
              void sessionManager.selectStudentSession(sessionId)
            }}
            getSessionTitle={sessionManager.getSessionTitle}
            openSessionMenuId={state.openSessionMenuId}
            toggleSessionMenu={toggleSessionMenu}
            handleSessionMenuTriggerKeyDown={handleSessionMenuTriggerKeyDown}
            handleSessionMenuKeyDown={handleSessionMenuKeyDown}
            setSessionMenuTriggerRef={setSessionMenuTriggerRef}
            setSessionMenuRef={setSessionMenuRef}
            renameSession={sessionManager.renameSession}
            toggleSessionArchive={sessionManager.toggleSessionArchive}
            sessionHasMore={state.sessionHasMore}
            sessionLoading={state.sessionLoading}
            sessionCursor={state.sessionCursor}
            loadSessionMessages={sessionManager.loadSessionMessages}
            sessionError={state.sessionError}
            verifyOpen={state.verifyOpen}
            handleVerify={handleVerify}
            nameInput={state.nameInput}
            classInput={state.classInput}
            credentialInput={state.credentialInput}
            verifying={state.verifying}
            verifyError={state.verifyError}
            verifyInfo={state.verifyInfo}
            todayAssignment={state.todayAssignment}
            assignmentLoading={state.assignmentLoading}
            assignmentError={state.assignmentError}
            resetVerification={sessionManager.resetVerification}
            startNewStudentSession={handleStartNewStudentSession}
            renameDialogSessionId={state.renameDialogSessionId}
            archiveDialogSessionId={state.archiveDialogSessionId}
            archiveDialogActionLabel={sessionManager.archiveDialogActionLabel}
            archiveDialogIsArchived={sessionManager.archiveDialogIsArchived}
            cancelRenameDialog={sessionManager.cancelRenameDialog}
            confirmRenameDialog={sessionManager.confirmRenameDialog}
            cancelArchiveDialog={sessionManager.cancelArchiveDialog}
            confirmArchiveDialog={sessionManager.confirmArchiveDialog}
          />
        }
        chat={
          homeOpen ? (
            <StudentTodayHome
              studentName={state.verifiedStudent?.student_name || ''}
              dateLabel={heroDateLabel}
              heroTitle="今日任务"
              heroSummary="今天先完成主任务，再查看历史记录或补充提问。"
              viewModel={todayHomeViewModel}
              onPrimaryAction={handlePrimaryHomeAction}
              onOpenHistory={handleOpenHistory}
              onOpenFreeChat={handleOpenFreeChat}
            />
          ) : (
            <ChatPanel
              renderedMessages={renderedMessages}
              sending={state.sending}
              pendingChatJobId={state.pendingChatJob?.job_id || ''}
              verifiedStudent={state.verifiedStudent}
              messagesRef={messagesRef}
              endRef={endRef}
              isNearBottom={isNearBottom}
              scrollToBottom={scrollToBottom}
              inputRef={inputRef}
              input={state.input}
              setInput={setInput}
              handleInputKeyDown={handleInputKeyDown}
              handleSend={handleSend}
              composerHint={composerHint}
              attachments={attachments}
              uploadingAttachments={uploadingAttachments}
              hasSendableAttachments={hasSendableAttachments}
              onPickFiles={addFiles}
              onRemoveAttachment={removeAttachment}
            />
          )
        }
      />
      {studentUseMobileShellV2 ? (
        <MobileTabBar
          items={mobileTabItems}
          activeId={mobileTab}
          onChange={handleMobileTabChange}
          ariaLabel="学生端移动导航"
        />
      ) : null}
    </div>
  )
}
