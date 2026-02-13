import SessionSidebarDialogs from './SessionSidebarDialogs'
import SessionSidebarHistorySection from './SessionSidebarHistorySection'
import SessionSidebarLearningSection from './SessionSidebarLearningSection'
import type { SessionSidebarProps } from './sessionSidebarTypes'

export default function SessionSidebar(props: SessionSidebarProps) {
  return (
    <>
      <button
        type="button"
        className={`sidebar-overlay ${props.sidebarOpen ? 'show' : ''}`}
        aria-label="关闭会话侧栏"
        onClick={() => props.dispatch({ type: 'SET', field: 'sidebarOpen', value: false })}
      />
      <aside id="student-session-sidebar" className={`session-sidebar ${props.sidebarOpen ? 'open' : 'collapsed'}`}>
        <SessionSidebarHistorySection
          dispatch={props.dispatch}
          verifiedStudent={props.verifiedStudent}
          historyLoading={props.historyLoading}
          historyError={props.historyError}
          historyHasMore={props.historyHasMore}
          refreshSessions={props.refreshSessions}
          showArchivedSessions={props.showArchivedSessions}
          historyQuery={props.historyQuery}
          visibleSessionCount={props.visibleSessionCount}
          groupedSessions={props.groupedSessions}
          deletedSessionIds={props.deletedSessionIds}
          activeSessionId={props.activeSessionId}
          onSelectSession={props.onSelectSession}
          getSessionTitle={props.getSessionTitle}
          openSessionMenuId={props.openSessionMenuId}
          toggleSessionMenu={props.toggleSessionMenu}
          handleSessionMenuTriggerKeyDown={props.handleSessionMenuTriggerKeyDown}
          handleSessionMenuKeyDown={props.handleSessionMenuKeyDown}
          setSessionMenuTriggerRef={props.setSessionMenuTriggerRef}
          setSessionMenuRef={props.setSessionMenuRef}
          renameSession={props.renameSession}
          toggleSessionArchive={props.toggleSessionArchive}
          sessionHasMore={props.sessionHasMore}
          sessionLoading={props.sessionLoading}
          sessionCursor={props.sessionCursor}
          loadSessionMessages={props.loadSessionMessages}
          sessionError={props.sessionError}
          startNewStudentSession={props.startNewStudentSession}
        />
        <SessionSidebarLearningSection
          apiBase={props.apiBase}
          dispatch={props.dispatch}
          verifiedStudent={props.verifiedStudent}
          verifyOpen={props.verifyOpen}
          handleVerify={props.handleVerify}
          handleSetPassword={props.handleSetPassword}
          nameInput={props.nameInput}
          classInput={props.classInput}
          credentialInput={props.credentialInput}
          credentialType={props.credentialType}
          newPasswordInput={props.newPasswordInput}
          verifying={props.verifying}
          settingPassword={props.settingPassword}
          verifyError={props.verifyError}
          verifyInfo={props.verifyInfo}
          todayAssignment={props.todayAssignment}
          assignmentLoading={props.assignmentLoading}
          assignmentError={props.assignmentError}
          resetVerification={props.resetVerification}
        />
      </aside>
      <SessionSidebarDialogs
        renameDialogSessionId={props.renameDialogSessionId}
        archiveDialogSessionId={props.archiveDialogSessionId}
        getSessionTitle={props.getSessionTitle}
        archiveDialogActionLabel={props.archiveDialogActionLabel}
        archiveDialogIsArchived={props.archiveDialogIsArchived}
        cancelRenameDialog={props.cancelRenameDialog}
        confirmRenameDialog={props.confirmRenameDialog}
        cancelArchiveDialog={props.cancelArchiveDialog}
        confirmArchiveDialog={props.confirmArchiveDialog}
      />
    </>
  )
}
