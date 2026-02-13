import { useCallback, useEffect, useMemo, useRef, type KeyboardEvent } from 'react'
import { renderMarkdown, absolutizeChartImageUrls } from '../../shared/markdown'
import { useSmartAutoScroll, useScrollPositionLock, evictOldestEntries } from '../../shared/useSmartAutoScroll'
import type { Message, PendingChatJob, RenderedMessage } from './appTypes'
import { useStudentState, PENDING_CHAT_KEY_PREFIX, todayDate } from './hooks/useStudentState'
import { useVerification } from './hooks/useVerification'
import { useSessionManager } from './hooks/useSessionManager'
import { useChatPolling } from './hooks/useChatPolling'
import { useAssignment } from './hooks/useAssignment'
import { useStudentSendFlow } from './features/chat/useStudentSendFlow'
import { selectComposerHint } from './features/chat/studentUiSelectors'
import { useStudentSessionSidebarState } from './features/session/useStudentSessionSidebarState'
import { useStudentSessionViewStateSync } from './features/session/useStudentSessionViewStateSync'
import { useChatAttachments } from '../../shared/useChatAttachments'
import StudentTopbar from './features/layout/StudentTopbar'
import StudentLayout from './features/layout/StudentLayout'
import ChatPanel from './features/chat/ChatPanel'
import SessionSidebar from './features/chat/SessionSidebar'
import 'katex/dist/katex.min.css'

export default function App() {
  const { state, dispatch, refs, setActiveSession } = useStudentState()
  const appRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const { messagesRef, endRef, isNearBottom, scrollToBottom, autoScroll } = useSmartAutoScroll()
  const { saveScrollHeight, restoreScrollPosition } = useScrollPositionLock(messagesRef)

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
    return state.messages.map((msg): RenderedMessage => {
      const cached = cache.get(msg.id)
      if (cached && cached.content === msg.content && cached.apiBase === state.apiBase) return { ...msg, html: cached.html }
      const html = absolutizeChartImageUrls(renderMarkdown(msg.content), state.apiBase)
      cache.set(msg.id, { content: msg.content, html, apiBase: state.apiBase })
      return { ...msg, html }
    })
  }, [state.messages, state.apiBase, refs.markdownCacheRef])

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
    if (refs.skipAutoSessionLoadIdRef.current) {
      const skippedSessionId = refs.skipAutoSessionLoadIdRef.current
      refs.skipAutoSessionLoadIdRef.current = ''
      if (skippedSessionId === state.activeSessionId) return
    }
    if (state.pendingChatJob?.job_id) {
      if (state.pendingChatJob.session_id === state.activeSessionId) return
      void sessionManager.loadSessionMessages(state.activeSessionId, -1, false)
      return
    }
    if (state.sending) return
    void sessionManager.loadSessionMessages(state.activeSessionId, -1, false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.activeSessionId, state.verifiedStudent?.student_id, state.apiBase, state.pendingChatJob?.job_id, state.pendingChatJob?.session_id, state.forceSessionLoadToken])

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

  // ── Render ──
  return (
    <div className="app flex h-dvh flex-col bg-bg overflow-hidden" ref={appRef}>
      <StudentTopbar
        verifiedStudent={state.verifiedStudent}
        sidebarOpen={state.sidebarOpen}
        dispatch={dispatch}
        startNewStudentSession={sessionManager.startNewStudentSession}
      />
      <StudentLayout
        sidebarOpen={state.sidebarOpen}
        sidebar={
          <SessionSidebar
            apiBase={state.apiBase}
            sidebarOpen={state.sidebarOpen}
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
            onSelectSession={sessionManager.selectStudentSession}
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
            verifying={state.verifying}
            verifyError={state.verifyError}
            todayAssignment={state.todayAssignment}
            assignmentLoading={state.assignmentLoading}
            assignmentError={state.assignmentError}
            resetVerification={sessionManager.resetVerification}
            startNewStudentSession={sessionManager.startNewStudentSession}
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
        }
      />
    </div>
  )
}
