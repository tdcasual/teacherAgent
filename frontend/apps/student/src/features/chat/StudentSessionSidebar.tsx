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
        <div className="flex justify-between items-center gap-1.5 max-[900px]:sticky max-[900px]:top-0 max-[900px]:z-1 max-[900px]:bg-white max-[900px]:pb-1.5">
          <strong>历史会话</strong>
          <div className="flex items-center gap-1.5 [&_.ghost]:px-[9px] [&_.ghost]:py-1 [&_.ghost]:text-[11px]">
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
        <div className="grid gap-1.5 max-[900px]:sticky max-[900px]:top-[34px] max-[900px]:z-1 max-[900px]:bg-white max-[900px]:pb-1">
          <input className="!px-2.5 !py-2 !rounded-[10px] !text-[13px]" value={historyQuery} onChange={(e) => setHistoryQuery(e.target.value)} placeholder="搜索会话" disabled={!verifiedStudent} />
        </div>
        {!verifiedStudent && <div className="text-xs text-muted">请先完成姓名验证后查看历史记录。</div>}
        {historyError && <div className="status err">{historyError}</div>}
        {verifiedStudent && !historyLoading && visibleSessionCount === 0 && !historyError && (
          <div className="text-xs text-muted">{showArchivedSessions ? '暂无归档会话。' : '暂无历史记录。'}</div>
        )}
        <div className="session-groups flex flex-col gap-2 overflow-auto min-h-0 flex-1 pr-1">
          {groupedSessions.map((group) => (
            <div key={group.key} className="flex flex-col gap-1">
              <div className="text-xs text-muted px-0.5">{group.label}</div>
              <div className="flex flex-col gap-1.5">
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
                    <div
                      key={sid}
                      className={`relative rounded-xl border px-2.5 py-2 transition-[border-color,background] duration-150 max-[900px]:px-[9px] max-[900px]:py-2 ${
                        isActive
                          ? 'border-[#86d6c4] bg-[#f4fbf8]'
                          : 'border-border bg-white hover:border-[#cfd4dc] hover:bg-[#fcfcfd]'
                      }`}
                    >
                      <button
                        type="button"
                        className="w-full border-none bg-transparent pr-7 text-left cursor-pointer block"
                        onClick={() => onSelectSession(sid)}
                      >
                        <div className="grid gap-0.5">
                          <div className="text-[13px] font-semibold text-ink leading-[1.35] whitespace-nowrap overflow-hidden text-ellipsis">{getSessionTitle(sid)}</div>
                          <div className="text-[11px] text-muted leading-[1.3]">
                            {(item.message_count || 0).toString()} 条{updatedLabel ? ` · ${updatedLabel}` : ''}
                          </div>
                        </div>
                        {item.preview ? <div className="text-xs text-muted mt-0.5 whitespace-nowrap overflow-hidden text-ellipsis">{item.preview}</div> : null}
                      </button>
                      <div className="absolute top-1.5 right-1.5">
                        <button
                          type="button"
                          id={triggerId}
                          ref={(node) => setSessionMenuTriggerRef(sid, node)}
                          className="w-[22px] h-[22px] border border-transparent rounded-full bg-transparent text-[#6b7280] cursor-pointer grid place-items-center text-base leading-none hover:bg-surface-soft hover:border-border hover:text-[#374151] aria-expanded:bg-surface-soft aria-expanded:border-border aria-expanded:text-[#374151]"
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
                            className="absolute top-[26px] right-0 min-w-[102px] border border-border rounded-[10px] bg-white shadow-sm p-1 grid gap-0.5 z-2 max-[900px]:min-w-[112px]"
                            role="menu"
                            aria-orientation="vertical"
                            aria-labelledby={triggerId}
                            onKeyDown={(event) => handleSessionMenuKeyDown(sid, event)}
                          >
                            <button
                              type="button"
                              role="menuitem"
                              className="session-menu-item border-none bg-transparent rounded-lg px-[9px] py-[7px] text-xs text-left text-[#374151] cursor-pointer hover:bg-surface-soft"
                              onClick={() => renameSession(sid)}
                            >
                              重命名
                            </button>
                            <button
                              type="button"
                              role="menuitem"
                              className={`session-menu-item border-none bg-transparent rounded-lg px-[9px] py-[7px] text-xs text-left cursor-pointer ${isArchived ? 'text-[#374151] hover:bg-surface-soft' : 'text-[#b42318] hover:bg-[#fff1f1]'}`}
                              onClick={() => toggleSessionArchive(sid)}
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
          <div className="flex gap-2 items-start flex-wrap">
            <button type="button" className="ghost" disabled={!historyHasMore || historyLoading} onClick={() => void refreshSessions('more')}>
              {historyLoading ? '加载中…' : historyHasMore ? '加载更多会话' : '已显示全部会话'}
            </button>
          </div>
        )}
        {verifiedStudent && activeSessionId && (
          <div className="flex gap-2 items-start flex-wrap">
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

        <section className="border-t border-border pt-2.5 grid gap-2">
          <div className="flex justify-between items-center gap-2">
            <strong>学习信息</strong>
            <button type="button" className="ghost" onClick={() => setVerifyOpen((prev) => !prev)}>
              {verifyOpen ? '收起' : '展开'}
            </button>
          </div>
          {verifiedStudent ? (
            <div className="text-xs text-muted">
              已验证：{verifiedStudent.class_name ? `${verifiedStudent.class_name} · ` : ''}
              {verifiedStudent.student_name}
            </div>
          ) : (
            <div className="text-xs text-muted">请先完成姓名验证后开始提问。</div>
          )}
          {verifyOpen && (
            <form className="grid gap-2.5" onSubmit={handleVerify}>
              <div className="grid gap-1.5">
                <label>姓名</label>
                <input value={nameInput} onChange={(e) => setNameInput(e.target.value)} placeholder="例如：刘昊然" />
              </div>
              <div className="grid gap-1.5">
                <label>班级（重名时必填）</label>
                <input value={classInput} onChange={(e) => setClassInput(e.target.value)} placeholder="例如：高二2403班" />
              </div>
              <button type="submit" className="border-none rounded-[10px] px-3 py-[9px] bg-accent text-white cursor-pointer" disabled={verifying}>
                {verifying ? '验证中…' : '确认身份'}
              </button>
              {verifyError && <div className="status err">{verifyError}</div>}
            </form>
          )}
          {verifiedStudent && (
            <div className="grid gap-1.5">
              <div className="text-xs text-muted">今日作业（{todayAssignment?.date || todayDate()}）</div>
              {assignmentLoading && <div className="text-xs text-muted">加载中...</div>}
              {assignmentError && <div className="text-xs text-muted">{assignmentError}</div>}
              {!assignmentLoading && !todayAssignment && !assignmentError && <div className="text-xs text-muted">今日暂无作业。</div>}
              {todayAssignment && (
                <>
                  <div className="text-xs text-muted">
                    作业编号：{todayAssignment.assignment_id || '-'} · 题数：{todayAssignment.question_count || 0}
                  </div>
                  {todayAssignment.meta?.target_kp?.length ? (
                    <div className="text-xs text-muted">知识点：{todayAssignment.meta.target_kp.join('，')}</div>
                  ) : null}
                  {todayAssignment.delivery?.files?.length ? (
                    <div className="grid gap-1.5">
                      {todayAssignment.delivery.files.map((file) => (
                        <a key={file.url} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[10px] bg-[#ecfaf5] text-[#0f766e] no-underline text-[13px] border border-[#cff0e6]" href={`${apiBase}${file.url}`} target="_blank" rel="noreferrer">
                          下载：{file.name}
                        </a>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-muted">在聊天中输入"开始今天作业"进入讨论。</div>
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