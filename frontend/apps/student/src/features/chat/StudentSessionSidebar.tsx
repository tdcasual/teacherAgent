import type { Dispatch, FormEvent, KeyboardEvent as ReactKeyboardEvent, SetStateAction } from 'react'
import { formatSessionUpdatedLabel } from '../../../../shared/time'
import { ConfirmDialog, PromptDialog } from '../../../../shared/dialog'
import type { AssignmentDetail, SessionGroup, StudentHistorySession, VerifiedStudent } from '../../appTypes'

const toDomSafeId = (value: string) => String(value || '').replace(/[^a-zA-Z0-9_-]/g, '_')

type Props = {
  apiBase: string
  sidebarOpen: boolean
  setSidebarOpen: Dispatch<SetStateAction<boolean>>

  verifiedStudent: VerifiedStudent | null
  historyLoading: boolean
  historyError: string
  historyHasMore: boolean
  refreshSessions: (mode?: 'more') => Promise<void>

  showArchivedSessions: boolean
  setShowArchivedSessions: Dispatch<SetStateAction<boolean>>

  historyQuery: string
  setHistoryQuery: Dispatch<SetStateAction<string>>

  visibleSessionCount: number
  groupedSessions: Array<SessionGroup<StudentHistorySession>>
  deletedSessionIds: string[]

  activeSessionId: string
  onSelectSession: (sessionId: string) => void
  getSessionTitle: (sessionId: string) => string

  openSessionMenuId: string
  toggleSessionMenu: (sessionId: string) => void
  handleSessionMenuTriggerKeyDown: (sessionId: string, isOpen: boolean, event: ReactKeyboardEvent<HTMLButtonElement>) => void
  handleSessionMenuKeyDown: (sessionId: string, event: ReactKeyboardEvent<HTMLDivElement>) => void
  setSessionMenuTriggerRef: (sessionId: string, node: HTMLButtonElement | null) => void
  setSessionMenuRef: (sessionId: string, node: HTMLDivElement | null) => void
  renameSession: (sessionId: string) => void
  toggleSessionArchive: (sessionId: string) => void

  sessionHasMore: boolean
  sessionLoading: boolean
  sessionCursor: number
  loadSessionMessages: (sessionId: string, cursor: number, append: boolean) => Promise<void>
  sessionError: string

  verifyOpen: boolean
  setVerifyOpen: Dispatch<SetStateAction<boolean>>
  handleVerify: (event: FormEvent) => void
  nameInput: string
  setNameInput: Dispatch<SetStateAction<string>>
  classInput: string
  setClassInput: Dispatch<SetStateAction<string>>
  verifying: boolean
  verifyError: string

  todayAssignment: AssignmentDetail | null
  assignmentLoading: boolean
  assignmentError: string
  todayDate: () => string

  resetVerification: () => void
  startNewStudentSession: () => void

  renameDialogSessionId: string | null
  archiveDialogSessionId: string | null
  archiveDialogActionLabel: string
  archiveDialogIsArchived: boolean
  cancelRenameDialog: () => void
  confirmRenameDialog: (nextTitle: string) => void
  cancelArchiveDialog: () => void
  confirmArchiveDialog: () => void
}

export default function StudentSessionSidebar(props: Props) {
  const {
    apiBase,
    sidebarOpen,
    setSidebarOpen,
    verifiedStudent,
    historyLoading,
    historyError,
    historyHasMore,
    refreshSessions,
    showArchivedSessions,
    setShowArchivedSessions,
    historyQuery,
    setHistoryQuery,
    visibleSessionCount,
    groupedSessions,
    deletedSessionIds,
    activeSessionId,
    onSelectSession,
    getSessionTitle,
    openSessionMenuId,
    toggleSessionMenu,
    handleSessionMenuTriggerKeyDown,
    handleSessionMenuKeyDown,
    setSessionMenuTriggerRef,
    setSessionMenuRef,
    renameSession,
    toggleSessionArchive,
    sessionHasMore,
    sessionLoading,
    sessionCursor,
    loadSessionMessages,
    sessionError,
    verifyOpen,
    setVerifyOpen,
    handleVerify,
    nameInput,
    setNameInput,
    classInput,
    setClassInput,
    verifying,
    verifyError,
    todayAssignment,
    assignmentLoading,
    assignmentError,
    todayDate,
    resetVerification,
    startNewStudentSession,
    renameDialogSessionId,
    archiveDialogSessionId,
    archiveDialogActionLabel,
    archiveDialogIsArchived,
    cancelRenameDialog,
    confirmRenameDialog,
    cancelArchiveDialog,
    confirmArchiveDialog,
  } = props

  return (
    <>
      <button
        type="button"
        className={`sidebar-overlay ${sidebarOpen ? 'show' : ''}`}
        aria-label="关闭会话侧栏"
        onClick={() => setSidebarOpen(false)}
      />
      <aside className={`session-sidebar ${sidebarOpen ? 'open' : 'collapsed'}`}>
        <div className="session-sidebar-header">
          <strong>历史会话</strong>
          <div className="session-sidebar-actions">
            <button type="button" className="ghost" onClick={startNewStudentSession}>
              新建
            </button>
            <button
              type="button"
              className="ghost"
              disabled={!verifiedStudent || historyLoading}
              onClick={() => void refreshSessions()}
            >
              {historyLoading ? '刷新中…' : '刷新'}
            </button>
            <button type="button" className="ghost" disabled={!verifiedStudent} onClick={() => setShowArchivedSessions((prev) => !prev)}>
              {showArchivedSessions ? '查看会话' : '查看归档'}
            </button>
          </div>
        </div>
        <div className="session-search">
          <input value={historyQuery} onChange={(e) => setHistoryQuery(e.target.value)} placeholder="搜索会话" disabled={!verifiedStudent} />
        </div>
        {!verifiedStudent && <div className="history-hint">请先完成姓名验证后查看历史记录。</div>}
        {historyError && <div className="status err">{historyError}</div>}
        {verifiedStudent && !historyLoading && visibleSessionCount === 0 && !historyError && (
          <div className="history-hint">{showArchivedSessions ? '暂无归档会话。' : '暂无历史记录。'}</div>
        )}
        <div className="session-groups">
          {groupedSessions.map((group) => (
            <div key={group.key} className="session-group">
              <div className="session-group-title">{group.label}</div>
              <div className="session-list">
                {group.items.map((item) => {
                  const sid = item.session_id
                  const isActive = sid === activeSessionId
                  const isMenuOpen = sid === openSessionMenuId
                  const isArchived = deletedSessionIds.includes(sid)
                  const menuDomIdBase = `student-session-menu-${toDomSafeId(sid)}`
                  const menuId = `${menuDomIdBase}-list`
                  const triggerId = `${menuDomIdBase}-trigger`
                  const updatedLabel = formatSessionUpdatedLabel(item.updated_at)
                  return (
                    <div key={sid} className={`session-item ${isActive ? 'active' : ''}`}>
                      <button
                        type="button"
                        className="session-select"
                        onClick={() => {
                          onSelectSession(sid)
                        }}
                      >
                        <div className="session-main">
                          <div className="session-id">{getSessionTitle(sid)}</div>
                          <div className="session-meta">
                            {(item.message_count || 0).toString()} 条{updatedLabel ? ` · ${updatedLabel}` : ''}
                          </div>
                        </div>
                        {item.preview ? <div className="session-preview">{item.preview}</div> : null}
                      </button>
                      <div className="session-menu-wrap">
                        <button
                          type="button"
                          id={triggerId}
                          ref={(node) => setSessionMenuTriggerRef(sid, node)}
                          className="session-menu-trigger"
                          aria-haspopup="menu"
                          aria-expanded={isMenuOpen}
                          aria-controls={menuId}
                          aria-label={`会话 ${getSessionTitle(sid)} 操作`}
                          onClick={(e) => {
                            e.stopPropagation()
                            toggleSessionMenu(sid)
                          }}
                          onKeyDown={(event) => handleSessionMenuTriggerKeyDown(sid, isMenuOpen, event)}
                        >
                          ⋯
                        </button>
                        {isMenuOpen ? (
                          <div
                            id={menuId}
                            ref={(node) => setSessionMenuRef(sid, node)}
                            className="session-menu"
                            role="menu"
                            aria-orientation="vertical"
                            aria-labelledby={triggerId}
                            onKeyDown={(event) => handleSessionMenuKeyDown(sid, event)}
                          >
                            <button
                              type="button"
                              role="menuitem"
                              className="session-menu-item"
                              onClick={() => {
                                renameSession(sid)
                              }}
                            >
                              重命名
                            </button>
                            <button
                              type="button"
                              role="menuitem"
                              className={`session-menu-item${isArchived ? '' : ' danger'}`}
                              onClick={() => {
                                toggleSessionArchive(sid)
                              }}
                            >
                              {isArchived ? '恢复' : '归档'}
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
        {verifiedStudent && (
          <div className="history-footer">
            <button type="button" className="ghost" disabled={!historyHasMore || historyLoading} onClick={() => void refreshSessions('more')}>
              {historyLoading ? '加载中…' : historyHasMore ? '加载更多会话' : '已显示全部会话'}
            </button>
          </div>
        )}
        {verifiedStudent && activeSessionId && (
          <div className="history-footer">
            <button
              type="button"
              className="ghost"
              disabled={!sessionHasMore || sessionLoading}
              onClick={() => void loadSessionMessages(activeSessionId, sessionCursor, true)}
            >
              {sessionLoading ? '加载中…' : sessionHasMore ? '加载更早消息' : '没有更早消息'}
            </button>
            {sessionError && <div className="status err">{sessionError}</div>}
          </div>
        )}

        <section className="student-side-card">
          <div className="student-side-header">
            <strong>学习信息</strong>
            <button type="button" className="ghost" onClick={() => setVerifyOpen((prev) => !prev)}>
              {verifyOpen ? '收起' : '展开'}
            </button>
          </div>
          {verifiedStudent ? (
            <div className="history-hint">
              已验证：{verifiedStudent.class_name ? `${verifiedStudent.class_name} · ` : ''}
              {verifiedStudent.student_name}
            </div>
          ) : (
            <div className="history-hint">请先完成姓名验证后开始提问。</div>
          )}
          {verifyOpen && (
            <form className="verify-form compact" onSubmit={handleVerify}>
              <div className="verify-row">
                <label>姓名</label>
                <input value={nameInput} onChange={(e) => setNameInput(e.target.value)} placeholder="例如：刘昊然" />
              </div>
              <div className="verify-row">
                <label>班级（重名时必填）</label>
                <input value={classInput} onChange={(e) => setClassInput(e.target.value)} placeholder="例如：高二2403班" />
              </div>
              <button type="submit" disabled={verifying}>
                {verifying ? '验证中…' : '确认身份'}
              </button>
              {verifyError && <div className="status err">{verifyError}</div>}
            </form>
          )}
          {verifiedStudent && (
            <div className="assignment-compact">
              <div className="assignment-meta">今日作业（{todayAssignment?.date || todayDate()}）</div>
              {assignmentLoading && <div className="assignment-status">加载中...</div>}
              {assignmentError && <div className="assignment-status err">{assignmentError}</div>}
              {!assignmentLoading && !todayAssignment && !assignmentError && <div className="assignment-empty">今日暂无作业。</div>}
              {todayAssignment && (
                <>
                  <div className="assignment-meta">
                    作业编号：{todayAssignment.assignment_id || '-'} · 题数：{todayAssignment.question_count || 0}
                  </div>
                  {todayAssignment.meta?.target_kp?.length ? (
                    <div className="assignment-meta">知识点：{todayAssignment.meta.target_kp.join('，')}</div>
                  ) : null}
                  {todayAssignment.delivery?.files?.length ? (
                    <div className="download-list">
                      {todayAssignment.delivery.files.map((file) => (
                        <a key={file.url} className="download-link" href={`${apiBase}${file.url}`} target="_blank" rel="noreferrer">
                          下载：{file.name}
                        </a>
                      ))}
                    </div>
                  ) : (
                    <div className="assignment-note">在聊天中输入“开始今天作业”进入讨论。</div>
                  )}
                </>
              )}
            </div>
          )}
          {verifiedStudent && (
            <button type="button" className="ghost" onClick={resetVerification}>
              重新验证
            </button>
          )}
        </section>
      </aside>

      <PromptDialog
        open={Boolean(renameDialogSessionId)}
        title="重命名会话"
        description="可留空以删除自定义名称。"
        label="会话名称"
        placeholder="输入会话名称"
        defaultValue={renameDialogSessionId ? getSessionTitle(renameDialogSessionId) : ''}
        confirmText="保存"
        onCancel={cancelRenameDialog}
        onConfirm={confirmRenameDialog}
      />
      <ConfirmDialog
        open={Boolean(archiveDialogSessionId)}
        title={`确认${archiveDialogActionLabel}会话？`}
        description={archiveDialogSessionId ? `会话：${getSessionTitle(archiveDialogSessionId)}` : undefined}
        confirmText={archiveDialogActionLabel}
        confirmTone={archiveDialogIsArchived ? 'primary' : 'danger'}
        cancelText="取消"
        onCancel={cancelArchiveDialog}
        onConfirm={confirmArchiveDialog}
      />
    </>
  )
}
