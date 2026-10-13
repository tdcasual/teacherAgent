import {
  Suspense,
  useCallback,
  useMemo,
  type ComponentType,
  type Dispatch,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from 'react';
import type { ComposerAttachment } from '../../../../shared/useChatAttachments';
import type {
  RenderedMessage,
  StudentAssignmentHistoryItem,
  StudentTodayHomeViewModel,
} from '../../appTypes';
import {
  coerceAssignmentKind,
  parseAllowPractice,
  type AssignmentKind,
} from '../../assignmentKind';
import type { StudentNavigation } from '../../hooks/useStudentNavigation';
import type { StudentAction, StudentState } from '../../hooks/useStudentState';
import SessionSidebar from '../chat/SessionSidebar';
import SessionSidebarDialogs from '../chat/SessionSidebarDialogs';
import SessionSidebarHistorySection from '../chat/SessionSidebarHistorySection';
import SessionSidebarLearningSection from '../chat/SessionSidebarLearningSection';
import type { SessionSidebarProps } from '../chat/sessionSidebarTypes';
import { matchReadyChatFiles, type StudentSubmitResult } from '../submit/studentSubmit';

type SessionManagerSlice = Pick<
  SessionSidebarProps,
  | 'refreshSessions'
  | 'groupedSessions'
  | 'getSessionTitle'
  | 'renameSession'
  | 'toggleSessionArchive'
  | 'loadSessionMessages'
  | 'resetVerification'
  | 'archiveDialogActionLabel'
  | 'archiveDialogIsArchived'
  | 'cancelRenameDialog'
  | 'confirmRenameDialog'
  | 'cancelArchiveDialog'
  | 'confirmArchiveDialog'
> & {
  visibleSessions: { length: number };
  selectStudentSession: (sessionId: string) => void;
};

type SidebarMenuSlice = Pick<
  SessionSidebarProps,
  | 'toggleSessionMenu'
  | 'handleSessionMenuTriggerKeyDown'
  | 'handleSessionMenuKeyDown'
  | 'setSessionMenuTriggerRef'
  | 'setSessionMenuRef'
>;

type ChatSlice = {
  renderedMessages: RenderedMessage[];
  messagesRef: RefObject<HTMLDivElement | null>;
  endRef: RefObject<HTMLDivElement | null>;
  isNearBottom: boolean;
  scrollToBottom: () => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  setInput: (value: string) => void;
  handleInputKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  handleSend: (event: FormEvent) => void;
  composerHint: string;
  attachments: ComposerAttachment[];
  uploadingAttachments: boolean;
  hasSendableAttachments: boolean;
  onPickFiles: (files: File[]) => void | Promise<void>;
  onRemoveAttachment: (localId: string) => void | Promise<void>;
  chatPickedFiles: File[];
};

type StudentAppPages = {
  StudentTodayHome: ComponentType<{
    dateLabel: string;
    viewModel: StudentTodayHomeViewModel;
    onPrimaryAction: () => void;
    onOpenAssignment: (assignmentId: string) => void;
    onOpenHistory: () => void;
    onOpenFreeChat: () => void;
    onOpenAssignmentHistory: () => void;
    onOpenSubmit: (assignmentId: string) => void;
  }>;
  StudentAssignmentHistoryPage: ComponentType<{
    items: StudentAssignmentHistoryItem[];
    loading: boolean;
    error: string;
    apiBase: string;
    studentId: string;
    onBack: () => void;
    onSubmit: (assignmentId: string) => void;
    onOpenAssignment: (assignmentId: string) => void;
  }>;
  StudentSubmitPanel: ComponentType<{
    apiBase: string;
    studentId: string;
    assignmentId: string;
    assignmentTitle: string;
    assignmentKind?: AssignmentKind;
    allowPractice?: boolean;
    chatFiles: File[];
    onClose: () => void;
    onSubmitted: (result: StudentSubmitResult) => void;
  }>;
  ChatPanel: ComponentType<{
    assignmentKind?: string;
    renderedMessages: RenderedMessage[];
    sending: boolean;
    pendingChatJobId: string;
    verifiedStudent: StudentState['verifiedStudent'];
    messagesRef: RefObject<HTMLDivElement | null>;
    endRef: RefObject<HTMLDivElement | null>;
    isNearBottom: boolean;
    scrollToBottom: () => void;
    inputRef: RefObject<HTMLTextAreaElement | null>;
    input: string;
    setInput: (value: string) => void;
    handleInputKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
    handleSend: (event: FormEvent) => void;
    composerHint: string;
    attachments: ComposerAttachment[];
    uploadingAttachments: boolean;
    hasSendableAttachments: boolean;
    onPickFiles: (files: File[]) => void | Promise<void>;
    onRemoveAttachment: (localId: string) => void | Promise<void>;
    onOpenSubmit?: () => void;
  }>;
};

type StudentAppContentParams = {
  state: StudentState;
  dispatch: Dispatch<StudentAction>;
  handleVerify: (event: FormEvent) => void;
  pageFallback: ReactNode;
  pages: StudentAppPages;
  assignmentHistory: {
    items: StudentAssignmentHistoryItem[];
    loading: boolean;
    error: string;
    reload: () => void | Promise<void>;
  };
  todayHomeViewModel: StudentTodayHomeViewModel;
  navigation: StudentNavigation;
  sessionManager: SessionManagerSlice;
  sidebarMenu: SidebarMenuSlice;
  chat: ChatSlice;
};

export function useStudentAppContent({
  state,
  dispatch,
  handleVerify,
  pageFallback,
  pages,
  assignmentHistory,
  todayHomeViewModel,
  navigation,
  sessionManager,
  sidebarMenu,
  chat,
}: StudentAppContentParams) {
  const {
    studentUseMobileShellV2,
    mobileTab,
    submitAssignmentId,
    assignmentHistoryOpen,
    setHomeOpen,
    setMobileSessionListOpen,
    setMobileTab,
    setSubmitAssignmentId,
    setAssignmentHistoryOpen,
    handleOpenAssignment,
    handleOpenSubmit,
    handlePrimaryHomeAction,
    handleOpenHistory,
    handleOpenFreeChat,
    handleOpenAssignmentHistory,
    handleStartNewStudentSession,
  } = navigation;
  const { StudentTodayHome, StudentAssignmentHistoryPage, StudentSubmitPanel, ChatPanel } = pages;

  const heroDateLabel = useMemo(() => {
    const now = new Date();
    return now.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' });
  }, []);

  const submitRow = useMemo(() => {
    return (
      state.todayAssignments.find((item) => item.assignment_id === submitAssignmentId) ||
      assignmentHistory.items.find((item) => item.assignment_id === submitAssignmentId) ||
      null
    );
  }, [assignmentHistory.items, state.todayAssignments, submitAssignmentId]);
  const selectedRow = useMemo(() => {
    return (
      state.todayAssignments.find((item) => item.assignment_id === state.selectedAssignmentId) ||
      assignmentHistory.items.find((item) => item.assignment_id === state.selectedAssignmentId) ||
      null
    );
  }, [assignmentHistory.items, state.todayAssignments, state.selectedAssignmentId]);
  const submitTitle = submitRow?.title || submitAssignmentId;
  const submitKind = submitRow ? coerceAssignmentKind(submitRow.assignment_kind) : undefined;
  const submitAllowPractice = submitRow
    ? parseAllowPractice(submitRow.allow_practice, coerceAssignmentKind(submitRow.assignment_kind))
    : false;

  const handleSubmitCompleted = useCallback(() => {
    dispatch({
      type: 'SET',
      field: 'assignmentRefreshNonce',
      value: state.assignmentRefreshNonce + 1,
    });
    void assignmentHistory.reload();
  }, [assignmentHistory, dispatch, state.assignmentRefreshNonce]);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      setHomeOpen(false);
      if (studentUseMobileShellV2) {
        setMobileSessionListOpen(false);
        setMobileTab('chat');
      }
      sessionManager.selectStudentSession(sessionId);
    },
    [sessionManager, setHomeOpen, setMobileSessionListOpen, setMobileTab, studentUseMobileShellV2],
  );

  const sessionSidebarContent = (
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
      onSelectSession={handleSelectSession}
      getSessionTitle={sessionManager.getSessionTitle}
      openSessionMenuId={state.openSessionMenuId}
      toggleSessionMenu={sidebarMenu.toggleSessionMenu}
      handleSessionMenuTriggerKeyDown={sidebarMenu.handleSessionMenuTriggerKeyDown}
      handleSessionMenuKeyDown={sidebarMenu.handleSessionMenuKeyDown}
      setSessionMenuTriggerRef={sidebarMenu.setSessionMenuTriggerRef}
      setSessionMenuRef={sidebarMenu.setSessionMenuRef}
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
      todayAssignments={state.todayAssignments}
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
  );

  const submitPanel = submitAssignmentId ? (
    <StudentSubmitPanel
      apiBase={state.apiBase}
      studentId={state.verifiedStudent?.student_id || ''}
      assignmentId={submitAssignmentId}
      assignmentTitle={submitTitle}
      assignmentKind={submitKind}
      allowPractice={submitAllowPractice}
      chatFiles={matchReadyChatFiles(
        chat.attachments.filter((item) => item.status === 'ready'),
        chat.chatPickedFiles,
      )}
      onClose={() => setSubmitAssignmentId('')}
      onSubmitted={handleSubmitCompleted}
    />
  ) : null;

  const historyPage = (
    <StudentAssignmentHistoryPage
      items={assignmentHistory.items}
      loading={assignmentHistory.loading}
      error={assignmentHistory.error}
      apiBase={state.apiBase}
      studentId={state.verifiedStudent?.student_id || ''}
      onBack={() => setAssignmentHistoryOpen(false)}
      onSubmit={handleOpenSubmit}
      onOpenAssignment={handleOpenAssignment}
    />
  );

  const todayHomeContent = (
    <StudentTodayHome
      dateLabel={heroDateLabel}
      viewModel={todayHomeViewModel}
      onPrimaryAction={handlePrimaryHomeAction}
      onOpenAssignment={handleOpenAssignment}
      onOpenHistory={handleOpenHistory}
      onOpenFreeChat={handleOpenFreeChat}
      onOpenAssignmentHistory={handleOpenAssignmentHistory}
      onOpenSubmit={handleOpenSubmit}
    />
  );

  const learningContent = (
    <Suspense fallback={pageFallback}>
      {submitPanel || (assignmentHistoryOpen ? historyPage : todayHomeContent)}
    </Suspense>
  );

  const chatContent = (
    <Suspense fallback={pageFallback}>
      <ChatPanel
        assignmentKind={selectedRow ? coerceAssignmentKind(selectedRow.assignment_kind) : undefined}
        renderedMessages={chat.renderedMessages}
        sending={state.sending}
        pendingChatJobId={state.pendingChatJob?.job_id || ''}
        verifiedStudent={state.verifiedStudent}
        messagesRef={chat.messagesRef}
        endRef={chat.endRef}
        isNearBottom={chat.isNearBottom}
        scrollToBottom={chat.scrollToBottom}
        inputRef={chat.inputRef}
        input={state.input}
        setInput={chat.setInput}
        handleInputKeyDown={chat.handleInputKeyDown}
        handleSend={chat.handleSend}
        composerHint={chat.composerHint}
        attachments={chat.attachments}
        uploadingAttachments={chat.uploadingAttachments}
        hasSendableAttachments={chat.hasSendableAttachments}
        onPickFiles={chat.onPickFiles}
        onRemoveAttachment={chat.onRemoveAttachment}
        onOpenSubmit={
          state.selectedAssignmentId
            ? () => handleOpenSubmit(state.selectedAssignmentId)
            : undefined
        }
      />
    </Suspense>
  );

  const mobileLearningContent =
    state.verifyOpen || !state.verifiedStudent ? (
      <main
        className="student-mobile-stage student-mobile-learning-stage"
        data-testid="student-learning-overview-panel"
      >
        <div className="student-mobile-pane">
          <SessionSidebarLearningSection
            apiBase={state.apiBase}
            dispatch={dispatch}
            verifiedStudent={state.verifiedStudent}
            verifyOpen={state.verifyOpen}
            handleVerify={handleVerify}
            nameInput={state.nameInput}
            classInput={state.classInput}
            credentialInput={state.credentialInput}
            verifying={state.verifying}
            verifyError={state.verifyError}
            verifyInfo={state.verifyInfo}
            todayAssignment={state.todayAssignment}
            todayAssignments={state.todayAssignments}
            assignmentLoading={state.assignmentLoading}
            assignmentError={state.assignmentError}
            resetVerification={sessionManager.resetVerification}
          />
        </div>
      </main>
    ) : (
      learningContent
    );

  const mobileSessionsContent = (
    <main
      className="student-mobile-stage student-mobile-sessions-stage"
      data-testid="student-session-list-panel"
    >
      <SessionSidebarHistorySection
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
        onSelectSession={handleSelectSession}
        getSessionTitle={sessionManager.getSessionTitle}
        openSessionMenuId={state.openSessionMenuId}
        toggleSessionMenu={sidebarMenu.toggleSessionMenu}
        handleSessionMenuTriggerKeyDown={sidebarMenu.handleSessionMenuTriggerKeyDown}
        handleSessionMenuKeyDown={sidebarMenu.handleSessionMenuKeyDown}
        setSessionMenuTriggerRef={sidebarMenu.setSessionMenuTriggerRef}
        setSessionMenuRef={sidebarMenu.setSessionMenuRef}
        renameSession={sessionManager.renameSession}
        toggleSessionArchive={sessionManager.toggleSessionArchive}
        sessionHasMore={state.sessionHasMore}
        sessionLoading={state.sessionLoading}
        sessionCursor={state.sessionCursor}
        loadSessionMessages={sessionManager.loadSessionMessages}
        sessionError={state.sessionError}
        startNewStudentSession={handleStartNewStudentSession}
      />
    </main>
  );

  const sessionDialogs = (
    <SessionSidebarDialogs
      renameDialogSessionId={state.renameDialogSessionId}
      archiveDialogSessionId={state.archiveDialogSessionId}
      getSessionTitle={sessionManager.getSessionTitle}
      archiveDialogActionLabel={sessionManager.archiveDialogActionLabel}
      archiveDialogIsArchived={sessionManager.archiveDialogIsArchived}
      cancelRenameDialog={sessionManager.cancelRenameDialog}
      confirmRenameDialog={sessionManager.confirmRenameDialog}
      cancelArchiveDialog={sessionManager.cancelArchiveDialog}
      confirmArchiveDialog={sessionManager.confirmArchiveDialog}
    />
  );

  return {
    sessionSidebarContent,
    learningContent,
    chatContent,
    mobileLearningContent,
    mobileSessionsContent,
    sessionDialogs,
  };
}
