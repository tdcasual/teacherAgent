import { lazy, useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import {
  renderMarkdown,
  absolutizeChartImageUrls,
  renderStreamingPlainText,
} from '../../shared/markdown';
import {
  useSmartAutoScroll,
  useScrollPositionLock,
  evictOldestEntries,
} from '../../shared/useSmartAutoScroll';
import type { Message, PendingChatJob, RenderedMessage } from './appTypes';
import { useStudentState, PENDING_CHAT_KEY_PREFIX, todayDate } from './hooks/useStudentState';
import { useVerification } from './hooks/useVerification';
import { useSessionManager } from './hooks/useSessionManager';
import { useChatPolling } from './hooks/useChatPolling';
import { useAssignment } from './hooks/useAssignment';
import { useAssignmentHistory } from './hooks/useAssignmentHistory';
import { useStudentSendFlow } from './features/chat/useStudentSendFlow';
import { selectComposerHint } from './features/chat/studentUiSelectors';
import { buildStudentTodayHomeViewModel } from './features/home/studentTodayHomeState';
import { useStudentSessionSidebarState } from './features/session/useStudentSessionSidebarState';
import { useStudentSessionViewStateSync } from './features/session/useStudentSessionViewStateSync';
import { useChatAttachments } from '../../shared/useChatAttachments';
import { useStudentNavigation } from './hooks/useStudentNavigation';
import { useStudentAppContent } from './features/layout/studentAppContent';
import StudentDesktopShell from './features/layout/StudentDesktopShell';
import StudentMobileShell from './features/layout/StudentMobileShell';

const StudentTodayHome = lazy(() => import('./features/home/StudentTodayHome'));
const StudentAssignmentHistoryPage = lazy(
  () => import('./features/history/StudentAssignmentHistoryPage'),
);
const StudentSubmitPanel = lazy(() => import('./features/submit/StudentSubmitPanel'));
const ChatPanel = lazy(() => import('./features/chat/ChatPanel'));
const pageFallback = <div className="flex-1 min-h-0 bg-app-bg" aria-busy="true" />;

export default function App() {
  const { state, dispatch, refs, setActiveSession } = useStudentState();
  const appRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [chatPickedFiles, setChatPickedFiles] = useState<File[]>([]);
  const { messagesRef, endRef, isNearBottom, scrollToBottom, autoScroll } = useSmartAutoScroll();
  const { saveScrollHeight, restoreScrollPosition } = useScrollPositionLock(messagesRef);

  const { viewStateSyncReady } = useStudentSessionViewStateSync({
    state,
    dispatch,
    setActiveSession,
  });
  const { handleVerify } = useVerification({ state, dispatch });
  useAssignment({ state, dispatch });

  const sessionManager = useSessionManager({
    state,
    dispatch,
    refs,
    setActiveSession,
    saveScrollHeight,
    restoreScrollPosition,
  });

  useChatPolling({
    state,
    dispatch,
    refs,
    setActiveSession,
    refreshSessions: sessionManager.refreshSessions,
  });

  const sidebarMenu = useStudentSessionSidebarState({
    sidebarOpen: state.sidebarOpen,
    openSessionMenuId: state.openSessionMenuId,
    dispatch,
  });

  const renderedMessages = useMemo(() => {
    const cache = refs.markdownCacheRef.current;
    evictOldestEntries(cache);
    const pendingPlaceholderId = state.pendingChatJob?.job_id
      ? String(state.pendingChatJob.placeholder_id || '').trim()
      : '';
    return state.messages.map((msg): RenderedMessage => {
      if (pendingPlaceholderId && msg.id === pendingPlaceholderId) {
        return { ...msg, html: renderStreamingPlainText(msg.content) };
      }
      const cached = cache.get(msg.id);
      if (cached && cached.content === msg.content && cached.apiBase === state.apiBase)
        return { ...msg, html: cached.html };
      const html = absolutizeChartImageUrls(renderMarkdown(msg.content), state.apiBase);
      cache.set(msg.id, { content: msg.content, html, apiBase: state.apiBase });
      return { ...msg, html };
    });
  }, [
    state.messages,
    state.apiBase,
    state.pendingChatJob?.job_id,
    state.pendingChatJob?.placeholder_id,
    refs.markdownCacheRef,
  ]);

  useEffect(() => {
    autoScroll();
  }, [state.messages, state.sending, autoScroll]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = '0px';
    const next = Math.min(220, Math.max(56, el.scrollHeight));
    el.style.height = `${next}px`;
  }, [state.input, state.verifiedStudent, state.pendingChatJob?.job_id]);

  useEffect(() => {
    if (!state.verifiedStudent?.student_id) return;
    if (!viewStateSyncReady) return;
    if (state.pendingChatJob?.job_id) return;
    if (state.activeSessionId) return;
    const next = `general_${todayDate()}`;
    setActiveSession(next);
  }, [
    state.verifiedStudent?.student_id,
    state.pendingChatJob?.job_id,
    state.activeSessionId,
    viewStateSyncReady,
    setActiveSession,
  ]);

  useEffect(() => {
    if (!state.verifiedStudent?.student_id) return;
    if (!state.activeSessionId) return;
    const forceTriggeredBySessionSelect =
      state.forceSessionLoadToken !== refs.lastHandledForceSessionLoadTokenRef.current;
    if (forceTriggeredBySessionSelect)
      refs.lastHandledForceSessionLoadTokenRef.current = state.forceSessionLoadToken;
    if (refs.skipAutoSessionLoadIdRef.current) {
      const skippedSessionId = refs.skipAutoSessionLoadIdRef.current;
      refs.skipAutoSessionLoadIdRef.current = '';
      if (skippedSessionId === state.activeSessionId) return;
    }
    if (state.pendingChatJob?.job_id) {
      const pendingMatchesActiveSession = state.pendingChatJob.session_id === state.activeSessionId;
      const hasLoadedActiveSessionHistory = state.sessionCursor !== 0;
      if (
        pendingMatchesActiveSession &&
        !forceTriggeredBySessionSelect &&
        hasLoadedActiveSessionHistory
      )
        return;
      void sessionManager.loadSessionMessages(state.activeSessionId, -1, false);
      return;
    }
    if (state.sending) return;
    void sessionManager.loadSessionMessages(state.activeSessionId, -1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    state.activeSessionId,
    state.verifiedStudent?.student_id,
    state.apiBase,
    state.pendingChatJob?.job_id,
    state.pendingChatJob?.session_id,
    state.forceSessionLoadToken,
    state.sessionCursor,
  ]);

  useEffect(() => {
    refs.activeSessionRef.current = state.activeSessionId;
  }, [state.activeSessionId, refs.activeSessionRef]);

  const setSending = useCallback(
    (v: boolean) => dispatch({ type: 'SET', field: 'sending', value: v }),
    [dispatch],
  );
  const setInput = useCallback(
    (v: string) => dispatch({ type: 'SET', field: 'input', value: v }),
    [dispatch],
  );
  const setPendingChatJob = useCallback(
    (v: PendingChatJob | null) => dispatch({ type: 'SET', field: 'pendingChatJob', value: v }),
    [dispatch],
  );
  const setVerifyError = useCallback(
    (v: string) => dispatch({ type: 'SET', field: 'verifyError', value: v }),
    [dispatch],
  );
  const setVerifyOpen = useCallback(
    (v: boolean) => dispatch({ type: 'SET', field: 'verifyOpen', value: v }),
    [dispatch],
  );
  const setMessages = useCallback(
    (v: Message[] | ((prev: Message[]) => Message[])) => {
      if (typeof v === 'function') dispatch({ type: 'UPDATE_MESSAGES', updater: v });
      else dispatch({ type: 'SET', field: 'messages', value: v });
    },
    [dispatch],
  );
  const updateMessage = useCallback(
    (id: string, patch: Partial<Message>) => {
      dispatch({
        type: 'UPDATE_MESSAGES',
        updater: (prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)),
      });
    },
    [dispatch],
  );

  const attachmentSessionId = state.activeSessionId || `general_${todayDate()}`;
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
  });
  const keepReadyAttachmentsOnSend = useCallback(() => {}, []);
  const handlePickFiles = useCallback(
    async (files: File[]) => {
      if (files.length) setChatPickedFiles((prev) => [...prev, ...files]);
      await addFiles(files);
    },
    [addFiles],
  );
  const handleRemoveAttachment = useCallback(
    async (localId: string) => {
      const target = attachments.find((item) => item.localId === localId);
      if (target?.fileName) {
        setChatPickedFiles((prev) => {
          const index = prev.findIndex((file) => file.name === target.fileName);
          if (index < 0) return prev;
          return prev.filter((_, itemIndex) => itemIndex !== index);
        });
      }
      await removeAttachment(localId);
    },
    [attachments, removeAttachment],
  );

  useEffect(() => {
    setChatPickedFiles([]);
  }, [attachmentSessionId]);

  useEffect(() => {
    const keepNames = attachments
      .filter((item) => item.status === 'ready' || item.status === 'uploading')
      .map((item) => item.fileName);
    setChatPickedFiles((prev) => {
      const remaining = [...keepNames];
      const next = prev.filter((file) => {
        const index = remaining.indexOf(file.name);
        if (index < 0) return false;
        remaining.splice(index, 1);
        return true;
      });
      if (next.length === prev.length && next.every((file, index) => file === prev[index]))
        return prev;
      return next;
    });
  }, [attachments]);

  const { handleSend } = useStudentSendFlow({
    apiBase: state.apiBase,
    input: state.input,
    messages: state.messages,
    activeSessionId: state.activeSessionId,
    selectedAssignmentId: state.selectedAssignmentId,
    sessions: state.sessions,
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
  });

  const composerHint = useMemo(
    () =>
      selectComposerHint({
        verifiedStudent: state.verifiedStudent,
        pendingChatJobId: state.pendingChatJob?.job_id || '',
        sending: state.sending,
      }),
    [state.pendingChatJob?.job_id, state.sending, state.verifiedStudent],
  );

  const todayHomeViewModel = useMemo(
    () =>
      buildStudentTodayHomeViewModel({
        verifiedStudent: state.verifiedStudent,
        assignmentLoading: state.assignmentLoading,
        assignmentError: state.assignmentError,
        todayAssignments: state.todayAssignments,
        activeSessionId: state.activeSessionId,
        messages: state.messages,
        pendingChatJob: state.pendingChatJob,
      }),
    [
      state.activeSessionId,
      state.assignmentError,
      state.assignmentLoading,
      state.messages,
      state.pendingChatJob,
      state.todayAssignments,
      state.verifiedStudent,
    ],
  );

  const handleInputKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key !== 'Enter') return;
      if (event.shiftKey) return;
      if (event.nativeEvent.isComposing) return;
      event.preventDefault();
      if (!state.verifiedStudent) return;
      if (state.sending || state.pendingChatJob?.job_id) return;
      if (!state.input.trim() && !hasSendableAttachments) return;
      event.currentTarget.form?.requestSubmit();
    },
    [
      state.verifiedStudent,
      state.sending,
      state.pendingChatJob?.job_id,
      state.input,
      hasSendableAttachments,
    ],
  );

  const nav = useStudentNavigation({
    dispatch,
    verifiedStudent: state.verifiedStudent,
    sidebarOpen: state.sidebarOpen,
    verifyOpen: state.verifyOpen,
    setActiveSession,
    todayHomeViewModel,
    startNewStudentSession: sessionManager.startNewStudentSession,
  });

  const assignmentHistory = useAssignmentHistory({
    apiBase: state.apiBase,
    studentId: state.verifiedStudent?.student_id || '',
    enabled: nav.assignmentHistoryOpen,
  });

  const content = useStudentAppContent({
    state,
    dispatch,
    handleVerify,
    pageFallback,
    pages: { StudentTodayHome, StudentAssignmentHistoryPage, StudentSubmitPanel, ChatPanel },
    assignmentHistory,
    todayHomeViewModel,
    navigation: nav,
    sessionManager,
    sidebarMenu,
    chat: {
      renderedMessages,
      messagesRef,
      endRef,
      isNearBottom,
      scrollToBottom,
      inputRef,
      setInput,
      handleInputKeyDown,
      handleSend,
      composerHint,
      attachments,
      uploadingAttachments,
      hasSendableAttachments,
      onPickFiles: handlePickFiles,
      onRemoveAttachment: handleRemoveAttachment,
      chatPickedFiles,
    },
  });

  if (nav.studentUseMobileShellV2) {
    return (
      <StudentMobileShell
        appRef={appRef}
        mobileShellV2Enabled={nav.mobileShellV2Enabled}
        verifiedStudent={state.verifiedStudent}
        sidebarOpen={state.sidebarOpen}
        homeOpen={nav.homeOpen}
        dispatch={dispatch}
        openTodayHome={nav.openTodayHome}
        startNewStudentSession={nav.handleStartNewStudentSession}
        mobileTab={nav.mobileTab}
        onMobileTabChange={nav.handleMobileTabChange}
        mobileLearningContent={content.mobileLearningContent}
        mobileSessionsContent={content.mobileSessionsContent}
        chatContent={content.chatContent}
        sessionDialogs={content.sessionDialogs}
      />
    );
  }

  return (
    <StudentDesktopShell
      appRef={appRef}
      mobileShellV2Enabled={nav.mobileShellV2Enabled}
      verifiedStudent={state.verifiedStudent}
      sidebarOpen={state.sidebarOpen}
      homeOpen={nav.homeOpen}
      assignmentHistoryOpen={nav.assignmentHistoryOpen}
      submitAssignmentId={nav.submitAssignmentId}
      dispatch={dispatch}
      openTodayHome={nav.openTodayHome}
      startNewStudentSession={nav.handleStartNewStudentSession}
      sidebar={content.sessionSidebarContent}
      learningContent={content.learningContent}
      chatContent={content.chatContent}
    />
  );
}
